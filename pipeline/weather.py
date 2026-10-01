import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import stats

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def make_grid(bbox_2180: tuple, spacing_m: float = 5000.0) -> list[tuple[float, float]]:
    """Grid points aligned to a fixed absolute EPSG:2180 grid (multiples of
    spacing_m from the origin), not to the bbox's own corner -- so two
    searches whose bboxes only partially overlap still produce identical
    (lat, lon) values wherever they cover the same ground. This is what
    lets _fetch_with_point_cache reuse cache entries across different
    radii/centers, the same way pipeline/search_area.py's fixed 10km tile
    grid already does for BDL. Points can extend up to one spacing_m
    beyond the bbox edge (no longer clamped to n_max/e_max) as a result."""
    n_min, e_min, n_max, e_max = bbox_2180
    n_start = math.floor(n_min / spacing_m) * spacing_m
    e_start = math.floor(e_min / spacing_m) * spacing_m
    n_steps = max(1, int(math.ceil((n_max - n_start) / spacing_m)))
    e_steps = max(1, int(math.ceil((e_max - e_start) / spacing_m)))
    points = []
    for i in range(n_steps + 1):
        n = n_start + i * spacing_m
        for j in range(e_steps + 1):
            e = e_start + j * spacing_m
            lon, lat = _TO_4326.transform(e, n)
            points.append((lat, lon))
    return points


def to_local_date(dates: pd.Series) -> pd.Series:
    """Plan 1.8b: the ONE shared UTC-instant -> Europe/Warsaw calendar-date
    conversion for a daily weather `date` column, used by pipeline.radar's
    merge_radar_into_daily, pipeline.flush.area_daily_weather and
    pipeline.conditions_timeline.with_local_date -- previously three
    separate implementations, two of them (flush/conditions_timeline)
    naive and one (radar) noon-corrected, which could disagree around a
    DST transition (see tests/test_weather.py's
    test_to_local_date_matches_across_a_dst_transition for the shared
    regression test across both of 2026's transition dates).

    Recentring on local noon before converting (matching radar's own
    original fix) survives up to +/-12h of drift between the UTC instant a
    row's `date` actually carries and that day's true local midnight --
    _parse_open_meteo_response above builds the whole date range with one
    FIXED 24h step from the first day's local midnight
    (pd.date_range(..., freq=Interval())), which is only 86400s across a
    DST transition day, not the real local elapsed time -- so a naive
    tz_convert().dt.date drifts by the DST hour for every day at and after
    the transition, silently collapsing or duplicating a calendar date.
    Naive (tz-less) dates, e.g. from test fakes, are returned as-is."""
    if dates.dt.tz is None:
        return dates.dt.date
    return (dates + pd.Timedelta(hours=12)).dt.tz_convert("Europe/Warsaw").dt.date


def _point_frame(data: dict, lat: float, lon: float) -> pd.DataFrame:
    """One point's DataFrame with lat/lon and a `date` column of a single, fixed
    dtype (datetime64[ns, UTC]). Needed because a fresh API response and a
    per-point cache read (parquet round trip) carry the same instants at
    DIFFERENT datetime resolutions (seconds vs milliseconds), and pandas 3's
    pd.concat of such frames yields dtype `object` -- which then crashed
    `.dt` accessors downstream (radar merge) as soon as a run mixed cached and
    freshly fetched points, e.g. after widening the search radius."""
    df = pd.DataFrame(data)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True).astype("datetime64[ns, UTC]")
    df["lat"] = lat
    df["lon"] = lon
    return df


def _point_cache_path(cache_dir: Path, lat: float, lon: float, suffix: str | None) -> Path:
    name = f"{lat:.6f}_{lon:.6f}"
    if suffix is not None:
        name += f"_{suffix}"
    return cache_dir / f"{name}.parquet"


