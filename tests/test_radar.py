import math
from datetime import datetime, timezone

import numpy as np
import pytest

from pipeline.radar import (
    GridHeader, parse_grs_asc, parse_hour_stamp, block_slices, sample_stack,
)


def _asc(values, xll=0.0, yll=0.0, cs=1000.0, nodata=-999.0) -> bytes:
    rows, cols = len(values), len(values[0])
    head = (f"ncols {cols}\nnrows {rows}\nxllcorner {xll}\nyllcorner {yll}\n"
            f"cellsize {cs}\nNODATA_value {nodata}\n")
    body = "\n".join(" ".join(f"{v:.2f}" for v in r) for r in values)
    return (head + body + "\n").encode("ascii")


GRID_3x4 = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]  # row 0 = northernmost


def test_parse_grs_asc_reads_header_and_values_top_row_first():
    header, grid = parse_grs_asc(_asc(GRID_3x4, xll=50000, yll=30000))
    assert header == GridHeader(ncols=4, nrows=3, xllcorner=50000.0, yllcorner=30000.0, cellsize=1000.0)
    assert grid.shape == (3, 4)
    assert grid[0, 0] == 1.0 and grid[2, 3] == 12.0


def test_parse_grs_asc_turns_nodata_into_nan():
    _, grid = parse_grs_asc(_asc([[1, -999], [0, 2]]))
    assert math.isnan(grid[0, 1])
    assert grid[1, 0] == 0.0


def test_parse_grs_asc_rejects_html_error_page():
    # IMGW answers a missing file with HTTP 200 + an HTML page, not a 404.
    with pytest.raises(ValueError):
        parse_grs_asc(b"<!DOCTYPE html><html><body>Brak pliku</body></html>")


def test_parse_grs_asc_rejects_truncated_grid():
    raw = _asc(GRID_3x4)[:-10]
    with pytest.raises(ValueError):
        parse_grs_asc(raw)


def test_parse_hour_stamp_is_utc_hour_end():
    stamp = parse_hour_stamp("Arch/x/202609211300_acc0060_grs.asc")
    assert stamp == datetime(2026, 9, 21, 13, 0, tzinfo=timezone.utc)


def test_parse_hour_stamp_rejects_other_names():
    with pytest.raises(ValueError):
        parse_hour_stamp("202609211300_acc0060_grs.png")


HEADER_3x4 = GridHeader(ncols=4, nrows=3, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)


def test_block_slices_zero_half_size_selects_the_containing_cell():
    (sl,) = block_slices(HEADER_3x4, [(1500.0, 500.0)], half_size_m=0)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[10.0]]  # bottom row (southmost), second column


def test_block_slices_square_block_covers_expected_cells():
    (sl,) = block_slices(HEADER_3x4, [(2000.0, 1500.0)], half_size_m=1000)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[2.0, 3.0], [6.0, 7.0], [10.0, 11.0]]


def test_block_slices_point_outside_grid_is_none():
    assert block_slices(HEADER_3x4, [(10000.0, 10000.0), (-500.0, 500.0)], half_size_m=0) == [None, None]


def test_sample_stack_means_blocks_ignoring_nan_and_all_nan_gives_nan():
    stack = np.array([
        [[1.0, 3.0], [np.nan, 5.0]],
        [[np.nan, np.nan], [np.nan, np.nan]],
    ])
    header = GridHeader(ncols=2, nrows=2, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)
    slices = block_slices(header, [(1000.0, 1000.0)], half_size_m=1000) + [None]
    out = sample_stack(stack, slices)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(3.0)  # mean(1, 3, 5)
    assert math.isnan(out[1, 0])
    assert math.isnan(out[0, 1])  # point outside grid


import io
import tarfile
from datetime import date, timedelta

import pandas as pd
from pyproj import Transformer

