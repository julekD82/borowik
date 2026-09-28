from datetime import date

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.bdl_packages import PackageComposition
from pipeline.habitat import load_profile, score_host_composition
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


def fake_weather_fetcher(points, past_days, forecast_days=1):
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


# --- Plan 1.7/1.8d: insufficient_climatology per stand -----------------------

def test_run_poc_insufficient_climatology_false_with_a_dense_window():
    # target_date's day-of-year must fall inside fake_climatology_fetcher's
    # actual range (2000-01-01, 60 days -> doy 1-60) with margin for the
    # +/-15-day window filter, or the window is empty regardless of "today".
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
        target_date=date(2026, 1, 20),
    )
    assert "insufficient_climatology" in result.columns
    assert not result["insufficient_climatology"].any()


def test_run_poc_insufficient_climatology_true_with_an_empty_window():
    def empty_climatology_fetcher(points, start_year, end_year):
        # dtype="datetime64[ns]" for "date" -- a plain columns=[...] empty
        # frame gives it object dtype instead, and climatology_window_values'
        # own .dt.dayofyear needs a real datetime column (matches the shape
        # a genuinely empty real fetch would have, not just an empty list).
        return pd.DataFrame({
            "lat": pd.Series(dtype=float), "lon": pd.Series(dtype=float),
            "date": pd.Series(dtype="datetime64[ns]"),
            "cwb26": pd.Series(dtype=float), "soil_moisture": pd.Series(dtype=float),
        })

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=empty_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
    )
    assert result["insufficient_climatology"].all()
    assert result.attrs["diagnostics"]["empty_climatology_count"] > 0


def test_run_poc_fetches_climatology_on_a_coarser_grid_than_weather():
    # Climatology's 30-year archive is far more expensive per point than a
    # live weather call (Open-Meteo's own weighting formula: weight scales
    # with days-range/14 x variables/10, so a 30-year pull already weighs
    # ~235 "calls" per point -- see docs/CODEX-HANDOFF.md). Climatology
    # varies smoothly over a few km, so it's fetched on a coarser grid and
    # each weather cell borrows its nearest climatology cell's history.
    weather_points_seen = []
    climatology_points_seen = []

    def counting_weather_fetcher(points, past_days, forecast_days=1):
        weather_points_seen.append(list(points))
        return fake_weather_fetcher(points, past_days, forecast_days)

    def counting_climatology_fetcher(points, start_year, end_year):
        climatology_points_seen.append(list(points))
        return fake_climatology_fetcher(points, start_year, end_year)

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=counting_weather_fetcher,
        climatology_fetcher=counting_climatology_fetcher,
        grid_spacing_m=2000.0,
        climatology_grid_spacing_m=8000.0,
        past_days=30,
    )

    assert len(climatology_points_seen) == 1
    assert len(weather_points_seen) == 1
    assert len(climatology_points_seen[0]) < len(weather_points_seen[0])
    assert result["H"].notna().all()
    assert result["R"].notna().all()


def test_run_poc_moisture_percentiles_follow_each_weather_point_not_the_climatology_cell():
    # Regression (found 2026-09-27 on the real Bedziemysl export): percentiles
    # were cached per CLIMATOLOGY cell but computed from the weather row of
    # whichever stand hit that cell first, so every weather point sharing a
    # (16 km) climatology cell got that first point's M -- the radar's/weather
    # grid's own spatial detail was thrown away. Two stands here share one
    # climatology cell but sit at different weather points, one dry, one wet.
    def two_stand_fetcher(layer, bbox):
        return gpd.GeoDataFrame({
            "adr_for": ["DRY", "WET"],
            "a_year": [2026, 2026],
            "area_type": ["D-STAN", "D-STAN"],
            "site_type": ["BMSW", "BMSW"],
            "species_cd": ["SO", "SO"],
            "part_cd": [10, 10],
            "spec_age": [60, 60],
            "geometry": [box(381000, 487000, 381100, 487100), box(389000, 495000, 389100, 495100)],
        }, crs="EPSG:2180")

    def split_weather_fetcher(points, past_days, forecast_days=1):
        median_lat = sorted(lat for lat, _ in points)[len(points) // 2]
        df = fake_weather_fetcher(points, past_days, forecast_days)
        df["precipitation_mm"] = [10.0 if lat > median_lat else 0.0 for lat in df["lat"]]
        return df

    def spread_climatology_fetcher(points, start_year, end_year):
        rows = []
        for lat, lon in points:
            for d in pd.date_range("2000-01-01", "2009-12-31", freq="D"):
                rows.append({"lat": lat, "lon": lon, "date": d,
                             "cwb26": -50.0 + 20.0 * (d.year - 2000), "soil_moisture": 0.4})
        return pd.DataFrame(rows)

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=two_stand_fetcher,
        weather_fetcher=split_weather_fetcher,
        climatology_fetcher=spread_climatology_fetcher,
        grid_spacing_m=2000.0,
        climatology_grid_spacing_m=50000.0,  # one shared climatology cell for both stands
        past_days=30,
        target_date=date(2026, 8, 30),
    )

    m = dict(zip(result["adr_for"], result["M"]))
    assert m["WET"] > m["DRY"]


