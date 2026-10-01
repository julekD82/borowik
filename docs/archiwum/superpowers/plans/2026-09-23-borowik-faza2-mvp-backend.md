# Borowik GIS — Faza 2 (MVP backend: maska prawna, presja, confidence, eksport) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Faza 1 scoring pipeline with the four Faza 2 MVP backend layers (spec §9 steps 8–11): a full legal mask (GDOŚ reserves/parks + BDL periodic access bans), a presja/dostępność (P) term from OSM data, deterministic confidence + log-contribution explanations, and a daily `scores_{date}.json` + stand-geometry export — all still pure-Python, no server/DB, no frontend.

**Architecture:** Same shape as Faza 1: small pure/testable modules wired together by one orchestration function, with real network calls isolated behind injectable `call_api`/`checker` parameters so composition logic is unit-tested with synthetic data and the real endpoints are exercised once, manually, per task. `pipeline/mvp.py::enrich_with_mvp_layers` takes the `stands` GeoDataFrame `run_poc` already produces (Faza 1) and adds the new columns on top; it does not replace or fork `run_poc`, so every Faza 1 test and the existing `notebooks/01_poc.py` keep working unmodified.

**Tech Stack:** Same as Faza 1 (Python 3.12, `uv`, GeoPandas + Shapely 2 + pyogrio + pyproj, `requests`, PyYAML, pytest, `responses`). No new dependencies — the GDOŚ fetch reuses `pipeline.bdl.fetch_bdl`'s generic WFS 2.0.0 GeoServer pagination, the BDL periodic-ban check and OSM Overpass fetch are plain `requests` JSON calls like `pipeline.weather`'s Open-Meteo boundary.

**Spec:** `docs/archiwum/projekt-borowik.md` (sections referenced below use its own `§` numbering).

## Global Constraints

