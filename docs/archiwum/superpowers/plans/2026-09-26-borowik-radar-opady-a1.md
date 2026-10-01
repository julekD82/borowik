# A1: opady z radaru IMGW (RainGRS) jako główne źródło opadów z przeszłości — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Open-Meteo's modelled daily precipitation with IMGW-PIB RainGRS (hourly radar + rain-gauge merge, 1 km grid) for every local day in the last `radar.window_days` (30) days at every weather grid point, gap-filled from Open-Meteo where radar hours are missing — so M/F (and `days_since_p10`) are computed from measured rain, with no change to temperature, ET0, soil moisture, climatology or any scoring coefficient.

**Architecture:** One new module, `pipeline/radar.py`, with a strict data-flow: (1) parse/sample ESRI-ASCII grids, (2) fetch + cache one UTC day at a time (archive `.tar` → else operational hourly `.asc` files → else nothing) into compressed `cache/radar_grs/YYYY-MM-DD.npz`, sampling the weather points immediately so at most one day of grids is ever in memory, (3) aggregate hours to local (Europe/Warsaw) days and merge into Open-Meteo's `weather_daily` frame with proportional gap-fill and a per-day `radar_frac`, (4) a wrapper `make_radar_weather_fetcher` with the exact signature of the existing `weather_fetcher`, so `pipeline.orchestrate.run_poc` keeps its interface; only `compute_weather_features` (new `rain_radar_coverage` feature), `run_poc` (export the column), confidence, export and `prepare_trip` wiring change.

**Tech Stack:** Python 3.12 (numpy, pandas, pyproj, requests, stdlib `tarfile`/`zoneinfo`), pytest; TypeScript frontend (`frontend/src/model.ts`, `main.ts`, Vitest) only for one optional field + attribution.

**Spec:** This plan's own "Decyzje projektowe" section is the spec. It was derived in the 2026-09-26 session (user decisions: flush model = phase today + day ratings (A2, later); rain source = radar primary, Open-Meteo gap-fill + forecast; order A1 then A2) and from a throwaway spike comparing 4 Weathercloud stations vs RainGRS vs Open-Meteo (results in `docs/archiwum/CODEX-HANDOFF.md` note (23), station data in `cache/stations/weathercloud_2026-09.yaml`, gitignored).

## Decyzje projektowe (spec)

Verified facts (live, 2026-09-26):
- RainGRS hourly grids: `https://danepubliczne.imgw.pl/pl/datastore/getfiledown/Oper/Nowcasting/rain_grs/grs_60_asc/YYYYMMDDHH00_acc0060_grs.asc` (last ~30 h only) and daily archive `.../getfiledown/Arch/Nowcasting/rain_grs/grs_60_asc/YYYY/MM/grs_60_asc_YYYY-MM-DD.tar` (2018→, lags ~2–3 days: on 2026-09-26 the newest archive day was 2026-09-23). No key, no documented rate limit. Licence: open data (ustawa z 11.08.2021), attribution to IMGW-PIB required.
- Each `.asc`: ESRI ASCII grid, `ncols 900 nrows 800 xllcorner 50000 yllcorner 30000 cellsize 1000 NODATA_value -999.00`, 3.6 MB; one archive day = 70–86 MB uncompressed tar, downloads in 4–9 s, parses in ~6 s; stored as uint16 centi-mm `npz_compressed` = **4–5 MB/day** for the whole of Poland.
- A missing file does **not** return 404 — the server answers HTTP 200 with an HTML page (tarfile raised `ReadError: truncated header`).
- Archive days before 2026-09-13 contain only 19 of 24 hours (19–23 UTC missing). 2026-09-10 had 18.
- Local DNS resolution of `danepubliczne.imgw.pl`, `api.open-meteo.com` and `github.com` failed intermittently during the session and recovered minutes later.
- Open-Meteo daily rows (`pipeline.weather._parse_open_meteo_response`) have `date` = the **UTC instant of local midnight** (e.g. `2026-09-25 22:00:00+00:00` is local 2026-09-26).

Decisions (D1–D4 need a quick user confirmation in Task 0; D5–D9 are implementation choices):
- **D1 Climatology unchanged.** Radar-based `p26w`/`cwb26` are compared against the existing Open-Meteo archive (ERA5) 1991–2020 climatology. Task 7 measures the radar/ERA5 bias on a 2-month 2025 sample; if the ratio is outside 0.85–1.15, **stop and ask** (no automatic correction factor in this plan).
- **D2 Only precipitation changes.** Temperature, ET0 and `soil_moisture` (and so `pct_sm`) stay from Open-Meteo. Soil moisture is still derived from Open-Meteo's own rain — known inconsistency, revisited in A2 (flush model).
- **D3 Spatial sampling = block mean.** Each weather grid point gets the mean of the 1 km radar cells inside a square of side `grid_spacing_m` centred on it (the area whose stands use that point via `_nearest_weather_row`). Per-stand radar sampling is out of scope (possible later).
- **D4 Confidence.** A stand whose `rain_radar_coverage` ≥ `radar.min_coverage_for_quality` (0.8) gets weather quality factor `pogoda_radar_1km: 0.9` [E] instead of `pogoda_nwp_2km: 0.8` and the reason "opady z radaru IMGW ~1 km (RainGRS), temperatura z modelu ~2 km". With the SREDNIA cap nothing changes class-wise; only the stated reason changes.
- **D5 Hours → local days.** A RainGRS file stamp is the hour's END in UTC (`GRS_TIMESTAMP_IS_HOUR_END = True`, verified empirically in Task 7); an hour belongs to the local (Europe/Warsaw) day of its START. Expected hours per local day come from `zoneinfo` (23/24/25 on DST days).
- **D6 Gap fill.** For a local day in the radar window with `k` of `n` expected hours present: `precip = radar_sum + open_meteo_daily * (1 - k/n)`, `radar_frac = k/n`. `k = 0` → Open-Meteo value, `radar_frac = 0`. Days outside the window (older, or forecast days) are untouched.
- **D7 Window.** `radar.window_days: 30` local days ending today (covers `p26w`'s 26 days + `p5`). `days_since_p10` older than 30 days still uses Open-Meteo.
- **D8 Cache.** `cache/radar_grs/YYYY-MM-DD.npz` per UTC file-stamp day, full-Poland grids (reused across any search area). Archive-sourced days are final (`complete=True`); oper-sourced days are partial and re-checked for an archive tar on each run. Raw tars are never written to disk.
- **D9 Failure.** Connection/DNS/timeout after 3 retries → `RadarUnavailableError` → the run continues on Open-Meteo only, with a loud `UWAGA` line, `radar_frac = 0`, and the NWP confidence reason. A run never fails because of IMGW.

## Global Constraints

- TDD: failing test first in every task. Every test runs with no network (fake `http_get`, synthetic grids).
- Run tests with: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (from the repo root `C:\Users\<uzytkownik>\Documents\Grzyby`).
- Do not change `fruiting.*`, `fruiting_classes`, `pressure.*`, `pipeline/habitat.py`, `pipeline/scoring.py`.
- `run_poc`'s signature does not change; the radar enters only through the `weather_fetcher` passed in by `prepare_trip`.
- Never hold more than one UTC day of radar grids in memory (30 days as float32 would be ~2 GB).
- Raw `.tar`/`.asc` never written to disk; only `cache/radar_grs/*.npz` (under the already-gitignored `cache/`).
- No personal data in the repo: Weathercloud station coordinates stay in `cache/stations/weathercloud_2026-09.yaml`; docs refer to stations only as S1–S4 with a rough area ("ok. 3–4 km od rejonu 1").
- IMGW attribution text wherever sources are listed: "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy" + a note that the data were processed.
- User-facing strings (prints, reasons, UI) in Polish; prints in ASCII-only Polish like the rest of `prepare_trip.py` (e.g. "niedostepny", "dob").
- Final task: full pytest, `npm test`, `npx tsc --noEmit`, `npx vite build` in `frontend/`, and a new note at the top of `docs/archiwum/CODEX-HANDOFF.md`.

## Review Focus

- Open-Meteo `date` is the UTC instant of local midnight (`2026-09-25 22:00+00:00` = local 26.09); merging on `.dt.date` without `tz_convert("Europe/Warsaw")` silently shifts every day by one — Task 3 test `test_merge_uses_local_date_of_utc_midnight_timestamps`.
- IMGW answers a missing tar/asc with HTTP 200 + HTML, not 404 — must be "missing", never a crash — Task 2 tests `test_html_instead_of_tar_falls_back_to_oper_hours` and `test_html_instead_of_asc_is_skipped`.
- IMGW unreachable (DNS failures seen live) → run completes on Open-Meteo with `UWAGA` — Task 4 test `test_radar_unavailable_falls_back_to_model_with_warning`.
- Archive days with missing hours (19–23 UTC before 2026-09-13) and the ~1.5-day archive→oper gap must produce proportional gap-fill and `radar_frac < 1`, never "0 mm because no file" — Task 3 tests `test_merge_partial_coverage_fills_missing_share_from_model` and `test_merge_no_radar_keeps_model_value`.
- DST days (2026-10-25 has 25 local hours, 2026-03-29 has 23) — Task 3 test `test_expected_local_hours_on_dst_days`.

---

## Task 0: Pre-flight (no code)

**Files:** none (possibly one commit of existing uncommitted work).

- [ ] **Step 1: Uncommitted work.** `git status` showed uncommitted `pipeline/weather.py` (`fetch_archive_daily`, `_default_archive_daily_call` — needed by Task 7's bias notebook), `uv.lock`, `.gitignore`, untracked `notebooks/03_backtest_gbif.py`, `CLAUDE.md`, `frontend/public/`, `launcher/`. Ask the user whether to commit `pipeline/weather.py` + `notebooks/03_backtest_gbif.py` as one separate commit before starting (`git add pipeline/weather.py notebooks/03_backtest_gbif.py && git commit -m "feat: fetch_archive_daily + GBIF backtest notebook"`). Do not touch `launcher/`, `frontend/public/`, `CLAUDE.md`, `.gitignore`, `uv.lock` unless the user says so.
- [ ] **Step 2: Confirm D1–D4** with the user in one short message (list them verbatim from "Decyzje projektowe"). If any changes, update this plan's section before Task 1.
- [ ] **Step 3: CRS/timestamp documentation check (read-only, 10 min max).** Try `https://danepubliczne.imgw.pl/pl/repository` for a RainGRS/`grs_60_asc` product description stating the grid CRS and whether the file time is the hour's start or end. Record what you found (or "nie znaleziono") for the handoff note. If the docs contradict `EPSG:2180` or hour-end, stop and ask.

---

## Task 1: `pipeline/radar.py` — grid parsing and block sampling

**Files:**
- Create: `pipeline/radar.py`
- Test: `tests/test_radar.py`

**Interfaces:**
- Produces: `GridHeader` (frozen dataclass: `ncols:int, nrows:int, xllcorner:float, yllcorner:float, cellsize:float`, `.as_array()`, `GridHeader.from_array(a)`), `parse_grs_asc(raw: bytes) -> tuple[GridHeader, np.ndarray]` (float32 `(nrows, ncols)`, NaN = no data), `parse_hour_stamp(name: str) -> datetime` (tz-aware UTC hour END), `to_grid_xy(points: list[tuple[float, float]]) -> list[tuple[float, float]]` (lat,lon → EPSG:2180 x,y), `block_slices(header, xy_points, half_size_m) -> list[tuple[slice, slice] | None]`, `sample_stack(stack: np.ndarray, slices) -> np.ndarray` (`(hours, points)` float64), constants `GRS_CRS`, `GRS_TIMESTAMP_IS_HOUR_END`, `WARSAW`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_radar.py
import math
from datetime import datetime, timezone

import numpy as np
import pytest

from pipeline.radar import (
    GridHeader, parse_grs_asc, parse_hour_stamp, block_slices, sample_stack,
)


def _asc(values, xll=0.0, yll=0.0, cs=1000.0, nodata=-999.0) -> bytes:
    rows, cols = len(values), len(values[0])
    head = (f"ncols {cols}\nnrows {rows}\nxllcorner {xll}\nyllcorner {yll}\n"
            f"cellsize {cs}\nNODATA_value {nodata}\n")
    body = "\n".join(" ".join(f"{v:.2f}" for v in r) for r in values)
    return (head + body + "\n").encode("ascii")


GRID_3x4 = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]  # row 0 = northernmost


def test_parse_grs_asc_reads_header_and_values_top_row_first():
    header, grid = parse_grs_asc(_asc(GRID_3x4, xll=50000, yll=30000))
    assert header == GridHeader(ncols=4, nrows=3, xllcorner=50000.0, yllcorner=30000.0, cellsize=1000.0)
    assert grid.shape == (3, 4)
    assert grid[0, 0] == 1.0 and grid[2, 3] == 12.0


def test_parse_grs_asc_turns_nodata_into_nan():
    _, grid = parse_grs_asc(_asc([[1, -999], [0, 2]]))
    assert math.isnan(grid[0, 1])
    assert grid[1, 0] == 0.0


def test_parse_grs_asc_rejects_html_error_page():
    # IMGW answers a missing file with HTTP 200 + an HTML page, not a 404.
    with pytest.raises(ValueError):
        parse_grs_asc(b"<!DOCTYPE html><html><body>Brak pliku</body></html>")


def test_parse_grs_asc_rejects_truncated_grid():
    raw = _asc(GRID_3x4)[:-10]
    with pytest.raises(ValueError):
        parse_grs_asc(raw)


def test_parse_hour_stamp_is_utc_hour_end():
    stamp = parse_hour_stamp("Arch/x/202609211300_acc0060_grs.asc")
    assert stamp == datetime(2026, 9, 21, 13, 0, tzinfo=timezone.utc)


def test_parse_hour_stamp_rejects_other_names():
    with pytest.raises(ValueError):
        parse_hour_stamp("202609211300_acc0060_grs.png")


HEADER_3x4 = GridHeader(ncols=4, nrows=3, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)


def test_block_slices_zero_half_size_selects_the_containing_cell():
    (sl,) = block_slices(HEADER_3x4, [(1500.0, 500.0)], half_size_m=0)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[10.0]]  # bottom row (southmost), second column


