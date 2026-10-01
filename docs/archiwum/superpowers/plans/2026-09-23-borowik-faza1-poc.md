# Borowik GIS — Faza 1 (Proof of Concept) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that BDL (drzewostany) and Open-Meteo (pogoda) data compose into a habitat/fruiting/ranking score per wydzielenie, rendered as a colored map for one 10×10 km tile, and that the ranking places the user's own known *Boletus edulis* spots near the top.

**Architecture:** Pure-Python pipeline, no server/DB. Small focused modules (`pipeline/tiles.py`, `pipeline/bdl.py`, `pipeline/habitat.py`, `pipeline/weather.py`, `pipeline/scoring.py`, `pipeline/validate.py`, `pipeline/orchestrate.py`) each independently unit-tested with synthetic data. Network-calling functions are isolated behind a thin, injectable `call_api`/`fetcher` boundary so the composition logic is testable without hitting real APIs; the real APIs are exercised once, manually, per task, against the concrete test tile.

**Tech Stack:** Python 3.12, `uv`, GeoPandas + Shapely 2 + pyogrio + pyproj, `requests` (BDL WFS), `openmeteo-requests` + `requests-cache` + `retry-requests` (Open-Meteo), PyYAML, folium, scipy, pytest, `responses` (HTTP mocking).

## Global Constraints

- Repo root: `C:\Users\<uzytkownik>\Documents\Grzyby` (no git repo yet — Task 1 initializes one).
- Python ≥3.12, dependency management via `uv` (spec §10 "Konkretne technologie").
- Storage format for Faza 1: GeoParquet files under `cache/`, no PostGIS/DB server (spec §6.1).
- Jednostka obliczeniowa: **wydzielenie BDL** (`stand_id` = `adr_for` + `@` + `a_year`), spec §3.2.
- BDL WFS endpoint: `https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows`, WFS 2.0.0, `outputFormat=application/json`.
- BDL CRS: **EPSG:2180**. Axis order for BBOX with `urn:ogc:def:crs:EPSG::2180` is **N_min,E_min,N_max,E_max** (spec §2.1, §7.1 — verified critical gotcha, do not swap).
- Test region (this plan): **Kieleczka, gmina Wielowieś** — centroid lat=50.526944, lon=18.605000 (EPSG:4326). Layer: `BDL:RDLP_Katowice_wydzielenia` — **[?] confirm exact name via WFS `GetCapabilities` before the first live call** (Task 3, Step "manual verification"); Nadleśnictwo Rudziniec, RDLP Katowice covers this gmina.
- Open-Meteo: free tier, non-commercial, no API key, <10 000 calls/day (spec §13). Use `openmeteo-requests` client with `requests_cache` + `retry_requests` per spec §10.
- Scoring formulas are fixed by spec §4 and §12.4 — do not invent alternatives:
  - `H = S_host^0.40 · S_site^0.35 · S_age^0.25`
  - `F = G_season · M^0.6 · T^0.4 · K_frost`, then `F_loc = clip(F · mod(m, pct_M), 0, 1)`
  - `M = logistic((mean(pct_CWB26, pct_SM) − 0.35) / 0.10)`
  - `T = exp(−(Tmean20 − 13)² / 32)`, ×0.3 if `Tmean5 > 17.5°C ∧ P5 < 5mm`
  - `K_frost = 0.2` if `Tmin3 < −2°C`; `0.6` if `−2…0°C`; else `1`
  - `R = 100 · MASK · H · F_loc` — **Faza 1 scope note:** the full spec formula also multiplies by `(1 − α·P)`, but Presja P and Dostępność A depend on OSM/population data that spec §9 assigns to Faza 2 (steps 8–9). Faza 1 computes `R` **without** the presja term (equivalent to α·P = 0). Do not add OSM fetching in this plan.
  - `MASK` (Faza 1 scope): `area_type == 'D-STAN' ∧ spec_age ≥ 12 ∧ NOT(zero-affinity species ∧ part_cd ≥ 8)`. The full spec mask (§4.2) also includes GDOŚ reserves and BDL WMS zakazy wstępu — that's explicitly Faza 2 (spec §9, step 8). Do not add legal-mask fetching in this plan.
  - `G_season` (Faza 1 scope): **constant 1.0**. Spec §4.4 defines it from a GBIF date-KDE, but GBIF fetching is not in the Faza 1 step list (spec §9, items 1–7) — it first appears bundled into "MVP źródła" in §11/Faza 2. Faza 1 hardcodes `G_season = 1.0` (documented simplification) so scope matches the spec's own Faza 1 boundary; Faza 2 replaces it.
- Host affinity table, site-type table, age curve: copied verbatim from spec §4.3 into `profiles/boletus_edulis.yaml` (Task 4).
- Known ambiguity in spec: §4.2's mask table lists "Tp" (topola) among zero-affinity mask species, but §4.3's host affinity table gives OS/TP = 0.2 (not zero) and only lists OL/JS/KL/WZ/AK at 0.0. This plan uses the §4.3 list (OL, JS, KL, WZ, AK) for the hard mask, since it's the more granular source — flagged `[?]` in code, not silently resolved.

---

## File Structure

```
Grzyby/
  pyproject.toml
  pipeline/
    __init__.py
    tiles.py         # EPSG:2180 tile bbox math (pure)
    bdl.py            # BDL WFS fetch + GeoParquet cache (thin IO + pure URL builder)
    habitat.py        # site_type/host/age scoring, MASK, H (pure, loads YAML profile)
    weather.py        # grid, weather fetch (DI), window features, climatology percentiles (pure)
    scoring.py         # M, T, K_frost, F, F_loc, R (pure)
    validate.py        # known-point ranking against scored stands (pure)
    orchestrate.py      # wires all fetchers/scorers together (DI-testable)
  profiles/
    boletus_edulis.yaml
  notebooks/
    01_poc.py          # thin script: real fetchers -> orchestrate.run_poc -> folium map
    known_points.example.yaml
  tests/
    test_tiles.py
    test_bdl.py
    test_habitat.py
    test_weather.py
    test_scoring.py
    test_validate.py
    test_orchestrate.py
  cache/                # gitignored, created at runtime
  docs/
    projekt-borowik.md  # already exists
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `pipeline/__init__.py`
- Create: `.gitignore`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: importable `pipeline` package with `pipeline.__version__`.

- [ ] **Step 1: Write the failing test**

`tests/test_setup.py`:
```python
import pipeline


def test_pipeline_package_has_version():
    assert pipeline.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline'` (or `uv` itself missing — install `uv` first if needed).

- [ ] **Step 3: Create the package and project files**

`pyproject.toml`:
```toml
[project]
name = "grzyby"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "geopandas>=1.0",
    "shapely>=2.0",
    "pyogrio>=0.9",
    "pyproj>=3.6",
    "requests>=2.31",
    "requests-cache>=1.2",
    "openmeteo-requests>=1.2",
    "retry-requests>=2.0",
    "pandas>=2.2",
    "numpy>=1.26",
    "pyyaml>=6.0",
    "folium>=0.16",
    "scipy>=1.13",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "responses>=0.25",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`pipeline/__init__.py`:
```python
__version__ = "0.1.0"
```

`.gitignore`:
```
cache/
.venv/
__pycache__/
*.pyc
notebooks/output/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv sync && uv run pytest tests/test_setup.py -v`
Expected: PASS

- [ ] **Step 5: Initialize git and commit**

```bash
git init
git add pyproject.toml pipeline/__init__.py .gitignore tests/test_setup.py
git commit -m "chore: scaffold Grzyby project with uv"
```

---

### Task 2: EPSG:2180 tile bbox utilities

**Files:**
- Create: `pipeline/tiles.py`
- Test: `tests/test_tiles.py`

**Interfaces:**
- Produces: `tile_bbox_2180(lat: float, lon: float, size_km: float = 10.0) -> tuple[float, float, float, float]` returning `(n_min, e_min, n_max, e_max)`.
- Produces: `wfs_bbox_param(bbox: tuple[float, float, float, float]) -> str`.
- Consumed by: Task 3 (`bdl.py`), Task 6 (`weather.py` grid).

- [ ] **Step 1: Write the failing test**

`tests/test_tiles.py`:
```python
from pipeline.tiles import tile_bbox_2180, wfs_bbox_param


