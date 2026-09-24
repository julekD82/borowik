# Borowik GIS — Grupowanie wydzieleń w rejony poszukiwań Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the scored-stands GeoDataFrame that `pipeline.mvp.enrich_with_mvp_layers` already produces into a small list (≤5) of spatial search **regions** — spec §5.6/§13 priority 1 — so the application's main output can eventually become "3–5 regions to search" instead of a flat table of wydzielenia. This plan covers the scoring/grouping module, its export, and wiring it into the existing MVP notebook. It does **not** cover the frontend, the `prepare_trip` CLI, or the accessibility/popularity rework — those are priorities 2–3 in `docs/projekt-borowik.md` §13 and are separate plans.

**Architecture:** One new pure, testable module, `pipeline/regions.py`, following the same shape as every other `pipeline/*.py` module (small composable functions, no I/O, GeoDataFrame in → GeoDataFrame out). It consumes the output columns `pipeline.mvp.enrich_with_mvp_layers` already produces (`mask_full`, `R_final`, `stand_id`, `geometry`) and needs no new network calls, so every function is directly unit-testable with synthetic GeoDataFrames — no `responses` mocking needed anywhere in this plan. A new `pipeline/export.py::write_regions_json` mirrors the existing `write_scores_json` shape. `notebooks/02_mvp.py` gets one more step appended at the end, exactly like it already appends GDOŚ/OSM/mvp-enrichment/export steps one after another.

**Tech Stack:** Same as the rest of the repo — Python 3.12, `uv`, GeoPandas + Shapely 2 + pyproj, PyYAML, pytest. No new dependencies: region clustering uses `shapely.ops.unary_union`, already a transitive dependency of Shapely 2 used elsewhere in this codebase's dependency tree (GeoPandas itself depends on it; not yet imported directly by any `pipeline/*.py` module, but it ships with the pinned `shapely>=2.0`).

**Spec:** `docs/projekt-borowik.md` — read §5.6 ("Grupowanie w rejony poszukiwań") and §13 priority 1 before starting; both are quoted inline below where relevant.

## Global Constraints

- Repo root: this worktree (`C:\Users\<uzytkownik>\Documents\Grzyby\.claude\worktrees\borowik-faza2-mvp-backend`). Python ≥3.12 via `uv`. No new entries needed in `pyproject.toml`.
- Storage format stays GeoParquet / plain JSON under `cache/` and `notebooks/output/` — no PostGIS/DB (unchanged project-wide constraint).
- Scope is exactly spec §5.6 + §13 priority 1 (grouping + its JSON export + notebook wiring). Priority 2 (`prepare_trip` CLI/parametrization), priority 3 (routing-based accessibility, confirmed/potential entrances), and any frontend work are **out of scope** for this plan.
- **Numeric defaults for `top_pct`, `buffer_m`, `top_n_per_region`, `max_regions` are this plan's own design decision, not values fixed by the spec.** Spec §5.6 step 1 says candidates come from "R powyżej progu (np. top 25% w obszarze, jak dziś w UI)" — this plan uses `top_pct: 0.25` because the spec's own example matches the UI ranking language already in §5.7. `buffer_m`, `top_n_per_region`, and `max_regions` have no spec-given value; this plan picks `buffer_m: 250.0` (merges stands separated by a single forest ride/minor road, not by a genuinely separate compartment), `top_n_per_region: 5`, `max_regions: 5` (spec §0/§12: "3–5 rejonów"). All four live in `profiles/boletus_edulis.yaml` under a new `regions:` key, `[E]`-tagged the same way `pressure:`/`confidence:` parameters already are, so they're tunable without touching code.
- **Region score is the median of the top-N candidate stands' `R_final` inside the cluster, never a sum.** This is the one hard requirement from spec §5.6 step 3 ("Nie premiować automatycznie największego lasu przez sumowanie punktów") and from the original user request that produced it — every task touching scoring must preserve this, and Task 3 adds a regression test that a large low-scoring cluster must not outrank a small high-scoring one.
- **Region geometry is the union of the member stands' own (unbuffered) geometries, not the buffered geometries used only to decide cluster membership.** Buffering is a clustering *decision*, not part of the *shown* region shape — showing a buffer-inflated polygon on the map would misrepresent the searchable area.
- `select_candidates`'s percentile is computed over `mask_full`-passing stands only, mirroring the existing pattern in `pipeline/orchestrate.py::run_poc` (diagnostics restricted to mask-passing rows) — masked stands have `R_final == 0` by construction (`pipeline.scoring.compute_ranking`) and would otherwise silently drag the threshold to 0.