from pipeline.radar import (
    RadarUnavailableError, archive_url, oper_url, quantize, dequantize, radar_hourly_at_points,
)

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
POINT = (50.0555, 21.7889)  # Bedziemysl
_X, _Y = _TO_2180.transform(POINT[1], POINT[0])
# 3x3 km synthetic grid whose centre cell contains POINT
XLL, YLL = math.floor(_X / 1000) * 1000 - 1000, math.floor(_Y / 1000) * 1000 - 1000


def _grid_bytes(centre_mm: float) -> bytes:
    v = [[0.0] * 3 for _ in range(3)]
    v[1][1] = centre_mm
    return _asc(v, xll=XLL, yll=YLL)


def _tar(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


HTML = b"<!DOCTYPE html><html><body>Brak</body></html>"


class FakeHttp:
    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses.get(url, HTML)


def test_quantize_roundtrip_keeps_centimillimetres_and_nan():
    g = np.array([[0.0, 1.234, np.nan, 700.0]], dtype=np.float32)
    back = dequantize(quantize(g))
    assert back[0, 1] == pytest.approx(1.23)
    assert math.isnan(back[0, 2])
    assert back[0, 3] == pytest.approx(655.34)  # clipped just below the NaN sentinel


def test_archive_and_oper_urls():
    assert archive_url(date(2026, 9, 21)).endswith(
        "/Arch/Nowcasting/rain_grs/grs_60_asc/2026/09/grs_60_asc_2026-09-21.tar")
    assert oper_url(datetime(2026, 9, 25, 13, tzinfo=timezone.utc)).endswith(
        "/Oper/Nowcasting/rain_grs/grs_60_asc/202609251300_acc0060_grs.asc")


def test_archive_day_is_sampled_cached_and_not_refetched(tmp_path):
    day = date(2026, 9, 21)
    http = FakeHttp({archive_url(day): _tar({
        "grs_60_asc_2026-09-21/202609210100_acc0060_grs.asc": _grid_bytes(2.5),
        "grs_60_asc_2026-09-21/202609210200_acc0060_grs.asc": _grid_bytes(1.0),
    })})
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    start = datetime(2026, 9, 21, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, 0, tzinfo=timezone.utc)

    df = radar_hourly_at_points([POINT], 0, start, end, tmp_path, http_get=http, now_utc=now)

    assert df["precip_mm"].tolist() == pytest.approx([2.5, 1.0])
    assert df["hour_end_utc"].tolist() == [
        pd.Timestamp("2026-09-21 01:00", tz="UTC"), pd.Timestamp("2026-09-21 02:00", tz="UTC")]
    assert (tmp_path / "2026-09-21.npz").exists()

    http.calls.clear()
    again = radar_hourly_at_points([POINT], 0, start, end, tmp_path, http_get=http, now_utc=now)
    assert again["precip_mm"].tolist() == pytest.approx([2.5, 1.0])
    assert not any("2026-09-21" in c for c in http.calls)  # complete archive day served from cache


def test_html_instead_of_tar_falls_back_to_oper_hours(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    http = FakeHttp({
        oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)): _grid_bytes(4.0),
        oper_url(datetime(2026, 9, 26, 2, tzinfo=timezone.utc)): _grid_bytes(0.5),
    })
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 26, 0, tzinfo=timezone.utc), now, tmp_path,
        http_get=http, now_utc=now)
    assert df["precip_mm"].tolist() == pytest.approx([4.0, 0.5])
    # hours after `now` are never requested
    assert oper_url(datetime(2026, 9, 26, 5, tzinfo=timezone.utc)) not in http.calls


def test_html_instead_of_asc_is_skipped(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    http = FakeHttp({oper_url(datetime(2026, 9, 26, 2, tzinfo=timezone.utc)): _grid_bytes(0.5)})
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 26, 0, tzinfo=timezone.utc), now, tmp_path,
        http_get=http, now_utc=now)
    assert df["hour_end_utc"].tolist() == [pd.Timestamp("2026-09-26 02:00", tz="UTC")]


