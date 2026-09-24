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


def _region_members(candidates: gpd.GeoDataFrame, seed_point, radius_m: float) -> gpd.GeoDataFrame:
    """Candidates whose ENTIRE geometry (not just its centroid) lies within
    `radius_m` of `seed_point` -- spec §5.6 "Nowa definicja rejonu (2.1)",
    plan 2.1 step A2.

    A centroid-only distance test lets a large/elongated stand (up to
    ~27 ha / ~900 m own diagonal in real BDL data) poke outside the
    intended circle even though its centroid is close, which blew the 2 km
    diameter completion criterion when checked against a real 25 km-run
    export during planning. Testing whole-geometry containment instead
    gives a triangle-inequality guarantee: every point of every accepted
    member is <= radius_m from seed_point, so any two points anywhere in
    the resulting region are <= 2*radius_m apart -- a hard bound on the
    region's diameter that holds no matter how large or continuous the
    surrounding forest is, which is exactly the bug this replaces (see
    group_into_regions).

    `sindex.query(geometry, predicate="contains")` returns candidates whose
    geometry the query geometry (here, the seed's buffer circle) contains
    -- i.e. exactly the candidates entirely within the buffer, using the
    exact geometry (not just its bounding box) despite going through the
    spatial index. Verified directly against plain `.within()` during
    planning; this is not the same as predicate="within", which tests the
    opposite direction."""
    seed_buffer = seed_point.buffer(radius_m)
    idx = candidates.sindex.query(seed_buffer, predicate="contains")
    return candidates.iloc[idx]


def _density_score(members: gpd.GeoDataFrame) -> float:
    """spec §5.6 window score, sum(area_ha * R_final) over a seed's members.
    The spec normalizes by window area, but every seed's candidate radius
    is identical, so that division is a constant factor that never changes
    the relative ranking of seeds -- dropped as an unnecessary
    simplification (see plan A2)."""
    return float(((members.geometry.area / 10000.0) * members["R_final"]).sum())


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


def group_into_regions(stands: gpd.GeoDataFrame, profile: dict) -> gpd.GeoDataFrame:
    """Top-level entry point, spec §5.6 "Nowa definicja rejonu (2.1)": turn a
    scored `stands` GeoDataFrame (pipeline.mvp.enrich_with_mvp_layers output
    -- must carry `mask_full`, `R_final`, `stand_id`, `geometry`) into at
    most `max_regions` search regions, each with a bounded footprint
    (diameter <= 2 * cfg["radius_m"], see _region_members) rather than the
    unbounded buffer+unary_union chain-merge from version 2.0, which let one
    region swallow an entire 187 km2 continuous forest complex on a real
    25 km run (spec §5.6 "Stan 2.1", plan 2.1 step A2)."""
    cfg = profile["regions"]
    empty = gpd.GeoDataFrame(
        {"region_id": [], "rank_score": [], "stand_count": [], "stand_ids": []},
        geometry=[], crs=stands.crs,
    )
    candidates = select_candidates(stands, cfg["top_pct"])
    if len(candidates) == 0:
        return empty
    candidates = candidates.reset_index(drop=True)

    radius_m = cfg["radius_m"]
    centroids = candidates.geometry.centroid

    # Every candidate is a potential region seed: its density score (spec
    # §5.6 step 2, see _density_score) and its members (spec step 2) only
    # ever need computing once each, reused below both for ranking seeds
    # and for building the accepted region's summary.
    seed_scores = []
    members_by_seed = {}
    for pos in range(len(candidates)):
        members = _region_members(candidates, centroids.iloc[pos], radius_m)
        members_by_seed[pos] = members
        seed_scores.append((_density_score(members), pos))
    seed_scores.sort(key=lambda t: t[0], reverse=True)

    accepted = []
    accepted_centers = []
    for _score, pos in seed_scores:
        if len(accepted) >= cfg["max_regions"]:
            break
        members = members_by_seed[pos]
        total_area_ha = float((members.geometry.area / 10000.0).sum())
        if total_area_ha < cfg["min_area_ha"]:
            continue
        summary = _summarize_cluster(members, cfg["top_n_per_region"])
        # spec step 4: reject a region too close to an already-accepted one.
        # Checked against the CANDIDATE region's own actual member centroid,
        # not the seed point -- a region's membership can be skewed enough
        # (e.g. only neighbours on one side survive _region_members) that its
        # true centroid drifts from the seed and ends up closer to an
        # existing region than the seed itself was, which would silently
        # violate min_separation_m if only the seed point were checked. This
        # is the same centroid write_regions_json later reports, so the
        # check and the reported distance always agree.
        actual_center = summary["geometry"].centroid
        if any(actual_center.distance(center) < cfg["min_separation_m"] for center in accepted_centers):
            continue
        accepted.append(summary)
        accepted_centers.append(actual_center)

    if not accepted:
        return empty

    for i, summary in enumerate(accepted, start=1):
        summary["region_id"] = f"region_{i}"

    return gpd.GeoDataFrame(
        accepted, geometry="geometry", crs=stands.crs
    )[["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]]
