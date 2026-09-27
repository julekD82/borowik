import math

import numpy as np
import pytest

from pipeline.flush import (
    FlushParams, Pulse, flush_params, detect_pulses, degree_days_after, wave_intensity, flush_series,
)
from pipeline.habitat import load_profile

PROFILE = load_profile("profiles/boletus_edulis.yaml")
P = FlushParams(wet_day_mm=1.0, pulse_min_mm=15.0, t_base_c=5.0, cold_night_c=5.0,
                cold_night_factor=0.5, frost_c=-1.0, dd_peak=100.0, dd_sigma=20.0)


def test_flush_params_scales_only_the_rain_threshold():
    base = flush_params(PROFILE)
    scaled = flush_params(PROFILE, rain_scale=0.5)
    assert scaled.pulse_min_mm == pytest.approx(base.pulse_min_mm * 0.5)
    assert scaled.dd_peak == base.dd_peak


def test_detect_pulses_merges_across_one_dry_day_and_applies_threshold():
    precip = [0, 5, 0, 12, 0, 0, 20, 0, 8, 0]
    pulses = detect_pulses(precip, P)
    assert pulses == [
        Pulse(start=1, end=3, rain_mm=17.0, strength=pytest.approx(17 / 30)),
        Pulse(start=6, end=8, rain_mm=28.0, strength=pytest.approx(28 / 30)),
    ]


def test_detect_pulses_does_not_merge_across_two_dry_days():
    assert detect_pulses([10, 0, 0, 10], P) == []  # two 10 mm episodes, each below 15


def test_degree_days_after_accumulates_from_the_day_after_the_pulse():
    dd = degree_days_after(1, tmean=[15, 15, 15, 15], tmin=[10, 10, 10, 10], params=P)
    assert math.isnan(dd[0]) and math.isnan(dd[1])
    assert dd[2:].tolist() == [10.0, 20.0]


def test_cold_night_halves_that_days_rate():
    dd = degree_days_after(0, tmean=[15, 15, 15], tmin=[10, 3, 10], params=P)
    assert dd[1:].tolist() == [5.0, 15.0]


def test_frost_ends_the_wave():
    dd = degree_days_after(0, tmean=[15, 15, 15, 15], tmin=[10, 10, -2, 10], params=P)
    assert dd[1] == 10.0 and np.isinf(dd[2]) and np.isinf(dd[3])
    assert wave_intensity(dd, 1.0, P)[2:].tolist() == [0.0, 0.0]


def test_wave_intensity_peaks_at_dd_peak_and_is_zero_before_the_pulse_ends():
    dd = np.array([np.nan, 100.0, 120.0])
    out = wave_intensity(dd, 0.8, P)
    assert out[0] == 0.0
    assert out[1] == pytest.approx(0.8)
    assert out[2] == pytest.approx(0.8 * math.exp(-0.5))


def test_flush_series_takes_the_stronger_of_overlapping_waves():
    precip = [20, 0, 0, 0, 30] + [0] * 15
    tmean, tmin = [15.0] * 20, [10.0] * 20
    index, pulses, dds = flush_series(precip, tmean, tmin, P)
    assert len(pulses) == 2 and len(dds) == 2
    expected = np.maximum(wave_intensity(dds[0], pulses[0].strength, P),
                          wave_intensity(dds[1], pulses[1].strength, P))
    assert index.tolist() == pytest.approx(expected.tolist())


from datetime import date, timedelta

import pandas as pd

from pipeline.flush import (
    PHASE_LABELS, wave_phase, peak_window, fmt_day_range, area_daily_weather,
    timeline_summary, build_area_timeline,
)


@pytest.mark.parametrize("dd,phase", [
    (50.0, "przed_fala"), (70.0, "poczatek"), (95.0, "szczyt"), (110.0, "szczyt"),
    (125.0, "starzeje_sie"), (150.0, "po_fali"), (math.inf, "po_fali"),
])
def test_wave_phase_boundaries(dd, phase):
    assert wave_phase(dd, P) == phase  # peak 100, sigma 20


def test_wave_phase_nan_is_przed_fala():
    assert wave_phase(float("nan"), P) == "przed_fala"


D0 = date(2026, 9, 20)


def _dates(n):
    return [D0 + timedelta(days=k) for k in range(n)]


def test_peak_window_from_series_and_by_extrapolation():
    tmean, tmin = [15.0] * 12, [10.0] * 12  # 10 DD/day from day 1
    full = degree_days_after(0, tmean, tmin, P)
    assert peak_window(full, _dates(12), P) == (D0 + timedelta(days=9), D0 + timedelta(days=11))
    short = degree_days_after(0, tmean[:5], tmin[:5], P)
    assert peak_window(short, _dates(5), P) == (D0 + timedelta(days=9), D0 + timedelta(days=11))


