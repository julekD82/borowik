import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer

from zoneinfo import ZoneInfo

from pipeline.weather import (
    make_grid,
    fetch_weather_raw,
    fetch_climatology_raw,
    compute_weather_features,
    climatology_window_values,
    percentile_rank,
    climatology_window_insufficient,
    to_local_date,
    precip_derived_features,
    stand_precip_features_table,
)

_WARSAW = ZoneInfo("Europe/Warsaw")


def _fixed_step_dates(first_local_day, n_days):
    """Reproduces pipeline.weather._parse_open_meteo_response's date
    construction bug (plan 1.8b): a FIXED 86400s UTC step from the first
    day's TRUE local midnight, instead of each day's own true local
    midnight -- correct only until the next DST transition."""
    start_utc = pd.Timestamp(first_local_day, tz=_WARSAW).tz_convert("UTC")
    return pd.Series(pd.date_range(start=start_utc, periods=n_days, freq="86400s"))


def test_make_grid_covers_bbox_with_points_in_lat_lon():
    bbox = (486000.0, 380000.0, 496000.0, 390000.0)  # 10x10 km
    grid = make_grid(bbox, spacing_m=5000.0)
    assert len(grid) >= 4  # at least a 2x2 grid over 10km with 5km spacing
    for lat, lon in grid:
        assert 40.0 < lat < 60.0
        assert 10.0 < lon < 25.0


def test_make_grid_is_aligned_to_a_fixed_absolute_grid_not_the_bbox_corner():
    # Two overlapping searches with different centers/radii must share exact
    # (lat, lon) values wherever their bboxes cover the same ground -- only
    # then does a per-point disk cache (below) reuse entries across
    # searches, the way pipeline/search_area.py's fixed 10km tile grid
    # already does for BDL. A grid built relative to each bbox's own corner
    # (the old behavior) would shift with the bbox and never overlap.
    small = make_grid((486000.0, 380000.0, 496000.0, 390000.0), spacing_m=5000.0)
    # Offset by 3123 m -- deliberately NOT a multiple of spacing_m, so a
    # grid built relative to each bbox's own corner (the old behavior)
    # would produce zero shared points even though the two areas overlap.
    large = make_grid((482877.0, 376877.0, 502877.0, 396877.0), spacing_m=5000.0)
    shared = set(small) & set(large)
    assert len(shared) >= 1  # the overlapping region has at least one common point


def test_make_grid_point_positions_are_exact_multiples_of_spacing():
    grid = make_grid((486000.0, 380000.0, 496000.0, 390000.0), spacing_m=5000.0)
    to_metric = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    for lat, lon in grid:
        e, n = to_metric.transform(lon, lat)
        assert e / 5000.0 == pytest.approx(round(e / 5000.0), abs=1e-6)
        assert n / 5000.0 == pytest.approx(round(n / 5000.0), abs=1e-6)


def _fake_daily_payload(offset=0.0):
    dates = pd.date_range("2026-06-25", periods=3, freq="D")
    return {
        "date": dates,
        "precipitation_mm": [1.0 + offset, 2.0 + offset, 3.0 + offset],
        "tmean_c": [12.0, 13.0, 14.0],
        "tmin_c": [8.0, 9.0, 10.0],
        "tmax_c": [16.0, 17.0, 18.0],
        "et0_mm": [1.5, 1.6, 1.7],
        "soil_moisture": [0.3, 0.31, 0.32],
    }