def test_run_poc_m_and_f_loc_ignore_model_soil_moisture():
    # 2026-09-27: profile soil_moisture_weight 0.0 -- both M and the
    # site-moisture modulation (pct_m -> F_loc) must be independent of the
    # Open-Meteo soil moisture reading.
    def weather_with_soil(value):
        def fetcher(points, past_days, forecast_days=1):
            df = fake_weather_fetcher(points, past_days, forecast_days)
            df["soil_moisture"] = value
            return df
        return fetcher

    def spread_climatology_fetcher(points, start_year, end_year):
        # Non-empty window around target_date with spread soil moisture, so
        # 0.05 and 0.9 would rank very differently if pct_sm still counted.
        rows = []
        for lat, lon in points:
            for d in pd.date_range("2000-01-01", "2009-12-31", freq="D"):
                k = d.year - 2000
                rows.append({"lat": lat, "lon": lon, "date": d,
                             "cwb26": -50.0 + 20.0 * k, "soil_moisture": 0.1 + 0.07 * k})
        return pd.DataFrame(rows)

    runs = [
        run_poc(
            layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
            bdl_fetcher=fake_bdl_fetcher, weather_fetcher=weather_with_soil(value),
            climatology_fetcher=spread_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
            target_date=date(2026, 8, 30),
        )
        for value in (0.05, 0.9)
    ]
    assert runs[0]["M"].tolist() == pytest.approx(runs[1]["M"].tolist())
    assert runs[0]["F_loc"].tolist() == pytest.approx(runs[1]["F_loc"].tolist())


def test_run_poc_defaults_climatology_grid_coarser_than_weather_grid():
    weather_points_seen = []
    climatology_points_seen = []

    def counting_weather_fetcher(points, past_days, forecast_days=1):
        weather_points_seen.append(list(points))
        return fake_weather_fetcher(points, past_days, forecast_days)

    def counting_climatology_fetcher(points, start_year, end_year):
        climatology_points_seen.append(list(points))
        return fake_climatology_fetcher(points, start_year, end_year)

    run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=counting_weather_fetcher,
        climatology_fetcher=counting_climatology_fetcher,
        grid_spacing_m=2000.0,
        past_days=30,
    )

    assert len(climatology_points_seen[0]) < len(weather_points_seen[0])


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


class _FrozenDate(date):
    """Same pattern as tests/test_weather.py's FrozenDate: freeze
    date.today() inside pipeline.orchestrate so target_date arithmetic
    (forecast_days, day-of-year) is deterministic regardless of when the
    test suite actually runs."""
    _today = date(2026, 9, 24)

    @classmethod
    def today(cls):
        return cls._today


def test_run_poc_defaults_forecast_days_to_one_without_target_date():
    # Plan 2.1 step A3: no --date given -> unchanged pre-A3 behaviour, one
    # forecast day (today only).
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert (result["forecast_days"] == 1).all()


def test_run_poc_derives_forecast_days_from_target_date_and_exposes_it_per_stand(monkeypatch):
    # spec 3.3 "Prognoza do dnia wyjazdu" / plan 2.1 step A3: --date N days
    # ahead of today must request forecast_days = N+1 (today counts as day
    # 1) from the weather fetcher, and that same number must be exported
    # per stand (the "ile dni okna to prognoza" banner field).
    import pipeline.orchestrate as orchestrate_mod
    monkeypatch.setattr(orchestrate_mod, "date", _FrozenDate)

    forecast_days_seen = []

    def counting_weather_fetcher(points, past_days, forecast_days=1):
        forecast_days_seen.append(forecast_days)
        return fake_weather_fetcher(points, past_days, forecast_days)

    target_date = date(2026, 9, 27)  # 3 days after the frozen "today"
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=counting_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
        target_date=target_date,
    )

    assert forecast_days_seen == [4]
    assert (result["forecast_days"] == 4).all()
    assert result.attrs["diagnostics"]["forecast_days"] == 4