def test_tile_bbox_is_exactly_size_km_square():
    n_min, e_min, n_max, e_max = tile_bbox_2180(50.526944, 18.605000, size_km=10.0)
    assert e_max - e_min == 10_000.0
    assert n_max - n_min == 10_000.0


def test_tile_bbox_center_is_inside_bbox():
    lat, lon = 50.526944, 18.605000
    n_min, e_min, n_max, e_max = tile_bbox_2180(lat, lon, size_km=10.0)
    from pyproj import Transformer
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    e_center, n_center = transformer.transform(lon, lat)
    assert e_min < e_center < e_max
    assert n_min < n_center < n_max


def test_wfs_bbox_param_uses_n_e_n_e_axis_order():
    bbox = (486000.0, 380000.0, 496000.0, 390000.0)  # n_min, e_min, n_max, e_max
    param = wfs_bbox_param(bbox)
    assert param == "486000.0,380000.0,496000.0,390000.0,urn:ogc:def:crs:EPSG::2180"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tiles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.tiles'`

- [ ] **Step 3: Implement**

`pipeline/tiles.py`:
```python
from pyproj import Transformer

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def tile_bbox_2180(lat: float, lon: float, size_km: float = 10.0) -> tuple[float, float, float, float]:
    """Return (n_min, e_min, n_max, e_max) in EPSG:2180 for a size_km x size_km
    tile centered on (lat, lon)."""
    e_center, n_center = _TO_2180.transform(lon, lat)
    half = size_km * 1000.0 / 2.0
    return (n_center - half, e_center - half, n_center + half, e_center + half)


def wfs_bbox_param(bbox: tuple[float, float, float, float]) -> str:
    """Format a (n_min, e_min, n_max, e_max) EPSG:2180 bbox for a WFS 2.0.0
    BBOX parameter. Axis order N,E is required for urn:ogc:def:crs:EPSG::2180."""
    n_min, e_min, n_max, e_max = bbox
    return f"{n_min},{e_min},{n_max},{e_max},urn:ogc:def:crs:EPSG::2180"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/tiles.py tests/test_tiles.py
git commit -m "feat: EPSG:2180 tile bbox utilities"
```

---

### Task 3: BDL WFS fetch with pagination + GeoParquet cache

**Files:**
- Create: `pipeline/bdl.py`
- Test: `tests/test_bdl.py`

