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


_NODATA_Q = 65535


class RadarUnavailableError(RuntimeError):
    """IMGW unreachable after retries (connection/DNS/timeout) -- distinct
    from "file not published", which is a normal None from http_get."""


def quantize(grid: np.ndarray) -> np.ndarray:
    q = np.clip(np.round(np.nan_to_num(grid, nan=0.0) * 100.0), 0, _NODATA_Q - 1)
    q[np.isnan(grid)] = _NODATA_Q
    return q.astype(np.uint16)


def dequantize(q: np.ndarray) -> np.ndarray:
    g = q.astype(np.float32) / 100.0
    g[q == _NODATA_Q] = np.nan
    return g


def archive_url(day: date) -> str:
    return f"{GRS_BASE_URL}/{GRS_ARCHIVE_PATH}/{day:%Y}/{day:%m}/grs_60_asc_{day.isoformat()}.tar"


def oper_url(file_stamp: datetime) -> str:
    return f"{GRS_BASE_URL}/{GRS_OPER_PATH}/{file_stamp:%Y%m%d%H%M}_acc0060_grs.asc"


def _default_http_get(url: str) -> bytes | None:
    import requests

    last_exc = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=300)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            # Intermittent DNS failures for danepubliczne.imgw.pl observed live 2026-09-26.
            last_exc = exc
            time.sleep(5 * (attempt + 1))
            continue
        return response.content if response.status_code == 200 else None
    raise RadarUnavailableError(f"IMGW niedostepny: {last_exc}")


@dataclass
class DayGrids:
    header: GridHeader
    hour_ends: list[datetime]  # tz-aware UTC, sorted
    q: np.ndarray              # (hours, nrows, ncols) uint16 centi-mm
    complete: bool             # True = from the archive tar (final)


def _day_path(cache_dir: Path, day: date) -> Path:
    return cache_dir / f"{day.isoformat()}.npz"


def _save_day(path: Path, data: DayGrids) -> None:
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        tmp, q=data.q, header=data.header.as_array(),
        hour_ends=np.array([int(h.timestamp()) for h in data.hour_ends], dtype=np.int64),
        complete=np.array(data.complete),
    )
    tmp.replace(path)


def _load_day(path: Path) -> DayGrids:
    with np.load(path) as z:
        return DayGrids(
            header=GridHeader.from_array(z["header"]),
            hour_ends=[datetime.fromtimestamp(int(t), tz=timezone.utc) for t in z["hour_ends"]],
            q=z["q"],
            complete=bool(z["complete"]),
        )


def _stack(header: GridHeader, grids: dict[datetime, np.ndarray], complete: bool) -> DayGrids:
    keys = sorted(grids)
    return DayGrids(header, keys, np.stack([grids[k] for k in keys]), complete)


def _parse_archive_tar(raw: bytes) -> DayGrids | None:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(raw))
    except tarfile.ReadError:
        return None  # HTML page instead of a tar: day not archived yet
    grids, header = {}, None
    for member in tf.getmembers():
        if not member.isfile() or not _STAMP_RE.search(member.name):
            continue
        try:
            header, grid = parse_grs_asc(tf.extractfile(member).read())
        except ValueError:
            continue
        grids[parse_hour_stamp(member.name)] = quantize(grid)
    return _stack(header, grids, complete=True) if grids else None


def _load_or_fetch_day(day: date, cache_dir: Path, http_get, now_utc: datetime) -> tuple[DayGrids | None, str]:
    """One UTC file-stamp day: complete cache -> archive tar -> oper hours."""
    path = _day_path(cache_dir, day)
    cached = _load_day(path) if path.exists() else None
    if cached is not None and cached.complete:
        return cached, "cache"
    raw = http_get(archive_url(day))
    if raw is not None:
        parsed = _parse_archive_tar(raw)
        if parsed is not None:
            _save_day(path, parsed)
            return parsed, "archiwum"
    grids = dict(zip(cached.hour_ends, cached.q)) if cached else {}
    header = cached.header if cached else None
    new = 0
    for hour in range(24):
        file_stamp = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
        hour_end = file_stamp if GRS_TIMESTAMP_IS_HOUR_END else file_stamp + timedelta(hours=1)
        if hour_end in grids or hour_end > now_utc or hour_end < now_utc - timedelta(hours=OPER_LOOKBACK_HOURS):
            continue
        raw = http_get(oper_url(file_stamp))
        if raw is None:
            continue
        try:
            header, grid = parse_grs_asc(raw)
        except ValueError:
            continue
        grids[hour_end] = quantize(grid)
        new += 1
    if not grids:
        return None, "brak"
    data = _stack(header, grids, complete=False)
    if new:
        _save_day(path, data)
    return data, "biezace"


