"""Faza UI.1: przelacznik presji grzybiarzy -- R_bez_presji = 100 * H * F_loc, drugi zestaw
rejonow liczony ta sama procedura, a przy wlaczonej presji R i rejony NIE ZMIENIONE."""
import copy
import json

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from pipeline.export import (
    build_details_record, build_habitat_card, build_score_record, build_access_card, write_regions_json,
)
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.prepare_trip import build_manifest
from pipeline.regions import group_into_regions
from pipeline.scoring import compute_ranking

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _scored():
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B", "C"],
        "species_cd": ["SO"] * 3, "site_type": ["BMSW"] * 3, "spec_age": [60] * 3,
        "mask": [True, True, False],
        "H": [0.9, 0.6, 0.8], "F": [0.7, 0.5, 0.7], "F_loc": [0.7, 0.5, 0.7], "R": [0.0] * 3,
        "S_host": [1.0, 0.7, 0.9], "S_site": [1.0, 0.9, 0.9], "S_age": [1.0, 1.0, 1.0],
        "M": [0.5] * 3, "T": [0.8] * 3, "K_frost": [1.0] * 3,
    }, geometry=[box(380100, 486100, 380200, 486200), box(380300, 486100, 380400, 486200),
                 box(390100, 496100, 390200, 496200)], crs="EPSG:2180")


def _no_osm():
    empty = gpd.GeoDataFrame({"population": []}, geometry=[], crs="EPSG:2180")
    bare = gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    return {"parking": bare, "roads": bare, "places": empty}


