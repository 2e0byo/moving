from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

static_dir = Path(__file__).parent.parent / "static"

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    return "foobar bas"


@app.post("/box")
def add_box(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    value: Annotated[Decimal, Form()],
    interior: Annotated[any, Form()],
):
    pass
