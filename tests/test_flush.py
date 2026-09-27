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
