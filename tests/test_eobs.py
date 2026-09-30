from datetime import date

import netCDF4
import numpy as np
import pandas as pd

from pipeline import eobs


def _make_nc(path, var, values):
    """Mini-siatka E-OBS: 3 dni, lat 50.05..50.25, lon 18.55..18.75, wartosci w jednostkach fizycznych."""
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("time", 3)
        ds.createDimension("latitude", 3)
        ds.createDimension("longitude", 3)
        t = ds.createVariable("time", "f8", ("time",))
        t.units = "days since 1950-01-01 00:00:00"
        t[:] = [(date(2020, 6, 1) - date(1950, 1, 1)).days + i for i in range(3)]
        la = ds.createVariable("latitude", "f4", ("latitude",))
        la[:] = [50.05, 50.15, 50.25]
        lo = ds.createVariable("longitude", "f4", ("longitude",))
        lo[:] = [18.55, 18.65, 18.75]
        v = ds.createVariable(var, "i2", ("time", "latitude", "longitude"), fill_value=-9999)
        v.scale_factor = 0.01
        v[:] = values


def test_convert_and_read_nearest_cell_with_missing(tmp_path):
    raw = np.ma.masked_all((3, 3, 3), dtype=np.float64)
    raw[:, 1, 1] = [10.0, 12.5, 0.0]  # wartosci fizyczne (netCDF4 pakuje scale_factor)
    raw[2, 1, 1] = np.ma.masked           # brak w trzecim dniu
    _make_nc(tmp_path / "x.nc", "tg", raw)
    out = eobs.convert_to_poland(tmp_path / "x.nc", "tg", eobs.npz_path(tmp_path, "tg", "2011-2025"))
    assert out.exists()
    df = eobs.EobsStore(tmp_path).daily(50.14, 18.66, date(2020, 5, 31), date(2020, 6, 3), variables=["tg"])
    assert list(df.index.date) == [date(2020, 5, 31), date(2020, 6, 1), date(2020, 6, 2), date(2020, 6, 3)]
    assert np.isnan(df["tg"].iloc[0])                      # przed zakresem pliku
    assert df["tg"].iloc[1] == 10.0 and df["tg"].iloc[2] == 12.5
    assert np.isnan(df["tg"].iloc[3])                      # brak wartosci != 0


def test_missing_chunk_gives_nan_not_error(tmp_path):
    df = eobs.EobsStore(tmp_path).daily(50.1, 18.6, date(2020, 6, 1), date(2020, 6, 2))
    assert df.isna().all().all()


def test_hargreaves_is_positive_in_summer_and_zero_without_range():
    idx = pd.date_range("2020-06-15", periods=2)
    et = eobs.hargreaves_et0(pd.Series([10.0, 10.0], index=idx), pd.Series([22.0, 10.0], index=idx), 50.5)
    assert 3.0 < et.iloc[0] < 6.0
    assert et.iloc[1] == 0.0


def test_region_paths_keep_poland_filename_and_separate_other_regions(tmp_path):
    assert eobs.npz_path(tmp_path, "tg", "2011-2025").name == "tg_2011-2025_PL.npz"
    assert eobs.npz_path(tmp_path, "tg", "2011-2025", "BI").name == "tg_2011-2025_BI.npz"
    import pytest
    with pytest.raises(KeyError):
        eobs.npz_path(tmp_path, "tg", "2011-2025", "XX")


def test_fetch_chunk_converts_only_missing_regions_and_keeps_existing(tmp_path, monkeypatch):
    pl = eobs.npz_path(tmp_path, "tg", "2011-2025", "PL")
    pl.parent.mkdir(parents=True)
    pl.write_bytes(b"istniejacy plik PL")
    converted = []

    def fake_download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"nc")
        return dest

    def fake_convert(nc, var, out, region):
        converted.append(region)
        out.write_bytes(b"npz")
        return out

    monkeypatch.setattr(eobs, "download", fake_download)
    monkeypatch.setattr(eobs, "convert_region", fake_convert)
    eobs.fetch_chunk(tmp_path, "tg", "2011-2025", ("PL", "BI"))
    assert converted == ["BI"] and pl.read_bytes() == b"istniejacy plik PL"
    assert not (tmp_path / "eobs" / "raw" / eobs.chunk_filename("tg", "2011-2025")).exists()
    eobs.fetch_chunk(tmp_path, "tg", "2011-2025", ("PL", "BI"))  # wszystko jest -> bez pobierania
    assert converted == ["BI"]


def test_bilinear_weights_four_surrounding_cells(tmp_path, monkeypatch):
    monkeypatch.setitem(eobs.REGIONS, "T", ((50.0, 50.3), (18.5, 18.8)))
    raw = np.ma.zeros((3, 3, 3), dtype=np.float64)
    raw[:, 0, 0], raw[:, 1, 0], raw[:, 0, 1], raw[:, 1, 1] = 10.0, 20.0, 30.0, 40.0  # (lat, lon)
    _make_nc(tmp_path / "x.nc", "tg", raw)
    eobs.convert_region(tmp_path / "x.nc", "tg", eobs.npz_path(tmp_path, "tg", "2011-2025", "T"), "T")
    store = eobs.EobsStore(tmp_path, region="T")
    # 25% drogi w szerokosci (50.05 -> 50.15), 50% w dlugosci (18.55 -> 18.65)
    df = store.daily_bilinear(50.075, 18.60, date(2020, 6, 1), date(2020, 6, 1), variables=["tg"])
    expected = 0.75 * 0.5 * 10 + 0.25 * 0.5 * 20 + 0.75 * 0.5 * 30 + 0.25 * 0.5 * 40
    assert abs(df["tg"].iloc[0] - expected) < 1e-6
    # najblizsza komorka przy srodku komorki = ta sama wartosc
    assert store.daily_bilinear(50.05, 18.55, date(2020, 6, 1), date(2020, 6, 1), ["tg"])["tg"].iloc[0] == 10.0