def test_block_slices_square_block_covers_expected_cells():
    (sl,) = block_slices(HEADER_3x4, [(2000.0, 1500.0)], half_size_m=1000)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[2.0, 3.0], [6.0, 7.0], [10.0, 11.0]]


def test_block_slices_point_outside_grid_is_none():
    assert block_slices(HEADER_3x4, [(10000.0, 10000.0), (-500.0, 500.0)], half_size_m=0) == [None, None]


def test_sample_stack_means_blocks_ignoring_nan_and_all_nan_gives_nan():
    stack = np.array([
        [[1.0, 3.0], [np.nan, 5.0]],
        [[np.nan, np.nan], [np.nan, np.nan]],
    ])
    header = GridHeader(ncols=2, nrows=2, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)
    slices = block_slices(header, [(1000.0, 1000.0)], half_size_m=1000) + [None]
    out = sample_stack(stack, slices)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(3.0)  # mean(1, 3, 5)
    assert math.isnan(out[1, 0])
    assert math.isnan(out[0, 1])  # point outside grid
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.radar'`.

- [ ] **Step 3: Implement**

```python
# pipeline/radar.py
"""IMGW-PIB RainGRS: hourly precipitation from weather radar merged with
rain gauges, 1 km grid over Poland, ESRI ASCII. Plan 2026-09-26 A1
(docs/archiwum/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md).

Why this exists: a 2026-09-26 comparison against 4 independent Weathercloud
stations near Bedziemysl (docs/archiwum/CODEX-HANDOFF.md note (23)) gave RainGRS a
1.5-4x lower daily MAE than Open-Meteo; Open-Meteo missed convective days
(29.08, 31.08, 03.09) and invented rain on others (03.09, 05.09, 15.09).

Source: https://danepubliczne.imgw.pl (open data, attribution required:
"Zrodlem pochodzenia danych jest IMGW-PIB"). Operational hourly files cover
only the last ~30 h; the daily archive tar lags ~2-3 days. A missing file is
served as HTTP 200 + HTML, not 404 -- every parser here must reject HTML."""
import io
import math
import re
import tarfile
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pyproj import Transformer

GRS_BASE_URL = "https://danepubliczne.imgw.pl/pl/datastore/getfiledown"
GRS_ARCHIVE_PATH = "Arch/Nowcasting/rain_grs/grs_60_asc"
GRS_OPER_PATH = "Oper/Nowcasting/rain_grs/grs_60_asc"
# Assumed EPSG:2180 (header xll=50000, yll=30000, 900x800 km fits PUWG 1992
# exactly); empirically consistent with station agreement on convective
# days -- see plan Task 0 step 3 / Task 7.
GRS_CRS = "EPSG:2180"
# File "YYYYMMDDHH00" = accumulation for the hour ENDING at that UTC time
# (plan Task 7 checks this against station daily sums).
GRS_TIMESTAMP_IS_HOUR_END = True
OPER_LOOKBACK_HOURS = 48
WARSAW = ZoneInfo("Europe/Warsaw")

_TO_GRID = Transformer.from_crs("EPSG:4326", GRS_CRS, always_xy=True)
_STAMP_RE = re.compile(r"(\d{12})_acc0060_grs\.asc$")


@dataclass(frozen=True)
class GridHeader:
    ncols: int
    nrows: int
    xllcorner: float
    yllcorner: float
    cellsize: float

    def as_array(self) -> np.ndarray:
        return np.array([self.ncols, self.nrows, self.xllcorner, self.yllcorner, self.cellsize],
                        dtype=np.float64)

    @classmethod
    def from_array(cls, a) -> "GridHeader":
        return cls(int(a[0]), int(a[1]), float(a[2]), float(a[3]), float(a[4]))


def parse_grs_asc(raw: bytes) -> tuple[GridHeader, np.ndarray]:
    """ESRI ASCII grid -> (header, float32 grid, row 0 = north). Negative
    values (NODATA -999) become NaN -- precipitation is never negative."""
    parts = raw.split(b"\n", 6)
    if len(parts) < 7 or not parts[0].strip().lower().startswith(b"ncols"):
        raise ValueError("not an ESRI ASCII grid (IMGW returned an HTML page?)")
    hdr = {}
    for line in parts[:6]:
        key, value = line.split()[:2]
        hdr[key.decode("ascii").lower()] = float(value)
    header = GridHeader(int(hdr["ncols"]), int(hdr["nrows"]), hdr["xllcorner"], hdr["yllcorner"],
                        hdr["cellsize"])
    values = np.array(parts[6].split(), dtype=np.float32)
    if values.size != header.ncols * header.nrows:
        raise ValueError(f"grid size mismatch: {values.size} != {header.ncols}x{header.nrows}")
    grid = values.reshape(header.nrows, header.ncols)
    grid[grid < 0] = np.nan
    return header, grid


def parse_hour_stamp(name: str) -> datetime:
    """File name -> tz-aware UTC END of the accumulated hour."""
    m = _STAMP_RE.search(name)
    if m is None:
        raise ValueError(f"not a RainGRS hourly file name: {name!r}")
    stamp = datetime.strptime(m.group(1), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    return stamp if GRS_TIMESTAMP_IS_HOUR_END else stamp + timedelta(hours=1)


def to_grid_xy(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [_TO_GRID.transform(lon, lat) for lat, lon in points]


def block_slices(header: GridHeader, xy_points, half_size_m: float) -> list[tuple[slice, slice] | None]:
    """(row, col) slices of the cells inside a square of side 2*half_size_m
    centred on each point (half_size_m <= 0: the single containing cell).
    Rows are counted from the top (north) as in the file. None = the block
    lies entirely outside the grid."""
    out = []
    cs = header.cellsize
    for x, y in xy_points:
        fx = (x - header.xllcorner) / cs
        fy = (y - header.yllcorner) / cs
        if half_size_m <= 0:
            c0 = c1 = math.floor(fx)
            k0 = k1 = math.floor(fy)  # k = row index counted from the bottom
        else:
            h = half_size_m / cs
            c0, c1 = math.floor(fx - h), math.ceil(fx + h) - 1
            k0, k1 = math.floor(fy - h), math.ceil(fy + h) - 1
        c0, c1 = max(c0, 0), min(c1, header.ncols - 1)
        k0, k1 = max(k0, 0), min(k1, header.nrows - 1)
        if c0 > c1 or k0 > k1:
            out.append(None)
            continue
        r0, r1 = header.nrows - 1 - k1, header.nrows - 1 - k0
        out.append((slice(r0, r1 + 1), slice(c0, c1 + 1)))
    return out


def sample_stack(stack: np.ndarray, slices) -> np.ndarray:
    """(hours, nrows, ncols) grids -> (hours, points) block means, NaN-aware.
    An all-NaN block (or a None slice) gives NaN = "no radar data here"."""
    out = np.full((stack.shape[0], len(slices)), np.nan, dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # nanmean of all-NaN
        for j, sl in enumerate(slices):
            if sl is None:
                continue
            block = stack[:, sl[0], sl[1]].reshape(stack.shape[0], -1)
            out[:, j] = np.nanmean(block, axis=1)
    return out
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/radar.py tests/test_radar.py
git commit -m "feat: RainGRS grid parsing and block sampling (plan A1 task 1)"
```

