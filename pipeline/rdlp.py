import io
import pathlib

import geopandas as gpd
import requests
from shapely.geometry import Point, box as shapely_box

DEFAULT_WFS_URL = "https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows"
RDLP_LAYER = "BDL:RDLP"


def fetch_rdlp_boundaries(base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame:
    """All 17 RDLP (regional forest directorate) boundary polygons in one
    unpaginated WFS 2.0.0 GetFeature call -- verified live 2026-09-24: 17
    features, ~11.4 MB, EPSG:2180, region_name attribute e.g. "KATOWICE".
    Small and slow-changing enough that no bbox filter or pagination is
    needed, unlike pipeline.bdl.fetch_bdl's per-tile wydzielenia fetch."""
    resp = requests.get(base_url, params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": RDLP_LAYER, "outputFormat": "application/json",
    }, timeout=60)
    resp.raise_for_status()
    return gpd.read_file(io.BytesIO(resp.content))


def layer_name_for_region(region_name: str) -> str:
    """Maps a BDL:RDLP `region_name` value (e.g. "ZIELONA GORA") to its
    wydzielenia WFS layer name (e.g. "BDL:RDLP_Zielona_Gora_wydzielenia").
    Verified live 2026-09-24 against all 17 real layer names from
    GetCapabilities -- region_name.title().replace(" ", "_") matches every
    one, including multi-word names."""
    return "BDL:RDLP_" + region_name.title().replace(" ", "_") + "_wydzielenia"


def resolve_rdlp_layer(lat: float, lon: float, rdlp_gdf: gpd.GeoDataFrame) -> str | None:
    """Which wydzielenia WFS layer covers (lat, lon), by point-in-polygon
    lookup against fetch_rdlp_boundaries' output. None if the point falls
    outside every RDLP polygon (outside Poland, or in the sea) -- BDL has
    no data to query there, and callers must treat that as a hard stop,
    not a silent fallback to some layer."""
    point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(rdlp_gdf.crs).iloc[0]
    hits = rdlp_gdf[rdlp_gdf.geometry.covers(point)]
    if len(hits) == 0:
        return None
    return layer_name_for_region(hits.iloc[0]["region_name"])


def fetch_rdlp_boundaries_cached(cache_dir, base_url: str = DEFAULT_WFS_URL) -> gpd.GeoDataFrame:
    """Existence-only cache (same pattern as pipeline.bdl.save_bdl_tile /
    the notebook's _cached_bdl_fetcher): RDLP boundaries change on the
    order of years, so no age check -- delete
    cache/rdlp_boundaries.parquet manually to force a refetch."""
    cache_dir = pathlib.Path(cache_dir)
    cache_path = cache_dir / "rdlp_boundaries.parquet"
    if cache_path.exists():
        return gpd.read_parquet(cache_path)
    gdf = fetch_rdlp_boundaries(base_url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(cache_path)
    return gdf


def regions_intersecting_bbox(bbox_2180: tuple, rdlp_gdf: gpd.GeoDataFrame) -> list[str]:
    """All region_name values whose RDLP polygon intersects the given
    (n_min, e_min, n_max, e_max) EPSG:2180 bbox (pipeline.tiles.tile_bbox_2180's
    shape) -- not just the one covering the bbox's center. A 10x10 km tile
    near an RDLP border can genuinely straddle two directorates;
    resolve_rdlp_layer alone would silently only ever fetch one of them
    (final review finding, prepare_trip CLI plan)."""
    n_min, e_min, n_max, e_max = bbox_2180
    tile_box = shapely_box(e_min, n_min, e_max, n_max)
    metric = rdlp_gdf.to_crs("EPSG:2180")
    hits = metric[metric.geometry.intersects(tile_box)]
    return hits["region_name"].tolist()
