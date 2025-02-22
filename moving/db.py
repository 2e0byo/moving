import sqlite3
from base64 import b64encode
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field

MB = 1024 * 1024 * 1024
MAX_PIC_SIZE_BYTES = MB * 100
NonEmptyStr = Annotated[str, Field(min_length=1)]
DB_PATH = Path(__file__).parent.parent / "db.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Picture(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    extension: NonEmptyStr
    data: bytes = Field(max_length=MAX_PIC_SIZE_BYTES)

    @classmethod
    async def from_uploaded(cls, uploaded: UploadFile):
        filename = uploaded.filename
        assert filename
        return cls(extension=filename.split(".")[-1], data=await uploaded.read())

    def as_data(self) -> str:
        return f"data:image/{self.extension};base64,{b64encode(self.data).decode()}"


class CreateBox(BaseModel):
    title: NonEmptyStr
    description: NonEmptyStr
    value: int = Field(gt=0)
    interior: list[Picture]
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

    def create(self) -> None:
        with connection(self.path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS box
                  (id INTEGER PRIMARY KEY, data TEXT, deleted INTEGER)
                STRICT;
                """
            )

    def add_box(self, box: CreateBox) -> Box:
        with connection(self.path) as conn:
            cur = conn.cursor()
            resp = cur.execute(
                "INSERT INTO box VALUES (null, ?, false) RETURNING id",
                [box.model_dump_json()],
            )
            id = resp.fetchone()[0]
        return Box.build(box, id)

    def load_box(self, id: int) -> Box:
        row = self.cursor().execute("SELECT * FROM box WHERE id=?", [id]).fetchone()
        if not row:
            raise FileNotFoundError
        id, data, deleted = row
        if deleted:
            raise FileNotFoundError
        return Box.build(CreateBox.model_validate_json(data), id)

    def n_boxes(self) -> int:
        return self.cursor().execute("SELECT COUNT(*) FROM box").fetchone()[0]

    def delete_box(self, id: int) -> None:
        self.cursor().execute("UPDATE box SET deleted=true WHERE id=?", [id])

    def boxes(self) -> list[Box]:
        boxes = (
            self.cursor()
            .execute("SELECT id, data FROM box WHERE deleted=false;")
            .fetchall()
        )
        return [
            Box.build(CreateBox.model_validate_json(data), id) for (id, data) in boxes
        ]


@cache
def db() -> DB:
    db = DB(DB_PATH)
    db.create()
    return db
