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


def test_build_overpass_query_includes_unpaved_tracks_for_routing():
    # Was "excludes unpaved tracks" -- that exclusion is real and still
    # applies to the euclidean d_park estimate (spec §4.5, "publicznej
    # drogi utwardzonej"), but it now happens by filtering
    # pipeline.mvp.enrich_with_mvp_layers's paved-only subset (Task 5), not
    # by leaving tracks out of the Overpass query entirely -- routing a
    # walking path from an entrance into forest interior needs them.
    q = build_overpass_query(BBOX_4326, PROFILE)
    assert "track" in q
    assert "path" in q


ELEMENTS = [
    {"type": "node", "id": 1, "lat": 50.51, "lon": 18.60, "tags": {"amenity": "parking"}},
    {
        "type": "way", "id": 2, "tags": {"highway": "track"},
        "geometry": [{"lat": 50.520, "lon": 18.610}, {"lat": 50.521, "lon": 18.611}, {"lat": 50.522, "lon": 18.612}],
    },
    {"type": "node", "id": 3, "lat": 50.53, "lon": 18.62, "tags": {"place": "village", "name": "Kieleczka", "population": "450"}},
    {"type": "node", "id": 4, "lat": 50.54, "lon": 18.63, "tags": {"place": "hamlet", "name": "Bez ludzi"}},  # no population tag
    {"type": "way", "id": 5, "tags": {"highway": "residential"}, "geometry": [{"lat": 50.50, "lon": 18.55}]},  # degenerate: 1 point
]


def test_parse_osm_elements_splits_into_parking_roads_places():
    frames = parse_osm_elements(ELEMENTS)
    assert set(frames) == {"parking", "roads", "places"}
    assert len(frames["parking"]) == 1
    assert len(frames["roads"]) == 1  # element 5 (1-point geometry) is dropped, not a valid line
    assert len(frames["places"]) == 2


def test_parse_osm_elements_coerces_missing_population_to_zero():
    frames = parse_osm_elements(ELEMENTS)
    pop_by_name = dict(zip(frames["places"]["name"], frames["places"]["population"]))
    assert pop_by_name["Kieleczka"] == pytest.approx(450.0)
    assert pop_by_name["Bez ludzi"] == pytest.approx(0.0)


def test_parse_osm_elements_builds_way_linestring_geometry():
    frames = parse_osm_elements(ELEMENTS)
    road_geom = frames["roads"].geometry.iloc[0]
    assert road_geom.geom_type == "LineString"
    assert list(road_geom.coords) == [(18.610, 50.520), (18.611, 50.521), (18.612, 50.522)]


def test_parse_osm_elements_skips_way_with_fewer_than_two_geometry_points():
    frames = parse_osm_elements(ELEMENTS)
    # element 5's highway=residential way has only 1 geometry point --
    # can't form a LineString, so it must be dropped rather than crash.
    assert len(frames["roads"]) == 1


def test_fetch_osm_features_uses_injected_call_api_and_reprojects_to_2180():
    captured = {}

    def fake_call_api(query):
        captured["query"] = query
        return {"elements": ELEMENTS}

    frames = fetch_osm_features(BBOX_2180, PROFILE, call_api=fake_call_api)

    assert "query" in captured
    assert frames["places"].crs.to_epsg() == 2180