def _fetch_with_point_cache(points: list[tuple[float, float]], cache_dir: Path,
                              suffix: str | None, call_api) -> list[dict]:
    """Per-point disk cache in front of a batched call_api. Mirrors
    pipeline/search_area.py's per-tile BDL cache (check file exists, print
    status, fetch and save on miss) at point granularity instead of tile
    granularity: Open-Meteo batches many points into one HTTP request, so a
    per-request cache (requests_cache, still used underneath by
    _default_open_meteo_call/_default_climatology_call for in-run retries)
    doesn't help reuse across searches whose grids only partially overlap.
    `suffix` scopes the cache key -- pass None for data that never changes
    (climatology's 30-year archive) or e.g. today's ISO date for data that
    does (live weather, a rolling window ending today)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached: dict[tuple[float, float], dict] = {}
    missing = []
    for lat, lon in points:
        path = _point_cache_path(cache_dir, lat, lon, suffix)
        if path.exists():
            cached[(lat, lon)] = pd.read_parquet(path).to_dict(orient="list")
        else:
            missing.append((lat, lon))
    print(f"  {len(points) - len(missing)}/{len(points)} z cache" +
          (f", pobieranie {len(missing)}..." if missing else ""), flush=True)
    if missing:
        fresh = call_api(missing)
        for point, data in zip(missing, fresh):
            path = _point_cache_path(cache_dir, point[0], point[1], suffix)
            temp = path.with_suffix(".tmp.parquet")
            pd.DataFrame(data).to_parquet(temp)
            temp.replace(path)
            cached[point] = data
    return [cached[p] for p in points]


_OPEN_METEO_BATCH_SIZE = 50  # see _chunked's docstring for why this exists

# Climatology gets its own, much smaller batch size. Open-Meteo weights a
# request by (days-range / 14) x (variables / 10) x locations (documented at
# open-meteo.com/en/pricing and openmeteo.substack.com/p/weather-data-for-
# multiple-locations-at-once); a 30-year, 3-variable climatology pull already
# weighs ~235 "calls" for a SINGLE point, so 50 points in one request (as
# used for the much lighter live-forecast call) weighs ~11750 and was
# observed live 2026-09-24 to fail with "Your API call requests too much
# data" -- a distinct, synchronous per-request error, not the request-count
# quota error batching originally fixed. 10 points/request keeps a single
# request's weight (~2350) well under that observed failure point and under
# the free tier's 5000/hour and 600/minute caps individually. Still a
# conservative guess pending a live re-run: Open-Meteo does not publish the
# exact per-request cap that triggers the "too much data" error.
_OPEN_METEO_CLIMATOLOGY_BATCH_SIZE = 10


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _parse_open_meteo_response(response) -> dict:
    daily = response.Daily()
    dates = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left",
    )
    hourly = response.Hourly()
    soil = hourly.Variables(0).ValuesAsNumpy()
    soil_daily = pd.Series(soil).groupby(np.arange(len(soil)) // 24).mean().to_numpy()
    return {
        "date": dates,
        "precipitation_mm": daily.Variables(0).ValuesAsNumpy(),
        "tmean_c": daily.Variables(1).ValuesAsNumpy(),
        "tmin_c": daily.Variables(2).ValuesAsNumpy(),
        "tmax_c": daily.Variables(3).ValuesAsNumpy(),
        "et0_mm": daily.Variables(4).ValuesAsNumpy(),
        "soil_moisture": soil_daily[: len(dates)],
    }


def _default_open_meteo_call(points: list[tuple[float, float]], past_days: int,
                               forecast_days: int = 1) -> list[dict]:
    """Thin IO boundary around the real Open-Meteo archive+forecast API.
    Not covered by unit tests (network); exercised manually.

    Batches every point into as few HTTP requests as possible (Open-Meteo
    accepts comma-separated latitude/longitude lists in one call) instead
    of one request per point -- at radius-search grid sizes (dozens to
    100+ points) the old one-request-per-point version exhausted
    Open-Meteo's free-tier hourly request quota on a single prepare_trip
    run (observed live 2026-09-24: a 121-point run failed mid-climatology
    with "Hourly API request limit exceeded"). Chunked at
    _OPEN_METEO_BATCH_SIZE (50, a conservative guess -- Open-Meteo does not
    publish a hard per-request location cap for this endpoint; verify
    against a real large-radius run once the hourly quota resets and widen
    if a single request handles more comfortably) so one pathologically
    large request doesn't risk a timeout or an undocumented limit either.
    Returns one dict per point, same order as `points`, same per-point
    shape this function used to return for a single point.

    `forecast_days` (plan 2.1 step A3, spec 3.3 "Prognoza do dnia
    wyjazdu"): Open-Meteo returns `past_days` historical days plus
    `forecast_days` days starting today (today counts as day 1) in one
    contiguous daily series -- verified live 2026-09-24 against
    api.open-meteo.com/v1/forecast (not the archive API) with
    past_days=5, forecast_days=16: 21 contiguous rows, no gap, no NaNs.
    compute_weather_features's windows are `.iloc[-N:]` on that series, so
    setting forecast_days = (target_date - today).days + 1 (see
    orchestrate.run_poc) makes every window end on the trip date for free,
    with no separate "end date" logic needed here."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    results = []
    for chunk in _chunked(points, _OPEN_METEO_BATCH_SIZE):
        responses = client.weather_api(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": [lat for lat, lon in chunk],
                "longitude": [lon for lat, lon in chunk],
                "daily": ["precipitation_sum", "temperature_2m_mean", "temperature_2m_min",
                           "temperature_2m_max", "et0_fao_evapotranspiration"],
                "hourly": ["soil_moisture_9_to_27cm"],
                "past_days": past_days,
                "forecast_days": forecast_days,
                "timezone": "Europe/Warsaw",
            },
        )
        results.extend(_parse_open_meteo_response(r) for r in responses)
    return results


