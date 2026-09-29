"""Faza 4: wspolne funkcje skryptow analitycznych (tylko z cache; API tylko tam,
gdzie skrypt to wprost mowi). Odtwarza ten sam przeplyw pogody co
pipeline.prepare_trip.run_trip_preparation do run_poc wlacznie, ale bez OSM/GDOS/
zakazow -- do porownan wartosci F/R miedzy wariantami pogody.
"""
import functools
import pathlib
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import geopandas as gpd  # noqa: E402

from pipeline.bdl import fetch_bdl  # noqa: E402
from pipeline.bdl_packages import load_packages  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402
from pipeline.orchestrate import (  # noqa: E402
    run_poc, DEFAULT_PAST_DAYS, CLIMATOLOGY_GRID_SPACING_M,
)
from pipeline.prepare_trip import (  # noqa: E402
    _radius_scaled_spacing, weather_grid_spacing_m, build_weather_fetcher,
    nearest_weather_point_per_stand, radar_mode,
)
from pipeline.radar import stand_radar_precip_daily  # noqa: E402
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer  # noqa: E402
from pipeline.search_area import search_tiles, fetch_search_stands, within_radius  # noqa: E402
from pipeline.tiles import tile_bbox_2180  # noqa: E402
from pipeline.weather import fetch_weather_raw, fetch_climatology_raw, make_grid  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
KIELECZKA = (50.5269, 18.605)
RADIUS_KM = 25.0
PROFILE_PATH = ROOT / "profiles" / "boletus_edulis.yaml"


class ApiForbidden(RuntimeError):
    """Rzucany, gdy skrypt 'tylko z cache' chce wywolac API."""


def _no_api(*_a, **_k):
    raise ApiForbidden("brak w cache -- ten skrypt nie wywoluje API")


def load_stands(lat=KIELECZKA[0], lon=KIELECZKA[1], radius_km=RADIUS_KM):
    center, tiles = search_tiles(lat, lon, radius_km)
    rdlp = fetch_rdlp_boundaries_cached(CACHE)
    layer = resolve_rdlp_layer(lat, lon, rdlp)
    context, _ = fetch_search_stands(tiles, rdlp, CACHE, fetch_bdl)
    stands = within_radius(context, center, radius_km)
    stands["stand_id"] = stands["adr_for"] + "@" + stands["a_year"].astype(str)
    return layer, stands


def score_with_grid(stands, layer, profile, *, temp_grid_km=None, target_date=None,
                    radius_km=RADIUS_KM, lat=KIELECZKA[0], lon=KIELECZKA[1],
                    weather_call_api=_no_api, package_dir=None, use_radar=True):
    """Odpowiednik run_trip_preparation od siatki pogodowej do run_poc; zwraca
    (scored, liczba_punktow_siatki, grid_spacing_m)."""
    profile = dict(profile)
    profile["weather"] = {**(profile.get("weather") or {}), "temp_grid_km": temp_grid_km}
    bbox = tile_bbox_2180(lat, lon, size_km=2 * radius_km)
    grid_spacing_m = weather_grid_spacing_m(profile, radius_km)
    clim_spacing_m = _radius_scaled_spacing(CLIMATOLOGY_GRID_SPACING_M, radius_km)
    grid_points = make_grid(bbox, spacing_m=grid_spacing_m)
    raw = functools.partial(fetch_weather_raw, call_api=weather_call_api, cache_dir=CACHE)
    weather_fetcher = build_weather_fetcher(
        raw, use_radar=use_radar, profile=profile, grid_spacing_m=grid_spacing_m, cache_dir=CACHE)
    clim_fetcher = functools.partial(fetch_climatology_raw, call_api=_no_api, cache_dir=CACHE)
    stand_precip = None
    if radar_mode(profile, use_radar) == "stand":
        fd = max(1, ((target_date or date.today()) - date.today()).days + 1)
        base_daily = raw(grid_points, DEFAULT_PAST_DAYS, forecast_days=fd)
        nearest = nearest_weather_point_per_stand(stands, grid_points)
        stand_precip = stand_radar_precip_daily(
            stands, nearest, base_daily, smoothing_km=profile["radar"].get("smoothing_km", 0),
            window_days=profile["radar"]["window_days"], cache_dir=CACHE / "radar_grs")
    package_index = load_packages(pathlib.Path(package_dir) if package_dir else CACHE / "bdl_packages")
    scored = run_poc(
        layer=layer, bbox_2180=bbox, profile=profile,
        bdl_fetcher=lambda _l, _b: stands.copy(), weather_fetcher=weather_fetcher,
        climatology_fetcher=clim_fetcher, grid_spacing_m=grid_spacing_m,
        climatology_grid_spacing_m=clim_spacing_m, target_date=target_date,
        package_index=package_index, stand_precip_daily=stand_precip)
    return scored, len(grid_points), grid_spacing_m


def open_meteo_weight(n_points, past_days, forecast_days, n_variables=6):
    """Koszt wywolania wg wzoru Open-Meteo: punkty x (dni/14) x (zmienne/10)
    (docs/CODEX-HANDOFF.md). 5 zmiennych dziennych + 1 godzinowa (gleba)."""
    return n_points * ((past_days + forecast_days) / 14.0) * (n_variables / 10.0)
