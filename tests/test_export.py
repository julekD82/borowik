import json
import math
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.export import (
    build_score_record, write_scores_json, export_stand_geometries,
    build_region_record, write_regions_json,
    build_details_record, write_details_json,
    write_manifest_json,
    build_diagnostics_record, write_diagnostics_json, write_diagnostics, DIAGNOSTICS_FIELDS,
)
from pipeline.scoring import compute_ranking
from pipeline.bdl_package_details import PackageStandDetails
from pipeline.tie_break import TieBreakRaw


def _enriched_stands():
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "H": [0.9, 0.5], "F": [0.6, 0.4], "F_loc": [0.6, 0.4],
        "P": [0.1, 0.2], "R_final": [48.6, 16.0],
        "mask_full": [True, False],
        "confidence": ["SREDNIA", "NISKA"],
        "confidence_reasons": [["a", "b"], ["c"]],
        "explanation": [[{"factor": "host", "contribution": 0.1, "text": "..."}], []],
        "distance_method": ["network", "euclidean"],
        "entrance_status": ["confirmed", "not_evaluated"],
        "d_park_m": [1234.5, float("nan")],
        "forecast_days": [1, 1],
        "G_season": [0.91, 1.0],
        "tie_break": [0.75, 0.5],
        "rain_radar_coverage": [0.0, 0.0],
        "s_host_source": ["paczka", "wfs"],
        "s_host_package_date": ["2026-06-23", None],
        "zakaz_status": ["brak", "nie_sprawdzono"],
        "gdos_status": ["brak", "brak"],
    }, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs="EPSG:2180")


def _enriched_stands_with_nan_h():
    # H is None on mask-failing stands (compute_habitat's age mask returns
    # None), and a float column mixing None with floats coerces to NaN --
    # confirmed in the real Faza 2 export (322 bare "NaN" tokens, all in H,
    # for the 325 non-mask-passing stands in one tile).
    stands = _enriched_stands()
    stands.loc[1, "H"] = float("nan")
    return stands


def test_build_score_record_shape_matches_architecture_schema():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["stand_id"] == "A"
    assert record["day"] == "2026-09-23"
    for key in ["H", "F", "F_loc", "P", "R", "mask", "confidence", "confidence_reasons", "explanation", "forecast_days"]:
        assert key in record
    assert record["R"] == 48.6
    assert record["mask"] is True
    assert record["forecast_days"] == 1
    assert record["s_host_source"] == "paczka"
    assert record["s_host_package_date"] == "2026-06-23"


def test_build_score_record_includes_g_season():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["G_season"] == pytest.approx(0.91)


def test_build_score_record_includes_tie_break():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["tie_break"] == pytest.approx(0.75)


def test_build_score_record_s_host_package_date_is_null_for_wfs_source():
    row = _enriched_stands().iloc[1]
    record = build_score_record(row, day="2026-09-23")
    assert record["s_host_source"] == "wfs"
    assert record["s_host_package_date"] is None


def test_build_score_record_includes_distance_method_and_entrance_status():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["distance_method"] == "network"
    assert record["entrance_status"] == "confirmed"


def test_build_score_record_includes_area_ha_from_geometry():
    # Plan 2.1 step A4 (spec §5.2): the frontend needs a stand's area to
    # filter out sub-0.5ha standalone-target listings -- computed from the
    # EPSG:2180 geometry itself (same source as pipeline.regions' own
    # area_ha), not BDL's own sub_area attribute (unused, possibly stale).
    row = _enriched_stands().iloc[0]  # box(0, 0, 1, 1) -- CRS units, 1 m^2
    record = build_score_record(row, day="2026-09-23")
    assert record["area_ha"] == pytest.approx(1.0 / 10000.0)


def test_write_scores_json_writes_one_record_per_stand(tmp_path):
    out_path = write_scores_json(_enriched_stands(), day="2026-09-23", out_path=tmp_path / "scores_2026-09-23.json")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert {r["stand_id"] for r in data} == {"A", "B"}


