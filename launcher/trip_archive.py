"""Zapisywanie migawek analizy do listy porownawczej ("zapisane mapy",
plan 2026-09-26 borowik-saved-maps). Wywolywane przez launcher/launcher.pyw;
testowane osobno jako czysta logika bez GUI."""
from __future__ import annotations

import json
import re
from pathlib import Path

_POLISH = str.maketrans("ąćęłńóśźż", "acelnoszz")
_SYMBOLS = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LENGTH = 60


def slugify(name: str) -> str:
    """Nazwa wpisana przez uzytkownika -> bezpieczna nazwa folderu. Usuwa
    wszystko poza [a-z0-9-], wiec ukosniki i '..' nigdy nie przejda dalej
    (bezpieczne przed path traversal). Pusty wynik dostaje falszywy slug
    "trip", zeby folder zawsze mial nazwe. Przycieta do 60 znakow, zeby
    bardzo dluga nazwa nie przekroczyla MAX_PATH w polaczeniu ze sciezka
    repo i nazwami plikow w srodku (review finding, plan
    2026-09-26-borowik-saved-maps)."""
    slug = _SYMBOLS.sub("-", name.strip().lower().translate(_POLISH)).strip("-")
    slug = slug[:_MAX_SLUG_LENGTH].strip("-")
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
    """Atomic write (temp file + rename, same pattern as
    frontend/scripts/sync-data.mjs) so a crash mid-write never leaves a
    half-written index.json behind."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = index_path.with_suffix(index_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp_path.replace(index_path)


def upsert_entry(entries: list[dict], entry: dict) -> list[dict]:
    return [entry, *[e for e in entries if e.get("id") != entry["id"]]]


import shutil
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class TripMeta:
    id: str
    name: str
    radius_km: float
    day: str
    lat: float
    lon: float
    saved_at: str


def read_day(scores_path: Path) -> str:
    """Pierwszy rekord scores.json -> jego pole "day". Brak pliku, pusta
    lista lub zly JSON = brak zsynchronizowanej analizy do zapisania."""
    try:
        data = json.loads(scores_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Brak zsynchronizowanych danych do zapisania. "
            "Uruchom najpierw analize i podglad."
        ) from exc
    if (
        not isinstance(data, list)
        or not data
        or not isinstance(data[0], dict)
        or "day" not in data[0]
    ):
        raise ValueError(
            "Brak zsynchronizowanych danych do zapisania. "
            "Uruchom najpierw analize i podglad."
        )
    return data[0]["day"]


TRIP_FILES = ["scores.json", "stands.geojson", "regions.json", "regions_bez_presji.json", "details.json", "conditions.json",
              "manifest.json", "access_points.json", "forest_roads.json"]


def copy_trip_files(data_dir: Path, dest_dir: Path) -> list[str]:
    """Copies whichever of TRIP_FILES exist in data_dir into dest_dir, and
    removes any TRIP_FILES entry in dest_dir that ISN'T present in
    data_dir -- otherwise re-saving over an existing trip whose new source
    lacks e.g. regions.json would leave the old snapshot's regions.json
    behind, silently mixing old regions with new stands (review finding,
    plan 2026-09-26-borowik-saved-maps)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in TRIP_FILES:
        src = data_dir / name
        dest = dest_dir / name
        if src.exists():
            shutil.copy2(src, dest)
            copied.append(name)
        else:
            dest.unlink(missing_ok=True)
    return copied


def trip_exists(trips_dir: Path, tid: str) -> bool:
    return (trips_dir / tid).exists()


def _backup_if_corrupted(index_path: Path, now: datetime) -> None:
    """read_index() silently returns [] for a corrupted/wrong-shape
    index.json -- correct for the browser (nothing to show), but wrong for
    save_trip's read-modify-write: writing back would discard whatever was
    in the file. Back it up first, so it's recoverable (review finding,
    plan 2026-09-26-borowik-saved-maps)."""
    if not index_path.exists():
        return
    raw = index_path.read_text(encoding="utf-8")
    try:
        valid = isinstance(json.loads(raw), list)
    except json.JSONDecodeError:
        valid = False
    if not valid:
        backup_path = index_path.with_name(
            f"{index_path.name}.bak-{now.strftime('%Y%m%dT%H%M%S')}"
        )
        backup_path.write_text(raw, encoding="utf-8")


def save_trip(data_dir: Path, trips_dir: Path, name: str, radius_km: float,
              lat: float, lon: float, now: datetime | None = None) -> TripMeta:
    """Pelny zapis: odczyt dnia, kopia plikow, aktualizacja index.json.
    Rzuca ValueError, jesli data_dir/scores.json nie istnieje/jest pusty."""
    now = now or datetime.now().astimezone()
    day = read_day(data_dir / "scores.json")
    tid = trip_id(name, day)
    copy_trip_files(data_dir, trips_dir / tid)
    meta = TripMeta(
        id=tid, name=name.strip(), radius_km=radius_km, day=day, lat=lat, lon=lon,
        saved_at=now.isoformat(timespec="seconds"),
    )
    index_path = trips_dir / "index.json"
    _backup_if_corrupted(index_path, now)
    write_index(index_path, upsert_entry(read_index(index_path), asdict(meta)))
    return meta
