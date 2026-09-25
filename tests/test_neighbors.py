import geopandas as gpd
from shapely.geometry import box

from pipeline.neighbors import find_neighbor_labels

DICTIONARIES = {
    "area_type": {"ZRAB": "zrąb", "L": "łąka"},
    "tree_species": {"SO": "sosna zwyczajna", "BK": "buk pospolity"},
}


def _stand(adr_for, geometry, area_type="D-STAN", species_cd="SO", spec_age=60):
    return {
        "adr_for": adr_for, "area_type": area_type, "species_cd": species_cd,
        "spec_age": spec_age, "geometry": geometry,
    }


def test_neighbor_different_species_d_stan_gets_drzewostan_label():
    target = _stand("TARGET", box(0, 0, 100, 100), species_cd="SO")
    other = _stand("OTHER", box(100, 0, 200, 100), species_cd="BK")  # shares full x=100 edge, 100m
    context = gpd.GeoDataFrame([target, other], crs="EPSG:2180")
    labels = find_neighbor_labels(context.iloc[0], context, DICTIONARIES)
    assert labels == ["drzewostan buk pospolity"]


def test_neighbor_same_species_and_old_is_not_a_distinguishing_neighbour():
    target = _stand("TARGET", box(0, 0, 100, 100), species_cd="SO", spec_age=60)
    other = _stand("OTHER", box(0, 100, 100, 200), species_cd="SO", spec_age=80)  # shares y=100 edge
    context = gpd.GeoDataFrame([target, other], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == []


def test_neighbor_young_stand_gets_mlodnik_label_even_if_same_species():
    target = _stand("TARGET", box(0, 0, 100, 100), species_cd="SO", spec_age=60)
    other = _stand("OTHER", box(-100, 0, 0, 100), species_cd="SO", spec_age=10)  # shares x=0 edge
    context = gpd.GeoDataFrame([target, other], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == ["młodnik sosna zwyczajna (10 lat)"]


def test_neighbor_non_d_stan_uses_area_type_dictionary_name():
    target = _stand("TARGET", box(0, 0, 100, 100))
    other = _stand("OTHER", box(0, -100, 100, 0), area_type="ZRAB")  # shares y=0 edge
    context = gpd.GeoDataFrame([target, other], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == ["zrąb"]


def test_neighbor_falls_back_to_raw_code_without_dictionaries():
    target = _stand("TARGET", box(0, 0, 100, 100))
    other = _stand("OTHER", box(0, -100, 100, 0), area_type="ZRAB")
    context = gpd.GeoDataFrame([target, other], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, {}) == ["ZRAB"]


def test_neighbor_below_minimum_shared_boundary_is_excluded():
    # Only a 5m touch (< 20m threshold), regardless of either polygon's
    # own overall perimeter -- exactly the "not a percentage of the
    # perimeter" requirement (spec §0.1).
    target = _stand("TARGET", box(0, 0, 1000, 1000), species_cd="SO")  # 4000m perimeter
    short_touch = _stand("SHORT", box(1000, 500, 1005, 505), species_cd="BK")  # shares 5m of x=1000
    context = gpd.GeoDataFrame([target, short_touch], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == []


def test_neighbor_at_exactly_the_minimum_boundary_is_included():
    target = _stand("TARGET", box(0, 0, 1000, 1000), species_cd="SO")
    exact_touch = _stand("EXACT", box(1000, 0, 1020, 20), species_cd="BK")  # shares exactly 20m
    context = gpd.GeoDataFrame([target, exact_touch], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == ["drzewostan buk pospolity"]


def test_neighbor_labels_are_deduplicated_and_sorted():
    target = _stand("TARGET", box(0, 0, 100, 100), species_cd="SO")
    other_a = _stand("A", box(100, 0, 200, 100), species_cd="BK")
    other_b = _stand("B", box(0, 100, 100, 200), species_cd="BK")  # same "drzewostan buk" label as A
    other_c = _stand("C", box(-100, 0, 0, 100), area_type="ZRAB", species_cd="SO")
    context = gpd.GeoDataFrame([target, other_a, other_b, other_c], crs="EPSG:2180")
    labels = find_neighbor_labels(context.iloc[0], context, DICTIONARIES)
    assert labels == ["drzewostan buk pospolity", "zrąb"]


def test_neighbor_excludes_self_and_geometrically_identical_rows():
    target = _stand("TARGET", box(0, 0, 100, 100), species_cd="SO")
    identical_other_id = _stand("DUPLICATE", box(0, 0, 100, 100), species_cd="BK")
    context = gpd.GeoDataFrame([target, identical_other_id], crs="EPSG:2180")
    assert find_neighbor_labels(context.iloc[0], context, DICTIONARIES) == []