def radar_hourly_at_points(points: list[tuple[float, float]], half_size_m: float,
                           start_utc: datetime, end_utc: datetime, cache_dir,
                           http_get=None, now_utc: datetime | None = None) -> pd.DataFrame:
    """Hourly RainGRS block means at `points` for hours ending in
    (start_utc, end_utc]. One UTC day of grids in memory at a time."""
    http_get = http_get or _default_http_get
    now_utc = now_utc or datetime.now(timezone.utc)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    xy = to_grid_xy(points)
    lats = np.array([p[0] for p in points])
    lons = np.array([p[1] for p in points])
    frames, sources = [], {}
    day = start_utc.date()
    while day <= end_utc.date():
        if datetime(day.year, day.month, day.day, tzinfo=timezone.utc) > now_utc:
            break
        data, source = _load_or_fetch_day(day, cache_dir, http_get, now_utc)
        sources[source] = sources.get(source, 0) + 1
        day += timedelta(days=1)
        if data is None:
            continue
        keep = [i for i, h in enumerate(data.hour_ends) if start_utc < h <= end_utc]
        if not keep:
            continue
        values = sample_stack(dequantize(data.q[keep]), block_slices(data.header, xy, half_size_m))
        hours = pd.DatetimeIndex([data.hour_ends[i] for i in keep])
        frames.append(pd.DataFrame({
            "lat": np.tile(lats, len(keep)),
            "lon": np.tile(lons, len(keep)),
            "hour_end_utc": hours.repeat(len(points)),
            "precip_mm": values.reshape(-1),
        }))
    print("Radar IMGW (RainGRS): " + ", ".join(f"{k} {v}" for k, v in sorted(sources.items())) + " dob",
          flush=True)
    if not frames:
        return pd.DataFrame({"lat": [], "lon": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"),
                             "precip_mm": []})
    return pd.concat(frames, ignore_index=True)


def expected_local_hours(day: date) -> int:
    """23/24/25 -- number of real hours in the Europe/Warsaw calendar day.
    Aware datetimes sharing one tzinfo subtract NAIVELY in Python, hence
    the explicit conversion to UTC first."""
    nxt = day + timedelta(days=1)
    start = datetime(day.year, day.month, day.day, tzinfo=WARSAW).astimezone(timezone.utc)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=WARSAW).astimezone(timezone.utc)
    return int(round((end - start).total_seconds() / 3600))


_DAILY_COLUMNS = ["lat", "lon", "local_date", "radar_mm", "radar_hours", "expected_hours"]


def radar_daily_at_points(hourly: pd.DataFrame) -> pd.DataFrame:
    """Sum hours into local days. An hour belongs to the local day of its
    START (hour_end - 1 h). NaN hours (no radar data at the point) are not
    counted, so they get gap-filled in merge_radar_into_daily."""
    valid = hourly.dropna(subset=["precip_mm"])
    if valid.empty:
        return pd.DataFrame(columns=_DAILY_COLUMNS)
    start_local = (pd.to_datetime(valid["hour_end_utc"], utc=True) - pd.Timedelta(hours=1)).dt.tz_convert("Europe/Warsaw")
    grouped = (
        valid.assign(local_date=start_local.dt.date)
        .groupby(["lat", "lon", "local_date"], as_index=False)
        .agg(radar_mm=("precip_mm", "sum"), radar_hours=("precip_mm", "size"))
    )
    grouped["expected_hours"] = grouped["local_date"].map(expected_local_hours)
    return grouped[_DAILY_COLUMNS]


