import io
import pathlib

import geopandas as gpd
import pandas as pd
import requests

from pipeline.tiles import wfs_bbox_param

DEFAULT_WFS_URL = "https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows"


def build_wfs_url(layer: str, bbox: tuple, start_index: int = 0, count: int = 1000,
                   base_url: str = DEFAULT_WFS_URL) -> str:
    req = requests.Request(
        "GET",
        base_url,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "bbox": wfs_bbox_param(bbox),
            "count": count,
            "startIndex": start_index,
        },
    )
    return req.prepare().url


def fetch_bdl(layer: str, bbox: tuple, page_size: int = 1000,
               base_url: str = DEFAULT_WFS_URL,
               session: requests.Session | None = None) -> gpd.GeoDataFrame:
    """Fetch all wydzielenia intersecting bbox from BDL WFS, paginating with
    startIndex/count until a page returns fewer than page_size features."""
    session = session or requests.Session()
    pages = []
    start_index = 0
    while True:
        url = build_wfs_url(layer, bbox, start_index=start_index, count=page_size, base_url=base_url)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        gdf = gpd.read_file(io.BytesIO(resp.content))
        pages.append(gdf)
        if len(gdf) < page_size:
            break
        start_index += page_size
    result = gpd.GeoDataFrame(pd.concat(pages, ignore_index=True), crs=pages[0].crs if pages else "EPSG:2180")
    if "part_cd" in result.columns:
        # The live BDL WFS (GeoJSON/GML attribute typing) returns part_cd as
        # a string column; pipeline.habitat.score_host and passes_mask both
        # do numeric arithmetic/comparisons on it, so normalize it here at
        # the true data-parsing source rather than downstream in every caller.
        result["part_cd"] = pd.to_numeric(result["part_cd"], errors="coerce")
    return result


def save_bdl_tile(gdf: gpd.GeoDataFrame, tile_id: str, cache_dir: pathlib.Path) -> pathlib.Path:
    cache_dir = pathlib.Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{tile_id}.parquet"
    gdf.to_parquet(out_path)
    return out_path