def test_build_score_record_converts_nan_to_none():
    row = _enriched_stands_with_nan_h().iloc[1]
    record = build_score_record(row, day="2026-09-23")
    assert record["H"] is None


def test_write_scores_json_produces_strict_json_with_no_bare_nan_tokens(tmp_path):
    out_path = write_scores_json(
        _enriched_stands_with_nan_h(), day="2026-09-23", out_path=tmp_path / "scores_2026-09-23.json"
    )
    raw = out_path.read_text(encoding="utf-8")
    assert "NaN" not in raw  # browsers' JSON.parse throws on a bare NaN token
    data = json.loads(raw)
    assert data[1]["H"] is None


def test_export_stand_geometries_round_trips(tmp_path):
    out_path = export_stand_geometries(_enriched_stands(), tmp_path / "stands.parquet")
    assert out_path.exists()
    reloaded = gpd.read_parquet(out_path)
    assert len(reloaded) == 2
    assert "stand_id" in reloaded.columns
    assert "geometry" in reloaded.columns


def _regions():
    return gpd.GeoDataFrame({
        "region_id": ["region_1"],
        "rank_score": [42.5],
        "stand_count": [3],
        "stand_ids": [["A", "B", "C"]],
    }, geometry=[box(380000, 486000, 380300, 486100)], crs="EPSG:2180")


def test_build_region_record_shape():
    row = _regions().iloc[0]
    record = build_region_record(row, day="2026-09-24")
    assert record == {
        "region_id": "region_1", "rank_score": 42.5, "stand_count": 3,
        "stand_ids": ["A", "B", "C"], "day": "2026-09-24",
    }


def test_write_regions_json_writes_one_record_per_region(tmp_path):
    out_path = write_regions_json(_regions(), day="2026-09-24", out_path=tmp_path / "regions_2026-09-24.json")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    record = data[0]
    assert record["region_id"] == "region_1"
    assert record["rank_score"] == 42.5
    assert record["stand_count"] == 3
    assert record["stand_ids"] == ["A", "B", "C"]
    assert record["day"] == "2026-09-24"


def test_write_regions_json_includes_wgs84_centroid_for_locating_the_region(tmp_path):
    # Final review finding: a region's stand_ids alone can't be placed on a
    # map or navigated to -- a consumer of this file needs a location.
    out_path = write_regions_json(_regions(), day="2026-09-24", out_path=tmp_path / "regions.json")
    record = json.loads(out_path.read_text(encoding="utf-8"))[0]
    assert "centroid_lat" in record and "centroid_lon" in record
    # box(380000, 486000, 380300, 486100) is EPSG:2180 (Poland); sanity-range
    # check on the reprojected WGS84 centroid, not a brittle exact value.
    assert 49.0 < record["centroid_lat"] < 55.0
    assert 14.0 < record["centroid_lon"] < 24.0


def test_write_regions_json_handles_empty_regions(tmp_path):
    empty = gpd.GeoDataFrame(
        {"region_id": [], "rank_score": [], "stand_count": [], "stand_ids": []},
        geometry=[], crs="EPSG:2180",
    )
    out_path = write_regions_json(empty, day="2026-09-24", out_path=tmp_path / "regions.json")
    assert json.loads(out_path.read_text(encoding="utf-8")) == []


_DICTIONARIES = {
    "tree_species": {"SO": "sosna zwyczajna", "BK": "buk pospolity"},
    "density": {"0.7": "0.7"},
    "soil_subtype": {"Bw": "brunatna wyługowana"},
    "part": {"7": "udział 70 %", "3": "udział 30 %", "MJS": "poniżej 5 % - miejscami"},
    "prot_categ": {"OCH USZK": "trw. uszk na sk. dział.przem"},
}


