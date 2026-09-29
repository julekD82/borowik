"""Faza 4: skladniki pogody (4.3), udzial prognozy w oknie (4.5)."""
import math
from datetime import date

import pandas as pd
import pytest

from pipeline.orchestrate import run_poc
from pipeline.weather import forecast_window_share, compute_weather_features
from tests.test_faza4_r_niezmienione import BBOX, PROFILE, _bdl, _clim, _weather


def test_forecast_window_share_is_zero_for_a_trip_today_and_one_for_a_full_window():
    assert forecast_window_share(0) == 0.0
    assert forecast_window_share(26) == pytest.approx(1.0)
    assert forecast_window_share(40) == pytest.approx(1.0)


def test_forecast_window_share_weights_recent_days_more_than_a_plain_count():
    share = forecast_window_share(4)
    assert share > 4 / 26          # dni wyjazdu waza najwiecej
    assert share == pytest.approx(sum(0.5 ** (a / 10) for a in range(4)) / sum(0.5 ** (a / 10) for a in range(26)))
    assert forecast_window_share(5) > forecast_window_share(4)


def test_weather_features_expose_plain_26_day_sum_and_coldest_recent_day():
    dates = pd.date_range("2026-09-01", periods=30, freq="D")
    df = pd.DataFrame({"lat": 50.0, "lon": 19.0, "date": dates, "precipitation_mm": 1.0,
                       "tmean_c": 10.0, "tmin_c": [5.0] * 27 + [2.0, -1.5, 0.5],
                       "tmax_c": 15.0, "et0_mm": 1.0})
    row = compute_weather_features(df).iloc[0]
    assert row["p26_sum"] == pytest.approx(26.0)
    assert row["tmin3"] == pytest.approx(-1.5)
    assert row["tmin3_date"] == str(dates[28].date())


def test_run_poc_exposes_weather_components_without_touching_f():
    r = run_poc(layer="X", bbox_2180=BBOX, profile=PROFILE, bdl_fetcher=_bdl, weather_fetcher=_weather,
                climatology_fetcher=_clim, grid_spacing_m=5000.0, past_days=60, target_date=date(2026, 9, 29))
    for col in ["p26_mm", "cwb26_mm", "cwb26_typical_mm", "tmean20_c", "tmin3_c", "tmin3_date",
                "forecast_window_share"]:
        assert col in r.columns
    assert (r["p26_mm"] >= 0).all()
    assert r["cwb26_typical_mm"].notna().all()
    # skladniki zgadzaja sie z percentylem: cwb26_mm wyzej niz typowy <=> percentyl > 0,5 (rozklad mediana ~20)
    assert all((c > t) == (p > 0.5) for c, t, p in zip(r["cwb26_mm"], r["cwb26_typical_mm"], r["pct_CWB26"]))


def test_run_poc_forecast_window_share_follows_days_ahead(monkeypatch):
    import pipeline.orchestrate as orch
    from datetime import timedelta

    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 25)

    monkeypatch.setattr(orch, "date", FakeDate)
    r = run_poc(layer="X", bbox_2180=BBOX, profile=PROFILE, bdl_fetcher=_bdl, weather_fetcher=_weather,
                climatology_fetcher=_clim, grid_spacing_m=5000.0, past_days=60, target_date=date(2026, 9, 29))
    assert r["forecast_days"].iloc[0] == 5
    assert r["forecast_window_share"].iloc[0] == pytest.approx(forecast_window_share(4))


# --- eksport karty pogody (4.3/4.5) ---

def _row(**over):
    base = {"p26_mm": 61.2, "cwb26_mm": 22.5, "cwb26_typical_mm": 18.0, "pct_CWB26": 0.62,
            "tmean20_c": 12.4, "tmin3_c": 3.1, "tmin3_date": "2026-09-28", "F": 0.66, "M": 0.7, "T": 0.9,
            "K_frost": 1.0, "G_season": 0.88, "forecast_days": 5, "forecast_window_share": 0.15}
    base.update(over)
    return pd.Series(base)