- Repo root: `C:\Users\<uzytkownik>\Documents\Grzyby` (existing git repo from Faza 1).
- Python ≥3.12, dependency management via `uv`. No new entries needed in `pyproject.toml` for this plan.
- Storage format: GeoParquet / plain JSON files under `cache/` and `notebooks/output/`, no PostGIS/DB server (spec §6.1) — unchanged from Faza 1.
- Scope is exactly spec §9 steps 8–11 (Faza 2 MVP backend). Step 12 (Vite/TS/MapLibre frontend), step 13 (Task Scheduler/GitHub Actions cron), and step 14 (manual season logging) are **out of scope** for this plan.
- **GBIF / `G_season` stays out of scope**, same as the Faza 1 plan's own note: §9's step list (items 8–14) never mentions GBIF, it only appears bundled into §11's "6 źródeł MVP" overview. `compute_fruiting`'s `g_season` parameter keeps defaulting to `1.0`. Do not add GBIF fetching in this plan.
- **GDOŚ WFS** (verified live, 2026-09-23): `https://sdi.gdos.gov.pl/wfs`, WFS 2.0.0, GeoServer, layers `GDOS:Rezerwaty` and `GDOS:ParkiNarodowe`, default CRS `urn:ogc:def:crs:EPSG::2180` — same GeoServer stack, same N,E axis order, and the same `startIndex`/`count` paging contract as the BDL WFS from Faza 1 (spec §2.1). This plan reuses `pipeline.bdl.fetch_bdl`/`build_wfs_url` directly by pointing `base_url` at GDOŚ instead of duplicating a WFS client.
- **BDL "zakazy wstępu" (periodic access bans)**: spec §4.2/§9 step 8 describes reading this via WMS `GetFeatureInfo`. The service (`https://mapserver.bdl.lasy.gov.pl/ArcGIS/services/WMS_zakazy_wstepu_do_lasu/MapServer`) is an ArcGIS MapServer that also exposes a REST `query` operation (`.../ArcGIS/rest/services/WMS_zakazy_wstepu_do_lasu/MapServer/<layerId>/query`) returning GeoJSON directly from a point — verified live (2026-09-23) with `geometry=<lon>,<lat>&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=geojson`. This plan uses that REST query instead of raw WMS `GetFeatureInfo` pixel math: same underlying data, far simpler client, no behavior difference for "does a ban intersect this point". **`[?]` layer id ambiguity:** the WMS `GetCapabilities` lists the periodic-ban layer at index **3** ("Okresowy zakaz wstępu do lasu wprowadza się ze względu na:"), but the REST `MapServer?f=json` listing puts the same title at index **0**. This plan hardcodes `layer_id=0` (the REST listing is what the REST query actually uses) — **confirm this against a fresh `MapServer?f=json` fetch before the first real call** (Task 5's manual verification step) and update the constant if it has changed.
- **OSM data**: spec §2.7/§9 step 9 names Geofabrik PBF (`pyrosm`/`osmium`) as the MVP source. This plan uses the **Overpass API** (`https://overpass-api.de/api/interpreter`) scoped to the single 10×10 km test tile instead: no new heavy dependency (`pyrosm` pulls in its own GDAL-adjacent build chain), no multi-hundred-MB province-wide PBF download, and a single small bbox query is exactly what spec §13's "Overpass: nie masowo" (don't use it in bulk) permits — bulk use is what's discouraged, not a single-tile query. Documented scope simplification, same spirit as Faza 1's `G_season` shortcut.
- **`Demand` (presja gravity model, spec §4.5) uses OSM place nodes, not the Eurostat/GUS 1 km population grid.** Spec's own source table marks "Siatka ludności 1 km" as `MVP (opc.)` — explicitly optional — and the formula itself sums over `miejscowości` (towns), which OSM `place=city|town|village|hamlet` nodes with a `population` tag represent directly. This avoids a second heavy geodata download for an already-optional input.
- **`Demand_norm` normalization is per-tile max-normalization** (`Demand / max(Demand over all stands in this run)`), since spec §4.5 names `Demand_norm` without defining how to normalize it and flags `k`/`800 m`/`10 km` as `[E]` unvalidated anyway. Documented plan decision, same pattern as Faza 1's OL/Tp mask-ambiguity resolution.
- **`stands.pmtiles` (tippecanoe) generation is deferred, not built in this plan.** `tippecanoe` has no native Windows build (this repo's dev machine is Windows 11) and its only consumer is the MapLibre frontend from spec §9 step 12, which is explicitly out of scope for this plan. Task 11 (export) produces the two data-bearing artifacts the frontend will eventually read from — `scores_{date}.json` and a stand-geometry GeoParquet export — so the tippecanoe packaging step has real inputs ready whenever step 12 is picked up.
- Presja/confidence/explanation parameters added to `profiles/boletus_edulis.yaml` in Task 3 are marked `[E]` (expert guess, unvalidated) wherever spec itself marks them `[E]`, matching Faza 1's existing convention in that file.
- `compute_ranking`'s new `p`/`alpha` parameters default to `p=0.0, alpha=0.3` so every existing Faza 1 call site and test keeps passing unmodified — `(1 - alpha*0.0) == 1.0`.

## Review Focus

- **OSM `population` tag missing, blank, or non-numeric on a place node** (very common in real OSM data — many `place` nodes have no `population` tag at all): `compute_demand` must treat it as `0`, not crash or propagate `NaN` into every stand's `P`. Covered in Task 6 (`osm.py` parsing) and Task 7 (`pressure.py`).
- **A tile with zero GDOŚ protected-area features** (the overwhelmingly common case — most 10×10 km tiles are nowhere near a reserve): `mark_gdos_blocked` must return an all-`False` series cheaply, not raise on an empty `GeoDataFrame` join. Covered in Task 4.
- **A tile with zero OSM places carrying population** (e.g. a tile with roads/parking but no named settlement in range): `demand_max` would be `0`, and `Demand_norm = Demand / 0` must not raise `ZeroDivisionError`/produce `inf`. Covered in Task 7 and Task 10.
- **`alpha = 0` must reproduce Faza 1's original `R` exactly** — this is the regression guard that the new pressure term never changes Faza 1 behavior when the presja slider is at its minimum. Covered in Task 1.
- **Fewer mask-passing stands than `top_n_for_ban_check`** (small/sparse tiles): the periodic-ban top-N check must run over all available stands instead of raising on `.head(N)` with `N` larger than the frame. Covered in Task 10.

---

## File Structure

```
Grzyby/
  pipeline/
    scoring.py        # MODIFY: compute_ranking gains p/alpha
    orchestrate.py     # MODIFY: run_poc also exposes S_host/S_site/S_age/M/T/K_frost columns
    gdos.py            # NEW: GDOŚ protected-area fetch + stand-blocking check
    zakazy.py          # NEW: BDL periodic access-ban point check
    osm.py             # NEW: Overpass fetch (parking/roads/places) + parsing
    pressure.py         # NEW: d_park, Demand, Demand_norm, P
    confidence.py       # NEW: data-quality + model confidence -> final confidence + reasons
    explain.py          # NEW: log-contribution decomposition -> template sentences
    mvp.py               # NEW: enrich_with_mvp_layers, wires the above onto run_poc's output
    export.py            # NEW: scores_{date}.json + stand-geometry export
  profiles/
    boletus_edulis.yaml # MODIFY: + pressure, legal_mask, confidence, osm sections
  notebooks/
    02_mvp.py            # NEW: real fetchers -> run_poc -> enrich_with_mvp_layers -> export
  tests/
    test_scoring.py      # MODIFY: append p/alpha cases
    test_orchestrate.py  # MODIFY: append sub-score column assertions
    test_gdos.py          # NEW
    test_zakazy.py        # NEW
    test_osm.py            # NEW
    test_pressure.py       # NEW
    test_confidence.py     # NEW
    test_explain.py        # NEW
    test_mvp.py             # NEW
    test_export.py          # NEW
```

---

### Task 1: `compute_ranking` gains the presja term

**Files:**
- Modify: `pipeline/scoring.py`
- Modify: `tests/test_scoring.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `compute_ranking(mask: bool, h: float | None, f_loc: float | None, p: float = 0.0, alpha: float = 0.3) -> float`
- Consumed by: Task 10 (`pipeline/mvp.py`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scoring.py`:
```python
def test_compute_ranking_default_p_reproduces_faza1_behavior():
    # alpha's default (0.3) must not matter when p defaults to 0.0 -- this is
    # the regression guard that Faza 2's pressure term never changes Faza 1's R.
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5) == pytest.approx(100 * 0.8 * 0.5)


def test_compute_ranking_applies_pressure_discount():
    r = compute_ranking(mask=True, h=0.8, f_loc=0.5, p=0.5, alpha=0.3)
    assert r == pytest.approx(100 * 0.8 * 0.5 * (1 - 0.3 * 0.5))


def test_compute_ranking_zero_pressure_matches_no_pressure_call():
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5, p=0.0, alpha=0.3) == pytest.approx(
        compute_ranking(mask=True, h=0.8, f_loc=0.5)
    )


def test_compute_ranking_full_pressure_zeroes_ranking():
    # alpha at its spec §4.1 max (0.6) with p=1.0 is the strongest discount the
    # slider allows; confirm the formula behaves at that boundary too.
    r = compute_ranking(mask=True, h=0.8, f_loc=0.5, p=1.0, alpha=0.6)
    assert r == pytest.approx(100 * 0.8 * 0.5 * 0.4)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v -k pressure`
Expected: FAIL with `TypeError: compute_ranking() got an unexpected keyword argument 'p'`

- [ ] **Step 3: Implement**

In `pipeline/scoring.py`, replace `compute_ranking`:
```python
def compute_ranking(mask: bool, h: float | None, f_loc: float | None,
                      p: float = 0.0, alpha: float = 0.3) -> float:
    if not mask or h is None or f_loc is None:
        return 0.0
    return 100.0 * h * f_loc * (1.0 - alpha * p)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS (all Faza 1 `compute_ranking` tests plus the new ones)

- [ ] **Step 5: Commit**

```bash
git add pipeline/scoring.py tests/test_scoring.py
git commit -m "feat: compute_ranking accepts a presja (P) discount term"
```

---

### Task 2: expose intermediate factor scores from `run_poc`

**Files:**
- Modify: `pipeline/orchestrate.py`
- Modify: `tests/test_orchestrate.py`

**Interfaces:**
- Consumes: `score_host`, `score_age` from `pipeline.habitat` (not previously imported directly in `orchestrate.py`; `score_site` is already imported).
- Produces: `run_poc`'s returned GeoDataFrame gains columns `S_host`, `S_site`, `S_age`, `M`, `T`, `K_frost` (all `float`), in addition to the existing `stand_id`, `H`, `F`, `F_loc`, `mask`, `R`.
- Consumed by: Task 10 (`pipeline/explain.py` wiring in `enrich_with_mvp_layers`), which needs these per-stand factor values to compute log-contributions.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_orchestrate.py`:
```python
def test_run_poc_exposes_intermediate_factor_scores_for_explanations():
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

    for col in ["S_host", "S_site", "S_age", "M", "T", "K_frost"]:
        assert col in result.columns

    row = result.loc[result["stand_id"] == "A-1@2026"].iloc[0]
    # species_cd=SO, part_cd=10, site_type=BMSW, spec_age=60 -> pure-stand host
    # affinity and the site_scores/age_breakpoints values already exercised by
    # test_habitat.py.
    assert row["S_host"] == pytest.approx(1.0)
    assert row["S_site"] == pytest.approx(1.00)
    assert row["S_age"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrate.py -v -k intermediate`
Expected: FAIL with `AssertionError` (columns missing) — the module still imports fine since `score_site` already exists.

- [ ] **Step 3: Implement**

In `pipeline/orchestrate.py`, change the import line and the scoring loop:
```python
from pipeline.habitat import compute_habitat, passes_mask, score_site, score_host, score_age
```

Inside the `for _, row in stands.iterrows():` loop, right after the existing `h = compute_habitat(row, profile)` / `_s_site, moisture_cls = score_site(...)` lines, add:
```python
        s_host = score_host(row["species_cd"], row.get("part_cd", 10), profile)
        s_age = score_age(row.get("spec_age"), profile)
```
(`_s_site` already holds `S_site` — rename its use below instead of recomputing.)

Add four new accumulator lists next to the existing ones (`h_values, f_values, f_loc_values, mask_values, r_values`):
```python
    s_host_values, s_site_values, s_age_values = [], [], []
    m_values, t_values, k_frost_values = [], [], []
```

Inside the loop, append to them alongside the existing `.append(...)` calls:
```python
        s_host_values.append(s_host)
        s_site_values.append(_s_site)
        s_age_values.append(s_age)
        m_values.append(m)
        t_values.append(t)
        k_frost_values.append(k_frost)
```

After the loop, alongside the existing `stands["H"] = h_values` block, add:
```python
    stands["S_host"] = s_host_values
    stands["S_site"] = s_site_values
    stands["S_age"] = s_age_values
    stands["M"] = m_values
    stands["T"] = t_values
    stands["K_frost"] = k_frost_values
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_orchestrate.py -v`
Expected: PASS (all existing Faza 1 orchestrate tests plus the new one)

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrate.py tests/test_orchestrate.py
git commit -m "feat: run_poc exposes S_host/S_site/S_age/M/T/K_frost for explanations"
```

---

### Task 3: profile config additions (pressure, legal mask, confidence, OSM)

**Files:**
- Modify: `profiles/boletus_edulis.yaml`

**Interfaces:**
- Produces: `profile["pressure"]`, `profile["legal_mask"]`, `profile["confidence"]`, `profile["osm"]` dict sections.
- Consumed by: Task 4 (`legal_mask.gdos_layers`), Task 6 (`osm.*`), Task 7 (`pressure.*`), Task 8 (`confidence.*`), Task 10 (`mvp.py` wiring, `pressure.alpha_default`).

- [ ] **Step 1: Append the new sections**

Append to `profiles/boletus_edulis.yaml`:
```yaml
legal_mask:
  gdos_layers: ["GDOS:Rezerwaty", "GDOS:ParkiNarodowe"]   # spec §4.2, §9 step 8

pressure:
  k: 2.0                    # [E] gravity-model steepness, spec §4.5 -- unvalidated
  park_decay_m: 800.0       # spec §4.5 "exp(-d_parking/800 m)"
  demand_decay_km: 10.0     # spec §4.5 "1 + (d/10 km)^2"
  euclid_factor: 1.3        # spec §4.5 straight-line-to-real-road correction (MVP, no routing)
  alpha_default: 0.3        # spec §4.1 "α ∈ [0; 0,6] suwak, domyślnie 0,3"

osm:
  parking_amenity: "parking"
  road_highway_types: ["trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track"]
  place_types: ["city", "town", "village", "hamlet"]

confidence:
  data_quality_factors:
    kompletnosc_gatunek_panujacy: 0.7     # spec §10: "0,7 tylko gatunek panujący (WFS)"
    kompletnosc_gatunek_nieznany: 0.5     # [E] MVP fallback: species_cd absent from host_affinity entirely
    swiezosc_bez_s2: 1.0                  # spec §10: "1,0 jeśli brak sygnału zmiany w S2" -- no S2 in this plan, always true
    pogoda_nwp_2km: 0.8                   # spec §10: "0,8 NWP 2 km" (Open-Meteo forecast/ICON-D2)
  data_quality_classes:
    - {max: 0.40, label: "NISKA"}
    - {max: 0.70, label: "SREDNIA"}
    - {max: 1.01, label: "WYSOKA"}
  model_confidence_cap: "SREDNIA"          # spec §10: "faza 1-4: maks. SREDNIA"
  reasons:
    model_uncalibrated: 'model nieskalibrowany na danych terenowych (limit do "średniej")'
    weather_nwp: "pogoda z modelu ~2 km (brak radaru w archiwum)"
    species_dominant_only: "skład gatunkowy: tylko gatunek panujący"
    species_unknown: "gatunek panujący nierozpoznany w profilu gatunku"

explanation:
  max_positive: 2   # spec §9: "generujemy zdania z szablonów (2 plusy i 1-2 minusy)"
  max_negative: 2
```

- [ ] **Step 2: Verify the file still parses and existing tests still pass**

Run: `uv run pytest tests/test_habitat.py tests/test_scoring.py tests/test_profile_coverage.py -v`
Expected: PASS (these tests only read `host_affinity`/`site_scores`/`fruiting*` keys, untouched by the new sections)

- [ ] **Step 3: Commit**

```bash
git add profiles/boletus_edulis.yaml
git commit -m "feat: add pressure/legal_mask/confidence/osm sections to boletus_edulis profile"
```

---

### Task 4: GDOŚ protected-area fetch + stand-blocking check

**Files:**
- Create: `pipeline/gdos.py`
- Test: `tests/test_gdos.py`

**Interfaces:**
- Consumes: `pipeline.bdl.fetch_bdl` (reused as a generic WFS 2.0.0 GeoServer client — see Global Constraints).
- Produces: `fetch_protected_areas(bbox: tuple, layers: tuple[str, ...] = DEFAULT_GDOS_LAYERS, base_url: str = DEFAULT_GDOS_WFS_URL, page_size: int = 1000) -> geopandas.GeoDataFrame`
- Produces: `mark_gdos_blocked(stands: geopandas.GeoDataFrame, protected_areas: geopandas.GeoDataFrame) -> pandas.Series` (bool, indexed like `stands`)
- Consumed by: Task 10 (`pipeline/mvp.py`), Task 12 (`notebooks/02_mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_gdos.py`:
```python
import geopandas as gpd
import pandas as pd
import responses
from shapely.geometry import box

from pipeline.gdos import fetch_protected_areas, mark_gdos_blocked, DEFAULT_GDOS_WFS_URL

BBOX = (486000.0, 380000.0, 496000.0, 390000.0)


def _reserve_feature(fid, name):
    return {
        "type": "Feature", "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380100, 486100], [380200, 486100], [380200, 486200], [380100, 486200], [380100, 486100]]]},
        "properties": {"nazwa": name},
    }


@responses.activate
def test_fetch_protected_areas_combines_both_gdos_layers():
    reserves = {"type": "FeatureCollection", "features": [_reserve_feature(1, "Rez. Test")]}
    parks = {"type": "FeatureCollection", "features": []}
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=reserves, status=200)
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=parks, status=200)

    gdf = fetch_protected_areas(BBOX)

    assert len(gdf) == 1
    assert gdf.iloc[0]["nazwa"] == "Rez. Test"


