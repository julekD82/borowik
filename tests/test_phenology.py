import pytest

from pipeline.habitat import load_profile
from pipeline.phenology import compute_g_season

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_compute_g_season_peaks_at_september_gbif_maximum():
    # September 15 is the GBIF monthly maximum (471 records) -- see the
    # profile's own gbif_monthly_counts comment for the source query.
    sept_15_doy = 258
    assert compute_g_season(sept_15_doy, PROFILE) == pytest.approx(1.0)


def test_compute_g_season_interpolates_linearly_between_month_midpoints():
    # Sept 15 (doy 258, weight 1.0) -> Oct 15 (doy 288, weight 350/471);
    # Sept 25 is exactly 1/3 of the way there.
    sept_25_doy = 268
    expected = 1.0 + (10.0 / 30.0) * (350.0 / 471.0 - 1.0)
    assert compute_g_season(sept_25_doy, PROFILE) == pytest.approx(expected, abs=1e-6)


def test_compute_g_season_floors_in_deep_winter():
    # January/February/March/April all have 0-1 GBIF records -- the raw
    # normalized weight is ~0, but the floor keeps F from being zeroed
    # outright by a single hard-coded multiplier.
    feb_15_doy = 46
    assert compute_g_season(feb_15_doy, PROFILE) == pytest.approx(
        PROFILE["phenology"]["g_season_floor"]
    )


def test_compute_g_season_interpolates_across_year_boundary():
    # Dec 15 (doy 349, weight 2/471) -> Jan 15 (doy 15 of the NEXT year,
    # weight 1/471) must interpolate smoothly across Dec 31 -> Jan 1
    # instead of jumping or raising.
    dec_20_doy = 354  # 5 days into the 31-day Dec15->Jan15 wrap
    w_dec, w_jan = 2.0 / 471.0, 1.0 / 471.0
    expected = max(
        PROFILE["phenology"]["g_season_floor"],
        w_dec + (5.0 / 31.0) * (w_jan - w_dec),
    )
    assert compute_g_season(dec_20_doy, PROFILE) == pytest.approx(expected, abs=1e-6)


def test_compute_g_season_never_exceeds_one():
    for doy in range(1, 366):
        assert 0.0 < compute_g_season(doy, PROFILE) <= 1.0
