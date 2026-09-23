import math
import geopandas as gpd
import pytest
from shapely.geometry import Point

from pipeline.habitat import load_profile
from pipeline.pressure import nearest_distance_m, compute_d_park, compute_demand, compute_pressure

PROFILE = load_profile("profiles/boletus_edulis.yaml")
CENTROID = Point(385000.0, 491000.0)


def test_nearest_distance_m_returns_min_distance():
    points = gpd.GeoDataFrame(geometry=[Point(385000.0, 491100.0), Point(385000.0, 491500.0)], crs="EPSG:2180")
    assert nearest_distance_m(CENTROID, points) == pytest.approx(100.0)


def test_nearest_distance_m_none_when_no_points():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    assert nearest_distance_m(CENTROID, empty) is None
    assert nearest_distance_m(CENTROID, None) is None


def test_compute_d_park_takes_closer_of_parking_or_road_times_euclid_factor():
    parking = gpd.GeoDataFrame(geometry=[Point(385000.0, 491200.0)], crs="EPSG:2180")  # 200 m
    roads = gpd.GeoDataFrame(geometry=[Point(385000.0, 491050.0)], crs="EPSG:2180")     # 50 m, closer
    d = compute_d_park(CENTROID, parking, roads, euclid_factor=1.3)
    assert d == pytest.approx(50.0 * 1.3)


def test_compute_d_park_none_when_neither_source_has_points():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    assert compute_d_park(CENTROID, empty, empty, euclid_factor=1.3) is None


def test_compute_demand_sums_gravity_weighted_population():
    places = gpd.GeoDataFrame(
        {"population": [1000.0, 500.0]},
        geometry=[Point(385000.0, 491000.0 + 10000.0), Point(385000.0, 491000.0 + 20000.0)],  # 10km, 20km
        crs="EPSG:2180",
    )
    demand = compute_demand(CENTROID, places, decay_km=10.0)
    expected = 1000.0 / (1 + (10.0 / 10.0) ** 2) + 500.0 / (1 + (20.0 / 10.0) ** 2)
    assert demand == pytest.approx(expected)


def test_compute_demand_zero_when_no_places():
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    assert compute_demand(CENTROID, empty, decay_km=10.0) == 0.0


def test_compute_pressure_matches_formula():
    p = compute_pressure(d_park=400.0, demand=50.0, demand_max=100.0, profile=PROFILE)
    cfg = PROFILE["pressure"]
    expected = 1 - math.exp(-cfg["k"] * (50.0 / 100.0) * math.exp(-400.0 / cfg["park_decay_m"]))
    assert p == pytest.approx(expected)


def test_compute_pressure_zero_demand_max_does_not_raise():
    p = compute_pressure(d_park=400.0, demand=0.0, demand_max=0.0, profile=PROFILE)
    assert p == pytest.approx(0.0)


def test_compute_pressure_none_d_park_treated_as_very_far():
    p = compute_pressure(d_park=None, demand=100.0, demand_max=100.0, profile=PROFILE)
    assert p == pytest.approx(0.0, abs=1e-6)