## Review Focus

- **A tile with zero mask-passing stands** (e.g. entirely masked out, or an empty input frame): `group_into_regions` must return an empty GeoDataFrame with the documented columns, not raise. Covered in Task 4.
- **Two clusters separated by a gap smaller than `buffer_m`** must merge into one region even though the individual stand geometries don't touch — this is the entire point of buffering before clustering. Covered in Task 2.
- **Two clusters separated by a gap larger than `buffer_m`** must stay as two separate regions — a clustering bug that merges everything into one blob would silently defeat the "3–5 distinct regions" goal. Covered in Task 2.
- **A cluster with fewer stands than `top_n_per_region`** must not raise or silently pad — `head(n)` on a short frame in pandas already just returns what's there, but this plan adds an explicit test since it's exactly the "few excellent stands" case Global Constraints' median rule exists to protect. Covered in Task 3.
- **More clusters than `max_regions`** must keep the highest-scoring ones and drop the rest, sorted deterministically by `rank_score` descending. Covered in Task 4.

---

## File Structure

```
pipeline/
  regions.py          # NEW: select_candidates, _assign_clusters, _summarize_cluster, group_into_regions
  export.py            # MODIFY: + build_region_record, write_regions_json
profiles/
  boletus_edulis.yaml  # MODIFY: + regions: section
notebooks/
  02_mvp.py            # MODIFY: append region grouping + regions_{date}.json export after existing MVP export step
tests/
  test_regions.py      # NEW
  test_export.py        # MODIFY: append region-export tests
```

---

### Task 1: `regions` profile config + `select_candidates`

**Files:**
- Modify: `profiles/boletus_edulis.yaml`
- Create: `pipeline/regions.py`
- Create: `tests/test_regions.py`

**Interfaces:**
- Consumes: `profile["regions"]` (new YAML key); a `stands` GeoDataFrame with columns `stand_id`, `R_final`, `mask_full`, `geometry` (this is exactly what `pipeline.mvp.enrich_with_mvp_layers` already returns).
- Produces: `select_candidates(stands: gpd.GeoDataFrame, top_pct: float) -> gpd.GeoDataFrame`, used by Task 4's `group_into_regions`.

- [ ] **Step 1: Add the `regions` section to the profile**

Append to the end of `profiles/boletus_edulis.yaml`:

```yaml
regions:
  top_pct: 0.25             # candidate stands = top 25% of R_final among mask_full-passing stands, spec §5.6 step 1 / §5.7
  buffer_m: 250.0            # merge candidate stands separated by up to this many metres into one region, spec §5.6 step 2 -- [E], plan decision
  top_n_per_region: 5        # region score = median of the top N candidate R_final values in it, spec §5.6 step 3 -- [E], plan decision
  max_regions: 5             # spec §0/§12 "3-5 rejonów na wycieczkę" -- [E], plan decision
```

- [ ] **Step 2: Write the failing tests for `select_candidates`**

Create `tests/test_regions.py`:

