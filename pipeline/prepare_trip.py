import argparse
import functools
import math
import pathlib
import sys
import time
from datetime import date, timedelta

import geopandas as gpd
import requests
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl
from pipeline.bdl_dictionaries import load_dictionaries
from pipeline.bdl_package_details import load_package_details
from pipeline.bdl_packages import load_packages
from pipeline.entrances import compute_forest_boundary, find_entrance_points, classify_entrances
from pipeline.export import (
    write_scores_json, export_stand_geometries, export_stand_geometries_geojson,
    write_regions_json, write_details_json,
)
from pipeline.gdos import fetch_protected_areas
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.neighbors import find_neighbor_labels
from pipeline.orchestrate import run_poc, WEATHER_GRID_SPACING_M, CLIMATOLOGY_GRID_SPACING_M
from pipeline.osm import fetch_osm_features, _default_overpass_call
from pipeline.rdlp import (
    fetch_rdlp_boundaries_cached, resolve_rdlp_layer,
)
from pipeline.regions import group_into_regions
from pipeline.search_area import (
    search_tiles, fetch_search_stands, within_radius,
    fetch_cached_gdos, fetch_cached_osm,
)
from pipeline.tie_break import load_tie_break_raw, tie_break_for_stand
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw, make_grid,
    _default_open_meteo_call, _default_climatology_call,
    _OPEN_METEO_BATCH_SIZE, _OPEN_METEO_CLIMATOLOGY_BATCH_SIZE,
)
from pipeline.zakazy import check_periodic_ban

MIN_RADIUS_KM = 10.0
MAX_RADIUS_KM = 50.0

# WEATHER_GRID_SPACING_M/CLIMATOLOGY_GRID_SPACING_M (orchestrate.py) are
# defined at this radius -- the CLI's own default (--radius-km above).
REFERENCE_RADIUS_KM = 25.0


def _radius_scaled_spacing(base_spacing_m: float, radius_km: float) -> float:
    """Scale a grid spacing linearly with the search radius, so total
    point count (and so API cost/weight -- see docs/CODEX-HANDOFF.md for
    the Open-Meteo weighting derivation) stays roughly constant across the
    whole 10-50km CLI range instead of growing with the search area: a
    15km search gets a finer grid than the 25km-reference spacing rather
    than the same fixed spacing "wasting" its point budget over less
    ground. User request 2026-09-24."""
    return base_spacing_m * radius_km / REFERENCE_RADIUS_KM


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prepare_trip",
        description="Przygotuj wyjazd: ocen wydzielenia do poszukiwan prawdziwkow dla podanej lokalizacji.",
    )
    parser.add_argument("--lat", type=float, required=True, help="Szerokosc geograficzna (WGS84)")
    parser.add_argument("--lon", type=float, required=True, help="Dlugosc geograficzna (WGS84)")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Etykieta dnia w nazwach plikow wynikowych (YYYY-MM-DD), domyslnie dzisiaj. "
             "Nie zmienia okna pogodowego (zawsze 'teraz' -- patrz docs/projekt-borowik.md).",
    )
    parser.add_argument(
        "--radius-km", type=float, default=25.0,
        help=f"Promien analizy ({MIN_RADIUS_KM:.0f}-{MAX_RADIUS_KM:.0f} km, domyslnie 25). "
             "Wiele kafli 10x10 km; wybierane sa wydzielenia ze srodkiem w promieniu.",
    )
    parser.add_argument("--profile", type=str, default="profiles/boletus_edulis.yaml")
    parser.add_argument("--out-dir", type=str, default="notebooks/output")
    parser.add_argument("--cache-dir", type=str, default="cache")
    args = parser.parse_args(argv)
    if not (math.isfinite(args.lat) and -90 <= args.lat <= 90 and
            math.isfinite(args.lon) and -180 <= args.lon <= 180):
        parser.error("--lat/--lon must be finite WGS84 coordinates")
    if not (MIN_RADIUS_KM <= args.radius_km <= MAX_RADIUS_KM):
        parser.error(f"--radius-km must be between {MIN_RADIUS_KM:.0f} and {MAX_RADIUS_KM:.0f}")
    if args.date is not None:
        try:
            parsed_date = date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"--date must be YYYY-MM-DD, got {args.date!r}")
        else:
            # Plan 2.1 step A3, user decision 2026-09-24: --date now drives
            # the actual weather fetch (past + forecast through that day),
            # so it must be resolvable to a real Open-Meteo forecast_days
            # value -- abort with a clear error instead of silently
            # computing for today, which would show numbers labelled with a
            # --date they don't actually reflect.
            today = date.today()
            if parsed_date < today:
                parser.error(
                    f"--date {args.date} jest w przeszlosci -- prognoza Open-Meteo "
                    f"dziala tylko od dzisiaj ({today.isoformat()})."
                )
            forecast_days_needed = (parsed_date - today).days + 1
            if forecast_days_needed > 16:
                parser.error(
                    f"--date {args.date} jest za daleko w przyszlosci -- Open-Meteo "
                    f"daje prognoze maks. 16 dni od dzisiaj (do "
                    f"{(today + timedelta(days=15)).isoformat()})."
                )
    return args