---

## Task 2: Fetch + per-day npz cache → hourly values at points

**Files:**
- Modify: `pipeline/radar.py` (append)
- Test: `tests/test_radar.py` (append)

**Interfaces:**
- Consumes: Task 1 (`parse_grs_asc`, `parse_hour_stamp`, `block_slices`, `sample_stack`, `to_grid_xy`, `GridHeader`).
- Produces: `RadarUnavailableError(RuntimeError)`; `quantize(grid) -> np.ndarray[uint16]`, `dequantize(q) -> np.ndarray[float32]`; `archive_url(day: date) -> str`, `oper_url(file_stamp: datetime) -> str`; `radar_hourly_at_points(points, half_size_m, start_utc, end_utc, cache_dir, http_get=None, now_utc=None) -> pd.DataFrame` with columns `lat, lon, hour_end_utc (tz-aware UTC), precip_mm (float, NaN = no data)`, including hours with `start_utc < hour_end_utc <= end_utc`. `http_get: Callable[[str], bytes | None]` — `None` = not published; raises `RadarUnavailableError` when the server is unreachable.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_radar.py (append)
import io
import tarfile
from datetime import date, timedelta

import pandas as pd
from pyproj import Transformer

from pipeline.radar import (
    RadarUnavailableError, archive_url, oper_url, quantize, dequantize, radar_hourly_at_points,
)

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
POINT = (50.0555, 21.7889)  # Bedziemysl
_X, _Y = _TO_2180.transform(POINT[1], POINT[0])
# 3x3 km synthetic grid whose centre cell contains POINT
XLL, YLL = math.floor(_X / 1000) * 1000 - 1000, math.floor(_Y / 1000) * 1000 - 1000


def _grid_bytes(centre_mm: float) -> bytes:
    v = [[0.0] * 3 for _ in range(3)]
    v[1][1] = centre_mm
    return _asc(v, xll=XLL, yll=YLL)


def _tar(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


HTML = b"<!DOCTYPE html><html><body>Brak</body></html>"


class FakeHttp:
    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses.get(url, HTML)


def test_quantize_roundtrip_keeps_centimillimetres_and_nan():
    g = np.array([[0.0, 1.234, np.nan, 700.0]], dtype=np.float32)
    back = dequantize(quantize(g))
    assert back[0, 1] == pytest.approx(1.23)
    assert math.isnan(back[0, 2])
    assert back[0, 3] == pytest.approx(655.34)  # clipped just below the NaN sentinel


def test_archive_and_oper_urls():
    assert archive_url(date(2026, 9, 21)).endswith(
        "/Arch/Nowcasting/rain_grs/grs_60_asc/2026/09/grs_60_asc_2026-09-21.tar")
    assert oper_url(datetime(2026, 9, 25, 13, tzinfo=timezone.utc)).endswith(
        "/Oper/Nowcasting/rain_grs/grs_60_asc/202609251300_acc0060_grs.asc")


def test_archive_day_is_sampled_cached_and_not_refetched(tmp_path):
    day = date(2026, 9, 21)
    http = FakeHttp({archive_url(day): _tar({
        "grs_60_asc_2026-09-21/202609210100_acc0060_grs.asc": _grid_bytes(2.5),
        "grs_60_asc_2026-09-21/202609210200_acc0060_grs.asc": _grid_bytes(1.0),
    })})
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    start = datetime(2026, 9, 21, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, 0, tzinfo=timezone.utc)

    df = radar_hourly_at_points([POINT], 0, start, end, tmp_path, http_get=http, now_utc=now)

    assert df["precip_mm"].tolist() == pytest.approx([2.5, 1.0])
    assert df["hour_end_utc"].tolist() == [
        pd.Timestamp("2026-09-21 01:00", tz="UTC"), pd.Timestamp("2026-09-21 02:00", tz="UTC")]
    assert (tmp_path / "2026-09-21.npz").exists()

    http.calls.clear()
    again = radar_hourly_at_points([POINT], 0, start, end, tmp_path, http_get=http, now_utc=now)
    assert again["precip_mm"].tolist() == pytest.approx([2.5, 1.0])
    assert not any("2026-09-21" in c for c in http.calls)  # complete archive day served from cache


def test_html_instead_of_tar_falls_back_to_oper_hours(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    http = FakeHttp({
        oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)): _grid_bytes(4.0),
        oper_url(datetime(2026, 9, 26, 2, tzinfo=timezone.utc)): _grid_bytes(0.5),
    })
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 26, 0, tzinfo=timezone.utc), now, tmp_path,
        http_get=http, now_utc=now)
    assert df["precip_mm"].tolist() == pytest.approx([4.0, 0.5])
    # hours after `now` are never requested
    assert oper_url(datetime(2026, 9, 26, 5, tzinfo=timezone.utc)) not in http.calls


def test_html_instead_of_asc_is_skipped(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    http = FakeHttp({oper_url(datetime(2026, 9, 26, 2, tzinfo=timezone.utc)): _grid_bytes(0.5)})
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 26, 0, tzinfo=timezone.utc), now, tmp_path,
        http_get=http, now_utc=now)
    assert df["hour_end_utc"].tolist() == [pd.Timestamp("2026-09-26 02:00", tz="UTC")]


def test_old_day_without_archive_does_not_request_oper_hours(tmp_path):
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    http = FakeHttp({})
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 11, 0, tzinfo=timezone.utc), tmp_path, http_get=http, now_utc=now)
    assert df.empty
    assert all("/Oper/" not in c for c in http.calls)  # oper keeps only ~30 h


def test_partial_oper_day_rechecks_archive_on_next_run(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    start = datetime(2026, 9, 26, 0, tzinfo=timezone.utc)
    http = FakeHttp({oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)): _grid_bytes(4.0)})
    radar_hourly_at_points([POINT], 0, start, now, tmp_path, http_get=http, now_utc=now)
    http.calls.clear()
    radar_hourly_at_points([POINT], 0, start, now, tmp_path, http_get=http, now_utc=now)
    assert archive_url(date(2026, 9, 26)) in http.calls
    assert oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)) not in http.calls  # cached hour


def test_unreachable_server_raises_radar_unavailable(tmp_path):
    def down(url):
        raise RadarUnavailableError("dns")
    with pytest.raises(RadarUnavailableError):
        radar_hourly_at_points([POINT], 0, datetime(2026, 9, 21, tzinfo=timezone.utc),
                               datetime(2026, 9, 22, tzinfo=timezone.utc), tmp_path,
                               http_get=down, now_utc=datetime(2026, 9, 26, tzinfo=timezone.utc))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'RadarUnavailableError'`.

- [ ] **Step 3: Implement (append to `pipeline/radar.py`)**

```python
_NODATA_Q = 65535


class RadarUnavailableError(RuntimeError):
    """IMGW unreachable after retries (connection/DNS/timeout) -- distinct
    from "file not published", which is a normal None from http_get."""


