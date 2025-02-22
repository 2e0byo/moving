import asyncio
import threading
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile, responses
from jinja2 import Environment, PackageLoader, select_autoescape

from moving.constants import permalink
from moving.labels import Label

from .auth import auth
from .db import DB, Box, CreateBox, CreatePicture, db

app = FastAPI()
templates = Environment(loader=PackageLoader("moving"), autoescape=select_autoescape())

label_queue = asyncio.Queue(128)


@app.get("/")
def homepage(
    _user: Annotated[str, Depends(auth)],
    db: Annotated[DB, Depends(db)],
) -> responses.HTMLResponse:
    n_boxes = db.n_boxes()
    return responses.HTMLResponse(
        templates.get_template("index.html.jinja2").render(n_boxes=n_boxes)
    )


@app.get("/add-box")
def add_box(_user: Annotated[str, Depends(auth)]) -> responses.HTMLResponse:
    return responses.HTMLResponse(templates.get_template("add.html.jinja2").render())


@app.post("/box")
async def add_box_submit(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    value: Annotated[int, Form()],
    interior: Annotated[list[UploadFile], Form()],
    db: Annotated[DB, Depends(db)],
    user: Annotated[str, Depends(auth)],
) -> responses.HTMLResponse:
    create_box = CreateBox(
        title=title,
        description=description,
        value=value,
        interior=[
            await CreatePicture.from_uploaded(pic) for pic in interior if pic.filename
        ],
        user=user,
    )
    box = db.add_box(create_box)
    box_html = render_box(box)
    label = Label(qr_contents=permalink(f"box?id={box.id}"), no=box.id, title=box.title)
    tex = await label.compile()
    db.add_label(box.id, tex)
    await label_queue.put(box.id)
    html = templates.get_template("submitted.html.jinja2").render(
        box=box, box_html=box_html
    )
    return responses.HTMLResponse(html)


def render_box(box: Box, hide_buttons: bool = False) -> str:
    return templates.get_template("box.html.jinja2").render(
        box=box, hide_buttons=hide_buttons
    )


@app.get("/box")
def get_box(
    _user: Annotated[str, Depends(auth)],
    id: int,
    db: Annotated[DB, Depends(db)],
) -> responses.HTMLResponse:
    try:
        box = db.load_box(id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    else:
        return responses.HTMLResponse(
            templates.get_template("boxes.html.jinja2").render(boxes=[render_box(box)])
        )


@app.get("/boxes")
def boxes(
    _user: Annotated[str, Depends(auth)],
    db: Annotated[DB, Depends(db)],
) -> responses.HTMLResponse:
    template = templates.get_template("box.html.jinja2")
    boxes = [template.render(box=box) for box in db.boxes()]
    return responses.HTMLResponse(
        templates.get_template("boxes.html.jinja2").render(boxes=boxes)
    )


@app.get("/label")
def get_label(
    _user: Annotated[str, Depends(auth)],
    db: Annotated[DB, Depends(db)],
    id: int,
) -> responses.Response:
    try:
        label = db.load_label(id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Label not found")
    else:
        return responses.Response(label, media_type="application/pdf")


@app.get("/image")
def get_image(
    _user: Annotated[str, Depends(auth)],
    db: Annotated[DB, Depends(db)],
    id: int,
) -> responses.Response:
    try:
        img = db.load_picture(id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    else:
        return img.as_response()


LABEL_LOCK = threading.Lock()


@app.get("/label-events")
def label_events(
    _user: Annotated[str, Depends(auth)],
) -> responses.StreamingResponse:
    if LABEL_LOCK.acquire(blocking=False):
        # Note this isn't full SSE; it's just ids linewise
        async def iter_labels():
            while True:
                yield f"{await label_queue.get()}\n"

        return responses.StreamingResponse(
            iter_labels(), media_type="text/event-stream"
        )
    else:
        raise HTTPException(
            status_code=409,
            detail="Only one label stream can be active at any one time, "
            "and one is already ongoing.",
        )


@app.get("/reprint")
async def reprint(
    _user: Annotated[str, Depends(auth)],
    id: int,
):
    await label_queue.put(id)
    template = templates.get_template("reprinted.html.jinja2")
    return responses.HTMLResponse(template.render(id=id))


@app.get("/delete")
async def delete_form(
    _user: Annotated[str, Depends(auth)],
    id: int,
    db: Annotated[DB, Depends(db)],
):
    try:
        box = db.load_box(id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Box not found")
    box_html = render_box(box, hide_buttons=True)
    template = templates.get_template("delete.html.jinja2")
    return responses.HTMLResponse(template.render(box=box, box_html=box_html))


@app.post("/delete")
async def delete(
    _user: Annotated[str, Depends(auth)],
    id: int,
    db: Annotated[DB, Depends(db)],
):
    db.delete_box(id)
    template = templates.get_template("deleted.html.jinja2")
    return responses.HTMLResponse(template.render(id=id))


if __name__ == "__main__":
    app()
