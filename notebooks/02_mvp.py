"""Faza 2 MVP backend: legal mask (GDOŚ + zakazy wstępu), presja (OSM),
confidence, explanations, export -- built on top of Faza 1's run_poc for the
same Kieleczka tile."""
import functools
import pathlib
from datetime import date

import geopandas as gpd
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl, save_bdl_tile
from pipeline.confidence import compute_confidence  # noqa: F401 (re-exported for notebook debugging)
from pipeline.export import write_scores_json, export_stand_geometries
from pipeline.gdos import fetch_protected_areas
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.orchestrate import run_poc
from pipeline.osm import fetch_osm_features
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw,
    _default_open_meteo_call, _default_climatology_call,
)
from pipeline.zakazy import check_periodic_ban

LAT, LON = 50.526944, 18.605000
LAYER = "BDL:RDLP_Katowice_wydzielenia"


def _rate_limited(default_call, *args, max_attempts=6, backoff_s=65, pace_s=2.0):
    import time
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return default_call(*args)
        except OpenMeteoRequestsError as exc:
            if "limit" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def _weather_call_api(points, past_days):
    return _rate_limited(_default_open_meteo_call, points, past_days)


def _climatology_call_api(points, start_year, end_year):
    return _rate_limited(_default_climatology_call, points, start_year, end_year)


profile = load_profile("profiles/boletus_edulis.yaml")
bbox = tile_bbox_2180(LAT, LON, size_km=10.0)

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
print(f"run_poc: {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing structural mask")

print("Fetching GDOŚ protected areas...")
gdos_gdf = fetch_protected_areas(bbox)
print(f"  {len(gdos_gdf)} protected-area features in tile")

print("Fetching OSM parking/roads/places (Overpass)...")
osm_features = fetch_osm_features(bbox, profile)
for name, gdf in osm_features.items():
    print(f"  {name}: {len(gdf)}")

print("Enriching with legal mask + presja + confidence + explanations...")
enriched = enrich_with_mvp_layers(
    scored, profile, gdos_gdf, osm_features,
    zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
)

out_dir = pathlib.Path("notebooks/output")
today = date.today().isoformat()
scores_path = write_scores_json(enriched, day=today, out_path=out_dir / f"scores_{today}.json")
stands_path = export_stand_geometries(enriched, out_dir / "stands_mvp.parquet")
print(f"Wrote {scores_path} and {stands_path}")

passing_full = enriched[enriched["mask_full"]]
print(
    f"mask_full passing: {len(passing_full)} / {len(enriched)}; "
    f"GDOŚ-blocked: {int(enriched['gdos_blocked'].sum())}; "
    f"periodic-ban checked: {int(enriched['periodic_ban_checked'].sum())}, "
    f"active bans found: {int(enriched['periodic_ban_active'].sum())}"
)
if len(passing_full):
    print(
        f"R_final (mask_full-passing): min {passing_full['R_final'].min():.1f} / "
        f"median {passing_full['R_final'].median():.1f} / max {passing_full['R_final'].max():.1f}"
    )

from pipeline.validate import rank_known_points, load_known_points

known_points_path = pathlib.Path("notebooks/known_points.yaml")
if known_points_path.exists():
    known_points = load_known_points(str(known_points_path))
    # rank_known_points (Faza 1, pipeline/validate.py) reads a column named
    # "R" -- alias R_final onto it for this re-validation run without
    # touching the Faza 1 module or its own tests.
    revalidation_frame = enriched.rename(columns={"R": "R_faza1", "R_final": "R"})
    validation = rank_known_points(revalidation_frame, known_points)
    print("Re-validation against R_final (legal mask + presja applied):")
    print(validation.to_string(index=False))
    good = validation[validation["label"] == "good"]
    if len(good) and good["rank_pct"].mean() < 70:
        print(
            "UWAGA: znane dobre miejsca średnio poniżej 70. percentyla po dodaniu "
            "maski prawnej i presji - sprawdź czy GDOŚ/zakazy wstępu/presja nie "
            "przycinają ich nadmiernie zanim pójdziesz dalej."
        )
else:
    print(f"Brak {known_points_path} - patrz notebooks/known_points.example.yaml (Faza 1).")

# Grouping disabled at user request: individual stand scores are the result.