def test_fetch_weather_raw_batches_all_points_into_one_call_api_call():
    # Regression guard: fetch_weather_raw used to call call_api once PER
    # point, which at radius-search grid sizes (dozens to 100+ points)
    # exhausted Open-Meteo's free-tier hourly request quota on a single
    # prepare_trip run (observed live: a 121-point run failed mid-
    # climatology with "Hourly API request limit exceeded"). call_api must
    # now be invoked once with the whole points list and return one result
    # per point, in the same order.
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append((list(points), past_days))
        return [_fake_daily_payload(offset=i) for i in range(len(points))]

    df = fetch_weather_raw([(50.5, 18.6), (50.55, 18.65)], past_days=3, call_api=fake_call_api)

    assert calls == [([(50.5, 18.6), (50.55, 18.65)], 3)]
    assert len(df) == 6
    assert set(df.columns) >= {"lat", "lon", "date", "precipitation_mm", "tmean_c", "tmin_c", "tmax_c", "et0_mm", "soil_moisture"}
    # each point's own payload (offset) lands on the matching lat/lon rows
    first_point_rows = df[(df["lat"] == 50.5) & (df["lon"] == 18.6)]
    second_point_rows = df[(df["lat"] == 50.55) & (df["lon"] == 18.65)]
    assert sorted(first_point_rows["precipitation_mm"]) == [1.0, 2.0, 3.0]
    assert sorted(second_point_rows["precipitation_mm"]) == [2.0, 3.0, 4.0]


def test_fetch_weather_raw_handles_a_single_point():
    df = fetch_weather_raw(
        [(50.5, 18.6)], past_days=3,
        call_api=lambda points, past_days, forecast_days=1: [_fake_daily_payload()],
    )
    assert len(df) == 3
    assert (df["lat"] == 50.5).all()


def test_fetch_weather_raw_passes_forecast_days_through_to_call_api():
    # spec 3.3 "Prognoza do dnia wyjazdu" (plan 2.1 step A3): forecast_days
    # must reach the real Open-Meteo request, not stay hardcoded at 1.
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append((past_days, forecast_days))
        return [_fake_daily_payload() for _ in points]

    fetch_weather_raw([(50.5, 18.6)], past_days=3, forecast_days=7, call_api=fake_call_api)

    assert calls == [(3, 7)]


def test_fetch_weather_raw_with_cache_dir_skips_call_api_on_a_repeat_call(tmp_path):
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(list(points))
        return [_fake_daily_payload(offset=i) for i in range(len(points))]

    points = [(50.5, 18.6), (50.55, 18.65)]
    fetch_weather_raw(points, past_days=3, call_api=fake_call_api, cache_dir=tmp_path)
    df = fetch_weather_raw(points, past_days=3, call_api=fake_call_api, cache_dir=tmp_path)

    assert len(calls) == 1  # second call served entirely from the point cache
    assert len(df) == 6


def test_fetch_weather_raw_with_cache_dir_fetches_only_the_new_point(tmp_path):
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(list(points))
        return [_fake_daily_payload(offset=i) for i in range(len(points))]

    fetch_weather_raw([(50.5, 18.6)], past_days=3, call_api=fake_call_api, cache_dir=tmp_path)
    fetch_weather_raw([(50.5, 18.6), (50.6, 18.7)], past_days=3, call_api=fake_call_api, cache_dir=tmp_path)

    assert calls == [[(50.5, 18.6)], [(50.6, 18.7)]]


def test_fetch_weather_raw_point_cache_distinguishes_different_forecast_horizons_same_day(tmp_path):
    # Two runs on the same day with a different --date (so a different
    # forecast_days) must NOT share a cache entry: the underlying Open-Meteo
    # response actually differs (different forecast length), so a shared
    # entry would silently serve a stale/too-short window (plan 2.1 step A3
    # requirement).
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(forecast_days)
        return [_fake_daily_payload() for _ in points]

    points = [(50.5, 18.6)]
    fetch_weather_raw(points, past_days=3, forecast_days=1, call_api=fake_call_api, cache_dir=tmp_path)
    fetch_weather_raw(points, past_days=3, forecast_days=5, call_api=fake_call_api, cache_dir=tmp_path)

    assert calls == [1, 5]  # both fetched -- no false cache hit across horizons

    # Re-running the SAME horizon again on the same day is still a cache hit.
    fetch_weather_raw(points, past_days=3, forecast_days=5, call_api=fake_call_api, cache_dir=tmp_path)
    assert calls == [1, 5]


