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
