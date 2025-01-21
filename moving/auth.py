"""Toy auth."""

import secrets
from json import loads
from pathlib import Path
from typing import Annotated, Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def passwords() -> list[tuple[bytes, bytes]]:
    data = loads((Path(__file__).parent.parent / ".secrets.json").read_text())
    # of course we should store hashes, but this isn't secure anyway
    return [(u.encode(), p.encode()) for (u, p) in data]


def index[T](haystack: Iterable[T], needle: T) -> int:
    """Non-short-circuiting 'contant time' index."""
    pos = -1
    for i, x in enumerate(haystack):
        if x == needle:
            pos = i
    return pos


def auth(
    given: Annotated[HTTPBasicCredentials, Depends(security)],
    known: Annotated[list[tuple[bytes, bytes]], Depends(passwords)],
) -> str:
    username = given.username.encode()
    password = given.password.encode()
    usernames = [x[0] for x in known]
    passwords = [x[1] for x in known]
    # Attempt at a constant time algo, for fun
    matching_username_index = index(
        [secrets.compare_digest(username, u) for u in usernames], True
    )
    matching_password_index = index(
        [secrets.compare_digest(password, p) for p in passwords], True
    )
    # both failed?
    possible = (matching_username_index + matching_password_index) >= 0
    # correct pair?
    matches = matching_username_index == matching_password_index
    if (int(possible) + int(matches)) == 2:
        return given.username
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )


__all__ = [auth]
