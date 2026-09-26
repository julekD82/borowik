from datetime import date, timedelta

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import box

from pipeline.prepare_trip import (
    parse_args, main, MIN_RADIUS_KM, MAX_RADIUS_KM,
    _rate_limited, _is_open_meteo_rate_limit, _is_overpass_retryable, _is_transient_network_error,
    _radius_scaled_spacing, REFERENCE_RADIUS_KM,
)
from pipeline.bdl_dictionaries import load_dictionaries
from pipeline.bdl_package_details import load_package_details
from pipeline.neighbors import find_neighbor_labels
from pipeline.export import write_details_json
from pipeline.tie_break import load_tie_break_raw, tie_break_for_stand


def _http_error(status_code):
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


def test_rate_limited_retries_once_on_a_retryable_error_then_succeeds(monkeypatch):
    import pipeline.prepare_trip as trip
    monkeypatch.setattr(trip.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(429)
        return "ok"

    result = _rate_limited(flaky, should_retry=lambda exc: True)
    assert result == "ok"
    assert len(calls) == 2


def test_rate_limited_reraises_immediately_when_predicate_declines(monkeypatch):
    import pipeline.prepare_trip as trip
    monkeypatch.setattr(trip.time, "sleep", lambda s: None)

    def always_fails():
        raise _http_error(500)

    with pytest.raises(requests.exceptions.HTTPError):
        _rate_limited(always_fails, should_retry=lambda exc: False)


def test_rate_limited_reraises_after_exhausting_max_attempts(monkeypatch):
    import pipeline.prepare_trip as trip
    monkeypatch.setattr(trip.time, "sleep", lambda s: None)
    calls = []

    def always_fails():
        calls.append(1)
        raise _http_error(429)

    with pytest.raises(requests.exceptions.HTTPError):
        _rate_limited(always_fails, should_retry=lambda exc: True, max_attempts=3)
    assert len(calls) == 3


def test_is_overpass_retryable_matches_429_406_and_504():
    # 429/406: overpass-api.de's own usage policy. 504: the Overpass API
    # author's own guidance (olbricht.nrw/command_line.html) -- "sent if
    # the server has already so much load that the request cannot be
    # executed... in most cases, it is best to try again later" -- and
    # observed live 2026-09-24 on tile 1/30 of a real run.
    assert _is_overpass_retryable(_http_error(429)) is True
    assert _is_overpass_retryable(_http_error(406)) is True
    assert _is_overpass_retryable(_http_error(504)) is True
    assert _is_overpass_retryable(_http_error(500)) is False
    assert _is_overpass_retryable(ValueError("unrelated")) is False


def test_radius_scaled_spacing_matches_the_base_value_at_the_reference_radius():
    # REFERENCE_RADIUS_KM is the CLI's own default (--radius-km 25) --
    # WEATHER_GRID_SPACING_M/CLIMATOLOGY_GRID_SPACING_M in orchestrate.py
    # are themselves defined at that radius, so scaling must be a no-op
    # there, matching every point count already verified live at 25km.
    assert _radius_scaled_spacing(5000.0, REFERENCE_RADIUS_KM) == pytest.approx(5000.0)


def test_radius_scaled_spacing_scales_linearly_with_radius():
    # User request 2026-09-24: a smaller search radius should use a finer
    # grid instead of the same fixed spacing "wasting" its point budget
    # over less ground -- total point count (and so API cost) stays
    # roughly constant across the whole 10-50km CLI range instead of
    # growing with the search area.
    assert _radius_scaled_spacing(5000.0, 15.0) == pytest.approx(3000.0)
    assert _radius_scaled_spacing(20000.0, 15.0) == pytest.approx(12000.0)
    assert _radius_scaled_spacing(5000.0, MIN_RADIUS_KM) == pytest.approx(2000.0)
    assert _radius_scaled_spacing(5000.0, MAX_RADIUS_KM) == pytest.approx(10000.0)


def test_is_transient_network_error_matches_connection_errors_not_arbitrary_exceptions():
    # GDOS (sdi.gdos.gov.pl) has no documented rate-limit policy like
    # Overpass or Open-Meteo -- a live run hit requests.exceptions.
    # ConnectionError (a ProtocolError under it) with no HTTP status at
    # all, so this matches broadly on the requests library's own
    # transient-error hierarchy rather than a specific status code.
    assert _is_transient_network_error(requests.exceptions.ConnectionError("reset")) is True
    assert _is_transient_network_error(requests.exceptions.Timeout("slow")) is True
    assert _is_transient_network_error(_http_error(500)) is True
    assert _is_transient_network_error(ValueError("unrelated")) is False


def test_is_open_meteo_rate_limit_matches_documented_message_only():
    from openmeteo_requests.Client import OpenMeteoRequestsError
    assert _is_open_meteo_rate_limit(OpenMeteoRequestsError("Hourly API request limit exceeded")) is True
    assert _is_open_meteo_rate_limit(OpenMeteoRequestsError("Your API call requests too much data")) is False
    assert _is_open_meteo_rate_limit(ValueError("limit")) is False


def test_parse_args_requires_lat_and_lon():
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_defaults():
    args = parse_args(["--lat", "50.5", "--lon", "18.6"])
    assert args.lat == 50.5
    assert args.lon == 18.6
    assert args.date is None
    assert args.radius_km == 25.0
    assert args.profile == "profiles/boletus_edulis.yaml"
    assert args.out_dir == "notebooks/output"
    assert args.cache_dir == "cache"


def test_parse_args_rejects_radius_below_minimum():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", "5"])


def test_parse_args_rejects_radius_above_maximum():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", "60"])


def test_parse_args_accepts_radius_at_boundaries():
    low = parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", str(MIN_RADIUS_KM)])
    high = parse_args(["--lat", "50.5", "--lon", "18.6", "--radius-km", str(MAX_RADIUS_KM)])
    assert low.radius_km == MIN_RADIUS_KM
    assert high.radius_km == MAX_RADIUS_KM


def test_parse_args_rejects_malformed_date():
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--date", "2026/09/24"])


def test_parse_args_accepts_well_formed_date():
    args = parse_args(["--lat", "50.5", "--lon", "18.6", "--date", "2026-10-05"])
    assert args.date == "2026-10-05"


def test_parse_args_rejects_date_in_the_past():
    # Plan 2.1 step A3, user decision 2026-09-24: abort with a clear error
    # rather than silently computing for today -- Open-Meteo's forecast
    # window can't retroactively end on a day that's already gone.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--date", yesterday])


def test_parse_args_accepts_date_of_today():
    today = date.today().isoformat()
    args = parse_args(["--lat", "50.5", "--lon", "18.6", "--date", today])
    assert args.date == today


def test_parse_args_rejects_date_more_than_16_days_ahead():
    # Open-Meteo's forecast API caps forecast_days at 16 (today + 15 days
    # ahead); --date today+16 would need forecast_days=17.
    too_far = (date.today() + timedelta(days=16)).isoformat()
    with pytest.raises(SystemExit):
        parse_args(["--lat", "50.5", "--lon", "18.6", "--date", too_far])


def test_parse_args_accepts_date_at_the_16_day_forecast_boundary():
    boundary = (date.today() + timedelta(days=15)).isoformat()  # forecast_days == 16, the max
    args = parse_args(["--lat", "50.5", "--lon", "18.6", "--date", boundary])
    assert args.date == boundary


def test_main_returns_1_and_prints_clean_error_outside_poland(monkeypatch, tmp_path, capsys):
    # Final review finding (Important #2): TripPreparationError -> print ->
    # return 1 was only proven by a manual run. This exercises the same
    # path with no network, by making the RDLP lookup itself return no
    # match, exactly as it does for a real out-of-Poland point.
    empty_rdlp = gpd.GeoDataFrame({"region_name": []}, geometry=[], crs="EPSG:2180")
    monkeypatch.setattr(
        "pipeline.prepare_trip.fetch_rdlp_boundaries_cached", lambda cache_dir: empty_rdlp
    )

    exit_code = main(["--lat", "0", "--lon", "0", "--cache-dir", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Blad" in captured.out
    assert "Traceback" not in captured.out


def _enriched_for_b3_regression():
    # Mimics the shape of `enriched` at the point run_trip_preparation runs
    # the plan 2.1 step B3 block (after enrich_with_mvp_layers) -- R_final/H
    # already final, plus the WFS columns B3 reads (adr_for, area_type,
    # species_cd, spec_age, stand_stru, prot_categ).
    return gpd.GeoDataFrame({
        "stand_id": ["A@2026", "B@2026"],
        "adr_for": ["A", "B"],
        "area_type": ["D-STAN", "D-STAN"],
        "species_cd": ["SO", "SW"],
        "spec_age": [60, 45],
        "stand_stru": ["DRZEW", None],
        "prot_categ": ["OCH USZK", None],
        "R_final": [48.6, 16.0],
        "H": [0.9, 0.5],
    }, geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs="EPSG:2180")


def test_b3_detail_card_step_does_not_change_r_or_h(tmp_path):
    # Plan 2.1 step B3 requirement (spec 5.3 pkt 3): the detail-card step
    # (dictionaries + package details + neighbours + details.json) must have
    # zero effect on scoring. Runs the exact sequence prepare_trip.py's B3
    # block runs (see pipeline/prepare_trip.py's run_trip_preparation,
    # after group_into_regions) against a synthetic `enriched` and asserts
    # R_final/H are byte-identical before and after.
    enriched = _enriched_for_b3_regression()
    r_before = enriched["R_final"].copy()
    h_before = enriched["H"].copy()

    empty_packages_dir = tmp_path / "bdl_packages"  # no packages cached -- the common case
    dictionaries = load_dictionaries(empty_packages_dir)
    package_details_index = load_package_details(empty_packages_dir)
    neighbors_by_stand = {
        row["adr_for"]: find_neighbor_labels(row, enriched, dictionaries)
        for _, row in enriched.iterrows()
    }
    write_details_json(
        enriched, package_details_index, neighbors_by_stand, dictionaries,
        day="2026-09-25", out_path=tmp_path / "details_2026-09-25.json",
        tie_break_index={},
    )

    pd.testing.assert_series_equal(enriched["R_final"], r_before)
    pd.testing.assert_series_equal(enriched["H"], h_before)


def test_tie_break_step_does_not_change_r_or_h(tmp_path):
    # Plan 2.1 "Zmiana 4": computing tie_break (before group_into_regions)
    # must have zero effect on R_final/H -- pipeline.tie_break is never
    # imported by pipeline.orchestrate/habitat/scoring/mvp (structural
    # guarantee), this is the explicit regression check, same pattern as
    # the B3 detail-card regression test above.
    enriched = _enriched_for_b3_regression()
    r_before = enriched["R_final"].copy()
    h_before = enriched["H"].copy()

    empty_packages_dir = tmp_path / "bdl_packages"  # no packages cached -- the common case
    tie_break_raw_index = load_tie_break_raw(empty_packages_dir)
    enriched["tie_break"] = [
        tie_break_for_stand(row["adr_for"], tie_break_raw_index) for _, row in enriched.iterrows()
    ]

    pd.testing.assert_series_equal(enriched["R_final"], r_before)
    pd.testing.assert_series_equal(enriched["H"], h_before)
    assert enriched["tie_break"].tolist() == [0.5, 0.5]  # neutral -- no package data


def test_parse_args_no_radar_flag():
    import pipeline.prepare_trip as trip
    assert trip.parse_args(["--lat", "50.0", "--lon", "21.0"]).no_radar is False
    assert trip.parse_args(["--lat", "50.0", "--lon", "21.0", "--no-radar"]).no_radar is True


def test_build_weather_fetcher_wraps_with_radar_using_half_grid_spacing(tmp_path):
    import pipeline.prepare_trip as trip
    captured = {}

    def factory(base, **kwargs):
        captured.update(kwargs)
        return "wrapped"

    base = object()
    profile = {"radar": {"enabled": True, "window_days": 30, "min_coverage_for_quality": 0.8}}
    out = trip.build_weather_fetcher(base, use_radar=True, profile=profile, grid_spacing_m=4000.0,
                                     cache_dir=tmp_path, radar_factory=factory)
    assert out == "wrapped"
    assert captured == {"half_size_m": 2000.0, "window_days": 30, "cache_dir": tmp_path / "radar_grs"}


def test_build_weather_fetcher_returns_base_when_radar_disabled(tmp_path):
    import pipeline.prepare_trip as trip
    base = object()
    on = {"radar": {"enabled": True, "window_days": 30, "min_coverage_for_quality": 0.8}}
    off = {"radar": {"enabled": False, "window_days": 30, "min_coverage_for_quality": 0.8}}
    assert trip.build_weather_fetcher(base, use_radar=False, profile=on, grid_spacing_m=4000.0,
                                      cache_dir=tmp_path) is base
    assert trip.build_weather_fetcher(base, use_radar=True, profile=off, grid_spacing_m=4000.0,
                                      cache_dir=tmp_path) is base
