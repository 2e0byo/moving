from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile, responses
from jinja2 import Environment, PackageLoader, select_autoescape

from .auth import auth
from .db import DB, CreateBox, Picture, db
from .static import AuthStaticFiles

app = FastAPI()
static_dir = Path(__file__).parent.parent / "static"
templates = Environment(loader=PackageLoader("moving"), autoescape=select_autoescape())

app.mount("/static", AuthStaticFiles(directory=static_dir), name="static")


@app.get("/")
def homepage(
    _user: Annotated[str, Depends(auth)],
    db: Annotated[DB, Depends(db)],
) -> responses.HTMLResponse:
    n_boxes = db.n_boxes()
    return responses.HTMLResponse(
        templates.get_template("index.html.jinja2").render(n_boxes=n_boxes)
    )
    return responses.RedirectResponse("/static/index.html")


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
        interior=[await Picture.from_uploaded(pic) for pic in interior if pic.filename],
        user=user,
    )
    box = db.add_box(create_box)
    box_html = load_box(box.id, db)
    html = templates.get_template("submitted.html.jinja2").render(
        box=box, box_html=box_html
    )
    return responses.HTMLResponse(html)


def load_box(
    id: int,
    db: DB,
) -> str:
    box = db.load_box(id)
    return templates.get_template("box.html.jinja2").render(box=box)


@app.get("/box")
def get_box(
    _user: Annotated[str, Depends(auth)],
    id: int,
    db: Annotated[DB, Depends(db)],
) -> responses.HTMLResponse:
    try:
        box = load_box(id, db)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    else:
        return responses.HTMLResponse(
            templates.get_template("boxes.html.jinja2").render(boxes=[box])
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


if __name__ == "__main__":
    app()