def test_build_details_record_full_shape_with_package():
    details_index = {
        "AA-1": PackageStandDetails(
            drzew_species=[("SO", "7"), ("BK", "3")],
            density_cd="0.7",
            podszyt_species=[("BK", "MJS")],
            soil_subtype_cd="Bw",
            source_name="PKG_ONE",
            package_date="2026-06-23",
        ),
    }
    neighbors = {"AA-1": ["drzewostan buk pospolity", "zrąb"]}
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", "OCH USZK", "2026-09-25",
        details_index, neighbors, _DICTIONARIES, {},
    )
    assert record["stand_id"] == "AA-1@2026"
    assert record["day"] == "2026-09-25"
    assert record["drzew_species"] == [
        {"species_cd": "SO", "name": "sosna zwyczajna", "share": "udział 70 %"},
        {"species_cd": "BK", "name": "buk pospolity", "share": "udział 30 %"},
    ]
    assert record["density"] == "0.7"
    assert record["podszyt_species"] == [
        {"species_cd": "BK", "name": "buk pospolity", "share": "poniżej 5 % - miejscami"},
    ]
    assert record["soil_type"] == "brunatna wyługowana"
    assert record["package_date"] == "2026-06-23"
    assert record["neighbors"] == ["drzewostan buk pospolity", "zrąb"]
    assert record["stand_stru"] == "DRZEW"
    assert record["prot_categ"] == "trw. uszk na sk. dział.przem"


def test_build_details_record_includes_veg_cover_and_density_index_with_package():
    tie_break_index = {"AA-1": TieBreakRaw(veg_cover_cd="MSZC", standdensity_index=0.9)}
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", None, "2026-09-25",
        {}, {}, {}, tie_break_index,
    )
    assert record["veg_cover"] == "mszysto-czernicowa"
    assert record["standdensity_index"] == pytest.approx(0.9)


def test_build_details_record_veg_cover_and_density_index_null_without_coverage():
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", None, "2026-09-25",
        {}, {}, {}, {},
    )
    assert record["veg_cover"] is None
    assert record["standdensity_index"] is None


def test_build_details_record_empty_package_fields_when_no_package():
    record = build_details_record(
        "BB-2@2026", "BB-2", None, None, "2026-09-25",
        {}, {}, _DICTIONARIES, {},
    )
    assert record["drzew_species"] == []
    assert record["density"] is None
    assert record["podszyt_species"] == []
    assert record["soil_type"] is None
    assert record["package_date"] is None
    assert record["neighbors"] == []
    assert record["stand_stru"] is None
    assert record["prot_categ"] is None


def test_build_details_record_neighbors_and_stand_stru_present_without_package():
    # spec: neighbours/stand_stru/prot_categ come from WFS and must work
    # even for a wydzielenie with no BDL package coverage.
    neighbors = {"CC-3": ["łąka"]}
    record = build_details_record(
        "CC-3@2026", "CC-3", "KO", "OCH USZK", "2026-09-25",
        {}, neighbors, _DICTIONARIES, {},
    )
    assert record["neighbors"] == ["łąka"]
    assert record["stand_stru"] == "KO"
    assert record["prot_categ"] == "trw. uszk na sk. dział.przem"
    assert record["drzew_species"] == []  # still no package data


def test_build_details_record_falls_back_to_raw_code_without_dictionary_entry():
    details_index = {
        "DD-4": PackageStandDetails(
            drzew_species=[("XX", "10")], density_cd="ZZZ", podszyt_species=[],
            soil_subtype_cd="YYY", source_name="PKG", package_date=None,
        ),
    }
    record = build_details_record("DD-4@2026", "DD-4", None, "UNKNOWN_CATEG", "2026-09-25", details_index, {}, {}, {})
    assert record["drzew_species"] == [{"species_cd": "XX", "name": "XX", "share": "10"}]
    assert record["density"] == "ZZZ"
    assert record["soil_type"] == "YYY"
    assert record["prot_categ"] == "UNKNOWN_CATEG"