def _seed_from_longer_forecast(points, cache_dir: Path, today: str, past_days: int, forecast_days: int) -> None:
    """Brakujacy wpis cache (dzis, past_days, forecast_days) wycina z dluzszej prognozy pobranej dzis dla
    tego samego punktu i tego samego past_days: Open-Meteo zwraca ciagla serie, a dni wspolne sa
    identyczne (sprawdzone na 288 punktach 1.10.2026: roznica 0 we wszystkich polach). prepare_trip
    pobiera najpierw 7 dni (os czasu warunkow), potem run_poc 1 dzien -- drugie zapytanie bylo zbedne."""
    rows = past_days + forecast_days
    for lat, lon in points:
        target = _point_cache_path(cache_dir, lat, lon, f"{today}_fd{forecast_days}_pd{past_days}_v1")
        if target.exists():
            continue
        longer = []
        for path in cache_dir.glob(f"{lat:.6f}_{lon:.6f}_{today}_fd*_pd{past_days}_v1.parquet"):
            fd = int(path.name.split("_fd")[1].split("_")[0])
            if fd > forecast_days:
                longer.append((fd, path))
        if not longer:
            continue
        frame = pd.read_parquet(min(longer)[1])
        if len(frame) < rows:
            continue
        temp = target.with_suffix(".tmp.parquet")
        frame.iloc[:rows].reset_index(drop=True).to_parquet(temp)
        temp.replace(target)


