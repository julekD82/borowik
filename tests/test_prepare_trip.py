import geopandas as gpd
import pytest

from pipeline.prepare_trip import parse_args, main, MIN_RADIUS_KM, MAX_RADIUS_KM


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