class TripPreparationError(RuntimeError):
    """Raised for a known, clean failure (currently: point outside every
    RDLP) that main() turns into a one-line CLI error instead of a
    traceback. Not raised for network/API errors, which are out of this
    plan's scope (spec §13 priority 8) and still surface as-is."""


def _is_open_meteo_rate_limit(exc: Exception) -> bool:
    # Distinct from the per-request data-volume error ("Your API call
    # requests too much data") -- that one is not transient and retrying it
    # unchanged just fails again; see docs/CODEX-HANDOFF.md.
    return isinstance(exc, OpenMeteoRequestsError) and "limit" in str(exc).lower()


def _is_overpass_retryable(exc: Exception) -> bool:
    # 429/406: overpass-api.de's own usage policy (wiki.openstreetmap.org/
    # wiki/Overpass_API) -- "If you receive an HTTP error code such as 429
    # or 406, pause for 30 seconds before making a new request." 504: the
    # Overpass API author's own guidance (olbricht.nrw/command_line.html)
    # -- "sent if the server has already so much load that the request
    # cannot be executed... in most cases, it is best to try again later"
    # -- observed live 2026-09-24 on tile 1/30 of a real 25km-radius run,
    # despite the same query succeeding earlier in isolated testing (see
    # profiles/boletus_edulis.yaml's routing_highway_types comment): the
    # public instance's own load varies, not just our query's shape.
    return (
        isinstance(exc, requests.exceptions.HTTPError)
        and exc.response is not None
        and exc.response.status_code in (429, 406, 504)
    )


def _is_transient_network_error(exc: Exception) -> bool:
    # GDOS (sdi.gdos.gov.pl) has no documented rate-limit policy like
    # Overpass or Open-Meteo -- a live run hit requests.exceptions.
    # ConnectionError (a urllib3 ProtocolError underneath, no HTTP status
    # at all) mid-run, tile 18/30. Matches the requests library's own
    # RequestException hierarchy broadly rather than a specific status
    # code, since there's no documented policy to be more specific about.
    return isinstance(exc, requests.exceptions.RequestException)


