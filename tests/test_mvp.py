import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box, Point, LineString

from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _scored_stands():
    # Mimics run_poc's output shape (Faza 1 + Task 2 columns) for two stands.
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "species_cd": ["SO", "SO"],
        "site_type": ["BMSW", "BMSW"],
        "spec_age": [60, 60],
        "mask": [True, True],
        "H": [0.9, 0.9],
        "F": [0.6, 0.6],
        "F_loc": [0.6, 0.6],
        "R": [54.0, 54.0],
        "S_host": [1.0, 1.0], "S_site": [1.0, 1.0], "S_age": [1.0, 1.0],
        "M": [0.5, 0.5], "T": [0.8, 0.8], "K_frost": [1.0, 1.0],
    }, geometry=[box(380100, 486100, 380200, 486200), box(390100, 496100, 390200, 496200)], crs="EPSG:2180")


def _no_osm_features():
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    empty_no_pop = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    return {"parking": empty_no_pop, "roads": empty_no_pop, "places": empty}


def _no_gdos():
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")


def test_enrich_adds_all_expected_columns_and_never_checks_ban():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: (_ for _ in ()).throw(AssertionError("should not be called")),
        top_n_for_ban_check=0,
    )
    for col in ["gdos_blocked", "mask_full", "d_park_m", "demand", "demand_norm", "P",
                "pressure_factor", "R_final", "periodic_ban_checked", "periodic_ban_active",
                "confidence", "confidence_reasons", "explanation"]:
        assert col in result.columns
    assert result["periodic_ban_checked"].tolist() == [False, False]


def test_enrich_zero_demand_and_no_parking_gives_zero_pressure():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    assert result["P"].tolist() == pytest.approx([0.0, 0.0])
    assert (result["R_final"] == result["R"]).all()  # pressure_factor == 1.0 -> unchanged


def test_enrich_gdos_block_zeroes_out_ranking():
    stands = _scored_stands()
    protected = gpd.GeoDataFrame(geometry=[box(380100, 486100, 380200, 486200)], crs="EPSG:2180")  # covers stand A only
    result = enrich_with_mvp_layers(
        stands, PROFILE, protected, _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    blocked_row = result[result["stand_id"] == "A"].iloc[0]
    open_row = result[result["stand_id"] == "B"].iloc[0]
    assert bool(blocked_row["gdos_blocked"]) is True
    assert bool(blocked_row["mask_full"]) is False
    assert blocked_row["R_final"] == pytest.approx(0.0)
    assert open_row["R_final"] > 0


def test_enrich_periodic_ban_zeroes_ranking_for_checked_stand():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: True, top_n_for_ban_check=10,
    )
    assert (result["periodic_ban_checked"]).all()
    assert (result["periodic_ban_active"]).all()
    assert result["R_final"].tolist() == pytest.approx([0.0, 0.0])


def test_enrich_periodic_ban_also_clears_mask_full():
    # A banned stand must not still export mask=true (spec §1: recommending
    # a banned area is worse than not recommending at all) -- R_final=0
    # alone isn't enough if a consumer filters/colours by mask directly.
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: True, top_n_for_ban_check=10,
    )
    assert (result["mask_full"] == False).all()


def test_enrich_top_n_larger_than_row_count_does_not_raise():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=1000,
    )
    assert len(result) == 2


def _routing_test_stands():
    # Same shape as _scored_stands() but with distinct H so R_final is
    # unambiguously ordered -- top_n_for_routing must not depend on
    # sort-tie-breaking behavior.
    return gpd.GeoDataFrame({
        "stand_id": ["HIGH", "LOW"],
        "species_cd": ["SO", "SO"], "site_type": ["BMSW", "BMSW"], "spec_age": [60, 60],
        "mask": [True, True],
        "H": [0.9, 0.5], "F": [0.6, 0.6], "F_loc": [0.6, 0.6], "R": [54.0, 30.0],
        "S_host": [1.0, 1.0], "S_site": [1.0, 1.0], "S_age": [1.0, 1.0],
        "M": [0.5, 0.5], "T": [0.8, 0.8], "K_frost": [1.0, 1.0],
    }, geometry=[box(380100, 486100, 380200, 486200), box(390100, 496100, 390200, 496200)], crs="EPSG:2180")


