import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from pipeline.habitat import load_profile
from pipeline.phenology import compute_g_season
from pipeline.scoring import classify_fruiting_level, compute_fruiting, score_frost, score_moisture, score_temperature
from pipeline.weather import climatology_window_values, compute_weather_features, percentile_rank
from pipeline.conditions_timeline import (
    build_conditions_timeline, rains_summary, recent_rains, with_local_date,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")
D0 = date(2026, 9, 20)


def test_with_local_date_converts_utc_midnight_to_local_day():
    utc_midnights = pd.to_datetime(["2026-09-20 22:00", "2026-09-21 22:00"], utc=True)  # local 21.09, 22.09
    daily = pd.DataFrame({"lat": [50.0, 50.0], "lon": [21.0, 21.0], "date": utc_midnights,
                          "precipitation_mm": [1.0, 2.0]})
    out = with_local_date(daily)
    assert out["local_date"].tolist() == [date(2026, 9, 21), date(2026, 9, 22)]


def _area(precip, start=D0):
    idx = [start + timedelta(days=k) for k in range(len(precip))]
    return pd.DataFrame({"precipitation_mm": precip}, index=idx)


def test_recent_rains_excludes_a_pulse_not_yet_ended():
    precip = [0, 0, 0, 0, 0, 20, 0, 0, 0, 25, 0, 0]  # pulse at idx5 (past), idx9 (future vs today)
    today = D0 + timedelta(days=7)
    rains = recent_rains(_area(precip), today, PROFILE)
    assert rains == [{"start": "2026-09-25", "end": "2026-09-25", "rain_mm": 20.0, "days_ago": 2}]


def test_recent_rains_returns_up_to_max_rains_most_recent_first():
    precip = [0, 0, 20, 0, 0, 0, 20, 0, 0, 0, 20, 0, 0, 0, 0]
    today = D0 + timedelta(days=14)
    rains = recent_rains(_area(precip), today, PROFILE)
    assert [r["start"] for r in rains] == ["2026-09-30", "2026-09-26"]  # 2 most recent, newest first


def test_recent_rains_rejects_missing_today():
    with pytest.raises(ValueError):
        recent_rains(_area([0.0] * 5), date(2026, 12, 1), PROFILE)


def test_recent_rains_ignores_forecast_rain_when_detecting_past_pulses():
    # Review finding: detect_pulses' one-dry-day-gap rule must not let a
    # FORECAST wet day (not yet fallen) bridge across the gap and merge
    # with an already-fallen pulse, pushing the merged pulse's `end` into
    # the future and so dropping it entirely from recent_rains (real past
    # rain must never vanish because of what the forecast says).
    precip = [0, 0, 0, 10, 10, 10, 0, 2, 3]  # pulse days 3-5 (30mm), dry day 6, today(day7)=2mm, forecast day8=3mm
    today = D0 + timedelta(days=7)
    rains = recent_rains(_area(precip), today, PROFILE)
    assert rains == [{"start": "2026-09-23", "end": "2026-09-27", "rain_mm": 32.0, "days_ago": 0}]


def test_rains_summary_formats_dates_mm_and_days_ago():
    rains = [{"start": "2026-09-25", "end": "2026-09-25", "rain_mm": 20.0, "days_ago": 2},
             {"start": "2026-09-11", "end": "2026-09-12", "rain_mm": 20.3, "days_ago": 15}]
    assert rains_summary(rains, 15.0) == (
        "Ostatni większy deszcz: 25.09 (20.0 mm), 2 dni temu"
        " · wcześniejszy deszcz: 11–12.09 (20.3 mm), 15 dni temu")


def test_rains_summary_without_rains_states_the_threshold():
    assert rains_summary([], 15.0) == "Brak deszczu ≥ 15 mm w ostatnich dniach."


def _daily_multi_point(points, start, days, precip=2.0, et0=1.0, tmean=13.0, tmin=6.0):
    """`tmean` may be a scalar (constant every day) or a callable of the
    day index (0-based) -- the latter lets a test vary weather over the
    fetched window, so per-day truncation in build_conditions_timeline is
    actually load-bearing (a constant fixture can't distinguish "today's
    window" from "the whole 47-day frame")."""
    rows = []
    for lat, lon in points:
        for i, d in enumerate(pd.date_range(start, periods=days, freq="D", tz="UTC")):
            t = tmean(i) if callable(tmean) else tmean
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": precip,
                         "et0_mm": et0, "tmean_c": t, "tmin_c": tmin})
    return pd.DataFrame(rows)