def test_fetch_weather_raw_point_cache_distinguishes_different_past_days_same_day(tmp_path):
    # Plan 1.8e: past_days must be part of the cache key too, not just
    # forecast_days -- a different rolling-window length is a genuinely
    # different Open-Meteo response, same reasoning as forecast_days above.
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(past_days)
        return [_fake_daily_payload() for _ in points]

    points = [(50.5, 18.6)]
    fetch_weather_raw(points, past_days=3, call_api=fake_call_api, cache_dir=tmp_path)
    fetch_weather_raw(points, past_days=92, call_api=fake_call_api, cache_dir=tmp_path)

    assert calls == [3, 92]  # both fetched -- no false cache hit across window lengths


def test_fetch_weather_raw_point_cache_expires_the_next_day(tmp_path, monkeypatch):
    import pipeline.weather as weather_mod

    class FrozenDate(weather_mod.date):
        _today = weather_mod.date(2026, 9, 24)

        @classmethod
        def today(cls):
            return cls._today

    monkeypatch.setattr(weather_mod, "date", FrozenDate)
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(list(points))
        return [_fake_daily_payload() for _ in points]

    points = [(50.5, 18.6)]
    fetch_weather_raw(points, past_days=3, call_api=fake_call_api, cache_dir=tmp_path)
    FrozenDate._today = weather_mod.date(2026, 9, 25)
    fetch_weather_raw(points, past_days=3, call_api=fake_call_api, cache_dir=tmp_path)

    assert len(calls) == 2  # new day -> cache miss, refetched


def _synthetic_daily_df():
    dates = pd.date_range("2026-05-01", periods=30, freq="D")
    return pd.DataFrame({
        "lat": [50.5] * 30,
        "lon": [18.6] * 30,
        "date": dates,
        "precipitation_mm": [1.0] * 30,
        "tmean_c": [13.0] * 30,
        "tmin_c": [5.0] * 30,
        "tmax_c": [20.0] * 30,
        "et0_mm": [1.0] * 30,
        "soil_moisture": [0.4] * 30,
    })


def test_compute_weather_features_windows():
    # spec 5.4 "Zmiany w F (2.1)" / plan 2.1 step C2: P1/P3/P7/P14/P21/P30
    # and dry_spell_days are dead (never fed into F, spec 14 rejects them as
    # features) and were removed. p5 stays (heat-penalty input,
    # heat_penalty_p5_mm); days_since_p10 stays (banner only, not an F
    # input).
    feat = compute_weather_features(_synthetic_daily_df())
    row = feat.iloc[0]
    assert row["p5"] == pytest.approx(5.0)
    assert row["tmean20"] == pytest.approx(13.0)
    assert row["tmin3"] == pytest.approx(5.0)
    assert row["days_since_p10"] >= 29  # no day ever reached 10mm
    for dead_column in ("p1", "p3", "p7", "p14", "p21", "p30", "dry_spell_days"):
        assert dead_column not in feat.columns


def test_fetch_climatology_raw_batches_all_points_into_one_call_api_call():
    # Same regression as fetch_weather_raw above -- this is the fetcher
    # that actually failed live ("Hourly API request limit exceeded" during
    # "Klimatologia: punkt 14/121"), since climatology's 30-year archive
    # request is the more expensive of the two per-call.
    calls = []

    def fake_call_api(points, start_year, end_year):
        calls.append((list(points), start_year, end_year))
        dates = pd.date_range("2020-06-25", periods=2, freq="D")
        return [{"date": dates, "cwb26": [1.0, 2.0], "soil_moisture": [0.3, 0.31]} for _ in points]

    df = fetch_climatology_raw(
        [(50.5, 18.6), (50.55, 18.65)], start_year=1991, end_year=2020, call_api=fake_call_api,
    )

    assert calls == [([(50.5, 18.6), (50.55, 18.65)], 1991, 2020)]
    assert len(df) == 4
    assert set(df["lat"]) == {50.5, 50.55}


def test_fetch_climatology_raw_with_cache_dir_never_expires(tmp_path):
    calls = []

    def fake_call_api(points, start_year, end_year):
        calls.append(list(points))
        dates = pd.date_range("2020-06-25", periods=2, freq="D")
        return [{"date": dates, "cwb26": [1.0, 2.0], "soil_moisture": [0.3, 0.31]} for _ in points]

    points = [(50.5, 18.6)]
    fetch_climatology_raw(points, start_year=1991, end_year=2020, call_api=fake_call_api, cache_dir=tmp_path)
    fetch_climatology_raw(points, start_year=1991, end_year=2020, call_api=fake_call_api, cache_dir=tmp_path)

    assert len(calls) == 1


