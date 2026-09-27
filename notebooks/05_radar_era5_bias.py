"""Plan A1 D1 check: is RainGRS systematically wetter/drier than the
Open-Meteo archive (ERA5) that the 1991-2020 climatology comes from? Sample:
2025-08-01..2025-09-30 on the Bedziemysl 20 km weather grid. ~61 archive
days (~5 GB download, ~15 min). Run: .venv/Scripts/python.exe notebooks/05_radar_era5_bias.py"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import pipeline.radar as radar
from pipeline.orchestrate import WEATHER_GRID_SPACING_M
from pipeline.prepare_trip import _radius_scaled_spacing
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import fetch_archive_daily, make_grid

LAT, LON, RADIUS_KM = 50.0555, 21.7889, 20.0


def main():
    spacing = _radius_scaled_spacing(WEATHER_GRID_SPACING_M, RADIUS_KM)
    points = make_grid(tile_bbox_2180(LAT, LON, size_km=2 * RADIUS_KM), spacing_m=spacing)
    era5 = fetch_archive_daily(points, "2025-08-01", "2025-09-30", cache_dir=Path("cache"))
    hourly = radar.radar_hourly_at_points(
        points, spacing / 2, datetime(2025, 7, 31, 22, tzinfo=timezone.utc),
        datetime(2025, 9, 30, 22, tzinfo=timezone.utc), Path("cache/radar_grs"))
    rd = radar.radar_daily_at_points(hourly)
    full = rd[rd["radar_hours"] == rd["expected_hours"]]
    era5["local_date"] = era5["date"].dt.tz_convert("Europe/Warsaw").dt.date
    joined = full.merge(era5[["lat", "lon", "local_date", "precipitation_mm"]], on=["lat", "lon", "local_date"])
    ratio = joined["radar_mm"].sum() / joined["precipitation_mm"].sum()
    print(f"punkty={len(points)} dni z pelnym radarem={joined['local_date'].nunique()} "
          f"suma radar={joined['radar_mm'].sum():.0f} ERA5={joined['precipitation_mm'].sum():.0f} "
          f"stosunek radar/ERA5={ratio:.3f}")
    per_point = joined.groupby(["lat", "lon"])[["radar_mm", "precipitation_mm"]].sum()
    print((per_point["radar_mm"] / per_point["precipitation_mm"]).describe().round(3))


if __name__ == "__main__":
    main()
