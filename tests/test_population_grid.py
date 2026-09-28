import math

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.habitat import load_profile
from pipeline.population_grid import load_population_points, impute_osm_population

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _write_grid(path, rows):
    """Synthetic GUS-shaped 1km-cell grid: one 1000m square polygon per row,
    `tot` population field (None = statistically suppressed cell), EPSG:2180
    -- matches the real zasob 24532 export's own CRS and field name."""
    gdf = gpd.GeoDataFrame(
        [{"tot": r["tot"]} for r in rows],
        geometry=[box(r["e"], r["n"], r["e"] + 1000.0, r["n"] + 1000.0) for r in rows],
        crs="EPSG:2180",
    )
    gdf.to_file(path, driver="GeoJSON")


def test_load_population_points_returns_none_for_missing_file(tmp_path):
    assert load_population_points(tmp_path / "does_not_exist.geojson", (0, 0, 1000, 1000)) is None


def test_load_population_points_filters_by_bbox_and_uses_cell_centroids(tmp_path):
    path = tmp_path / "grid.geojson"
    _write_grid(path, [
        {"e": 0.0, "n": 0.0, "tot": 100},       # inside bbox
        {"e": 50_000.0, "n": 50_000.0, "tot": 200},  # far outside bbox
    ])
    points = load_population_points(path, (-500.0, -500.0, 1500.0, 1500.0))
    assert len(points) == 1
    assert points.iloc[0]["population"] == pytest.approx(100.0)
    # Centroid of the 0,0 - 1000,1000 square is (500, 500).
    assert points.iloc[0].geometry.x == pytest.approx(500.0)
    assert points.iloc[0].geometry.y == pytest.approx(500.0)
    assert str(points.crs).endswith("2180")


def test_load_population_points_drops_and_counts_suppressed_cells(tmp_path):
    path = tmp_path / "grid.geojson"
    _write_grid(path, [
        {"e": 0.0, "n": 0.0, "tot": 100},
        {"e": 100.0, "n": 100.0, "tot": None},  # statistically suppressed
    ])
    points = load_population_points(path, (-500.0, -500.0, 1500.0, 1500.0))
    assert len(points) == 1  # the suppressed cell is dropped, not treated as 0
    assert points.attrs["missing_count"] == 1
    assert points.attrs["cell_count"] == 1


# --- OSM fallback imputation ------------------------------------------------

def _places(rows):
    return gpd.GeoDataFrame(
        [{"place": r["place"], "population": r["population"]} for r in rows],
        geometry=[box(0, 0, 1, 1)] * len(rows),
        crs="EPSG:2180",
    )


def test_impute_osm_population_fills_missing_by_class():
    places = _places([{"place": "village", "population": float("nan")},
                       {"place": "city", "population": float("nan")}])
    result = impute_osm_population(places, PROFILE)
    assert result.iloc[0]["population"] == pytest.approx(500.0)
    assert result.iloc[0]["population_source"] == "osm_z_imputacja"
    assert result.iloc[1]["population"] == pytest.approx(50000.0)


def test_impute_osm_population_leaves_real_values_and_marks_source():
    places = _places([{"place": "town", "population": 12345.0}])
    result = impute_osm_population(places, PROFILE)
    assert result.iloc[0]["population"] == pytest.approx(12345.0)
    assert result.iloc[0]["population_source"] == "osm"


def test_impute_osm_population_unlisted_class_falls_back_to_zero_not_a_guess():
    places = _places([{"place": "isolated_dwelling", "population": float("nan")}])
    result = impute_osm_population(places, PROFILE)
    assert result.iloc[0]["population"] == pytest.approx(0.0)


def test_impute_osm_population_handles_none_and_empty():
    assert impute_osm_population(None, PROFILE) is None
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    assert len(impute_osm_population(empty, PROFILE)) == 0
