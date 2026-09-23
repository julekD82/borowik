import pandas as pd
import pytest

from pipeline.habitat import load_profile
from pipeline.osm import build_overpass_query, parse_osm_elements, fetch_osm_features

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX_4326 = (50.50, 18.55, 50.55, 18.65)  # south, west, north, east
BBOX_2180 = (486000.0, 380000.0, 496000.0, 390000.0)


def test_build_overpass_query_includes_bbox_and_configured_filters():
    q = build_overpass_query(BBOX_4326, PROFILE)
    assert "50.5,18.55,50.55,18.65" in q
    assert 'amenity"="parking"' in q
    assert "secondary" in q  # from profile.osm.road_highway_types
    assert "village" in q  # from profile.osm.place_types


def test_build_overpass_query_excludes_unpaved_tracks():
    # Spec §4.5 defines d_park against "publicznej drogi utwardzonej" (a
    # public PAVED road) -- highway=track is an unpaved forest track,
    # usually closed to cars in Lasy Państwowe forests, and including it
    # made d_park (and so the accessibility half of P) nearly constant
    # across an entire tile (found in live review of a real run).
    q = build_overpass_query(BBOX_4326, PROFILE)
    assert "track" not in q


ELEMENTS = [
    {"type": "node", "id": 1, "lat": 50.51, "lon": 18.60, "tags": {"amenity": "parking"}},
    {"type": "way", "id": 2, "center": {"lat": 50.52, "lon": 18.61}, "tags": {"highway": "track"}},
    {"type": "node", "id": 3, "lat": 50.53, "lon": 18.62, "tags": {"place": "village", "name": "Kieleczka", "population": "450"}},
    {"type": "node", "id": 4, "lat": 50.54, "lon": 18.63, "tags": {"place": "hamlet", "name": "Bez ludzi"}},  # no population tag
]


def test_parse_osm_elements_splits_into_parking_roads_places():
    frames = parse_osm_elements(ELEMENTS)
    assert set(frames) == {"parking", "roads", "places"}
    assert len(frames["parking"]) == 1
    assert len(frames["roads"]) == 1
    assert len(frames["places"]) == 2


def test_parse_osm_elements_coerces_missing_population_to_zero():
    frames = parse_osm_elements(ELEMENTS)
    places = frames["places"].set_index(frames["places"]["name"] if "name" in frames["places"] else frames["places"].index)
    pop_by_name = dict(zip(frames["places"]["name"], frames["places"]["population"]))
    assert pop_by_name["Kieleczka"] == pytest.approx(450.0)
    assert pop_by_name["Bez ludzi"] == pytest.approx(0.0)


def test_parse_osm_elements_uses_way_center_as_geometry():
    frames = parse_osm_elements(ELEMENTS)
    road_point = frames["roads"].geometry.iloc[0]
    assert road_point.x == pytest.approx(18.61)
    assert road_point.y == pytest.approx(50.52)


def test_fetch_osm_features_uses_injected_call_api_and_reprojects_to_2180():
    captured = {}

    def fake_call_api(query):
        captured["query"] = query
        return {"elements": ELEMENTS}

    frames = fetch_osm_features(BBOX_2180, PROFILE, call_api=fake_call_api)

    assert "query" in captured
    assert frames["places"].crs.to_epsg() == 2180
