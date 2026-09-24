"""Metric search radius and bounded, reusable 10 km source queries."""
import hashlib
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, box

from pipeline.rdlp import regions_intersecting_bbox, layer_name_for_region

TO_METRIC = Transformer.from_crs(4326, 2180, always_xy=True)
TILE_M = 10000


def search_tiles(lat, lon, radius_km):
    """Aligned tile bboxes (N,E,N,E) whose interior intersects the disk.

    Distance-to-box avoids approximating the circle with a polygon buffer.
    Alignment allows nearby searches to reuse cache entries.
    """
    if not (math.isfinite(lat) and -90 <= lat <= 90 and
            math.isfinite(lon) and -180 <= lon <= 180 and
            math.isfinite(radius_km) and 10 <= radius_km <= 50):
        raise ValueError("Coordinates must be finite WGS84; radius must be 10–50 km")
    e, n = TO_METRIC.transform(lon, lat)
    radius = radius_km * 1000
    if not (math.isfinite(e) and math.isfinite(n)):
        raise ValueError("Coordinates cannot be projected to EPSG:2180")
    point = Point(e, n)
    tiles = []
    for south in range(math.floor((n-radius)/TILE_M)*TILE_M, math.ceil((n+radius)/TILE_M)*TILE_M, TILE_M):
        for west in range(math.floor((e-radius)/TILE_M)*TILE_M, math.ceil((e+radius)/TILE_M)*TILE_M, TILE_M):
            if box(west, south, west+TILE_M, south+TILE_M).distance(point) < radius:
                tiles.append((south, west, south+TILE_M, west+TILE_M))
    return point, tiles


def merge_frames(frames, keys=None):
    """Merge full source geometries in one CRS, removing repeated features."""
    frames = [frame.to_crs(2180) for frame in frames if len(frame)]
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=2180)
    result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=2180)
    if keys:
        result = result.drop_duplicates(subset=keys)
    else:
        # Including geometry preserves OSM node/way IDs from separate namespaces.
        result = result.assign(_geometry_key=result.geometry.to_wkb())
        cols = (["osm_id"] if "osm_id" in result else []) + ["_geometry_key"]
        result = result.drop_duplicates(subset=cols).drop(columns="_geometry_key")
    return result.reset_index(drop=True)


def within_radius(stands, center, radius_km):
    """Select by metric centroid; retain the entire original stand polygon."""
    if not len(stands):
        return stands.copy()
    metric = stands.to_crs(2180)
    return metric.loc[metric.geometry.centroid.distance(center) <= radius_km*1000].copy().reset_index(drop=True)


def fetch_search_stands(tiles, rdlp, cache_dir, fetcher):
    """Fetch every intersected RDLP per tile, with layer-specific v2 cache.

    Legacy centered-tile caches cannot prove coverage or source layer and are
    deliberately not reused. Failures propagate; no partial result is exported.
    """
    frames, layers = [], set()
    for index, bbox in enumerate(tiles, 1):
        for region in sorted(set(regions_intersecting_bbox(bbox, rdlp))):
            layer = layer_name_for_region(region)
            layers.add(layer)
            layer_key = hashlib.sha256(layer.encode("utf-8")).hexdigest()[:16]
            cache_path = Path(cache_dir) / "bdl_tiles_v2" / layer_key / f"E{bbox[1]}N{bbox[0]}S{TILE_M}.parquet"
            print(f"BDL {index}/{len(tiles)}: {region} ({'cache' if cache_path.exists() else 'WFS'})", flush=True)
            if cache_path.exists():
                frame = gpd.read_parquet(cache_path)
            else:
                frame = fetcher(layer, bbox)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temp = cache_path.with_suffix(".tmp.parquet")
                frame.to_parquet(temp)
                temp.replace(cache_path)
            frames.append(frame)
    return merge_frames(frames, ["adr_for", "a_year"]), sorted(layers)