def _clim(points, cwb26=30.0):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2000-01-01", periods=400, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": cwb26})
    return pd.DataFrame(rows)


def test_build_conditions_timeline_rejects_missing_today():
    points = [(50.0, 21.0)]
    daily = _daily_multi_point(points, "2026-08-01", 10)
    with pytest.raises(ValueError):
        build_conditions_timeline(daily, points, _clim(points), points, date(2026, 12, 1), PROFILE)


def test_build_conditions_timeline_seven_days_match_direct_recomputation():
    # Review finding: with CONSTANT fixture weather every rolling window is
    # identical regardless of which day it ends on, so a bug that skipped
    # per-day truncation entirely (e.g. always using the whole 47-day
    # frame) would still pass. tmean ramps day-over-day so each horizon
    # day's trailing windows (tmean20/tmean5) genuinely differ, and the
    # direct-recomputation below only matches production if it truncates
    # to the SAME day each time.
    points = [(50.0, 21.0), (50.1, 21.1)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    daily = _daily_multi_point(points, start, 47, tmean=lambda i: 5.0 + 0.4 * i)
    clim_df = _clim(points)

    legacy = {**PROFILE, "conditions": {**PROFILE["conditions"], "aggregation": "median_of_features"}}
    out = build_conditions_timeline(daily, points, clim_df, points, today, legacy)

    assert [d["date"] for d in out["days"]] == [(today + timedelta(days=k)).isoformat() for k in range(7)]
    assert out["days"][0]["forecast"] is False and all(d["forecast"] for d in out["days"][1:])
    # The ramp must actually reach the per-day F values, not just the
    # per-day date/forecast bookkeeping above -- catches a mutation that
    # feeds every day the same (e.g. last-day-only) weather window.
    assert len({d["F"] for d in out["days"]}) > 1

    with_ld = with_local_date(daily)
    for k, entry in enumerate(out["days"]):
        day_k = today + timedelta(days=k)
        sub = with_ld[with_ld["local_date"] <= day_k]
        feats = compute_weather_features(sub)
        target_doy = day_k.timetuple().tm_yday
        cwb_hist = np.concatenate([climatology_window_values(clim_df, lat, lon, target_doy, "cwb26")
                                    for lat, lon in points])
        pct_cwb26 = percentile_rank(float(feats["cwb26"].median()), cwb_hist)
        m = score_moisture(pct_cwb26, 0.5, PROFILE)
        t = score_temperature(float(feats["tmean20"].median()), float(feats["tmean5"].median()),
                              float(feats["p5"].median()), PROFILE)
        k_frost = score_frost(float(feats["tmin3"].median()), PROFILE)
        g_season = compute_g_season(target_doy, PROFILE)
        expected_f = compute_fruiting(m, t, k_frost, g_season=g_season)
        assert entry["F"] == pytest.approx(round(expected_f, 3))
        assert entry["level"] == classify_fruiting_level(expected_f, PROFILE)


def test_conditions_timeline_does_not_use_the_disproven_wave_model():
    # Structural guarantee (Plan-B): production reuses only pulse DETECTION
    # from pipeline.flush, never its thermal-clock/Gaussian model.
    src = pathlib.Path("pipeline/conditions_timeline.py").read_text(encoding="utf-8")
    for name in ["wave_intensity", "wave_phase", "peak_window", "build_area_timeline",
                 "PHASE_LABELS", "degree_days_after", "timeline_summary", "flush_series"]:
        assert name not in src, name


# --- Faza 4.3-4.5: skladniki, agregacja, niepewnosc ---

from pipeline.conditions_timeline import (  # noqa: E402
    aggregate_point_f, uncertainty_level, weighted_median, AGGREGATIONS,
)


def test_uncertainty_level_follows_profile_thresholds_in_days_ahead():
    assert [uncertainty_level(k, PROFILE) for k in (0, 3, 4, 7, 8, 12)] == [
        "ok", "ok", "uncertain", "uncertain", "indicative", "indicative"]
    custom = {"ui": {"forecast_uncertain_from_day": 2, "forecast_indicative_from_day": 5}}
    assert [uncertainty_level(k, custom) for k in (1, 2, 4, 5)] == ["ok", "uncertain", "uncertain", "indicative"]


def test_weighted_median_and_aggregations():
    assert weighted_median([1, 2, 3], [1, 1, 1]) == 2
    assert weighted_median([1, 2, 3], [10, 1, 1]) == 1          # jeden punkt z wiekszoscia wydzielen
    f = [0.2, 0.6, 0.8]
    assert aggregate_point_f(f, "median_f_points") == pytest.approx(0.6)
    assert aggregate_point_f(f, "median_f_stands", stand_weights=[10, 1, 1]) == pytest.approx(0.2)
    assert aggregate_point_f(f, "area_weighted_mean", area_weights=[1, 1, 2]) == pytest.approx((0.2 + 0.6 + 1.6) / 4)
    with pytest.raises(ValueError):
        aggregate_point_f(f, "nie_ma")


def _timeline(points, tmin=None, profile=PROFILE, weights=None, tmean_by_point=None):
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    daily = _daily_multi_point(points, start, 47, tmean=lambda i: 8.0 + 0.1 * i)
    if tmin:
        for (lat, lon), value in tmin.items():
            daily.loc[(daily["lat"] == lat) & (daily["lon"] == lon), "tmin_c"] = value
    return build_conditions_timeline(daily, points, _clim(points), points, today, profile, point_weights=weights)


def test_timeline_days_carry_components_uncertainty_and_area_shares():
    points = [(50.0, 21.0), (50.1, 21.1)]
    out = _timeline(points, tmin={(50.1, 21.1): -1.0},
                    weights={(50.0, 21.0): {"area_ha": 300.0, "stands": 30}, (50.1, 21.1): {"area_ha": 100.0, "stands": 10}})
    d0, d5 = out["days"][0], out["days"][5]
    assert d0["days_ahead"] == 0 and d0["uncertainty"] == "ok"
    assert d5["days_ahead"] == 5 and d5["uncertainty"] == "uncertain"
    c = d0["components"]
    assert set(c) >= {"cwb26_mm", "cwb26_typical_mm", "pct_cwb26", "tmean20_c", "temp_optimum_c", "tmin3_c", "M", "T", "K_frost"}
    assert c["temp_optimum_c"] == PROFILE["fruiting"]["temp_optimum_c"]
    # przymrozek tylko w punkcie z 25% powierzchni lasu -> mediana tmin3 go nie pokazuje, udzial tak
    assert d0["frost_area_share"] == pytest.approx(0.25)
    assert set(d0["F_by_aggregation"]) == set(AGGREGATIONS)


def test_timeline_default_aggregation_is_median_f_stands_and_legacy_option_keeps_the_pre_faza4_f():
    assert PROFILE["conditions"]["aggregation"] == "median_f_stands"
    points = [(50.0, 21.0), (50.1, 21.1), (50.2, 21.2)]
    frost = {(50.2, 21.2): -3.0}
    legacy = {**PROFILE, "conditions": {**PROFILE["conditions"], "aggregation": "median_of_features"}}
    base = _timeline(points, tmin=frost, profile=legacy)
    weights = {(50.0, 21.0): {"area_ha": 1.0, "stands": 1}, (50.1, 21.1): {"area_ha": 1.0, "stands": 1},
               (50.2, 21.2): {"area_ha": 98.0, "stands": 98}}
    prof = {**PROFILE, "conditions": {**PROFILE["conditions"], "aggregation": "area_weighted_mean"}}
    weighted = _timeline(points, tmin=frost, profile=prof, weights=weights)
    assert base["days"][0]["F"] == base["days"][0]["F_by_aggregation"]["median_of_features"]
    assert weighted["days"][0]["F"] == weighted["days"][0]["F_by_aggregation"]["area_weighted_mean"]
    assert weighted["days"][0]["F"] < base["days"][0]["F"]      # wieksza czesc lasu dostala przymrozek


def test_timeline_rejects_an_unknown_aggregation():
    prof = {**PROFILE, "conditions": {**PROFILE["conditions"], "aggregation": "x"}}
    with pytest.raises(ValueError):
        _timeline([(50.0, 21.0)], profile=prof)


def test_timeline_is_strict_json_even_with_an_empty_climatology_window():
    import json
    points = [(50.0, 21.0)]
    today = date(2026, 9, 27)
    daily = _daily_multi_point(points, pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40), 47)
    out = build_conditions_timeline(daily, points, _clim(points).iloc[:0], points, today, PROFILE)
    json.dumps(out, allow_nan=False)
    assert out["days"][0]["components"]["cwb26_typical_mm"] is None
    assert out["uncertainty_thresholds"] == {"uncertain_from_day": 4, "indicative_from_day": 8}
