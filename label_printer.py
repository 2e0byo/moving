# ruff: noqa: T201
from subprocess import run
from tempfile import NamedTemporaryFile

import httpx

from moving.auth import passwords
from moving.constants import SERVER_NAME

server = f"https://{SERVER_NAME}/"
server = "http://localhost:8000/"

user, password = passwords()[0]
auth = httpx.BasicAuth(user, password)

events = server + "label-events"
label = server + "label?id={id}"
PRINTER = "DYMO_LabelWriter_310"


def print_label(id: int):
    data = httpx.get(label.format(id=id), auth=auth).raise_for_status().content
    with NamedTemporaryFile(mode="wb") as f:
        f.write(data)
        run(["lp", "-d", PRINTER, f.name])
    print("Done with label", id)


def subscribe():
    with httpx.stream("GET", events, auth=auth, timeout=None) as events_stream:
        for line in events_stream.iter_lines():
            print("Got label", line)
            id = int(line)
            print_label(id)

    print("Server closed connection; exiting")


if __name__ == "__main__":
    subscribe()
