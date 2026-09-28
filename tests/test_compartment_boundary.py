import geopandas as gpd
from shapely.geometry import box

from pipeline.compartment_boundary import compartment_boundary_features


def test_stand_touching_compartment_edge_has_shared_boundary_and_short_distance():
    # Compartment: (0,0)-(2,2). Stand: (0,0)-(1,1) -- shares the compartment's
    # left (x=0) and bottom (y=0) edges over a unit length each.
    stands = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-100   -a   -00"]},
        geometry=[box(0, 0, 1, 1)], crs="EPSG:2180",
    )
    compartments = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-100   -    -"]},
        geometry=[box(0, 0, 2, 2)], crs="EPSG:2180",
    )
    result = compartment_boundary_features(stands, compartments)
    dist, shared_len = result["02-10-1-01-100   -a   -00"]
    assert dist == 0.5
    assert shared_len == 2.0


def test_interior_stand_has_no_shared_boundary_and_larger_distance():
    stands = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-200   -b   -00"]},
        geometry=[box(0.5, 0.5, 1.5, 1.5)], crs="EPSG:2180",
    )
    compartments = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-200   -    -"]},
        geometry=[box(0, 0, 3, 3)], crs="EPSG:2180",
    )
    result = compartment_boundary_features(stands, compartments)
    dist, shared_len = result["02-10-1-01-200   -b   -00"]
    assert dist == 1.0
    assert shared_len == 0.0


def test_stand_with_no_matching_compartment_gets_none():
    stands = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-99-999   -a   -00"]},
        geometry=[box(0, 0, 1, 1)], crs="EPSG:2180",
    )
    compartments = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-100   -    -"]},
        geometry=[box(0, 0, 2, 2)], crs="EPSG:2180",
    )
    result = compartment_boundary_features(stands, compartments)
    assert result["02-10-1-99-999   -a   -00"] == (None, None)


def test_empty_compartments_gdf_gives_none_for_every_stand():
    stands = gpd.GeoDataFrame(
        {"adr_for": ["02-10-1-01-100   -a   -00"]},
        geometry=[box(0, 0, 1, 1)], crs="EPSG:2180",
    )
    compartments = gpd.GeoDataFrame({"adr_for": []}, geometry=[], crs="EPSG:2180")
    result = compartment_boundary_features(stands, compartments)
    assert result["02-10-1-01-100   -a   -00"] == (None, None)
