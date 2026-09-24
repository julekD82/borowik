# Borowik GIS — `prepare_trip` CLI (parametrized, one-command trip prep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded single-location pipeline run (today only `notebooks/02_mvp.py`, fixed to the Kieleczka tile in RDLP Katowice) with a real command-line entry point — spec §13 priority 2 — that takes `--lat`/`--lon`/`--date`/`--radius-km` and produces `scores_{date}.json` + `regions_{date}.json` + a stand-geometry export for **any** location in Poland, without editing code. This closes the gap identified in `docs/projekt-borowik.md` §6: "Nie da się dziś uruchomić analizy dla innej lokalizacji niż zahardkodowana w `notebooks/02_mvp.py`."

**Architecture:** A new `pipeline/rdlp.py` module resolves which of the 17 BDL WFS wydzielenia layers covers a given (lat, lon) — the missing piece that made the location hardcoded in the first place — by point-in-polygon lookup against BDL's own `BDL:RDLP` boundary layer (verified live, see Global Constraints). A new `pipeline/prepare_trip.py` module wires that resolver together with the already-existing, already-tested pipeline (`run_poc`, `enrich_with_mvp_layers`, `group_into_regions`, the `write_*_json`/`export_stand_geometries` exports from `docs/superpowers/plans/2026-09-24-borowik-regions.md`) behind an `argparse` CLI, following the same real-I/O-with-injectable-boundaries shape every other `pipeline/*.py` module already uses. `notebooks/02_mvp.py` is left untouched (see Global Constraints) — this plan adds a new, separate entry point rather than risking the existing, already-manually-verified debug script and its `known_points.yaml` revalidation feature.