def fetch_weather_raw(points: list[tuple[float, float]], past_days: int = 92,
                        forecast_days: int = 1, call_api=None,
                        cache_dir: Path | None = None) -> pd.DataFrame:
    call_api = call_api or _default_open_meteo_call
    if cache_dir is None:
        results = call_api(points, past_days, forecast_days=forecast_days)
    else:
        # Scoped to today, forecast_days AND past_days (plan 2.1 step A3 +
        # plan 1.8e): past_days is a rolling window ending "now", so
        # yesterday's cached values would silently look like today's -- and
        # two runs on the same day with a different --date (so a different
        # forecast_days) or a different past_days fetch a genuinely
        # different Open-Meteo response, so they must not share a cache
        # entry either. "_v1" is the cache format version (plan 1.8e): bump
        # it if this row shape ever changes incompatibly, so an old file
        # is never misread as the new shape -- old files are never deleted
        # for this, just no longer matched by the new key.
        _seed_from_longer_forecast(points, Path(cache_dir) / "weather_points", date.today().isoformat(),
                                   past_days, forecast_days)
        results = _fetch_with_point_cache(
            points, Path(cache_dir) / "weather_points",
            f"{date.today().isoformat()}_fd{forecast_days}_pd{past_days}_v1",
            lambda pts: call_api(pts, past_days, forecast_days=forecast_days),
        )
    frames = [_point_frame(data, lat, lon) for (lat, lon), data in zip(points, results)]
    result = pd.concat(frames, ignore_index=True)
    if cache_dir is not None:
        # Plan 2.2: keep the raw forecast with its issue time. Best-effort --
        # a failed archive write must never abort an otherwise good run.
        try:
            from pipeline.forecast_archive import archive_forecast
            archive_forecast(result, Path(cache_dir), forecast_days)
        except OSError as exc:
            print(f"  UWAGA: nie zapisano archiwum prognoz: {exc}", flush=True)
    return result


def _rolling_sum(series: pd.Series, window: int) -> float:
    return series.iloc[-window:].sum()


def _exp_weighted_sum(series: pd.Series, window: int, half_life_days: float = 10.0) -> float:
    tail = series.iloc[-window:]
    n = len(tail)
    ages = np.arange(n - 1, -1, -1)
    weights = 0.5 ** (ages / half_life_days)
    return float((tail.to_numpy() * weights).sum())


def _exp_weighted_mean(series: pd.Series, window: int, half_life_days: float = 10.0) -> float:
    """Same weights as _exp_weighted_sum, normalised -- the share of the
    P26w window's weight that `series` (0..1 per day) represents."""
    tail = series.iloc[-window:]
    ages = np.arange(len(tail) - 1, -1, -1)
    weights = 0.5 ** (ages / half_life_days)
    return float((tail.to_numpy(dtype=float) * weights).sum() / weights.sum())


def precip_derived_features(p: pd.Series, radar_frac: pd.Series | None = None) -> dict:
    """Everything derived purely from a daily precipitation series (+ its
    optional radar_frac companion): p5, p26w, days_since_p10,
    rain_radar_coverage. Plan 1.5: pulled out of `compute_weather_features`
    so the per-stand radar path (pipeline.orchestrate.run_poc's
    `stand_precip_daily`) can recompute the SAME precip-only features from a
    stand's own merged precip series -- combined there with the shared
    weather point's et026w into a stand-specific cwb26 -- without
    duplicating this logic (or its days_since_p10 edge cases) a second time.

    `p5` feeds score_temperature's heat penalty (spec §4.3: Tmean5 > 17.5°C
    AND P5 < 5 mm), profile key heat_penalty_p5_mm. `rain_radar_coverage` is
    plan A1's exp-weighted share of the P26w window whose rain came from the
    IMGW radar rather than Open-Meteo's model."""
    p26w = _exp_weighted_sum(p, window=min(26, len(p)))
    rain_radar_coverage = (
        _exp_weighted_mean(radar_frac, window=min(26, len(p)))
        if radar_frac is not None else 0.0
    )
    at_or_above_10 = p[p >= 10.0]
    if len(at_or_above_10):
        last_p10_pos = p.index.get_indexer(at_or_above_10.index).max()
        days_since_p10 = (len(p) - 1) - last_p10_pos
    else:
        days_since_p10 = len(p)
    return {
        "p5": _rolling_sum(p, 5), "p26w": p26w,
        "days_since_p10": days_since_p10, "rain_radar_coverage": rain_radar_coverage,
    }