**Interfaces:**
- Consumes: `wfs_bbox_param` from Task 2.
- Produces: `build_wfs_url(layer: str, bbox: tuple, start_index: int = 0, count: int = 1000, base_url: str = DEFAULT_WFS_URL) -> str`
- Produces: `fetch_bdl(layer: str, bbox: tuple, page_size: int = 1000, base_url: str = DEFAULT_WFS_URL, session: requests.Session | None = None) -> geopandas.GeoDataFrame`
- Produces: `save_bdl_tile(gdf: geopandas.GeoDataFrame, tile_id: str, cache_dir: pathlib.Path) -> pathlib.Path`
- Consumed by: Task 11 (`orchestrate.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_bdl.py`:
```python
import json
import geopandas as gpd
import responses

from pipeline.bdl import build_wfs_url, fetch_bdl, save_bdl_tile, DEFAULT_WFS_URL

BBOX = (486000.0, 380000.0, 496000.0, 390000.0)
LAYER = "BDL:RDLP_Katowice_wydzielenia"


def _feature(fid, adr_for):
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380100, 486100], [380200, 486100], [380200, 486200], [380100, 486200], [380100, 486100]]]},
        "properties": {
            "adr_for": adr_for, "area_type": "D-STAN", "site_type": "BMSW",
            "species_cd": "SO", "part_cd": 10, "spec_age": 60, "a_year": 2026,
        },
    }


def test_build_wfs_url_contains_bbox_and_paging_params():
    url = build_wfs_url(LAYER, BBOX, start_index=1000, count=500)
    assert url.startswith(DEFAULT_WFS_URL)
    assert "typeNames=BDL%3ARDLP_Katowice_wydzielenia" in url or "typeNames=BDL:RDLP_Katowice_wydzielenia" in url
    assert "startIndex=1000" in url
    assert "count=500" in url
    assert "urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180" in url or "urn:ogc:def:crs:EPSG::2180" in url


@responses.activate
def test_fetch_bdl_paginates_until_short_page():
    page1 = {"type": "FeatureCollection", "features": [_feature(1, "08-01-1-01-108"), _feature(2, "08-01-1-01-109")]}
    page2 = {"type": "FeatureCollection", "features": [_feature(3, "08-01-1-01-110")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=page1, status=200)
    responses.add(responses.GET, DEFAULT_WFS_URL, json=page2, status=200)

    gdf = fetch_bdl(LAYER, BBOX, page_size=2)

    assert len(gdf) == 3
    assert list(gdf["adr_for"]) == ["08-01-1-01-108", "08-01-1-01-109", "08-01-1-01-110"]
    assert len(responses.calls) == 2


def test_save_bdl_tile_writes_geoparquet(tmp_path):
    gdf = gpd.GeoDataFrame.from_features([_feature(1, "08-01-1-01-108")])
    gdf = gdf.set_crs("EPSG:2180")

    out_path = save_bdl_tile(gdf, "E380N486", tmp_path)

    assert out_path.exists()
    reloaded = gpd.read_parquet(out_path)
    assert len(reloaded) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bdl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.bdl'`

- [ ] **Step 3: Implement**

`pipeline/bdl.py`:
```python
import io
import pathlib

import geopandas as gpd
import requests

from pipeline.tiles import wfs_bbox_param

DEFAULT_WFS_URL = "https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows"


def build_wfs_url(layer: str, bbox: tuple, start_index: int = 0, count: int = 1000,
                   base_url: str = DEFAULT_WFS_URL) -> str:
    req = requests.Request(
        "GET",
        base_url,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "bbox": wfs_bbox_param(bbox),
            "count": count,
            "startIndex": start_index,
        },
    )
    return req.prepare().url


def fetch_bdl(layer: str, bbox: tuple, page_size: int = 1000,
               base_url: str = DEFAULT_WFS_URL,
               session: requests.Session | None = None) -> gpd.GeoDataFrame:
    """Fetch all wydzielenia intersecting bbox from BDL WFS, paginating with
    startIndex/count until a page returns fewer than page_size features."""
    session = session or requests.Session()
    pages = []
    start_index = 0
    while True:
        url = build_wfs_url(layer, bbox, start_index=start_index, count=page_size, base_url=base_url)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        gdf = gpd.read_file(io.BytesIO(resp.content))
        pages.append(gdf)
        if len(gdf) < page_size:
            break
        start_index += page_size
    result = gpd.GeoDataFrame(pd_concat(pages), crs=pages[0].crs if pages else "EPSG:2180")
    return result


def pd_concat(frames):
    import pandas as pd
    return pd.concat(frames, ignore_index=True)


def save_bdl_tile(gdf: gpd.GeoDataFrame, tile_id: str, cache_dir: pathlib.Path) -> pathlib.Path:
    cache_dir = pathlib.Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{tile_id}.parquet"
    gdf.to_parquet(out_path)
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bdl.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification against the real API (not part of pytest)**

Before relying on `BDL:RDLP_Katowice_wydzielenia`, confirm the exact layer name:

```bash
uv run python -c "
import requests
r = requests.get('https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows', params={
    'service': 'WFS', 'version': '2.0.0', 'request': 'GetCapabilities'
}, timeout=30)
print([l for l in r.text.split('<Name>') if 'Katowice' in l][:3])
"
```

Then run one real fetch for the Kieleczka tile and print the row count (spec §2.1 measured ~1904 features for a comparable tile):

```bash
uv run python -c "
from pipeline.tiles import tile_bbox_2180
from pipeline.bdl import fetch_bdl
bbox = tile_bbox_2180(50.526944, 18.605000, size_km=10.0)
gdf = fetch_bdl('BDL:RDLP_Katowice_wydzielenia', bbox)
print(len(gdf), gdf.columns.tolist())
"
```

If the layer name differs from `BDL:RDLP_Katowice_wydzielenia`, update the constant used in `notebooks/01_poc.py` (Task 11) accordingly.

- [ ] **Step 6: Commit**

```bash
git add pipeline/bdl.py tests/test_bdl.py
git commit -m "feat: BDL WFS paginated fetch and GeoParquet cache"
```

---

### Task 4: Species profile config

**Files:**
- Create: `profiles/boletus_edulis.yaml`

**Interfaces:**
- Consumed by: Task 5 (`habitat.load_profile`).

- [ ] **Step 1: Write the profile file**

`profiles/boletus_edulis.yaml` (values copied from spec §4.3; codes assumed ASCII as returned by the WFS — verify against a real `site_type`/`species_cd` value from Task 3's manual fetch and adjust keys if diacritics are actually used):

```yaml
name: "prawdziwki (grupa Boletus edulis)"
weights:
  host: 0.40
  site: 0.35
  age: 0.25

host_affinity:
  SO: 1.0
  SW: 1.0
  BK: 0.9
  DB: 0.8
  DB.S: 0.8
  DB.B: 0.8
  JD: 0.8
  BRZ: 0.7
  GB: 0.3
  MD: 0.3
  DG: 0.3
  LP: 0.3
  OS: 0.2
  TP: 0.2
  OL: 0.0
  JS: 0.0
  KL: 0.0
  WZ: 0.0
  AK: 0.0
unknown_host_affinity: 0.5     # "nieznana domieszka" default, spec §4.3
zero_affinity_mask_species: [OL, JS, KL, WZ, AK]   # hard mask threshold, spec §4.2 (see plan note re: "Tp" ambiguity)

# site_type -> [S_site, moisture_cls] (0=suche,1=swieze,2=wilgotne,3=bagienne)
site_scores:
  BMSW: [1.00, 1]
  BSW:  [0.85, 1]
  LMSW: [0.85, 1]
  BMW:  [0.65, 2]
  BW:   [0.65, 2]
  LMW:  [0.65, 2]
  LSW:  [0.60, 1]
  BS:   [0.45, 0]
  LW:   [0.40, 2]
  BMB:  [0.15, 3]
  BB:   [0.15, 3]
  LMB:  [0.15, 3]
  OL:   [0.0, 3]
  OLJ:  [0.0, 3]
  LL:   [0.0, 2]
unknown_site_score: 0.5
unknown_site_moisture_cls: 1

age_breakpoints:
  mask_below: 12
  segments:
    - {from: 12, to: 20, value_from: 0.3, value_to: 0.6}
    - {from: 20, to: 35, value_from: 0.6, value_to: 1.0}
    - {from: 35, to: 120, value_from: 1.0, value_to: 1.0}
  above_120: 0.9

fruiting:
  moisture_midpoint: 0.35
  moisture_slope: 0.10
  temp_optimum_c: 13.0
  temp_sigma_c: 4.0
  heat_penalty_tmean5_c: 17.5
  heat_penalty_p5_mm: 5.0
  heat_penalty_factor: 0.3
  frost_tmin3_hard_c: -2.0
  frost_tmin3_soft_c: 0.0
  frost_hard_factor: 0.2
  frost_soft_factor: 0.6
  dry_pct_threshold: 0.3
  wet_pct_threshold: 0.8
  dry_multiplier_by_moisture: [0.6, 0.9, 1.2, 1.0]
  wet_multiplier_by_moisture: [1.15, 1.0, 0.85, 0.7]

fruiting_classes:
  - {max: 0.20, label: "Słabe warunki"}
  - {max: 0.45, label: "Umiarkowane"}
  - {max: 0.70, label: "Dobre"}
  - {max: 1.01, label: "Bardzo dobre"}
```

- [ ] **Step 2: Commit**

```bash
git add profiles/boletus_edulis.yaml
git commit -m "feat: boletus_edulis MVP scoring profile"
```

---

### Task 5: Habitat scoring (S_host, S_site, S_age, H, MASK)

**Files:**
- Create: `pipeline/habitat.py`
- Test: `tests/test_habitat.py`

**Interfaces:**
- Consumes: `profiles/boletus_edulis.yaml` (Task 4).
- Produces: `load_profile(path) -> dict`
- Produces: `score_host(species_cd: str, part_cd: int, profile: dict) -> float`
- Produces: `score_site(site_type: str, profile: dict) -> tuple[float, int]`
- Produces: `score_age(age: int | None, profile: dict) -> float | None` (`None` = masked)
- Produces: `compute_habitat(row: dict, profile: dict) -> float | None`
- Produces: `passes_mask(row: dict, profile: dict) -> bool`
- Consumed by: Task 9 (`scoring.compute_ranking`), Task 11 (`orchestrate.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_habitat.py`:
```python
import math
import pytest

from pipeline.habitat import (
    load_profile, score_host, score_site, score_age, compute_habitat, passes_mask,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_host_pure_stand_matches_affinity():
    assert score_host("SO", 10, PROFILE) == pytest.approx(1.0)


def test_score_host_mixes_with_unknown_admixture_default():
    # DB affinity 0.8, share=0.5 -> 0.5*0.8 + 0.5*0.5
    assert score_host("DB", 5, PROFILE) == pytest.approx(0.5 * 0.8 + 0.5 * 0.5)


def test_score_site_known_codes():
    assert score_site("BMSW", PROFILE) == (pytest.approx(1.00), 1)
    assert score_site("BS", PROFILE) == (pytest.approx(0.45), 0)


def test_score_site_unknown_code_falls_back():
    assert score_site("XYZ", PROFILE) == (pytest.approx(0.5), 1)


def test_score_age_masks_young_stands():
    assert score_age(5, PROFILE) is None


def test_score_age_interpolates_first_segment():
    # 12-20: 0.3 -> 0.6
    assert score_age(15, PROFILE) == pytest.approx(0.3 + (15 - 12) / (20 - 12) * (0.6 - 0.3))


def test_score_age_plateau_and_old_growth():
    assert score_age(60, PROFILE) == pytest.approx(1.0)
    assert score_age(150, PROFILE) == pytest.approx(0.9)


def test_compute_habitat_combines_weighted_geometric_mean():
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW", "spec_age": 60}
    assert compute_habitat(row, PROFILE) == pytest.approx(1.0)

    row2 = {"species_cd": "DB", "part_cd": 10, "site_type": "LSW", "spec_age": 27}
    s_host = score_host("DB", 10, PROFILE)
    s_site, _ = score_site("LSW", PROFILE)
    s_age = score_age(27, PROFILE)
    expected = s_host ** 0.40 * s_site ** 0.35 * s_age ** 0.25
    assert compute_habitat(row2, PROFILE) == pytest.approx(expected)


def test_compute_habitat_none_when_masked_by_age():
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW", "spec_age": 5}
    assert compute_habitat(row, PROFILE) is None


def test_passes_mask_rejects_zero_affinity_dominant_species():
    row = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "OL", "part_cd": 9}
    assert passes_mask(row, PROFILE) is False


def test_passes_mask_accepts_normal_stand():
    row = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "SO", "part_cd": 10}
    assert passes_mask(row, PROFILE) is True


def test_passes_mask_rejects_non_stand_area_type():
    row = {"area_type": "ZRAB", "spec_age": 60, "species_cd": "SO", "part_cd": 10}
    assert passes_mask(row, PROFILE) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_habitat.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.habitat'`

- [ ] **Step 3: Implement**

