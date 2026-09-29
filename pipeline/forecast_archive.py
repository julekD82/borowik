"""Plan 2.2: archiwum prognoz z data wydania.

Kazde pobranie pogody z Open-Meteo zapisuje surowe prognozy dobowe (od dnia
pobrania wzwyz) z data i godzina pobrania. Jeden plik na dzien pobrania:
`prognoza_YYYY-MM-DD.parquet`. Zapis jest tylko-dopisujacy -- wiersze
istniejacych punktow nigdy nie sa nadpisywane (drugi przebieg tego samego
dnia dopisuje co najwyzej nowe punkty), a archiwum lezy poza cache pogodowym,
wiec czyszczenie `cache/weather_points` go nie dotyka.
"""
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ARCHIVE_DIRNAME = "archiwum_prognoz"
KEY_COLUMNS = ["lat", "lon", "date"]
KEPT_COLUMNS = ["lat", "lon", "date", "precipitation_mm", "tmean_c", "tmin_c", "tmax_c", "et0_mm",
                "fetched_at", "forecast_days"]


def archive_path(cache_dir: Path, fetch_day: date) -> Path:
    return Path(cache_dir) / ARCHIVE_DIRNAME / f"prognoza_{fetch_day.isoformat()}.parquet"


def archive_forecast(daily_df: pd.DataFrame, cache_dir: Path, forecast_days: int,
                     now: datetime | None = None) -> Path | None:
    """Zapisz wiersze prognozy (date >= dzien pobrania, czas lokalny) z ramki
    `fetch_weather_raw`. Zwraca sciezke pliku albo None, gdy nie ma czego
    zapisac (np. forecast_days=1 daje tylko dzis -- to tez prognoza i jest zapisywane)."""
    now = now or datetime.now(timezone.utc)
    fetch_day = now.astimezone().date()
    if daily_df is None or daily_df.empty:
        return None
    local_dates = pd.to_datetime(daily_df["date"], utc=True)
    local_dates = (local_dates + pd.Timedelta(hours=12)).dt.tz_convert("Europe/Warsaw").dt.date
    rows = daily_df.loc[local_dates >= fetch_day].copy()
    if rows.empty:
        return None
    rows["fetched_at"] = now.isoformat()
    rows["forecast_days"] = int(forecast_days)
    rows = rows[[c for c in KEPT_COLUMNS if c in rows.columns]]

    path = archive_path(cache_dir, fetch_day)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        known_points = set(zip(existing["lat"].round(6), existing["lon"].round(6)))
        is_new = [(la, lo) not in known_points for la, lo in zip(rows["lat"].round(6), rows["lon"].round(6))]
        rows = rows.loc[is_new]
        if rows.empty:
            return path
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        combined = rows.reset_index(drop=True)
    temp = path.with_suffix(".tmp.parquet")
    combined.to_parquet(temp)
    temp.replace(path)
    return path