def stand_precip_features_table(stand_precip_daily: pd.DataFrame) -> pd.DataFrame:
    """Plan 1.5 performance: the same per-stand p5/p26w/rain_radar_coverage
    `precip_derived_features` would give for each stand_id's own group, but
    computed in one vectorized pass over the whole frame instead of
    materialising one pandas group object per stand.

    Why this exists: `{sid: g for sid, g in df.groupby("stand_id")}` (the
    first version of this) forces pandas to build one full DataFrame per
    group -- fine for the ~144 weather-point groups `compute_weather_features`
    handles, but at the tens-of-thousands-of-stands scale of a real
    prepare_trip run, materialising every group up front dominated total
    run time (many minutes, still climbing, on a real 19716-stand Kieleczka
    20 km run 2026-09-28) instead of the couple of seconds it should take.

    Fast path: if every stand has the same number of rows in the same
    chronological order (guaranteed by construction -- stand_radar_precip_
    daily builds one row per stand per date of the SAME shared weather
    fetch), reshape straight into a (n_stands, n_dates) matrix and compute
    every stand's exp-weighted sum with two matrix-vector products, no
    per-stand Python loop at all. Falls back to the exact per-group
    computation (same numbers, just slower) when that assumption doesn't
    hold, e.g. a hand-built test fixture with uneven series lengths -- never
    silently wrong, only silently slower in that case."""
    df = stand_precip_daily.sort_values(["stand_id", "date"], kind="mergesort")
    sizes = df.groupby("stand_id", sort=False).size()
    if sizes.nunique() != 1:
        rows = []
        for sid, g in df.groupby("stand_id", sort=False):
            feat = precip_derived_features(g["precipitation_mm"], g["radar_frac"])
            rows.append({"stand_id": sid, "p5": feat["p5"], "p26w": feat["p26w"],
                        "rain_radar_coverage": feat["rain_radar_coverage"],
                        "p26_sum": _rolling_sum(g["precipitation_mm"], 26)})
        return pd.DataFrame(rows).set_index("stand_id")

    n_stands = len(sizes)
    n_dates = int(sizes.iloc[0])
    stand_order = df["stand_id"].to_numpy().reshape(n_stands, n_dates)[:, 0]
    precip = df["precipitation_mm"].to_numpy(dtype=float).reshape(n_stands, n_dates)
    radar_frac = df["radar_frac"].to_numpy(dtype=float).reshape(n_stands, n_dates)

    window = min(26, n_dates)
    ages = np.arange(window - 1, -1, -1)
    weights = 0.5 ** (ages / 10.0)
    p26w = precip[:, -window:] @ weights
    rain_radar_coverage = (radar_frac[:, -window:] @ weights) / weights.sum()
    p5 = precip[:, -min(5, n_dates):].sum(axis=1)
    p26_sum = precip[:, -window:].sum(axis=1)

    return pd.DataFrame(
        {"p5": p5, "p26w": p26w, "rain_radar_coverage": rain_radar_coverage, "p26_sum": p26_sum}, index=stand_order,
    ).rename_axis("stand_id")


def _coldest_recent_day(group: pd.DataFrame, days: int = 3) -> str | None:
    """Faza 4.3: data (ISO, lokalna) najzimniejszej doby sposrod ostatnich `days`."""
    tail = group.iloc[-days:]
    if not len(tail) or tail["tmin_c"].isna().all():
        return None
    local = to_local_date(tail["date"])
    return str(local.iloc[int(np.argmin(tail["tmin_c"].to_numpy()))])


def forecast_window_share(days_ahead: int, window: int = 26, half_life_days: float = 10.0) -> float:
    """Faza 4.5: wykladniczo wazony (tak jak P26w) udzial okna, ktory lezy w przyszlosci
    wzgledem dzisiaj, gdy wyjazd jest za `days_ahead` dni -- czyli ile z oceny opadu to
    prognoza, nie obserwacja. 0 dla wyjazdu dzisiaj."""
    if days_ahead <= 0:
        return 0.0
    ages = np.arange(window)               # 0 = dzien wyjazdu
    weights = 0.5 ** (ages / half_life_days)
    return float(weights[: min(days_ahead, window)].sum() / weights.sum())