def test_weather_card_has_components_optimum_and_forecast_share():
    from pipeline.export import build_weather_card
    card = build_weather_card(_row(), PROFILE)
    assert card["p26_mm"] == 61.2 and card["cwb26_typical_mm"] == 18.0 and card["pct_cwb26"] == 0.62
    assert card["temp_optimum_c"] == PROFILE["fruiting"]["temp_optimum_c"]
    assert card["frost"] == "brak" and card["frost_date"] is None
    assert card["F"] == 0.66 and card["forecast_window_share"] == 0.15


def test_weather_card_frost_levels_use_profile_thresholds_and_report_when():
    from pipeline.export import build_weather_card
    soft = build_weather_card(_row(tmin3_c=-0.5), PROFILE)
    hard = build_weather_card(_row(tmin3_c=-3.0), PROFILE)
    assert (soft["frost"], soft["frost_date"]) == ("slaby", "2026-09-28")
    assert (hard["frost"], hard["frost_date"]) == ("silny", "2026-09-28")


def test_weather_card_is_none_for_rows_without_the_columns_and_json_safe_for_nan():
    import json
    from pipeline.export import build_weather_card
    assert build_weather_card(pd.Series({"F": 0.5}), PROFILE) is None
    card = build_weather_card(_row(cwb26_typical_mm=float("nan")), PROFILE)
    assert card["cwb26_typical_mm"] is None
    json.dumps(card, allow_nan=False)


# --- poprawka 4: panel liczy opad tak jak mapa ---

def test_stand_precip_aggregates_to_points_by_area_weight_and_only_masked_stands():
    import geopandas as gpd
    from shapely.geometry import box
    from pipeline.prepare_trip import stand_precip_to_points
    scored = gpd.GeoDataFrame({
        "stand_id": ["a", "b", "c"], "mask": [True, True, False],
        "weather_point_lat": [50.0, 50.0, 50.0], "weather_point_lon": [19.0, 19.0, 19.0],
        "geometry": [box(0, 0, 100, 100), box(0, 0, 300, 100), box(0, 0, 9999, 9999)],
    }, crs="EPSG:2180")
    d = pd.date_range("2026-09-01", periods=2, freq="D", tz="UTC")
    sp = pd.DataFrame({"stand_id": ["a"] * 2 + ["b"] * 2 + ["c"] * 2, "date": list(d) * 3,
                       "precipitation_mm": [4.0, 0.0, 0.0, 8.0, 100.0, 100.0],
                       "radar_frac": [1.0, 1.0, 0.0, 0.0, 1.0, 1.0]})
    out = stand_precip_to_points(sp, scored).sort_values("date").reset_index(drop=True)
    assert out["precipitation_mm"].tolist() == pytest.approx([1.0, 6.0])   # (1*4+3*0)/4 ; (1*0+3*8)/4
    assert out["radar_frac"].tolist() == pytest.approx([0.25, 0.25])


def test_apply_point_precip_overrides_matching_rows_and_keeps_model_elsewhere():
    from pipeline.prepare_trip import apply_point_precip
    d = pd.date_range("2026-09-01", periods=2, freq="D", tz="UTC")
    daily = pd.DataFrame({"lat": [50.0, 50.0, 51.0, 51.0], "lon": [19.0] * 4, "date": list(d) * 2,
                          "precipitation_mm": [2.0, 2.0, 3.0, 3.0]})
    pp = pd.DataFrame({"lat": [50.0], "lon": [19.0], "date": [d[0]], "precipitation_mm": [9.0], "radar_frac": [1.0]})
    out = apply_point_precip(daily, pp)
    assert out["precipitation_mm"].tolist() == [9.0, 2.0, 3.0, 3.0]
    assert out["radar_frac"].tolist() == [1.0, 0.0, 0.0, 0.0]


def test_truncate_trailing_days_drops_only_the_last_n_dates():
    from pipeline.prepare_trip import truncate_trailing_days
    d = pd.date_range("2026-09-01", periods=5, freq="D")
    df = pd.DataFrame({"stand_id": ["a"] * 5 + ["b"] * 5, "date": list(d) * 2, "v": range(10)})
    assert truncate_trailing_days(df, 0) is df
    out = truncate_trailing_days(df, 2)
    assert sorted(out["date"].unique()) == list(d[:3]) and len(out) == 6
