# Borowik GIS — Accessibility: entrances + network routing for top-N Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement spec §13 priority 3: replace the euclidean×1.3 distance-to-nearest-parking-or-paved-road estimate with (a) detected candidate forest entrances (road/track crossings of the forest boundary), each flagged **confirmed** (near a known OSM parking point) or **potential** (not), and (b) real road/track-network routing distance to the nearest entrance for the top 20–30 candidate stands by ranking — replacing the "silent straight-line guess" the current MVP uses for everyone, spec §5.5.2.

**Architecture:** Three new small, pure/testable modules following this codebase's established shape (no I/O beyond what's injected): `pipeline/entrances.py` (forest boundary + entrance detection/classification), `pipeline/routing.py` (a `networkx` graph built from OSM road/track linework, shortest-path distance, nearest-entrance lookup). `pipeline/osm.py` changes what `fetch_osm_features` fetches — full LineString geometry for the *broader* routing network (paved roads **and** tracks/paths) instead of the narrower paved-only center-point set it fetches today — since routing a walking path from an entrance into forest interior needs the unpaved track network, while the *existing* euclidean estimate deliberately stays paved-only (unchanged reasoning, just relocated). `pipeline/mvp.py::enrich_with_mvp_layers` gains new, defaulted (opt-in) parameters that refine `d_park_m`/`P`/`R_final` for only the top-N stands by the already-computed euclidean ranking — mirroring the exact pattern `top_n_for_ban_check` already uses, so every existing call site and test keeps passing unmodified.

**Tech Stack:** Python 3.12, `uv`, GeoPandas + Shapely 2, pytest. **New dependency: `networkx`** (pure-Python graph library, no C-extension build chain, added via `uv add networkx`) for the routing graph and shortest-path search.

**Spec:** `docs/projekt-borowik.md` §5.5.2 ("Szacowana popularność rejonu"), §13 priority 3.

## Global Constraints