def quantize(grid: np.ndarray) -> np.ndarray:
    q = np.clip(np.round(np.nan_to_num(grid, nan=0.0) * 100.0), 0, _NODATA_Q - 1)
    q[np.isnan(grid)] = _NODATA_Q
    return q.astype(np.uint16)


def dequantize(q: np.ndarray) -> np.ndarray:
    g = q.astype(np.float32) / 100.0
    g[q == _NODATA_Q] = np.nan
    return g


def archive_url(day: date) -> str:
    return f"{GRS_BASE_URL}/{GRS_ARCHIVE_PATH}/{day:%Y}/{day:%m}/grs_60_asc_{day.isoformat()}.tar"


def oper_url(file_stamp: datetime) -> str:
    return f"{GRS_BASE_URL}/{GRS_OPER_PATH}/{file_stamp:%Y%m%d%H%M}_acc0060_grs.asc"


def _default_http_get(url: str) -> bytes | None:
    import requests

    last_exc = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=300)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            # Intermittent DNS failures for danepubliczne.imgw.pl observed live 2026-09-26.
            last_exc = exc
            time.sleep(5 * (attempt + 1))
            continue
        return response.content if response.status_code == 200 else None
    raise RadarUnavailableError(f"IMGW niedostepny: {last_exc}")


@dataclass
class DayGrids:
    header: GridHeader
    hour_ends: list[datetime]  # tz-aware UTC, sorted
    q: np.ndarray              # (hours, nrows, ncols) uint16 centi-mm
    complete: bool             # True = from the archive tar (final)


def _day_path(cache_dir: Path, day: date) -> Path:
    return cache_dir / f"{day.isoformat()}.npz"


def _save_day(path: Path, data: DayGrids) -> None:
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        tmp, q=data.q, header=data.header.as_array(),
        hour_ends=np.array([int(h.timestamp()) for h in data.hour_ends], dtype=np.int64),
        complete=np.array(data.complete),
    )
    tmp.replace(path)


def _load_day(path: Path) -> DayGrids:
    with np.load(path) as z:
        return DayGrids(
            header=GridHeader.from_array(z["header"]),
            hour_ends=[datetime.fromtimestamp(int(t), tz=timezone.utc) for t in z["hour_ends"]],
            q=z["q"],
            complete=bool(z["complete"]),
        )


def _stack(header: GridHeader, grids: dict[datetime, np.ndarray], complete: bool) -> DayGrids:
    keys = sorted(grids)
    return DayGrids(header, keys, np.stack([grids[k] for k in keys]), complete)


def _parse_archive_tar(raw: bytes) -> DayGrids | None:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(raw))
    except tarfile.ReadError:
        return None  # HTML page instead of a tar: day not archived yet
    grids, header = {}, None
    for member in tf.getmembers():
        if not member.isfile() or not _STAMP_RE.search(member.name):
            continue
        try:
            header, grid = parse_grs_asc(tf.extractfile(member).read())
        except ValueError:
            continue
        grids[parse_hour_stamp(member.name)] = quantize(grid)
    return _stack(header, grids, complete=True) if grids else None


def _load_or_fetch_day(day: date, cache_dir: Path, http_get, now_utc: datetime) -> tuple[DayGrids | None, str]:
    """One UTC file-stamp day: complete cache -> archive tar -> oper hours."""
    path = _day_path(cache_dir, day)
    cached = _load_day(path) if path.exists() else None
    if cached is not None and cached.complete:
        return cached, "cache"
    raw = http_get(archive_url(day))
    if raw is not None:
        parsed = _parse_archive_tar(raw)
        if parsed is not None:
            _save_day(path, parsed)
            return parsed, "archiwum"
    grids = dict(zip(cached.hour_ends, cached.q)) if cached else {}
    header = cached.header if cached else None
    new = 0
    for hour in range(24):
        file_stamp = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
        hour_end = file_stamp if GRS_TIMESTAMP_IS_HOUR_END else file_stamp + timedelta(hours=1)
        if hour_end in grids or hour_end > now_utc or hour_end < now_utc - timedelta(hours=OPER_LOOKBACK_HOURS):
            continue
        raw = http_get(oper_url(file_stamp))
        if raw is None:
            continue
        try:
            header, grid = parse_grs_asc(raw)
        except ValueError:
            continue
        grids[hour_end] = quantize(grid)
        new += 1
    if not grids:
        return None, "brak"
    data = _stack(header, grids, complete=False)
    if new:
        _save_day(path, data)
    return data, "biezace"


def radar_hourly_at_points(points: list[tuple[float, float]], half_size_m: float,
                           start_utc: datetime, end_utc: datetime, cache_dir,
                           http_get=None, now_utc: datetime | None = None) -> pd.DataFrame:
    """Hourly RainGRS block means at `points` for hours ending in
    (start_utc, end_utc]. One UTC day of grids in memory at a time."""
    http_get = http_get or _default_http_get
    now_utc = now_utc or datetime.now(timezone.utc)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    xy = to_grid_xy(points)
    lats = np.array([p[0] for p in points])
    lons = np.array([p[1] for p in points])
    frames, sources = [], {}
    day = start_utc.date()
    while day <= end_utc.date():
        if datetime(day.year, day.month, day.day, tzinfo=timezone.utc) > now_utc:
            break
        data, source = _load_or_fetch_day(day, cache_dir, http_get, now_utc)
        sources[source] = sources.get(source, 0) + 1
        day += timedelta(days=1)
        if data is None:
            continue
        keep = [i for i, h in enumerate(data.hour_ends) if start_utc < h <= end_utc]
        if not keep:
            continue
        values = sample_stack(dequantize(data.q[keep]), block_slices(data.header, xy, half_size_m))
        hours = pd.DatetimeIndex([data.hour_ends[i] for i in keep])
        frames.append(pd.DataFrame({
            "lat": np.tile(lats, len(keep)),
            "lon": np.tile(lons, len(keep)),
            "hour_end_utc": hours.repeat(len(points)),
            "precip_mm": values.reshape(-1),
        }))
    print("Radar IMGW (RainGRS): " + ", ".join(f"{k} {v}" for k, v in sorted(sources.items())) + " dob",
          flush=True)
    if not frames:
        return pd.DataFrame({"lat": [], "lon": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"),
                             "precip_mm": []})
    return pd.concat(frames, ignore_index=True)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/radar.py tests/test_radar.py
git commit -m "feat: RainGRS archive/oper fetch with per-day npz cache (plan A1 task 2)"
```

---

## Task 3: Hours → local days, merge into Open-Meteo daily frame

**Files:**
- Modify: `pipeline/radar.py` (append)
- Test: `tests/test_radar.py` (append)

**Interfaces:**
- Consumes: Task 2's hourly frame (`lat, lon, hour_end_utc, precip_mm`).
- Produces: `expected_local_hours(day: date) -> int`; `radar_daily_at_points(hourly: pd.DataFrame) -> pd.DataFrame` (`lat, lon, local_date (datetime.date), radar_mm, radar_hours, expected_hours`); `merge_radar_into_daily(weather_daily, radar_daily, window_start: date, window_end: date) -> pd.DataFrame` — same rows/columns as `weather_daily` plus `precipitation_mm_model` (original Open-Meteo value) and `radar_frac` (0–1).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_radar.py (append)
from pipeline.radar import expected_local_hours, radar_daily_at_points, merge_radar_into_daily


def _hourly(rows):
    return pd.DataFrame(rows, columns=["lat", "lon", "hour_end_utc", "precip_mm"])


def test_expected_local_hours_on_dst_days():
    assert expected_local_hours(date(2026, 9, 21)) == 24
    assert expected_local_hours(date(2026, 10, 25)) == 25  # CEST -> CET
    assert expected_local_hours(date(2026, 3, 29)) == 23   # CET -> CEST


def test_radar_daily_assigns_each_hour_to_local_day_of_its_start():
    h = _hourly([
        (50.0, 21.0, pd.Timestamp("2026-09-20 22:00", tz="UTC"), 1.0),  # 23:00-00:00 local 20.09
        (50.0, 21.0, pd.Timestamp("2026-09-20 23:00", tz="UTC"), 2.0),  # 00:00-01:00 local 21.09
        (50.0, 21.0, pd.Timestamp("2026-09-21 00:00", tz="UTC"), float("nan")),  # no data: not counted
    ])
    d = radar_daily_at_points(h).set_index("local_date")
    assert d.loc[date(2026, 9, 20), "radar_mm"] == 1.0
    assert d.loc[date(2026, 9, 21), "radar_mm"] == 2.0
    assert d.loc[date(2026, 9, 21), "radar_hours"] == 1
    assert d.loc[date(2026, 9, 21), "expected_hours"] == 24


def _om_daily(values_by_local_day: dict):
    # Same shape as pipeline.weather._parse_open_meteo_response: `date` is the
    # UTC instant of LOCAL midnight (22:00 UTC the previous day in summer time).
    rows = []
    for d, mm in values_by_local_day.items():
        rows.append({"lat": 50.0, "lon": 21.0,
                     "date": pd.Timestamp(d.isoformat(), tz="Europe/Warsaw").tz_convert("UTC"),
                     "precipitation_mm": mm, "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0,
                     "et0_mm": 1.0, "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def _radar_day(d, mm, hours, expected=24):
    return pd.DataFrame([{"lat": 50.0, "lon": 21.0, "local_date": d, "radar_mm": mm,
                          "radar_hours": hours, "expected_hours": expected}])


def test_merge_uses_local_date_of_utc_midnight_timestamps():
    daily = _om_daily({date(2026, 9, 21): 17.0, date(2026, 9, 22): 13.0})
    out = merge_radar_into_daily(daily, _radar_day(date(2026, 9, 22), 12.5, 24),
                                 date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].tolist() == pytest.approx([17.0, 12.5])
    assert out["radar_frac"].tolist() == [0.0, 1.0]
    assert out["precipitation_mm_model"].tolist() == pytest.approx([17.0, 13.0])


def test_merge_partial_coverage_fills_missing_share_from_model():
    daily = _om_daily({date(2026, 9, 11): 20.0})
    out = merge_radar_into_daily(daily, _radar_day(date(2026, 9, 11), 15.0, 18),
                                 date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].iloc[0] == pytest.approx(15.0 + 20.0 * 6 / 24)
    assert out["radar_frac"].iloc[0] == pytest.approx(0.75)


def test_merge_no_radar_keeps_model_value():
    daily = _om_daily({date(2026, 9, 24): 0.1})
    empty = radar_daily_at_points(_hourly([]))
    out = merge_radar_into_daily(daily, empty, date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].iloc[0] == pytest.approx(0.1)
    assert out["radar_frac"].iloc[0] == 0.0


def test_merge_leaves_days_outside_window_untouched():
    daily = _om_daily({date(2026, 8, 1): 5.0, date(2026, 9, 27): 3.0})  # too old / forecast
    radar = pd.concat([_radar_day(date(2026, 8, 1), 0.0, 24), _radar_day(date(2026, 9, 27), 0.0, 24)])
    out = merge_radar_into_daily(daily, radar, date(2026, 8, 28), date(2026, 9, 26))
    assert out["precipitation_mm"].tolist() == pytest.approx([5.0, 3.0])
    assert out["radar_frac"].tolist() == [0.0, 0.0]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'expected_local_hours'`.