def test_write_details_json_one_record_per_stand(tmp_path):
    stands = gpd.GeoDataFrame({
        "stand_id": ["AA-1@2026", "BB-2@2026"],
        "adr_for": ["AA-1", "BB-2"],
        "stand_stru": ["DRZEW", None],
        "prot_categ": ["OCH USZK", None],
    }, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs="EPSG:2180")
    details_index = {
        "AA-1": PackageStandDetails(
            drzew_species=[("SO", "10")], density_cd=None, podszyt_species=[],
            soil_subtype_cd=None, source_name="PKG", package_date=None,
        ),
    }
    out_path = write_details_json(
        stands, details_index, {}, _DICTIONARIES, day="2026-09-25", out_path=tmp_path / "details.json",
        tie_break_index={},
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert {r["stand_id"] for r in data} == {"AA-1@2026", "BB-2@2026"}
    with_package = next(r for r in data if r["stand_id"] == "AA-1@2026")
    without_package = next(r for r in data if r["stand_id"] == "BB-2@2026")
    assert with_package["drzew_species"]
    assert without_package["drzew_species"] == []
    assert without_package["stand_stru"] is None


from pipeline.export import SCORE_FIELDS


def test_score_fields_include_rain_radar_coverage():
    assert "rain_radar_coverage" in SCORE_FIELDS


from pipeline.export import write_conditions_json


def test_write_conditions_json_adds_day_and_writes_strict_json(tmp_path):
    timeline = {"generated_for": "2026-09-27", "horizon_days": 7, "pulse_min_mm": 15.0,
                "rains": [], "days": [{"date": "2026-09-27", "F": 0.5, "level": 2, "forecast": False}],
                "summary": "Brak deszczu ≥ 15 mm w ostatnich dniach."}
    path = write_conditions_json(timeline, "2026-09-27", tmp_path / "conditions_2026-09-27.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["day"] == "2026-09-27" and data["summary"] == timeline["summary"]


def test_write_manifest_json_round_trips_the_whole_dict(tmp_path):
    # write_manifest_json only serializes -- pipeline.prepare_trip.build_manifest
    # owns field completeness (see tests/test_prepare_trip.py); this just
    # checks the file is written where asked and reads back byte-identical
    # (allow_nan=False, same as every other write_*_json above).
    manifest = {"run_id": "abc123", "day": "2026-09-28", "commit": None, "uncommitted_changes": None,
                "sources": {"radar_coverage_mean": 0.86}, "counts": {"stand_count": 4703}}
    path = write_manifest_json(manifest, tmp_path / "run_manifest_2026-09-28.json")
    assert path == tmp_path / "run_manifest_2026-09-28.json"
    assert json.loads(path.read_text(encoding="utf-8")) == manifest


def _diagnostics_stands():
    # Row A: structural mask true, no GDOS/zakaz exclusion -> mask_full true,
    # R_final follows the normal formula. Row B: structural mask true, but
    # GDOS-blocked -> mask_full false, R_final = 0 (spec §9.3), the case the
    # reconstruction test must also get right, not just the "everything
    # passes" happy path.
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "S_host": [0.9, 0.7], "S_site": [1.0, 0.85], "S_age": [1.0, 1.0],
        "H": [0.9, 0.5], "pct_CWB26": [0.66, 0.4], "M": [0.62, 0.3],
        "T": [0.8, 0.5], "K_frost": [1.0, 1.0], "G_season": [0.91, 0.91],
        "F": [0.6, 0.3], "q": [1.0, 0.9], "F_loc": [0.6, 0.27],
        "P": [0.4, 0.2], "distance_method": ["network", "euclidean"],
        "s_host_source": ["paczka", "wfs"], "s_host_package_date": ["2026-06-23", None],
        "sklad_niepelny": [False, False],
        "rain_radar_coverage": [0.75, 0.0],
        "demand": [1234.5, 0.0], "d_park_m": [500.0, float("nan")],
        "weather_point_lat": [50.5, 50.6], "weather_point_lon": [18.6, 18.7],
        "climatology_cell_lat": [50.4, 50.4], "climatology_cell_lon": [18.5, 18.5],
        "gdos_status": ["brak", "blokada"],
        "zakaz_status": ["brak", "nie_sprawdzono"],
        "mask": [True, True],
        "mask_full": [True, False],
        "R_final": [
            compute_ranking(True, 0.9, 0.6, p=0.4, alpha=0.3),
            0.0,
        ],
    }, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs="EPSG:2180")


