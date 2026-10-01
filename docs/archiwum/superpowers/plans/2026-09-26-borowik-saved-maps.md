# Borowik — zapisane mapy (lista do porównywania analiz) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user save the currently-active analysis (map + stand list) under a name from the launcher, and switch between saved analyses in the browser via a panel above the map, to compare them — without re-running the pipeline.

**Architecture:** Full-data snapshots on disk, not browser storage. A new pure Python module (`launcher/trip_archive.py`) copies the four already-synced files (`scores.json`, `stands.geojson`, optional `regions.json`/`details.json`) into `frontend/public/data/trips/<id>/` and appends a metadata entry to `frontend/public/data/trips/index.json`; `launcher/launcher.pyw` gets a "Nazwa miejsca" field and a "Zapisz do listy" button that call it. The frontend's `loadData()` gains a `basePath` parameter so the exact same load/parse/render path already used for the live dataset can point at a saved trip's folder instead; a new dropdown panel lists saved trips and switches between them.

**Tech Stack:** Python 3.12 (stdlib only: `json`, `re`, `shutil`, `dataclasses`, `pathlib`, `datetime`), pytest, existing `tkinter` launcher; TypeScript frontend (`frontend/src/model.ts`, `main.ts`, `style.css`), Vitest.

**Spec:** `docs/archiwum/superpowers/specs/2026-09-26-borowik-saved-maps-design.md`

## Global Constraints