- [ ] **Step 3: Implement (append to `pipeline/radar.py`)**

```python
def expected_local_hours(day: date) -> int:
    """23/24/25 -- number of real hours in the Europe/Warsaw calendar day.
    Aware datetimes sharing one tzinfo subtract NAIVELY in Python, hence
    the explicit conversion to UTC first."""
    nxt = day + timedelta(days=1)
    start = datetime(day.year, day.month, day.day, tzinfo=WARSAW).astimezone(timezone.utc)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=WARSAW).astimezone(timezone.utc)
    return int(round((end - start).total_seconds() / 3600))


_DAILY_COLUMNS = ["lat", "lon", "local_date", "radar_mm", "radar_hours", "expected_hours"]


def radar_daily_at_points(hourly: pd.DataFrame) -> pd.DataFrame:
    """Sum hours into local days. An hour belongs to the local day of its
    START (hour_end - 1 h). NaN hours (no radar data at the point) are not
    counted, so they get gap-filled in merge_radar_into_daily."""
    valid = hourly.dropna(subset=["precip_mm"])
    if valid.empty:
        return pd.DataFrame(columns=_DAILY_COLUMNS)
    start_local = (pd.to_datetime(valid["hour_end_utc"], utc=True) - pd.Timedelta(hours=1)).dt.tz_convert("Europe/Warsaw")
    grouped = (
        valid.assign(local_date=start_local.dt.date)
        .groupby(["lat", "lon", "local_date"], as_index=False)
        .agg(radar_mm=("precip_mm", "sum"), radar_hours=("precip_mm", "size"))
    )
    grouped["expected_hours"] = grouped["local_date"].map(expected_local_hours)
    return grouped[_DAILY_COLUMNS]


def merge_radar_into_daily(weather_daily: pd.DataFrame, radar_daily: pd.DataFrame,
                           window_start: date, window_end: date) -> pd.DataFrame:
    """Plan A1 D6: precip = radar_sum + model * (1 - k/n) for local days in
    [window_start, window_end] with k>0 radar hours; untouched otherwise."""
    out = weather_daily.reset_index(drop=True).copy()
    out["precipitation_mm"] = out["precipitation_mm"].astype(float)
    out["precipitation_mm_model"] = out["precipitation_mm"]
    out["radar_frac"] = 0.0
    if radar_daily.empty:
        return out
    dates = out["date"]
    # Open-Meteo's `date` is the UTC instant of LOCAL midnight -- converting
    # is what makes 2026-09-25 22:00 UTC mean local 2026-09-26.
    local_date = (dates.dt.tz_convert("Europe/Warsaw") if dates.dt.tz is not None else dates).dt.date
    in_window = ((local_date >= window_start) & (local_date <= window_end)).to_numpy()
    joined = radar_daily.set_index(["lat", "lon", "local_date"]).reindex(
        pd.MultiIndex.from_arrays([out["lat"], out["lon"], local_date]))
    hours = joined["radar_hours"].to_numpy(dtype=float)
    expected = joined["expected_hours"].to_numpy(dtype=float)
    has = in_window & np.nan_to_num(hours, nan=0.0).astype(bool)
    frac = np.clip(np.nan_to_num(hours / expected, nan=0.0), 0.0, 1.0)
    merged = joined["radar_mm"].to_numpy(dtype=float) + out["precipitation_mm_model"].to_numpy() * (1.0 - frac)
    out.loc[has, "precipitation_mm"] = merged[has]
    out.loc[has, "radar_frac"] = frac[has]
    return out
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py -q -p no:cacheprovider`
Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/radar.py tests/test_radar.py
git commit -m "feat: aggregate RainGRS to local days and merge with gap-fill (plan A1 task 3)"
```

---

## Task 4: Radar weather fetcher + `rain_radar_coverage` feature + `run_poc` column

**Files:**
- Modify: `pipeline/radar.py` (append), `pipeline/weather.py` (`compute_weather_features`, new `_exp_weighted_mean`), `pipeline/orchestrate.py` (collect/export column + diagnostic)
- Test: `tests/test_radar.py`, `tests/test_weather.py`, `tests/test_orchestrate.py` (append)

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces: `radar_window(today: date, window_days: int, now_utc: datetime) -> tuple[date, date, datetime, datetime]`; `make_radar_weather_fetcher(base_fetcher, *, half_size_m: float, window_days: int, cache_dir, http_get=None, now_utc=None, today=None, radar_hourly_fn=None)` returning `fetcher(points, past_days, forecast_days=1) -> pd.DataFrame` (same signature as `pipeline.weather.fetch_weather_raw` partials). `compute_weather_features` output gains `rain_radar_coverage` (0.0 when the input has no `radar_frac` column). `run_poc` output gains per-stand `rain_radar_coverage` and `attrs["diagnostics"]["radar_coverage_mean"]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_radar.py (append)
from pipeline.radar import make_radar_weather_fetcher, radar_window


def test_radar_window_ends_now_and_spans_window_days_of_local_days():
    now = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    ws, we, s_utc, e_utc = radar_window(date(2026, 9, 26), 30, now)
    assert (ws, we) == (date(2026, 8, 28), date(2026, 9, 26))
    assert s_utc == datetime(2026, 8, 27, 22, tzinfo=timezone.utc)  # local midnight 28.08
    assert e_utc == now


def _base_fetcher(points, past_days, forecast_days=1):
    return _om_daily({date(2026, 9, 21): 17.0, date(2026, 9, 22): 13.0})


def test_radar_weather_fetcher_replaces_precipitation_in_window():
    def fake_hourly(points, half_size_m, start_utc, end_utc, cache_dir, http_get=None, now_utc=None):
        assert half_size_m == 2000.0
        return _hourly([(50.0, 21.0, pd.Timestamp("2026-09-21 12:00", tz="UTC"), 20.0)])

    fetcher = make_radar_weather_fetcher(
        _base_fetcher, half_size_m=2000.0, window_days=30, cache_dir="unused",
        now_utc=datetime(2026, 9, 26, 10, tzinfo=timezone.utc), today=date(2026, 9, 26),
        radar_hourly_fn=fake_hourly)
    out = fetcher([(50.0, 21.0)], 92, forecast_days=1)
    assert out["precipitation_mm"].tolist() == pytest.approx([20.0 + 17.0 * 23 / 24, 13.0])
    assert out["radar_frac"].tolist() == pytest.approx([1 / 24, 0.0])


def test_radar_unavailable_falls_back_to_model_with_warning(capsys):
    def down(*args, **kwargs):
        raise RadarUnavailableError("dns")

    fetcher = make_radar_weather_fetcher(
        _base_fetcher, half_size_m=2000.0, window_days=30, cache_dir="unused",
        now_utc=datetime(2026, 9, 26, 10, tzinfo=timezone.utc), today=date(2026, 9, 26),
        radar_hourly_fn=down)
    out = fetcher([(50.0, 21.0)], 92)
    assert out["precipitation_mm"].tolist() == pytest.approx([17.0, 13.0])
    assert (out["radar_frac"] == 0.0).all()
    assert "UWAGA: radar IMGW niedostepny" in capsys.readouterr().out
```

```python
# tests/test_weather.py (append)
def test_compute_weather_features_rain_radar_coverage_is_exp_weighted_radar_frac():
    dates = pd.date_range("2026-09-01", periods=26, freq="D")
    frac = [0.0] * 25 + [1.0]  # only the most recent day from radar
    df = pd.DataFrame({"lat": 50.0, "lon": 21.0, "date": dates, "precipitation_mm": 1.0,
                       "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0, "et0_mm": 1.0,
                       "soil_moisture": 0.3, "radar_frac": frac})
    feat = compute_weather_features(df).iloc[0]
    weights = 0.5 ** (np.arange(25, -1, -1) / 10.0)
    assert feat["rain_radar_coverage"] == pytest.approx(weights[-1] / weights.sum())


