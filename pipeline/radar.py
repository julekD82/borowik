"""IMGW-PIB RainGRS: hourly precipitation from weather radar merged with
rain gauges, 1 km grid over Poland, ESRI ASCII. Plan 2026-09-26 A1
(docs/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md).

Why this exists: a 2026-09-26 comparison against 4 independent Weathercloud
stations near Bedziemysl (docs/CODEX-HANDOFF.md note (23)) gave RainGRS a
1.5-4x lower daily MAE than Open-Meteo; Open-Meteo missed convective days
(29.08, 31.08, 03.09) and invented rain on others (03.09, 05.09, 15.09).

Source: https://danepubliczne.imgw.pl (open data, attribution required:
"Zrodlem pochodzenia danych jest IMGW-PIB"). Operational hourly files cover
only the last ~30 h; the daily archive tar lags ~2-3 days. A missing file is
served as HTTP 200 + HTML, not 404 -- every parser here must reject HTML."""
import io
import math
import re
import tarfile
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pyproj import Transformer

GRS_BASE_URL = "https://danepubliczne.imgw.pl/pl/datastore/getfiledown"
GRS_ARCHIVE_PATH = "Arch/Nowcasting/rain_grs/grs_60_asc"
GRS_OPER_PATH = "Oper/Nowcasting/rain_grs/grs_60_asc"
# Assumed EPSG:2180 (header xll=50000, yll=30000, 900x800 km fits PUWG 1992
# exactly); empirically consistent with station agreement on convective
# days -- see plan Task 0 step 3 / Task 7.
GRS_CRS = "EPSG:2180"
# File "YYYYMMDDHH00" = accumulation for the hour ENDING at that UTC time
# (plan Task 7 checks this against station daily sums).
GRS_TIMESTAMP_IS_HOUR_END = True
OPER_LOOKBACK_HOURS = 48
WARSAW = ZoneInfo("Europe/Warsaw")

_TO_GRID = Transformer.from_crs("EPSG:4326", GRS_CRS, always_xy=True)
_STAMP_RE = re.compile(r"(\d{12})_acc0060_grs\.asc$")


@dataclass(frozen=True)
class GridHeader:
    ncols: int
    nrows: int
    xllcorner: float
    yllcorner: float
    cellsize: float

    def as_array(self) -> np.ndarray:
        return np.array([self.ncols, self.nrows, self.xllcorner, self.yllcorner, self.cellsize],
                        dtype=np.float64)

    @classmethod
    def from_array(cls, a) -> "GridHeader":
        return cls(int(a[0]), int(a[1]), float(a[2]), float(a[3]), float(a[4]))


def parse_grs_asc(raw: bytes) -> tuple[GridHeader, np.ndarray]:
    """ESRI ASCII grid -> (header, float32 grid, row 0 = north). Negative
    values (NODATA -999) become NaN -- precipitation is never negative."""
    parts = raw.split(b"\n", 6)
    if len(parts) < 7 or not parts[0].strip().lower().startswith(b"ncols"):
        raise ValueError("not an ESRI ASCII grid (IMGW returned an HTML page?)")
    hdr = {}
    for line in parts[:6]:
        key, value = line.split()[:2]
        hdr[key.decode("ascii").lower()] = float(value)
    header = GridHeader(int(hdr["ncols"]), int(hdr["nrows"]), hdr["xllcorner"], hdr["yllcorner"],
                        hdr["cellsize"])
    values = np.array(parts[6].split(), dtype=np.float32)
    if values.size != header.ncols * header.nrows:
        raise ValueError(f"grid size mismatch: {values.size} != {header.ncols}x{header.nrows}")
    grid = values.reshape(header.nrows, header.ncols)
    grid[grid < 0] = np.nan
    return header, grid


def parse_hour_stamp(name: str) -> datetime:
    """File name -> tz-aware UTC END of the accumulated hour."""
    m = _STAMP_RE.search(name)
    if m is None:
        raise ValueError(f"not a RainGRS hourly file name: {name!r}")
    stamp = datetime.strptime(m.group(1), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    return stamp if GRS_TIMESTAMP_IS_HOUR_END else stamp + timedelta(hours=1)


def to_grid_xy(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [_TO_GRID.transform(lon, lat) for lat, lon in points]


def block_slices(header: GridHeader, xy_points, half_size_m: float) -> list[tuple[slice, slice] | None]:
    """(row, col) slices of the cells inside a square of side 2*half_size_m
    centred on each point (half_size_m <= 0: the single containing cell).
    Rows are counted from the top (north) as in the file. None = the block
    lies entirely outside the grid."""
    out = []
    cs = header.cellsize
    for x, y in xy_points:
        fx = (x - header.xllcorner) / cs
        fy = (y - header.yllcorner) / cs
        if half_size_m <= 0:
            c0 = c1 = math.floor(fx)
            k0 = k1 = math.floor(fy)  # k = row index counted from the bottom
        else:
            h = half_size_m / cs
            c0, c1 = math.floor(fx - h), math.ceil(fx + h) - 1
            k0, k1 = math.floor(fy - h), math.ceil(fy + h) - 1
        c0, c1 = max(c0, 0), min(c1, header.ncols - 1)
        k0, k1 = max(k0, 0), min(k1, header.nrows - 1)
        if c0 > c1 or k0 > k1:
            out.append(None)
            continue
        r0, r1 = header.nrows - 1 - k1, header.nrows - 1 - k0
        out.append((slice(r0, r1 + 1), slice(c0, c1 + 1)))
    return out


def sample_stack(stack: np.ndarray, slices) -> np.ndarray:
    """(hours, nrows, ncols) grids -> (hours, points) block means, NaN-aware.
    An all-NaN block (or a None slice) gives NaN = "no radar data here"."""
    out = np.full((stack.shape[0], len(slices)), np.nan, dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # nanmean of all-NaN
        for j, sl in enumerate(slices):
            if sl is None:
                continue
            block = stack[:, sl[0], sl[1]].reshape(stack.shape[0], -1)
            out[:, j] = np.nanmean(block, axis=1)
    return out