@responses.activate
def test_fetch_protected_areas_handles_no_hits_in_either_layer():
    empty = {"type": "FeatureCollection", "features": []}
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=empty, status=200)
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=empty, status=200)

    gdf = fetch_protected_areas(BBOX)

    assert len(gdf) == 0


def _stands_gdf():
    return gpd.GeoDataFrame(
        {"stand_id": ["A", "B"]},
        geometry=[box(380100, 486100, 380200, 486200), box(381000, 487000, 381100, 487100)],
        crs="EPSG:2180",
    )


def test_mark_gdos_blocked_flags_intersecting_stand_only():
    protected = gpd.GeoDataFrame(
        {"nazwa": ["Rez. Test"]},
        geometry=[box(380150, 486150, 380250, 486250)],  # overlaps stand A, not B
        crs="EPSG:2180",
    )
    blocked = mark_gdos_blocked(_stands_gdf(), protected)
    assert blocked.tolist() == [True, False]


def test_mark_gdos_blocked_all_false_when_no_protected_areas():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    blocked = mark_gdos_blocked(_stands_gdf(), empty)
    assert blocked.tolist() == [False, False]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gdos.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.gdos'`

- [ ] **Step 3: Implement**

`pipeline/gdos.py`:
```python
import geopandas as gpd
import pandas as pd

from pipeline.bdl import fetch_bdl

DEFAULT_GDOS_WFS_URL = "https://sdi.gdos.gov.pl/wfs"
DEFAULT_GDOS_LAYERS = ("GDOS:Rezerwaty", "GDOS:ParkiNarodowe")


def fetch_protected_areas(bbox: tuple, layers: tuple = DEFAULT_GDOS_LAYERS,
                            base_url: str = DEFAULT_GDOS_WFS_URL,
                            page_size: int = 1000) -> gpd.GeoDataFrame:
    """GDOŚ's geoserver is the same WFS 2.0.0 GeoServer stack as BDL's (spec
    §2.1 vs the GDOŚ WFS GetCapabilities, verified 2026-09-23): same
    startIndex/count paging, same urn:ogc:def:crs:EPSG::2180 N,E axis order.
    Reuse pipeline.bdl.fetch_bdl instead of duplicating a WFS client."""
    frames = [fetch_bdl(layer, bbox, page_size=page_size, base_url=base_url) for layer in layers]
    frames = [f for f in frames if len(f)]
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)


def mark_gdos_blocked(stands: gpd.GeoDataFrame, protected_areas: gpd.GeoDataFrame) -> pd.Series:
    """True where a stand's polygon intersects any GDOŚ reserve/national-park
    polygon. Cheap all-False short-circuit for the overwhelmingly common case
    of a tile with no protected areas at all."""
    if len(protected_areas) == 0:
        return pd.Series(False, index=stands.index)
    hits = gpd.sjoin(stands[["geometry"]], protected_areas[["geometry"]],
                       how="left", predicate="intersects")
    blocked = hits.groupby(level=0)["index_right"].apply(lambda s: s.notna().any())
    return blocked.reindex(stands.index, fill_value=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gdos.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification against the real API (not part of pytest)**

```bash
uv run python -c "
from pipeline.tiles import tile_bbox_2180
from pipeline.gdos import fetch_protected_areas
bbox = tile_bbox_2180(50.526944, 18.605000, size_km=10.0)
gdf = fetch_protected_areas(bbox)
print(len(gdf), gdf.columns.tolist() if len(gdf) else '(no protected areas in this tile)')
"
```
Expected: no exceptions; either an empty result (Kieleczka tile is not known to overlap a reserve) or a small GeoDataFrame with reserve attributes.

- [ ] **Step 6: Commit**

```bash
git add pipeline/gdos.py tests/test_gdos.py
git commit -m "feat: GDOŚ protected-area fetch and stand-blocking check"
```

---

### Task 5: BDL periodic access-ban point check

**Files:**
- Create: `pipeline/zakazy.py`
- Test: `tests/test_zakazy.py`

**Interfaces:**
- Produces: `build_zakazy_query_url(lat: float, lon: float, layer_id: int = DEFAULT_LAYER_ID, base_url: str = DEFAULT_ZAKAZY_URL) -> str`
- Produces: `check_periodic_ban(lat: float, lon: float, call_api=None) -> bool`
- Consumed by: Task 10 (`pipeline/mvp.py`), Task 12 (`notebooks/02_mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_zakazy.py`:
```python
import pytest

from pipeline.zakazy import build_zakazy_query_url, check_periodic_ban, DEFAULT_ZAKAZY_URL


def test_build_zakazy_query_url_contains_point_and_geojson_format():
    url = build_zakazy_query_url(50.526944, 18.605000)
    assert url.startswith(DEFAULT_ZAKAZY_URL)
    assert "geometryType=esriGeometryPoint" in url
    assert "f=geojson" in url
    assert "18.605" in url and "50.526944" in url


def test_check_periodic_ban_true_when_features_present():
    def fake_call_api(lat, lon):
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}}]}

    assert check_periodic_ban(50.5, 18.6, call_api=fake_call_api) is True


def test_check_periodic_ban_false_when_no_features():
    def fake_call_api(lat, lon):
        return {"type": "FeatureCollection", "features": []}

    assert check_periodic_ban(50.5, 18.6, call_api=fake_call_api) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_zakazy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.zakazy'`

- [ ] **Step 3: Implement**

`pipeline/zakazy.py`:
```python
import requests

# ArcGIS REST query on the BDL periodic-access-ban MapServer, used instead of
# raw WMS GetFeatureInfo pixel math (see plan Global Constraints for the
# layer-id [?] verified 2026-09-23: WMS GetCapabilities lists this layer at
# index 3, the REST MapServer listing at index 0 -- 0 is what this module's
# query URL actually hits, re-verify via Step 5 before relying on it).
DEFAULT_ZAKAZY_URL = "https://mapserver.bdl.lasy.gov.pl/ArcGIS/rest/services/WMS_zakazy_wstepu_do_lasu/MapServer"
DEFAULT_LAYER_ID = 0


def build_zakazy_query_url(lat: float, lon: float, layer_id: int = DEFAULT_LAYER_ID,
                             base_url: str = DEFAULT_ZAKAZY_URL) -> str:
    req = requests.Request(
        "GET",
        f"{base_url}/{layer_id}/query",
        params={
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
        },
    )
    return req.prepare().url


def _default_zakazy_call(lat: float, lon: float) -> dict:
    """Thin IO boundary; not unit tested (network), see Step 5 manual
    verification."""
    resp = requests.get(build_zakazy_query_url(lat, lon), timeout=30)
    resp.raise_for_status()
    return resp.json()


def check_periodic_ban(lat: float, lon: float, call_api=None) -> bool:
    """True if a periodic access ban polygon covers (lat, lon) right now."""
    call_api = call_api or _default_zakazy_call
    data = call_api(lat, lon)
    return len(data.get("features", [])) > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_zakazy.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification against the real API (not part of pytest)**

First confirm the layer id is still 0 (the `[?]` in Global Constraints):
```bash
uv run python -c "
import requests
r = requests.get('https://mapserver.bdl.lasy.gov.pl/ArcGIS/rest/services/WMS_zakazy_wstepu_do_lasu/MapServer?f=json', timeout=30)
for layer in r.json()['layers']:
    print(layer['id'], layer['name'])
