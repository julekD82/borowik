import json
import geopandas as gpd
import pandas as pd
import responses

from pipeline.bdl import build_wfs_url, fetch_bdl, save_bdl_tile, DEFAULT_WFS_URL

BBOX = (486000.0, 380000.0, 496000.0, 390000.0)
LAYER = "BDL:RDLP_Katowice_wydzielenia"


def _feature(fid, adr_for):
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380100, 486100], [380200, 486100], [380200, 486200], [380100, 486200], [380100, 486100]]]},
        "properties": {
            "adr_for": adr_for, "area_type": "D-STAN", "site_type": "BMSW",
            "species_cd": "SO", "part_cd": 10, "spec_age": 60, "a_year": 2026,
        },
    }


def test_build_wfs_url_contains_bbox_and_paging_params():
    url = build_wfs_url(LAYER, BBOX, start_index=1000, count=500)
    assert url.startswith(DEFAULT_WFS_URL)
    assert "typeNames=BDL%3ARDLP_Katowice_wydzielenia" in url or "typeNames=BDL:RDLP_Katowice_wydzielenia" in url
    assert "startIndex=1000" in url
    assert "count=500" in url
    assert "urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180" in url or "urn:ogc:def:crs:EPSG::2180" in url


@responses.activate
def test_fetch_bdl_paginates_until_short_page():
    page1 = {"type": "FeatureCollection", "features": [_feature(1, "08-01-1-01-108"), _feature(2, "08-01-1-01-109")]}
    page2 = {"type": "FeatureCollection", "features": [_feature(3, "08-01-1-01-110")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=page1, status=200)
    responses.add(responses.GET, DEFAULT_WFS_URL, json=page2, status=200)

    gdf = fetch_bdl(LAYER, BBOX, page_size=2)

    assert len(gdf) == 3
    assert list(gdf["adr_for"]) == ["08-01-1-01-108", "08-01-1-01-109", "08-01-1-01-110"]
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_bdl_coerces_string_part_cd_to_numeric():
    # The live BDL WFS returns part_cd as a string attribute (GeoJSON/GML
    # typing); fetch_bdl should normalize it to numeric so downstream
    # arithmetic in pipeline.habitat (score_host, passes_mask) doesn't break.
    feature = _feature(1, "08-01-1-01-108")
    feature["properties"]["part_cd"] = "10"
    page = {"type": "FeatureCollection", "features": [feature]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=page, status=200)

    gdf = fetch_bdl(LAYER, BBOX, page_size=10)

    assert pd.api.types.is_numeric_dtype(gdf["part_cd"])
    assert gdf["part_cd"].iloc[0] == 10


def test_save_bdl_tile_writes_geoparquet(tmp_path):
    gdf = gpd.GeoDataFrame.from_features([_feature(1, "08-01-1-01-108")])
    gdf = gdf.set_crs("EPSG:2180")

    out_path = save_bdl_tile(gdf, "E380N486", tmp_path)

    assert out_path.exists()
    reloaded = gpd.read_parquet(out_path)
    assert len(reloaded) == 1