def test_compute_weather_features_without_radar_frac_reports_zero_coverage():
    dates = pd.date_range("2026-09-01", periods=5, freq="D")
    df = pd.DataFrame({"lat": 50.0, "lon": 21.0, "date": dates, "precipitation_mm": 1.0,
                       "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0, "et0_mm": 1.0,
                       "soil_moisture": 0.3})
    assert compute_weather_features(df).iloc[0]["rain_radar_coverage"] == 0.0
```

```python
# tests/test_orchestrate.py (append)
def test_run_poc_exposes_rain_radar_coverage_per_stand_and_in_diagnostics():
    def radar_weather_fetcher(points, past_days, forecast_days=1):
        df = fake_weather_fetcher(points, past_days, forecast_days)
        df["radar_frac"] = 1.0
        return df

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=radar_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert result["rain_radar_coverage"].tolist() == pytest.approx([1.0, 1.0])
    assert result.attrs["diagnostics"]["radar_coverage_mean"] == pytest.approx(1.0)


def test_run_poc_without_radar_reports_zero_coverage():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert result["rain_radar_coverage"].tolist() == [0.0, 0.0]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_radar.py tests/test_weather.py tests/test_orchestrate.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'make_radar_weather_fetcher'` (and `KeyError: 'rain_radar_coverage'` in the other two files).

- [ ] **Step 3: Implement**

Append to `pipeline/radar.py`:

```python
def radar_window(today: date, window_days: int, now_utc: datetime) -> tuple[date, date, datetime, datetime]:
    """Local-day window [today - window_days + 1, today] and its UTC bounds
    (end clipped to now: future hours have no radar)."""
    window_start = today - timedelta(days=window_days - 1)
    start_utc = datetime(window_start.year, window_start.month, window_start.day,
                         tzinfo=WARSAW).astimezone(timezone.utc)
    nxt = today + timedelta(days=1)
    end_utc = min(now_utc, datetime(nxt.year, nxt.month, nxt.day, tzinfo=WARSAW).astimezone(timezone.utc))
    return window_start, today, start_utc, end_utc


def make_radar_weather_fetcher(base_fetcher, *, half_size_m: float, window_days: int, cache_dir,
                               http_get=None, now_utc: datetime | None = None, today: date | None = None,
                               radar_hourly_fn=None):
    """Wrap an Open-Meteo weather_fetcher (same signature) so precipitation
    in the radar window comes from RainGRS. IMGW down -> Open-Meteo only."""
    radar_hourly_fn = radar_hourly_fn or radar_hourly_at_points

    def fetcher(points, past_days, forecast_days=1):
        daily = base_fetcher(points, past_days, forecast_days=forecast_days)
        now = now_utc or datetime.now(timezone.utc)
        local_today = today or now.astimezone(WARSAW).date()
        window_start, window_end, start_utc, end_utc = radar_window(local_today, window_days, now)
        try:
            hourly = radar_hourly_fn(points, half_size_m, start_utc, end_utc, cache_dir,
                                     http_get=http_get, now_utc=now)
        except RadarUnavailableError as exc:
            print(f"UWAGA: radar IMGW niedostepny ({exc}) -- opady tylko z modelu Open-Meteo.", flush=True)
            hourly = pd.DataFrame({"lat": [], "lon": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"),
                                   "precip_mm": []})
        return merge_radar_into_daily(daily, radar_daily_at_points(hourly), window_start, window_end)

    return fetcher
```

In `pipeline/weather.py`, add next to `_exp_weighted_sum`:

```python
def _exp_weighted_mean(series: pd.Series, window: int, half_life_days: float = 10.0) -> float:
    """Same weights as _exp_weighted_sum, normalised -- the share of the
    P26w window's weight that `series` (0..1 per day) represents."""
    tail = series.iloc[-window:]
    ages = np.arange(len(tail) - 1, -1, -1)
    weights = 0.5 ** (ages / half_life_days)
    return float((tail.to_numpy(dtype=float) * weights).sum() / weights.sum())
```

In `compute_weather_features`, inside the loop after `p26w = ...`:

```python
        # Plan A1: share of the P26w window's weight whose rain came from
        # the IMGW radar (pipeline.radar) rather than Open-Meteo's model.
        rain_radar_coverage = (
            _exp_weighted_mean(group["radar_frac"], window=min(26, len(p)))
            if "radar_frac" in group else 0.0
        )
```

and add `"rain_radar_coverage": rain_radar_coverage,` to the appended row dict.

In `pipeline/orchestrate.py::run_poc`: next to `m_values, t_values, k_frost_values = [], [], []` add `rain_radar_coverage_values = []`; after `wrow = _nearest_weather_row(centroid, weather_feat_gdf)` add
`rain_radar_coverage_values.append(float(wrow.get("rain_radar_coverage", 0.0)))`;
after `stands["K_frost"] = k_frost_values` add `stands["rain_radar_coverage"] = rain_radar_coverage_values`; in `stands.attrs["diagnostics"]` add
`"radar_coverage_mean": float(sum(rain_radar_coverage_values) / len(rain_radar_coverage_values)) if rain_radar_coverage_values else 0.0,`.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: whole suite passes (previous count + 7).

- [ ] **Step 5: Commit**

```bash
git add pipeline/radar.py pipeline/weather.py pipeline/orchestrate.py tests/test_radar.py tests/test_weather.py tests/test_orchestrate.py
git commit -m "feat: radar-backed weather fetcher and rain_radar_coverage per stand (plan A1 task 4)"
```

---

## Task 5: Confidence, profile, export, frontend field + IMGW attribution

**Files:**
- Modify: `profiles/boletus_edulis.yaml`, `pipeline/confidence.py`, `pipeline/export.py`, `frontend/src/model.ts`, `frontend/src/main.ts` (about dialog), `frontend/README.md`
- Test: `tests/test_confidence.py`, `tests/test_export.py`, `frontend/src/model.test.ts`

**Interfaces:**
- Consumes: per-stand `rain_radar_coverage` (Task 4).
- Produces: profile keys `radar.enabled` (bool), `radar.window_days` (30), `radar.min_coverage_for_quality` (0.8), `confidence.data_quality_factors.pogoda_radar_1km` (0.9), `confidence.reasons.weather_radar`; export field `rain_radar_coverage`; TS `Stand.rain_radar_coverage?: number | null`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_confidence.py (append)
def test_score_data_quality_uses_radar_factor_when_coverage_high():
    base = {"species_cd": "SO", "s_host_source": "wfs"}
    nwp = score_data_quality({**base, "rain_radar_coverage": 0.0}, PROFILE)
    radar = score_data_quality({**base, "rain_radar_coverage": 0.9}, PROFILE)
    f = PROFILE["confidence"]["data_quality_factors"]
    assert radar / nwp == pytest.approx(f["pogoda_radar_1km"] / f["pogoda_nwp_2km"])


def test_compute_confidence_reason_names_radar_only_above_threshold():
    reasons_cfg = PROFILE["confidence"]["reasons"]
    _, low = compute_confidence({"species_cd": "SO", "rain_radar_coverage": 0.5}, PROFILE)
    _, high = compute_confidence({"species_cd": "SO", "rain_radar_coverage": 0.8}, PROFILE)
    _, missing = compute_confidence({"species_cd": "SO"}, PROFILE)
    assert reasons_cfg["weather_nwp"] in low and reasons_cfg["weather_radar"] not in low
    assert reasons_cfg["weather_radar"] in high and reasons_cfg["weather_nwp"] not in high
    assert reasons_cfg["weather_nwp"] in missing
```

(If `tests/test_confidence.py` does not already import `pytest`, `score_data_quality`, `compute_confidence`, `PROFILE`, add the imports at the top in the same style as the existing ones.)

```python
# tests/test_export.py (append)
from pipeline.export import SCORE_FIELDS


def test_score_fields_include_rain_radar_coverage():
    assert "rain_radar_coverage" in SCORE_FIELDS
```

`build_score_record` reads every `SCORE_FIELDS` entry with `row[field]` (strict, same as `G_season`/`tie_break`), so the stand fixtures used by `build_score_record(`/`write_scores_json(` in `tests/test_export.py` (lines ~49–112, helper `_enriched_stands()` and the inline rows) and `tests/test_frontend_export.py:33` need `"rain_radar_coverage": 0.0` added — find them with `grep -n "tie_break" tests/test_export.py tests/test_frontend_export.py` (the previous optional field was added to exactly those fixtures) and add the new key next to it.

```ts
// frontend/src/model.test.ts (append inside the same describe block as the G_season tests, ~line 114)
  it("accepts an optional rain_radar_coverage field and still loads without it", () => {
    const scores = [
      { ...score("A", 40), rain_radar_coverage: 0.93 },
      score("B", 30), // no rain_radar_coverage -- older export
    ];
    const result = parseData(scores, stands);
    expect(result.scores.map((s) => s.rain_radar_coverage)).toEqual([0.93, undefined]);
  });
  it("rejects a malformed rain_radar_coverage instead of silently accepting it", () => {
    expect(() =>
      parseData(
        [{ ...score("A", 40), rain_radar_coverage: "not-a-number" }, score("B", 30)],
        stands,
      ),
    ).toThrow();
  });
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_confidence.py tests/test_export.py -q -p no:cacheprovider` and `cd frontend && npm test`
Expected: FAIL — `KeyError: 'pogoda_radar_1km'`, `AssertionError` on SCORE_FIELDS, Vitest failure on the string value.