def _enrich(**kw):
    return enrich_with_mvp_layers(
        _scored(), PROFILE, gpd.GeoDataFrame(geometry=[], crs="EPSG:2180"), _no_osm(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=0, **kw)


def test_r_bez_presji_is_100_h_floc_for_masked_and_zero_otherwise():
    out = _enrich()
    for _, row in out.iterrows():
        expected = 100.0 * row["H"] * row["F_loc"] if row["mask_full"] else 0.0
        assert row["R_bez_presji"] == pytest.approx(expected, abs=1e-12)


def test_r_bez_presji_is_zero_for_periodic_ban_like_r_final():
    out = enrich_with_mvp_layers(
        _scored(), PROFILE, gpd.GeoDataFrame(geometry=[], crs="EPSG:2180"), _no_osm(),
        zakaz_checker=lambda lat, lon: True, top_n_for_ban_check=10)
    assert (out["R_final"] == 0.0).all()
    assert (out["R_bez_presji"] == 0.0).all()


def test_r_final_with_pressure_is_unchanged_formula():
    """Przy wlaczonej presji wynik to dalej 100*H*F_loc*(1 - alpha*P)."""
    out = _enrich()
    alpha = PROFILE["pressure"]["alpha_default"]
    for _, row in out.iterrows():
        expected = compute_ranking(bool(row["mask_full"]), row["H"], row["F_loc"], p=row["P"], alpha=alpha)
        assert row["R_final"] == pytest.approx(expected, abs=1e-12)


def test_r_bez_presji_is_at_least_r_final_for_every_stand():
    out = _enrich()
    assert (out["R_bez_presji"] >= out["R_final"] - 1e-12).all()


def _regions_profile():
    profile = copy.deepcopy(PROFILE)
    profile["regions"] = {"top_pct": 1.0, "radius_m": 500.0, "min_area_ha": 0.0001,
                          "min_separation_m": 3000.0, "top_n_per_region": 5, "max_regions": 5}
    return profile


def _two_clusters():
    """Klaster W (x=380000) wygrywa z presja, klaster E (x=390000) bez presji: E ma wyzsze
    H*F_loc, ale wysokie P."""
    rows = []
    for i in range(3):
        rows.append({"stand_id": f"W{i}", "H": 0.8, "F_loc": 0.8, "P": 0.05,
                     "geometry": box(380000 + i * 100, 486000, 380090 + i * 100, 486100)})
        rows.append({"stand_id": f"E{i}", "H": 0.95, "F_loc": 0.9, "P": 0.9,
                     "geometry": box(390000 + i * 100, 486000, 390090 + i * 100, 486100)})
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    gdf["mask_full"] = True
    alpha = 0.3
    gdf["R_final"] = [compute_ranking(True, r.H, r.F_loc, p=r.P, alpha=alpha) for r in gdf.itertuples()]
    gdf["R_bez_presji"] = [compute_ranking(True, r.H, r.F_loc, p=0.0, alpha=0.0) for r in gdf.itertuples()]
    return gdf


def test_regions_without_pressure_use_the_same_procedure_on_r_bez_presji():
    stands = _two_clusters()
    profile = _regions_profile()
    with_p = group_into_regions(stands, profile)
    without_p = group_into_regions(stands.assign(R_final=stands["R_bez_presji"]), profile)
    # z presja pierwszy rejon to klaster W, bez presji -- E
    assert with_p.iloc[0]["stand_ids"][0].startswith("W")
    assert without_p.iloc[0]["stand_ids"][0].startswith("E")
    assert with_p.iloc[0]["rank_score"] == pytest.approx(
        stands[stands.stand_id.str.startswith("W")]["R_final"].median())
    assert without_p.iloc[0]["rank_score"] == pytest.approx(
        stands[stands.stand_id.str.startswith("E")]["R_bez_presji"].median())


def test_regions_with_pressure_ignore_the_new_column():
    """Dodanie R_bez_presji nie zmienia rejonow z presja (identyczne jak przed zmiana)."""
    stands = _two_clusters()
    profile = _regions_profile()
    before = group_into_regions(stands.drop(columns=["R_bez_presji"]), profile)
    after = group_into_regions(stands, profile)
    assert before["region_id"].tolist() == after["region_id"].tolist()
    assert before["stand_ids"].tolist() == after["stand_ids"].tolist()
    assert before["rank_score"].tolist() == after["rank_score"].tolist()


def _exportable(frame):
    """Uzupelnia pola eksportu, ktorych nie produkuje syntetyczna ramka (pogoda, zrodlo skladu)."""
    from pipeline.export import SCORE_FIELDS
    for field in SCORE_FIELDS:
        if field not in frame.columns:
            frame[field] = None
    return frame


def test_build_score_record_exports_r_bez_presji_and_keeps_r():
    out = _exportable(_enrich())
    row = out.iloc[0]
    record = build_score_record(row, day="2026-09-29")
    assert record["R"] == pytest.approx(row["R_final"])
    assert record["R_bez_presji"] == pytest.approx(100.0 * row["H"] * row["F_loc"])


def test_build_score_record_falls_back_to_h_times_floc_without_the_column():
    out = _exportable(_enrich()).drop(columns=["R_bez_presji"])
    record = build_score_record(out.iloc[1], day="2026-09-29")
    assert record["R_bez_presji"] == pytest.approx(100.0 * 0.6 * 0.5)
    masked_out = build_score_record(out.iloc[2], day="2026-09-29")
    assert masked_out["R_bez_presji"] == 0.0


def test_regions_bez_presji_file_has_same_shape_as_regions_file(tmp_path):
    stands = _two_clusters()
    regions = group_into_regions(stands.assign(R_final=stands["R_bez_presji"]), _regions_profile())
    path = write_regions_json(regions, day="2026-09-29", out_path=tmp_path / "regions_bez_presji_2026-09-29.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data and set(data[0]) >= {"region_id", "rank_score", "stand_count", "stand_ids", "day",
                                     "centroid_lat", "centroid_lon"}


def test_habitat_card_carries_model_components_and_age_mode():
    out = _enrich()
    card = build_habitat_card(out.iloc[1], PROFILE)
    assert card == {"S_host": 0.7, "S_site": 0.9, "S_age": 1.0, "age_mode": "neutral"}
    assert build_habitat_card(out.iloc[1].drop("S_host"), PROFILE) is None


def test_access_card_exports_pressure_contributions():
    import pandas as pd
    row = pd.Series({"pressure_model": "access_points", "d_parking_m": 100.0, "d_entrance_m": 50.0,
                     "d_hard_forest_road_m": None, "top_point_id": "p1", "top_point_type": "parking",
                     "pcontrib_parking": 0.4, "pcontrib_entrance": 0.1, "pcontrib_forest_road": 0.0})
    card = build_access_card(row)
    assert card["pressure_contrib"] == {"parking": 0.4, "entrance": 0.1, "forest_road": 0.0}


def test_manifest_carries_alpha_and_region_count_bez_presji(tmp_path):
    from datetime import date
    manifest = build_manifest(
        lat=50.5, lon=18.6, radius_km=20, day="2026-09-29", target_date=date(2026, 9, 29),
        profile_path="profiles/boletus_edulis.yaml", use_radar=True, repo_dir=tmp_path,
        diagnostics={}, tile_count=1, gdos_failed_tile_count=0, osm_failed_tile_count=0,
        zakaz_checked_count=0, region_count=5, pressure_alpha=0.3, region_count_bez_presji=4)
    assert manifest["pressure_alpha"] == 0.3
    assert manifest["counts"]["region_count_bez_presji"] == 4


# --- UI.3: nazwy (miejscowosc przy rejonie, nadlesnictwo przy wydzieleniu) ---

def _places():
    return gpd.GeoDataFrame({
        "name": ["Lazniki", "Daleko", "", "Pole"],
        "place": ["village", "town", "village", "farm"],
        "geometry": [Point(380500, 486000), Point(400000, 500000), Point(380010, 486010), Point(380001, 486001)],
    }, crs="EPSG:2180")


def test_nearest_place_skips_unnamed_and_non_settlement_classes():
    from pipeline.export import nearest_place
    result = nearest_place(Point(380000, 486000), _places())
    assert result == {"name": "Lazniki", "distance_m": 500}


def test_nearest_place_none_without_places():
    from pipeline.export import nearest_place
    assert nearest_place(Point(0, 0), None) is None
    assert nearest_place(Point(0, 0), gpd.GeoDataFrame({"name": []}, geometry=[], crs="EPSG:2180")) is None


def test_write_regions_json_adds_near_place_only_when_places_given(tmp_path):
    stands = _two_clusters()
    regions = group_into_regions(stands, _regions_profile())
    without = json.loads(write_regions_json(regions, "2026-09-29", tmp_path / "a.json").read_text(encoding="utf-8"))
    with_places = json.loads(
        write_regions_json(regions, "2026-09-29", tmp_path / "b.json", places=_places()).read_text(encoding="utf-8"))
    assert all("near_place" not in r for r in without)
    assert all(r["near_place"]["name"] for r in with_places)


def test_forest_district_name_from_package_name():
    from pipeline.export import forest_district_name
    assert forest_district_name("BDL_02_16_KOSZECIN_2026") == "Koszecin"
    assert forest_district_name("BDL_02_29_STRZELCE_OPOLSKIE_2026") == "Strzelce Opolskie"
    assert forest_district_name(None) is None
    assert forest_district_name(float("nan")) is None
    assert forest_district_name("cos innego") is None