`pipeline/habitat.py`:
```python
import yaml


def load_profile(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def score_host(species_cd: str, part_cd: int, profile: dict) -> float:
    affinity = profile["host_affinity"].get(species_cd, profile["unknown_host_affinity"])
    share = (part_cd or 0) / 10.0
    return share * affinity + (1 - share) * profile["unknown_host_affinity"]


def score_site(site_type: str, profile: dict) -> tuple[float, int]:
    entry = profile["site_scores"].get(site_type)
    if entry is None:
        return profile["unknown_site_score"], profile["unknown_site_moisture_cls"]
    value, moisture_cls = entry
    return float(value), int(moisture_cls)


def score_age(age: int | None, profile: dict) -> float | None:
    cfg = profile["age_breakpoints"]
    if age is None or age < cfg["mask_below"]:
        return None
    for seg in cfg["segments"]:
        if seg["from"] <= age < seg["to"]:
            span = seg["to"] - seg["from"]
            frac = (age - seg["from"]) / span if span else 0.0
            return seg["value_from"] + frac * (seg["value_to"] - seg["value_from"])
    last = cfg["segments"][-1]
    if age >= last["to"] and age <= 120:
        return last["value_to"]
    return cfg["above_120"]


def compute_habitat(row: dict, profile: dict) -> float | None:
    weights = profile["weights"]
    s_host = score_host(row["species_cd"], row.get("part_cd", 10), profile)
    s_site, _moisture_cls = score_site(row["site_type"], profile)
    s_age = score_age(row.get("spec_age"), profile)
    if s_age is None:
        return None
    return (s_host ** weights["host"]) * (s_site ** weights["site"]) * (s_age ** weights["age"])


def passes_mask(row: dict, profile: dict) -> bool:
    if row.get("area_type") != "D-STAN":
        return False
    if row.get("spec_age") is None or row["spec_age"] < profile["age_breakpoints"]["mask_below"]:
        return False
    species = row.get("species_cd")
    if species in profile["zero_affinity_mask_species"] and (row.get("part_cd") or 0) >= 8:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_habitat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/habitat.py tests/test_habitat.py
git commit -m "feat: habitat scoring (S_host, S_site, S_age, H, MASK)"
```

---

### Task 6: Weather grid + injectable fetch + window features

**Files:**
- Create: `pipeline/weather.py`
- Test: `tests/test_weather.py`

**Interfaces:**
- Consumes: EPSG:2180 bbox tuple shape from Task 2.
- Produces: `make_grid(bbox_2180: tuple, spacing_m: float = 5000.0) -> list[tuple[float, float]]` (list of `(lat, lon)`)
- Produces: `fetch_weather_raw(points: list[tuple[float, float]], past_days: int = 92, call_api=None) -> pandas.DataFrame` with columns `[lat, lon, date, precipitation_mm, tmean_c, tmin_c, tmax_c, et0_mm, soil_moisture]`
- Produces: `compute_weather_features(daily_df: pandas.DataFrame) -> pandas.DataFrame` with one row per `(lat, lon)` = latest day, columns `[lat, lon, date, p1, p3, p7, p14, p21, p30, p26w, cwb26, tmean5, tmean20, tmin3, days_since_p10, dry_spell_days]`
- Consumed by: Task 7 (climatology), Task 8 (F scoring), Task 11 (orchestrate).

- [ ] **Step 1: Write the failing tests**

`tests/test_weather.py`:
```python
import pandas as pd
import pytest

from pipeline.weather import make_grid, fetch_weather_raw, compute_weather_features


def test_make_grid_covers_bbox_with_points_in_lat_lon():
    bbox = (486000.0, 380000.0, 496000.0, 390000.0)  # 10x10 km
    grid = make_grid(bbox, spacing_m=5000.0)
    assert len(grid) >= 4  # at least a 2x2 grid over 10km with 5km spacing
    for lat, lon in grid:
        assert 40.0 < lat < 60.0
        assert 10.0 < lon < 25.0


def test_fetch_weather_raw_uses_injected_call_api():
    calls = []

    def fake_call_api(lat, lon, past_days):
        calls.append((lat, lon, past_days))
        dates = pd.date_range("2026-06-25", periods=3, freq="D")
        return {
            "date": dates,
            "precipitation_mm": [1.0, 2.0, 3.0],
            "tmean_c": [12.0, 13.0, 14.0],
            "tmin_c": [8.0, 9.0, 10.0],
            "tmax_c": [16.0, 17.0, 18.0],
            "et0_mm": [1.5, 1.6, 1.7],
            "soil_moisture": [0.3, 0.31, 0.32],
        }

    df = fetch_weather_raw([(50.5, 18.6), (50.55, 18.65)], past_days=3, call_api=fake_call_api)

    assert len(calls) == 2
    assert len(df) == 6
    assert set(df.columns) >= {"lat", "lon", "date", "precipitation_mm", "tmean_c", "tmin_c", "tmax_c", "et0_mm", "soil_moisture"}


def _synthetic_daily_df():
    dates = pd.date_range("2026-05-01", periods=30, freq="D")
    return pd.DataFrame({
        "lat": [50.5] * 30,
        "lon": [18.6] * 30,
        "date": dates,
        "precipitation_mm": [1.0] * 30,
        "tmean_c": [13.0] * 30,
        "tmin_c": [5.0] * 30,
        "tmax_c": [20.0] * 30,
        "et0_mm": [1.0] * 30,
        "soil_moisture": [0.4] * 30,
    })


def test_compute_weather_features_windows():
    feat = compute_weather_features(_synthetic_daily_df())
    row = feat.iloc[0]
    assert row["p7"] == pytest.approx(7.0)
    assert row["p14"] == pytest.approx(14.0)
    assert row["p30"] == pytest.approx(30.0)
    assert row["tmean20"] == pytest.approx(13.0)
    assert row["tmin3"] == pytest.approx(5.0)
    assert row["days_since_p10"] >= 29  # no day ever reached 10mm
    assert row["dry_spell_days"] == 0  # 1mm/day never below 1mm threshold
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_weather.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.weather'`

- [ ] **Step 3: Implement**

