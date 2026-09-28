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

import geopandas as gpd
import numpy as np
import pandas as pd
import scipy.sparse as sp
from pyproj import Transformer
from shapely.geometry import box as shapely_box

from pipeline.weather import to_local_date

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


def cell_bounds(header: GridHeader, row: int, col: int) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) of the grid cell at array index (row, col) --
    row counted from the top (north), as in `parse_grs_asc`'s output and
    `block_slices`'s slices. Plan 1.5.1: shared by the stand-polygon weight
    builder below."""
    cs = header.cellsize
    y_top = header.yllcorner + (header.nrows - row) * cs
    x_left = header.xllcorner + col * cs
    return x_left, y_top - cs, x_left + cs, y_top


def _bbox_cell_range(header: GridHeader, minx: float, miny: float, maxx: float, maxy: float,
                      margin_cells: int = 0) -> tuple[int, int, int, int]:
    """(row0, row1, col0, col1) array-index range (inclusive, row 0 = north)
    of every cell overlapping [minx, maxx] x [miny, maxy], expanded by
    `margin_cells` on every side and clipped to the grid -- the margin gives
    `smooth_grid_stack` real neighbours at the edge of the cropped window
    instead of an artificial zero-padded boundary."""
    cs = header.cellsize
    c0 = math.floor((minx - header.xllcorner) / cs) - margin_cells
    c1 = math.floor((maxx - header.xllcorner) / cs) + margin_cells
    k0 = math.floor((miny - header.yllcorner) / cs) - margin_cells  # k = row from bottom
    k1 = math.floor((maxy - header.yllcorner) / cs) + margin_cells
    c0, c1 = max(c0, 0), min(c1, header.ncols - 1)
    k0, k1 = max(k0, 0), min(k1, header.nrows - 1)
    row0, row1 = header.nrows - 1 - k1, header.nrows - 1 - k0
    return row0, row1, c0, c1


def smoothing_radius_cells(smoothing_km: float, cellsize_m: float) -> int:
    """Plan 1.5.2: `radar.smoothing_km` in {0,1,2,3} as a whole number of
    grid cells (RainGRS cellsize is 1000 m, so normally 1:1 -- the division
    only matters if a test grid uses a different cellsize)."""
    if smoothing_km <= 0:
        return 0
    return max(1, round(smoothing_km * 1000.0 / cellsize_m))


def smooth_grid_stack(stack: np.ndarray, radius_cells: int) -> np.ndarray:
    """NaN-aware spatial box filter over the last two axes of `stack`
    (..., nrows, ncols): each cell becomes the mean of the (2r+1)x(2r+1)
    square around it, counting only non-NaN neighbours (a cell with zero
    valid neighbours stays NaN). Plan 1.5.2: protects against a single noisy
    radar cell/beam-shadow artefact dominating a stand's sample; radius_cells
    = 0 returns `stack` unchanged (no smoothing, raw 1 km field)."""
    if radius_cells <= 0:
        return stack
    from scipy.ndimage import uniform_filter

    size = 2 * radius_cells + 1
    valid = ~np.isnan(stack)
    filled = np.nan_to_num(stack, nan=0.0)
    window_area = float(size * size)
    axes = tuple(range(stack.ndim - 2, stack.ndim))
    sum_vals = uniform_filter(filled, size=size, mode="constant", cval=0.0, axes=axes) * window_area
    sum_valid = uniform_filter(valid.astype(np.float64), size=size, mode="constant", cval=0.0, axes=axes) * window_area
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # 0/0 where sum_valid == 0
        smoothed = sum_vals / sum_valid
    smoothed[sum_valid == 0] = np.nan
    return smoothed


@dataclass
class StandWeights:
    """Plan 1.5.1: a sparse (n_stands x n_crop_cells) area-weight matrix
    mapping each stand polygon to the RainGRS 1 km cells it overlaps, plus
    where that crop sits inside the full national grid (row0/col0) so the
    same-shaped slice of any day's grid lines up with `weights`'s columns."""
    stand_ids: list
    row0: int
    col0: int
    n_rows: int
    n_cols: int
    weights: sp.csr_matrix  # (len(stand_ids), n_rows * n_cols), rows sum to <= 1
    spatial_coverage: np.ndarray  # (len(stand_ids),) -- 1.0 unless part of the stand fell outside the grid


def build_stand_cell_weights(stands: gpd.GeoDataFrame, header: GridHeader, margin_cells: int = 0) -> StandWeights:
    """Plan 1.5.1: one weight per (stand, overlapping cell) pair, weight =
    share of the stand's area covered by that cell. A stand smaller than one
    cell (the common case -- a RainGRS cell is 100 ha, most wydzielenia are a
    few ha) takes its centroid's cell with weight 1 (spec 1.5.1); a larger
    stand's weight is the real intersection area with every cell it
    overlaps, normalised by the total intersected area (so weights sum to 1
    even if geometry/CRS rounding leaves a sliver uncovered). `stands` must
    already be in the grid's own CRS (EPSG:2180 for RainGRS -- true for BDL
    stand geometries, no reprojection needed)."""
    cs = header.cellsize
    cell_area = cs * cs
    xll, yll, nrows, ncols = header.xllcorner, header.yllcorner, header.nrows, header.ncols
    stand_ids = stands["stand_id"].tolist()
    geoms = stands.geometry.to_numpy()
    minx, miny, maxx, maxy = stands.total_bounds
    row0, row1, col0, col1 = _bbox_cell_range(header, minx, miny, maxx, maxy, margin_cells)
    n_rows, n_cols = row1 - row0 + 1, col1 - col0 + 1

    cell_index: dict[tuple[int, int], int] = {}
    rows_idx, cols_idx, weight_vals = [], [], []
    spatial_coverage = np.ones(len(stand_ids), dtype=np.float64)

    def _local_col(row: int, col: int) -> int:
        key = (row - row0, col - col0)
        idx = cell_index.get(key)
        if idx is None:
            idx = key[0] * n_cols + key[1]
            cell_index[key] = idx
        return idx

    for i, geom in enumerate(geoms):
        centroid = geom.centroid
        cx, cy = centroid.x, centroid.y
        c = math.floor((cx - xll) / cs)
        k = math.floor((cy - yll) / cs)  # row from bottom
        if not (0 <= c < ncols and 0 <= k < nrows):
            spatial_coverage[i] = 0.0
            continue
        centroid_row = nrows - 1 - k
        if geom.area <= cell_area:
            rows_idx.append(i)
            cols_idx.append(_local_col(centroid_row, c))
            weight_vals.append(1.0)
            continue
        gminx, gminy, gmaxx, gmaxy = geom.bounds
        r0, r1, cc0, cc1 = _bbox_cell_range(header, gminx, gminy, gmaxx, gmaxy)
        found = []
        for r in range(r0, r1 + 1):
            for cidx in range(cc0, cc1 + 1):
                cell_poly = shapely_box(*cell_bounds(header, r, cidx))
                inter_area = geom.intersection(cell_poly).area
                if inter_area > 0:
                    found.append((r, cidx, inter_area))
        total = sum(a for _, _, a in found)
        if total <= 0:
            # Geometry entirely outside the grid (shouldn't happen for a
            # Polish forest stand, but a defensive fallback all the same):
            # keep the centroid-cell behaviour rather than dropping the stand.
            if 0 <= c < ncols and 0 <= k < nrows:
                rows_idx.append(i)
                cols_idx.append(_local_col(centroid_row, c))
                weight_vals.append(1.0)
            else:
                spatial_coverage[i] = 0.0
            continue
        spatial_coverage[i] = min(1.0, total / geom.area)
        for r, cidx, area in found:
            rows_idx.append(i)
            cols_idx.append(_local_col(r, cidx))
            weight_vals.append(area / total)

    weights = sp.csr_matrix(
        (weight_vals, (rows_idx, cols_idx)), shape=(len(stand_ids), n_rows * n_cols),
    )
    return StandWeights(stand_ids=stand_ids, row0=row0, col0=col0, n_rows=n_rows, n_cols=n_cols,
                        weights=weights, spatial_coverage=spatial_coverage)


def sample_stack_weighted(stack: np.ndarray, stand_weights: StandWeights) -> np.ndarray:
    """(hours, n_rows, n_cols) grid crop -> (hours, n_stands) area-weighted
    means, NaN-aware: an hour where every cell a stand overlaps is NaN gives
    NaN for that stand/hour; a partially-NaN set of cells renormalises the
    weighted mean over just the valid ones (mirrors `sample_stack`'s
    NaN handling for the block-mean path, generalised to real area weights
    via one sparse matmul per hour-batch instead of a python loop -- plan
    1.5.1's "implementacja wektorowa")."""
    h = stack.shape[0]
    flat = stack.reshape(h, -1)
    valid = ~np.isnan(flat)
    filled = np.nan_to_num(flat, nan=0.0)
    w = stand_weights.weights  # (S, C)
    numerator = np.asarray(w @ filled.T)  # (S, H)
    denom = np.asarray(w @ valid.T.astype(np.float64))  # (S, H)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # 0/0 where denom == 0
        result = numerator / denom
    result[denom == 0] = np.nan
    return result.T  # (H, S)


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
        except requests.exceptions.RequestException as exc:
            # Intermittent DNS failures for danepubliczne.imgw.pl observed
            # live 2026-09-26 (ConnectionError/Timeout); a connection dropped
            # mid-download (e.g. downloading an ~80 MB archive tar) raises
            # ChunkedEncodingError instead -- same RequestException family,
            # same retry-then-give-up treatment (D9).
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


def radar_daily_at_points(hourly: pd.DataFrame, key_cols: tuple[str, ...] = ("lat", "lon")) -> pd.DataFrame:
    """Sum hours into local days. An hour belongs to the local day of its
    START (hour_end - 1 h). NaN hours (no radar data at the point) are not
    counted, so they get gap-filled in merge_radar_into_daily.

    `key_cols` (plan 1.5.1): defaults to the original (lat, lon) block-point
    identity; the per-stand radar path (`radar_hourly_at_stands`) reuses this
    exact function with `key_cols=("stand_id",)` instead of duplicating the
    local-day grouping logic (including its DST handling) for stands."""
    key_cols = list(key_cols)
    columns = key_cols + ["local_date", "radar_mm", "radar_hours", "expected_hours"]
    valid = hourly.dropna(subset=["precip_mm"])
    if valid.empty:
        return pd.DataFrame(columns=columns)
    start_local = (pd.to_datetime(valid["hour_end_utc"], utc=True) - pd.Timedelta(hours=1)).dt.tz_convert("Europe/Warsaw")
    grouped = (
        valid.assign(local_date=start_local.dt.date)
        .groupby(key_cols + ["local_date"], as_index=False)
        .agg(radar_mm=("precip_mm", "sum"), radar_hours=("precip_mm", "size"))
    )
    grouped["expected_hours"] = grouped["local_date"].map(expected_local_hours)
    return grouped[columns]


def merge_radar_into_daily(weather_daily: pd.DataFrame, radar_daily: pd.DataFrame,
                           window_start: date, window_end: date,
                           key_cols: tuple[str, ...] = ("lat", "lon")) -> pd.DataFrame:
    """Plan A1 D6: precip = radar_sum + model * (1 - k/n) for local days in
    [window_start, window_end] with k>0 radar hours; untouched otherwise.

    `key_cols` (plan 1.5.1): generalises the original (lat, lon) join key so
    the same merge formula -- and the same DST-safe local-date handling --
    serves the per-stand radar path with `key_cols=("stand_id",)`."""
    key_cols = list(key_cols)
    out = weather_daily.reset_index(drop=True).copy()
    out["precipitation_mm"] = out["precipitation_mm"].astype(float)
    out["precipitation_mm_model"] = out["precipitation_mm"]
    out["radar_frac"] = 0.0
    if radar_daily.empty:
        return out
    # Plan 1.8b: shared with pipeline.flush/pipeline.conditions_timeline's
    # own local-date conversion -- see pipeline.weather.to_local_date's
    # docstring for why the noon-recentering matters here.
    local_date = to_local_date(out["date"])
    in_window = ((local_date >= window_start) & (local_date <= window_end)).to_numpy()
    joined = radar_daily.set_index(key_cols + ["local_date"]).reindex(
        pd.MultiIndex.from_arrays([out[c] for c in key_cols] + [local_date]))
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


def radar_hourly_at_stands(stands: gpd.GeoDataFrame, smoothing_km: float,
                           start_utc: datetime, end_utc: datetime, cache_dir,
                           http_get=None, now_utc: datetime | None = None) -> pd.DataFrame:
    """Plan 1.5.1/1.5.2: hourly RainGRS, area-weighted per stand polygon
    (`build_stand_cell_weights`) instead of a block mean around a shared
    weather point, with an optional NaN-aware spatial smoothing pass
    (`smooth_grid_stack`) first. Reuses the exact same per-day cache/fetch
    path as `radar_hourly_at_points` (`_load_or_fetch_day`) -- a run that
    already has block-mode radar cached for this window fetches nothing new
    for stand mode, and vice versa.

    Returns a long frame [stand_id, hour_end_utc, precip_mm] with a
    `.attrs["spatial_coverage"]` dict {stand_id: fraction of the stand's own
    area actually covered by a grid cell -- plan 1.5.1's "pokrycie
    przestrzenne", tracked separately from the per-hour data-availability
    fraction that `radar_daily_at_points`/`merge_radar_into_daily` already
    compute as radar_hours/expected_hours}."""
    http_get = http_get or _default_http_get
    now_utc = now_utc or datetime.now(timezone.utc)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames, sources = [], {}
    stand_weights: StandWeights | None = None
    day = start_utc.date()
    while day <= end_utc.date():
        if datetime(day.year, day.month, day.day, tzinfo=timezone.utc) > now_utc:
            break
        data, source = _load_or_fetch_day(day, cache_dir, http_get, now_utc)
        sources[source] = sources.get(source, 0) + 1
        day += timedelta(days=1)
        if data is None:
            continue
        if stand_weights is None:
            radius_cells = smoothing_radius_cells(smoothing_km, data.header.cellsize)
            stand_weights = build_stand_cell_weights(stands, data.header, margin_cells=radius_cells)
        keep = [i for i, h in enumerate(data.hour_ends) if start_utc < h <= end_utc]
        if not keep:
            continue
        crop_q = data.q[np.ix_(keep,
                               range(stand_weights.row0, stand_weights.row0 + stand_weights.n_rows),
                               range(stand_weights.col0, stand_weights.col0 + stand_weights.n_cols))]
        crop = dequantize(crop_q)
        radius_cells = smoothing_radius_cells(smoothing_km, data.header.cellsize)
        crop = smooth_grid_stack(crop, radius_cells)
        values = sample_stack_weighted(crop, stand_weights)
        hours = pd.DatetimeIndex([data.hour_ends[i] for i in keep])
        frames.append(pd.DataFrame({
            "stand_id": np.tile(stand_weights.stand_ids, len(keep)),
            "hour_end_utc": hours.repeat(len(stand_weights.stand_ids)),
            "precip_mm": values.reshape(-1),
        }))
    print("Radar IMGW (RainGRS, per wydzielenie): " +
          ", ".join(f"{k} {v}" for k, v in sorted(sources.items())) + " dob", flush=True)
    if not frames:
        empty = pd.DataFrame({"stand_id": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"), "precip_mm": []})
        empty.attrs["spatial_coverage"] = {}
        return empty
    out = pd.concat(frames, ignore_index=True)
    out.attrs["spatial_coverage"] = (
        dict(zip(stand_weights.stand_ids, stand_weights.spatial_coverage.tolist())) if stand_weights else {}
    )
    return out


def stand_radar_precip_daily(stands: gpd.GeoDataFrame, nearest_weather_point: dict,
                             base_weather_daily: pd.DataFrame, *, smoothing_km: float, window_days: int,
                             cache_dir, http_get=None, now_utc: datetime | None = None,
                             today: date | None = None, radar_hourly_fn=None) -> pd.DataFrame:
    """Plan 1.5: per-stand daily precipitation -- RainGRS sampled over each
    stand's own polygon for local days in the radar window, gap-filled
    outside that window (and for hours radar doesn't cover inside it) with
    the Open-Meteo model precip of `nearest_weather_point[stand_id]`, via the
    exact same merge formula `make_radar_weather_fetcher` uses for the
    block-mode path (`merge_radar_into_daily`, generalised with
    `key_cols=("stand_id",)`).

    `base_weather_daily` must be the RAW model fetch (no radar already
    merged in) at the weather grid points -- the caller passes the
    un-wrapped base fetcher's own output, not `build_weather_fetcher`'s
    radar-wrapped one, precisely so precipitation is decided per stand here
    instead of per weather point. IMGW failures never abort a run (D9, same
    contract as `make_radar_weather_fetcher`): every stand just falls back
    to 100% model precip with radar_frac = 0."""
    radar_hourly_fn = radar_hourly_fn or radar_hourly_at_stands
    now = now_utc or datetime.now(timezone.utc)
    local_today = today or now.astimezone(WARSAW).date()
    window_start, window_end, start_utc, end_utc = radar_window(local_today, window_days, now)

    stand_ids = stands["stand_id"].tolist()
    point_by_stand = pd.DataFrame({
        "stand_id": stand_ids,
        "lat": [nearest_weather_point[sid][0] for sid in stand_ids],
        "lon": [nearest_weather_point[sid][1] for sid in stand_ids],
    })
    stand_model_daily = point_by_stand.merge(
        base_weather_daily[["lat", "lon", "date", "precipitation_mm"]], on=["lat", "lon"], how="left",
    )[["stand_id", "date", "precipitation_mm"]]

    try:
        hourly = radar_hourly_fn(stands, smoothing_km, start_utc, end_utc, cache_dir,
                                 http_get=http_get, now_utc=now)
        spatial_coverage = hourly.attrs.get("spatial_coverage", {})
    except RadarUnavailableError as exc:
        print(f"UWAGA: radar IMGW niedostepny ({exc}) -- opady na wydzielenie tylko z modelu Open-Meteo.",
              flush=True)
        hourly = pd.DataFrame({"stand_id": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"), "precip_mm": []})
        spatial_coverage = {}
    except Exception as exc:  # D9: never fail a run because of IMGW.
        print(f"UWAGA: radar IMGW niedostepny (blad: {exc}) -- opady na wydzielenie tylko z modelu Open-Meteo.",
              flush=True)
        hourly = pd.DataFrame({"stand_id": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"), "precip_mm": []})
        spatial_coverage = {}

    radar_daily = radar_daily_at_points(hourly, key_cols=("stand_id",))
    merged = merge_radar_into_daily(stand_model_daily, radar_daily, window_start, window_end,
                                    key_cols=("stand_id",))
    merged.attrs["spatial_coverage"] = spatial_coverage
    return merged


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
        except Exception as exc:
            # D9: "a run never fails because of IMGW" -- a corrupt cached
            # .npz, a truncated archive tar surviving http_get's retries, or
            # a malformed grid header are unanticipated failure shapes, not
            # RadarUnavailableError, but the fallback must be the same.
            print(f"UWAGA: radar IMGW niedostepny (blad: {exc}) -- opady tylko z modelu Open-Meteo.", flush=True)
            hourly = pd.DataFrame({"lat": [], "lon": [], "hour_end_utc": pd.DatetimeIndex([], tz="UTC"),
                                   "precip_mm": []})
        return merge_radar_into_daily(daily, radar_daily_at_points(hourly), window_start, window_end)

    return fetcher
