import geopandas as gpd
import responses
from shapely.geometry import box

from pipeline.rdlp import (
    fetch_rdlp_boundaries, layer_name_for_region, resolve_rdlp_layer,
    fetch_rdlp_boundaries_cached, DEFAULT_WFS_URL,
)

# Verified live 2026-09-24 (see plan Global Constraints): GetCapabilities'
# 17 real BDL:RDLP_<Name>_wydzielenia layer names, and BDL:RDLP's 17 real
# region_name attribute values, in the same RDLP order.
REAL_RDLP_LAYER_NAMES = [
    "BDL:RDLP_Białystok_wydzielenia", "BDL:RDLP_Gdańsk_wydzielenia", "BDL:RDLP_Katowice_wydzielenia",
    "BDL:RDLP_Kraków_wydzielenia", "BDL:RDLP_Krosno_wydzielenia", "BDL:RDLP_Lublin_wydzielenia",
    "BDL:RDLP_Olsztyn_wydzielenia", "BDL:RDLP_Piła_wydzielenia", "BDL:RDLP_Poznań_wydzielenia",
    "BDL:RDLP_Radom_wydzielenia", "BDL:RDLP_Szczecin_wydzielenia", "BDL:RDLP_Szczecinek_wydzielenia",
    "BDL:RDLP_Toruń_wydzielenia", "BDL:RDLP_Warszawa_wydzielenia", "BDL:RDLP_Wrocław_wydzielenia",
    "BDL:RDLP_Zielona_Góra_wydzielenia", "BDL:RDLP_Łódź_wydzielenia",
]
REAL_REGION_NAMES = [
    "BIAŁYSTOK", "GDAŃSK", "KATOWICE", "KRAKÓW", "KROSNO", "LUBLIN", "OLSZTYN", "PIŁA", "POZNAŃ",
    "RADOM", "SZCZECIN", "SZCZECINEK", "TORUŃ", "WARSZAWA", "WROCŁAW", "ZIELONA GÓRA", "ŁÓDŹ",
]


def test_layer_name_for_region_matches_all_17_real_bdl_layers():
    computed = {layer_name_for_region(name) for name in REAL_REGION_NAMES}
    assert computed == set(REAL_RDLP_LAYER_NAMES)


def test_layer_name_for_region_simple_case():
    assert layer_name_for_region("KATOWICE") == "BDL:RDLP_Katowice_wydzielenia"


def _region_feature(fid, region_name):
    return {
        "type": "Feature", "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380000, 486000], [500000, 486000], [500000, 700000], [380000, 700000], [380000, 486000]]]},
        "properties": {"a_year": 2026, "region_cd": "02", "region_name": region_name},
    }


@responses.activate
def test_fetch_rdlp_boundaries_parses_features():
    collection = {"type": "FeatureCollection", "features": [_region_feature(1, "KATOWICE"), _region_feature(2, "KRAKOW")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=collection, status=200)

    gdf = fetch_rdlp_boundaries()

    assert len(gdf) == 2
    assert set(gdf["region_name"]) == {"KATOWICE", "KRAKOW"}


def _rdlp_gdf():
    # Two adjacent, non-overlapping "RDLP" boxes in EPSG:2180 (real BDL
    # CRS), plain ASCII region_name -- layer_name_for_region's diacritic
    # handling is already covered by the regression test above.
    return gpd.GeoDataFrame(
        {"region_name": ["KATOWICE", "KRAKOW"]},
        geometry=[box(380000, 486000, 390000, 496000), box(400000, 486000, 410000, 496000)],
        crs="EPSG:2180",
    )


def test_resolve_rdlp_layer_finds_containing_polygon_box1():
    # WGS84 centroid of box1 (380000,486000,390000,496000), computed via
    # pyproj EPSG:2180 -> EPSG:4326 during planning.
    layer = resolve_rdlp_layer(lat=52.2729723880693, lon=17.314011763359918, rdlp_gdf=_rdlp_gdf())
    assert layer == "BDL:RDLP_Katowice_wydzielenia"


def test_resolve_rdlp_layer_finds_containing_polygon_box2():
    # WGS84 centroid of box2 (400000,486000,410000,496000).
    layer = resolve_rdlp_layer(lat=52.2767943376323, lon=17.607123274159406, rdlp_gdf=_rdlp_gdf())
    assert layer == "BDL:RDLP_Krakow_wydzielenia"


def test_resolve_rdlp_layer_returns_none_outside_every_polygon():
    # Well outside both boxes (roughly (600000, 700000) in EPSG:2180).
    layer = resolve_rdlp_layer(lat=54.15455087660452, lon=20.531757957006068, rdlp_gdf=_rdlp_gdf())
    assert layer is None


@responses.activate
def test_fetch_rdlp_boundaries_cached_writes_and_reuses_cache(tmp_path):
    collection = {"type": "FeatureCollection", "features": [_region_feature(1, "KATOWICE")]}
    responses.add(responses.GET, DEFAULT_WFS_URL, json=collection, status=200)

    first = fetch_rdlp_boundaries_cached(tmp_path)
    assert len(first) == 1
    assert (tmp_path / "rdlp_boundaries.parquet").exists()
    assert len(responses.calls) == 1

    second = fetch_rdlp_boundaries_cached(tmp_path)  # cache hit -- no new HTTP call
    assert len(second) == 1
    assert len(responses.calls) == 1