`pipeline/weather.py`:
```python
import math

import numpy as np
import pandas as pd
from pyproj import Transformer

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def make_grid(bbox_2180: tuple, spacing_m: float = 5000.0) -> list[tuple[float, float]]:
    n_min, e_min, n_max, e_max = bbox_2180
    n_steps = max(1, int(math.ceil((n_max - n_min) / spacing_m)))
    e_steps = max(1, int(math.ceil((e_max - e_min) / spacing_m)))
    points = []
    for i in range(n_steps + 1):
        n = min(n_min + i * spacing_m, n_max)
        for j in range(e_steps + 1):
            e = min(e_min + j * spacing_m, e_max)
            lon, lat = _TO_4326.transform(e, n)
            points.append((lat, lon))
    return points


def _default_open_meteo_call(lat: float, lon: float, past_days: int) -> dict:
    """Thin IO boundary around the real Open-Meteo archive+forecast API.
    Not covered by unit tests (network); exercised manually, see Task 6 Step 5."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    responses = client.weather_api(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": ["precipitation_sum", "temperature_2m_mean", "temperature_2m_min",
                       "temperature_2m_max", "et0_fao_evapotranspiration"],
            "hourly": ["soil_moisture_9_to_27cm"],
            "past_days": past_days,
            "forecast_days": 1,
            "timezone": "Europe/Warsaw",
        },
    )
    response = responses[0]
    daily = response.Daily()
    dates = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left",
    )
    hourly = response.Hourly()
    soil = hourly.Variables(0).ValuesAsNumpy()
    soil_daily = pd.Series(soil).groupby(np.arange(len(soil)) // 24).mean().to_numpy()
    return {
        "date": dates,
        "precipitation_mm": daily.Variables(0).ValuesAsNumpy(),
        "tmean_c": daily.Variables(1).ValuesAsNumpy(),
        "tmin_c": daily.Variables(2).ValuesAsNumpy(),
        "tmax_c": daily.Variables(3).ValuesAsNumpy(),
        "et0_mm": daily.Variables(4).ValuesAsNumpy(),
        "soil_moisture": soil_daily[: len(dates)],
    }


def fetch_weather_raw(points: list[tuple[float, float]], past_days: int = 92, call_api=None) -> pd.DataFrame:
    call_api = call_api or _default_open_meteo_call
    frames = []
    for lat, lon in points:
        data = call_api(lat, lon, past_days)
        df = pd.DataFrame(data)
        df["lat"] = lat
        df["lon"] = lon
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _rolling_sum(series: pd.Series, window: int) -> float:
    return series.iloc[-window:].sum()


def _exp_weighted_sum(series: pd.Series, window: int, half_life_days: float = 10.0) -> float:
    tail = series.iloc[-window:]
    n = len(tail)
    ages = np.arange(n - 1, -1, -1)
    weights = 0.5 ** (ages / half_life_days)
    return float((tail.to_numpy() * weights).sum())


def compute_weather_features(daily_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (lat, lon), group in daily_df.sort_values("date").groupby(["lat", "lon"]):
        p = group["precipitation_mm"]
        et0 = group["et0_mm"]
        tmean = group["tmean_c"]
        tmin = group["tmin_c"]
        p26w = _exp_weighted_sum(p, window=min(26, len(p)))
        et026w = _exp_weighted_sum(et0, window=min(26, len(et0)))
        at_or_above_10 = group[p >= 10.0]
        if len(at_or_above_10):
            last_p10_pos = group.index.get_indexer(at_or_above_10.index).max()
            days_since_p10 = (len(group) - 1) - last_p10_pos
        else:
            days_since_p10 = len(group)
        dry_mask = (p < 1.0).to_numpy()
        dry_spell = 0
        for is_dry in dry_mask[::-1]:
            if not is_dry:
                break
            dry_spell += 1
        rows.append({
            "lat": lat, "lon": lon, "date": group["date"].iloc[-1],
            "p1": _rolling_sum(p, 1), "p3": _rolling_sum(p, 3), "p7": _rolling_sum(p, 7),
            "p14": _rolling_sum(p, 14), "p21": _rolling_sum(p, 21), "p30": _rolling_sum(p, 30),
            "p26w": p26w, "cwb26": p26w - et026w,
            "tmean5": tmean.iloc[-5:].mean(), "tmean20": tmean.iloc[-20:].mean(),
            "tmin3": tmin.iloc[-3:].min(),
            "days_since_p10": days_since_p10, "dry_spell_days": dry_spell,
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_weather.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification against the real API (not part of pytest)**

```bash
uv run python -c "
from pipeline.weather import fetch_weather_raw
df = fetch_weather_raw([(50.526944, 18.605000)], past_days=30)
print(df.tail())
"
```
Confirm no exceptions and plausible September values (precip mm, temps ~10-20C).

- [ ] **Step 6: Commit**

```bash
git add pipeline/weather.py tests/test_weather.py
git commit -m "feat: weather grid, injectable Open-Meteo fetch, window features"
```

---

### Task 7: Climatology percentiles

**Files:**
- Modify: `pipeline/weather.py` (append climatology functions)
- Modify: `tests/test_weather.py` (append tests)

**Interfaces:**
- Consumes: `make_grid` points (Task 6).
- Produces: `fetch_climatology_raw(points: list[tuple[float, float]], start_year: int = 1991, end_year: int = 2020, call_api=None) -> pandas.DataFrame` columns `[lat, lon, date, cwb26, soil_moisture]` (one row per historical day where a 26-day window could be computed)
- Produces: `climatology_window_values(clim_df: pandas.DataFrame, lat: float, lon: float, day_of_year: int, column: str, window_days: int = 15) -> numpy.ndarray`
- Produces: `percentile_rank(value: float, historical_values: numpy.ndarray) -> float` (0..1)
- Consumed by: Task 8 (`scoring.score_moisture` inputs), Task 11 (orchestrate).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_weather.py`:
```python
import numpy as np
from pipeline.weather import climatology_window_values, percentile_rank


def test_percentile_rank_of_median_like_value():
    historical = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert percentile_rank(30.0, historical) == pytest.approx(0.5, abs=0.15)
    assert percentile_rank(5.0, historical) == pytest.approx(0.0, abs=0.05)
    assert percentile_rank(55.0, historical) == pytest.approx(1.0, abs=0.05)


def test_climatology_window_values_filters_by_point_and_doy_window():
    clim_df = pd.DataFrame({
        "lat": [50.5, 50.5, 50.5, 50.5, 60.0],
        "lon": [18.6, 18.6, 18.6, 18.6, 18.6],
        "date": pd.to_datetime(["2000-08-10", "2000-08-20", "2000-09-15", "2005-08-12", "2000-08-11"]),
        "cwb26": [1.0, 2.0, 99.0, 3.0, 100.0],
    })
    # target day_of_year ~ Aug 15 (227), window 15 days -> Aug 1..Aug 30 roughly
    from datetime import date
    doy = date(2026, 8, 15).timetuple().tm_yday
    values = climatology_window_values(clim_df, lat=50.5, lon=18.6, day_of_year=doy, column="cwb26", window_days=15)
    assert 1.0 in values and 2.0 in values and 3.0 in values
    assert 99.0 not in values   # outside +/-15 day window (Sep 15)
    assert 100.0 not in values  # wrong point (lat 60.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_weather.py -v -k climatology or percentile`
Expected: FAIL with `ImportError: cannot import name 'climatology_window_values'`

- [ ] **Step 3: Implement**

Append to `pipeline/weather.py`:
```python
from scipy import stats


def fetch_climatology_raw(points: list[tuple[float, float]], start_year: int = 1991,
                            end_year: int = 2020, call_api=None) -> pd.DataFrame:
    """Same shape/DI pattern as fetch_weather_raw but against the ERA5-Land
    archive for a fixed historical period. Real network call isolated in
    call_api for testability; default implementation calls Open-Meteo's
    historical-weather-api and then reuses compute_weather_features'
    windowing helpers day by day (implemented alongside the manual
    verification step, not unit tested)."""
    call_api = call_api or (lambda lat, lon, sy, ey: _default_climatology_call(lat, lon, sy, ey))
    frames = []
    for lat, lon in points:
        data = call_api(lat, lon, start_year, end_year)
        df = pd.DataFrame(data)
        df["lat"] = lat
        df["lon"] = lon
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _default_climatology_call(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    """Thin IO boundary; not unit tested, see Task 7 Step 5 manual verification."""
    raise NotImplementedError(
        "Wire to Open-Meteo historical-weather-api, compute daily cwb26/soil_moisture "
        "via the same window helpers as compute_weather_features, at implementation time."
    )


def climatology_window_values(clim_df: pd.DataFrame, lat: float, lon: float, day_of_year: int,
                                column: str, window_days: int = 15) -> np.ndarray:
    at_point = clim_df[(clim_df["lat"] == lat) & (clim_df["lon"] == lon)].copy()
    doy = at_point["date"].dt.dayofyear
    diff = (doy - day_of_year).abs()
    wrapped_diff = np.minimum(diff, 365 - diff)
    mask = wrapped_diff <= window_days
    return at_point.loc[mask, column].to_numpy()


def percentile_rank(value: float, historical_values: np.ndarray) -> float:
    if len(historical_values) == 0:
        return 0.5
    return float(stats.percentileofscore(historical_values, value, kind="mean") / 100.0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_weather.py -v`
Expected: PASS (note: `fetch_climatology_raw`'s default path is intentionally `NotImplementedError` until Step 5 — tests only exercise `climatology_window_values`/`percentile_rank`, which don't touch the default call path)

- [ ] **Step 5: Wire the real climatology call and verify manually**

Replace `_default_climatology_call`'s body with a real call to Open-Meteo's `archive-api.open-meteo.com/v1/archive` for `start_year`-`end_year`, reusing `compute_weather_features`'s rolling-window math per historical day (loop the `cwb26`/`soil_moisture` computation across the full 30-year series, not just the last day). Run:

```bash
uv run python -c "
from pipeline.weather import fetch_climatology_raw
df = fetch_climatology_raw([(50.526944, 18.605000)], start_year=1991, end_year=2020)
print(len(df), df.head())
"
```
Expected: several thousand rows (≈30 years × 365 days), no exceptions.

- [ ] **Step 6: Commit**

