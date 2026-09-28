import json

import pytest
from shapely.geometry import LineString, Point

from pipeline.access_data import (
    _decode_bdl_bytes, build_access_overpass_query, fetch_bdl_fire_roads, fetch_bdl_parkings,
    load_access_sources, parse_access_osm_elements,
)
from pipeline.habitat import load_profile

CFG = load_profile("profiles/boletus_edulis.yaml")["pressure"]["access_points"]


def _feature(code, x, y, oid, name="X"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
            "properties": {"objectid": oid, "tur_rec_pnt_cd": code, "nzw_ob": name}}


def test_decode_falls_back_to_cp1250_for_bdl_polish_letters():
    raw = '{"n":"Leśny"}'.encode("cp1250")
    assert json.loads(_decode_bdl_bytes(raw))["n"] == "Leśny"
    assert json.loads(_decode_bdl_bytes('{"n":"Leśny"}'.encode("utf-8")))["n"] == "Leśny"


def test_fetch_bdl_parkings_keeps_only_parking_codes():
    feats = [_feature("PARKING", 1, 2, 1), _feature("MSC POST", 3, 4, 2),
             _feature("MSC WYPOCZ", 5, 6, 3), _feature("PL ZABAW", 7, 8, 4)]
    gdf = fetch_bdl_parkings((0, 0, 10, 10), get=lambda *a: {"features": feats})
    assert sorted(gdf["subtype"]) == ["miejsce_postoju", "parking_lesny"]
    assert gdf.crs.to_epsg() == 2180


def test_fetch_bdl_pagination_stops_when_server_repeats_page():
    calls = []

    def get(service, type_name, bbox, start):
        calls.append(start)
        return {"features": [_feature("PARKING", 1, 2, 1)]}  # ignoruje startIndex

    gdf = fetch_bdl_parkings((0, 0, 10, 10), get=get)
    assert len(gdf) == 1 and len(calls) <= 2


def test_fetch_bdl_fire_roads_splits_multilinestring_and_keeps_number():
    feat = {"type": "Feature",
            "geometry": {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[5, 5], [6, 6]]]},
            "properties": {"objectid": 9, "nr_ppoz": " 72 "}}
    gdf = fetch_bdl_fire_roads((0, 0, 10, 10), get=lambda *a: {"features": [feat]})
    assert len(gdf) == 2 and set(gdf["fire_no"]) == {"72"}
    assert all(g.geom_type == "LineString" for g in gdf.geometry)


def test_overpass_query_has_roads_and_barriers_but_no_parking_aisles():
    q = build_access_overpass_query((50.0, 18.0, 50.1, 18.1), CFG)
    assert 'node["barrier"' in q and "gate|lift_gate" in q
    assert "parking_aisle" in q and "track" in q and q.endswith("out geom;")


def test_parse_access_osm_elements_reads_surface_tags_and_gates():
    elements = [
        {"type": "way", "id": 1, "tags": {"highway": "track", "surface": "gravel", "tracktype": "grade2"},
         "geometry": [{"lat": 50.0, "lon": 18.0}, {"lat": 50.001, "lon": 18.0}]},
        {"type": "node", "id": 2, "lat": 50.0, "lon": 18.0, "tags": {"barrier": "gate", "access": "forestry"}},
        {"type": "way", "id": 3, "tags": {"building": "yes"}, "geometry": [{"lat": 1, "lon": 1}, {"lat": 2, "lon": 2}]},
    ]
    out = parse_access_osm_elements(elements)
    assert len(out["roads"]) == 1 and out["roads"]["surface"].iloc[0] == "gravel"
    assert len(out["gates"]) == 1 and out["gates"]["access"].iloc[0] == "forestry"


def _osm_elements():
    return {"elements": [
        {"type": "way", "id": 1, "tags": {"highway": "track"},
         "geometry": [{"lat": 50.5, "lon": 18.6}, {"lat": 50.501, "lon": 18.6}]},
    ]}


def test_load_access_sources_caches_tiles_and_reports_failures(tmp_path):
    tiles = [(300000, 470000, 310000, 480000), (310000, 470000, 320000, 480000)]
    bdl_calls, osm_calls = [], []

    def bdl_get(service, type_name, bbox, start):
        bdl_calls.append(bbox)
        return {"features": []}

    def osm_call(query):
        osm_calls.append(query)
        return _osm_elements()

    first = load_access_sources(tiles, tmp_path, CFG, osm_call, bdl_get=bdl_get)
    assert first["failed"] == {"bdl": [], "osm": []} and len(first["osm_roads"]) >= 1
    n_bdl, n_osm = len(bdl_calls), len(osm_calls)
    second = load_access_sources(tiles, tmp_path, CFG, osm_call, bdl_get=bdl_get)
    assert len(bdl_calls) == n_bdl and len(osm_calls) == n_osm          # drugi przebieg z cache
    assert second["cache_hits"] == {"bdl": 2, "osm": 2}


def test_load_access_sources_stops_osm_after_first_failure_but_continues_bdl(tmp_path):
    tiles = [(300000, 470000, 310000, 480000), (310000, 470000, 320000, 480000), (320000, 470000, 330000, 480000)]
    osm_calls = []

    def osm_call(query):
        osm_calls.append(1)
        raise RuntimeError("504")

    out = load_access_sources(tiles, tmp_path, CFG, osm_call, bdl_get=lambda *a: {"features": []})
    assert len(osm_calls) == 1                        # po pierwszym bledzie nie mecz serwera
    assert len(out["failed"]["osm"]) == 3 and out["failed"]["bdl"] == []