def _rate_limited(default_call, *args, should_retry, max_attempts=6, backoff_s=65, pace_s=2.0):
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return default_call(*args)
        except Exception as exc:
            if not should_retry(exc) or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def run_trip_preparation(lat: float, lon: float, day: str, radius_km: float,
                          profile_path: str, out_dir: pathlib.Path, cache_dir: pathlib.Path,
                          target_date: date | None = None) -> dict:
    """Analyze stands whose EPSG:2180 centroid lies within the search radius.

    Source queries use aligned 10 km tiles; scoring, pressure normalization
    and region grouping run once across the complete area, not per tile.
    Both the per-stand export and the region export are always written --
    the frontend toggles between them, this function doesn't choose.

    `target_date` (plan 2.1 step A3) defaults to today when omitted, same
    as before this step existed -- `main()` is the only caller that passes
    a parsed --date through, after parse_args has already validated it's
    neither in the past nor beyond Open-Meteo's 16-day forecast horizon."""
    center, tiles = search_tiles(lat, lon, radius_km)
    profile = load_profile(profile_path)
    bbox = tile_bbox_2180(lat, lon, size_km=2 * radius_km)
    cache_dir = pathlib.Path(cache_dir)

    print(f"Resolving RDLP for ({lat}, {lon})...")
    rdlp_gdf = fetch_rdlp_boundaries_cached(cache_dir)
    layer = resolve_rdlp_layer(lat, lon, rdlp_gdf)
    if layer is None:
        raise TripPreparationError(
            f"Punkt ({lat}, {lon}) nie lezy w zadnym RDLP (poza Polska?) -- BDL nie ma dla niego danych."
        )
    print(f"  RDLP layer: {layer}")
    print(f"Obszar: promien {radius_km:g} km, {len(tiles)} kafli 10x10 km.", flush=True)
    print("Pierwsza analiza duzego obszaru moze trwac dlugo (pogoda i klimatologia).", flush=True)
    context_stands, layers = fetch_search_stands(tiles, rdlp_gdf, cache_dir, fetch_bdl)
    stands = within_radius(context_stands, center, radius_km)
    if not len(stands):
        raise TripPreparationError("Brak wydzielen BDL w podanym promieniu. Poprzednie wyniki pozostawiono bez zmian.")

    # plan 2.1 step B2: auto-detected by adr_for, no config/CLI flag needed.
    # A missing cache/bdl_packages/ (or one with nothing usable in it)
    # gives {} -- every stand just falls back to the WFS panujący+part_cd
    # S_host, same as before this step existed.
    package_index = load_packages(cache_dir / "bdl_packages")
    if package_index:
        print(f"Paczki BDL: {len(package_index)} wydzielen z pelnym skladem gatunkowym.", flush=True)

    # Spacing scales with radius_km so total point count (API cost) stays
    # roughly constant across the whole 10-50km range instead of growing
    # with the search area -- a smaller radius gets a finer grid rather
    # than "wasting" the same point budget over less ground. See
    # _radius_scaled_spacing's own docstring.
    grid_spacing_m = _radius_scaled_spacing(WEATHER_GRID_SPACING_M, radius_km)
    climatology_grid_spacing_m = _radius_scaled_spacing(CLIMATOLOGY_GRID_SPACING_M, radius_km)
    point_count = len(make_grid(bbox, spacing_m=grid_spacing_m))
    climatology_point_count = len(make_grid(bbox, spacing_m=climatology_grid_spacing_m))
    print(
        f"Siatka pogodowa: {point_count} punktow (odstep {grid_spacing_m/1000:.1f} km), "
        f"pobierane partiami po {_OPEN_METEO_BATCH_SIZE} w jednym zapytaniu "
        "(nie jeden punkt na zapytanie).",
        flush=True,
    )
    print(
        f"Siatka klimatologii: {climatology_point_count} punktow "
        f"(odstep {climatology_grid_spacing_m/1000:.1f} km, rzadsza niz pogoda -- "
        "30 lat archiwum na punkt jest znacznie kosztowniejsze niz biezaca pogoda).",
        flush=True,
    )

    def _weather_call_api(points_, past_days, forecast_days=1):
        print(
            f"Pogoda: {len(points_)} punktow (partiami po {_OPEN_METEO_BATCH_SIZE}), "
            f"prognoza {forecast_days} dni",
            flush=True,
        )
        return _rate_limited(
            _default_open_meteo_call, points_, past_days, forecast_days, should_retry=_is_open_meteo_rate_limit,
        )

    def _climatology_call_api(points_, start_year, end_year):
        print(f"Klimatologia: {len(points_)} punktow (partiami po {_OPEN_METEO_CLIMATOLOGY_BATCH_SIZE})", flush=True)
        return _rate_limited(
            _default_climatology_call, points_, start_year, end_year, should_retry=_is_open_meteo_rate_limit,
        )

    def _osm_call_api(query):
        # overpass-api.de has no request-count DI seam like Open-Meteo's
        # client -- pace every call a little (not documented as required,
        # just defensive) and retry on the 429/406/504 the docs describe.
        return _rate_limited(
            _default_overpass_call, query, should_retry=_is_overpass_retryable, backoff_s=30, pace_s=1.0,
        )

    def _gdos_call_api(bbox):
        # No documented rate-limit policy for GDOS, unlike Overpass/Open-
        # Meteo -- just a couple of quick retries for a transient network
        # blip (ConnectionError, observed live 2026-09-24) before
        # fetch_cached_gdos's own fallback gives up on the tile entirely.
        return _rate_limited(
            fetch_protected_areas, bbox, should_retry=_is_transient_network_error,
            max_attempts=3, backoff_s=5, pace_s=0.5,
        )

    scored = run_poc(
        layer=layer, bbox_2180=bbox, profile=profile,
        bdl_fetcher=lambda _layer, _bbox: stands.copy(),
        weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api, cache_dir=cache_dir),
        climatology_fetcher=functools.partial(
            fetch_climatology_raw, call_api=_climatology_call_api, cache_dir=cache_dir,
        ),
        grid_spacing_m=grid_spacing_m,
        climatology_grid_spacing_m=climatology_grid_spacing_m,
        target_date=target_date,
        package_index=package_index,
    )
    print(
        f"run_poc: {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing structural mask, "
        f"{scored.attrs['diagnostics']['package_stand_count']} z paczki BDL"
    )

    gdos_gdf, gdos_failed_tiles = fetch_cached_gdos(tiles, cache_dir, _gdos_call_api)
    osm_features, osm_failed_tiles = fetch_cached_osm(
        tiles, cache_dir, profile, functools.partial(fetch_osm_features, call_api=_osm_call_api),
    )
    if gdos_failed_tiles:
        print(
            f"UWAGA: dane GDOS niedostepne dla {len(gdos_failed_tiles)}/{len(tiles)} kafli -- "
            "ochrona prawna (rezerwaty, parki narodowe) moze byc niepelna w tym obszarze. "
            "Wydzielenia w tych kaflach NIE sa oznaczone jako zablokowane z tego powodu.",
            flush=True,
        )
    if osm_failed_tiles:
        print(
            f"UWAGA: dane OSM niedostepne dla {len(osm_failed_tiles)}/{len(tiles)} kafli -- "
            "odleglosc do wejscia i szacunek popularnosci moga byc mniej dokladne w tym obszarze.",
            flush=True,
        )

    print("Detecting forest entrances...")
    # Keep surrounding forest: clipping the forest at the search circle would
    # create artificial entrances along that arbitrary boundary.
    forest_boundary = compute_forest_boundary(context_stands)
    raw_entrances = find_entrance_points(forest_boundary, osm_features["roads"])
    entrances = classify_entrances(raw_entrances, osm_features["parking"], profile["entrances"]["confirmed_tolerance_m"])
    confirmed_count = int((entrances["status"] == "confirmed").sum()) if len(entrances) else 0
    print(f"  {len(entrances)} candidate entrance(s), {confirmed_count} confirmed")

    print("Enriching with legal mask + presja + confidence + explanations...")
    enriched = enrich_with_mvp_layers(
        scored, profile, gdos_gdf, osm_features,
        zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
        roads_routing_gdf=osm_features["roads"], entrances_gdf=entrances,
        top_n_for_routing=profile["entrances"]["top_n_for_routing"],
    )

    # Plan 2.1 "Zmiana 4": must run before group_into_regions below --
    # pipeline.regions._summarize_cluster uses tie_break as a secondary
    # sort key for region member ordering. Reuses the same
    # cache/bdl_packages/ directory as load_packages/load_package_details
    # above; a stand whose adr_for isn't covered gets a neutral 0.5
    # (pipeline.tie_break.tie_break_for_stand).
    tie_break_raw_index = load_tie_break_raw(cache_dir / "bdl_packages")
    enriched["tie_break"] = [
        tie_break_for_stand(row["adr_for"], tie_break_raw_index) for _, row in enriched.iterrows()
    ]

    print("Grouping into search regions...")
    regions = group_into_regions(enriched, profile)

    # plan 2.1 step B3: card-detail data only (species composition, density,
    # podszyt, soil type from a BDL package; neighbours + stand_stru/
    # prot_categ from WFS) -- reads already-scored `enriched`/`context_stands`
    # and never feeds back into them, so this cannot change H/F/R (see
    # pipeline.bdl_package_details' module docstring for the structural
    # guarantee, and tests/test_prepare_trip.py for the explicit regression
    # check).
    print("Building wydzielenie detail cards (paczka BDL + sasiedztwo)...")
    dictionaries = load_dictionaries(cache_dir / "bdl_packages")
    package_details_index = load_package_details(cache_dir / "bdl_packages")
    neighbors_by_stand = {
        row["adr_for"]: find_neighbor_labels(row, context_stands, dictionaries)
        for _, row in enriched.iterrows()
    }

    out_dir = pathlib.Path(out_dir)
    scores_path = write_scores_json(enriched, day=day, out_path=out_dir / f"scores_{day}.json")
    stands_path = export_stand_geometries(enriched, out_dir / "stands_mvp.parquet")
    geojson_path = export_stand_geometries_geojson(enriched, out_dir / "stands.geojson")
    regions_path = write_regions_json(regions, day=day, out_path=out_dir / f"regions_{day}.json")
    details_path = write_details_json(
        enriched, package_details_index, neighbors_by_stand, dictionaries,
        day=day, out_path=out_dir / f"details_{day}.json",
    )
    print(f"  {len(regions)} region(s)")

    return {
        "layer": layer, "layers": layers, "tile_count": len(tiles),
        "radius_km": radius_km, "stand_count": len(scored),
        "mask_passing": int(enriched["mask_full"].sum()),
        "region_count": len(regions),
        "scores_path": scores_path, "stands_path": stands_path,
        "geojson_path": geojson_path, "regions_path": regions_path,
        "details_path": details_path,
        "gdos_failed_tile_count": len(gdos_failed_tiles),
        "osm_failed_tile_count": len(osm_failed_tiles),
        "forecast_days": scored.attrs["diagnostics"]["forecast_days"],
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    today = date.today()
    # parse_args already rejected a past date or one needing forecast_days
    # > 16, so fromisoformat here is always valid and in Open-Meteo's range.
    target_date = date.fromisoformat(args.date) if args.date else today
    day = args.date or today.isoformat()
    try:
        summary = run_trip_preparation(
            lat=args.lat, lon=args.lon, day=day, radius_km=args.radius_km,
            profile_path=args.profile, out_dir=pathlib.Path(args.out_dir), cache_dir=pathlib.Path(args.cache_dir),
            target_date=target_date,
        )
    except TripPreparationError as exc:
        print(f"Blad: {exc}")
        return 1
    print(
        "Gotowe: "
        f"{summary['mask_passing']}/{summary['stand_count']} wydzielen przechodzi maske, "
        f"{summary['region_count']} rejon(y)."
        + (f" Prognoza: {summary['forecast_days'] - 1} dni naprzod." if summary["forecast_days"] > 1 else "")
    )
    print(
        f"Wyniki: {summary['scores_path']}, {summary['stands_path']}, "
        f"{summary['geojson_path']}, {summary['regions_path']}, {summary['details_path']}"
    )
    if summary["gdos_failed_tile_count"] or summary["osm_failed_tile_count"]:
        print(
            f"Niepelne dane: GDOS pominiety dla {summary['gdos_failed_tile_count']} kafli, "
            f"OSM pominiety dla {summary['osm_failed_tile_count']} kafli z {summary['tile_count']}. "
            "Sprawdz logi wyzej."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
