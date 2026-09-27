"""Plan A1 Task 7: RainGRS vs Open-Meteo vs independent Weathercloud stations.
Station data: cache/stations/weathercloud_2026-09.yaml (gitignored -- private
station locations). Run: .venv/Scripts/python.exe notebooks/04_radar_vs_stations.py"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

import pipeline.radar as radar
from pipeline.weather import _default_open_meteo_call

STATIONS = yaml.safe_load(Path("cache/stations/weathercloud_2026-09.yaml").read_text(encoding="utf-8"))["stations"]
FIRST, LAST = date(2026, 8, 29), date(2026, 9, 26)
FULL_FROM, FULL_TO = date(2026, 9, 13), date(2026, 9, 23)  # archive days with all 24 hours


def radar_daily(points, shift_hours: int) -> pd.DataFrame:
    start = datetime(2026, 8, 28, 22, tzinfo=timezone.utc)
    end = datetime(2026, 9, 26, 22, tzinfo=timezone.utc)
    hourly = radar.radar_hourly_at_points(points, 0, start, end, Path("cache/radar_grs"))
    hourly["hour_end_utc"] = hourly["hour_end_utc"] + pd.Timedelta(hours=shift_hours)
    return radar.radar_daily_at_points(hourly)


def main():
    names = list(STATIONS)
    points = [(STATIONS[n]["lat"], STATIONS[n]["lon"]) for n in names]
    om = _default_open_meteo_call(points, past_days=(date.today() - FIRST).days, forecast_days=1)
    for shift, label in [(0, "znacznik = koniec godziny"), (1, "znacznik = poczatek godziny")]:
        rd = radar_daily(points, shift)
        print(f"\n### {label}")
        for name, (lat, lon), om_point in zip(names, points, om):
            obs = {date.fromisoformat(str(k)): v for k, v in STATIONS[name]["daily_mm"].items()}
            om_by_day = {pd.Timestamp(t).tz_convert("Europe/Warsaw").date(): float(v)
                         for t, v in zip(om_point["date"], om_point["precipitation_mm"])}
            r = rd[(rd["lat"] == lat) & (rd["lon"] == lon)].set_index("local_date")
            rows = []
            d = FULL_FROM
            while d <= FULL_TO:
                rows.append((obs.get(d, 0.0), float(r["radar_mm"].get(d, 0.0)), om_by_day.get(d, float("nan"))))
                d += timedelta(days=1)
            df = pd.DataFrame(rows, columns=["obs", "radar", "om"])
            print(f"{name:20s} 13-23.09 suma obs={df.obs.sum():5.1f} radar={df.radar.sum():5.1f} "
                  f"OM={df.om.sum():5.1f} | MAE radar={(df.radar - df.obs).abs().mean():.2f} "
                  f"OM={(df.om - df.obs).abs().mean():.2f}")


if __name__ == "__main__":
    main()
