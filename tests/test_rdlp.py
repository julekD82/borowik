import responses

from pipeline.rdlp import fetch_rdlp_boundaries, layer_name_for_region, DEFAULT_WFS_URL

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
