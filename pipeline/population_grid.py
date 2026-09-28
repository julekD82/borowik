"""Plan wdrozenia 1.4: GUS NSP 2021 1km population grid (zasob 24532) as the
population point source for pipeline.pressure.compute_demand, replacing OSM
place-node population (which silently became 0 for any settlement without a
`population` tag -- spec S5.4/S9.1).

The grid ships as one polygon (1km square) per cell nationwide, EPSG:2180
already (no reprojection needed), with total population in the `tot` field.
compute_demand only needs point geometries + a `population` column, so each
cell becomes a point at its own centroid -- "each square is one demand point"
is a coarser approximation than a real settlement location, but it is a
real, complete population count instead of an OSM tag that may not exist.
"""
from pathlib import Path

import geopandas as gpd
import pyogrio

# GUS's own field name for total population per 1km cell (verified against
# the real zasob 24532 export: 315,857 features nationwide, EPSG:2180,
# MultiPolygon, fields oid/shape_leng/shape_area/code/pl_code/tot/tot_male/
# tot_fem/tot_0_14/tot_15_64/tot_65_/multipolygon_area/multipolygon_length).
_POPULATION_FIELD = "tot"


def load_population_points(path, bbox_2180: tuple[float, float, float, float]) -> gpd.GeoDataFrame | None:
    """Returns a GeoDataFrame with `population`/geometry (cell centroids,
    EPSG:2180) for every grid cell intersecting `bbox_2180` (n_min, e_min,
    n_max, e_max -- same axis order pipeline.tiles.tile_bbox_2180 returns),
    or None if `path` doesn't exist -- the caller's cue to fall back to
    OSM place nodes (impute_osm_population below) instead of raising.

    A cell suppressed for statistical secrecy is expected to carry a null
    `tot` in the source file rather than a fabricated 0 (a real, sparsely
    populated forest/field cell legitimately has `tot == 0` and must stay
    distinguishable from "GUS withheld this") -- null rows are dropped here
    and counted in `.attrs["missing_count"]` rather than silently treated
    as 0 population, per spec §5.4."""
    path = Path(path)
    if not path.exists():
        return None
    n_min, e_min, n_max, e_max = bbox_2180
    # pyogrio's bbox is (xmin, ymin, xmax, ymax) i.e. (easting, northing) --
    # the opposite axis order from tile_bbox_2180's own (n_min, e_min, ...).
    raw = pyogrio.read_dataframe(path, bbox=(e_min, n_min, e_max, n_max))
    missing_count = int(raw[_POPULATION_FIELD].isna().sum())
    raw = raw.dropna(subset=[_POPULATION_FIELD])
    points = gpd.GeoDataFrame(
        {"population": raw[_POPULATION_FIELD].astype(float).values},
        geometry=raw.geometry.centroid.values,
        crs=raw.crs,
    )
    points.attrs["missing_count"] = missing_count
    points.attrs["cell_count"] = len(points)
    return points


def impute_osm_population(places_gdf: gpd.GeoDataFrame, profile: dict) -> gpd.GeoDataFrame:
    """Fallback path (no GUS grid file configured/found): fill a missing
    `population` (None/NaN -- pipeline.osm.parse_osm_elements no longer
    defaults it to 0.0 itself) with profile["population"]
    ["osm_fallback_population_by_class"][place_class], keyed by OSM's own
    `place` tag (hamlet/village/town/city). A place whose class isn't in
    that mapping, or that already had a real tag, is left untouched. Adds
    `population_source` ("osm" for a real tag, "osm_z_imputacja" for a
    filled-in default) so the manifest/diagnostics can report which."""
    if places_gdf is None:
        return places_gdf
    places_gdf = places_gdf.copy()
    if not len(places_gdf):
        # Nothing to impute -- also sidesteps a KeyError on a minimal empty
        # fixture (e.g. tests/test_mvp.py's) that has a "population" column
        # but no "place" column at all.
        return places_gdf
    defaults = profile["population"]["osm_fallback_population_by_class"]
    has_real_value = places_gdf["population"].notna()
    places_gdf["population_source"] = "osm"
    places_gdf.loc[~has_real_value, "population_source"] = "osm_z_imputacja"
    imputed = places_gdf.loc[~has_real_value, "place"].map(defaults)
    places_gdf.loc[~has_real_value, "population"] = imputed
    # A place class with no profile default (not hamlet/village/town/city)
    # still has no real number -- 0.0 (never contributes to Demand) is the
    # honest floor here, not a fabricated guess for an unlisted class.
    places_gdf["population"] = places_gdf["population"].fillna(0.0).astype(float)
    return places_gdf
