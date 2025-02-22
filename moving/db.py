import sqlite3
from base64 import b64encode
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import UploadFile, responses
from pydantic import BaseModel, ConfigDict, Field

from moving.constants import permalink

MB = 1024 * 1024 * 1024
MAX_PIC_SIZE_BYTES = MB * 100
NonEmptyStr = Annotated[str, Field(min_length=1)]
DB_PATH = Path(__file__).parent.parent / "db.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreatePicture(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    extension: NonEmptyStr
    data: bytes = Field(max_length=MAX_PIC_SIZE_BYTES)

    @classmethod
    async def from_uploaded(cls, uploaded: UploadFile):
        filename = uploaded.filename
        assert filename
        return cls(extension=filename.split(".")[-1], data=await uploaded.read())


class Picture(CreatePicture):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    extension: NonEmptyStr
    data: bytes = Field(max_length=MAX_PIC_SIZE_BYTES)
    id: int

    def as_data(self) -> str:
        return f"data:image/{self.extension};base64,{b64encode(self.data).decode()}"

    def permalink(self) -> str:
        return permalink(f"image?id={self.id}")

    def as_response(self) -> responses.Response:
        return responses.Response(self.data, media_type=f"image/{self.extension}")


class CreateBox(BaseModel):
    title: NonEmptyStr
    description: NonEmptyStr
    value: int = Field(gt=0)
    interior: list[CreatePicture]
    user: NonEmptyStr
    timestamp: datetime = Field(default_factory=utc_now)


class Box(CreateBox):
    id: int

    @classmethod
    def build(cls, box: CreateBox, id: int):
        return cls.model_validate(box.model_dump() | {"id": id})


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    yield conn
    conn.commit()
    conn.close()


@dataclass
class DB:
    path: Path

    def connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def cursor(self):
        return self.connection().cursor()

    def fetchone(self, *args):
        row = self.cursor().execute(*args).fetchone()
        if not row:
            raise FileNotFoundError
        else:
            return row

    def fetchall(self, *args):
        rows = self.cursor().execute(*args).fetchall()
        if not rows:
            raise FileNotFoundError
        else:
            return rows

    def create(self) -> None:
        with connection(self.path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS box (
                   id            INTEGER PRIMARY KEY
                 , title         TEXT
                 , description   TEXT
                 , value         INTEGER
                 , user          TEXT
                 , timestamp     TEXT
                 , deleted       INTEGER
                )
                STRICT;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS label (
                   box_id   INTEGER PRIMARY KEY
                 , data BLOB
                )
                STRICT;
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS picture (
                   id         INTEGER PRIMARY KEY
                 , box_id     INTEGER
                 , extension  TEXT
                 , data       BLOB
                 , FOREIGN KEY(box_id) REFERENCES box(id)
                )
                STRICT;
            """
            )

    def add_box(self, box: CreateBox) -> Box:
        box_row = box.model_copy(update=dict(interiol=[])).model_dump(mode="json")

        with connection(self.path) as conn:
            cur = conn.cursor()
            resp = cur.execute(
                """INSERT INTO box VALUES (
                   null
                 , ?
                 , ?
                 , ?
                 , ?
                 , ?
                 , false
                ) RETURNING id
                """,
                [
                    box_row["title"],
                    box_row["description"],
                    box_row["value"],
                    box_row["user"],
                    box_row["timestamp"],
                ],
            )
            id = resp.fetchone()[0]
            for picture in box.interior:
                cur.execute(
                    """INSERT INTO picture VALUES (
                       null
                     , ?
                     , ?
                     , ?
                    )
                    """,
                    [
                        id,
                        picture.extension,
                        picture.data,
                    ],
                )

        return Box.build(box, id)

    def load_box(self, id: int) -> Box:
        row = self.fetchone("SELECT * FROM box WHERE id=?", [id])
        id, title, description, value, user, timestamp, deleted = row
        if deleted:
            raise FileNotFoundError
        # yeah we could do this all in 1 query...
        picture_rows = self.fetchall(
            "SELECT id, extension, data FROM picture WHERE box_id=?", [id]
        )
        pictures = [
            Picture(id=id, extension=extension, data=data)
            for (id, extension, data) in picture_rows
        ]
        return Box(
            id=id,
            title=title,
            description=description,
            value=value,
            user=user,
            timestamp=timestamp,
            interior=pictures,
        )

    def load_picture(self, id: int) -> Picture:
        id, extension, data = self.fetchone(
            "SELECT id, extension, data FROM picture WHERE id=?", [id]
        )
        return Picture(id=id, extension=extension, data=data)

    def n_boxes(self) -> int:
        return self.fetchone("SELECT COUNT(*) FROM box WHERE deleted=false")[0]

    def delete_box(self, id: int) -> None:
        with connection(self.path) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE box SET deleted=true WHERE id=?", [id])

    def boxes(self) -> list[Box]:
        # crude impl; we never have *that* many boxes...
        ids = self.fetchall("SELECT id from box where deleted=false")
        return [self.load_box(id[0]) for id in ids]

    def add_label(self, box_id: int, label: bytes) -> None:
        with connection(self.path) as conn:
            cur = conn.cursor()
            resp = cur.execute(
                "INSERT INTO label VALUES (?, ?) RETURNING box_id", [box_id, label]
            )
            assert resp.fetchone()[0] == box_id

    def load_label(self, box_id: int) -> bytes:
        return self.fetchone("SELECT data FROM label WHERE box_id=?", [box_id])[0]


@cache
def db() -> DB:
    db = DB(DB_PATH)
    db.create()
    return db
