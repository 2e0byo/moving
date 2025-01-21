from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, responses
from fastapi.staticfiles import StaticFiles

from .auth import auth

app = FastAPI()
static_dir = Path(__file__).parent.parent / "static"

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def homepage(_user: Annotated[str, Depends(auth)]) -> responses.RedirectResponse:
    return responses.RedirectResponse("/static/index.html")


@app.post("/box")
def add_box(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    value: Annotated[Decimal, Form()],
    interior: Annotated[Any, Form()],
):
    pass


if __name__ == "__main__":
    app()