def merge_radar_into_daily(weather_daily: pd.DataFrame, radar_daily: pd.DataFrame,
                           window_start: date, window_end: date) -> pd.DataFrame:
    """Plan A1 D6: precip = radar_sum + model * (1 - k/n) for local days in
    [window_start, window_end] with k>0 radar hours; untouched otherwise."""
    out = weather_daily.reset_index(drop=True).copy()
    out["precipitation_mm"] = out["precipitation_mm"].astype(float)
    out["precipitation_mm_model"] = out["precipitation_mm"]
    out["radar_frac"] = 0.0
    if radar_daily.empty:
        return out
    dates = out["date"]
    # Open-Meteo's `date` is the UTC instant of LOCAL midnight -- converting
    # is what makes 2026-09-25 22:00 UTC mean local 2026-09-26.
    local_date = (dates.dt.tz_convert("Europe/Warsaw") if dates.dt.tz is not None else dates).dt.date
    in_window = ((local_date >= window_start) & (local_date <= window_end)).to_numpy()
    joined = radar_daily.set_index(["lat", "lon", "local_date"]).reindex(
        pd.MultiIndex.from_arrays([out["lat"], out["lon"], local_date]))
    hours = joined["radar_hours"].to_numpy(dtype=float)
    expected = joined["expected_hours"].to_numpy(dtype=float)
    has = in_window & np.nan_to_num(hours, nan=0.0).astype(bool)
    frac = np.clip(np.nan_to_num(hours / expected, nan=0.0), 0.0, 1.0)
    merged = joined["radar_mm"].to_numpy(dtype=float) + out["precipitation_mm_model"].to_numpy() * (1.0 - frac)
    out.loc[has, "precipitation_mm"] = merged[has]
    out.loc[has, "radar_frac"] = frac[has]
    return out


def radar_window(today: date, window_days: int, now_utc: datetime) -> tuple[date, date, datetime, datetime]:
    """Local-day window [today - window_days + 1, today] and its UTC bounds
    (end clipped to now: future hours have no radar)."""
    window_start = today - timedelta(days=window_days - 1)
    start_utc = datetime(window_start.year, window_start.month, window_start.day,
                         tzinfo=WARSAW).astimezone(timezone.utc)
    nxt = today + timedelta(days=1)
    end_utc = min(now_utc, datetime(nxt.year, nxt.month, nxt.day, tzinfo=WARSAW).astimezone(timezone.utc))
    return window_start, today, start_utc, end_utc


def make_radar_weather_fetcher(base_fetcher, *, half_size_m: float, window_days: int, cache_dir,
                               http_get=None, now_utc: datetime | None = None, today: date | None = None,
                               radar_hourly_fn=None):
    """Wrap an Open-Meteo weather_fetcher (same signature) so precipitation
    in the radar window comes from RainGRS. IMGW down -> Open-Meteo only."""
    radar_hourly_fn = radar_hourly_fn or radar_hourly_at_points

    def fetcher(points, past_days, forecast_days=1):
        daily = base_fetcher(points, past_days, forecast_days=forecast_days)
        now = now_utc or datetime.now(timezone.utc)
        local_today = today or now.astimezone(WARSAW).date()
        window_start, window_end, start_utc, end_utc = radar_window(local_today, window_days, now)
        try:
            hourly = radar_hourly_fn(points, half_size_m, start_utc, end_utc, cache_dir,
                                     http_get=http_get, now_utc=now)
        except RadarUnavailableError as exc:
            print(f"UWAGA: radar IMGW niedostepny ({exc}) -- opady tylko z modelu Open-Meteo.", flush=True)
            hourly = pd.DataFrame({"lat": [], "lon": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"),
                                   "precip_mm": []})
        return merge_radar_into_daily(daily, radar_daily_at_points(hourly), window_start, window_end)

    return fetcher
