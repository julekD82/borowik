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