def test_fetch_climatology_raw_distinguishes_different_year_ranges(tmp_path):
    # Plan 1.8e: start_year/end_year must be part of the cache key -- a
    # cached point from one 30-year range must never be silently served for
    # a request naming a different range (spec S13.1: "klimatologia nie ma
    # w kluczu daty waznosci"/zakresu lat).
    calls = []

    def fake_call_api(points, start_year, end_year):
        calls.append((start_year, end_year))
        dates = pd.date_range("2020-06-25", periods=2, freq="D")
        return [{"date": dates, "cwb26": [1.0, 2.0], "soil_moisture": [0.3, 0.31]} for _ in points]

    points = [(50.5, 18.6)]
    fetch_climatology_raw(points, start_year=1991, end_year=2020, call_api=fake_call_api, cache_dir=tmp_path)
    fetch_climatology_raw(points, start_year=1981, end_year=2010, call_api=fake_call_api, cache_dir=tmp_path)

    assert calls == [(1991, 2020), (1981, 2010)]  # both fetched -- no false cache hit across ranges


def test_percentile_rank_of_median_like_value():
    historical = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert percentile_rank(30.0, historical) == pytest.approx(0.5, abs=0.15)
    assert percentile_rank(5.0, historical) == pytest.approx(0.0, abs=0.05)
    assert percentile_rank(55.0, historical) == pytest.approx(1.0, abs=0.05)


def test_percentile_rank_ignores_nan_entries():
    # Plan 1.8d: a real but incomplete window (NaN gaps) must rank against
    # only the valid entries, not let scipy see the NaNs at all.
    with_gaps = np.array([10.0, np.nan, 20.0, 30.0, np.nan, 40.0, 50.0])
    clean = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert percentile_rank(30.0, with_gaps) == pytest.approx(percentile_rank(30.0, clean))


def test_percentile_rank_all_nan_falls_back_to_neutral():
    assert percentile_rank(30.0, np.array([np.nan, np.nan])) == 0.5


# --- Plan 1.8b: shared, DST-safe local-date conversion ----------------------
# One shared test across both of 2026's Polish DST transition dates, for the
# ONE function (to_local_date) now used by pipeline.radar.merge_radar_into_daily,
# pipeline.flush.area_daily_weather and pipeline.conditions_timeline.with_local_date
# alike (plan text: "wspolny test... na 2026-03-29 i 2026-10-25").

def test_to_local_date_correct_across_october_fall_back_transition():
    # Without the noon-recentering fix, the fixed-86400s-step date column
    # (the real _parse_open_meteo_response construction) reads a FULL DAY
    # EARLY for 2026-10-26 onward: naive UTC 2026-10-25T22:00 converts (post-
    # transition, UTC+1) to local 2026-10-25T23:00 -- date() = Oct 25, not
    # the intended Oct 26 (verified by hand against zoneinfo for this exact
    # date range; see this test's git history/commit message for the numbers).
    days = pd.date_range("2026-10-23", periods=6, freq="D").date
    dates = _fixed_step_dates(days[0], len(days))
    assert list(to_local_date(dates)) == list(days)


def test_to_local_date_correct_across_march_spring_forward_transition():
    # The fixed-step drift here is 1h LATE instead of early, which (for this
    # specific date range) happens to stay within the same calendar day even
    # without the fix -- this test just confirms the fix doesn't break the
    # case that already worked, alongside the October case that didn't.
    days = pd.date_range("2026-03-27", periods=6, freq="D").date
    dates = _fixed_step_dates(days[0], len(days))
    assert list(to_local_date(dates)) == list(days)


def test_to_local_date_passes_through_naive_dates_unchanged():
    naive = pd.Series(pd.date_range("2026-06-01", periods=3, freq="D"))
    assert list(to_local_date(naive)) == list(naive.dt.date)


# --- Plan 1.7/1.8d: climatology_window_insufficient -------------------------

