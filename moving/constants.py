# ruff: noqa: ERA001
SERVER_NAME = "moving.2e0byo.co.uk"


def permalink(path: str) -> str:
    return f"https://{SERVER_NAME}/{path}"


# SERVER_NAME = "localhost:8000"


# def permalink(path: str) -> str:
#     return f"http://{SERVER_NAME}/{path}"