def test_enrich_routing_refines_only_top_n_stands_and_records_method():
    stands = _routing_test_stands()
    # HIGH's centroid is exactly (380150, 486150); this track starts there.
    roads_routing = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(380150, 486150), (380150, 486250)])],
        crs="EPSG:2180",
    )
    entrances = gpd.GeoDataFrame(
        {"status": ["confirmed"]},
        geometry=[Point(380150, 486250)],
        crs="EPSG:2180",
    )
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
        roads_routing_gdf=roads_routing, entrances_gdf=entrances, top_n_for_routing=1,
    )
    refined = result[result["stand_id"] == "HIGH"].iloc[0]
    unrefined = result[result["stand_id"] == "LOW"].iloc[0]
    assert refined["distance_method"] == "network"
    assert refined["entrance_status"] == "confirmed"
    assert refined["d_park_m"] == pytest.approx(100.0)
    assert unrefined["distance_method"] == "euclidean"
    assert unrefined["entrance_status"] == "not_evaluated"


def test_enrich_without_routing_params_keeps_existing_behavior():
    # Regression guard: every existing caller (no routing args) is
    # completely unaffected by this feature's addition.
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    assert (result["distance_method"] == "euclidean").all()
    assert (result["entrance_status"] == "not_evaluated").all()


def test_enrich_routing_with_no_reachable_entrance_falls_back_to_euclidean():
    stands = _routing_test_stands()
    # Two genuinely disjoint graph components: one near HIGH's centroid (so
    # it snaps to a real nearby node), one far away where the entrance is.
    # A single road segment would still produce *a* (very long but finite)
    # route via snap distance alone -- it takes two disconnected components
    # to actually trigger NetworkXNoPath.
    disconnected_roads = gpd.GeoDataFrame(
        {"highway": ["track", "track"]},
        geometry=[
            LineString([(380150, 486150), (380150, 486160)]),  # HIGH's own component
            LineString([(500000, 600000), (500100, 600000)]),  # entrance's component
        ],
        crs="EPSG:2180",
    )
    entrances = gpd.GeoDataFrame(
        {"status": ["potential"]}, geometry=[Point(500100, 600000)], crs="EPSG:2180",
    )
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
        roads_routing_gdf=disconnected_roads, entrances_gdf=entrances, top_n_for_routing=1,
    )
    refined_candidate = result[result["stand_id"] == "HIGH"].iloc[0]
    # A disconnected/unreachable entrance means nearest_entrance_distance
    # returns (None, None) -- must leave the stand on its euclidean values,
    # not crash or zero it out.
    assert refined_candidate["distance_method"] == "euclidean"


def test_enrich_explanation_is_a_list_of_dicts_with_expected_keys():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    explanation = result.iloc[0]["explanation"]
    assert isinstance(explanation, list)
    for entry in explanation:
        assert set(entry) == {"factor", "contribution", "text"}


def test_enrich_adds_g_season_explanation_note_when_below_threshold():
    stands = _scored_stands()
    stands["G_season"] = [0.2, 1.0]  # A: deep off-season, B: peak season
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=0,
    )
    exp_a = result[result["stand_id"] == "A"].iloc[0]["explanation"]
    exp_b = result[result["stand_id"] == "B"].iloc[0]["explanation"]
    assert any(e["factor"] == "g_season" for e in exp_a)
    assert not any(e["factor"] == "g_season" for e in exp_b)


def test_enrich_defaults_g_season_to_one_when_column_absent():
    # Older/synthetic callers that don't set G_season (e.g. _scored_stands
    # itself, most other tests in this file) must not crash or spuriously
    # add the note.
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=0,
    )
    for exp in result["explanation"]:
        assert not any(e["factor"] == "g_season" for e in exp)
