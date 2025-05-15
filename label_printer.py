# ruff: noqa: T201
from subprocess import run
from tempfile import NamedTemporaryFile

import httpx
from typer import Typer

from moving.auth import passwords
from moving.constants import SERVER_NAME

app = Typer()

server = f"https://{SERVER_NAME}/"

user, password = passwords()[0]
auth = httpx.BasicAuth(user, password)

events = server + "label-events"
label = server + "label?id={id}"
PRINTER = "DYMO_LabelWriter_310"


@app.command()
def print_label(id: int):
    data = httpx.get(label.format(id=id), auth=auth).raise_for_status().content
    with NamedTemporaryFile(mode="wb") as f:
        f.write(data)
        run(["lp", "-d", PRINTER, f.name])
    print("Done with label", id)


def subscribe():
    print("connecting")
    with httpx.stream("GET", events, auth=auth, timeout=None) as events_stream:
        print("waiting for line")
        for line in events_stream.iter_lines():
            print("Got label", line)
            id = int(line)
            print_label(id)

    print("Server closed connection; exiting")


if __name__ == "__main__":
    app()