```bash
git add pipeline/weather.py tests/test_weather.py
git commit -m "feat: climatology percentile windowing"
```

---

### Task 8: Fruiting F and F_loc scoring

**Files:**
- Create: `pipeline/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `boletus_edulis.yaml` `fruiting` section (Task 4).
- Produces: `score_moisture(pct_cwb26: float, pct_sm: float, profile: dict) -> float`
- Produces: `score_temperature(tmean20: float, tmean5: float, p5: float, profile: dict) -> float`
- Produces: `score_frost(tmin3: float, profile: dict) -> float`
- Produces: `compute_fruiting(m: float, t: float, k_frost: float, g_season: float = 1.0) -> float`
- Produces: `apply_moisture_modulation(f: float, moisture_cls: int, pct_m: float, profile: dict) -> float`
- Produces: `classify_fruiting(f: float, profile: dict) -> str`
- Consumed by: Task 9, Task 11.

- [ ] **Step 1: Write the failing tests**

`tests/test_scoring.py`:
```python
import math
import pytest

from pipeline.habitat import load_profile
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, classify_fruiting,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_moisture_at_midpoint_is_half():
    assert score_moisture(0.35, 0.35, PROFILE) == pytest.approx(0.5)


def test_score_moisture_above_midpoint_is_higher():
    assert score_moisture(0.6, 0.6, PROFILE) == pytest.approx(1 / (1 + math.exp(-2.5)))


def test_score_temperature_at_optimum_no_penalty():
    assert score_temperature(tmean20=13.0, tmean5=13.0, p5=10.0, profile=PROFILE) == pytest.approx(1.0)


def test_score_temperature_heat_penalty_applies():
    base = math.exp(-(20.0 - 13.0) ** 2 / 32)
    assert score_temperature(tmean20=20.0, tmean5=20.0, p5=2.0, profile=PROFILE) == pytest.approx(base * 0.3)


def test_score_temperature_no_heat_penalty_when_wet():
    base = math.exp(-(20.0 - 13.0) ** 2 / 32)
    assert score_temperature(tmean20=20.0, tmean5=20.0, p5=10.0, profile=PROFILE) == pytest.approx(base)


def test_score_frost_thresholds():
    assert score_frost(-3.0, PROFILE) == pytest.approx(0.2)
    assert score_frost(-1.0, PROFILE) == pytest.approx(0.6)
    assert score_frost(2.0, PROFILE) == pytest.approx(1.0)


def test_compute_fruiting_combines_m_t_k():
    f = compute_fruiting(m=0.5, t=1.0, k_frost=1.0, g_season=1.0)
    assert f == pytest.approx(0.5 ** 0.6)


def test_apply_moisture_modulation_dry_branch():
    # moisture_cls=1 (swieze), dry multiplier table index 1 -> 0.9
    result = apply_moisture_modulation(f=0.5, moisture_cls=1, pct_m=0.2, profile=PROFILE)
    assert result == pytest.approx(0.5 * 0.9)


def test_apply_moisture_modulation_wet_branch():
    # moisture_cls=2 (wilgotne), wet multiplier table index 2 -> 0.85
    result = apply_moisture_modulation(f=0.5, moisture_cls=2, pct_m=0.9, profile=PROFILE)
    assert result == pytest.approx(0.5 * 0.85)


def test_apply_moisture_modulation_clips_to_one():
    result = apply_moisture_modulation(f=0.9, moisture_cls=0, pct_m=0.9, profile=PROFILE)
    assert result == pytest.approx(1.0)


def test_apply_moisture_modulation_neutral_branch_unchanged():
    result = apply_moisture_modulation(f=0.5, moisture_cls=1, pct_m=0.5, profile=PROFILE)
    assert result == pytest.approx(0.5)


@pytest.mark.parametrize("f,expected", [
    (0.1, "Słabe warunki"),
    (0.2, "Umiarkowane"),
    (0.44, "Umiarkowane"),
    (0.45, "Dobre"),
    (0.69, "Dobre"),
    (0.70, "Bardzo dobre"),
])
def test_classify_fruiting_boundaries(f, expected):
    assert classify_fruiting(f, PROFILE) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.scoring'`

- [ ] **Step 3: Implement**

`pipeline/scoring.py`:
```python
import math


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_moisture(pct_cwb26: float, pct_sm: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    mean_pct = (pct_cwb26 + pct_sm) / 2.0
    return _logistic((mean_pct - cfg["moisture_midpoint"]) / cfg["moisture_slope"])


def score_temperature(tmean20: float, tmean5: float, p5: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    base = math.exp(-((tmean20 - cfg["temp_optimum_c"]) ** 2) / (2 * cfg["temp_sigma_c"] ** 2))
    if tmean5 > cfg["heat_penalty_tmean5_c"] and p5 < cfg["heat_penalty_p5_mm"]:
        base *= cfg["heat_penalty_factor"]
    return base


def score_frost(tmin3: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    if tmin3 < cfg["frost_tmin3_hard_c"]:
        return cfg["frost_hard_factor"]
    if tmin3 < cfg["frost_tmin3_soft_c"]:
        return cfg["frost_soft_factor"]
    return 1.0


def compute_fruiting(m: float, t: float, k_frost: float, g_season: float = 1.0) -> float:
    return g_season * (m ** 0.6) * (t ** 0.4) * k_frost


def apply_moisture_modulation(f: float, moisture_cls: int, pct_m: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    if pct_m < cfg["dry_pct_threshold"]:
        multiplier = cfg["dry_multiplier_by_moisture"][moisture_cls]
    elif pct_m > cfg["wet_pct_threshold"]:
        multiplier = cfg["wet_multiplier_by_moisture"][moisture_cls]
    else:
        multiplier = 1.0
    return max(0.0, min(1.0, f * multiplier))


def classify_fruiting(f: float, profile: dict) -> str:
    for cls in profile["fruiting_classes"]:
        if f < cls["max"]:
            return cls["label"]
    return profile["fruiting_classes"][-1]["label"]
```

Note: with `fruiting_classes` maxima `[0.20, 0.45, 0.70, 1.01]`, `f < max` correctly returns "Umiarkowane" for `f=0.2` (fails `0.2<0.20`, matches `0.2<0.45`) and "Dobre" for `f=0.45` — verify this matches the parametrized test above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/scoring.py tests/test_scoring.py
git commit -m "feat: fruiting F/F_loc scoring (moisture, temperature, frost)"
```

---

### Task 9: Ranking R

**Files:**
- Modify: `pipeline/scoring.py` (append)
- Modify: `tests/test_scoring.py` (append)

**Interfaces:**
- Consumes: `passes_mask` result (Task 5) as `mask: bool`, `H` (Task 5), `F_loc` (Task 8).
- Produces: `compute_ranking(mask: bool, h: float | None, f_loc: float | None) -> float`
- Consumed by: Task 11.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scoring.py`:
```python
from pipeline.scoring import compute_ranking


def test_compute_ranking_multiplies_when_passing_mask():
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5) == pytest.approx(100 * 0.8 * 0.5)


def test_compute_ranking_zero_when_masked():
    assert compute_ranking(mask=False, h=0.9, f_loc=0.9) == pytest.approx(0.0)


def test_compute_ranking_zero_when_habitat_none():
    assert compute_ranking(mask=True, h=None, f_loc=0.9) == pytest.approx(0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v -k ranking`
Expected: FAIL with `ImportError: cannot import name 'compute_ranking'`

- [ ] **Step 3: Implement**

Append to `pipeline/scoring.py`:
```python
def compute_ranking(mask: bool, h: float | None, f_loc: float | None) -> float:
    if not mask or h is None or f_loc is None:
        return 0.0
    return 100.0 * h * f_loc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/scoring.py tests/test_scoring.py
git commit -m "feat: ranking R = 100*MASK*H*F_loc"
```

---

### Task 10: Known-point validation ranking

