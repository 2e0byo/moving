from fastapi import Request
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from .auth import verify_request

# inspired by https://github.com/fastapi/fastapi/issues/858#issuecomment-876564020


class AuthStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        request = Request(scope, receive)
        await verify_request(request)
        return await super().__call__(scope, receive, send)
