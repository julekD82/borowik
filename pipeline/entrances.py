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
