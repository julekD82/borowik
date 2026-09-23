import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box, Point

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


def test_enrich_explanation_is_a_list_of_dicts_with_expected_keys():
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=10,
    )
    explanation = result.iloc[0]["explanation"]
    assert isinstance(explanation, list)
    for entry in explanation:
        assert set(entry) == {"factor", "contribution", "text"}