- [ ] **Step 3: Implement**

`profiles/boletus_edulis.yaml`:
- under `confidence.data_quality_factors` add
  `    pogoda_radar_1km: 0.9                 # [E] plan 2026-09-26 A1: opady z radaru IMGW RainGRS 1 km (temperatura nadal NWP) -- lepsze niz NWP 0,8, nie pelne 1,0`
- under `confidence.reasons` add
  `    weather_radar: "opady z radaru IMGW ~1 km (RainGRS), temperatura z modelu ~2 km"`
- new top-level section (after `pressure:`):

```yaml
radar:
  # Plan 2026-09-26 A1 (docs/archiwum/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md):
  # IMGW-PIB RainGRS replaces Open-Meteo precipitation for local days in the
  # last window_days days; Open-Meteo fills missing hours and the forecast.
  enabled: true
  window_days: 30                # covers P26w (26 d) + P5
  min_coverage_for_quality: 0.8  # rain_radar_coverage threshold for pogoda_radar_1km
```

`pipeline/confidence.py`:

```python
def _uses_radar(row, profile) -> bool:
    coverage = row.get("rain_radar_coverage")
    return coverage is not None and coverage >= profile["radar"]["min_coverage_for_quality"]
```

In `score_data_quality` replace the return with:

```python
    weather = cfg["pogoda_radar_1km"] if _uses_radar(row, profile) else cfg["pogoda_nwp_2km"]
    return kompletnosc * cfg["swiezosc_bez_s2"] * weather
```

In `compute_confidence` replace the `if factors["pogoda_nwp_2km"] < 1.0:` block with:

```python
    if _uses_radar(row, profile):
        reasons.append(cfg["reasons"]["weather_radar"])
    elif factors["pogoda_nwp_2km"] < 1.0:
        reasons.append(cfg["reasons"]["weather_nwp"])
```

(`row` may be a pandas Series from `pipeline/mvp.py`; `.get` works on both. A NaN coverage compares False → NWP path, which is the intended fallback.)

`pipeline/export.py`: append to `SCORE_FIELDS`, after `"tie_break",`:

```python
    # Plan 2026-09-26 A1: exp-weighted share of the P26w window whose rain
    # came from the IMGW radar (pipeline.radar), 0 = Open-Meteo only.
    "rain_radar_coverage",
```

`frontend/src/model.ts`: add `rain_radar_coverage?: number | null;` to the score interface next to `G_season?`, and in the validation chain next to `(s.G_season === undefined || numeric(s.G_season)) &&` add `(s.rain_radar_coverage === undefined || numeric(s.rain_radar_coverage)) &&` (use the same null handling the G_season line uses).

`frontend/src/main.ts` (about dialog `source-links`): after the Open-Meteo link insert
`<a href="https://danepubliczne.imgw.pl/" target="_blank" rel="noopener noreferrer">IMGW-PIB (radar RainGRS, dane przetworzone)</a>, `.

`frontend/README.md`: add a short "Źródła danych" line: "Opady z ostatnich 30 dni: radar IMGW-PIB RainGRS (1 km, godzinowy), uzupełniany modelem Open-Meteo. Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy; dane zostały przetworzone (sumy dobowe, średnie blokowe)."

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`, then in `frontend/`: `npm test`, `npx tsc --noEmit`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add profiles/boletus_edulis.yaml pipeline/confidence.py pipeline/export.py tests/test_confidence.py tests/test_export.py frontend/src/model.ts frontend/src/model.test.ts frontend/src/main.ts frontend/README.md
git commit -m "feat: radar-aware weather confidence, export field and IMGW attribution (plan A1 task 5)"
```

---

## Task 6: `prepare_trip` wiring + `--no-radar`

**Files:**
- Modify: `pipeline/prepare_trip.py`
- Test: `tests/test_prepare_trip.py` (append)

**Interfaces:**
- Consumes: `make_radar_weather_fetcher` (Task 4), `profile["radar"]` (Task 5).
- Note: the test file imports the module as `trip` inside individual tests (`import pipeline.prepare_trip as trip`, see line ~28) — do the same at the top of each new test function.
- Produces: CLI flag `--no-radar` (`args.no_radar: bool`); `build_weather_fetcher(base_fetcher, *, use_radar: bool, profile: dict, grid_spacing_m: float, cache_dir: pathlib.Path, radar_factory=make_radar_weather_fetcher)`; `run_trip_preparation(..., use_radar: bool = True)`; `summary["radar_coverage_mean"]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prepare_trip.py (append)
def test_parse_args_no_radar_flag():
    import pipeline.prepare_trip as trip
    assert trip.parse_args(["--lat", "50.0", "--lon", "21.0"]).no_radar is False
    assert trip.parse_args(["--lat", "50.0", "--lon", "21.0", "--no-radar"]).no_radar is True


def test_build_weather_fetcher_wraps_with_radar_using_half_grid_spacing(tmp_path):
    import pipeline.prepare_trip as trip
    captured = {}

    def factory(base, **kwargs):
        captured.update(kwargs)
        return "wrapped"

    base = object()
    profile = {"radar": {"enabled": True, "window_days": 30, "min_coverage_for_quality": 0.8}}
    out = trip.build_weather_fetcher(base, use_radar=True, profile=profile, grid_spacing_m=4000.0,
                                     cache_dir=tmp_path, radar_factory=factory)
    assert out == "wrapped"
    assert captured == {"half_size_m": 2000.0, "window_days": 30, "cache_dir": tmp_path / "radar_grs"}


def test_build_weather_fetcher_returns_base_when_radar_disabled(tmp_path):
    import pipeline.prepare_trip as trip
    base = object()
    on = {"radar": {"enabled": True, "window_days": 30, "min_coverage_for_quality": 0.8}}
    off = {"radar": {"enabled": False, "window_days": 30, "min_coverage_for_quality": 0.8}}
    assert trip.build_weather_fetcher(base, use_radar=False, profile=on, grid_spacing_m=4000.0,
                                      cache_dir=tmp_path) is base
    assert trip.build_weather_fetcher(base, use_radar=True, profile=off, grid_spacing_m=4000.0,
                                      cache_dir=tmp_path) is base
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prepare_trip.py -q -p no:cacheprovider`
Expected: FAIL — unrecognized `--no-radar` / `AttributeError: build_weather_fetcher`.

- [ ] **Step 3: Implement**

In `pipeline/prepare_trip.py`:
- import: `from pipeline.radar import make_radar_weather_fetcher`
- in `parse_args`, after `--cache-dir`:

```python
    parser.add_argument(
        "--no-radar", action="store_true",
        help="Nie uzywaj radaru IMGW (RainGRS) -- opady tylko z modelu Open-Meteo (np. do porownania).",
    )
```

- new module-level function (near `radius_scaled_spacing`):

```python
def build_weather_fetcher(base_fetcher, *, use_radar: bool, profile: dict, grid_spacing_m: float,
                          cache_dir: pathlib.Path, radar_factory=make_radar_weather_fetcher):
    """Plan 2026-09-26 A1: wrap the Open-Meteo fetcher so past precipitation
    comes from the IMGW radar, averaged over each weather point's own
    grid_spacing_m square (the area whose stands use that point)."""
    if not use_radar or not profile["radar"]["enabled"]:
        return base_fetcher
    return radar_factory(
        base_fetcher,
        half_size_m=grid_spacing_m / 2.0,
        window_days=profile["radar"]["window_days"],
        cache_dir=pathlib.Path(cache_dir) / "radar_grs",
    )
```

- `run_trip_preparation(...)` gains `use_radar: bool = True` (last parameter); in the `run_poc(...)` call replace the `weather_fetcher=` argument with

```python
        weather_fetcher=build_weather_fetcher(
            functools.partial(fetch_weather_raw, call_api=_weather_call_api, cache_dir=cache_dir),
            use_radar=use_radar, profile=profile, grid_spacing_m=grid_spacing_m, cache_dir=cache_dir,
        ),
```

- after the existing `run_poc: ...` print add
  `print(f"Opady z radaru IMGW: srednie pokrycie okna P26w {scored.attrs['diagnostics']['radar_coverage_mean']:.0%}", flush=True)`