- Saved snapshots are frozen copies, never regenerated on read — switching a saved trip must never trigger a pipeline run or overwrite the trip's own files.
- Storage is plain files under `frontend/public/data/trips/` (already covered by `frontend/.gitignore`'s `public/data/*` — no `.gitignore` change needed), never `localStorage`/IndexedDB.
- The place name is typed by hand in the launcher; radius comes from the launcher's existing radius field; the day comes from `scores.json`'s own `day` field — no change to `pipeline/` is needed or in scope.
- Saving is one explicit launcher button ("Zapisz do listy"), never automatic on every pipeline run.
- The browser always starts on the live ("Aktualna") dataset from `data/`; the saved-trips panel is additive, never a blocking startup screen.
- Deleting/renaming a saved trip from the app is out of scope (YAGNI) — the user removes a folder in Explorer if needed.
- JSON field names follow this repo's existing snake_case convention throughout (`stand_id`, `d_park_m`, `radius_km`, ...) — no camelCase.
- Run backend tests with `.venv/Scripts/python.exe -m pytest -q` from the repo root; run frontend tests with `npm.cmd test` and `npm.cmd run build` from `frontend/`.

## Review Focus

- "Zapisz do listy" clicked with no synced analysis yet (no `frontend/public/data/scores.json`) — must show a clear error and create nothing, not crash or leave a broken `trips/` entry.
- Saving the same name + day a second time without confirming the overwrite prompt — must leave the existing saved trip completely untouched.
- `frontend/public/data/trips/index.json` corrupted or hand-edited into the wrong shape — the browser must fall back to an empty saved-trips list, not fail to load the live "Aktualna" view too.
- A place name containing characters unsafe for a folder name (slashes, `..`, only whitespace, Polish diacritics) — the generated folder id must be safe, non-empty, and stay inside `trips/` (no path traversal).
- A saved trip whose files are incomplete/corrupted — selecting it in the browser must show the existing load-error banner, not a blank page, and must not corrupt the "Aktualna" view.

---

## Task 1: `launcher/trip_archive.py` — naming and index helpers

**Files:**
- Create: `launcher/trip_archive.py`
- Test: `tests/test_trip_archive.py`

**Interfaces:**
- Produces: `slugify(name: str) -> str`, `trip_id(name: str, day: str) -> str`, `read_index(index_path: Path) -> list[dict]`, `write_index(index_path: Path, entries: list[dict]) -> None`, `upsert_entry(entries: list[dict], entry: dict) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trip_archive.py
import json

from launcher.trip_archive import slugify, trip_id, read_index, write_index, upsert_entry


def test_slugify_lowercases_and_transliterates_polish_diacritics():
    assert slugify("Będziemyśl") == "bedziemysl"


def test_slugify_collapses_symbols_and_whitespace_to_single_dashes():
    assert slugify("  Nadl.  Kędzierzyn ! ") == "nadl-kedzierzyn"


def test_slugify_strips_path_traversal_attempts():
    assert slugify("../../etc/passwd") == "etc-passwd"
    assert ".." not in slugify("../../etc/passwd")
    assert "/" not in slugify("a/b\\c")


def test_slugify_empty_or_symbols_only_falls_back_to_trip():
    assert slugify("") == "trip"
    assert slugify("   ") == "trip"
    assert slugify("###") == "trip"


def test_trip_id_combines_slug_and_day():
    assert trip_id("Będziemyśl", "2026-09-26") == "bedziemysl-2026-09-26"


def test_read_index_missing_file_is_empty_list(tmp_path):
    assert read_index(tmp_path / "index.json") == []


def test_read_index_corrupted_json_is_empty_list(tmp_path):
    path = tmp_path / "index.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert read_index(path) == []


def test_read_index_wrong_shape_is_empty_list(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert read_index(path) == []


def test_write_index_then_read_index_roundtrips(tmp_path):
    path = tmp_path / "trips" / "index.json"
    entries = [{"id": "a-2026-09-26", "name": "A"}]
    write_index(path, entries)
    assert read_index(path) == entries


def test_upsert_entry_prepends_new_entry():
    entries = [{"id": "old", "name": "Old"}]
    result = upsert_entry(entries, {"id": "new", "name": "New"})
    assert result == [{"id": "new", "name": "New"}, {"id": "old", "name": "Old"}]


def test_upsert_entry_replaces_existing_entry_with_same_id_and_keeps_order():
    entries = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    result = upsert_entry(entries, {"id": "a", "name": "A2"})
    assert result == [{"id": "a", "name": "A2"}, {"id": "b", "name": "B"}]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'launcher.trip_archive'`.

- [ ] **Step 3: Implement**

```python
# launcher/trip_archive.py
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add launcher/trip_archive.py tests/test_trip_archive.py
git commit -m "feat: trip_archive naming/index helpers for saved-maps list (plan step 1)"
```

---

## Task 2: `launcher/trip_archive.py` — reading the day, copying files, full save

**Files:**
- Modify: `launcher/trip_archive.py` (append)
- Test: `tests/test_trip_archive.py` (append)

**Interfaces:**
- Consumes: Task 1 (`trip_id`, `read_index`, `write_index`, `upsert_entry`).
- Produces: `TripMeta` (frozen-shape dataclass: `id, name, radius_km, day, lat, lon, saved_at`), `read_day(scores_path: Path) -> str` (raises `ValueError` with a user-facing Polish message if missing/empty/invalid), `TRIP_FILES: list[str]`, `copy_trip_files(data_dir: Path, dest_dir: Path) -> list[str]`, `trip_exists(trips_dir: Path, tid: str) -> bool`, `save_trip(data_dir: Path, trips_dir: Path, name: str, radius_km: float, lat: float, lon: float, now: datetime | None = None) -> TripMeta`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trip_archive.py (append)
import json
from datetime import datetime, timezone

import pytest

from launcher.trip_archive import (
    TripMeta, read_day, TRIP_FILES, copy_trip_files, trip_exists, save_trip,
)


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_read_day_returns_day_of_first_record(tmp_path):
    path = tmp_path / "scores.json"
    _write_json(path, [{"stand_id": "A", "day": "2026-09-26"}])
    assert read_day(path) == "2026-09-26"


def test_read_day_missing_file_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        read_day(tmp_path / "scores.json")


def test_read_day_empty_list_raises_value_error(tmp_path):
    path = tmp_path / "scores.json"
    _write_json(path, [])
    with pytest.raises(ValueError):
        read_day(path)


def test_read_day_corrupted_json_raises_value_error(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_day(path)


def test_copy_trip_files_copies_only_existing_files(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "scores.json").write_text("[]", encoding="utf-8")
    (data_dir / "stands.geojson").write_text("{}", encoding="utf-8")
    # regions.json / details.json intentionally absent (optional files)
    dest = tmp_path / "trips" / "some-id"
    copied = copy_trip_files(data_dir, dest)
    assert sorted(copied) == ["scores.json", "stands.geojson"]
    assert (dest / "scores.json").read_text(encoding="utf-8") == "[]"
    assert not (dest / "regions.json").exists()


def test_copy_trip_files_copies_optional_files_when_present(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in TRIP_FILES:
        (data_dir / name).write_text("x", encoding="utf-8")
    dest = tmp_path / "trips" / "some-id"
    copied = copy_trip_files(data_dir, dest)
    assert sorted(copied) == sorted(TRIP_FILES)


def test_trip_exists_false_for_missing_folder(tmp_path):
    assert trip_exists(tmp_path / "trips", "nope") is False


def test_trip_exists_true_for_existing_folder(tmp_path):
    trips_dir = tmp_path / "trips"
    (trips_dir / "here").mkdir(parents=True)
    assert trip_exists(trips_dir, "here") is True


def test_save_trip_copies_files_and_writes_index_entry(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    (data_dir / "stands.geojson").write_text("{}", encoding="utf-8")
    trips_dir = tmp_path / "data" / "trips"
    now = datetime(2026, 9, 26, 18, 4, 12, tzinfo=timezone.utc)

    meta = save_trip(data_dir, trips_dir, "Będziemyśl", 20.0, 50.0555, 21.7889, now=now)

    assert meta == TripMeta(
        id="bedziemysl-2026-09-26", name="Będziemyśl", radius_km=20.0,
        day="2026-09-26", lat=50.0555, lon=21.7889,
        saved_at="2026-09-26T18:04:12+00:00",
    )
    assert (trips_dir / "bedziemysl-2026-09-26" / "scores.json").exists()
    index = json.loads((trips_dir / "index.json").read_text(encoding="utf-8"))
    assert index == [
        {"id": "bedziemysl-2026-09-26", "name": "Będziemyśl", "radius_km": 20.0,
         "day": "2026-09-26", "lat": 50.0555, "lon": 21.7889,
         "saved_at": "2026-09-26T18:04:12+00:00"}
    ]


def test_save_trip_raises_when_no_synced_data(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with pytest.raises(ValueError):
        save_trip(data_dir, tmp_path / "trips", "X", 20.0, 50.0, 21.0)


def test_save_trip_overwrites_existing_entry_with_same_id(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    trips_dir = tmp_path / "data" / "trips"
    save_trip(data_dir, trips_dir, "X", 20.0, 50.0, 21.0)
    save_trip(data_dir, trips_dir, "X", 25.0, 50.0, 21.0)
    index = json.loads((trips_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 1
    assert index[0]["radius_km"] == 25.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q`
Expected: FAIL — `ImportError: cannot import name 'TripMeta'`.

- [ ] **Step 3: Implement (append to `launcher/trip_archive.py`)**

```python
# launcher/trip_archive.py (append)
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
    if not isinstance(data, list) or not data or "day" not in data[0]:
        raise ValueError(
            "Brak zsynchronizowanych danych do zapisania. "
            "Uruchom najpierw analize i podglad."
        )
    return data[0]["day"]


TRIP_FILES = ["scores.json", "stands.geojson", "regions.json", "details.json"]


def copy_trip_files(data_dir: Path, dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in TRIP_FILES:
        src = data_dir / name
        if src.exists():
            shutil.copy2(src, dest_dir / name)
            copied.append(name)
    return copied


def trip_exists(trips_dir: Path, tid: str) -> bool:
    return (trips_dir / tid).exists()


def save_trip(data_dir: Path, trips_dir: Path, name: str, radius_km: float,
              lat: float, lon: float, now: datetime | None = None) -> TripMeta:
    """Pelny zapis: odczyt dnia, kopia plikow, aktualizacja index.json.
    Rzuca ValueError, jesli data_dir/scores.json nie istnieje/jest pusty."""
    day = read_day(data_dir / "scores.json")
    tid = trip_id(name, day)
    copy_trip_files(data_dir, trips_dir / tid)
    meta = TripMeta(
        id=tid, name=name.strip(), radius_km=radius_km, day=day, lat=lat, lon=lon,
        saved_at=(now or datetime.now().astimezone()).isoformat(timespec="seconds"),
    )
    index_path = trips_dir / "index.json"
    write_index(index_path, upsert_entry(read_index(index_path), asdict(meta)))
    return meta
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q`
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add launcher/trip_archive.py tests/test_trip_archive.py
git commit -m "feat: read_day/copy_trip_files/save_trip for saved-maps list (plan step 2)"
```

---

## Task 3: Launcher GUI — "Nazwa miejsca" field + "Zapisz do listy" button

**Files:**
- Modify: `launcher/launcher.pyw`

**Interfaces:**
- Consumes: Task 2 (`launcher.trip_archive.read_day`, `trip_id`, `trip_exists`, `save_trip`, `TripMeta`).

No automated test — this file has no existing test coverage (GUI wiring, matches current practice); verified manually in this task's last step.

- [ ] **Step 1: Add the import and `sys.path` fix-up**

`launcher.pyw` is normally launched by double-clicking (its own directory becomes `sys.path[0]`, not the repo root), so `launcher.trip_archive` needs the repo root added explicitly before the import works as a package.

In `launcher/launcher.pyw`, right after the existing `REPO_ROOT = Path(__file__).resolve().parent.parent` line, add:

```python
sys.path.insert(0, str(REPO_ROOT))
from launcher.trip_archive import read_day, save_trip, trip_exists, trip_id
```

- [ ] **Step 2: Add "Nazwa miejsca" to the default config and the form**

In `DEFAULT_CONFIG`, add a `place` key:

```python
DEFAULT_CONFIG = {"lat": "53.1509", "lon": "16.7382", "radius_km": "25", "place": ""}
```

In `LauncherApp.__init__`, right after the `radius_var` `Entry` block (after `ttk.Entry(form, textvariable=self.radius_var, ...).grid(...)`), add a new row:

```python
        ttk.Label(form, text="Nazwa miejsca:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.place_var = tk.StringVar(value=config["place"])
        ttk.Entry(form, textvariable=self.place_var, width=30).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=5, pady=(6, 0)
        )
```

- [ ] **Step 3: Add the "Zapisz do listy" button**

Right after `self.stop_button = ttk.Button(buttons, text="Zatrzymaj serwer", ...)` and its `.pack(...)` line, add:

```python
        self.save_trip_button = ttk.Button(
            buttons, text="Zapisz do listy", command=self.on_save_trip
        )
        self.save_trip_button.pack(side="left", padx=8)
```

- [ ] **Step 4: Implement `on_save_trip`**

Add this method to `LauncherApp` (near `on_run_preview`):

```python
    def on_save_trip(self) -> None:
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        name = self.place_var.get().strip()
        if not name:
            messagebox.showerror("Blad", "Podaj nazwe miejsca przed zapisem.")
            return
        values = self.validate_inputs()
        if values is None:
            return
        lat, lon, radius = values
        data_dir = FRONTEND_DIR / "public" / "data"
        trips_dir = data_dir / "trips"
        try:
            day = read_day(data_dir / "scores.json")
        except ValueError as exc:
            messagebox.showerror("Blad", str(exc))
            return
        tid = trip_id(name, day)
        if trip_exists(trips_dir, tid) and not messagebox.askyesno(
            "Potwierdzenie",
            f"Wpis '{name}' z dnia {day} juz istnieje. Nadpisac?",
        ):
            self.log("Zapis anulowany (wpis juz istnieje).")
            return
        meta = save_trip(data_dir, trips_dir, name, radius, lat, lon)
        save_config({
            "lat": str(lat), "lon": str(lon), "radius_km": str(radius), "place": name,
        })
        self.log(f"Zapisano '{meta.name} - {meta.radius_km:g}km - {meta.day}' do listy.")
        self.set_status("Zapisano do listy zapisanych map.")
```

- [ ] **Step 5: Manual verification**

1. Run `pythonw.exe launcher/launcher.pyw` (or double-click it).
2. Run an analysis ("Uruchom analize i podglad") so `frontend/public/data/scores.json` exists.
3. Type a place name (e.g. "Test"), click "Zapisz do listy" — confirm the log line and status bar show the saved label, and `frontend/public/data/trips/test-<day>/` now contains `scores.json`/`stands.geojson`.
4. Click "Zapisz do listy" again with the same name — confirm the overwrite dialog appears; click "Nie" and confirm nothing changed (check the folder's mtime or log); click again and choose "Tak", confirm it re-saves.
5. Clear `place` field to empty, click "Zapisz do listy" — confirm the "Podaj nazwe miejsca" error and no folder is created.
6. Manually delete/rename `frontend/public/data/scores.json`, click "Zapisz do listy" with a name filled in — confirm the "Brak zsynchronizowanych danych" error and no folder is created.

- [ ] **Step 6: Commit**

```bash
git add launcher/launcher.pyw
git commit -m "feat: launcher place-name field and Zapisz do listy button (plan step 3)"
```

---

## Task 4: Frontend data layer — `TripMeta`, `parseTrips`, `formatTripLabel`, `loadTrips`, `loadData(basePath)`

**Files:**
- Modify: `frontend/src/model.ts`
- Test: `frontend/src/model.test.ts`

**Interfaces:**
- Consumes: nothing new (uses this file's existing private `object`/`date`/`finite` helpers).
- Produces: `TripMeta = { id: string; name: string; radius_km: number; day: string; lat: number; lon: number; saved_at: string }`, `parseTrips(raw: unknown): TripMeta[]`, `formatTripLabel(trip: TripMeta): string`, `loadTrips(): Promise<TripMeta[]>`, `loadData(basePath: string = "data/")` (existing function, gains the parameter — same return shape as today).

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/model.test.ts (append)
import { parseTrips, formatTripLabel } from "./model";
import type { TripMeta } from "./model";

const trip = (overrides: Partial<TripMeta> = {}): TripMeta => ({
  id: "bedziemysl-2026-09-26",
  name: "Będziemyśl",
  radius_km: 20,
  day: "2026-09-26",
  lat: 50.0555,
  lon: 21.7889,
  saved_at: "2026-09-26T18:04:12+02:00",
  ...overrides,
});

describe("saved trips", () => {
  it("formats a trip as name - radius - short date", () => {
    expect(formatTripLabel(trip())).toBe("Będziemyśl - 20km - 26.09");
  });
  it("parses a well-formed trips list", () => {
    expect(parseTrips([trip()])).toEqual([trip()]);
  });
  it("returns an empty list for a non-array payload", () => {
    expect(parseTrips({ not: "an array" })).toEqual([]);
    expect(parseTrips(null)).toEqual([]);
  });
  it("filters out entries missing required fields, keeping valid ones", () => {
    const bad = { ...trip(), id: undefined };
    expect(parseTrips([trip(), bad])).toEqual([trip()]);
  });
  it("filters out an entry with a malformed day", () => {
    const bad = trip({ day: "26-09-2026" });
    expect(parseTrips([bad])).toEqual([]);
  });
  it("filters out an entry with a non-finite radius or coordinate", () => {
    expect(parseTrips([trip({ radius_km: NaN })])).toEqual([]);
    expect(parseTrips([trip({ lat: Infinity })])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm.cmd test`
Expected: FAIL — `formatTripLabel`/`parseTrips`/`TripMeta` not exported from `./model`.

- [ ] **Step 3: Implement (append to `frontend/src/model.ts`, after the existing `loadData` function)**

```typescript
// frontend/src/model.ts (append)
export type TripMeta = {
  id: string;
  name: string;
  radius_km: number;
  day: string;
  lat: number;
  lon: number;
  saved_at: string;
};
export function formatTripLabel(trip: TripMeta): string {
  const [, month, day] = trip.day.split("-");
  return `${trip.name} - ${trip.radius_km}km - ${day}.${month}`;
}
export function parseTrips(raw: unknown): TripMeta[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (t): t is TripMeta =>
      object(t) &&
      typeof t.id === "string" &&
      t.id.length > 0 &&
      typeof t.name === "string" &&
      t.name.length > 0 &&
      finite(t.radius_km) &&
      date(t.day) &&
      finite(t.lat) &&
      finite(t.lon) &&
      typeof t.saved_at === "string",
  );
}
// index.json is optional and, unlike scores/stands/regions/details, is
// appended to incrementally by the launcher over time -- a single bad
// entry (or a missing/corrupted file) means "fewer saved trips to show",
// never a load failure for the live analysis. Same tolerant pattern as
// storage.ts's readSaved, not parseData's throw-on-invalid pattern.
export async function loadTrips(): Promise<TripMeta[]> {
  try {
    const response = await fetch(
      `${import.meta.env.BASE_URL}data/trips/index.json`,
      { cache: "no-cache", signal: AbortSignal.timeout(20000) },
    );
    if (!response.ok) return [];
    return parseTrips(await response.json());
  } catch {
    return [];
  }
}
```

- [ ] **Step 4: Modify `loadData` to accept a `basePath`**

In `frontend/src/model.ts`, change the existing `loadData` function signature and its three `fetch()` URLs (the pattern repeats three times: the `Promise.all` block, the `regionsResponse` fetch, and the `detailsResponse` fetch):

```typescript
export async function loadData(basePath: string = "data/") {
  const [scoresRaw, standsRaw] = await Promise.all(
    ["scores.json", "stands.geojson"].map(async (file) => {
      const response = await fetch(`${import.meta.env.BASE_URL}${basePath}${file}`, {
        cache: "no-cache",
        signal: AbortSignal.timeout(20000),
      });
```

(leave the rest of that `map` callback unchanged). Then in the `regionsResponse` fetch:

```typescript
  const regionsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}regions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
```

And in the `detailsResponse` fetch:

```typescript
  const detailsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}details.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
```

No other line in `loadData` changes; the default parameter value `"data/"` means every existing caller (`main.ts`'s current `await loadData()` call, and every existing test that exercises `parseData` directly) keeps working unchanged.

- [ ] **Step 5: Run to verify tests pass**

Run: `cd frontend && npm.cmd test`
Expected: all tests pass, including the new "saved trips" describe block.

- [ ] **Step 6: Typecheck and build**

Run: `cd frontend && npm.cmd run build`
Expected: succeeds (no TypeScript errors) — `main.ts` still calls `loadData()` with zero arguments at this point, which is valid because of the default parameter.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/model.ts frontend/src/model.test.ts
git commit -m "feat: TripMeta/parseTrips/loadTrips and basePath-aware loadData (plan step 4)"
```

---

## Task 5: Frontend UI — "Zapisane mapy" panel and switching

**Files:**
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/style.css`

**Interfaces:**
- Consumes: Task 4 (`TripMeta`, `loadTrips`, `formatTripLabel`, `loadData(basePath)`).

No new automated test: this task wires already-tested pure functions into the DOM rendering path that `main.ts` already leaves untested (there is no existing test file for `main.ts`'s DOM wiring — `model.test.ts` covers only the pure `model.ts` functions). Verified manually in this task's last step.

- [ ] **Step 1: Add the panel markup**

In `frontend/src/main.ts`, in the big template literal assigned to `#app` (the one starting `document.querySelector<HTMLDivElement>("#app")!.innerHTML = \``), insert a new `<section>` between the existing `<section id="conditions" ...>...</section>` line and the `<section class="workspace" ...>` line:

```typescript
    <section id="trips-bar" class="trips-bar" aria-label="Zapisane mapy"><label for="trips-select">${icon("bookmark")}<span>Zapisane mapy</span></label><select id="trips-select"><option value="">Aktualna</option></select></section>
```

- [ ] **Step 2: Add `.trips-bar` styling**

In `frontend/src/style.css`, right after the existing `.conditions { ... }` rule block, add:

```css
.trips-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--soft);
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 14px;
}
.trips-bar label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--green);
  flex-shrink: 0;
}
.trips-bar svg {
  width: 18px;
  height: 18px;
}
.trips-bar select {
  flex: 1;
  max-width: 320px;
}
```

- [ ] **Step 3: Add module state and `formatTripLabel`/`loadTrips` imports**

In `frontend/src/main.ts`, extend the existing `import { ... } from "./model"` block with `loadTrips, formatTripLabel`, and the existing `import type { ... } from "./model"` block with `TripMeta`. Then, near the other module-level `let` declarations (next to `let loadError = "";`), add:

```typescript
let savedTrips: TripMeta[] = [];
let currentTripId: string | null = null;
let currentBasePath = "data/";
```

- [ ] **Step 4: Add `renderTripsPanel`**

Add this function near `updateSavedCount` (it follows the same "read module state, write one DOM node" shape):

```typescript
function renderTripsPanel() {
  const options = [
    `<option value="">Aktualna</option>`,
    ...savedTrips.map(
      (t) => `<option value="${escape(t.id)}">${escape(formatTripLabel(t))}</option>`,
    ),
  ];
  $("#trips-select").innerHTML = options.join("");
  ($("#trips-select") as HTMLSelectElement).value = currentTripId ?? "";
}
```

- [ ] **Step 5: Make `initialize` accept a target and load trips alongside data**

In `frontend/src/main.ts`, change the `initialize` function signature and its data-loading line:

```typescript
async function initialize(basePath: string = "data/", tripId: string | null = null) {
  currentBasePath = basePath;
  currentTripId = tripId;
  loaded = false;
  loadError = "";
  $("#cards").innerHTML =
    '<div class="empty"><span class="loading-ring"></span><h2>Wczytujemy analizę…</h2></div>';
  renderPanel();
  try {
    const [data, trips] = await Promise.all([loadData(basePath), loadTrips()]);
    savedTrips = trips;
    renderTripsPanel();
    entries = data.entries;
```

(the rest of the function body — from `allScores = data.scores;` onward — is unchanged).

- [ ] **Step 6: Wire the `<select>`'s `change` event**

In `frontend/src/main.ts`, near the other top-level `document.addEventListener(...)` calls (right after the existing `document.addEventListener("click", ...)` block closes), add:

```typescript
document.addEventListener("change", (event) => {
  const select = event.target as HTMLElement;
  if (select.id !== "trips-select") return;
  const value = (select as HTMLSelectElement).value;
  void initialize(value ? `data/trips/${value}/` : "data/", value || null);
});
```

- [ ] **Step 7: Make "retry" re-attempt the same target**

In the existing `switch (button.id)` block's `case "retry":`, change:

```typescript
    case "retry":
      void initialize(currentBasePath, currentTripId);
      break;
```

- [ ] **Step 8: Typecheck and build**

Run: `cd frontend && npm.cmd run build`
Expected: succeeds.

- [ ] **Step 9: Manual verification**

1. `npm.cmd run sync-data && npm.cmd run dev`, open the page — confirm the "Zapisane mapy" bar shows with only "Aktualna" selected (no `trips/index.json` yet).
2. Using the launcher (Task 3), save the currently-synced analysis under a name, e.g. "Test".
3. Reload the page — confirm "Test - Xkm - DD.MM" now appears in the dropdown.
4. Select it — confirm the map/list/analysis-date update to that trip's data; select "Aktualna" — confirm it switches back.
5. Run a fresh `pipeline.prepare_trip` for a different place/radius via the launcher and `npm.cmd run sync-data` again (or via the launcher's "Uruchom analize i podglad") — confirm "Aktualna" now shows the new data while the earlier saved "Test" entry, when selected, still shows the old data unchanged.
6. In `frontend/public/data/trips/<id>/`, delete `stands.geojson` to simulate a corrupted saved trip; select it in the dropdown — confirm the existing error banner appears (not a blank page) and that switching back to "Aktualna" still works.
7. Hand-edit `frontend/public/data/trips/index.json` into invalid JSON text (e.g. append a stray `,`), reload the page — confirm "Aktualna" still loads normally and the dropdown falls back to showing only "Aktualna" (no crash, no error banner from the trips list itself). Restore a valid `index.json` afterwards.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/main.ts frontend/src/style.css
git commit -m "feat: Zapisane mapy panel to browse and switch saved analyses (plan step 5)"
```

---

## Task 6: Documentation and final verification

**Files:**
- Modify: `frontend/README.md`
- Modify: `docs/archiwum/CODEX-HANDOFF.md`

- [ ] **Step 1: Document the feature in `frontend/README.md`**

In the "Zachowanie interfejsu" section (after the existing bullet about `localStorage`/saved regions), add:

```markdown
- Pasek „Zapisane mapy” nad listą/mapą pozwala przełączać się między „Aktualną” (dane z `data/`, zawsze dostępne) a analizami zapisanymi przez launcher (`frontend/public/data/trips/<id>/`, wymienione w `data/trips/index.json`). Zapisany wpis jest zamrożoną migawką: ponowna analiza tego samego miejsca nie zmienia wcześniej zapisanych wpisów. Zapis/usuwanie wpisów odbywa się w launcherze/Eksploratorze, nie w przeglądarce.
```

- [ ] **Step 2: Add a top note to `docs/archiwum/CODEX-HANDOFF.md`**

Add a new top-of-file note (matching this doc's existing "newest note at the top" convention) summarizing: what was built (`launcher/trip_archive.py`, launcher's "Nazwa miejsca"/"Zapisz do listy", frontend's `loadTrips`/`loadData(basePath)`/"Zapisane mapy" panel), that it's purely additive (no change to `pipeline/`, no change to any existing exported field), and the YAGNI cuts (no delete/rename from the app, no cap on saved trips).

- [ ] **Step 3: Full verification sweep**

Run, from the repo root:
```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: all pass, including the new `tests/test_trip_archive.py`.

Run, from `frontend/`:
```bash
npm.cmd test
npm.cmd run build
```
Expected: all pass; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/README.md docs/archiwum/CODEX-HANDOFF.md
git commit -m "docs: document saved-maps comparison list (plan step 6)"
```
