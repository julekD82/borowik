import math

import numpy as np
import pandas as pd
from pyproj import Transformer

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
