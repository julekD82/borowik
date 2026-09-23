import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX = (486000.0, 380000.0, 496000.0, 390000.0)


def fake_bdl_fetcher(layer, bbox):
    return gpd.GeoDataFrame({
        "adr_for": ["A-1", "A-2"],
        "a_year": [2026, 2026],
        "area_type": ["D-STAN", "D-STAN"],
        "site_type": ["BMSW", "BS"],
        "species_cd": ["SO", "SO"],
        "part_cd": [10, 10],
        "spec_age": [60, 60],
        "geometry": [box(380100, 486100, 380200, 486200), box(380300, 486300, 380400, 486400)],
    }, crs="EPSG:2180")


def fake_weather_fetcher(points, past_days):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2026-08-01", periods=30, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": 2.0,
                         "tmean_c": 13.0, "tmin_c": 6.0, "tmax_c": 18.0,
                         "et0_mm": 1.0, "soil_moisture": 0.4})
    return pd.DataFrame(rows)


def fake_climatology_fetcher(points, start_year, end_year):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2000-01-01", periods=60, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": 30.0, "soil_moisture": 0.4})
    return pd.DataFrame(rows)


def test_run_poc_produces_scored_geodataframe_with_expected_columns():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )

    assert len(result) == 2
    for col in ["stand_id", "H", "F", "F_loc", "mask", "R"]:
        assert col in result.columns
    assert result["stand_id"].tolist() == ["A-1@2026", "A-2@2026"]
    # BS site_type -> S_site=0.45 lower than BMSW's 1.0, so row 2's H should be lower
    assert result.loc[result["stand_id"] == "A-2@2026", "H"].iloc[0] < result.loc[result["stand_id"] == "A-1@2026", "H"].iloc[0]


def test_run_poc_reports_clean_diagnostics_for_known_codes():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )

    diag = result.attrs["diagnostics"]
    assert diag["stand_count"] == 2
    assert diag["unknown_site_count"] == 0
    assert diag["unknown_species_count"] == 0
    assert diag["nan_h_count"] == 0


def test_run_poc_counts_unknown_codes_and_nan_h():
    def unknown_code_fetcher(layer, bbox):
        gdf = fake_bdl_fetcher(layer, bbox)
        gdf.loc[1, "site_type"] = "BMŚW"   # un-normalized -> not a profile key
        gdf.loc[1, "species_cd"] = "ŚW"
        return gdf

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=unknown_code_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )

    diag = result.attrs["diagnostics"]
    assert diag["unknown_site_count"] == 1
    assert diag["unknown_species_count"] == 1
    assert diag["nan_h_count"] == 0


def test_run_poc_exposes_intermediate_factor_scores_for_explanations():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )

    for col in ["S_host", "S_site", "S_age", "M", "T", "K_frost"]:
        assert col in result.columns

    row = result.loc[result["stand_id"] == "A-1@2026"].iloc[0]
    # species_cd=SO, part_cd=10, site_type=BMSW, spec_age=60 -> pure-stand host
    # affinity and the site_scores/age_breakpoints values already exercised by
    # test_habitat.py.
    assert row["S_host"] == pytest.approx(1.0)
    assert row["S_site"] == pytest.approx(1.00)
    assert row["S_age"] == pytest.approx(1.0)