def test_old_day_without_archive_does_not_request_oper_hours(tmp_path):
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    http = FakeHttp({})
    df = radar_hourly_at_points(
        [POINT], 0, datetime(2026, 9, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 11, 0, tzinfo=timezone.utc), tmp_path, http_get=http, now_utc=now)
    assert df.empty
    assert all("/Oper/" not in c for c in http.calls)  # oper keeps only ~30 h


def test_partial_oper_day_rechecks_archive_on_next_run(tmp_path):
    now = datetime(2026, 9, 26, 3, 30, tzinfo=timezone.utc)
    start = datetime(2026, 9, 26, 0, tzinfo=timezone.utc)
    http = FakeHttp({oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)): _grid_bytes(4.0)})
    radar_hourly_at_points([POINT], 0, start, now, tmp_path, http_get=http, now_utc=now)
    http.calls.clear()
    radar_hourly_at_points([POINT], 0, start, now, tmp_path, http_get=http, now_utc=now)
    assert archive_url(date(2026, 9, 26)) in http.calls
    assert oper_url(datetime(2026, 9, 26, 1, tzinfo=timezone.utc)) not in http.calls  # cached hour


def test_unreachable_server_raises_radar_unavailable(tmp_path):
    def down(url):
        raise RadarUnavailableError("dns")
    with pytest.raises(RadarUnavailableError):
        radar_hourly_at_points([POINT], 0, datetime(2026, 9, 21, tzinfo=timezone.utc),
                               datetime(2026, 9, 22, tzinfo=timezone.utc), tmp_path,
                               http_get=down, now_utc=datetime(2026, 9, 26, tzinfo=timezone.utc))


def test_default_http_get_retries_and_gives_up_on_any_request_exception(monkeypatch):
    import requests

    from pipeline.radar import _default_http_get

    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def broken_get(url, timeout):
        calls.append(url)
        # A mid-download connection drop raises ChunkedEncodingError, not
        # ConnectionError/Timeout -- both are requests.exceptions.RequestException,
        # but only the first two were retried before this fix (D9: "a run
        # never fails because of IMGW" requires treating the whole
        # RequestException family the same way).
        raise requests.exceptions.ChunkedEncodingError("connection broken")

    monkeypatch.setattr(requests, "get", broken_get)
    with pytest.raises(RadarUnavailableError):
        _default_http_get("https://danepubliczne.imgw.pl/x")
    assert len(calls) == 3  # retried, not raised raw on the first attempt


from pipeline.radar import expected_local_hours, radar_daily_at_points, merge_radar_into_daily


def _hourly(rows):
    return pd.DataFrame(rows, columns=["lat", "lon", "hour_end_utc", "precip_mm"])


def test_expected_local_hours_on_dst_days():
    assert expected_local_hours(date(2026, 9, 21)) == 24
    assert expected_local_hours(date(2026, 10, 25)) == 25  # CEST -> CET
    assert expected_local_hours(date(2026, 3, 29)) == 23   # CET -> CEST


def test_radar_daily_assigns_each_hour_to_local_day_of_its_start():
    h = _hourly([
        (50.0, 21.0, pd.Timestamp("2026-09-20 22:00", tz="UTC"), 1.0),  # 23:00-00:00 local 20.09
        (50.0, 21.0, pd.Timestamp("2026-09-20 23:00", tz="UTC"), 2.0),  # 00:00-01:00 local 21.09
        (50.0, 21.0, pd.Timestamp("2026-09-21 00:00", tz="UTC"), float("nan")),  # no data: not counted
    ])
    d = radar_daily_at_points(h).set_index("local_date")
    assert d.loc[date(2026, 9, 20), "radar_mm"] == 1.0
    assert d.loc[date(2026, 9, 21), "radar_mm"] == 2.0
    assert d.loc[date(2026, 9, 21), "radar_hours"] == 1
    assert d.loc[date(2026, 9, 21), "expected_hours"] == 24


