import geopandas as gpd
import pytest
from shapely.geometry import box, LineString

from pipeline.entrances import compute_forest_boundary, find_entrance_points


def _stand_row(stand_id, x, area_type="D-STAN"):
    return {"stand_id": stand_id, "area_type": area_type, "geometry": box(x, 486000, x + 1000, 487000)}


def test_compute_forest_boundary_unions_d_stan_stands_only():
    stands = gpd.GeoDataFrame([
        _stand_row("A", 380000, "D-STAN"),
        _stand_row("B", 381000, "D-STAN"),   # adjacent -> merges with A
        _stand_row("C", 390000, "LAKA"),      # non-forest, excluded
    ], crs="EPSG:2180")
    boundary = compute_forest_boundary(stands)
    assert boundary.area == pytest.approx(2 * 1000 * 1000)  # A+B only, merged


def test_compute_forest_boundary_returns_none_when_no_forest_stands():
    stands = gpd.GeoDataFrame([_stand_row("C", 390000, "LAKA")], crs="EPSG:2180")
    assert compute_forest_boundary(stands) is None


def test_find_entrance_points_detects_crossing_road():
    forest = box(380000, 486000, 381000, 487000)
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(379500, 486500), (380500, 486500)])],  # crosses west edge at x=380000
        crs="EPSG:2180",
    )
    entrances = find_entrance_points(forest, roads)
    assert len(entrances) == 1
    pt = entrances.iloc[0].geometry
    assert pt.x == pytest.approx(380000)
    assert pt.y == pytest.approx(486500)


def test_find_entrance_points_ignores_road_entirely_outside():
    forest = box(380000, 486000, 381000, 487000)
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(390000, 486500), (391000, 486500)])],  # far away, no crossing
        crs="EPSG:2180",
    )
    entrances = find_entrance_points(forest, roads)
    assert len(entrances) == 0


def test_find_entrance_points_returns_empty_for_none_boundary():
    roads = gpd.GeoDataFrame({"highway": ["track"]}, geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:2180")
    entrances = find_entrance_points(None, roads)
    assert len(entrances) == 0