- add `"radar_coverage_mean": scored.attrs["diagnostics"]["radar_coverage_mean"],` to the summary dict (next to `"forecast_days"`).
- `main()`: pass `use_radar=not args.no_radar` to `run_trip_preparation`.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/prepare_trip.py tests/test_prepare_trip.py
git commit -m "feat: wire IMGW radar into prepare_trip with --no-radar escape hatch (plan A1 task 6)"
```

---

## Task 7: Validation notebooks (stations; radar vs ERA5 bias)

**Files:**
- Create: `notebooks/04_radar_vs_stations.py`, `notebooks/05_radar_era5_bias.py`

**Interfaces:**
- Consumes: `pipeline.radar.radar_hourly_at_points`, `radar_daily_at_points`; `pipeline.weather._default_open_meteo_call`, `fetch_archive_daily` (committed in Task 0; if the user declined that commit, stop and ask).

- [ ] **Step 1: Station comparison notebook**

```python
# notebooks/04_radar_vs_stations.py
"""Plan A1 Task 7: RainGRS vs Open-Meteo vs independent Weathercloud stations.
Station data: cache/stations/weathercloud_2026-09.yaml (gitignored -- private
station locations). Run: .venv/Scripts/python.exe notebooks/04_radar_vs_stations.py"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

import pipeline.radar as radar
from pipeline.weather import _default_open_meteo_call

STATIONS = yaml.safe_load(Path("cache/stations/weathercloud_2026-09.yaml").read_text(encoding="utf-8"))["stations"]
FIRST, LAST = date(2026, 8, 29), date(2026, 9, 26)
FULL_FROM, FULL_TO = date(2026, 9, 13), date(2026, 9, 23)  # archive days with all 24 hours


def radar_daily(points, shift_hours: int) -> pd.DataFrame:
    start = datetime(2026, 8, 28, 22, tzinfo=timezone.utc)
    end = datetime(2026, 9, 26, 22, tzinfo=timezone.utc)
    hourly = radar.radar_hourly_at_points(points, 0, start, end, Path("cache/radar_grs"))
    hourly["hour_end_utc"] = hourly["hour_end_utc"] + pd.Timedelta(hours=shift_hours)
    return radar.radar_daily_at_points(hourly)


def main():
    names = list(STATIONS)
    points = [(STATIONS[n]["lat"], STATIONS[n]["lon"]) for n in names]
    om = _default_open_meteo_call(points, past_days=(date.today() - FIRST).days, forecast_days=1)
    for shift, label in [(0, "znacznik = koniec godziny"), (1, "znacznik = poczatek godziny")]:
        rd = radar_daily(points, shift)
        print(f"\n### {label}")
        for name, (lat, lon), om_point in zip(names, points, om):
            obs = {date.fromisoformat(str(k)): v for k, v in STATIONS[name]["daily_mm"].items()}
            om_by_day = {pd.Timestamp(t).tz_convert("Europe/Warsaw").date(): float(v)
                         for t, v in zip(om_point["date"], om_point["precipitation_mm"])}
            r = rd[(rd["lat"] == lat) & (rd["lon"] == lon)].set_index("local_date")
            rows = []
            d = FULL_FROM
            while d <= FULL_TO:
                rows.append((obs.get(d, 0.0), float(r["radar_mm"].get(d, 0.0)), om_by_day.get(d, float("nan"))))
                d += timedelta(days=1)
            df = pd.DataFrame(rows, columns=["obs", "radar", "om"])
            print(f"{name:20s} 13-23.09 suma obs={df.obs.sum():5.1f} radar={df.radar.sum():5.1f} "
                  f"OM={df.om.sum():5.1f} | MAE radar={(df.radar - df.obs).abs().mean():.2f} "
                  f"OM={(df.om - df.obs).abs().mean():.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and check acceptance**

Run: `.venv/Scripts/python.exe notebooks/04_radar_vs_stations.py` (first run downloads ~2.3 GB of archive tars, ~5 min; writes ~150 MB to `cache/radar_grs/`).
Accept when, for "znacznik = koniec godziny", 13–23.09 radar MAE is within ±0.05 mm of the spike: S1 0.91, S2 0.28, S3 0.55, S4 0.38, and radar MAE < OM MAE for all four. If "poczatek godziny" gives a clearly lower total MAE (>5% relative), set `GRS_TIMESTAMP_IS_HOUR_END = False` in `pipeline/radar.py`, rerun the whole test suite, and record it. If acceptance fails otherwise, stop and report the table.

- [ ] **Step 3: Radar vs ERA5 bias notebook (D1)**

```python
# notebooks/05_radar_era5_bias.py
"""Plan A1 D1 check: is RainGRS systematically wetter/drier than the
Open-Meteo archive (ERA5) that the 1991-2020 climatology comes from? Sample:
2025-08-01..2025-09-30 on the Bedziemysl 20 km weather grid. ~61 archive
days (~5 GB download, ~15 min). Run: .venv/Scripts/python.exe notebooks/05_radar_era5_bias.py"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import pipeline.radar as radar
from pipeline.orchestrate import WEATHER_GRID_SPACING_M
from pipeline.prepare_trip import _radius_scaled_spacing
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import fetch_archive_daily, make_grid

LAT, LON, RADIUS_KM = 50.0555, 21.7889, 20.0


def main():
    spacing = _radius_scaled_spacing(WEATHER_GRID_SPACING_M, RADIUS_KM)
    points = make_grid(tile_bbox_2180(LAT, LON, size_km=2 * RADIUS_KM), spacing_m=spacing)
    era5 = fetch_archive_daily(points, "2025-08-01", "2025-09-30", cache_dir=Path("cache"))
    hourly = radar.radar_hourly_at_points(
        points, spacing / 2, datetime(2025, 7, 31, 22, tzinfo=timezone.utc),
        datetime(2025, 9, 30, 22, tzinfo=timezone.utc), Path("cache/radar_grs"))
    rd = radar.radar_daily_at_points(hourly)
    full = rd[rd["radar_hours"] == rd["expected_hours"]]
    era5["local_date"] = era5["date"].dt.tz_convert("Europe/Warsaw").dt.date
    joined = full.merge(era5[["lat", "lon", "local_date", "precipitation_mm"]], on=["lat", "lon", "local_date"])
    ratio = joined["radar_mm"].sum() / joined["precipitation_mm"].sum()
    print(f"punkty={len(points)} dni z pelnym radarem={joined['local_date'].nunique()} "
          f"suma radar={joined['radar_mm'].sum():.0f} ERA5={joined['precipitation_mm'].sum():.0f} "
          f"stosunek radar/ERA5={ratio:.3f}")
    per_point = joined.groupby(["lat", "lon"])[["radar_mm", "precipitation_mm"]].sum()
    print((per_point["radar_mm"] / per_point["precipitation_mm"]).describe().round(3))


if __name__ == "__main__":
    main()
```

(`_radius_scaled_spacing(base_spacing_m, radius_km)` and `pipeline.tiles.tile_bbox_2180(lat, lon, size_km=...)` are exactly what `run_trip_preparation` uses, so the grid matches a real `--radius-km 20` run.)

- [ ] **Step 4: Run it (background, ~15 min) and apply the D1 rule**

Run: `.venv/Scripts/python.exe notebooks/05_radar_era5_bias.py`
If 0.85 ≤ ratio ≤ 1.15: record the numbers, no code change. Otherwise **stop and ask the user** (options to present: per-area scale factor applied to radar before percentile ranking; radar-only climatology from 2018–2025; accept the bias).

- [ ] **Step 5: Commit**

```bash
git add notebooks/04_radar_vs_stations.py notebooks/05_radar_era5_bias.py
git commit -m "chore: radar validation notebooks (stations, ERA5 bias) (plan A1 task 7)"
```

---

## Task 8: Real run Będziemyśl, before/after, docs, final verification

**Files:**
- Modify: `docs/archiwum/CODEX-HANDOFF.md` (new top note (24)), `docs/archiwum/projekt-borowik.md` (radar sections)

- [ ] **Step 1: Before/after runs**

```bash
.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 50.0555 --lon 21.7889 --radius-km 20 --no-radar --out-dir notebooks/output/no_radar
.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 50.0555 --lon 21.7889 --radius-km 20
```

Expected: both complete; the radar run prints `Radar IMGW (RainGRS): ...` and `Opady z radaru IMGW: srednie pokrycie okna P26w NN%` with NN ≥ 70 (lower only if run right after midnight — today's local day then has almost no radar hours and the highest weight).

- [ ] **Step 2: Compare** (one-off inline script, not committed): for both `scores_{today}.json`, print the M distribution (parse `M=` from the `moisture` explanation text as in the 2026-09-26 session), F classes, R ≥ 85 count and the 5 regions (`regions_{today}.json` centroids + rank_score). Specifically check whether the sharp M step 0.43 → 0.94 around lon 21.72 (Open-Meteo grid artefact seen 2026-09-26) is gone or smaller. Record the table for the handoff note. Sync the frontend data the usual way (`frontend/scripts/sync-data.mjs`, see `frontend/README.md`).

- [ ] **Step 3: Docs**

`docs/archiwum/projekt-borowik.md`: in the data-sources table row for "IMGW radar" (currently "tylko najnowszy plik ... Poza obecnym zakresem — wymaga pollera"), and the two bullets that say radar needs a permanently running poller (search for "pollera"), replace with: public RainGRS archive (daily tar, 2018→, lag ~2–3 days) + last ~30 h hourly files → no poller needed; integrated in plan A1 (2026-09-26) as the primary source of past precipitation; 4-station comparison summary (MAE radar 0.28–0.91 vs Open-Meteo 1.04–1.65 mm/d, 13–23.09.2026). In §10 data quality, add "0,9 opady z radaru IMGW 1 km (A1)" next to "0,8 NWP ~2 km".

`docs/archiwum/CODEX-HANDOFF.md`: new top note "## 2026-09-2x — aktualne (24): A1 — opady z radaru IMGW RainGRS" — what was built (modules, profile keys, CLI flag), Task 0 CRS/timestamp findings, Task 7 tables (stations + ERA5 ratio), Task 8 before/after table, test counts, open issues (soil moisture still from Open-Meteo — A2; per-stand radar sampling not done; next step A2 flush model, B pressure from cyclists/foot traffic on forest tracks).

- [ ] **Step 4: Final verification**

Run:
```bash
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
cd frontend && npm test && npx tsc --noEmit && npx vite build
git diff --check
```
Expected: all green; report exact pass counts in the handoff note.

- [ ] **Step 5: Commit**

```bash
git add docs/archiwum/CODEX-HANDOFF.md docs/archiwum/projekt-borowik.md
git commit -m "docs: record A1 radar precipitation integration and validation"
```