def compute_weather_features(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Each window is `.iloc[-N:]` on `group`, sorted chronologically --
    i.e. it ends on whatever the LAST row of `daily_df` is, not "today".
    That's what makes plan 2.1 step A3 ("okna liczone do dnia wyjazdu")
    work with no extra "end date" parameter here: the caller just needs to
    have fetched data ending on the trip date (orchestrate.run_poc's
    forecast_days), and every window below follows automatically.

    P1/P3/P7/P14/P21/P30 and dry_spell_days (plan 2.1 step C2, spec §5.4
    "Zmiany w F (2.1)") were removed: never fed into F (spec §14 rejects
    them as features -- redundant with P26w/CWB26), dead weight kept only
    for a table nobody read. days_since_p10 stays -- it's the one dead-to-F
    window feature spec §5.4 explicitly keeps, for the regional banner
    ("ostatni opad >= 10 mm: X dni temu"), not as an F input.

    `et026w` (plan 1.5): the CWB26 window's evapotranspiration half, exposed
    separately from `cwb26` itself so a per-stand radar-precip override
    (orchestrate.run_poc) can recombine it with a stand-specific p26w
    instead of this weather point's own -- ET0/temperature/climatology are
    unaffected by Phase 1.5, only precipitation is."""
    rows = []
    for (lat, lon), group in daily_df.sort_values("date").groupby(["lat", "lon"]):
        p = group["precipitation_mm"]
        et0 = group["et0_mm"]
        tmean = group["tmean_c"]
        tmin = group["tmin_c"]
        et026w = _exp_weighted_sum(et0, window=min(26, len(et0)))
        precip_feat = precip_derived_features(p, group["radar_frac"] if "radar_frac" in group else None)
        rows.append({
            "lat": lat, "lon": lon, "date": group["date"].iloc[-1],
            "p5": precip_feat["p5"],
            "p26w": precip_feat["p26w"], "cwb26": precip_feat["p26w"] - et026w, "et026w": et026w,
            "tmean5": tmean.iloc[-5:].mean(), "tmean20": tmean.iloc[-20:].mean(),
            "tmin3": tmin.iloc[-3:].min(),
            "days_since_p10": precip_feat["days_since_p10"],
            "rain_radar_coverage": precip_feat["rain_radar_coverage"],
            # Faza 4.3: skladniki do prezentacji (nie wchodza do F): zwykla suma
            # opadu z 26 dni w mm oraz data najzimniejszej doby z ostatnich 3.
            "p26_sum": _rolling_sum(p, 26),
            "tmin3_date": _coldest_recent_day(group),
        })
    return pd.DataFrame(rows)


def fetch_climatology_raw(points: list[tuple[float, float]], start_year: int = 1991,
                            end_year: int = 2020, call_api=None,
                            cache_dir: Path | None = None) -> pd.DataFrame:
    """Same shape/DI pattern as fetch_weather_raw but against the ERA5-Land
    archive for a fixed historical period. Real network call isolated in
    call_api for testability; default implementation calls Open-Meteo's
    historical-weather-api and then reuses compute_weather_features'
    windowing helpers day by day (implemented alongside the manual
    verification step, not unit tested).

    Note: the returned "soil_moisture" column is sourced from the archive
    API's soil_moisture_7_to_28cm depth bin, which differs slightly from
    fetch_weather_raw's live soil_moisture (forecast API's
    soil_moisture_9_to_27cm bin) -- the archive API does not expose the same
    9-27cm bin. A percentile_rank comparison of live vs. climatology
    soil_moisture is therefore depth-approximate, not an exact apples-to-apples
    match."""
    call_api = call_api or _default_climatology_call
    if cache_dir is None:
        results = call_api(points, start_year, end_year)
    else:
        # Scoped to the year range + format version (plan 1.8e) -- a fixed
        # None suffix (pre-1.8e) let a cached point survive a start_year/
        # end_year change silently, serving the WRONG period's archive as
        # if it were the requested one. A cached point still IS reused
        # indefinitely across searches and days for the SAME range, since
        # the 30-year archive itself never changes once fetched.
        results = _fetch_with_point_cache(
            points, Path(cache_dir) / "climatology_points", f"{start_year}_{end_year}_v1",
            lambda pts: call_api(pts, start_year, end_year),
        )
    frames = [_point_frame(data, lat, lon) for (lat, lon), data in zip(points, results)]
    return pd.concat(frames, ignore_index=True)


def _parse_climatology_response(response) -> dict:
    daily = response.Daily()
    dates = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left",
    )
    precipitation = daily.Variables(0).ValuesAsNumpy()
    et0 = daily.Variables(1).ValuesAsNumpy()

    hourly = response.Hourly()
    soil = hourly.Variables(0).ValuesAsNumpy()
    soil_daily = pd.Series(soil).groupby(np.arange(len(soil)) // 24).mean().to_numpy()
    soil_daily = soil_daily[: len(dates)]

    precip_series = pd.Series(precipitation)
    et0_series = pd.Series(et0)

    n = len(dates)
    window = 26
    cwb26 = np.full(n, np.nan)
    for i in range(window - 1, n):
        p_tail = precip_series.iloc[i - window + 1: i + 1]
        et0_tail = et0_series.iloc[i - window + 1: i + 1]
        p26w = _exp_weighted_sum(p_tail, window=window)
        et026w = _exp_weighted_sum(et0_tail, window=window)
        cwb26[i] = p26w - et026w

    valid = ~np.isnan(cwb26)
    return {
        "date": dates[valid],
        "cwb26": cwb26[valid],
        # NOTE: 7-28cm depth bin, not the 9-27cm bin used by fetch_weather_raw's
        # live soil_moisture -- see fetch_climatology_raw's docstring.
        "soil_moisture": soil_daily[valid],
    }


def _default_climatology_call(points: list[tuple[float, float]], start_year: int, end_year: int) -> list[dict]:
    """Thin IO boundary around the real Open-Meteo historical-weather archive
    API. Not covered by unit tests (network); exercised manually.

    Batches points into requests of _OPEN_METEO_CLIMATOLOGY_BATCH_SIZE (much
    smaller than _default_open_meteo_call's, see that constant's comment) --
    this is the fetcher that actually failed live twice: first with "Hourly
    API request limit exceeded" one-point-per-request (fixed by batching),
    then, once orchestrate.run_poc started fetching climatology on a coarser
    grid (fewer, but still batched, points) at the original 50-point batch
    size, with "Your API call requests too much data" -- Open-Meteo's
    per-request data-volume guard, distinct from the request-count quota.
    Returns one dict per point, same order as `points`."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo_archive", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    results = []
    for chunk in _chunked(points, _OPEN_METEO_CLIMATOLOGY_BATCH_SIZE):
        responses = client.weather_api(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": [lat for lat, lon in chunk],
                "longitude": [lon for lat, lon in chunk],
                "start_date": f"{start_year}-01-01",
                "end_date": f"{end_year}-12-31",
                "daily": ["precipitation_sum", "et0_fao_evapotranspiration"],
                # Archive API depth bins differ from the forecast API's soil_moisture_9_to_27cm;
                # soil_moisture_7_to_28cm is the closest match available for the historical archive.
                "hourly": ["soil_moisture_7_to_28cm"],
                "timezone": "Europe/Warsaw",
            },
        )
        results.extend(_parse_climatology_response(r) for r in responses)
    return results