```python
import geopandas as gpd
from shapely.geometry import box

from pipeline.regions import select_candidates


def _stand(stand_id, r_final, mask_full=True, x=380000):
    return {
        "stand_id": stand_id, "R_final": r_final, "mask_full": mask_full,
        "geometry": box(x, 486000, x + 100, 486100),
    }


def test_select_candidates_keeps_only_top_fraction_of_mask_passing_stands():
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 1000) for i in range(1, 11)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=0.2)
    # top 20% of 10 stands by R_final (1..10) -> R_final >= 9.0 -> stands 9 and 10
    assert sorted(result["stand_id"].tolist()) == ["S10", "S9"]


def test_select_candidates_ignores_mask_failing_stands_even_with_high_r():
    rows = [
        _stand("low_pass", r_final=5.0, mask_full=True, x=380000),
        _stand("high_fail", r_final=99.0, mask_full=False, x=381000),
    ]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=1.0)
    assert result["stand_id"].tolist() == ["low_pass"]


def test_select_candidates_returns_empty_frame_when_nothing_passes_mask():
    rows = [_stand("only", r_final=50.0, mask_full=False)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=0.25)
    assert len(result) == 0
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'pipeline.regions'` (the file doesn't exist yet).

- [ ] **Step 4: Create `pipeline/regions.py` with `select_candidates`**

```python
import geopandas as gpd
from shapely.ops import unary_union


def select_candidates(stands: gpd.GeoDataFrame, top_pct: float) -> gpd.GeoDataFrame:
    """Mask-passing stands in the top `top_pct` fraction of R_final, spec
    §5.6 step 1. The percentile is taken over mask-passing stands only --
    masked stands have R_final == 0 by construction
    (pipeline.scoring.compute_ranking) and would otherwise drag the
    threshold down, letting low-R stands in."""
    passing = stands[stands["mask_full"]]
    if len(passing) == 0:
        return passing
    threshold = passing["R_final"].quantile(1.0 - top_pct)
    return passing[passing["R_final"] >= threshold]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add profiles/boletus_edulis.yaml pipeline/regions.py tests/test_regions.py
git commit -m "feat: add regions profile config and select_candidates"
```

---

### Task 2: Spatial clustering (`_assign_clusters`)

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `tests/test_regions.py`

**Interfaces:**
- Consumes: `select_candidates`'s output shape (a `gpd.GeoDataFrame` with `stand_id`, `R_final`, `geometry`).
- Produces: `_assign_clusters(candidates: gpd.GeoDataFrame, buffer_m: float) -> list[gpd.GeoDataFrame]`, used by Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_regions.py`:

```python
from pipeline.regions import _assign_clusters


def test_assign_clusters_merges_stands_separated_by_a_gap_within_buffer():
    rows = [
        _stand("A", r_final=50.0, x=380000),  # box 380000-380100
        _stand("B", r_final=60.0, x=380300),  # box 380300-380400, 200 m gap from A
    ]
    candidates = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    clusters = _assign_clusters(candidates, buffer_m=250.0)
    assert len(clusters) == 1
    assert sorted(clusters[0]["stand_id"].tolist()) == ["A", "B"]


def test_assign_clusters_keeps_gap_larger_than_buffer_separate():
    rows = [
        _stand("A", r_final=50.0, x=380000),  # box 380000-380100
        _stand("B", r_final=60.0, x=381000),  # box 381000-381100, 900 m gap from A
    ]
    candidates = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    clusters = _assign_clusters(candidates, buffer_m=250.0)
    assert len(clusters) == 2
    ids = sorted(c["stand_id"].iloc[0] for c in clusters)
    assert ids == ["A", "B"]


def test_assign_clusters_returns_empty_list_for_empty_input():
    empty = gpd.GeoDataFrame({"stand_id": [], "R_final": []}, geometry=[], crs="EPSG:2180")
    assert _assign_clusters(empty, buffer_m=250.0) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: the three new tests FAIL with `ImportError: cannot import name '_assign_clusters'`.

- [ ] **Step 3: Implement `_assign_clusters`**

Append to `pipeline/regions.py`:

```python
def _assign_clusters(candidates: gpd.GeoDataFrame, buffer_m: float) -> list[gpd.GeoDataFrame]:
    """Split `candidates` into disjoint spatial clusters: stands within
    `buffer_m` of each other end up in the same cluster (spec §5.6 step 2).
    A stand's own (unbuffered) geometry always lies inside its own buffered
    copy (buffering a polygon by a non-negative distance always produces a
    geometry that contains the original), so it always intersects exactly
    the one merged component it contributed to -- this holds regardless of
    polygon concavity, unlike testing centroid containment."""
    if len(candidates) == 0:
        return []
    buffered = candidates.geometry.buffer(buffer_m)
    merged = unary_union(list(buffered))
    components = [merged] if merged.geom_type == "Polygon" else list(merged.geoms)
    clusters = []
    for component in components:
        members = candidates[candidates.geometry.intersects(component)]
        if len(members):
            clusters.append(members)
    return clusters
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py tests/test_regions.py
git commit -m "feat: cluster candidate stands by buffered spatial proximity"
```

---

### Task 3: Region score = median of top-N (`_summarize_cluster`)

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `tests/test_regions.py`

**Interfaces:**
- Consumes: one cluster's `gpd.GeoDataFrame` from `_assign_clusters`'s output list.
- Produces: `_summarize_cluster(members: gpd.GeoDataFrame, top_n: int) -> dict` with keys `rank_score` (float), `stand_count` (int), `stand_ids` (list[str]), `geometry` (shapely geometry) — used by Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_regions.py`:

```python
import pytest

from pipeline.regions import _summarize_cluster


def test_summarize_cluster_uses_median_of_top_n_not_sum():
    # A large cluster of many just-above-threshold stands must not outrank
    # a small cluster of a few excellent ones purely by being numerous --
    # spec §5.6 step 3, the whole reason this function exists.
    many_mediocre = gpd.GeoDataFrame(
        [_stand(f"M{i}", r_final=20.0, x=380000 + i * 300) for i in range(10)],
        crs="EPSG:2180",
    )
    few_excellent = gpd.GeoDataFrame(
        [_stand("E1", r_final=90.0, x=390000), _stand("E2", r_final=88.0, x=390300)],
        crs="EPSG:2180",
    )
    mediocre_summary = _summarize_cluster(many_mediocre, top_n=5)
    excellent_summary = _summarize_cluster(few_excellent, top_n=5)
    assert excellent_summary["rank_score"] > mediocre_summary["rank_score"]
    assert mediocre_summary["rank_score"] == 20.0
    assert excellent_summary["rank_score"] == 89.0  # median of [90, 88], top_n=5 > available 2


def test_summarize_cluster_geometry_is_union_of_member_geometries_not_buffered():
    members = gpd.GeoDataFrame(
        [_stand("A", r_final=50.0, x=380000), _stand("B", r_final=60.0, x=380100)],
        crs="EPSG:2180",
    )
    summary = _summarize_cluster(members, top_n=5)
    # two touching 100x100 boxes -> exact union area, not inflated by any buffer
    assert summary["geometry"].area == pytest.approx(2 * 100 * 100)


def test_summarize_cluster_stand_ids_and_count():
    members = gpd.GeoDataFrame(
        [_stand("A", r_final=50.0, x=380000), _stand("B", r_final=60.0, x=380100)],
        crs="EPSG:2180",
    )
    summary = _summarize_cluster(members, top_n=5)
    assert summary["stand_count"] == 2
    assert sorted(summary["stand_ids"]) == ["A", "B"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: the three new tests FAIL with `ImportError: cannot import name '_summarize_cluster'`.

- [ ] **Step 3: Implement `_summarize_cluster`**

Append to `pipeline/regions.py`:

```python
def _summarize_cluster(members: gpd.GeoDataFrame, top_n: int) -> dict:
    """Region score = median R_final of the top `top_n` candidate stands in
    the cluster (spec §5.6 step 3) -- deliberately not a sum, so a large
    forest complex full of just-above-threshold stands does not
    automatically outrank a small complex of a few excellent stands. If the
    cluster has fewer than `top_n` members, `.head(top_n)` on a short frame
    just returns what's there -- no special-casing needed."""
    top = members.sort_values("R_final", ascending=False).head(top_n)
    return {
        "rank_score": float(top["R_final"].median()),
        "stand_count": int(len(members)),
        "stand_ids": members["stand_id"].tolist(),
        "geometry": unary_union(list(members.geometry)),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py tests/test_regions.py
git commit -m "feat: score regions by median of top-N stands, not a sum"
```

---

### Task 4: Public API `group_into_regions`

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `tests/test_regions.py`

**Interfaces:**
- Consumes: `select_candidates`, `_assign_clusters`, `_summarize_cluster` (Tasks 1–3); `profile["regions"]` (Task 1).
- Produces: `group_into_regions(stands: gpd.GeoDataFrame, profile: dict) -> gpd.GeoDataFrame` with columns `["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]`, sorted by `rank_score` descending, at most `profile["regions"]["max_regions"]` rows. This is the function Task 5 (export) and Task 6 (notebook wiring) call.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_regions.py`:

```python
from pipeline.habitat import load_profile
from pipeline.regions import group_into_regions

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_group_into_regions_empty_when_nothing_passes_mask():
    stands = gpd.GeoDataFrame(
        [{"stand_id": "A", "R_final": 99.0, "mask_full": False,
          "geometry": box(380000, 486000, 380100, 486100)}],
        crs="EPSG:2180",
    )
    result = group_into_regions(stands, PROFILE)
    assert len(result) == 0
    assert list(result.columns) == ["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]


def test_group_into_regions_caps_at_max_regions_and_sorts_by_score():
    # 8 clusters, each a single stand 5 km apart (far beyond buffer_m),
    # scores 10..80 -- with max_regions=5 (profile default) only the best 5 survive.
    rows = [_stand(f"S{i}", r_final=float(i) * 10, x=380000 + i * 5000) for i in range(1, 9)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert len(result) == PROFILE["regions"]["max_regions"]
    assert result["rank_score"].tolist() == sorted(result["rank_score"].tolist(), reverse=True)
    assert result["rank_score"].max() == 80.0


def test_group_into_regions_region_ids_are_sequential():
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 5000) for i in range(1, 4)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert result["region_id"].tolist() == ["region_1", "region_2", "region_3"]


def test_group_into_regions_does_not_let_a_sprawling_mediocre_cluster_beat_a_tight_excellent_one():
    # End-to-end version of the Task 3 unit test, through the public API.
    mediocre_rows = [_stand(f"M{i}", r_final=20.0, x=380000 + i * 300) for i in range(10)]
    excellent_rows = [_stand("E1", r_final=90.0, x=390000), _stand("E2", r_final=88.0, x=390300)]
    stands = gpd.GeoDataFrame(mediocre_rows + excellent_rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert result.iloc[0]["stand_ids"] == ["E1", "E2"] or set(result.iloc[0]["stand_ids"]) == {"E1", "E2"}
    assert result.iloc[0]["rank_score"] == 89.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: the four new tests FAIL with `ImportError: cannot import name 'group_into_regions'`.

- [ ] **Step 3: Implement `group_into_regions`**

Append to `pipeline/regions.py`:

```python
def group_into_regions(stands: gpd.GeoDataFrame, profile: dict) -> gpd.GeoDataFrame:
    """Top-level entry point, spec §5.6: turn a scored `stands` GeoDataFrame
    (pipeline.mvp.enrich_with_mvp_layers output -- must carry `mask_full`,
    `R_final`, `stand_id`, `geometry`) into at most `max_regions` search
    regions, each scored by the median of its best stands rather than a
    sum, so this is the main output the application shows instead of a flat
    table of wydzielenia (spec §0)."""
    cfg = profile["regions"]
    empty = gpd.GeoDataFrame(
        {"region_id": [], "rank_score": [], "stand_count": [], "stand_ids": []},
        geometry=[], crs=stands.crs,
    )
    candidates = select_candidates(stands, cfg["top_pct"])
    if len(candidates) == 0:
        return empty

    clusters = _assign_clusters(candidates, cfg["buffer_m"])
    summaries = [_summarize_cluster(cluster, cfg["top_n_per_region"]) for cluster in clusters]
    if not summaries:
        return empty

    summaries.sort(key=lambda s: s["rank_score"], reverse=True)
    top_summaries = summaries[: cfg["max_regions"]]
    for i, summary in enumerate(top_summaries, start=1):
        summary["region_id"] = f"region_{i}"

    return gpd.GeoDataFrame(
        top_summaries, geometry="geometry", crs=stands.crs
    )[["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: 13 passed.

- [ ] **Step 5: Run the full test suite to check nothing else broke**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (144 pre-existing + 13 new = 157 passed).

- [ ] **Step 6: Commit**

```bash
git add pipeline/regions.py tests/test_regions.py
git commit -m "feat: group_into_regions public API"
```

---

### Task 5: Export `regions_{date}.json`

**Files:**
- Modify: `pipeline/export.py`
- Modify: `tests/test_export.py`

**Interfaces:**
- Consumes: `group_into_regions`'s output shape (Task 4): columns `region_id`, `rank_score`, `stand_count`, `stand_ids`, `geometry`.
- Produces: `build_region_record(row, day: str) -> dict` and `write_regions_json(regions: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path`, matching the existing `build_score_record`/`write_scores_json` shape in the same file. Used by Task 6.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_export.py`:

```python
from pipeline.export import build_region_record, write_regions_json


def _regions():
    return gpd.GeoDataFrame({
        "region_id": ["region_1"],
        "rank_score": [42.5],
        "stand_count": [3],
        "stand_ids": [["A", "B", "C"]],
    }, geometry=[box(380000, 486000, 380300, 486100)], crs="EPSG:2180")


def test_build_region_record_shape():
    row = _regions().iloc[0]
    record = build_region_record(row, day="2026-09-24")
    assert record == {
        "region_id": "region_1", "rank_score": 42.5, "stand_count": 3,
        "stand_ids": ["A", "B", "C"], "day": "2026-09-24",
    }


def test_write_regions_json_writes_one_record_per_region(tmp_path):
    out_path = write_regions_json(_regions(), day="2026-09-24", out_path=tmp_path / "regions_2026-09-24.json")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data == [{
        "region_id": "region_1", "rank_score": 42.5, "stand_count": 3,
        "stand_ids": ["A", "B", "C"], "day": "2026-09-24",
    }]


def test_write_regions_json_handles_empty_regions(tmp_path):
    empty = gpd.GeoDataFrame(
        {"region_id": [], "rank_score": [], "stand_count": [], "stand_ids": []},
        geometry=[], crs="EPSG:2180",
    )
    out_path = write_regions_json(empty, day="2026-09-24", out_path=tmp_path / "regions.json")
    assert json.loads(out_path.read_text(encoding="utf-8")) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: the three new tests FAIL with `ImportError: cannot import name 'build_region_record'`.

- [ ] **Step 3: Implement `build_region_record` and `write_regions_json`**

Append to `pipeline/export.py`:

```python
REGION_FIELDS = ["region_id", "rank_score", "stand_count", "stand_ids"]


def build_region_record(row, day: str) -> dict:
    """Matches spec §7.2's regions_{date}.json: the rejony list that becomes
    the application's main output, alongside the existing scores_{date}.json
    detail view."""
    record = {field: _json_safe(row[field]) for field in REGION_FIELDS}
    record["region_id"] = str(record["region_id"])
    record["rank_score"] = _json_safe(float(row["rank_score"]))
    record["stand_count"] = int(row["stand_count"])
    record["stand_ids"] = list(row["stand_ids"])
    record["day"] = day
    return record


def write_regions_json(regions: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [build_region_record(row, day) for _, row in regions.iterrows()]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: all `test_export.py` tests pass (7 pre-existing + 3 new = 10 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/export.py tests/test_export.py
git commit -m "feat: export regions_{date}.json"
```

---

### Task 6: Wire region grouping into the MVP notebook

**Files:**
- Modify: `notebooks/02_mvp.py`

**Interfaces:**
- Consumes: `pipeline.regions.group_into_regions` (Task 4), `pipeline.export.write_regions_json` (Task 5), and the `enriched` GeoDataFrame `notebooks/02_mvp.py` already builds via `enrich_with_mvp_layers`.
- Produces: no new function — this task only extends the notebook script's own end-to-end run, the same way it already chains GDOŚ → OSM → `enrich_with_mvp_layers` → export.

- [ ] **Step 1: Add the import**

In `notebooks/02_mvp.py`, in the existing import block (alongside `from pipeline.mvp import enrich_with_mvp_layers`), add:

```python
from pipeline.regions import group_into_regions
```

- [ ] **Step 2: Append region grouping and export after the existing export step**

`notebooks/02_mvp.py` currently ends (after the `known_points` re-validation block) with the `else:` branch printing "Brak notebooks/known_points.yaml...". Immediately after that `if/else` block (i.e. as the new final lines of the file), append:

```python
print("Grouping into search regions...")
regions = group_into_regions(enriched, profile)
regions_path = write_regions_json(regions, day=today, out_path=out_dir / f"regions_{today}.json")
print(f"Wrote {regions_path}: {len(regions)} region(s)")
for _, region in regions.iterrows():
    print(
        f"  {region['region_id']}: rank_score={region['rank_score']:.1f}, "
        f"stands={region['stand_count']}"
    )
```

This also requires importing `write_regions_json` — add it to the existing `from pipeline.export import write_scores_json, export_stand_geometries` line, making it:

```python
from pipeline.export import write_scores_json, export_stand_geometries, write_regions_json
```

- [ ] **Step 3: Manual verification (network-dependent, not covered by pytest)**

This notebook script calls live BDL/GDOŚ/Open-Meteo/Overpass/zakazy-wstępu endpoints, exactly like the rest of `notebooks/02_mvp.py` already does — it is intentionally excluded from the automated test suite for the same reason every other step in this file is (see the module's own docstring). Run it manually:

Run: `.venv/Scripts/python.exe notebooks/02_mvp.py`
Expected: the script completes through its existing output, then prints `Grouping into search regions...`, `Wrote notebooks/output/regions_<today>.json: N region(s)`, and one summary line per region. Confirm `notebooks/output/regions_<today>.json` exists and contains at most 5 records, each with `region_id`, `rank_score`, `stand_count`, `stand_ids`, `day`.

If this run hits a live-service error unrelated to this plan's code (e.g. Overpass rate limiting, a transient BDL timeout), that's a pre-existing flakiness of the manual verification step, not a regression from this task — rerun once; if it still fails, capture the traceback in the commit message body instead of silently skipping verification.

- [ ] **Step 4: Run the full automated test suite one more time**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (157 passed, unchanged from Task 4 — this task adds no new automated tests, only notebook wiring).

- [ ] **Step 5: Commit**

```bash
git add notebooks/02_mvp.py
git commit -m "feat: wire region grouping and export into the MVP notebook"
```

---

## Progress log (update this section as tasks complete — this is how a future session knows where to continue)

- [x] Task 1: `regions` profile config + `select_candidates`
- [x] Task 2: Spatial clustering (`_assign_clusters`)
- [x] Task 3: Region score = median of top-N (`_summarize_cluster`)
- [x] Task 4: Public API `group_into_regions`
- [x] Task 5: Export `regions_{date}.json`
- [x] Task 6: Wire region grouping into the MVP notebook

**Plan complete (2026-09-24).** All 6 tasks implemented via TDD, full suite green (161 passed). Manually verified end-to-end against live BDL/GDOŚ/Overpass/Open-Meteo/zakazy services on the existing Kieleczka tile: 4 regions produced from 721 mask-passing stands. Final whole-branch review (fresh subagent, opus) found one Important gap (regions export had no location) — fixed with a WGS84 centroid, TDD RED→GREEN, suite 161/161. One Important finding was declined as a ruling (see the plan's own workspace ledger, or the branch's git history, for the full reasoning) and four Minor findings were deferred, not fixed. Full detail lives in the git commit history of this branch (`git log --oneline` from commit `02583b8`) and was in `.superpowers/sdd/2026-09-24-borowik-regions/progress.md` before that workspace was cleaned up per superpowers:executing-plans.

**Next up:** `docs/projekt-borowik.md` §13 priority 2 (`prepare_trip` CLI/parametrization) — needs its own plan via superpowers:writing-plans, not started. Priority 3 (routing-based accessibility, confirmed/potential entrances) is after that. Also worth a look before priority 2: the regions export's declined finding above (large buffered-union complexes trending to rank highest) — revisit once there's real usage data, per the ruling's stated cost-if-wrong.