"
```
Expected: layer id `0` is named something like "Okresowy zakaz wstępu do lasu wprowadza się ze względu na:". If the id has changed, update `DEFAULT_LAYER_ID` in `pipeline/zakazy.py`.

Then a real point check:
```bash
uv run python -c "
from pipeline.zakazy import check_periodic_ban
print(check_periodic_ban(50.526944, 18.605000))
"
```
Expected: no exceptions; prints `True` or `False`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/zakazy.py tests/test_zakazy.py
git commit -m "feat: BDL periodic access-ban point check via ArcGIS REST query"
```

---

### Task 6: OSM Overpass fetch (parking, roads, places)

**Files:**
- Create: `pipeline/osm.py`
- Test: `tests/test_osm.py`

**Interfaces:**
- Consumes: `bbox_2180` tuple shape from Task 2 (Faza 1 `pipeline.tiles`).
- Produces: `build_overpass_query(bbox_4326: tuple, profile: dict) -> str`
- Produces: `parse_osm_elements(elements: list[dict]) -> dict[str, geopandas.GeoDataFrame]` with keys `"parking"`, `"roads"`, `"places"` (the `"places"` frame has a numeric `population` column, coerced, missing/blank -> `0.0`)
- Produces: `fetch_osm_features(bbox_2180: tuple, profile: dict, call_api=None) -> dict[str, geopandas.GeoDataFrame]` (result frames in `EPSG:2180`, matching `stands.crs`)
- Consumed by: Task 10 (`pipeline/mvp.py`), Task 12 (`notebooks/02_mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_osm.py`:
```python
import pandas as pd
import pytest

from pipeline.habitat import load_profile
from pipeline.osm import build_overpass_query, parse_osm_elements, fetch_osm_features

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX_4326 = (50.50, 18.55, 50.55, 18.65)  # south, west, north, east
BBOX_2180 = (486000.0, 380000.0, 496000.0, 390000.0)


def test_build_overpass_query_includes_bbox_and_configured_filters():
    q = build_overpass_query(BBOX_4326, PROFILE)
    assert "50.5,18.55,50.55,18.65" in q
    assert 'amenity"="parking"' in q
    assert "track" in q  # from profile.osm.road_highway_types
    assert "village" in q  # from profile.osm.place_types


ELEMENTS = [
    {"type": "node", "id": 1, "lat": 50.51, "lon": 18.60, "tags": {"amenity": "parking"}},
    {"type": "way", "id": 2, "center": {"lat": 50.52, "lon": 18.61}, "tags": {"highway": "track"}},
    {"type": "node", "id": 3, "lat": 50.53, "lon": 18.62, "tags": {"place": "village", "name": "Kieleczka", "population": "450"}},
    {"type": "node", "id": 4, "lat": 50.54, "lon": 18.63, "tags": {"place": "hamlet", "name": "Bez ludzi"}},  # no population tag
]


def test_parse_osm_elements_splits_into_parking_roads_places():
    frames = parse_osm_elements(ELEMENTS)
    assert set(frames) == {"parking", "roads", "places"}
    assert len(frames["parking"]) == 1
    assert len(frames["roads"]) == 1
    assert len(frames["places"]) == 2


def test_parse_osm_elements_coerces_missing_population_to_zero():
    frames = parse_osm_elements(ELEMENTS)
    places = frames["places"].set_index(frames["places"]["name"] if "name" in frames["places"] else frames["places"].index)
    pop_by_name = dict(zip(frames["places"]["name"], frames["places"]["population"]))
    assert pop_by_name["Kieleczka"] == pytest.approx(450.0)
    assert pop_by_name["Bez ludzi"] == pytest.approx(0.0)


def test_parse_osm_elements_uses_way_center_as_geometry():
    frames = parse_osm_elements(ELEMENTS)
    road_point = frames["roads"].geometry.iloc[0]
    assert road_point.x == pytest.approx(18.61)
    assert road_point.y == pytest.approx(50.52)


def test_fetch_osm_features_uses_injected_call_api_and_reprojects_to_2180():
    captured = {}

    def fake_call_api(query):
        captured["query"] = query
        return {"elements": ELEMENTS}

    frames = fetch_osm_features(BBOX_2180, PROFILE, call_api=fake_call_api)

    assert "query" in captured
    assert frames["places"].crs.to_epsg() == 2180
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_osm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.osm'`

- [ ] **Step 3: Implement**

`pipeline/osm.py`:
```python
import geopandas as gpd
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _bbox_2180_to_4326(bbox_2180: tuple) -> tuple:
    n_min, e_min, n_max, e_max = bbox_2180
    corners = [(e_min, n_min), (e_min, n_max), (e_max, n_min), (e_max, n_max)]
    lons, lats = zip(*(_TO_4326.transform(e, n) for e, n in corners))
    return (min(lats), min(lons), max(lats), max(lons))  # south, west, north, east


def build_overpass_query(bbox_4326: tuple, profile: dict) -> str:
    south, west, north, east = bbox_4326
    bbox_str = f"{south},{west},{north},{east}"
    cfg = profile["osm"]
    highway_re = "|".join(cfg["road_highway_types"])
    place_re = "|".join(cfg["place_types"])
    return (
        f'[out:json][timeout:25];'
        f'('
        f'node["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["highway"~"^({highway_re})$"]({bbox_str});'
        f'node["place"~"^({place_re})$"]({bbox_str});'
        f');'
        f'out center tags;'
    )


def _element_point(element: dict):
    if "lat" in element and "lon" in element:
        return Point(element["lon"], element["lat"])
    center = element.get("center")
    if center:
        return Point(center["lon"], center["lat"])
    return None


def parse_osm_elements(elements: list[dict]) -> dict:
    parking_rows, road_rows, place_rows = [], [], []
    for el in elements:
        tags = el.get("tags", {})
        point = _element_point(el)
        if point is None:
            continue
        if tags.get("amenity") == "parking":
            parking_rows.append({"osm_id": el["id"], "geometry": point})
        elif "highway" in tags:
            road_rows.append({"osm_id": el["id"], "highway": tags["highway"], "geometry": point})
        elif "place" in tags:
            population = pd.to_numeric(tags.get("population"), errors="coerce")
            place_rows.append({
                "osm_id": el["id"], "place": tags["place"], "name": tags.get("name", ""),
                "population": 0.0 if pd.isna(population) else float(population),
                "geometry": point,
            })
    return {
        "parking": gpd.GeoDataFrame(parking_rows, geometry="geometry", crs="EPSG:4326") if parking_rows
                    else gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326"),
        "roads": gpd.GeoDataFrame(road_rows, geometry="geometry", crs="EPSG:4326") if road_rows
                  else gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326"),
        "places": gpd.GeoDataFrame(place_rows, geometry="geometry", crs="EPSG:4326") if place_rows
                   else gpd.GeoDataFrame({"osm_id": [], "population": []}, geometry=[], crs="EPSG:4326"),
    }


def _default_overpass_call(query: str) -> dict:
    """Thin IO boundary; not unit tested (network), see Task 6 Step 5 manual
    verification. POST, not GET-with-huge-URL -- Overpass rejects/queues long
    GET query strings under load."""
    resp = requests.post(DEFAULT_OVERPASS_URL, data={"data": query}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_osm_features(bbox_2180: tuple, profile: dict, call_api=None) -> dict:
    call_api = call_api or _default_overpass_call
    bbox_4326 = _bbox_2180_to_4326(bbox_2180)
    query = build_overpass_query(bbox_4326, profile)
    data = call_api(query)
    frames = parse_osm_elements(data.get("elements", []))
    return {name: gdf.to_crs("EPSG:2180") for name, gdf in frames.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_osm.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification against the real API (not part of pytest)**

```bash
uv run python -c "
from pipeline.habitat import load_profile
from pipeline.tiles import tile_bbox_2180
from pipeline.osm import fetch_osm_features
profile = load_profile('profiles/boletus_edulis.yaml')
bbox = tile_bbox_2180(50.526944, 18.605000, size_km=10.0)
frames = fetch_osm_features(bbox, profile)
for name, gdf in frames.items():
    print(name, len(gdf))
print(frames['places'][['name', 'population']] if len(frames['places']) else 'no places')
"
```
Expected: no exceptions; some parking/roads/places counts for the Kieleczka tile (village of Kieleczka itself should show up in `places`).

- [ ] **Step 6: Commit**

```bash
git add pipeline/osm.py tests/test_osm.py
git commit -m "feat: OSM Overpass fetch for parking/roads/places"
```

---

### Task 7: distance, Demand, and presja (P) scoring

**Files:**
- Create: `pipeline/pressure.py`
- Test: `tests/test_pressure.py`

**Interfaces:**
- Consumes: `profile["pressure"]` (Task 3), GeoDataFrames shaped like Task 6's `fetch_osm_features` output.
- Produces: `nearest_distance_m(point, points_gdf: geopandas.GeoDataFrame | None) -> float | None`
- Produces: `compute_d_park(centroid, parking_gdf, roads_gdf, euclid_factor: float) -> float | None`
- Produces: `compute_demand(centroid, places_gdf, decay_km: float) -> float`
- Produces: `compute_pressure(d_park: float | None, demand: float, demand_max: float, profile: dict) -> float`
- Consumed by: Task 10 (`pipeline/mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_pressure.py`:
```python
import math
import geopandas as gpd
import pytest
from shapely.geometry import Point

from pipeline.habitat import load_profile
from pipeline.pressure import nearest_distance_m, compute_d_park, compute_demand, compute_pressure

PROFILE = load_profile("profiles/boletus_edulis.yaml")
CENTROID = Point(385000.0, 491000.0)


def test_nearest_distance_m_returns_min_distance():
    points = gpd.GeoDataFrame(geometry=[Point(385000.0, 491100.0), Point(385000.0, 491500.0)], crs="EPSG:2180")
    assert nearest_distance_m(CENTROID, points) == pytest.approx(100.0)


def test_nearest_distance_m_none_when_no_points():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    assert nearest_distance_m(CENTROID, empty) is None
    assert nearest_distance_m(CENTROID, None) is None


def test_compute_d_park_takes_closer_of_parking_or_road_times_euclid_factor():
    parking = gpd.GeoDataFrame(geometry=[Point(385000.0, 491200.0)], crs="EPSG:2180")  # 200 m
    roads = gpd.GeoDataFrame(geometry=[Point(385000.0, 491050.0)], crs="EPSG:2180")     # 50 m, closer
    d = compute_d_park(CENTROID, parking, roads, euclid_factor=1.3)
    assert d == pytest.approx(50.0 * 1.3)


def test_compute_d_park_none_when_neither_source_has_points():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    assert compute_d_park(CENTROID, empty, empty, euclid_factor=1.3) is None


def test_compute_demand_sums_gravity_weighted_population():
    places = gpd.GeoDataFrame(
        {"population": [1000.0, 500.0]},
        geometry=[Point(385000.0, 491000.0 + 10000.0), Point(385000.0, 491000.0 + 20000.0)],  # 10km, 20km
        crs="EPSG:2180",
    )
    demand = compute_demand(CENTROID, places, decay_km=10.0)
    expected = 1000.0 / (1 + (10.0 / 10.0) ** 2) + 500.0 / (1 + (20.0 / 10.0) ** 2)
    assert demand == pytest.approx(expected)


def test_compute_demand_zero_when_no_places():
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    assert compute_demand(CENTROID, empty, decay_km=10.0) == 0.0


def test_compute_pressure_matches_formula():
    p = compute_pressure(d_park=400.0, demand=50.0, demand_max=100.0, profile=PROFILE)
    cfg = PROFILE["pressure"]
    expected = 1 - math.exp(-cfg["k"] * (50.0 / 100.0) * math.exp(-400.0 / cfg["park_decay_m"]))
    assert p == pytest.approx(expected)


def test_compute_pressure_zero_demand_max_does_not_raise():
    p = compute_pressure(d_park=400.0, demand=0.0, demand_max=0.0, profile=PROFILE)
    assert p == pytest.approx(0.0)


def test_compute_pressure_none_d_park_treated_as_very_far():
    p = compute_pressure(d_park=None, demand=100.0, demand_max=100.0, profile=PROFILE)
    assert p == pytest.approx(0.0, abs=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pressure.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.pressure'`

- [ ] **Step 3: Implement**

`pipeline/pressure.py`:
```python
import math


def nearest_distance_m(point, points_gdf) -> float | None:
    if points_gdf is None or len(points_gdf) == 0:
        return None
    return float(points_gdf.distance(point).min())


def compute_d_park(centroid, parking_gdf, roads_gdf, euclid_factor: float) -> float | None:
    d_parking = nearest_distance_m(centroid, parking_gdf)
    d_road = nearest_distance_m(centroid, roads_gdf)
    candidates = [d for d in (d_parking, d_road) if d is not None]
    if not candidates:
        return None
    return min(candidates) * euclid_factor


def compute_demand(centroid, places_gdf, decay_km: float) -> float:
    if places_gdf is None or len(places_gdf) == 0:
        return 0.0
    dists_km = places_gdf.distance(centroid) / 1000.0
    pops = places_gdf["population"].fillna(0.0).astype(float)
    return float((pops / (1 + (dists_km / decay_km) ** 2)).sum())


def compute_pressure(d_park: float | None, demand: float, demand_max: float, profile: dict) -> float:
    """P = 1 - exp(-k * Demand_norm * exp(-d_park/park_decay_m)), spec §4.5.
    d_park=None (no parking/road data at all in this tile) is treated as
    "infinitely far", which drives the park_term to 0 and P to 0 -- a
    conservative default (never overstate pressure) rather than a crash."""
    cfg = profile["pressure"]
    demand_norm = 0.0 if demand_max in (0, 0.0, None) else demand / demand_max
    effective_d_park = d_park if d_park is not None else math.inf
    park_term = math.exp(-effective_d_park / cfg["park_decay_m"])
    return 1.0 - math.exp(-cfg["k"] * demand_norm * park_term)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pressure.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/pressure.py tests/test_pressure.py
git commit -m "feat: d_park/Demand/pressure (P) scoring from OSM features"
```

---

### Task 8: confidence scoring

**Files:**
- Create: `pipeline/confidence.py`
- Test: `tests/test_confidence.py`

**Interfaces:**
- Consumes: `profile["confidence"]` (Task 3), `profile["host_affinity"]` (Faza 1).
- Produces: `score_data_quality(row: dict, profile: dict) -> float`
- Produces: `classify_data_quality(value: float, profile: dict) -> str`
- Produces: `compute_confidence(row: dict, profile: dict) -> tuple[str, list[str]]`
- Consumed by: Task 10 (`pipeline/mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_confidence.py`:
```python
import pytest

from pipeline.habitat import load_profile
from pipeline.confidence import score_data_quality, classify_data_quality, compute_confidence

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_data_quality_known_species():
    row = {"species_cd": "SO"}
    cfg = PROFILE["confidence"]["data_quality_factors"]
    expected = cfg["kompletnosc_gatunek_panujacy"] * cfg["swiezosc_bez_s2"] * cfg["pogoda_nwp_2km"]
    assert score_data_quality(row, PROFILE) == pytest.approx(expected)


def test_score_data_quality_unknown_species_is_lower():
    row_known = {"species_cd": "SO"}
    row_unknown = {"species_cd": "ZZZ"}
    assert score_data_quality(row_unknown, PROFILE) < score_data_quality(row_known, PROFILE)


def test_classify_data_quality_boundaries():
    assert classify_data_quality(0.39, PROFILE) == "NISKA"
    assert classify_data_quality(0.40, PROFILE) == "SREDNIA"
    assert classify_data_quality(0.69, PROFILE) == "SREDNIA"
    assert classify_data_quality(0.70, PROFILE) == "WYSOKA"


def test_compute_confidence_caps_at_model_confidence():
    # data quality for a known species (0.7*1.0*0.8=0.56) classifies SREDNIA,
    # and model_confidence_cap is also SREDNIA -- final must be SREDNIA, not
    # upgraded past the model cap even if data quality were higher.
    row = {"species_cd": "SO"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "SREDNIA"
    assert PROFILE["confidence"]["reasons"]["model_uncalibrated"] in reasons


def test_compute_confidence_includes_species_unknown_reason():
    row = {"species_cd": "ZZZ"}
    _final, reasons = compute_confidence(row, PROFILE)
    assert PROFILE["confidence"]["reasons"]["species_unknown"] in reasons


def test_compute_confidence_never_exceeds_niska_when_data_quality_is_niska(monkeypatch):
    low_profile = {**PROFILE, "confidence": {
        **PROFILE["confidence"],
        "data_quality_factors": {**PROFILE["confidence"]["data_quality_factors"], "pogoda_nwp_2km": 0.1},
    }}
    final, _reasons = compute_confidence({"species_cd": "SO"}, low_profile)
    assert final == "NISKA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_confidence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.confidence'`

- [ ] **Step 3: Implement**

`pipeline/confidence.py`:
```python
CONFIDENCE_ORDER = {"NISKA": 0, "SREDNIA": 1, "WYSOKA": 2}


def score_data_quality(row: dict, profile: dict) -> float:
    cfg = profile["confidence"]["data_quality_factors"]
    species_known = row.get("species_cd") in profile["host_affinity"]
    kompletnosc = cfg["kompletnosc_gatunek_panujacy"] if species_known else cfg["kompletnosc_gatunek_nieznany"]
    return kompletnosc * cfg["swiezosc_bez_s2"] * cfg["pogoda_nwp_2km"]


def classify_data_quality(value: float, profile: dict) -> str:
    for cls in profile["confidence"]["data_quality_classes"]:
        if value < cls["max"]:
            return cls["label"]
    return profile["confidence"]["data_quality_classes"][-1]["label"]


def compute_confidence(row: dict, profile: dict) -> tuple[str, list[str]]:
    cfg = profile["confidence"]
    dq_value = score_data_quality(row, profile)
    dq_class = classify_data_quality(dq_value, profile)
    model_class = cfg["model_confidence_cap"]
    final_class = dq_class if CONFIDENCE_ORDER[dq_class] <= CONFIDENCE_ORDER[model_class] else model_class

    reasons = [cfg["reasons"]["model_uncalibrated"]]
    factors = cfg["data_quality_factors"]
    if factors["pogoda_nwp_2km"] < 1.0:
        reasons.append(cfg["reasons"]["weather_nwp"])
    species_known = row.get("species_cd") in profile["host_affinity"]
    if species_known:
        reasons.append(cfg["reasons"]["species_dominant_only"])
    else:
        reasons.append(cfg["reasons"]["species_unknown"])
    return final_class, reasons
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_confidence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/confidence.py tests/test_confidence.py
git commit -m "feat: data-quality + model confidence -> final confidence and reasons"
```

---

### Task 9: log-contribution explanations

**Files:**
- Create: `pipeline/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (pure module); Task 10 supplies the `values`/`area_medians`/`meta` dicts from `stands` columns produced by Task 2.
- Produces: `compute_log_contributions(values: dict[str, float], area_medians: dict[str, float]) -> dict[str, float]`
- Produces: `generate_explanation(contributions: dict[str, float], values: dict[str, float], meta: dict, profile: dict) -> list[dict]` (each entry `{"factor": str, "contribution": float, "text": str}`)
- Consumed by: Task 10 (`pipeline/mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_explain.py`:
```python
import math
import pytest

from pipeline.habitat import load_profile
from pipeline.explain import compute_log_contributions, generate_explanation, FACTOR_WEIGHTS

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_compute_log_contributions_positive_above_median():
    values = {"host": 1.0, "site": 1.0, "age": 1.0, "moisture": 0.5, "temperature": 1.0, "frost": 1.0, "pressure_factor": 1.0}
    medians = {"host": 0.5, "site": 0.5, "age": 0.5, "moisture": 0.5, "temperature": 0.5, "frost": 1.0, "pressure_factor": 1.0}
    contributions = compute_log_contributions(values, medians)
    assert contributions["host"] == pytest.approx(FACTOR_WEIGHTS["host"] * math.log(1.0 / 0.5))
    # value == median -> log ratio is 0, but the factor is still included (not skipped)
    assert "frost" in contributions
    assert contributions["frost"] == pytest.approx(0.0)


def test_compute_log_contributions_skips_non_positive_inputs():
    values = {"host": 0.0, "site": 1.0}
    medians = {"host": 0.5, "site": 0.5}
    contributions = compute_log_contributions(values, medians)
    assert "host" not in contributions
    assert "site" in contributions


def test_compute_log_contributions_skips_missing_median():
    values = {"host": 1.0}
    medians = {}
    contributions = compute_log_contributions(values, medians)
    assert contributions == {}


def test_generate_explanation_picks_top_positives_and_negatives():
    contributions = {"host": 0.5, "site": 0.3, "age": 0.1, "moisture": -0.4, "temperature": -0.2, "frost": 0.0}
    values = {"host": 1.0, "site": 0.9, "age": 0.8, "moisture": 0.2, "temperature": 0.3, "frost": 1.0, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.1}
    entries = generate_explanation(contributions, values, meta, PROFILE)

    factors = [e["factor"] for e in entries]
    assert factors[:2] == ["host", "site"]  # top 2 positive, descending
    assert "moisture" in factors[-2:]  # most negative included
    for entry in entries:
        assert entry["text"]
        assert isinstance(entry["contribution"], float)


def test_generate_explanation_respects_profile_max_counts():
    contributions = {"host": 0.9, "site": 0.5, "age": 0.4, "moisture": -0.9, "temperature": -0.5, "frost": -0.4}
    values = {"host": 1.0, "site": 1.0, "age": 1.0, "moisture": 0.1, "temperature": 0.1, "frost": 0.1, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.1}
    entries = generate_explanation(contributions, values, meta, PROFILE)
    assert sum(1 for e in entries if e["contribution"] > 0) <= PROFILE["explanation"]["max_positive"]
    assert sum(1 for e in entries if e["contribution"] < 0) <= PROFILE["explanation"]["max_negative"]


def test_generate_explanation_handles_no_negative_contributions():
    contributions = {"host": 0.5, "site": 0.1}
    values = {"host": 1.0, "site": 1.0, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.0}
    entries = generate_explanation(contributions, values, meta, PROFILE)
    assert all(e["contribution"] > 0 for e in entries)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_explain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.explain'`

- [ ] **Step 3: Implement**

`pipeline/explain.py`:
```python
import math

# Weights mirror the exponents already hardcoded in pipeline.habitat.compute_habitat
# (host/site/age) and pipeline.scoring.compute_fruiting (moisture/temperature);
# frost and the presja discount enter H/F/R with an implicit exponent of 1.
FACTOR_WEIGHTS = {
    "host": 0.40, "site": 0.35, "age": 0.25,
    "moisture": 0.6, "temperature": 0.4, "frost": 1.0,
    "pressure_factor": 1.0,
}

TEMPLATES = {
    "host": {
        "up": "gatunek panujący {species_cd} ma wysokie powinowactwo do borowika (S_host={value:.2f})",
        "down": "gatunek panujący {species_cd} słabo pasuje do borowika (S_host={value:.2f})",
    },
    "site": {
        "up": "siedlisko {site_type} sprzyja owocnikowaniu (S_site={value:.2f})",
        "down": "siedlisko {site_type} słabo sprzyja owocnikowaniu (S_site={value:.2f})",
    },
    "age": {
        "up": "wiek drzewostanu {age} lat jest w dobrym przedziale (S_age={value:.2f})",
        "down": "wiek drzewostanu {age} lat jest poza optymalnym przedziałem (S_age={value:.2f})",
    },
    "moisture": {
        "up": "wilgotność ostatnich 26 dni powyżej normy dla tej pory roku (M={value:.2f})",
        "down": "wilgotność ostatnich 26 dni poniżej normy dla tej pory roku (M={value:.2f})",
    },
    "temperature": {
        "up": "temperatura blisko optimum dla owocnikowania (T={value:.2f})",
        "down": "temperatura odbiega od optimum dla owocnikowania (T={value:.2f})",
    },
    "frost": {
        "up": "brak istotnego ryzyka przymrozku (K_frost={value:.2f})",
        "down": "ryzyko przymrozku obniża szansę na owocniki (K_frost={value:.2f})",
    },
    "pressure_factor": {
        "up": "niska presja innych grzybiarzy w tej okolicy (P={P:.2f})",
        "down": "wysoka presja innych grzybiarzy w tej okolicy (P={P:.2f})",
    },
}


def compute_log_contributions(values: dict, area_medians: dict) -> dict:
    contributions = {}
    for factor, weight in FACTOR_WEIGHTS.items():
        value = values.get(factor)
        median = area_medians.get(factor)
        if value is None or median is None or value <= 0 or median <= 0:
            continue
        contributions[factor] = weight * (math.log(value) - math.log(median))
    return contributions


def generate_explanation(contributions: dict, values: dict, meta: dict, profile: dict) -> list:
    cfg = profile["explanation"]
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    ups = [item for item in ranked if item[1] > 0][: cfg["max_positive"]]
    downs = sorted((item for item in ranked if item[1] < 0), key=lambda kv: kv[1])[: cfg["max_negative"]]

    entries = []
    for factor, contribution in ups + downs:
        direction = "up" if contribution > 0 else "down"
        template = TEMPLATES[factor][direction]
        fmt_args = {**meta, "value": values.get(factor, 0.0)}
        text = template.format(**fmt_args)
        entries.append({"factor": factor, "contribution": float(contribution), "text": text})
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_explain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/explain.py tests/test_explain.py
git commit -m "feat: log-contribution explanation generator (deterministic, template-based)"
```

---

### Task 10: MVP enrichment orchestration

**Files:**
- Create: `pipeline/mvp.py`
- Test: `tests/test_mvp.py`

**Interfaces:**
- Consumes: `run_poc`'s output shape (Faza 1 `pipeline.orchestrate`, extended in Task 2), `mark_gdos_blocked` (Task 4), `check_periodic_ban`-shaped `zakaz_checker` (Task 5), `fetch_osm_features`-shaped `osm_features` dict (Task 6), `compute_d_park`/`compute_demand`/`compute_pressure` (Task 7), `compute_ranking` (Task 1), `compute_confidence` (Task 8), `compute_log_contributions`/`generate_explanation` (Task 9).
- Produces: `enrich_with_mvp_layers(stands: geopandas.GeoDataFrame, profile: dict, gdos_gdf: geopandas.GeoDataFrame, osm_features: dict, zakaz_checker, alpha: float | None = None, top_n_for_ban_check: int = 50) -> geopandas.GeoDataFrame` — returns `stands` with new columns `gdos_blocked`, `mask_full`, `d_park_m`, `demand`, `demand_norm`, `P`, `pressure_factor`, `R_final`, `periodic_ban_checked`, `periodic_ban_active`, `confidence`, `confidence_reasons`, `explanation`.
- Consumed by: Task 11 (`pipeline/export.py`), Task 12 (`notebooks/02_mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_mvp.py`:
```python
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box, Point

from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _scored_stands():
    # Mimics run_poc's output shape (Faza 1 + Task 2 columns) for two stands.
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "species_cd": ["SO", "SO"],
        "site_type": ["BMSW", "BMSW"],
        "spec_age": [60, 60],
        "mask": [True, True],
        "H": [0.9, 0.9],
        "F": [0.6, 0.6],
        "F_loc": [0.6, 0.6],
        "R": [54.0, 54.0],
        "S_host": [1.0, 1.0], "S_site": [1.0, 1.0], "S_age": [1.0, 1.0],
        "M": [0.5, 0.5], "T": [0.8, 0.8], "K_frost": [1.0, 1.0],
    }, geometry=[box(380100, 486100, 380200, 486200), box(390100, 496100, 390200, 496200)], crs="EPSG:2180")


def _no_osm_features():
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    empty_no_pop = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    return {"parking": empty_no_pop, "roads": empty_no_pop, "places": empty}


def _no_gdos():
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")


def test_enrich_adds_all_expected_columns_and_never_checks_ban():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: (_ for _ in ()).throw(AssertionError("should not be called")),
        top_n_for_ban_check=0,
    )
    for col in ["gdos_blocked", "mask_full", "d_park_m", "demand", "demand_norm", "P",
                "pressure_factor", "R_final", "periodic_ban_checked", "periodic_ban_active",
                "confidence", "confidence_reasons", "explanation"]:
        assert col in result.columns
    assert result["periodic_ban_checked"].tolist() == [False, False]


def test_enrich_zero_demand_and_no_parking_gives_zero_pressure():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    assert (result["P"] == pytest.approx(0.0)).all()
    assert (result["R_final"] == result["R"]).all()  # pressure_factor == 1.0 -> unchanged


def test_enrich_gdos_block_zeroes_out_ranking():
    stands = _scored_stands()
    protected = gpd.GeoDataFrame(geometry=[box(380100, 486100, 380200, 486200)], crs="EPSG:2180")  # covers stand A only
    result = enrich_with_mvp_layers(
        stands, PROFILE, protected, _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    blocked_row = result[result["stand_id"] == "A"].iloc[0]
    open_row = result[result["stand_id"] == "B"].iloc[0]
    assert bool(blocked_row["gdos_blocked"]) is True
    assert bool(blocked_row["mask_full"]) is False
    assert blocked_row["R_final"] == pytest.approx(0.0)
    assert open_row["R_final"] > 0


def test_enrich_periodic_ban_zeroes_ranking_for_checked_stand():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: True, top_n_for_ban_check=10,
    )
    assert (result["periodic_ban_checked"]).all()
    assert (result["periodic_ban_active"]).all()
    assert (result["R_final"] == pytest.approx(0.0)).all()


def test_enrich_top_n_larger_than_row_count_does_not_raise():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=1000,
    )
    assert len(result) == 2


def test_enrich_explanation_is_a_list_of_dicts_with_expected_keys():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    explanation = result.iloc[0]["explanation"]
    assert isinstance(explanation, list)
    for entry in explanation:
        assert set(entry) == {"factor", "contribution", "text"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mvp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.mvp'`

- [ ] **Step 3: Implement**

`pipeline/mvp.py`:
```python
import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.confidence import compute_confidence
from pipeline.explain import compute_log_contributions, generate_explanation
from pipeline.gdos import mark_gdos_blocked
from pipeline.pressure import compute_d_park, compute_demand, compute_pressure
from pipeline.scoring import compute_ranking

_EXPLANATION_FACTORS = ["S_host", "S_site", "S_age", "M", "T", "K_frost"]
_FACTOR_KEY_MAP = {
    "S_host": "host", "S_site": "site", "S_age": "age",
    "M": "moisture", "T": "temperature", "K_frost": "frost",
}


def enrich_with_mvp_layers(stands: gpd.GeoDataFrame, profile: dict, gdos_gdf: gpd.GeoDataFrame,
                              osm_features: dict, zakaz_checker, alpha: float | None = None,
                              top_n_for_ban_check: int = 50) -> gpd.GeoDataFrame:
    stands = stands.copy()
    alpha = profile["pressure"]["alpha_default"] if alpha is None else alpha

    gdos_blocked = mark_gdos_blocked(stands, gdos_gdf)
    stands["gdos_blocked"] = gdos_blocked
    stands["mask_full"] = stands["mask"] & ~gdos_blocked

    parking = osm_features.get("parking")
    roads = osm_features.get("roads")
    places = osm_features.get("places")
    centroids = stands.geometry.centroid

    d_parks = [compute_d_park(c, parking, roads, profile["pressure"]["euclid_factor"]) for c in centroids]
    demands = [compute_demand(c, places, profile["pressure"]["demand_decay_km"]) for c in centroids]
    demand_max = max([d for d in demands if d is not None], default=0.0)

    pressures = [
        compute_pressure(dp, dm, demand_max, profile) for dp, dm in zip(d_parks, demands)
    ]

    stands["d_park_m"] = d_parks
    stands["demand"] = demands
    stands["demand_norm"] = [0.0 if demand_max == 0 else d / demand_max for d in demands]
    stands["P"] = pressures
    stands["pressure_factor"] = [1.0 - alpha * p for p in pressures]

    stands["R_final"] = [
        compute_ranking(mask, h, f_loc, p=p, alpha=alpha)
        for mask, h, f_loc, p in zip(stands["mask_full"], stands["H"], stands["F_loc"], stands["P"])
    ]

    stands["periodic_ban_checked"] = False
    stands["periodic_ban_active"] = False
    if top_n_for_ban_check > 0 and len(stands):
        # centroids already carries stands.crs (centroid preserves it); do not
        # call set_crs on it -- set_crs raises on a GeoSeries whose crs is
        # already set unless allow_override=True. Reproject directly instead.
        centroids_4326 = centroids.to_crs("EPSG:4326")
        top_idx = stands.sort_values("R_final", ascending=False).head(top_n_for_ban_check).index
        for idx in top_idx:
            lon, lat = centroids_4326.loc[idx].x, centroids_4326.loc[idx].y
            banned = zakaz_checker(lat, lon)
            stands.loc[idx, "periodic_ban_checked"] = True
            stands.loc[idx, "periodic_ban_active"] = bool(banned)
            if banned:
                stands.loc[idx, "R_final"] = 0.0

    confidences, reasons_list = [], []
    for _, row in stands.iterrows():
        cls, reasons = compute_confidence(row, profile)
        confidences.append(cls)
        reasons_list.append(reasons)
    stands["confidence"] = confidences
    stands["confidence_reasons"] = reasons_list

    passing = stands[stands["mask_full"]]
    area_medians = {}
    for col in _EXPLANATION_FACTORS:
        key = _FACTOR_KEY_MAP[col]
        values = passing[col].dropna()
        values = values[values > 0]
        if len(values):
            area_medians[key] = float(values.median())
    pf_values = passing["pressure_factor"].dropna()
    pf_values = pf_values[pf_values > 0]
    if len(pf_values):
        area_medians["pressure_factor"] = float(pf_values.median())

    explanations = []
    for _, row in stands.iterrows():
        values = {_FACTOR_KEY_MAP[col]: row[col] for col in _EXPLANATION_FACTORS}
        values["pressure_factor"] = row["pressure_factor"]
        contributions = compute_log_contributions(values, area_medians)
        meta = {"species_cd": row.get("species_cd"), "site_type": row.get("site_type"),
                 "age": row.get("spec_age"), "P": row.get("P", 0.0)}
        explanations.append(generate_explanation(contributions, values, meta, profile))
    stands["explanation"] = explanations

    return stands
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mvp.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/mvp.py tests/test_mvp.py
git commit -m "feat: MVP enrichment orchestration (legal mask, pressure, confidence, explanations)"
```

---

### Task 11: export (`scores_{date}.json` + stand-geometry GeoParquet)

**Files:**
- Create: `pipeline/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `enrich_with_mvp_layers`'s output shape (Task 10).
- Produces: `build_score_record(row: dict, day: str) -> dict`
- Produces: `write_scores_json(stands: geopandas.GeoDataFrame, day: str, out_path) -> pathlib.Path`
- Produces: `export_stand_geometries(stands: geopandas.GeoDataFrame, out_path) -> pathlib.Path`
- Consumed by: Task 12 (`notebooks/02_mvp.py`).

- [ ] **Step 1: Write the failing tests**

`tests/test_export.py`:
```python
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline.export import build_score_record, write_scores_json, export_stand_geometries


def _enriched_stands():
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "H": [0.9, 0.5], "F": [0.6, 0.4], "F_loc": [0.6, 0.4],
        "P": [0.1, 0.2], "R_final": [48.6, 16.0],
        "mask_full": [True, False],
        "confidence": ["SREDNIA", "NISKA"],
        "confidence_reasons": [["a", "b"], ["c"]],
        "explanation": [[{"factor": "host", "contribution": 0.1, "text": "..."}], []],
    }, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs="EPSG:2180")


def test_build_score_record_shape_matches_architecture_schema():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["stand_id"] == "A"
    assert record["day"] == "2026-09-23"
    for key in ["H", "F", "F_loc", "P", "R", "mask", "confidence", "confidence_reasons", "explanation"]:
        assert key in record
    assert record["R"] == 48.6
    assert record["mask"] is True


def test_write_scores_json_writes_one_record_per_stand(tmp_path):
    out_path = write_scores_json(_enriched_stands(), day="2026-09-23", out_path=tmp_path / "scores_2026-09-23.json")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert {r["stand_id"] for r in data} == {"A", "B"}


def test_export_stand_geometries_round_trips(tmp_path):
    out_path = export_stand_geometries(_enriched_stands(), tmp_path / "stands.parquet")
    assert out_path.exists()
    reloaded = gpd.read_parquet(out_path)
    assert len(reloaded) == 2
    assert "stand_id" in reloaded.columns
    assert "geometry" in reloaded.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.export'`

- [ ] **Step 3: Implement**

`pipeline/export.py`:
```python
import json
import pathlib

import geopandas as gpd

SCORE_FIELDS = ["stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation"]


def build_score_record(row, day: str) -> dict:
    """Matches the architecture diagram's scores_YYYY-MM-DD.json shape (spec
    §6.1: "id -> H, F, P, R, conf, wyjaśnienie") and the score_daily table
    columns (spec §6.2)."""
    record = {field: row[field] for field in SCORE_FIELDS}
    record["day"] = day
    record["R"] = float(row["R_final"])
    record["mask"] = bool(row["mask_full"])
    return record


def write_scores_json(stands: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [build_score_record(row, day) for _, row in stands.iterrows()]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def export_stand_geometries(stands: gpd.GeoDataFrame, out_path) -> pathlib.Path:
    """Minimal id+geometry export -- the input the eventual tippecanoe/PMTiles
    packaging step (spec §9 step 11/12, out of scope for this plan, see
    Global Constraints) will consume once the frontend exists to read it."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stands[["stand_id", "geometry"]].to_parquet(out_path)
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/export.py tests/test_export.py
git commit -m "feat: scores_{date}.json and stand-geometry export"
```

---

### Task 12: `notebooks/02_mvp.py` — real wiring, manual verification, re-validation

**Files:**
- Create: `notebooks/02_mvp.py`

**Interfaces:**
- Consumes: `run_poc` (Faza 1 `pipeline.orchestrate`, extended in Task 2), `fetch_protected_areas` (Task 4), `check_periodic_ban` (Task 5), `fetch_osm_features` (Task 6), `enrich_with_mvp_layers` (Task 10), `write_scores_json`/`export_stand_geometries` (Task 11), `rank_known_points`/`load_known_points` (Faza 1 `pipeline.validate`).
- Produces: `notebooks/output/scores_<today>.json`, `notebooks/output/stands_mvp.parquet`, console diagnostics, a re-run of the known-points qualitative validation against `R_final`.

- [ ] **Step 1: Write the script**

`notebooks/02_mvp.py`:
```python
"""Faza 2 MVP backend: legal mask (GDOŚ + zakazy wstępu), presja (OSM),
confidence, explanations, export -- built on top of Faza 1's run_poc for the
same Kieleczka tile."""
import functools
import pathlib
from datetime import date

import geopandas as gpd
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl, save_bdl_tile
from pipeline.confidence import compute_confidence  # noqa: F401 (re-exported for notebook debugging)
from pipeline.export import write_scores_json, export_stand_geometries
from pipeline.gdos import fetch_protected_areas
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.orchestrate import run_poc
from pipeline.osm import fetch_osm_features
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw,
    _default_open_meteo_call, _default_climatology_call,
)
from pipeline.zakazy import check_periodic_ban

LAT, LON = 50.526944, 18.605000
LAYER = "BDL:RDLP_Katowice_wydzielenia"


def _rate_limited(default_call, *args, max_attempts=6, backoff_s=65, pace_s=2.0):
    import time
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return default_call(*args)
        except OpenMeteoRequestsError as exc:
            if "limit" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def _weather_call_api(lat, lon, past_days):
    return _rate_limited(_default_open_meteo_call, lat, lon, past_days)


def _climatology_call_api(lat, lon, start_year, end_year):
    return _rate_limited(_default_climatology_call, lat, lon, start_year, end_year)


profile = load_profile("profiles/boletus_edulis.yaml")
bbox = tile_bbox_2180(LAT, LON, size_km=10.0)

CACHE_DIR = pathlib.Path("cache")
TILE_ID = f"E{int(bbox[1])}N{int(bbox[0])}"
_tile_path = CACHE_DIR / f"{TILE_ID}.parquet"


def _cached_bdl_fetcher(layer, bbox_2180):
    if _tile_path.exists():
        print(f"BDL tile cache hit: {_tile_path}")
        return gpd.read_parquet(_tile_path)
    print(f"BDL tile cache miss, fetching from WFS -> {_tile_path}")
    gdf = fetch_bdl(layer, bbox_2180)
    save_bdl_tile(gdf, TILE_ID, CACHE_DIR)
    return gdf


scored = run_poc(
    layer=LAYER,
    bbox_2180=bbox,
    profile=profile,
    bdl_fetcher=_cached_bdl_fetcher,
    weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api),
    climatology_fetcher=functools.partial(fetch_climatology_raw, call_api=_climatology_call_api),
)
print(f"run_poc: {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing structural mask")

print("Fetching GDOŚ protected areas...")
gdos_gdf = fetch_protected_areas(bbox)
print(f"  {len(gdos_gdf)} protected-area features in tile")

print("Fetching OSM parking/roads/places (Overpass)...")
osm_features = fetch_osm_features(bbox, profile)
for name, gdf in osm_features.items():
    print(f"  {name}: {len(gdf)}")

print("Enriching with legal mask + presja + confidence + explanations...")
enriched = enrich_with_mvp_layers(
    scored, profile, gdos_gdf, osm_features,
    zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
)

out_dir = pathlib.Path("notebooks/output")
today = date.today().isoformat()
scores_path = write_scores_json(enriched, day=today, out_path=out_dir / f"scores_{today}.json")
stands_path = export_stand_geometries(enriched, out_dir / "stands_mvp.parquet")
print(f"Wrote {scores_path} and {stands_path}")

passing_full = enriched[enriched["mask_full"]]
print(
    f"mask_full passing: {len(passing_full)} / {len(enriched)}; "
    f"GDOŚ-blocked: {int(enriched['gdos_blocked'].sum())}; "
    f"periodic-ban checked: {int(enriched['periodic_ban_checked'].sum())}, "
    f"active bans found: {int(enriched['periodic_ban_active'].sum())}"
)
if len(passing_full):
    print(
        f"R_final (mask_full-passing): min {passing_full['R_final'].min():.1f} / "
        f"median {passing_full['R_final'].median():.1f} / max {passing_full['R_final'].max():.1f}"
    )

from pipeline.validate import rank_known_points, load_known_points

known_points_path = pathlib.Path("notebooks/known_points.yaml")
if known_points_path.exists():
    known_points = load_known_points(str(known_points_path))
    # rank_known_points (Faza 1, pipeline/validate.py) reads a column named
    # "R" -- alias R_final onto it for this re-validation run without
    # touching the Faza 1 module or its own tests.
    revalidation_frame = enriched.rename(columns={"R": "R_faza1", "R_final": "R"})
    validation = rank_known_points(revalidation_frame, known_points)
    print("Re-validation against R_final (legal mask + presja applied):")
    print(validation.to_string(index=False))
    good = validation[validation["label"] == "good"]
    if len(good) and good["rank_pct"].mean() < 70:
        print(
            "UWAGA: znane dobre miejsca średnio poniżej 70. percentyla po dodaniu "
            "maski prawnej i presji - sprawdź czy GDOŚ/zakazy wstępu/presja nie "
            "przycinają ich nadmiernie zanim pójdziesz dalej."
        )
else:
    print(f"Brak {known_points_path} - patrz notebooks/known_points.example.yaml (Faza 1).")
```

- [ ] **Step 2: Manual end-to-end run against the real APIs**

```bash
uv run python notebooks/02_mvp.py
```
Expected: no exceptions; prints GDOŚ/OSM feature counts, `mask_full` vs structural-mask counts, an `R_final` summary, and (if `notebooks/known_points.yaml` exists from Faza 1) the re-validation table. `notebooks/output/scores_<today>.json` and `notebooks/output/stands_mvp.parquet` are created.

- [ ] **Step 3: Spot-check one `scores_<today>.json` record by hand**

```bash
uv run python -c "
import json, pathlib
from datetime import date
records = json.loads(pathlib.Path(f'notebooks/output/scores_{date.today().isoformat()}.json').read_text(encoding='utf-8'))
top = sorted(records, key=lambda r: r['R'], reverse=True)[0]
print(json.dumps(top, ensure_ascii=False, indent=2))
"
```
Expected: a record with populated `H`, `F`, `F_loc`, `P`, `R`, `mask`, `confidence`, `confidence_reasons`, and a non-empty `explanation` list whose sentences are plausible given the other fields (e.g. a high-`R` stand's explanation names its host/site as positives).

- [ ] **Step 4: Run the full test suite one more time**

Run: `uv run pytest -v`
Expected: PASS (all Faza 1 and Faza 2 tests)

- [ ] **Step 5: Commit**

```bash
git add notebooks/02_mvp.py
git commit -m "feat: Faza 2 MVP backend orchestration script (mask, presja, confidence, export)"
```
