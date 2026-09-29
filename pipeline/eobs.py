"""Plan 2.6: E-OBS 0.1 st. (ensemble mean) lokalnie -- klimatologia i kontrole bez limitow API.

Pliki E-OBS (Europa, ok. 1 GB na zmienna i 15 lat) sa pobierane pojedynczo,
przycinane do Polski i zapisywane jako maly, skompresowany `.npz` w
`cache/eobs/` (wartosci int16 w setnych: tg/tn/tx w 0,01 C, rr w 0,01 mm;
brak danych = -32768); surowy plik jest kasowany po konwersji.

Licencja E-OBS: wylacznie niekomercyjne badania i edukacja (ECA&D data policy).
Zrodlo: https://surfobs.climate.copernicus.eu/dataaccess/access_eobs_chunks.php
"""
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble"
VERSION = "v33.0e"
PERIODS = ["1980-1994", "1995-2010", "2011-2025"]
VARIABLES = ["tg", "tn", "tx", "rr"]
LAT_RANGE = (48.8, 55.2)
LON_RANGE = (13.8, 24.4)
MISSING = -32768
SCALE = 100.0  # int16 = wartosc * 100


def chunk_filename(var: str, period: str) -> str:
    return f"{var}_ens_mean_0.1deg_reg_{period}_{VERSION}.nc"


def chunk_url(var: str, period: str) -> str:
    return f"{BASE_URL}/{chunk_filename(var, period)}"


def npz_path(cache_dir: Path, var: str, period: str) -> Path:
    return Path(cache_dir) / "eobs" / f"{var}_{period}_PL.npz"


def convert_to_poland(nc_path: Path, var: str, out_path: Path) -> Path:
    """Przytnij plik E-OBS do Polski i zapisz jako int16 (setne). Odczyt po kawalkach czasu."""
    import netCDF4
    with netCDF4.Dataset(nc_path) as ds:
        lat, lon = ds.variables["latitude"][:], ds.variables["longitude"][:]
        i0, i1 = np.searchsorted(lat, LAT_RANGE[0]), np.searchsorted(lat, LAT_RANGE[1])
        j0, j1 = np.searchsorted(lon, LON_RANGE[0]), np.searchsorted(lon, LON_RANGE[1])
        tvar = ds.variables["time"]
        times = netCDF4.num2date(tvar[:], tvar.units, only_use_cftime_datetimes=False,
                                 only_use_python_datetimes=True)
        days = np.array([np.datetime64(t.date()) for t in times], dtype="datetime64[D]")
        data = ds.variables[var]
        data.set_auto_maskandscale(True)
        out = np.full((len(days), i1 - i0, j1 - j0), MISSING, dtype=np.int16)
        for s in range(0, len(days), 366):
            block = data[s:s + 366, i0:i1, j0:j1]
            filled = np.ma.filled(block.astype("float32"), np.nan)
            valid = np.clip(np.round(np.nan_to_num(filled, nan=0.0) * SCALE), MISSING + 1, 32767)
            out[s:s + 366] = np.where(np.isnan(filled), MISSING, valid).astype(np.int16)
        lat_sel, lon_sel = np.asarray(lat[i0:i1], dtype="float32"), np.asarray(lon[j0:j1], dtype="float32")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp = out_path.with_name(out_path.stem + ".tmp.npz")
    np.savez_compressed(temp, values=out, days=days, lat=lat_sel, lon=lon_sel)
    temp.replace(out_path)
    return out_path


def download(url: str, dest: Path, chunk: int = 1 << 20) -> Path:
    """Strumieniowe pobranie z wznawianiem (Range) -- pliki maja ok. 1 GB."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = dest.stat().st_size if dest.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with requests.get(url, stream=True, headers=headers, timeout=60) as r:
        if r.status_code == 416:  # juz pobrane w calosci
            return dest
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        with dest.open(mode) as fh:
            for block in r.iter_content(chunk):
                fh.write(block)
    return dest


def fetch_chunk(cache_dir: Path, var: str, period: str) -> Path:
    """Pobierz, przytnij do Polski, skasuj surowy plik. Idempotentne."""
    out = npz_path(cache_dir, var, period)
    if out.exists():
        return out
    raw = Path(cache_dir) / "eobs" / "raw" / chunk_filename(var, period)
    download(chunk_url(var, period), raw)
    convert_to_poland(raw, var, out)
    raw.unlink()
    return out


class EobsStore:
    """Dostep do lokalnych danych E-OBS: dobowa tabela dla najblizszej komorki siatki."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self._chunks: dict[tuple[str, str], dict] = {}

    def _load(self, var: str, period: str) -> dict | None:
        key = (var, period)
        if key not in self._chunks:
            path = npz_path(self.cache_dir, var, period)
            if not path.exists():
                self._chunks[key] = None
            else:
                z = np.load(path)
                self._chunks[key] = {k: z[k] for k in ("values", "days", "lat", "lon")}
        return self._chunks[key]

    def cell(self, lat: float, lon: float) -> tuple[float, float]:
        """Wspolrzedne srodka najblizszej komorki siatki 0,1 st."""
        return round(lat * 10 - 0.5) / 10 + 0.05, round(lon * 10 - 0.5) / 10 + 0.05

    def daily(self, lat: float, lon: float, start: date, end: date, variables=VARIABLES) -> pd.DataFrame:
        """Dobowa tabela (index = data) dla najblizszej komorki; brak = NaN. Kolumny: tg,tn,tx (C), rr (mm)."""
        index = pd.date_range(start, end, freq="D")
        frame = pd.DataFrame(np.nan, index=index, columns=list(variables))
        for var in variables:
            for period in PERIODS:
                chunk = self._load(var, period)
                if chunk is None:
                    continue
                i = int(np.argmin(np.abs(chunk["lat"] - lat)))
                j = int(np.argmin(np.abs(chunk["lon"] - lon)))
                series = pd.Series(chunk["values"][:, i, j].astype("float32"),
                                   index=pd.to_datetime(chunk["days"]))
                series = series.where(series != MISSING) / SCALE
                overlap = frame.index.intersection(series.index)
                frame.loc[overlap, var] = series.loc[overlap].to_numpy()
        return frame


def hargreaves_et0(tmin: pd.Series, tmax: pd.Series, lat: float) -> pd.Series:
    """ET0 wg Hargreaves-Samani z TN/TX (mm/dobe) -- jedna metoda dla klimatologii i biezacych dni.
    Ra (promieniowanie pozaziemskie) wg FAO-56 z szerokosci geograficznej i dnia roku."""
    doy = pd.DatetimeIndex(tmin.index).dayofyear.to_numpy()
    phi = math.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * math.pi * doy / 365)
    delta = 0.409 * np.sin(2 * math.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-math.tan(phi) * np.tan(delta), -1, 1))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (ws * math.sin(phi) * np.sin(delta)
                                              + math.cos(phi) * np.cos(delta) * np.sin(ws))
    ra_mm = 0.408 * ra
    trange = (tmax - tmin).clip(lower=0)
    tmean = (tmax + tmin) / 2
    return pd.Series(0.0023 * (tmean + 17.8) * np.sqrt(trange) * ra_mm, index=tmin.index)