def test_climatology_window_insufficient_true_when_empty():
    assert climatology_window_insufficient(np.array([])) is True


def test_climatology_window_insufficient_true_below_half_valid():
    # 2 valid out of 5 = 40% < 50%.
    window = np.array([1.0, 2.0, np.nan, np.nan, np.nan])
    assert climatology_window_insufficient(window) is True


def test_climatology_window_insufficient_false_at_or_above_half_valid():
    # 3 valid out of 5 = 60% >= 50%.
    window = np.array([1.0, 2.0, 3.0, np.nan, np.nan])
    assert climatology_window_insufficient(window) is False


def test_climatology_window_insufficient_false_when_fully_populated():
    assert climatology_window_insufficient(np.array([1.0, 2.0, 3.0])) is False


def test_climatology_window_values_filters_by_point_and_doy_window():
    clim_df = pd.DataFrame({
        "lat": [50.5, 50.5, 50.5, 50.5, 60.0],
        "lon": [18.6, 18.6, 18.6, 18.6, 18.6],
        "date": pd.to_datetime(["2000-08-10", "2000-08-20", "2000-09-15", "2005-08-12", "2000-08-11"]),
        "cwb26": [1.0, 2.0, 99.0, 3.0, 100.0],
    })
    # target day_of_year ~ Aug 15 (227), window 15 days -> Aug 1..Aug 30 roughly
    from datetime import date
    doy = date(2026, 8, 15).timetuple().tm_yday
    values = climatology_window_values(clim_df, lat=50.5, lon=18.6, day_of_year=doy, column="cwb26", window_days=15)
    assert 1.0 in values and 2.0 in values and 3.0 in values
    assert 99.0 not in values   # outside +/-15 day window (Sep 15)
    assert 100.0 not in values  # wrong point (lat 60.0)


def test_compute_weather_features_rain_radar_coverage_is_exp_weighted_radar_frac():
    dates = pd.date_range("2026-09-01", periods=26, freq="D")
    frac = [0.0] * 25 + [1.0]  # only the most recent day from radar
    df = pd.DataFrame({"lat": 50.0, "lon": 21.0, "date": dates, "precipitation_mm": 1.0,
                       "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0, "et0_mm": 1.0,
                       "soil_moisture": 0.3, "radar_frac": frac})
    feat = compute_weather_features(df).iloc[0]
    weights = 0.5 ** (np.arange(25, -1, -1) / 10.0)
    assert feat["rain_radar_coverage"] == pytest.approx(weights[-1] / weights.sum())


def test_compute_weather_features_without_radar_frac_reports_zero_coverage():
    dates = pd.date_range("2026-09-01", periods=5, freq="D")
    df = pd.DataFrame({"lat": 50.0, "lon": 21.0, "date": dates, "precipitation_mm": 1.0,
                       "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0, "et0_mm": 1.0,
                       "soil_moisture": 0.3})
    assert compute_weather_features(df).iloc[0]["rain_radar_coverage"] == 0.0


def _uniform_stand_precip(stand_specs: dict[str, tuple[float, float]], n_days: int = 30) -> pd.DataFrame:
    """`stand_specs`: {stand_id: (precip_mm_per_day, radar_frac)} -- every
    stand gets the SAME date range (n_days), just different constant values,
    matching the real shape stand_radar_precip_daily always produces (one
    row per stand per date of one shared weather fetch)."""
    dates = pd.date_range("2026-08-01", periods=n_days, freq="D")
    frames = []
    for sid, (mm, frac) in stand_specs.items():
        frames.append(pd.DataFrame({"stand_id": sid, "date": dates, "precipitation_mm": mm, "radar_frac": frac}))
    return pd.concat(frames, ignore_index=True)


def test_stand_precip_features_table_matches_precip_derived_features_per_stand():
    df = _uniform_stand_precip({"a": (2.0, 1.0), "b": (10.0, 0.25)}, n_days=30)
    table = stand_precip_features_table(df)
    for sid in ("a", "b"):
        g = df[df["stand_id"] == sid].sort_values("date")
        expected = precip_derived_features(g["precipitation_mm"], g["radar_frac"])
        assert table.loc[sid, "p5"] == pytest.approx(expected["p5"])
        assert table.loc[sid, "p26w"] == pytest.approx(expected["p26w"])
        assert table.loc[sid, "rain_radar_coverage"] == pytest.approx(expected["rain_radar_coverage"])