**Files:**
- Create: `pipeline/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: a scored `geopandas.GeoDataFrame` with columns `[stand_id, R, geometry]` (produced in Task 11).
- Produces: `rank_known_points(stands: geopandas.GeoDataFrame, known_points: list[dict]) -> pandas.DataFrame` where each `known_points` item is `{"name": str, "label": "good"|"bad", "lat": float, "lon": float}`; output columns `[name, label, stand_id, R, rank_pct]`, `rank_pct` = percentage of stands with strictly lower `R`.
- Produces: `load_known_points(path: str) -> list[dict]` (YAML loader)
- Consumed by: Task 12 (manual validation run).

- [ ] **Step 1: Write the failing tests**

`tests/test_validate.py`:
```python
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.validate import rank_known_points, load_known_points


def _synthetic_stands():
    # five 1x1 degree squares side by side, R increasing left to right
    polys = [box(i, 50.0, i + 1, 51.0) for i in range(5)]
    return gpd.GeoDataFrame({
        "stand_id": ["s1", "s2", "s3", "s4", "s5"],
        "R": [10.0, 20.0, 30.0, 40.0, 50.0],
        "geometry": polys,
    }, crs="EPSG:4326")


def test_rank_known_points_matches_containing_stand_and_percentile():
    stands = _synthetic_stands()
    known = [
        {"name": "Znane dobre miejsce", "label": "good", "lat": 50.5, "lon": 3.5},  # inside s4, R=40
        {"name": "Znane puste miejsce", "label": "bad", "lat": 50.5, "lon": 0.5},   # inside s1, R=10
    ]

    result = rank_known_points(stands, known)

    good = result[result["name"] == "Znane dobre miejsce"].iloc[0]
    assert good["stand_id"] == "s4"
    assert good["R"] == pytest.approx(40.0)
    assert good["rank_pct"] == pytest.approx(60.0)  # 3 of 5 stands have R<40

    bad = result[result["name"] == "Znane puste miejsce"].iloc[0]
    assert bad["stand_id"] == "s1"
    assert bad["rank_pct"] == pytest.approx(0.0)


