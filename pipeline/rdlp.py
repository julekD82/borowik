import io

import geopandas as gpd
import requests

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