- Repo root: this worktree (`C:\Users\<uzytkownik>\Documents\Grzyby\.claude\worktrees\borowik-faza2-mvp-backend`). Python ≥3.12 via `uv`.
- **`notebooks/02_mvp.py` is not modified by this plan** — same reasoning as the `prepare_trip` CLI plan: it already works and stays the fixed-tile manual/debug script it documents itself to be. Only `pipeline/prepare_trip.py` (the canonical entry point going forward) is wired to the new accessibility features.
- **Overpass fetch, verified live 2026-09-24**: `out geom;` (replacing the current `out center tags;`) returns, for a matched **way**, `{"type":"way","id":...,"bounds":{...},"nodes":[...],"geometry":[{"lat":...,"lon":...}, ...],"tags":{...}}` — a full ordered vertex list, confirmed against real `highway=residential`/`highway=track` ways. For a matched **node**, Overpass's `geom`/`center` output modifiers only add detail for ways/relations — a node is always printed with its own top-level `lat`/`lon`, which is how `pipeline.osm._element_point`'s existing node handling already works today and needs no change.
- **`profile["osm"]["routing_highway_types"]`** (new) is the union fetched from Overpass: the existing paved list (`road_highway_types`: trunk/primary/secondary/tertiary/unclassified/residential) **plus** `track`, `path`, `footway`, `bridleway` — the unpaved network a walking route from a car-accessible entrance into forest interior actually needs. **`profile["osm"]["road_highway_types"]`** (existing, unchanged) keeps its original, narrower, paved-only role: `pipeline.mvp.enrich_with_mvp_layers` filters the fetched road set down to it before computing the existing euclidean `d_park` estimate, so that estimate's behavior (and the reason `track` was excluded from it — see the profile YAML's own existing comment: including it made `d_park` nearly constant across a tile) is **unchanged** for every stand not in the routing-refined top-N.
- **Forest boundary** = `unary_union` of stand geometries with `area_type == "D-STAN"` in the tile — **not** `mask_full`-passing only. A young plantation or a protected reserve is still physically forest; excluding them from the boundary would fabricate fake "entrances" at their inner edges where they border an included stand.
- **Entrance points** = geometric intersections of the routing-network road/track LineStrings with the forest boundary polygon's exterior line (`boundary.boundary`). Multiple ways crossing the boundary at nearly the same spot are **not deduplicated** in this plan — an accepted, documented simplification; a slightly redundant entrance list is not a correctness bug.
- **`confirmed`** = within `profile["entrances"]["confirmed_tolerance_m"]` (new, default 50.0 m — `[E]`, plan decision) of a known OSM parking point (`osm_features["parking"]`, unchanged fetch). **`potential`** = everything else. This is the spec's own two-state model (§5.5.2): no third "verified via BDL turystyczny layer" state — that data source is still unconnected (spec §3.7), out of scope here.
- **Routing graph nodes are LineString vertices**, rounded to 3 decimal places (millimetre precision in EPSG:2180 metres) so that ways sharing an OSM node produce the identical graph-node key. **A query point (stand centroid or entrance) snaps to its nearest existing graph node**, not the nearest point on an edge — spec §5.5.2's own "najprostsze rozwiązanie" principle; the snap distance is added to the path length so short snaps don't distort short routes.
- **Only the top `profile["entrances"]["top_n_for_routing"]` stands** (new, default 25 — `[E]`, matching spec §13 priority 3's "top 20–30 wydzieleń") **by the already-computed euclidean `R_final`** get network-routed distance; everyone else keeps the euclidean×1.3 estimate. A new `distance_method` column (`"network"`/`"euclidean"`) and the existing/new `entrance_status` column (`"confirmed"`/`"potential"`/`"not_evaluated"`) make this visible in data and export — spec §13 priority 3's own completion criterion.
- **`enrich_with_mvp_layers` gains `roads_routing_gdf=None, entrances_gdf=None, top_n_for_routing=0`** as new, defaulted parameters — every existing call site and test (which omit them) gets `distance_method="euclidean"`/`entrance_status="not_evaluated"` on every row and **identical** `R_final`/`P`/`pressure_factor` values to today; the routing refinement block is a complete no-op when these are omitted.
- **Out of scope for this plan** (per spec §13's own priority split): barriers (rivers without bridges, fences — priority 10), trails/tourist infrastructure as a popularity signal and buildings/miejscowości directly adjacent to the forest edge (both part of §5.5.2's broader factor list but not named in priority 3's own three-item description), deduplicating near-coincident entrance points, and any change to `notebooks/02_mvp.py`.

## Review Focus

- **A tile with no routing-network ways at all** (data-sparse rural tile): `build_road_graph` must return an empty graph, not raise; `network_distance`/`nearest_entrance_distance` must return `(None, None)` cleanly, and the top-N refinement loop in `enrich_with_mvp_layers` must leave those stands' euclidean values untouched, not crash or zero them out. Covered in Task 4 and Task 5.
- **A tile with no entrance points found at all** (forest boundary never crossed by any fetched way): same fallback — routing refinement is a no-op for every top-N stand. Covered in Task 5.
- **Two disconnected road-graph components** (a real gap in OSM track coverage): a stand's nearest node in one component and every entrance's nearest node in another must produce `network_distance() is None` (via `networkx.NetworkXNoPath`), triggering the per-stand euclidean fallback rather than a stale or wrong distance. Covered in Task 4.
- **The confirmed/potential tolerance boundary**: an entrance exactly at `confirmed_tolerance_m` from a parking point, and one just beyond it, must land on opposite sides of the classification — pins the `<=` vs `<` choice explicitly rather than leaving it to accident. Covered in Task 3.
- **`enrich_with_mvp_layers` called exactly as every pre-existing test already calls it** (no routing arguments) must produce identical `R_final`/`P`/`pressure_factor` to before this plan — the regression guard that the whole feature is opt-in. Covered in Task 5 (new test) and by every pre-existing `tests/test_mvp.py` test continuing to pass unmodified.

---

## File Structure

```
pipeline/
  osm.py              # MODIFY: routing_highway_types query, full LineString way geometry via `out geom`
  entrances.py          # NEW: compute_forest_boundary, find_entrance_points, classify_entrances
  routing.py              # NEW: build_road_graph, network_distance, nearest_entrance_distance
  mvp.py                    # MODIFY: enrich_with_mvp_layers gains optional top-N routing refinement
  export.py                  # MODIFY: distance_method/entrance_status added to SCORE_FIELDS
  prepare_trip.py              # MODIFY: wire entrance detection + routing refinement into run_trip_preparation
profiles/
  boletus_edulis.yaml            # MODIFY: + routing_highway_types, + entrances: section
pyproject.toml                    # MODIFY: + networkx dependency
tests/
  test_osm.py                      # MODIFY: routing_highway_types query test, way LineString geometry test
  test_entrances.py                  # NEW
  test_routing.py                      # NEW
  test_mvp.py                            # MODIFY: routing-refinement tests
  test_export.py                           # MODIFY: distance_method/entrance_status test
```

---

### Task 1: Fetch full road/track/path linework from Overpass

**Files:**
- Modify: `profiles/boletus_edulis.yaml`
- Modify: `pipeline/osm.py`
- Modify: `tests/test_osm.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `fetch_osm_features(bbox_2180, profile, call_api=None)`'s `"roads"` GeoDataFrame now carries **LineString** geometry (was Point) and includes the broader `routing_highway_types` set (was `road_highway_types` only). Used by Task 2 (`find_entrance_points`), Task 4 (`build_road_graph`), and Task 5/7 (the paved-only filtering that preserves the existing euclidean behavior).

- [ ] **Step 1: Add `routing_highway_types` to the profile**

In `profiles/boletus_edulis.yaml`, in the existing `osm:` section, add a new key right after `road_highway_types`:

```yaml
  routing_highway_types: ["trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track", "path", "footway", "bridleway"]
```

- [ ] **Step 2: Update the failing/changed tests in `tests/test_osm.py`**

Replace the existing `ELEMENTS` fixture and the two tests that read its way element, and rewrite `test_build_overpass_query_excludes_unpaved_tracks`:

```python
def test_build_overpass_query_includes_unpaved_tracks_for_routing():
    # Was "excludes unpaved tracks" -- that exclusion is real and still
    # applies to the euclidean d_park estimate (spec §4.5, "publicznej
    # drogi utwardzonej"), but it now happens by filtering
    # pipeline.mvp.enrich_with_mvp_layers's paved-only subset (Task 5), not
    # by leaving tracks out of the Overpass query entirely -- routing a
    # walking path from an entrance into forest interior needs them.
    q = build_overpass_query(BBOX_4326, PROFILE)
    assert "track" in q
    assert "path" in q


ELEMENTS = [
    {"type": "node", "id": 1, "lat": 50.51, "lon": 18.60, "tags": {"amenity": "parking"}},
    {
        "type": "way", "id": 2, "tags": {"highway": "track"},
        "geometry": [{"lat": 50.520, "lon": 18.610}, {"lat": 50.521, "lon": 18.611}, {"lat": 50.522, "lon": 18.612}],
    },
    {"type": "node", "id": 3, "lat": 50.53, "lon": 18.62, "tags": {"place": "village", "name": "Kieleczka", "population": "450"}},
    {"type": "node", "id": 4, "lat": 50.54, "lon": 18.63, "tags": {"place": "hamlet", "name": "Bez ludzi"}},  # no population tag
    {"type": "way", "id": 5, "tags": {"highway": "residential"}, "geometry": [{"lat": 50.50, "lon": 18.55}]},  # degenerate: 1 point
]


def test_parse_osm_elements_splits_into_parking_roads_places():
    frames = parse_osm_elements(ELEMENTS)
    assert set(frames) == {"parking", "roads", "places"}
    assert len(frames["parking"]) == 1
    assert len(frames["roads"]) == 1  # element 5 (1-point geometry) is dropped, not a valid line
    assert len(frames["places"]) == 2


def test_parse_osm_elements_coerces_missing_population_to_zero():
    frames = parse_osm_elements(ELEMENTS)
    pop_by_name = dict(zip(frames["places"]["name"], frames["places"]["population"]))
    assert pop_by_name["Kieleczka"] == pytest.approx(450.0)
    assert pop_by_name["Bez ludzi"] == pytest.approx(0.0)


def test_parse_osm_elements_builds_way_linestring_geometry():
    frames = parse_osm_elements(ELEMENTS)
    road_geom = frames["roads"].geometry.iloc[0]
    assert road_geom.geom_type == "LineString"
    assert list(road_geom.coords) == [(18.610, 50.520), (18.611, 50.521), (18.612, 50.522)]


def test_parse_osm_elements_skips_way_with_fewer_than_two_geometry_points():
    frames = parse_osm_elements(ELEMENTS)
    # element 5's highway=residential way has only 1 geometry point --
    # can't form a LineString, so it must be dropped rather than crash.
    assert len(frames["roads"]) == 1
```

Leave `test_build_overpass_query_includes_bbox_and_configured_filters` and `test_fetch_osm_features_uses_injected_call_api_and_reprojects_to_2180` as they are (both still pass unmodified against the new `ELEMENTS`/query shape).

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_osm.py -v`
Expected: `test_build_overpass_query_includes_unpaved_tracks_for_routing` FAILS (`"track" in q` is currently False, since the query still uses `road_highway_types`); the three `parse_osm_elements` tests FAIL or produce wrong results (way element 2 currently has no `"center"` key so today's `_element_point` returns `None` and the row is dropped, not built as a road — `len(frames["roads"])` would be `0`, not `1`, and `test_parse_osm_elements_builds_way_linestring_geometry` fails with `IndexError` on the empty roads frame).

- [ ] **Step 4: Update `build_overpass_query` and `parse_osm_elements`**

In `pipeline/osm.py`, change the highway source and the `out` statement:

```python
def build_overpass_query(bbox_4326: tuple, profile: dict) -> str:
    south, west, north, east = bbox_4326
    bbox_str = f"{south},{west},{north},{east}"
    cfg = profile["osm"]
    highway_re = "|".join(cfg["routing_highway_types"])
    place_re = "|".join(cfg["place_types"])
    return (
        f'[out:json][timeout:25];'
        f'('
        f'node["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["highway"~"^({highway_re})$"]({bbox_str});'
        f'node["place"~"^({place_re})$"]({bbox_str});'
        f');'
        f'out geom;'
    )
```

Replace `_element_point` with a representative-point helper plus a new linework helper, and update `parse_osm_elements`:

```python
def _element_representative_point(element: dict):
    """A single representative Point for a node or way. Nodes use their own
    lat/lon; ways use the centroid of their own linework -- Overpass
    `out geom;` (replacing `out center tags;`, Task 1 of the accessibility
    plan) no longer returns a `center` field."""
    if "lat" in element and "lon" in element:
        return Point(element["lon"], element["lat"])
    geometry = element.get("geometry")
    if not geometry:
        return None
    coords = [(pt["lon"], pt["lat"]) for pt in geometry]
    if len(coords) == 1:
        return Point(coords[0])
    return LineString(coords).centroid


def _way_linestring(element: dict):
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 2:
        return None
    return LineString([(pt["lon"], pt["lat"]) for pt in geometry])


def parse_osm_elements(elements: list[dict]) -> dict:
    parking_rows, road_rows, place_rows = [], [], []
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("amenity") == "parking":
            point = _element_representative_point(el)
            if point is not None:
                parking_rows.append({"osm_id": el["id"], "geometry": point})
        elif "highway" in tags:
            line = _way_linestring(el)
            if line is not None:
                road_rows.append({"osm_id": el["id"], "highway": tags["highway"], "geometry": line})
        elif "place" in tags:
            point = _element_representative_point(el)
            if point is None:
                continue
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
                  else gpd.GeoDataFrame({"osm_id": [], "highway": []}, geometry=[], crs="EPSG:4326"),
        "places": gpd.GeoDataFrame(place_rows, geometry="geometry", crs="EPSG:4326") if place_rows
                   else gpd.GeoDataFrame({"osm_id": [], "population": []}, geometry=[], crs="EPSG:4326"),
    }
```

Add `LineString` to the existing `from shapely.geometry import Point` import line, making it `from shapely.geometry import Point, LineString`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_osm.py -v`
Expected: 8 passed (5 pre-existing, unmodified or rewritten in Step 2, + 3 new).

- [ ] **Step 6: Run the full test suite to check nothing else broke**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass. `pipeline.mvp.enrich_with_mvp_layers` still calls `compute_d_park(c, parking, roads, ...)` with `roads` now carrying LineString geometry instead of Point — `geopandas.GeoSeries.distance()` is well-defined for any geometry type against a Point, so this is not expected to break any existing `tests/test_mvp.py`/`tests/test_pressure.py` assertion (those use their own synthetic Point/box fixtures, not `pipeline.osm`'s output, so they are unaffected either way).

- [ ] **Step 7: Commit**

```bash
git add profiles/boletus_edulis.yaml pipeline/osm.py tests/test_osm.py
git commit -m "feat: fetch full road/track/path linework instead of way center points"
```

---

### Task 2: Forest boundary + candidate entrance detection

**Files:**
- Create: `pipeline/entrances.py`
- Create: `tests/test_entrances.py`

**Interfaces:**
- Consumes: a `stands` GeoDataFrame with `area_type`/`geometry` columns (exactly `run_poc`'s output shape); a `roads` GeoDataFrame with LineString geometry (Task 1's output shape).
- Produces: `compute_forest_boundary(stands) -> BaseGeometry | None` and `find_entrance_points(forest_boundary, roads_gdf) -> gpd.GeoDataFrame` (columns `geometry`, `highway`). Used by Task 3 and Task 7.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_entrances.py`:

```python
import geopandas as gpd
import pytest
from shapely.geometry import box, LineString

from pipeline.entrances import compute_forest_boundary, find_entrance_points


def _stand_row(stand_id, x, area_type="D-STAN"):
    return {"stand_id": stand_id, "area_type": area_type, "geometry": box(x, 486000, x + 1000, 487000)}


def test_compute_forest_boundary_unions_d_stan_stands_only():
    stands = gpd.GeoDataFrame([
        _stand_row("A", 380000, "D-STAN"),
        _stand_row("B", 381000, "D-STAN"),   # adjacent -> merges with A
        _stand_row("C", 390000, "LAKA"),      # non-forest, excluded
    ], crs="EPSG:2180")
    boundary = compute_forest_boundary(stands)
    assert boundary.area == pytest.approx(2 * 1000 * 1000)  # A+B only, merged


def test_compute_forest_boundary_returns_none_when_no_forest_stands():
    stands = gpd.GeoDataFrame([_stand_row("C", 390000, "LAKA")], crs="EPSG:2180")
    assert compute_forest_boundary(stands) is None


def test_find_entrance_points_detects_crossing_road():
    forest = box(380000, 486000, 381000, 487000)
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(379500, 486500), (380500, 486500)])],  # crosses west edge at x=380000
        crs="EPSG:2180",
    )
    entrances = find_entrance_points(forest, roads)
    assert len(entrances) == 1
    pt = entrances.iloc[0].geometry
    assert pt.x == pytest.approx(380000)
    assert pt.y == pytest.approx(486500)


def test_find_entrance_points_ignores_road_entirely_outside():
    forest = box(380000, 486000, 381000, 487000)
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(390000, 486500), (391000, 486500)])],  # far away, no crossing
        crs="EPSG:2180",
    )
    entrances = find_entrance_points(forest, roads)
    assert len(entrances) == 0


def test_find_entrance_points_returns_empty_for_none_boundary():
    roads = gpd.GeoDataFrame({"highway": ["track"]}, geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:2180")
    entrances = find_entrance_points(None, roads)
    assert len(entrances) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entrances.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'pipeline.entrances'`.

- [ ] **Step 3: Create `pipeline/entrances.py`**

```python
import geopandas as gpd
from shapely.ops import unary_union


def compute_forest_boundary(stands: gpd.GeoDataFrame):
    """Union of every D-STAN (actual forest stand) geometry in the tile --
    not just mask_full-passing ones, so a young plantation or a reserve
    doesn't fabricate a fake entrance at its own inner edge (spec §5.5.2)."""
    forest_stands = stands[stands["area_type"] == "D-STAN"]
    if len(forest_stands) == 0:
        return None
    return unary_union(list(forest_stands.geometry))


def _extract_points(geom) -> list:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type in ("LineString", "MultiLineString"):
        # A road running along the boundary rather than crossing it -- a
        # rare edge case; approximated by its endpoints.
        line = geom if geom.geom_type == "LineString" else unary_union(geom)
        return _extract_points(line.boundary)
    if geom.geom_type == "GeometryCollection":
        points = []
        for part in geom.geoms:
            points.extend(_extract_points(part))
        return points
    return []


def find_entrance_points(forest_boundary, roads_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Points where a road/track/path LineString crosses the forest
    boundary -- candidate entrances to the forest complex (spec §5.5.2).
    Near-duplicate entrances from multiple ways crossing at almost the same
    spot are not merged (accepted simplification, see plan Global
    Constraints)."""
    empty = gpd.GeoDataFrame({"highway": []}, geometry=[], crs=roads_gdf.crs)
    if forest_boundary is None or forest_boundary.is_empty or len(roads_gdf) == 0:
        return empty
    boundary_line = forest_boundary.boundary
    rows = []
    for _, row in roads_gdf.iterrows():
        for pt in _extract_points(row.geometry.intersection(boundary_line)):
            rows.append({"geometry": pt, "highway": row.get("highway")})
    if not rows:
        return empty
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=roads_gdf.crs)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entrances.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/entrances.py tests/test_entrances.py
git commit -m "feat: detect candidate forest entrances from road/boundary crossings"
```

---

### Task 3: Confirmed vs. potential entrance classification

**Files:**
- Modify: `pipeline/entrances.py`
- Modify: `tests/test_entrances.py`

**Interfaces:**
- Consumes: `find_entrance_points`'s output shape (Task 2); a `parking_gdf` (Point geometry, `pipeline.osm.fetch_osm_features`'s `"parking"` shape).
- Produces: `classify_entrances(entrances_gdf, parking_gdf, confirmed_tolerance_m) -> gpd.GeoDataFrame` (adds a `status` column, `"confirmed"`/`"potential"`). Used by Task 5 (via Task 7's wiring) and directly by `pipeline.routing.nearest_entrance_distance` (Task 4).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_entrances.py`:

```python
from shapely.geometry import Point

from pipeline.entrances import classify_entrances


def test_classify_entrances_marks_confirmed_near_parking():
    entrances = gpd.GeoDataFrame(geometry=[Point(380000, 486500)], crs="EPSG:2180")
    parking = gpd.GeoDataFrame(geometry=[Point(380020, 486500)], crs="EPSG:2180")  # 20 m away
    result = classify_entrances(entrances, parking, confirmed_tolerance_m=50.0)
    assert result.iloc[0]["status"] == "confirmed"


def test_classify_entrances_marks_potential_when_far_from_parking():
    entrances = gpd.GeoDataFrame(geometry=[Point(380000, 486500)], crs="EPSG:2180")
    parking = gpd.GeoDataFrame(geometry=[Point(380100, 486500)], crs="EPSG:2180")  # 100 m away
    result = classify_entrances(entrances, parking, confirmed_tolerance_m=50.0)
    assert result.iloc[0]["status"] == "potential"


def test_classify_entrances_marks_potential_when_no_parking_at_all():
    entrances = gpd.GeoDataFrame(geometry=[Point(380000, 486500)], crs="EPSG:2180")
    empty_parking = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    result = classify_entrances(entrances, empty_parking, confirmed_tolerance_m=50.0)
    assert result.iloc[0]["status"] == "potential"


def test_classify_entrances_boundary_exactly_at_tolerance_is_confirmed():
    entrances = gpd.GeoDataFrame(geometry=[Point(380000, 486500)], crs="EPSG:2180")
    parking = gpd.GeoDataFrame(geometry=[Point(380050, 486500)], crs="EPSG:2180")  # exactly 50 m
    result = classify_entrances(entrances, parking, confirmed_tolerance_m=50.0)
    assert result.iloc[0]["status"] == "confirmed"  # inclusive boundary


def test_classify_entrances_boundary_just_beyond_tolerance_is_potential():
    entrances = gpd.GeoDataFrame(geometry=[Point(380000, 486500)], crs="EPSG:2180")
    parking = gpd.GeoDataFrame(geometry=[Point(380050.01, 486500)], crs="EPSG:2180")  # 50.01 m
    result = classify_entrances(entrances, parking, confirmed_tolerance_m=50.0)
    assert result.iloc[0]["status"] == "potential"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entrances.py -v`
Expected: the five new tests FAIL with `ImportError: cannot import name 'classify_entrances'`.

- [ ] **Step 3: Implement `classify_entrances`**

Append to `pipeline/entrances.py`:

```python
def classify_entrances(entrances_gdf: gpd.GeoDataFrame, parking_gdf: gpd.GeoDataFrame,
                         confirmed_tolerance_m: float) -> gpd.GeoDataFrame:
    """'confirmed' if within confirmed_tolerance_m of a known OSM parking
    point, else 'potential' -- spec §5.5.2's two-state entrance model."""
    entrances_gdf = entrances_gdf.copy()
    if parking_gdf is None or len(parking_gdf) == 0:
        entrances_gdf["status"] = "potential"
        return entrances_gdf
    statuses = [
        "confirmed" if parking_gdf.distance(geom).min() <= confirmed_tolerance_m else "potential"
        for geom in entrances_gdf.geometry
    ]
    entrances_gdf["status"] = statuses
    return entrances_gdf
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entrances.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/entrances.py tests/test_entrances.py
git commit -m "feat: classify entrances as confirmed or potential"
```

---

### Task 4: Road/track routing graph + shortest-path distance

**Files:**
- Modify: `pyproject.toml`
- Create: `pipeline/routing.py`
- Create: `tests/test_routing.py`

**Interfaces:**
- Consumes: a `roads` GeoDataFrame with LineString geometry (Task 1's output shape); an `entrances_gdf` with `status`/`geometry` columns (Task 3's output shape).
- Produces: `build_road_graph(roads_gdf) -> networkx.Graph`, `network_distance(graph, point_a, point_b) -> float | None`, `nearest_entrance_distance(graph, stand_centroid, entrances_gdf) -> tuple[float | None, str | None]`. Used by Task 5.

- [ ] **Step 1: Add the `networkx` dependency**

Run: `uv add networkx`
Expected: `pyproject.toml`'s `dependencies` list gains a `"networkx>=..."` entry and `uv.lock` updates; the command exits 0.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_routing.py`:

```python
import geopandas as gpd
import networkx as nx
import pytest
from shapely.geometry import LineString, Point

from pipeline.routing import build_road_graph, network_distance, nearest_entrance_distance


def _two_segment_roads():
    return gpd.GeoDataFrame(
        {"highway": ["track", "track"]},
        geometry=[
            LineString([(380000, 486000), (380100, 486000)]),
            LineString([(380100, 486000), (380100, 486100)]),  # shares (380100, 486000)
        ],
        crs="EPSG:2180",
    )


def test_build_road_graph_connects_shared_vertices():
    graph = build_road_graph(_two_segment_roads())
    assert graph.number_of_nodes() == 3
    assert nx.has_path(graph, (380000.0, 486000.0), (380100.0, 486100.0))


def test_build_road_graph_empty_input():
    roads = gpd.GeoDataFrame({"highway": []}, geometry=[], crs="EPSG:2180")
    graph = build_road_graph(roads)
    assert graph.number_of_nodes() == 0


def test_network_distance_along_two_segments():
    graph = build_road_graph(_two_segment_roads())
    distance = network_distance(graph, Point(380000, 486000), Point(380100, 486100))
    assert distance == pytest.approx(200.0)  # 100 + 100, exact vertex match, zero snap distance


def test_network_distance_returns_none_for_disconnected_components():
    roads = gpd.GeoDataFrame(
        {"highway": ["track", "track"]},
        geometry=[
            LineString([(380000, 486000), (380100, 486000)]),
            LineString([(500000, 600000), (500100, 600000)]),  # far away, disconnected
        ],
        crs="EPSG:2180",
    )
    graph = build_road_graph(roads)
    distance = network_distance(graph, Point(380000, 486000), Point(500000, 600000))
    assert distance is None


def test_network_distance_returns_none_for_empty_graph():
    graph = nx.Graph()
    assert network_distance(graph, Point(0, 0), Point(1, 1)) is None


def test_nearest_entrance_distance_picks_the_closer_entrance_regardless_of_status():
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(380000, 486000), (380200, 486000)])],
        crs="EPSG:2180",
    )
    graph = build_road_graph(roads)
    entrances = gpd.GeoDataFrame(
        {"status": ["potential", "confirmed"]},
        geometry=[Point(380000, 486000), Point(380200, 486000)],
        crs="EPSG:2180",
    )
    distance, status = nearest_entrance_distance(graph, Point(380000, 486000), entrances)
    assert distance == pytest.approx(0.0)
    assert status == "potential"


def test_nearest_entrance_distance_none_for_empty_entrances():
    graph = nx.Graph()
    empty = gpd.GeoDataFrame({"status": []}, geometry=[], crs="EPSG:2180")
    distance, status = nearest_entrance_distance(graph, Point(0, 0), empty)
    assert distance is None
    assert status is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_routing.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'pipeline.routing'`.

- [ ] **Step 4: Create `pipeline/routing.py`**

```python
import networkx as nx
from shapely.geometry import Point


def build_road_graph(roads_gdf) -> nx.Graph:
    """Nodes = every distinct vertex coordinate across all road/track/path
    LineStrings (rounded to 3 decimals -- millimetre precision in EPSG:2180
    metres -- so ways sharing an OSM node produce the same graph-node key);
    edges = consecutive vertex pairs within a LineString, weighted by
    Euclidean segment length. Roads that share a vertex (the normal case at
    OSM way intersections) are connected."""
    graph = nx.Graph()
    for geom in roads_gdf.geometry:
        if geom is None or geom.is_empty or geom.geom_type != "LineString":
            continue
        coords = [(round(x, 3), round(y, 3)) for x, y in geom.coords]
        for a, b in zip(coords[:-1], coords[1:]):
            length = Point(a).distance(Point(b))
            graph.add_edge(a, b, weight=length)
    return graph


def _nearest_graph_node(graph: nx.Graph, point):
    if graph.number_of_nodes() == 0:
        return None
    return min(graph.nodes, key=lambda n: (n[0] - point.x) ** 2 + (n[1] - point.y) ** 2)


def network_distance(graph: nx.Graph, point_a, point_b) -> float | None:
    """Shortest-path distance along the road/track graph between the graph
    nodes nearest point_a and point_b, plus the straight-line snap distance
    from each point to its nearest node (spec §5.5.2's own "snap to nearest
    node" simplification). None if the graph is empty or the two points
    fall in disconnected components -- callers must fall back to the
    euclidean estimate in that case, not treat None as zero."""
    node_a = _nearest_graph_node(graph, point_a)
    node_b = _nearest_graph_node(graph, point_b)
    if node_a is None or node_b is None:
        return None
    try:
        path_length = nx.shortest_path_length(graph, node_a, node_b, weight="weight")
    except nx.NetworkXNoPath:
        return None
    return path_length + point_a.distance(Point(node_a)) + point_b.distance(Point(node_b))


def nearest_entrance_distance(graph: nx.Graph, stand_centroid, entrances_gdf) -> tuple:
    """(distance_m, status) for whichever entrance in entrances_gdf has the
    smallest network_distance from stand_centroid -- the nearest one
    overall, not necessarily a confirmed one; status just reports what that
    nearest entrance is (spec §5.5.2: distance is about "wygoda dojazdu",
    confirmed/potential is a separate, honestly-labelled fact). (None, None)
    if entrances_gdf is empty or nothing is reachable."""
    best = None
    for _, row in entrances_gdf.iterrows():
        distance = network_distance(graph, stand_centroid, row.geometry)
        if distance is not None and (best is None or distance < best[0]):
            best = (distance, row["status"])
    return best if best is not None else (None, None)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_routing.py -v`
Expected: 7 passed.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock pipeline/routing.py tests/test_routing.py
git commit -m "feat: road/track routing graph and shortest-path distance to nearest entrance"
```

---

### Task 5: Wire top-N network-routing refinement into `enrich_with_mvp_layers`

**Files:**
- Modify: `pipeline/mvp.py`
- Modify: `tests/test_mvp.py`

**Interfaces:**
- Consumes: `pipeline.routing.build_road_graph`/`nearest_entrance_distance` (Task 4); the `entrances_gdf` shape from Task 3.
- Produces: `enrich_with_mvp_layers` gains `roads_routing_gdf=None, entrances_gdf=None, top_n_for_routing=0` parameters and always-present `distance_method`/`entrance_status` output columns. Used by Task 6 (export) and Task 7 (CLI wiring).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mvp.py` (add `LineString` to the existing `from shapely.geometry import box, Point` import, making it `from shapely.geometry import box, Point, LineString`):

```python
def _routing_test_stands():
    # Same shape as _scored_stands() but with distinct H so R_final is
    # unambiguously ordered -- top_n_for_routing must not depend on
    # sort-tie-breaking behavior.
    return gpd.GeoDataFrame({
        "stand_id": ["HIGH", "LOW"],
        "species_cd": ["SO", "SO"], "site_type": ["BMSW", "BMSW"], "spec_age": [60, 60],
        "mask": [True, True],
        "H": [0.9, 0.5], "F": [0.6, 0.6], "F_loc": [0.6, 0.6], "R": [54.0, 30.0],
        "S_host": [1.0, 1.0], "S_site": [1.0, 1.0], "S_age": [1.0, 1.0],
        "M": [0.5, 0.5], "T": [0.8, 0.8], "K_frost": [1.0, 1.0],
    }, geometry=[box(380100, 486100, 380200, 486200), box(390100, 496100, 390200, 496200)], crs="EPSG:2180")


def test_enrich_routing_refines_only_top_n_stands_and_records_method():
    stands = _routing_test_stands()
    # HIGH's centroid is exactly (380150, 486150); this track starts there.
    roads_routing = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(380150, 486150), (380150, 486250)])],
        crs="EPSG:2180",
    )
    entrances = gpd.GeoDataFrame(
        {"status": ["confirmed"]},
        geometry=[Point(380150, 486250)],
        crs="EPSG:2180",
    )
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
        roads_routing_gdf=roads_routing, entrances_gdf=entrances, top_n_for_routing=1,
    )
    refined = result[result["stand_id"] == "HIGH"].iloc[0]
    unrefined = result[result["stand_id"] == "LOW"].iloc[0]
    assert refined["distance_method"] == "network"
    assert refined["entrance_status"] == "confirmed"
    assert refined["d_park_m"] == pytest.approx(100.0)
    assert unrefined["distance_method"] == "euclidean"
    assert unrefined["entrance_status"] == "not_evaluated"


def test_enrich_without_routing_params_keeps_existing_behavior():
    # Regression guard: every existing caller (no routing args) is
    # completely unaffected by this feature's addition.
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    assert (result["distance_method"] == "euclidean").all()
    assert (result["entrance_status"] == "not_evaluated").all()


def test_enrich_routing_with_no_reachable_entrance_falls_back_to_euclidean():
    stands = _routing_test_stands()
    disconnected_roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(500000, 600000), (500100, 600000)])],  # nowhere near either stand
        crs="EPSG:2180",
    )
    entrances = gpd.GeoDataFrame(
        {"status": ["potential"]}, geometry=[Point(500100, 600000)], crs="EPSG:2180",
    )
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
        roads_routing_gdf=disconnected_roads, entrances_gdf=entrances, top_n_for_routing=1,
    )
    refined_candidate = result[result["stand_id"] == "HIGH"].iloc[0]
    # A disconnected/unreachable entrance means nearest_entrance_distance
    # returns (None, None) -- must leave the stand on its euclidean values,
    # not crash or zero it out.
    assert refined_candidate["distance_method"] == "euclidean"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mvp.py -v`
Expected: the three new tests FAIL with `TypeError: enrich_with_mvp_layers() got an unexpected keyword argument 'roads_routing_gdf'`.

- [ ] **Step 3: Implement the routing refinement in `pipeline/mvp.py`**

Add the import (alongside the existing `pipeline.*` imports):

```python
from pipeline.routing import build_road_graph, nearest_entrance_distance
```

Change the function signature and body:

```python
def enrich_with_mvp_layers(stands: gpd.GeoDataFrame, profile: dict, gdos_gdf: gpd.GeoDataFrame,
                              osm_features: dict, zakaz_checker, alpha: float | None = None,
                              top_n_for_ban_check: int = 50,
                              roads_routing_gdf: gpd.GeoDataFrame | None = None,
                              entrances_gdf: gpd.GeoDataFrame | None = None,
                              top_n_for_routing: int = 0) -> gpd.GeoDataFrame:
    stands = stands.copy()
    alpha = profile["pressure"]["alpha_default"] if alpha is None else alpha

    gdos_blocked = mark_gdos_blocked(stands, gdos_gdf)
    stands["gdos_blocked"] = gdos_blocked
    stands["mask_full"] = stands["mask"] & ~gdos_blocked

    parking = osm_features.get("parking")
    roads = osm_features.get("roads")
    if roads is not None and "highway" in roads.columns:
        # osm_features["roads"] now carries the full routing network
        # (paved + track/path, profile["osm"]["routing_highway_types"],
        # Task 1) -- the euclidean d_park estimate below keeps its
        # original, deliberately paved-only scope (see
        # profiles/boletus_edulis.yaml's own comment on why "track" was
        # excluded: it made d_park nearly constant across a tile).
        roads = roads[roads["highway"].isin(profile["osm"]["road_highway_types"])]
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
    stands["distance_method"] = "euclidean"
    stands["entrance_status"] = "not_evaluated"

    stands["R_final"] = [
        compute_ranking(mask, h, f_loc, p=p, alpha=alpha)
        for mask, h, f_loc, p in zip(stands["mask_full"], stands["H"], stands["F_loc"], stands["P"])
    ]

    if top_n_for_routing > 0 and roads_routing_gdf is not None and entrances_gdf is not None and len(entrances_gdf):
        graph = build_road_graph(roads_routing_gdf)
        top_idx = stands.sort_values("R_final", ascending=False).head(top_n_for_routing).index
        for idx in top_idx:
            centroid = stands.loc[idx, "geometry"].centroid
            distance, status = nearest_entrance_distance(graph, centroid, entrances_gdf)
            if distance is None:
                continue
            new_p = compute_pressure(distance, stands.loc[idx, "demand"], demand_max, profile)
            stands.loc[idx, "d_park_m"] = distance
            stands.loc[idx, "P"] = new_p
            stands.loc[idx, "pressure_factor"] = 1.0 - alpha * new_p
            stands.loc[idx, "distance_method"] = "network"
            stands.loc[idx, "entrance_status"] = status
            stands.loc[idx, "R_final"] = compute_ranking(
                stands.loc[idx, "mask_full"], stands.loc[idx, "H"], stands.loc[idx, "F_loc"],
                p=new_p, alpha=alpha,
            )

    stands["periodic_ban_checked"] = False
```

(The rest of the function — the periodic-ban-check block onward — is unchanged; leave it exactly as it is today, just now running after the routing-refinement block instead of immediately after the `R_final` list comprehension.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mvp.py -v`
Expected: all `test_mvp.py` tests pass (existing ones unmodified + 3 new).

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/mvp.py tests/test_mvp.py
git commit -m "feat: refine top-N stands' pressure with real routing distance to nearest entrance"
```

---

### Task 6: Export `distance_method` / `entrance_status`

**Files:**
- Modify: `pipeline/export.py`
- Modify: `tests/test_export.py`

**Interfaces:**
- Consumes: `enrich_with_mvp_layers`'s new always-present columns (Task 5).
- Produces: `scores_{date}.json` records now include `distance_method`/`entrance_status`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export.py`, and add `"distance_method": ["network", "euclidean"], "entrance_status": ["confirmed", "not_evaluated"],` to `_enriched_stands()`'s dict literal:

```python
def test_build_score_record_includes_distance_method_and_entrance_status():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["distance_method"] == "network"
    assert record["entrance_status"] == "confirmed"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: `test_build_score_record_includes_distance_method_and_entrance_status` FAILS with `KeyError: 'distance_method'` — `SCORE_FIELDS` doesn't include it yet, so `build_score_record`'s output has no such key and `record["distance_method"]` raises.

- [ ] **Step 3: Add the two fields to `SCORE_FIELDS`**

In `pipeline/export.py`:

```python
SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: all `test_export.py` tests pass (pre-existing + 1 new).

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/export.py tests/test_export.py
git commit -m "feat: export distance_method and entrance_status per stand"
```

---

### Task 7: Wire entrance detection + routing into `prepare_trip`, manual verification

**Files:**
- Modify: `profiles/boletus_edulis.yaml`
- Modify: `pipeline/prepare_trip.py`

**Interfaces:**
- Consumes: `pipeline.entrances.compute_forest_boundary`/`find_entrance_points`/`classify_entrances` (Tasks 2–3); `enrich_with_mvp_layers`'s new parameters (Task 5).
- Produces: no new function — `run_trip_preparation` now produces real `distance_method`/`entrance_status` values instead of `"euclidean"`/`"not_evaluated"` for every stand. No new automated tests (real-I/O orchestration, same reasoning as `run_trip_preparation`'s own existing lack of unit tests); proven by manual verification in Step 3.

- [ ] **Step 1: Add the `entrances` section to the profile**

Append to `profiles/boletus_edulis.yaml` (after the `regions:` section added by the earlier regions plan):

```yaml
entrances:
  confirmed_tolerance_m: 50.0    # spec §5.5.2 -- [E] plan decision: entrance within this distance of a known OSM parking point counts as 'confirmed'
  top_n_for_routing: 25          # spec §13 priority 3 "top 20-30 wydzielen" -- [E] plan decision
```

- [ ] **Step 2: Wire entrance detection and routing into `run_trip_preparation`**

In `pipeline/prepare_trip.py`, add the import:

```python
from pipeline.entrances import compute_forest_boundary, find_entrance_points, classify_entrances
```

Replace this block:

```python
    print("Fetching OSM parking/roads/places (Overpass)...")
    osm_features = fetch_osm_features(bbox, profile)

    print("Enriching with legal mask + presja + confidence + explanations...")
    enriched = enrich_with_mvp_layers(
        scored, profile, gdos_gdf, osm_features,
        zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
    )
```

with:

```python
    print("Fetching OSM parking/roads/places (Overpass)...")
    osm_features = fetch_osm_features(bbox, profile)

    print("Detecting forest entrances...")
    forest_boundary = compute_forest_boundary(scored)
    raw_entrances = find_entrance_points(forest_boundary, osm_features["roads"])
    entrances = classify_entrances(raw_entrances, osm_features["parking"], profile["entrances"]["confirmed_tolerance_m"])
    confirmed_count = int((entrances["status"] == "confirmed").sum()) if len(entrances) else 0
    print(f"  {len(entrances)} candidate entrance(s), {confirmed_count} confirmed")

    print("Enriching with legal mask + presja + confidence + explanations...")
    enriched = enrich_with_mvp_layers(
        scored, profile, gdos_gdf, osm_features,
        zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
        roads_routing_gdf=osm_features["roads"], entrances_gdf=entrances,
        top_n_for_routing=profile["entrances"]["top_n_for_routing"],
    )
```

- [ ] **Step 3: Manual verification against live services (network-dependent, not covered by pytest)**

Run: `.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 53.1509 --lon 16.7382` (Piła, the same already-cached tile the `prepare_trip` CLI plan verified — the BDL fetch will be a cache hit, so this run is faster and only re-exercises the new OSM/entrance/routing path plus a live Open-Meteo/Overpass/zakazy call).

Expected: prints `Detecting forest entrances...` followed by a count line (`N candidate entrance(s), M confirmed`), then completes exactly as before ending with `Gotowe: ...`/`Wyniki: ...`. Then check `notebooks/output/scores_<today>.json`: confirm that **some** records have `"distance_method": "network"` (the top ~25 by `R_final`) and the rest have `"distance_method": "euclidean"` — i.e. the refinement actually ran and only touched the intended subset. If the tile's entrance count is 0 (possible if no road/track happens to cross the forest boundary within this specific tile) every stand will show `"euclidean"` — in that case, rerun for a different real location (e.g. the Kieleczka tile, `--lat 50.526944 --lon 18.605000`) to get a tile where at least one entrance is found, since a wholly-empty entrance result exercises only the fallback path, not the feature itself.

If a live run hits a transient service error unrelated to this plan's code (Overpass rate limiting, a transient BDL/GDOŚ timeout — the same pre-existing flakiness the regions and `prepare_trip` plans already noted), rerun once; if it still fails, capture the traceback in the commit message body instead of silently skipping verification.

- [ ] **Step 4: Run the full automated test suite one more time**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass, unchanged from Task 6 — this task adds no new automated tests, only CLI wiring proven manually above.

- [ ] **Step 5: Commit**

```bash
git add profiles/boletus_edulis.yaml pipeline/prepare_trip.py
git commit -m "feat: wire entrance detection and top-N routing into prepare_trip"
```

---

## Progress log (update this section as tasks complete — this is how a future session knows where to continue)

- [x] Task 1: Fetch full road/track/path linework from Overpass
- [x] Task 2: Forest boundary + candidate entrance detection
- [x] Task 3: Confirmed vs. potential entrance classification
- [x] Task 4: Road/track routing graph + shortest-path distance
- [x] Task 5: Wire top-N network-routing refinement into `enrich_with_mvp_layers`
- [x] Task 6: Export `distance_method` / `entrance_status`
- [x] Task 7: Wire entrance detection + routing into `prepare_trip`, manual verification

**Plan complete (2026-09-24).** All 7 tasks implemented via TDD, full suite green (204 passed). Manually verified end-to-end against live BDL/GDOŚ/Overpass/Open-Meteo/zakazy services on the real Piła tile.

**This plan surfaced more real, code-level bugs during manual verification than the prior two plans combined** — all caught by testing against real data, not synthetic fixtures, and all fixed within this plan rather than deferred:
1. `routing_highway_types` originally included `path`/`footway`/`bridleway`; `path` alone made the Overpass query 504 on a real forest tile. Narrowed to paved + `track`.
2. `nearest_entrance_distance` recomputed a fresh Dijkstra search per candidate entrance (hundreds) for each top-N stand — fixed to one search per stand.
3. Node-snapping used a linear scan over every graph node (~0.2s/call × hundreds of entrances = ~117s for one stand on real data) — fixed with a `scipy.spatial.cKDTree` (117.55s → 0.12s).
4. Final review: `compute_forest_boundary` had no gap-closing, so BDL's internal fragmentation of a single forest (power lines, clear-cuts, forest-road strips) produced spurious interior "entrances" — 45% of detected entrances on real data were interior, not edge, crossings. Fixed with morphological closing (110 boundary parts → 12, 604 entrances → 357 on the same real tile).

Also declined-and-documented: full multi-layer RDLP fetch (unrelated, carried over from the `prepare_trip` CLI plan's own "Next up").

**Next up:**
1. `docs/projekt-borowik.md` §13 priority 4 (minimal frontend: map of regions + stand detail panel) — needs its own plan, not started; it can finally show something other than raw JSON, and can display the `distance_method`/`entrance_status`/entrance confirmed-vs-potential fields this plan adds.
2. The RDLP-border multi-layer-fetch gap noted in the `prepare_trip` CLI plan's own "Next up" — still open, independent of this plan.
3. Worth a look before further accessibility work: this plan's own routing network is now `track`-only (no `path`/`footway`) due to the Overpass query-size limit found here — if that proves too narrow in practice, the real fix is splitting the Overpass query into smaller sub-areas, not just re-adding the broader type list.
4. Run `uv lock`/`uv sync` once a session with a real `uv` binary picks this up, to bring `uv.lock` back in sync with `pyproject.toml`'s `networkx` addition (from this plan) — deferred since Task 4, still open.