def test_load_known_points_reads_yaml(tmp_path):
    p = tmp_path / "known_points.yaml"
    p.write_text(
        "- name: Test spot\n  label: good\n  lat: 50.5\n  lon: 18.6\n",
        encoding="utf-8",
    )
    points = load_known_points(str(p))
    assert points == [{"name": "Test spot", "label": "good", "lat": 50.5, "lon": 18.6}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.validate'`

- [ ] **Step 3: Implement**

`pipeline/validate.py`:
```python
import geopandas as gpd
import pandas as pd
import yaml


def rank_known_points(stands: gpd.GeoDataFrame, known_points: list[dict]) -> pd.DataFrame:
    pts = gpd.GeoDataFrame(
        known_points,
        geometry=gpd.points_from_xy([p["lon"] for p in known_points], [p["lat"] for p in known_points]),
        crs="EPSG:4326",
    ).to_crs(stands.crs)

    joined = gpd.sjoin_nearest(pts, stands[["stand_id", "R", "geometry"]], how="left")

    r_values = stands["R"].to_numpy()
    joined["rank_pct"] = joined["R"].apply(lambda r: float((r_values < r).mean() * 100.0))

    return joined[["name", "label", "stand_id", "R", "rank_pct"]].reset_index(drop=True)


def load_known_points(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/validate.py tests/test_validate.py
git commit -m "feat: rank known mushroom spots against scored stands"
```

---

### Task 11: Orchestration + PoC map

**Files:**
- Create: `pipeline/orchestrate.py`
- Test: `tests/test_orchestrate.py`
- Create: `notebooks/01_poc.py`

**Interfaces:**
- Consumes: `fetch_bdl` (Task 3), `load_profile`/`compute_habitat`/`passes_mask` (Task 5), `make_grid`/`fetch_weather_raw`/`compute_weather_features`/`fetch_climatology_raw`/`climatology_window_values`/`percentile_rank` (Tasks 6-7), `score_moisture`/`score_temperature`/`score_frost`/`compute_fruiting`/`apply_moisture_modulation`/`compute_ranking` (Tasks 8-9).
- Produces: `run_poc(layer: str, bbox_2180: tuple, profile: dict, bdl_fetcher, weather_fetcher, climatology_fetcher, grid_spacing_m: float = 5000.0, past_days: int = 92) -> geopandas.GeoDataFrame` with columns `[stand_id, ..., H, F, F_loc, mask, R, geometry]`.
- Consumed by: `notebooks/01_poc.py` (real fetchers), Task 12 (validation run).

- [ ] **Step 1: Write the failing test**

`tests/test_orchestrate.py`:
```python
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX = (486000.0, 380000.0, 496000.0, 390000.0)


def fake_bdl_fetcher(layer, bbox):
    return gpd.GeoDataFrame({
        "adr_for": ["A-1", "A-2"],
        "a_year": [2026, 2026],
        "area_type": ["D-STAN", "D-STAN"],
        "site_type": ["BMSW", "BS"],
        "species_cd": ["SO", "SO"],
        "part_cd": [10, 10],
        "spec_age": [60, 60],
        "geometry": [box(380100, 486100, 380200, 486200), box(380300, 486300, 380400, 486400)],
    }, crs="EPSG:2180")


def fake_weather_fetcher(points, past_days):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2026-08-01", periods=30, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": 2.0,
                         "tmean_c": 13.0, "tmin_c": 6.0, "tmax_c": 18.0,
                         "et0_mm": 1.0, "soil_moisture": 0.4})
    return pd.DataFrame(rows)


def fake_climatology_fetcher(points, start_year, end_year):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2000-01-01", periods=60, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": 30.0, "soil_moisture": 0.4})
    return pd.DataFrame(rows)


def test_run_poc_produces_scored_geodataframe_with_expected_columns():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )

    assert len(result) == 2
    for col in ["stand_id", "H", "F", "F_loc", "mask", "R"]:
        assert col in result.columns
    assert result["stand_id"].tolist() == ["A-1@2026", "A-2@2026"]
    # BS site_type -> S_site=0.45 lower than BMSW's 1.0, so row 2's H should be lower
    assert result.loc[result["stand_id"] == "A-2@2026", "H"].iloc[0] < result.loc[result["stand_id"] == "A-1@2026", "H"].iloc[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.orchestrate'`

- [ ] **Step 3: Implement**

`pipeline/orchestrate.py`:
```python
from datetime import date

import geopandas as gpd
import pandas as pd

from pipeline.habitat import compute_habitat, passes_mask, score_site
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, compute_ranking,
)
from pipeline.weather import (
    make_grid, compute_weather_features, climatology_window_values, percentile_rank,
)


def _nearest_weather_row(centroid, weather_feat_gdf):
    idx = weather_feat_gdf.geometry.distance(centroid).idxmin()
    return weather_feat_gdf.loc[idx]


def run_poc(layer: str, bbox_2180: tuple, profile: dict,
             bdl_fetcher, weather_fetcher, climatology_fetcher,
             grid_spacing_m: float = 5000.0, past_days: int = 92) -> gpd.GeoDataFrame:
    stands = bdl_fetcher(layer, bbox_2180)
    stands["stand_id"] = stands["adr_for"] + "@" + stands["a_year"].astype(str)

    grid_points = make_grid(bbox_2180, spacing_m=grid_spacing_m)
    weather_daily = weather_fetcher(grid_points, past_days)
    weather_feat = compute_weather_features(weather_daily)
    # compute_weather_features (Task 6) doesn't carry today's soil_moisture
    # through to its output row (it's a windowed-features table, not a daily
    # snapshot) — pull the latest day's soil_moisture per point straight from
    # the raw daily fetch and merge it in, so pct_sm below compares a real
    # reading against climatology instead of a hardcoded placeholder.
    latest_sm = (
        weather_daily.sort_values("date")
        .groupby(["lat", "lon"], as_index=False)
        .last()[["lat", "lon", "soil_moisture"]]
    )
    weather_feat = weather_feat.merge(latest_sm, on=["lat", "lon"], how="left")
    weather_feat_gdf = gpd.GeoDataFrame(
        weather_feat,
        geometry=gpd.points_from_xy(weather_feat["lon"], weather_feat["lat"]),
        crs="EPSG:4326",
    ).to_crs(stands.crs)

    clim_df = climatology_fetcher(grid_points, 1991, 2020)
    today_doy = date.today().timetuple().tm_yday

    h_values, f_values, f_loc_values, mask_values, r_values = [], [], [], [], []
    for _, row in stands.iterrows():
        mask = passes_mask(row, profile)
        h = compute_habitat(row, profile)
        _s_site, moisture_cls = score_site(row["site_type"], profile)

        centroid = row.geometry.centroid
        wrow = _nearest_weather_row(centroid, weather_feat_gdf)

        cwb26_hist = climatology_window_values(clim_df, wrow["lat"], wrow["lon"], today_doy, "cwb26")
        sm_hist = climatology_window_values(clim_df, wrow["lat"], wrow["lon"], today_doy, "soil_moisture")
        pct_cwb26 = percentile_rank(wrow["cwb26"], cwb26_hist)
        pct_sm = percentile_rank(wrow["soil_moisture"], sm_hist)

        m = score_moisture(pct_cwb26, pct_sm, profile)
        t = score_temperature(wrow["tmean20"], wrow["tmean5"], wrow["p1"], profile)
        k_frost = score_frost(wrow["tmin3"], profile)
        f = compute_fruiting(m, t, k_frost, g_season=1.0)
        pct_m = (pct_cwb26 + pct_sm) / 2.0
        f_loc = apply_moisture_modulation(f, moisture_cls, pct_m, profile)
        r = compute_ranking(mask, h, f_loc)

        mask_values.append(mask)
        h_values.append(h)
        f_values.append(f)
        f_loc_values.append(f_loc)
        r_values.append(r)

    stands["mask"] = mask_values
    stands["H"] = h_values
    stands["F"] = f_values
    stands["F_loc"] = f_loc_values
    stands["R"] = r_values
    return stands
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Write the real-fetcher orchestration script**

`notebooks/01_poc.py`:
```python
"""Faza 1 PoC: fetch BDL + Open-Meteo for the Kieleczka tile, score, map."""
import folium

from pipeline.bdl import fetch_bdl
from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import fetch_weather_raw, fetch_climatology_raw

LAT, LON = 50.526944, 18.605000
LAYER = "BDL:RDLP_Katowice_wydzielenia"  # confirmed in Task 3 Step 5 - update if GetCapabilities disagrees

profile = load_profile("profiles/boletus_edulis.yaml")
bbox = tile_bbox_2180(LAT, LON, size_km=10.0)

scored = run_poc(
    layer=LAYER,
    bbox_2180=bbox,
    profile=profile,
    bdl_fetcher=fetch_bdl,
    weather_fetcher=fetch_weather_raw,
    climatology_fetcher=fetch_climatology_raw,
)

scored_wgs84 = scored.to_crs("EPSG:4326")
m = folium.Map(location=[LAT, LON], zoom_start=12, tiles="OpenStreetMap")


def _color(r: float) -> str:
    if r >= 40:
        return "#1a9850"
    if r >= 20:
        return "#91cf60"
    if r >= 5:
        return "#fee08b"
    return "#999999"


folium.GeoJson(
    scored_wgs84,
    style_function=lambda feat: {
        "fillColor": _color(feat["properties"]["R"]),
        "color": "black", "weight": 0.5, "fillOpacity": 0.6,
    },
    tooltip=folium.GeoJsonTooltip(fields=["stand_id", "site_type", "species_cd", "spec_age", "H", "F_loc", "R"]),
).add_to(m)

import pathlib
out_dir = pathlib.Path("notebooks/output")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "poc_map.html"
m.save(str(out_path))
print(f"Saved {out_path}, {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing mask")
```

Run manually: `uv run python notebooks/01_poc.py`. Acceptance check for Faza 1 (spec §12, row 1): open `notebooks/output/poc_map.html` in a browser and confirm a colored map of wydzielenia renders over the Kieleczka tile.

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrate.py tests/test_orchestrate.py notebooks/01_poc.py
git commit -m "feat: wire BDL+weather+scoring into a PoC folium map"
```

---

### Task 12: Qualitative validation against known spots (spec §9 step 7)

**Files:**
- Create: `notebooks/known_points.example.yaml`
- Modify: `notebooks/01_poc.py` (append validation block)

**Interfaces:**
- Consumes: `rank_known_points`, `load_known_points` (Task 10); `scored` GeoDataFrame from Task 11.

- [ ] **Step 1: Create the template known-points file**

`notebooks/known_points.example.yaml`:
```yaml
# Copy to known_points.yaml (gitignored — personal foraging spots) and fill in
# 10-20 real coordinates: places you know have Boletus edulis ("good") and
# places you've checked and found none ("bad"). lat/lon in EPSG:4326.
- name: "Przykład - dobre miejsce"
  label: good
  lat: 50.5300
  lon: 18.6100
- name: "Przykład - puste miejsce"
  label: bad
  lat: 50.5200
  lon: 18.6000
```

Add `notebooks/known_points.yaml` to `.gitignore` (personal data, not committed):
- [ ] **Step 2: Update `.gitignore`**

Append to `.gitignore`:
```
notebooks/known_points.yaml
```

- [ ] **Step 3: Append the validation block to the orchestration script**

Append to `notebooks/01_poc.py`:
```python
import pathlib
from pipeline.validate import rank_known_points, load_known_points

known_points_path = pathlib.Path("notebooks/known_points.yaml")
if known_points_path.exists():
    known_points = load_known_points(str(known_points_path))
    validation = rank_known_points(scored, known_points)
    print(validation.to_string(index=False))
    good = validation[validation["label"] == "good"]
    if len(good) and good["rank_pct"].mean() < 70:
        print(
            "UWAGA: znane dobre miejsca średnio poniżej 70. percentyla - "
            "przejrzyj S_site/S_host w profiles/boletus_edulis.yaml przed Fazą 2 "
            "(spec sekcja 9, krok 7)."
        )
else:
    print(f"Brak {known_points_path} - skopiuj notebooks/known_points.example.yaml i uzupełnij 10-20 znanych miejsc.")
```

- [ ] **Step 4: Manual run — this is the Faza 1 acceptance criterion**

1. Copy `notebooks/known_points.example.yaml` to `notebooks/known_points.yaml`.
2. Fill in 10-20 real coordinates of places you know grow/don't grow *B. edulis*, within the Kieleczka tile.
3. Run `uv run python notebooks/01_poc.py`.
4. Read the printed `rank_pct` per known point. Per spec §12 row 1 acceptance criterion: known good spots should land in the upper part of the ranking. If they don't, revisit `S_site`/`S_host` in `profiles/boletus_edulis.yaml` (spec §9 step 7) before starting Faza 2.

- [ ] **Step 5: Commit**

```bash
git add notebooks/known_points.example.yaml notebooks/01_poc.py .gitignore
git commit -m "feat: qualitative validation against known foraging spots"
```

---

## Self-Review Notes

- **Spec coverage:** Tasks 1-11 implement spec §9 Faza 1 items 1-6 (repo scaffolding, `fetch_bdl`, site_type parser + affinity tables, `fetch_weather`, climatology, H/F/R computation + map). Task 12 implements item 7 (qualitative validation). Deliberately deferred to Faza 2 per spec §9 items 8-9: legal mask (GDOŚ/zakazy wstępu), OSM/Demand-based Presja P, PMTiles/MapLibre frontend, confidence/explanations UI.
- **Scope guard:** GBIF/G_season, NMT/TWI, Sentinel-2, radar, PostGIS are explicitly out of scope per spec §9 (Faza 3+) and not touched by this plan.
- **Open question carried into code:** `zero_affinity_mask_species` resolves the §4.2/§4.3 "Tp" discrepancy using §4.3's list — flagged in Global Constraints and in the YAML profile comment, not silently decided.
- **Open question carried into Task 3:** exact WFS layer name for RDLP Katowice must be confirmed via `GetCapabilities` before the first live fetch (inferred from a web search, not yet verified against the live service in this session).