def test_peak_window_none_without_accumulated_days_or_after_frost():
    assert peak_window(np.array([np.nan, np.nan]), _dates(2), P) is None
    frost = degree_days_after(0, [15, 15, 15], [10, -5, 10], P)
    assert peak_window(frost, _dates(3), P) is None


def test_fmt_day_range():
    assert fmt_day_range(date(2026, 9, 21), date(2026, 9, 23)) == "21–23.09"
    assert fmt_day_range(date(2026, 9, 30), date(2026, 10, 2)) == "30.09–2.10"
    assert fmt_day_range(date(2026, 9, 11), date(2026, 9, 11)) == "11.09"


def test_area_daily_weather_uses_local_dates_and_median():
    utc_midnights = pd.to_datetime(["2026-09-20 22:00", "2026-09-21 22:00"], utc=True)  # local 21.09, 22.09
    rows = []
    for (lat, lon), mm in [((50.0, 21.0), 10.0), ((50.1, 21.1), 20.0), ((50.2, 21.2), 30.0), ((60.0, 10.0), 99.0)]:
        for d in utc_midnights:
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": mm, "tmean_c": 12.0, "tmin_c": 6.0})
    area = area_daily_weather(pd.DataFrame(rows), [(50.0, 21.0), (50.1, 21.1), (50.2, 21.2)])
    assert list(area.index) == [date(2026, 9, 21), date(2026, 9, 22)]
    assert area["precipitation_mm"].tolist() == [20.0, 20.0]  # (60, 10) not in points -> excluded


def _area(precip, tmean=15.0, tmin=10.0, start=D0):
    idx = [start + timedelta(days=k) for k in range(len(precip))]
    return pd.DataFrame({"precipitation_mm": precip, "tmean_c": tmean, "tmin_c": tmin}, index=idx)


def _profile(**overrides):
    flush = {**PROFILE["flush"], "pulse_min_mm": 15.0, "dd_peak": 100.0, "dd_sigma": 20.0,
             "t_base_c": 5.0, "cold_night_c": 5.0, **overrides}
    return {**PROFILE, "flush": flush}


def test_build_area_timeline_reports_upcoming_wave_and_seven_tiles():
    precip = [0.0] * 3 + [30.0] + [0.0] * 20   # pulse on 23.09, then 10 DD/day
    today = date(2026, 9, 26)                   # 3 days after -> DD 30 -> przed_fala
    out = build_area_timeline(_area(precip), today, _profile())
    assert out["generated_for"] == "2026-09-26"
    assert [d["date"] for d in out["days"]] == [(today + timedelta(days=k)).isoformat() for k in range(7)]
    assert out["days"][0]["forecast"] is False and all(d["forecast"] for d in out["days"][1:])
    assert all(0 <= d["level"] <= 3 for d in out["days"])
    (wave,) = out["waves"]
    assert wave["phase"] == "przed_fala" and wave["rain_start"] == wave["rain_end"] == "2026-09-23"
    assert (wave["peak_from"], wave["peak_to"]) == ("2026-10-02", "2026-10-04")
    assert out["summary"] == "Fala po deszczu 23.09: grzyby dopiero rosną, szczyt ok. 2–4.10"


def test_build_area_timeline_without_pulses_says_so():
    out = build_area_timeline(_area([0.0] * 20), date(2026, 9, 26), _profile())
    assert out["waves"] == []
    assert out["summary"].startswith("Brak świeżej fali po większym deszczu")
    assert all(d["level"] == 0 for d in out["days"])


def test_build_area_timeline_rejects_missing_today():
    with pytest.raises(ValueError):
        build_area_timeline(_area([0.0] * 5), date(2026, 12, 1), _profile())


def test_timeline_summary_lists_the_older_wave_second():
    waves = [
        {"rain_start": "2026-09-21", "rain_end": "2026-09-23", "phase": "poczatek",
         "phase_label": PHASE_LABELS["poczatek"], "peak_from": "2026-10-01", "peak_to": "2026-10-03"},
        {"rain_start": "2026-09-11", "rain_end": "2026-09-12", "phase": "starzeje_sie",
         "phase_label": PHASE_LABELS["starzeje_sie"], "peak_from": "2026-09-22", "peak_to": "2026-09-24"},
    ]
    assert timeline_summary(waves, 12.7) == (
        "Fala po deszczu 21–23.09: początek wysypu, szczyt ok. 1–3.10"
        " · starsza fala po deszczu 11–12.09: fala się starzeje")
