import math

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import stats

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def make_grid(bbox_2180: tuple, spacing_m: float = 5000.0) -> list[tuple[float, float]]:
    n_min, e_min, n_max, e_max = bbox_2180
    n_steps = max(1, int(math.ceil((n_max - n_min) / spacing_m)))
    e_steps = max(1, int(math.ceil((e_max - e_min) / spacing_m)))
    points = []
    for i in range(n_steps + 1):
        n = min(n_min + i * spacing_m, n_max)
        for j in range(e_steps + 1):
            e = min(e_min + j * spacing_m, e_max)
            lon, lat = _TO_4326.transform(e, n)
            points.append((lat, lon))
    return points


def _default_open_meteo_call(lat: float, lon: float, past_days: int) -> dict:
    """Thin IO boundary around the real Open-Meteo archive+forecast API.
    Not covered by unit tests (network); exercised manually, see Task 6 Step 5."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    responses = client.weather_api(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": ["precipitation_sum", "temperature_2m_mean", "temperature_2m_min",
                       "temperature_2m_max", "et0_fao_evapotranspiration"],
            "hourly": ["soil_moisture_9_to_27cm"],
            "past_days": past_days,
            "forecast_days": 1,
            "timezone": "Europe/Warsaw",
        },
    )
    response = responses[0]
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


def fetch_weather_raw(points: list[tuple[float, float]], past_days: int = 92, call_api=None) -> pd.DataFrame:
    call_api = call_api or _default_open_meteo_call
    frames = []
    for lat, lon in points:
        data = call_api(lat, lon, past_days)
        df = pd.DataFrame(data)
        df["lat"] = lat
        df["lon"] = lon
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _rolling_sum(series: pd.Series, window: int) -> float:
    return series.iloc[-window:].sum()


def _exp_weighted_sum(series: pd.Series, window: int, half_life_days: float = 10.0) -> float:
    tail = series.iloc[-window:]
    n = len(tail)
    ages = np.arange(n - 1, -1, -1)
    weights = 0.5 ** (ages / half_life_days)
    return float((tail.to_numpy() * weights).sum())


def compute_weather_features(daily_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (lat, lon), group in daily_df.sort_values("date").groupby(["lat", "lon"]):
        p = group["precipitation_mm"]
        et0 = group["et0_mm"]
        tmean = group["tmean_c"]
        tmin = group["tmin_c"]
        p26w = _exp_weighted_sum(p, window=min(26, len(p)))
        et026w = _exp_weighted_sum(et0, window=min(26, len(et0)))
        at_or_above_10 = group[p >= 10.0]
        if len(at_or_above_10):
            last_p10_pos = group.index.get_indexer(at_or_above_10.index).max()
            days_since_p10 = (len(group) - 1) - last_p10_pos
        else:
            days_since_p10 = len(group)
        dry_mask = (p < 1.0).to_numpy()
        dry_spell = 0
        for is_dry in dry_mask[::-1]:
            if not is_dry:
                break
            dry_spell += 1
        rows.append({
            "lat": lat, "lon": lon, "date": group["date"].iloc[-1],
            "p1": _rolling_sum(p, 1), "p3": _rolling_sum(p, 3), "p7": _rolling_sum(p, 7),
            "p14": _rolling_sum(p, 14), "p21": _rolling_sum(p, 21), "p30": _rolling_sum(p, 30),
            "p26w": p26w, "cwb26": p26w - et026w,
            "tmean5": tmean.iloc[-5:].mean(), "tmean20": tmean.iloc[-20:].mean(),
            "tmin3": tmin.iloc[-3:].min(),
            "days_since_p10": days_since_p10, "dry_spell_days": dry_spell,
        })
    return pd.DataFrame(rows)


def fetch_climatology_raw(points: list[tuple[float, float]], start_year: int = 1991,
                            end_year: int = 2020, call_api=None) -> pd.DataFrame:
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
    call_api = call_api or (lambda lat, lon, sy, ey: _default_climatology_call(lat, lon, sy, ey))
    frames = []
    for lat, lon in points:
        data = call_api(lat, lon, start_year, end_year)
        df = pd.DataFrame(data)
        df["lat"] = lat
        df["lon"] = lon
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _default_climatology_call(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    """Thin IO boundary around the real Open-Meteo historical-weather archive API.
    Not covered by unit tests (network); exercised manually, see Task 7 Step 5."""
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry

    cache_session = requests_cache.CachedSession(".cache/open_meteo_archive", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    responses = client.weather_api(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{start_year}-01-01",
            "end_date": f"{end_year}-12-31",
            "daily": ["precipitation_sum", "et0_fao_evapotranspiration"],
            # Archive API depth bins differ from the forecast API's soil_moisture_9_to_27cm;
            # soil_moisture_7_to_28cm is the closest match available for the historical archive.
            "hourly": ["soil_moisture_7_to_28cm"],
            "timezone": "Europe/Warsaw",
        },
    )
    response = responses[0]
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


def climatology_window_values(clim_df: pd.DataFrame, lat: float, lon: float, day_of_year: int,
                                column: str, window_days: int = 15) -> np.ndarray:
    at_point = clim_df[(clim_df["lat"] == lat) & (clim_df["lon"] == lon)].copy()
    doy = at_point["date"].dt.dayofyear
    diff = (doy - day_of_year).abs()
    wrapped_diff = np.minimum(diff, 365 - diff)
    mask = wrapped_diff <= window_days
    return at_point.loc[mask, column].to_numpy()


def percentile_rank(value: float, historical_values: np.ndarray) -> float:
    if len(historical_values) == 0:
        return 0.5
    return float(stats.percentileofscore(historical_values, value, kind="mean") / 100.0)