def test_stand_precip_features_table_row_order_does_not_matter():
    df = _uniform_stand_precip({"a": (2.0, 1.0), "b": (10.0, 0.25)}, n_days=30)
    shuffled = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
    table = stand_precip_features_table(shuffled)
    expected = stand_precip_features_table(df)
    assert table.loc["a"].tolist() == pytest.approx(expected.loc["a"].tolist())
    assert table.loc["b"].tolist() == pytest.approx(expected.loc["b"].tolist())


def test_stand_precip_features_table_falls_back_for_uneven_group_sizes():
    # Real stand_radar_precip_daily output always has one row per stand per
    # shared date range (uniform) -- this exercises the defensive fallback
    # path for a hand-built fixture that doesn't hold that invariant.
    dates_a = pd.date_range("2026-08-01", periods=10, freq="D")
    dates_b = pd.date_range("2026-08-01", periods=5, freq="D")
    df = pd.concat([
        pd.DataFrame({"stand_id": "a", "date": dates_a, "precipitation_mm": 2.0, "radar_frac": 1.0}),
        pd.DataFrame({"stand_id": "b", "date": dates_b, "precipitation_mm": 10.0, "radar_frac": 0.5}),
    ], ignore_index=True)
    table = stand_precip_features_table(df)
    expected_a = precip_derived_features(pd.Series([2.0] * 10), pd.Series([1.0] * 10))
    expected_b = precip_derived_features(pd.Series([10.0] * 5), pd.Series([0.5] * 5))
    assert table.loc["a", "p26w"] == pytest.approx(expected_a["p26w"])
    assert table.loc["b", "p26w"] == pytest.approx(expected_b["p26w"])


# --- regresja: cache + swiezy pobor punktow (pandas 3: concat roznych rozdzielczosci dat -> object) ---

def _fake_point_data(resolution: str, days: int = 5) -> dict:
    """Mimics pipeline.weather._parse_open_meteo_response: a tz-aware date range at
    second resolution (a fresh API response), while a parquet round trip
    (the per-point cache) gives millisecond resolution."""
    start = pd.Timestamp("2026-09-20", tz="UTC").as_unit(resolution)
    dates = pd.date_range(start=start, periods=days, freq="D")
    zeros = np.zeros(days)
    return {"date": dates, "precipitation_mm": zeros, "tmean_c": zeros, "tmin_c": zeros,
            "tmax_c": zeros, "et0_mm": zeros, "soil_moisture": zeros}


def test_fetch_weather_raw_mixing_cached_and_fresh_points_keeps_datetime_dtype(tmp_path):
    from pipeline.weather import fetch_weather_raw, to_local_date
    points = [(50.0, 18.0), (50.1, 18.1), (50.2, 18.2), (50.3, 18.3)]
    api = lambda pts, past, forecast_days=1: [_fake_point_data("s") for _ in pts]
    fetch_weather_raw(points[:2], 92, 1, api, tmp_path)         # fills the per-point cache (2 points)
    result = fetch_weather_raw(points, 92, 1, api, tmp_path)    # 2 from cache + 2 fresh, like a 25 km run
    assert isinstance(result["date"].dtype, pd.DatetimeTZDtype)  # was `object` -> .dt crashed in radar merge
    assert len(to_local_date(result["date"])) == len(result)


def test_fetch_climatology_raw_mixing_cached_and_fresh_points_keeps_datetime_dtype(tmp_path):
    from pipeline.weather import fetch_climatology_raw
    points = [(50.0, 18.0), (50.1, 18.1), (50.2, 18.2)]
    api = lambda pts, start, end: [_fake_point_data("s") for _ in pts]
    fetch_climatology_raw(points[:1], 1991, 2020, api, tmp_path)
    result = fetch_climatology_raw(points, 1991, 2020, api, tmp_path)
    assert isinstance(result["date"].dtype, pd.DatetimeTZDtype)