def _om_daily(values_by_local_day: dict):
    # Same shape as pipeline.weather._parse_open_meteo_response: `date` is the
    # UTC instant of LOCAL midnight (22:00 UTC the previous day in summer time).
    rows = []
    for d, mm in values_by_local_day.items():
        rows.append({"lat": 50.0, "lon": 21.0,
                     "date": pd.Timestamp(d.isoformat(), tz="Europe/Warsaw").tz_convert("UTC"),
                     "precipitation_mm": mm, "tmean_c": 12.0, "tmin_c": 6.0, "tmax_c": 18.0,
                     "et0_mm": 1.0, "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def _radar_day(d, mm, hours, expected=24):
    return pd.DataFrame([{"lat": 50.0, "lon": 21.0, "local_date": d, "radar_mm": mm,
                          "radar_hours": hours, "expected_hours": expected}])


def test_merge_uses_local_date_of_utc_midnight_timestamps():
    daily = _om_daily({date(2026, 9, 21): 17.0, date(2026, 9, 22): 13.0})
    out = merge_radar_into_daily(daily, _radar_day(date(2026, 9, 22), 12.5, 24),
                                 date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].tolist() == pytest.approx([17.0, 12.5])
    assert out["radar_frac"].tolist() == [0.0, 1.0]
    assert out["precipitation_mm_model"].tolist() == pytest.approx([17.0, 13.0])


def test_merge_partial_coverage_fills_missing_share_from_model():
    daily = _om_daily({date(2026, 9, 11): 20.0})
    out = merge_radar_into_daily(daily, _radar_day(date(2026, 9, 11), 15.0, 18),
                                 date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].iloc[0] == pytest.approx(15.0 + 20.0 * 6 / 24)
    assert out["radar_frac"].iloc[0] == pytest.approx(0.75)


def test_merge_no_radar_keeps_model_value():
    daily = _om_daily({date(2026, 9, 24): 0.1})
    empty = radar_daily_at_points(_hourly([]))
    out = merge_radar_into_daily(daily, empty, date(2026, 9, 1), date(2026, 9, 26))
    assert out["precipitation_mm"].iloc[0] == pytest.approx(0.1)
    assert out["radar_frac"].iloc[0] == 0.0


def test_merge_leaves_days_outside_window_untouched():
    daily = _om_daily({date(2026, 8, 1): 5.0, date(2026, 9, 27): 3.0})  # too old / forecast
    radar = pd.concat([_radar_day(date(2026, 8, 1), 0.0, 24), _radar_day(date(2026, 9, 27), 0.0, 24)])
    out = merge_radar_into_daily(daily, radar, date(2026, 8, 28), date(2026, 9, 26))
    assert out["precipitation_mm"].tolist() == pytest.approx([5.0, 3.0])
    assert out["radar_frac"].tolist() == [0.0, 0.0]


from pipeline.radar import make_radar_weather_fetcher, radar_window


def test_radar_window_ends_now_and_spans_window_days_of_local_days():
    now = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    ws, we, s_utc, e_utc = radar_window(date(2026, 9, 26), 30, now)
    assert (ws, we) == (date(2026, 8, 28), date(2026, 9, 26))
    assert s_utc == datetime(2026, 8, 27, 22, tzinfo=timezone.utc)  # local midnight 28.08
    assert e_utc == now


def _base_fetcher(points, past_days, forecast_days=1):
    return _om_daily({date(2026, 9, 21): 17.0, date(2026, 9, 22): 13.0})


def test_radar_weather_fetcher_replaces_precipitation_in_window():
    def fake_hourly(points, half_size_m, start_utc, end_utc, cache_dir, http_get=None, now_utc=None):
        assert half_size_m == 2000.0
        return _hourly([(50.0, 21.0, pd.Timestamp("2026-09-21 12:00", tz="UTC"), 20.0)])

    fetcher = make_radar_weather_fetcher(
        _base_fetcher, half_size_m=2000.0, window_days=30, cache_dir="unused",
        now_utc=datetime(2026, 9, 26, 10, tzinfo=timezone.utc), today=date(2026, 9, 26),
        radar_hourly_fn=fake_hourly)
    out = fetcher([(50.0, 21.0)], 92, forecast_days=1)
    assert out["precipitation_mm"].tolist() == pytest.approx([20.0 + 17.0 * 23 / 24, 13.0])
    assert out["radar_frac"].tolist() == pytest.approx([1 / 24, 0.0])


def test_radar_unavailable_falls_back_to_model_with_warning(capsys):
    def down(*args, **kwargs):
        raise RadarUnavailableError("dns")

    fetcher = make_radar_weather_fetcher(
        _base_fetcher, half_size_m=2000.0, window_days=30, cache_dir="unused",
        now_utc=datetime(2026, 9, 26, 10, tzinfo=timezone.utc), today=date(2026, 9, 26),
        radar_hourly_fn=down)
    out = fetcher([(50.0, 21.0)], 92)
    assert out["precipitation_mm"].tolist() == pytest.approx([17.0, 13.0])
    assert (out["radar_frac"] == 0.0).all()
    assert "UWAGA: radar IMGW niedostepny" in capsys.readouterr().out


def test_radar_unexpected_error_still_falls_back_to_model_with_warning(capsys):
    # D9 ("a run never fails because of IMGW") must hold for any failure
    # inside radar_hourly_fn, not only the anticipated RadarUnavailableError
    # -- a corrupt cached .npz, a malformed grid header, or a truncated
    # archive tar surface as EOFError/ValueError/KeyError, not
    # RadarUnavailableError.
    def broken(*args, **kwargs):
        raise EOFError("corrupt cache/radar_grs/2026-09-21.npz")

    fetcher = make_radar_weather_fetcher(
        _base_fetcher, half_size_m=2000.0, window_days=30, cache_dir="unused",
        now_utc=datetime(2026, 9, 26, 10, tzinfo=timezone.utc), today=date(2026, 9, 26),
        radar_hourly_fn=broken)
    out = fetcher([(50.0, 21.0)], 92)
    assert out["precipitation_mm"].tolist() == pytest.approx([17.0, 13.0])
    assert (out["radar_frac"] == 0.0).all()
    assert "UWAGA: radar IMGW niedostepny" in capsys.readouterr().out


def test_merge_derives_local_date_correctly_across_a_fixed_step_dst_series():
    # pipeline.weather._parse_open_meteo_response builds `date` with a FIXED
    # 24h UTC step from the first local midnight (pd.date_range(..., freq=
    # 86400s)) -- unlike _om_daily's helper above, which tz_converts each day
    # independently and can't reproduce the 1h drift a DST transition
    # (2026-10-25, CEST->CET) introduces into that fixed step. Naively
    # tz_converting this fixed-step series and taking .dt.date collapses two
    # different UTC instants onto the same local date and permanently shifts
    # every later day back by one -- exactly what Review Focus #1 warns about.
    start = pd.Timestamp("2026-10-23 22:00", tz="UTC")  # true local midnight 24.10 (CEST, UTC+2)
    dates = pd.date_range(start, periods=6, freq=pd.Timedelta(seconds=86400))
    daily = pd.DataFrame({"lat": 50.0, "lon": 21.0, "date": dates, "precipitation_mm": 0.0})
    radar = pd.concat([
        _radar_day(date(2026, 10, 24), 10.0, 24, expected=24),
        _radar_day(date(2026, 10, 25), 20.0, 25, expected=25),
        _radar_day(date(2026, 10, 26), 30.0, 24, expected=24),
        _radar_day(date(2026, 10, 27), 40.0, 24, expected=24),
        _radar_day(date(2026, 10, 28), 50.0, 24, expected=24),
    ], ignore_index=True)
    out = merge_radar_into_daily(daily, radar, date(2026, 10, 1), date(2026, 11, 1))
    assert out["precipitation_mm"].tolist() == pytest.approx([10.0, 20.0, 30.0, 40.0, 50.0, 0.0])
