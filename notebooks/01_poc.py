"""Faza 1 PoC: fetch BDL + Open-Meteo for the Kieleczka tile, score, map."""
import functools
import pathlib
import time

import folium
import geopandas as gpd
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl, save_bdl_tile
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

# Read-through GeoParquet cache for the BDL tile (plan Global Constraints:
# "Faza 1 storage is GeoParquet files under cache/"). Kept here in the
# notebook script rather than inside run_poc, which stays pure/DI-testable.
CACHE_DIR = pathlib.Path("cache")
TILE_ID = f"E{int(bbox[1])}N{int(bbox[0])}"
_tile_path = CACHE_DIR / f"{TILE_ID}.parquet"


def _cached_bdl_fetcher(layer, bbox_2180):
    if _tile_path.exists():
        print(f"BDL tile cache hit: {_tile_path}")
        return gpd.read_parquet(_tile_path)
    print(f"BDL tile cache miss, fetching from WFS -> {_tile_path}")
    gdf = fetch_bdl(layer, bbox_2180)
    save_bdl_tile(gdf, TILE_ID, CACHE_DIR)
    return gdf


scored = run_poc(
    layer=LAYER,
    bbox_2180=bbox,
    profile=profile,
    bdl_fetcher=_cached_bdl_fetcher,
    weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api),
    climatology_fetcher=functools.partial(fetch_climatology_raw, call_api=_climatology_call_api),
)

scored_wgs84 = scored.to_crs("EPSG:4326")
# Folium's "OpenStreetMap" tile alias hits tile.openstreetmap.org, which
# actively 403s app traffic that doesn't follow its volunteer-run usage
# policy (osm.wiki/Blocked); the "CartoDB positron" alias now requires an
# API key too. Esri's World Street Map tile service is free, keyless, and
# was verified reachable during Faza 1 development.
m = folium.Map(
    location=[LAT, LON], zoom_start=12,
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, HERE, Garmin, FAO, NOAA, USGS, &copy; OpenStreetMap contributors, and the GIS User Community",
)


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

out_dir = pathlib.Path("notebooks/output")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "poc_map.html"
m.save(str(out_path))
diag = scored.attrs.get("diagnostics", {})
print(
    f"Saved {out_path}, {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing mask; "
    f"unknown site_type (mask-passing): {diag.get('unknown_site_count')}, "
    f"unknown species_cd (mask-passing): {diag.get('unknown_species_count')}, "
    f"empty climatology windows: {diag.get('empty_climatology_count')}, "
    f"non-finite H: {diag.get('nan_h_count')}"
)

passing = scored[scored["mask"]]
if len(passing):
    print(
        f"R (mask-passing): min {passing['R'].min():.1f} / "
        f"median {passing['R'].median():.1f} / max {passing['R'].max():.1f}"
    )
    by_site = (
        passing.groupby("site_type")["R"]
        .agg(["count", "median", "max"])
        .sort_values("median", ascending=False)
    )
    print("R by site_type (mask-passing, median desc):")
    print(by_site.to_string())

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
