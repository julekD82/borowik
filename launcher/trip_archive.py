"""Zapisywanie migawek analizy do listy porownawczej ("zapisane mapy",
plan 2026-09-26 borowik-saved-maps). Wywolywane przez launcher/launcher.pyw;
testowane osobno jako czysta logika bez GUI."""
from __future__ import annotations

import json
import re
from pathlib import Path

_POLISH = str.maketrans("ąćęłńóśźż", "acelnoszz")
_SYMBOLS = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Nazwa wpisana przez uzytkownika -> bezpieczna nazwa folderu. Usuwa
    wszystko poza [a-z0-9-], wiec ukosniki i '..' nigdy nie przejda dalej
    (bezpieczne przed path traversal). Pusty wynik dostaje falszywy slug
    "trip", zeby folder zawsze mial nazwe."""
    slug = _SYMBOLS.sub("-", name.strip().lower().translate(_POLISH)).strip("-")
    return slug or "trip"


def trip_id(name: str, day: str) -> str:
    return f"{slugify(name)}-{day}"


def read_index(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def write_index(index_path: Path, entries: list[dict]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def upsert_entry(entries: list[dict], entry: dict) -> list[dict]:
    return [entry, *[e for e in entries if e.get("id") != entry["id"]]]