def test_run_poc_uses_target_date_not_today_for_climatology_day_of_year(monkeypatch):
    # spec 3.3/5.4, plan 2.1 step A3: climatology percentiles must be looked
    # up for the TRIP date's day-of-year, not today's. Proven behaviourally:
    # a synthetic climatology history placed only around the target date's
    # day-of-year (July, far from the frozen "today" in January) is found
    # (empty_climatology_count == 0) only if run_poc actually queries that
    # day-of-year instead of today's.
    import pipeline.orchestrate as orchestrate_mod
    monkeypatch.setattr(orchestrate_mod, "date", _FrozenDate)
    # setattr (not direct assignment) so monkeypatch restores this shared
    # class attribute after the test -- _FrozenDate is defined once at
    # module scope and reused by other tests below.
    monkeypatch.setattr(_FrozenDate, "_today", date(2026, 1, 15))  # doy ~15, far from July

    target_date = date(2026, 7, 15)  # doy ~196

    def climatology_fetcher_seasonal(points, start_year, end_year):
        rows = []
        for lat, lon in points:
            for d in pd.date_range("2020-07-01", periods=30, freq="D"):
                rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": 30.0, "soil_moisture": 0.4})
        return pd.DataFrame(rows)

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=climatology_fetcher_seasonal, grid_spacing_m=5000.0, past_days=30,
        target_date=target_date,
    )

    assert result.attrs["diagnostics"]["empty_climatology_count"] == 0


def test_run_poc_defaults_s_host_source_to_wfs_without_package_index():
    # Plan 2.1 step B2: no package_index (or one that misses every stand)
    # must reproduce pre-B2 behaviour exactly.
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert (result["s_host_source"] == "wfs").all()
    assert result["s_host_package_date"].isna().all()
    assert result.attrs["diagnostics"]["package_stand_count"] == 0


def test_run_poc_uses_package_composition_per_stand_with_wfs_fallback():
    # A-1 is covered by a package (mixed SO/BK composition); A-2 is not --
    # this exercises per-stand fallback within a single mixed run, not just
    # an all-or-nothing package_index.
    composition = [("SO", 0.6), ("BK", 0.4)]
    package_index = {
        "A-1": PackageComposition(species=composition, source_name="PKG_TEST", package_date="2026-06-23"),
    }
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
        package_index=package_index,
    )
    a1 = result.loc[result["stand_id"] == "A-1@2026"].iloc[0]
    a2 = result.loc[result["stand_id"] == "A-2@2026"].iloc[0]

    assert a1["s_host_source"] == "paczka"
    assert a1["s_host_package_date"] == "2026-06-23"
    expected_s_host, _unknown = score_host_composition(composition, PROFILE)
    assert a1["S_host"] == pytest.approx(expected_s_host)
    assert a1["S_host"] != pytest.approx(1.0)  # WFS fallback (SO, part_cd=10) would have given 1.0

    assert a2["s_host_source"] == "wfs"
    assert pd.isna(a2["s_host_package_date"])  # pandas stores the column's None as NaN
    assert a2["S_host"] == pytest.approx(1.0)  # unchanged: SO, part_cd=10, no package coverage

    assert result.attrs["diagnostics"]["package_stand_count"] == 1
    assert result.attrs["diagnostics"]["package_unknown_species_count"] == 0


def test_run_poc_counts_unknown_species_from_package_composition():
    package_index = {
        "A-1": PackageComposition(species=[("SO", 0.5), ("ZZZ", 0.5)], source_name="PKG", package_date=None),
    }
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
        package_index=package_index,
    )
    assert result.attrs["diagnostics"]["package_unknown_species_count"] == 1


def test_run_poc_exposes_g_season_per_stand_and_in_diagnostics():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
        target_date=date(2026, 9, 15),  # GBIF monthly maximum, G_season == 1.0
    )
    assert result["G_season"].tolist() == pytest.approx([1.0, 1.0])
    assert result.attrs["diagnostics"]["g_season"] == pytest.approx(1.0)


def test_run_poc_g_season_reduces_f_relative_to_hardcoded_one(monkeypatch):
    import pipeline.orchestrate as orchestrate_mod

    monkeypatch.setattr(orchestrate_mod, "date", _FrozenDate)
    monkeypatch.setattr(_FrozenDate, "_today", date(2026, 1, 1))

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
        target_date=date(2026, 1, 1),  # deep winter -- G_season floors near 0.05
    )
    assert result["G_season"].iloc[0] == pytest.approx(PROFILE["phenology"]["g_season_floor"], abs=0.01)
    # F = G_season * M^0.6 * T^0.4 * K_frost, so a floored G_season pulls F
    # down close to that same floor (M/T/K_frost each <= 1.0 by construction).
    assert result["F"].iloc[0] < 0.1


def test_run_poc_exposes_rain_radar_coverage_per_stand_and_in_diagnostics():
    def radar_weather_fetcher(points, past_days, forecast_days=1):
        df = fake_weather_fetcher(points, past_days, forecast_days)
        df["radar_frac"] = 1.0
        return df

    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=radar_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert result["rain_radar_coverage"].tolist() == pytest.approx([1.0, 1.0])
    assert result.attrs["diagnostics"]["radar_coverage_mean"] == pytest.approx(1.0)


def test_run_poc_without_radar_reports_zero_coverage():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia", bbox_2180=BBOX, profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher, weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher, grid_spacing_m=5000.0, past_days=30,
    )
    assert result["rain_radar_coverage"].tolist() == [0.0, 0.0]
