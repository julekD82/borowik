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


def point_in_any_bbox(centroid, bboxes: list) -> bool:
    """True when `centroid` (an EPSG:2180 point, e.g. a stand's geometry
    centroid) falls inside any of `bboxes` (n_min, e_min, n_max, e_max
    tuples -- the same shape pipeline.search_area's tile lists and failed-
    tile lists use). Shared by pipeline.gdos.gdos_status (plan 1.6) and
    pipeline.mvp's OSM tile-skip confidence check (plan 1.7), so both agree
    on what "this stand's tile" means."""
    for n_min, e_min, n_max, e_max in bboxes or []:
        if n_min <= centroid.y <= n_max and e_min <= centroid.x <= e_max:
            return True
    return False