**Tech Stack:** Same as the rest of the repo — Python 3.12, `uv`, GeoPandas + Shapely 2 + pyproj, `requests`, `argparse` (standard library, no new dependency), pytest, `responses` for the network-touching `pipeline/rdlp.py` tests (matching `pipeline/bdl.py`/`pipeline/gdos.py`'s existing test style).

**Spec:** `docs/projekt-borowik.md` §6 (implementation status — this plan closes the "brak parametryzacji" gap), §7.2 (architecture: "jedno polecenie na komputerze przed wyjazdem"), §13 priority 2.

## Global Constraints

- Repo root: this worktree (`C:\Users\<uzytkownik>\Documents\Grzyby\.claude\worktrees\borowik-faza2-mvp-backend`). Python ≥3.12 via `uv`. No new entries needed in `pyproject.toml` (`argparse` is standard library).
- **RDLP boundary layer, verified live 2026-09-24 against the real BDL WFS** (`https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows`, `typeNames=BDL:RDLP`, no bbox filter — GeoServer, WFS 2.0.0, same stack as `pipeline.bdl`/`pipeline.gdos`): returns exactly **17 features**, CRS `EPSG:2180`, geometry type `MultiPolygon`, attributes `a_year`, `region_cd`, `region_name` (e.g. `"KATOWICE"`, `"ZIELONA GÓRA"` — uppercase, no leading/trailing whitespace, confirmed programmatically for all 17). Response size ~11.4 MB.
- **Layer-name mapping, verified live 2026-09-24 against `GetCapabilities`**: every one of the 17 real `BDL:RDLP_<Name>_wydzielenia` layer names (already used as the hardcoded `LAYER` constant in `notebooks/02_mvp.py`) equals `"BDL:RDLP_" + region_name.title().replace(" ", "_") + "_wydzielenia"` computed from the matching `BDL:RDLP` feature's `region_name` — verified by set-equality over all 17 pairs, not just spot-checked. This mapping is `pipeline.rdlp.layer_name_for_region`; Task 1 pins the full verified list as a regression test, the same durable-guard pattern `tests/test_profile_coverage.py` already uses for BDL site/species codes.
- **A point outside every RDLP polygon (outside Poland, or in the sea) is a hard stop, not a silent fallback.** `resolve_rdlp_layer` returns `None` in that case (Task 2); `run_trip_preparation` (Task 5) raises `TripPreparationError` instead of guessing a layer, and `main()` turns that into a clean one-line error message and exit code 1 — no stack trace.
- **`--radius-km` is accepted and validated (10–50, matching spec §9.1's suwak range and default of 25) but does not yet expand processing beyond the single 10×10 km BDL tile containing the point.** Spec §8.1 already documents this as a known, un-implemented gap ("Prekomputowany region domowy i cache wielu kafli jednocześnie nie są jeszcze zaimplementowane"). `main()` does not print a per-run caveat about this (it would be noise on every single run); the CLI's own `--help` text says so once, in the flag's own description.
- **`--date` is accepted and validated (`YYYY-MM-DD`) and used as the output-file date label, but does not change which weather data is fetched.** The underlying pipeline (`pipeline.weather.fetch_weather_raw`/`_default_open_meteo_call`) always fetches `past_days` history plus a 1-day forecast anchored on *today*, regardless of `--date` — extending that to a genuine future-dated forecast window is a change to `pipeline/weather.py`'s own semantics (which days a "window ending here" computation includes), out of scope for a CLI-parametrization plan. `main()` prints one caveat line when `--date` differs from today, explaining this, so the limitation is visible rather than silently wrong.
- **`notebooks/02_mvp.py` is not modified by this plan.** It already works (manually verified in the regions plan, including the Faza-1 `known_points.yaml` revalidation block that `run_trip_preparation` has no equivalent for) and stays as the fixed-tile manual/debug script it already documents itself to be in its own module docstring. `pipeline/prepare_trip.py` duplicates a small amount of orchestration glue from it (the `_rate_limited` Open-Meteo backoff wrapper, the cached-BDL-fetch closure) rather than extracting a shared helper that would require touching the notebook — an accepted, small, deliberate cost of not risking regression on already-verified code, consistent with this project's own instruction not to remove or destabilize working code.
- `pipeline/rdlp.py`'s cache (`cache/rdlp_boundaries.parquet`) is existence-only, same pattern as `pipeline.bdl.save_bdl_tile`/the notebook's `_cached_bdl_fetcher` — no age check. RDLP boundaries change on the order of years (new nadleśnictwa reorganizations), far slower than anything else in this pipeline; delete the cache file manually to force a refetch.

## Review Focus

- **A point outside every RDLP polygon** (e.g. lat/lon in the Baltic Sea, or outside Poland entirely): must produce a clean one-line CLI error and exit code 1, never a raw traceback or a silently-wrong layer guess. Covered by Task 2's unit test and Task 5's manual verification.
- **`--radius-km` outside 10–50 or a malformed `--date`**: `parse_args` must reject these with a clear `argparse` usage error (exit code 2, the standard argparse convention), not proceed with a bogus value into network calls. Covered in Task 4.
- **A region name with a multi-word or heavily-diacritic form** (e.g. `"ZIELONA GÓRA"`, `"BIAŁYSTOK"`): `layer_name_for_region` must produce exactly the real WFS layer name, not a plausible-looking near-miss (a subtly wrong layer name would fail the WFS call with an unhelpful GeoServer error far downstream, or silently query the wrong forest district). Covered in Task 1's regression test against all 17 real names.
- **Re-running for a location whose RDLP boundaries are already cached** must not re-fetch the 11.4 MB boundary set from the network. Covered in Task 3.
- **The RDLP boundary GeoDataFrame's CRS is EPSG:2180, but users naturally supply lat/lon in WGS84.** `resolve_rdlp_layer` must reproject the input point into the boundary data's actual CRS (not assume WGS84 throughout, and not hardcode EPSG:2180 as if it always matched), or every lookup silently fails. Covered in Task 2's test, which points are supplied in WGS84 against EPSG:2180 fixtures.

---

## File Structure

```
pipeline/
  rdlp.py            # NEW: fetch_rdlp_boundaries, layer_name_for_region, resolve_rdlp_layer, fetch_rdlp_boundaries_cached
  prepare_trip.py     # NEW: parse_args, TripPreparationError, run_trip_preparation, main
tests/
  test_rdlp.py         # NEW
  test_prepare_trip.py  # NEW
```

---

### Task 1: `pipeline/rdlp.py` — fetch RDLP boundaries + layer-name mapping

**Files:**
- Create: `pipeline/rdlp.py`
- Create: `tests/test_rdlp.py`

**Interfaces:**
- Consumes: nothing new (plain `requests`/`geopandas`, same as `pipeline.gdos`).
- Produces: `fetch_rdlp_boundaries(base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame` (columns include `region_name`; CRS `EPSG:2180`) and `layer_name_for_region(region_name: str) -> str`, both used by Task 2 and Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rdlp.py`:

```python
import responses

from pipeline.rdlp import fetch_rdlp_boundaries, layer_name_for_region, DEFAULT_WFS_URL

# Verified live 2026-09-24 (see plan Global Constraints): GetCapabilities'
# 17 real BDL:RDLP_<Name>_wydzielenia layer names, and BDL:RDLP's 17 real
# region_name attribute values, in the same RDLP order.
REAL_RDLP_LAYER_NAMES = [
    "BDL:RDLP_Białystok_wydzielenia", "BDL:RDLP_Gdańsk_wydzielenia", "BDL:RDLP_Katowice_wydzielenia",
    "BDL:RDLP_Kraków_wydzielenia", "BDL:RDLP_Krosno_wydzielenia", "BDL:RDLP_Lublin_wydzielenia",
    "BDL:RDLP_Olsztyn_wydzielenia", "BDL:RDLP_Piła_wydzielenia", "BDL:RDLP_Poznań_wydzielenia",
    "BDL:RDLP_Radom_wydzielenia", "BDL:RDLP_Szczecin_wydzielenia", "BDL:RDLP_Szczecinek_wydzielenia",
    "BDL:RDLP_Toruń_wydzielenia", "BDL:RDLP_Warszawa_wydzielenia", "BDL:RDLP_Wrocław_wydzielenia",
    "BDL:RDLP_Zielona_Góra_wydzielenia", "BDL:RDLP_Łódź_wydzielenia",
]
REAL_REGION_NAMES = [
    "BIAŁYSTOK", "GDAŃSK", "KATOWICE", "KRAKÓW", "KROSNO", "LUBLIN", "OLSZTYN", "PIŁA", "POZNAŃ",
    "RADOM", "SZCZECIN", "SZCZECINEK", "TORUŃ", "WARSZAWA", "WROCŁAW", "ZIELONA GÓRA", "ŁÓDŹ",
]


def test_layer_name_for_region_matches_all_17_real_bdl_layers():
    computed = {layer_name_for_region(name) for name in REAL_REGION_NAMES}
    assert computed == set(REAL_RDLP_LAYER_NAMES)


def test_layer_name_for_region_simple_case():
    assert layer_name_for_region("KATOWICE") == "BDL:RDLP_Katowice_wydzielenia"


def _region_feature(fid, region_name):
    return {
        "type": "Feature", "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380000, 486000], [500000, 486000], [500000, 700000], [380000, 700000], [380000, 486000]]]},
        "properties": {"a_year": 2026, "region_cd": "02", "region_name": region_name},
    }


@responses.activate
def test_fetch_rdlp_boundaries_parses_features():
    collection = {"type": "FeatureCollection", "features": [_region_feature(1, "KATOWICE"), _region_feature(2, "KRAKOW")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=collection, status=200)

    gdf = fetch_rdlp_boundaries()

    assert len(gdf) == 2
    assert set(gdf["region_name"]) == {"KATOWICE", "KRAKOW"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'pipeline.rdlp'`.

- [ ] **Step 3: Create `pipeline/rdlp.py` with `fetch_rdlp_boundaries` and `layer_name_for_region`**

```python
import io

import geopandas as gpd
import requests

DEFAULT_WFS_URL = "https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows"
RDLP_LAYER = "BDL:RDLP"


def fetch_rdlp_boundaries(base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame:
    """All 17 RDLP (regional forest directorate) boundary polygons in one
    unpaginated WFS 2.0.0 GetFeature call -- verified live 2026-09-24: 17
    features, ~11.4 MB, EPSG:2180, region_name attribute e.g. "KATOWICE".
    Small and slow-changing enough that no bbox filter or pagination is
    needed, unlike pipeline.bdl.fetch_bdl's per-tile wydzielenia fetch."""
    resp = requests.get(base_url, params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": RDLP_LAYER, "outputFormat": "application/json",
    }, timeout=60)
    resp.raise_for_status()
    return gpd.read_file(io.BytesIO(resp.content))


def layer_name_for_region(region_name: str) -> str:
    """Maps a BDL:RDLP `region_name` value (e.g. "ZIELONA GORA") to its
    wydzielenia WFS layer name (e.g. "BDL:RDLP_Zielona_Gora_wydzielenia").
    Verified live 2026-09-24 against all 17 real layer names from
    GetCapabilities -- region_name.title().replace(" ", "_") matches every
    one, including multi-word names."""
    return "BDL:RDLP_" + region_name.title().replace(" ", "_") + "_wydzielenia"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/rdlp.py tests/test_rdlp.py
git commit -m "feat: fetch BDL RDLP boundaries and map region_name to WFS layer names"
```

---

### Task 2: `resolve_rdlp_layer` — point-in-polygon lookup

**Files:**
- Modify: `pipeline/rdlp.py`
- Modify: `tests/test_rdlp.py`

**Interfaces:**
- Consumes: `layer_name_for_region` (Task 1); a `rdlp_gdf` shaped like `fetch_rdlp_boundaries`'s output (`region_name` column, any CRS the GeoDataFrame declares).
- Produces: `resolve_rdlp_layer(lat: float, lon: float, rdlp_gdf: gpd.GeoDataFrame) -> str | None`, used by Task 5.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rdlp.py`:

```python
import geopandas as gpd
from shapely.geometry import box

from pipeline.rdlp import resolve_rdlp_layer


def _rdlp_gdf():
    # Two adjacent, non-overlapping "RDLP" boxes in EPSG:2180 (real BDL
    # CRS), plain ASCII region_name -- layer_name_for_region's diacritic
    # handling is already covered by Task 1's regression test.
    return gpd.GeoDataFrame(
        {"region_name": ["KATOWICE", "KRAKOW"]},
        geometry=[box(380000, 486000, 390000, 496000), box(400000, 486000, 410000, 496000)],
        crs="EPSG:2180",
    )


def test_resolve_rdlp_layer_finds_containing_polygon_box1():
    # WGS84 centroid of box1 (380000,486000,390000,496000), computed via
    # pyproj EPSG:2180 -> EPSG:4326 and verified live against the real
    # BDL:RDLP data for a nearby point (see plan's live-verification notes).
    layer = resolve_rdlp_layer(lat=52.2729723880693, lon=17.314011763359918, rdlp_gdf=_rdlp_gdf())
    assert layer == "BDL:RDLP_Katowice_wydzielenia"


def test_resolve_rdlp_layer_finds_containing_polygon_box2():
    # WGS84 centroid of box2 (400000,486000,410000,496000).
    layer = resolve_rdlp_layer(lat=52.2767943376323, lon=17.607123274159406, rdlp_gdf=_rdlp_gdf())
    assert layer == "BDL:RDLP_Krakow_wydzielenia"


def test_resolve_rdlp_layer_returns_none_outside_every_polygon():
    # Well outside both boxes (roughly (600000, 700000) in EPSG:2180).
    layer = resolve_rdlp_layer(lat=54.15455087660452, lon=20.531757957006068, rdlp_gdf=_rdlp_gdf())
    assert layer is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: the three new tests FAIL with `ImportError: cannot import name 'resolve_rdlp_layer'`.

- [ ] **Step 3: Implement `resolve_rdlp_layer`**

Append to `pipeline/rdlp.py`:

```python
from shapely.geometry import Point


def resolve_rdlp_layer(lat: float, lon: float, rdlp_gdf: gpd.GeoDataFrame) -> str | None:
    """Which wydzielenia WFS layer covers (lat, lon), by point-in-polygon
    lookup against fetch_rdlp_boundaries' output. None if the point falls
    outside every RDLP polygon (outside Poland, or in the sea) -- BDL has
    no data to query there, and callers must treat that as a hard stop,
    not a silent fallback to some layer."""
    point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(rdlp_gdf.crs).iloc[0]
    hits = rdlp_gdf[rdlp_gdf.geometry.contains(point)]
    if len(hits) == 0:
        return None
    return layer_name_for_region(hits.iloc[0]["region_name"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/rdlp.py tests/test_rdlp.py
git commit -m "feat: resolve_rdlp_layer point-in-polygon lookup"
```

---

### Task 3: `fetch_rdlp_boundaries_cached`

**Files:**
- Modify: `pipeline/rdlp.py`
- Modify: `tests/test_rdlp.py`

**Interfaces:**
- Consumes: `fetch_rdlp_boundaries` (Task 1).
- Produces: `fetch_rdlp_boundaries_cached(cache_dir, base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame`, used by Task 5.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rdlp.py`:

```python
from pipeline.rdlp import fetch_rdlp_boundaries_cached


@responses.activate
def test_fetch_rdlp_boundaries_cached_writes_and_reuses_cache(tmp_path):
    collection = {"type": "FeatureCollection", "features": [_region_feature(1, "KATOWICE")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=collection, status=200)

    first = fetch_rdlp_boundaries_cached(tmp_path)
    assert len(first) == 1
    assert (tmp_path / "rdlp_boundaries.parquet").exists()
    assert len(responses.calls) == 1

    second = fetch_rdlp_boundaries_cached(tmp_path)  # cache hit -- no new HTTP call
    assert len(second) == 1
    assert len(responses.calls) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: the new test FAILS with `ImportError: cannot import name 'fetch_rdlp_boundaries_cached'`.

- [ ] **Step 3: Implement `fetch_rdlp_boundaries_cached`**

Append to `pipeline/rdlp.py` (add `import pathlib` to the existing import block at the top):

```python
def fetch_rdlp_boundaries_cached(cache_dir, base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame:
    """Existence-only cache (same pattern as pipeline.bdl.save_bdl_tile /
    the notebook's _cached_bdl_fetcher): RDLP boundaries change on the
    order of years, so no age check -- delete
    cache/rdlp_boundaries.parquet manually to force a refetch."""
    cache_dir = pathlib.Path(cache_dir)
    cache_path = cache_dir / "rdlp_boundaries.parquet"
    if cache_path.exists():
        return gpd.read_parquet(cache_path)
    gdf = fetch_rdlp_boundaries(base_url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(cache_path)
    return gdf
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rdlp.py -v`
Expected: 7 passed.

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (161 pre-existing + 7 new = 168 passed).

- [ ] **Step 6: Commit**

```bash
git add pipeline/rdlp.py tests/test_rdlp.py
git commit -m "feat: cache RDLP boundaries to disk"
```

---

### Task 4: `pipeline/prepare_trip.py::parse_args`

**Files:**
- Create: `pipeline/prepare_trip.py`
- Create: `tests/test_prepare_trip.py`

**Interfaces:**
- Consumes: nothing new (plain `argparse`).
- Produces: `parse_args(argv=None) -> argparse.Namespace` with fields `lat`, `lon`, `date`, `radius_km`, `profile`, `out_dir`, `cache_dir`; module-level constants `MIN_RADIUS_KM = 10.0`, `MAX_RADIUS_KM = 50.0`. Used by Task 5's `main`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prepare_trip.py`:

```python
import pytest

from pipeline.prepare_trip import parse_args, MIN_RADIUS_KM, MAX_RADIUS_KM


def test_parse_args_requires_lat_and_lon():
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_defaults():
    args = parse_args(["--lat", "50.5", "--lon", "18.6"])
    assert args.lat == 50.5
    assert args.lon == 18.6
    assert args.date is None
    assert args.radius_km == 25.0
    assert args.profile == "profiles/boletus_edulis.yaml"
    assert args.out_dir == "notebooks/output"
    assert args.cache_dir == "cache"


def test_parse_args_rejects_radius_below_minimum():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", "5"])


def test_parse_args_rejects_radius_above_maximum():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", "60"])


def test_parse_args_accepts_radius_at_boundaries():
    low = parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", str(MIN_RADIUS_KM)])
    high = parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", str(MAX_RADIUS_KM)])
    assert low.radius_km == MIN_RADIUS_KM
    assert high.radius_km == MAX_RADIUS_KM


def test_parse_args_rejects_malformed_date():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--date", "2026/09/24"])


def test_parse_args_accepts_well_formed_date():
    args = parse_args(["--lat", "50.5", "--lon", "18.6", "--date", "2026-10-05"])
    assert args.date == "2026-10-05"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prepare_trip.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'pipeline.prepare_trip'`.

- [ ] **Step 3: Create `pipeline/prepare_trip.py` with `parse_args`**

```python
import argparse
from datetime import date

MIN_RADIUS_KM = 10.0
MAX_RADIUS_KM = 50.0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prepare_trip",
        description="Przygotuj wyjazd: policz rejony poszukiwan prawdziwkow dla podanej lokalizacji.",
    )
    parser.add_argument("--lat", type=float, required=True, help="Szerokosc geograficzna (WGS84)")
    parser.add_argument("--lon", type=float, required=True, help="Dlugosc geograficzna (WGS84)")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Etykieta dnia w nazwach plikow wynikowych (YYYY-MM-DD), domyslnie dzisiaj. "
             "Nie zmienia okna pogodowego (zawsze 'teraz' -- patrz docs/projekt-borowik.md).",
    )
    parser.add_argument(
        "--radius-km", type=float, default=25.0,
        help=f"Deklarowany promien poszukiwan ({MIN_RADIUS_KM:.0f}-{MAX_RADIUS_KM:.0f} km). "
             "Obecnie tylko walidowany -- przetwarzany jest jeden kafel 10x10 km wokol punktu "
             "(patrz docs/projekt-borowik.md sec.8.1).",
    )
    parser.add_argument("--profile", type=str, default="profiles/boletus_edulis.yaml")
    parser.add_argument("--out-dir", type=str, default="notebooks/output")
    parser.add_argument("--cache-dir", type=str, default="cache")
    args = parser.parse_args(argv)
    if not (MIN_RADIUS_KM <= args.radius_km <= MAX_RADIUS_KM):
        parser.error(f"--radius-km must be between {MIN_RADIUS_KM:.0f} and {MAX_RADIUS_KM:.0f}")
    if args.date is not None:
        try:
            date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"--date must be YYYY-MM-DD, got {args.date!r}")
    return args
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prepare_trip.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/prepare_trip.py tests/test_prepare_trip.py
git commit -m "feat: prepare_trip CLI argument parsing and validation"
```

---

### Task 5: `run_trip_preparation` + `main` — wire the CLI end-to-end

**Files:**
- Modify: `pipeline/prepare_trip.py`

**Interfaces:**
- Consumes: `parse_args` (Task 4); `pipeline.rdlp.fetch_rdlp_boundaries_cached`/`resolve_rdlp_layer` (Tasks 2–3); `pipeline.bdl.fetch_bdl`/`save_bdl_tile`; `pipeline.tiles.tile_bbox_2180`; `pipeline.habitat.load_profile`; `pipeline.orchestrate.run_poc`; `pipeline.gdos.fetch_protected_areas`; `pipeline.osm.fetch_osm_features`; `pipeline.mvp.enrich_with_mvp_layers`; `pipeline.zakazy.check_periodic_ban`; `pipeline.regions.group_into_regions`; `pipeline.export.write_scores_json`/`export_stand_geometries`/`write_regions_json` — all consumed exactly as `notebooks/02_mvp.py` already wires them (no signature changes to any of them).
- Produces: `TripPreparationError(RuntimeError)`; `run_trip_preparation(lat, lon, day, radius_km, profile_path, out_dir, cache_dir) -> dict`; `main(argv=None) -> int`. This task has no new automated tests (real-I/O orchestration against five live network services — the same reason `notebooks/02_mvp.py`'s equivalent code has none); it is proven by the manual verification in Step 2 below, exactly as `notebooks/02_mvp.py` was proven in the regions plan's Task 6.

- [ ] **Step 1: Implement `run_trip_preparation` and `main`**

Append to `pipeline/prepare_trip.py` (add `functools`, `pathlib`, `sys`, `time` to the existing import block, plus the new imports below):

```python
import functools
import pathlib
import sys
import time

import geopandas as gpd
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl, save_bdl_tile
from pipeline.export import write_scores_json, export_stand_geometries, write_regions_json
from pipeline.gdos import fetch_protected_areas
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.orchestrate import run_poc
from pipeline.osm import fetch_osm_features
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer
from pipeline.regions import group_into_regions
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw,
    _default_open_meteo_call, _default_climatology_call,
)
from pipeline.zakazy import check_periodic_ban


class TripPreparationError(RuntimeError):
    """Raised for a known, clean failure (currently: point outside every
    RDLP) that main() turns into a one-line CLI error instead of a
    traceback. Not raised for network/API errors, which are out of this
    plan's scope (spec §13 priority 8) and still surface as-is."""


def _rate_limited(default_call, *args, max_attempts=6, backoff_s=65, pace_s=2.0):
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return default_call(*args)
        except OpenMeteoRequestsError as exc:
            if "limit" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def run_trip_preparation(lat: float, lon: float, day: str, radius_km: float,
                          profile_path: str, out_dir: pathlib.Path, cache_dir: pathlib.Path) -> dict:
    """Runs the full MVP pipeline (BDL -> weather -> mask -> H/F/P/R ->
    regions -> export) for the 10x10 km BDL tile containing (lat, lon).
    Returns a summary dict for the CLI to print; writes scores_{day}.json,
    regions_{day}.json and stands_mvp.parquet under out_dir as a side
    effect. radius_km is accepted for forward compatibility but does not
    yet change which tiles are processed (see plan Global Constraints)."""
    del radius_km  # not yet used -- documented limitation, see Global Constraints
    profile = load_profile(profile_path)
    bbox = tile_bbox_2180(lat, lon, size_km=10.0)
    cache_dir = pathlib.Path(cache_dir)
    tile_id = f"E{int(bbox[1])}N{int(bbox[0])}"
    tile_path = cache_dir / f"{tile_id}.parquet"

    print(f"Resolving RDLP for ({lat}, {lon})...")
    rdlp_gdf = fetch_rdlp_boundaries_cached(cache_dir)
    layer = resolve_rdlp_layer(lat, lon, rdlp_gdf)
    if layer is None:
        raise TripPreparationError(
            f"Punkt ({lat}, {lon}) nie lezy w zadnym RDLP (poza Polska?) -- BDL nie ma dla niego danych."
        )
    print(f"  RDLP layer: {layer}")

    def _cached_bdl_fetcher(layer, bbox_2180):
        if tile_path.exists():
            print(f"BDL tile cache hit: {tile_path}")
            return gpd.read_parquet(tile_path)
        print(f"BDL tile cache miss, fetching from WFS -> {tile_path}")
        gdf = fetch_bdl(layer, bbox_2180)
        save_bdl_tile(gdf, tile_id, cache_dir)
        return gdf

    def _weather_call_api(lat_, lon_, past_days):
        return _rate_limited(_default_open_meteo_call, lat_, lon_, past_days)

    def _climatology_call_api(lat_, lon_, start_year, end_year):
        return _rate_limited(_default_climatology_call, lat_, lon_, start_year, end_year)

    scored = run_poc(
        layer=layer, bbox_2180=bbox, profile=profile,
        bdl_fetcher=_cached_bdl_fetcher,
        weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api),
        climatology_fetcher=functools.partial(fetch_climatology_raw, call_api=_climatology_call_api),
    )
    print(f"run_poc: {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing structural mask")

    print("Fetching GDOS protected areas...")
    gdos_gdf = fetch_protected_areas(bbox)

    print("Fetching OSM parking/roads/places (Overpass)...")
    osm_features = fetch_osm_features(bbox, profile)

    print("Enriching with legal mask + presja + confidence + explanations...")
    enriched = enrich_with_mvp_layers(
        scored, profile, gdos_gdf, osm_features,
        zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
    )

    out_dir = pathlib.Path(out_dir)
    scores_path = write_scores_json(enriched, day=day, out_path=out_dir / f"scores_{day}.json")
    stands_path = export_stand_geometries(enriched, out_dir / "stands_mvp.parquet")

    print("Grouping into search regions...")
    regions = group_into_regions(enriched, profile)
    regions_path = write_regions_json(regions, day=day, out_path=out_dir / f"regions_{day}.json")

    return {
        "layer": layer, "tile_id": tile_id, "stand_count": len(scored),
        "mask_passing": int(enriched["mask_full"].sum()),
        "region_count": len(regions),
        "scores_path": scores_path, "stands_path": stands_path, "regions_path": regions_path,
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    today = date.today().isoformat()
    day = args.date or today
    if args.date is not None and args.date != today:
        print(
            f"Uwaga: prognoza pogody odzwierciedla dzisiejsze okno Open-Meteo, "
            f"nie dokladnie dzien {args.date} -- patrz docs/projekt-borowik.md sec.7.2."
        )
    try:
        summary = run_trip_preparation(
            lat=args.lat, lon=args.lon, day=day, radius_km=args.radius_km,
            profile_path=args.profile, out_dir=pathlib.Path(args.out_dir), cache_dir=pathlib.Path(args.cache_dir),
        )
    except TripPreparationError as exc:
        print(f"Blad: {exc}")
        return 1
    print(
        f"Gotowe: {summary['region_count']} rejon(y), "
        f"{summary['mask_passing']}/{summary['stand_count']} wydzielen przechodzi maske."
    )
    print(f"Wyniki: {summary['scores_path']}, {summary['regions_path']}, {summary['stands_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`main` reuses the `from datetime import date` already imported at module level for `parse_args`'s `date.fromisoformat` validation (Task 4) — no new datetime import needed here.

- [ ] **Step 2: Manual verification against live services, two locations (network-dependent, not covered by pytest)**

This module calls live BDL/GDOŚ/Overpass/Open-Meteo/zakazy-wstępu endpoints, same as `notebooks/02_mvp.py`. Run it for a location in a **different** RDLP than the one hardcoded in the notebook (Katowice), to prove the auto-resolution genuinely generalizes — Piła, verified live during planning to resolve to `BDL:RDLP_Piła_wydzielenia`:

Run: `.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 53.1509 --lon 16.7382`
Expected: prints `Resolving RDLP for (53.1509, 16.7382)...`, then `  RDLP layer: BDL:RDLP_Piła_wydzielenia`, then the same run_poc/GDOŚ/OSM/enrichment/region-grouping lines the regions plan's Task 6 already verified for Katowice, ending with `Gotowe: N rejon(y), ...` and a `Wyniki: ...` line naming three files under `notebooks/output/`. Confirm `notebooks/output/scores_<today>.json` and `notebooks/output/regions_<today>.json` were written/updated and are valid JSON.

Then verify the outside-Poland error path:

Run: `.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 0 --lon 0`
Expected: prints `Resolving RDLP for (0.0, 0.0)...` then `Blad: Punkt (0.0, 0.0) nie lezy w zadnym RDLP (poza Polska?) -- BDL nie ma dla niego danych.` and exits — check with `echo $?` (bash) that the exit code is `1`, not a Python traceback.

If either live run hits a transient service error unrelated to this plan's code (Overpass rate limiting, a transient BDL timeout — the same pre-existing flakiness the regions plan's Task 6 already noted), rerun once; if it still fails, capture the traceback in the commit message body instead of silently skipping verification.

- [ ] **Step 3: Run the full automated test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (175 passed: 168 after Task 3 + Task 4's 7 new `test_prepare_trip.py` tests, unchanged by this task — it adds no new automated tests, only the CLI wiring proven manually above).

- [ ] **Step 4: Commit**

```bash
git add pipeline/prepare_trip.py
git commit -m "feat: prepare_trip CLI end-to-end (any location, any RDLP)"
```

---

## Progress log (update this section as tasks complete — this is how a future session knows where to continue)

- [x] Task 1: `pipeline/rdlp.py` — fetch RDLP boundaries + layer-name mapping
- [x] Task 2: `resolve_rdlp_layer` — point-in-polygon lookup
- [x] Task 3: `fetch_rdlp_boundaries_cached`
- [x] Task 4: `pipeline/prepare_trip.py::parse_args`
- [x] Task 5: `run_trip_preparation` + `main` — wire the CLI end-to-end

**Plan complete (2026-09-24).** All 5 tasks implemented via TDD, full suite green (178 passed). Manually verified end-to-end against live BDL/GDOŚ/Overpass/Open-Meteo/zakazy services for **Piła** (53.1509, 16.7382) — a location and RDLP never hardcoded anywhere in this codebase — auto-resolving correctly to `BDL:RDLP_Piła_wydzielenia` and producing 4 regions from 1815 stands. Also verified the outside-Poland error path (clean exit code 1, no traceback).

Final whole-branch review (fresh subagent, opus) found two Important gaps, both fixed:
1. ~18% of 10×10 km tiles straddle two RDLP boundaries (reviewer's own grid sample over Poland); the CLI only ever fetched one, silently dropping the other's stands with no indication. Fixed with a warning (`pipeline.rdlp.regions_intersecting_bbox`) naming the missing RDLP(s) — **not** with full multi-layer fetching, which was ruled out of this fix pass as its own real feature (merging/deduplicating boundary-straddling stands, a cache-key change) deserving its own plan.
2. The outside-Poland exit-code-1 path had no automated test (manual-only). Added one via `monkeypatch`, no network needed.

Three Minor findings deferred (not fixed): `stands_mvp.parquet`'s filename has no date/location (inherited from the untouched notebook); a point exactly on an RDLP boundary line reports "outside Poland" (`contains` vs. `covers`, very unlikely with real float input); the BDL tile cache key doesn't include the layer (harmless today, a prerequisite if the deferred multi-layer-fetch feature is ever built).

**Next up:**
1. **RDLP-border multi-layer fetch** (the declined-in-this-fix-pass alternative above) — needs its own small plan: fetch every RDLP layer whose polygon intersects the tile bbox (not just the center-point layer), concatenate, decide how to handle any wydzielenia that appear in both fetches near the shared boundary, and extend the BDL tile cache key to include the layer set.
2. `docs/projekt-borowik.md` §13 priority 3 (routing-based accessibility for the top-N candidates: confirmed vs. potential entrances, real road-network distance instead of euclidean×1.3) — needs its own plan, not started. Priority 4 (minimal frontend) depends on both this plan and priority 3's region/stand shape being stable.