_OPEN_METEO_ARCHIVE_DAILY_BATCH_SIZE = 30  # lighter per-point weight than the
# 30-year climatology pull (one calendar year, same variable set as the live
# forecast call) -- see _OPEN_METEO_CLIMATOLOGY_BATCH_SIZE's docstring for the
# weight formula this is scaled down from. Conservative guess, same caveat.


def _default_archive_daily_call(points: list[tuple[float, float]], start_date: str, end_date: str) -> list[dict]:
    """Archive API pull for an arbitrary date range with the same variable
    set/order as _default_open_meteo_call's live forecast (so
    _parse_open_meteo_response can be reused as-is) -- for backtesting
    scoring against a specific historical period, not for the 30-year
    climatology baseline (_default_climatology_call), which only needs
    precipitation+ET0+soil_moisture."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo_archive_daily", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    results = []
    for chunk in _chunked(points, _OPEN_METEO_ARCHIVE_DAILY_BATCH_SIZE):
        responses = client.weather_api(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": [lat for lat, lon in chunk],
                "longitude": [lon for lat, lon in chunk],
                "start_date": start_date,
                "end_date": end_date,
                "daily": ["precipitation_sum", "temperature_2m_mean", "temperature_2m_min",
                           "temperature_2m_max", "et0_fao_evapotranspiration"],
                "hourly": ["soil_moisture_7_to_28cm"],
                "timezone": "Europe/Warsaw",
            },
        )
        results.extend(_parse_open_meteo_response(r) for r in responses)
    return results


def fetch_archive_daily(points: list[tuple[float, float]], start_date: str, end_date: str,
                          call_api=None, cache_dir: Path | None = None) -> pd.DataFrame:
    """Daily weather series for an arbitrary past [start_date, end_date]
    range -- e.g. a full calendar year, for reconstructing what
    compute_weather_features would have seen on any past day (backtesting).
    Same DI/caching shape as fetch_weather_raw/fetch_climatology_raw."""
    call_api = call_api or _default_archive_daily_call
    if cache_dir is None:
        results = call_api(points, start_date, end_date)
    else:
        results = _fetch_with_point_cache(
            points, Path(cache_dir) / "archive_daily_points",
            f"{start_date}_{end_date}",
            lambda pts: call_api(pts, start_date, end_date),
        )
    frames = []
    for (lat, lon), data in zip(points, results):
        df = pd.DataFrame(data)
        df["lat"] = lat
        df["lon"] = lon
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def climatology_window_values(clim_df: pd.DataFrame, lat: float, lon: float, day_of_year: int,
                                column: str, window_days: int = 15) -> np.ndarray:
    at_point = clim_df[(clim_df["lat"] == lat) & (clim_df["lon"] == lon)].copy()
    doy = at_point["date"].dt.dayofyear
    diff = (doy - day_of_year).abs()
    wrapped_diff = np.minimum(diff, 365 - diff)
    mask = wrapped_diff <= window_days
    return at_point.loc[mask, column].to_numpy()


def percentile_rank(value: float, historical_values: np.ndarray) -> float:
    """Plan 1.8d: NaN entries in `historical_values` (a real but incomplete
    climatology window, distinct from a genuinely empty one) are dropped
    before ranking -- scipy's percentileofscore has no defined "ignore NaN"
    behaviour, so leaving them in silently corrupts the rank. A window that
    is empty either originally or after dropping NaNs falls back to the
    same neutral 0.5 either way."""
    valid = historical_values[~np.isnan(historical_values)]
    if len(valid) == 0:
        return 0.5
    return float(stats.percentileofscore(valid, value, kind="mean") / 100.0)


# Plan wdrozenia 1.7: "mniej niz 50% waznych wartosci w oknie" (spec:
# empty_or_thin_climatology confidence reason) -- shared threshold so
# pipeline.orchestrate's per-point cache and any direct caller agree on
# what "thin" means.
MIN_VALID_FRACTION = 0.5


def climatology_window_insufficient(historical_values: np.ndarray) -> bool:
    """True when the window is empty, or fewer than MIN_VALID_FRACTION of
    its entries are non-NaN -- the trigger for plan 1.7's
    empty_or_thin_climatology confidence reason (percentile_rank's own 0.5
    fallback happens either way; this is only about whether to say so)."""
    if len(historical_values) == 0:
        return True
    valid_fraction = np.count_nonzero(~np.isnan(historical_values)) / len(historical_values)
    return bool(valid_fraction < MIN_VALID_FRACTION)
