from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, responses

from .auth import auth
from .static import AuthStaticFiles

app = FastAPI()
static_dir = Path(__file__).parent.parent / "static"

app.mount("/static", AuthStaticFiles(directory=static_dir), name="static")


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
