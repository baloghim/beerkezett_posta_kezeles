from dataclasses import dataclass
from datetime import date
from pathlib import Path


class EDPDError(Exception):
    """Felhasználónak megjeleníthető működési hiba."""


@dataclass(frozen=True)
class Document:
    archive: Path
    member: str
    name: str
    size: int
    crc: int


@dataclass(frozen=True)
class Day:
    date: date
    archives: tuple[Path, ...]
    documents: tuple[Document, ...]
    error: str = ""


@dataclass(frozen=True)
class Capabilities:
    overwrite: bool = True
    delete: bool = True
