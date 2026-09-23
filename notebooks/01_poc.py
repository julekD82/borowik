"""Faza 1 PoC: fetch BDL + Open-Meteo for the Kieleczka tile, score, map."""
import functools
import time

import folium
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl
from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw,
    _default_open_meteo_call, _default_climatology_call,
)

LAT, LON = 50.526944, 18.605000
LAYER = "BDL:RDLP_Katowice_wydzielenia"  # confirmed in Task 3 Step 5 - update if GetCapabilities disagrees

# Open-Meteo's free tier enforces a per-minute request cap. run_poc's grid
# fetchers call one point after another with no pacing, which can burst past
# that cap (observed: "Minutely API request limit exceeded" on the archive
# API partway through a 9-point grid). Wrap the real call_api functions with
# a small delay + backoff-and-retry on that specific error, using
# fetch_weather_raw/fetch_climatology_raw's existing call_api injection point
# (no change to pipeline/weather.py needed).


def _rate_limited(default_call, *args, max_attempts=6, backoff_s=65, pace_s=2.0):
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return default_call(*args)
        except OpenMeteoRequestsError as exc:
            if "limit" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def _weather_call_api(lat, lon, past_days):
    return _rate_limited(_default_open_meteo_call, lat, lon, past_days)


def _climatology_call_api(lat, lon, start_year, end_year):
    return _rate_limited(_default_climatology_call, lat, lon, start_year, end_year)


profile = load_profile("profiles/boletus_edulis.yaml")
bbox = tile_bbox_2180(LAT, LON, size_km=10.0)

scored = run_poc(
    layer=LAYER,
    bbox_2180=bbox,
    profile=profile,
    bdl_fetcher=fetch_bdl,
    weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api),
    climatology_fetcher=functools.partial(fetch_climatology_raw, call_api=_climatology_call_api),
)

scored_wgs84 = scored.to_crs("EPSG:4326")
m = folium.Map(location=[LAT, LON], zoom_start=12, tiles="OpenStreetMap")


def _color(r: float) -> str:
    if r >= 40:
        return "#1a9850"
    if r >= 20:
        return "#91cf60"
    if r >= 5:
        return "#fee08b"
    return "#999999"


folium.GeoJson(
    scored_wgs84,
    style_function=lambda feat: {
        "fillColor": _color(feat["properties"]["R"]),
        "color": "black", "weight": 0.5, "fillOpacity": 0.6,
    },
    tooltip=folium.GeoJsonTooltip(fields=["stand_id", "site_type", "species_cd", "spec_age", "H", "F_loc", "R"]),
).add_to(m)

import pathlib
out_dir = pathlib.Path("notebooks/output")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "poc_map.html"
m.save(str(out_path))
print(f"Saved {out_path}, {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing mask")

import pathlib
from pipeline.validate import rank_known_points, load_known_points

known_points_path = pathlib.Path("notebooks/known_points.yaml")
if known_points_path.exists():
    known_points = load_known_points(str(known_points_path))
    validation = rank_known_points(scored, known_points)
    print(validation.to_string(index=False))
    good = validation[validation["label"] == "good"]
    if len(good) and good["rank_pct"].mean() < 70:
        print(
            "UWAGA: znane dobre miejsca średnio poniżej 70. percentyla - "
            "przejrzyj S_site/S_host w profiles/boletus_edulis.yaml przed Fazą 2 "
            "(spec sekcja 9, krok 7)."
        )
else:
    print(f"Brak {known_points_path} - skopiuj notebooks/known_points.example.yaml i uzupełnij 10-20 znanych miejsc.")