def test_build_diagnostics_record_has_every_field_the_spec_lists():
    stands = _diagnostics_stands()
    record = build_diagnostics_record(stands.iloc[0], "2026-09-28")
    for field in DIAGNOSTICS_FIELDS:
        assert field in record, f"missing {field}"
    for field in ("day", "stand_id", "mask", "Demand", "d_park_m", "weather_point",
                  "climatology_cell", "gdos_status", "zakaz_status"):
        assert field in record, f"missing {field}"
    assert record["weather_point"] == {"lat": 50.5, "lon": 18.6}
    assert record["gdos_status"] == "brak"
    assert record["zakaz_status"] == "brak"


def test_build_diagnostics_record_zakaz_and_gdos_status_variants():
    stands = _diagnostics_stands()
    blocked = build_diagnostics_record(stands.iloc[1], "2026-09-28")
    assert blocked["gdos_status"] == "blokada"
    assert blocked["zakaz_status"] == "nie_sprawdzono"  # periodic_ban_checked=False


def test_reconstruct_r_final_from_diagnostics_matches_scores_within_1e9(tmp_path):
    # Plan 1.2 acceptance: R_final must be reconstructable from the
    # diagnostics export alone (plus scores.json's own mask/R), without any
    # network call, tolerance 1e-9 -- same check the technical review already
    # ran once by hand (docs/Borowik_opis_techniczny_i_walidacja.md §17.2).
    stands = _diagnostics_stands()
    alpha = 0.3
    for _, row in stands.iterrows():
        diag = build_diagnostics_record(row, "2026-09-28")
        mask_full = diag["mask"] and diag["gdos_status"] != "blokada" and diag["zakaz_status"] != "zakaz"
        reconstructed = compute_ranking(mask_full, diag["H"], diag["F_loc"], p=diag["P"], alpha=alpha)
        assert reconstructed == pytest.approx(float(row["R_final"]), abs=1e-9)


def test_write_diagnostics_json_writes_one_record_per_stand(tmp_path):
    stands = _diagnostics_stands()
    path = write_diagnostics_json(stands, "2026-09-28", tmp_path / "diagnostics_2026-09-28.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert {r["stand_id"] for r in data} == {"A", "B"}


def test_write_diagnostics_picks_json_when_under_the_size_limit(tmp_path):
    stands = _diagnostics_stands()
    path = write_diagnostics(stands, "2026-09-28", tmp_path)
    assert path == tmp_path / "diagnostics_2026-09-28.json"
    assert path.exists()


def test_write_diagnostics_switches_to_parquet_over_the_size_limit(tmp_path, monkeypatch):
    import pipeline.export as export_mod
    monkeypatch.setattr(export_mod, "_DIAGNOSTICS_SIZE_LIMIT_BYTES", 10)  # force the switch
    stands = _diagnostics_stands()
    path = write_diagnostics(stands, "2026-09-28", tmp_path)
    assert path == tmp_path / "diagnostics_2026-09-28.parquet"
    assert path.exists()
    assert not (tmp_path / "diagnostics_2026-09-28.json").exists()
    df = pd.read_parquet(path)
    assert len(df) == 2
    assert set(df["stand_id"]) == {"A", "B"}
