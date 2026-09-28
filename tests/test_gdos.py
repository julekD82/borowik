import geopandas as gpd
import pandas as pd
import responses
from shapely.geometry import box

from shapely.geometry import Point

from pipeline.gdos import fetch_protected_areas, mark_gdos_blocked, gdos_status, DEFAULT_GDOS_WFS_URL

BBOX = (486000.0, 380000.0, 496000.0, 390000.0)


def _reserve_feature(fid, name):
    return {
        "type": "Feature", "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [[[380100, 486100], [380200, 486100], [380200, 486200], [380100, 486200], [380100, 486100]]]},
        "properties": {"nazwa": name},
    }


@responses.activate
def test_fetch_protected_areas_combines_both_gdos_layers():
    reserves = {"type": "FeatureCollection", "features": [_reserve_feature(1, "Rez. Test")]}
    parks = {"type": "FeatureCollection", "features": []}
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=reserves, status=200)
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=parks, status=200)

    gdf = fetch_protected_areas(BBOX)

    assert len(gdf) == 1
    assert gdf.iloc[0]["nazwa"] == "Rez. Test"


@responses.activate
def test_fetch_protected_areas_handles_no_hits_in_either_layer():
    empty = {"type": "FeatureCollection", "features": []}
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=empty, status=200)
    responses.add(responses.GET, DEFAULT_GDOS_WFS_URL, json=empty, status=200)

    gdf = fetch_protected_areas(BBOX)

    assert len(gdf) == 0


def _stands_gdf():
    return gpd.GeoDataFrame(
        {"stand_id": ["A", "B"]},
        geometry=[box(380100, 486100, 380200, 486200), box(381000, 487000, 381100, 487100)],
        crs="EPSG:2180",
    )


def test_mark_gdos_blocked_flags_intersecting_stand_only():
    protected = gpd.GeoDataFrame(
        {"nazwa": ["Rez. Test"]},
        geometry=[box(380150, 486150, 380250, 486250)],  # overlaps stand A, not B
        crs="EPSG:2180",
    )
    blocked = mark_gdos_blocked(_stands_gdf(), protected)
    assert blocked.tolist() == [True, False]


def test_mark_gdos_blocked_all_false_when_no_protected_areas():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    blocked = mark_gdos_blocked(_stands_gdf(), empty)
    assert blocked.tolist() == [False, False]


# --- Plan 1.6: gdos_status ---------------------------------------------------

def test_gdos_status_brak_when_not_blocked_and_no_failed_tile():
    assert gdos_status(False, Point(500.0, 500.0), []) == "brak"


def test_gdos_status_blokada_when_blocked():
    assert gdos_status(True, Point(500.0, 500.0), []) == "blokada"


def test_gdos_status_kafel_pominiety_when_centroid_falls_in_a_failed_tile():
    failed_tiles = [(0.0, 0.0, 1000.0, 1000.0)]  # (n_min, e_min, n_max, e_max)
    assert gdos_status(False, Point(500.0, 500.0), failed_tiles) == "kafel_pominiety"


def test_gdos_status_kafel_pominiety_takes_priority_over_blokada():
    # mark_gdos_blocked's own optimistic fallback means "blocked" can only
    # ever be True here from a tile that DID succeed -- but if this stand's
    # own home tile is in the failed list, the honest status is "we don't
    # actually know", not "confirmed blocked".
    failed_tiles = [(0.0, 0.0, 1000.0, 1000.0)]
    assert gdos_status(True, Point(500.0, 500.0), failed_tiles) == "kafel_pominiety"


def test_gdos_status_outside_any_failed_tile_falls_through_to_brak_or_blokada():
    failed_tiles = [(0.0, 0.0, 1000.0, 1000.0)]
    assert gdos_status(False, Point(5000.0, 5000.0), failed_tiles) == "brak"


def test_gdos_status_handles_none_failed_tiles():
    assert gdos_status(False, Point(500.0, 500.0), None) == "brak"
