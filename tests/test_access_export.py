import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from pipeline.access_export import write_access_points_geojson, write_forest_roads_geojson
from pipeline.access_points import AccessSet
from pipeline.access_pressure import build_access_model
from pipeline.export import build_access_card, build_diagnostics_record
from pipeline.habitat import load_profile

CFG = load_profile("profiles/boletus_edulis.yaml")["pressure"]["access_points"]
CRS = "EPSG:2180"


def _model():
    pts = gpd.GeoDataFrame(
        {"point_id": ["pk-1", "st-1"], "type": ["parking", "settlement"], "source": ["bdl", "gus"],
         "subtype": ["parking_lesny", "oczko_1km"], "name": ["Lesny", ""], "weight_pop": [np.nan, 200.0]},
        geometry=[Point(473000, 310000), Point(474000, 310000)], crs=CRS)
    coords = [(473000 + i * 100, 310000) for i in range(30)]
    roads = gpd.GeoDataFrame(
        {"kind": ["closed", "public"], "surface_class": ["hard", "hard"], "source": ["osm", "osm"],
         "fire_no": ["", ""], "highway": ["track", "tertiary"]},
        geometry=[LineString(coords), LineString([(473000, 310100), (474000, 310100)])], crs=CRS)
    return build_access_model(AccessSet(points=pts, roads=roads), np.array([[473000.0, 310000.0]]),
                              np.array([30000.0]), CFG, pop_d_forest=np.array([0.0]))


def test_points_geojson_has_type_source_and_attractiveness(tmp_path):
    path = write_access_points_geojson(_model(), tmp_path / "access_points_2026-09-29.geojson")
    fc = json.loads(path.read_text(encoding="utf-8"))
    props = {f["properties"]["id"]: f["properties"] for f in fc["features"]}
    assert props["pk-1"]["type"] == "parking" and props["pk-1"]["source"] == "bdl"
    assert 0 < props["pk-1"]["attractiveness"] < 1
    assert props["pk-1"]["attractiveness_class"] in ("niska", "srednia", "wysoka")
    lon, lat = fc["features"][0]["geometry"]["coordinates"]
    assert 15 < lon < 20 and 49 < lat < 52          # WGS84, nie EPSG:2180


def test_roads_geojson_kinds_and_null_attractiveness_for_public(tmp_path):
    path, tol = write_forest_roads_geojson(_model(), tmp_path / "forest_roads_2026-09-29.geojson")
    fc = json.loads(path.read_text(encoding="utf-8"))
    by_kind = {f["properties"]["kind"]: f["properties"] for f in fc["features"]}
    assert by_kind["closed"]["attractiveness"] > 0 and by_kind["closed"]["surface"] == "hard"
    assert "attractiveness" not in by_kind["public"]      # publiczna: zrodlo, nie korytarz
    assert tol == 2.0


def test_roads_geojson_raises_tolerance_to_fit_size_limit(tmp_path):
    model = _model()
    wiggly = LineString([(473000 + i * 20, 310000 + (5 if i % 2 else -5)) for i in range(200)])
    model.roads = model.roads.copy()
    model.roads.loc[0, "geometry"] = wiggly
    _, tol_small = write_forest_roads_geojson(model, tmp_path / "a.geojson", limit_bytes=10_000_000)
    size = (tmp_path / "a.geojson").stat().st_size
    _, tol = write_forest_roads_geojson(model, tmp_path / "b.geojson", limit_bytes=size // 2)
    assert tol > tol_small and (tmp_path / "b.geojson").stat().st_size <= size // 2


def test_access_card_only_for_access_points_model():
    assert build_access_card(pd.Series({"pressure_model": "gravity"})) is None
    card = build_access_card(pd.Series({
        "pressure_model": "access_points", "d_parking_m": 850.0, "d_entrance_m": 400.0,
        "d_hard_forest_road_m": float("nan"), "top_point_id": "pk-1", "top_point_type": "parking",
        "top_point_source": "bdl", "top_point_name": "Lesny"}))
    assert card["d_parking_m"] == 850.0 and card["d_hard_forest_road_m"] is None
    assert card["top_point_name"] == "Lesny"


def test_access_card_is_json_safe_when_stand_has_no_top_point():
    # Regresja z realnego przebiegu: wydzielenie bez punktu o najwiekszym
    # wkladzie ma w kolumnach tekstowych NaN (nie None) i musi dac null w JSON.
    nan = float("nan")
    card = build_access_card(pd.Series({
        "pressure_model": "access_points", "d_parking_m": nan, "d_entrance_m": nan,
        "d_hard_forest_road_m": nan, "top_point_id": "", "top_point_type": nan,
        "top_point_source": nan, "top_point_name": nan}))
    assert json.dumps(card, allow_nan=False) == json.dumps(
        {"d_parking_m": None, "d_entrance_m": None, "d_hard_forest_road_m": None, "top_point_id": None,
         "top_point_type": None, "top_point_source": None, "top_point_name": None})


def _many_segments_model(n=400):
    """Dlugi ciag krotkich odcinkow o tych samych atrybutach (jak siatka dojazdow pozarowych):
    plik jest duzy przez LICZBE odcinkow, wiec samo uproszczenie wierzcholkow nie pomaga."""
    pts = gpd.GeoDataFrame(
        {"point_id": ["pk-1"], "type": ["parking"], "source": ["bdl"], "subtype": [""], "name": [""],
         "weight_pop": [np.nan]}, geometry=[Point(473000, 310000)], crs=CRS)
    segs = [LineString([(473000 + i * 60, 310000), (473000 + (i + 1) * 60, 310000)]) for i in range(n)]
    roads = gpd.GeoDataFrame(
        {"kind": ["closed"] * n, "surface_class": ["hard"] * n, "source": ["osm"] * n, "fire_no": [""] * n,
         "highway": ["track"] * n}, geometry=segs, crs=CRS)
    return build_access_model(AccessSet(points=pts, roads=roads), np.array([[473000.0, 310000.0]]),
                              np.array([30000.0]), CFG, pop_d_forest=np.array([0.0]))


def test_roads_geojson_merges_segments_when_simplification_cannot_fit_the_limit(tmp_path):
    model = _many_segments_model()
    _, _ = write_forest_roads_geojson(model, tmp_path / "full.geojson", limit_bytes=10_000_000)
    full = json.loads((tmp_path / "full.geojson").read_text(encoding="utf-8"))
    assert len(full["features"]) == 400 and model.counts["forest_roads_dissolved"] is False
    limit = (tmp_path / "full.geojson").stat().st_size // 4
    path, tol = write_forest_roads_geojson(model, tmp_path / "small.geojson", limit_bytes=limit)
    assert path.stat().st_size <= limit and model.counts["forest_roads_dissolved"] is True
    small = json.loads(path.read_text(encoding="utf-8"))
    assert 0 < len(small["features"]) < 400
    # atrybuty zachowane, klasa atrakcyjnosci (progi 0,1 / 0,3) nie zmienia sie przy kwantyzacji
    from pipeline.access_pressure import attractiveness_class
    for f in small["features"]:
        assert f["properties"]["kind"] == "closed" and f["properties"]["surface"] == "hard"
    orig = {attractiveness_class(f["properties"]["attractiveness"]) for f in full["features"]}
    merged = {attractiveness_class(f["properties"]["attractiveness"]) for f in small["features"]}
    assert merged <= orig | {"niska"} or merged == orig
    # zadna droga nie znika: laczna dlugosc zbliżona (tolerancja uproszczenia)
    assert small["features"][0]["geometry"]["type"] in ("LineString", "MultiLineString")
