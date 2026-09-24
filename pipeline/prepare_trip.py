import argparse
import functools
import pathlib
import sys
import time
from datetime import date

import geopandas as gpd
from openmeteo_requests.Client import OpenMeteoRequestsError

from pipeline.bdl import fetch_bdl, save_bdl_tile
from pipeline.entrances import compute_forest_boundary, find_entrance_points, classify_entrances
from pipeline.export import write_scores_json, export_stand_geometries, write_regions_json
from pipeline.gdos import fetch_protected_areas
from pipeline.habitat import load_profile
from pipeline.mvp import enrich_with_mvp_layers
from pipeline.orchestrate import run_poc
from pipeline.osm import fetch_osm_features
from pipeline.rdlp import (
    fetch_rdlp_boundaries_cached, resolve_rdlp_layer, regions_intersecting_bbox, layer_name_for_region,
)
from pipeline.regions import group_into_regions
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import (
    fetch_weather_raw, fetch_climatology_raw,
    _default_open_meteo_call, _default_climatology_call,
)
from pipeline.zakazy import check_periodic_ban

MIN_RADIUS_KM = 10.0
MAX_RADIUS_KM = 50.0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prepare_trip",
        description="Przygotuj wyjazd: policz rejony poszukiwan prawdziwkow dla podanej lokalizacji.",
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
        help=f"Deklarowany promien poszukiwan ({MIN_RADIUS_KM:.0f}-{MAX_RADIUS_KM:.0f} km). "
             "Obecnie tylko walidowany -- przetwarzany jest jeden kafel 10x10 km wokol punktu "
             "(patrz docs/projekt-borowik.md sec.8.1).",
    )
    parser.add_argument("--profile", type=str, default="profiles/boletus_edulis.yaml")
    parser.add_argument("--out-dir", type=str, default="notebooks/output")
    parser.add_argument("--cache-dir", type=str, default="cache")
    args = parser.parse_args(argv)
    if not (MIN_RADIUS_KM <= args.radius_km <= MAX_RADIUS_KM):
        parser.error(f"--radius-km must be between {MIN_RADIUS_KM:.0f} and {MAX_RADIUS_KM:.0f}")
    if args.date is not None:
        try:
            date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"--date must be YYYY-MM-DD, got {args.date!r}")
    return args


class TripPreparationError(RuntimeError):
    """Raised for a known, clean failure (currently: point outside every
    RDLP) that main() turns into a one-line CLI error instead of a
    traceback. Not raised for network/API errors, which are out of this
    plan's scope (spec §13 priority 8) and still surface as-is."""


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


def run_trip_preparation(lat: float, lon: float, day: str, radius_km: float,
                          profile_path: str, out_dir: pathlib.Path, cache_dir: pathlib.Path) -> dict:
    """Runs the full MVP pipeline (BDL -> weather -> mask -> H/F/P/R ->
    regions -> export) for the 10x10 km BDL tile containing (lat, lon).
    Returns a summary dict for the CLI to print; writes scores_{day}.json,
    regions_{day}.json and stands_mvp.parquet under out_dir as a side
    effect. radius_km is accepted for forward compatibility but does not
    yet change which tiles are processed (see plan Global Constraints)."""
    del radius_km  # not yet used -- documented limitation, see Global Constraints
    profile = load_profile(profile_path)
    bbox = tile_bbox_2180(lat, lon, size_km=10.0)
    cache_dir = pathlib.Path(cache_dir)
    tile_id = f"E{int(bbox[1])}N{int(bbox[0])}"
    tile_path = cache_dir / f"{tile_id}.parquet"

    print(f"Resolving RDLP for ({lat}, {lon})...")
    rdlp_gdf = fetch_rdlp_boundaries_cached(cache_dir)
    layer = resolve_rdlp_layer(lat, lon, rdlp_gdf)
    if layer is None:
        raise TripPreparationError(
            f"Punkt ({lat}, {lon}) nie lezy w zadnym RDLP (poza Polska?) -- BDL nie ma dla niego danych."
        )
    print(f"  RDLP layer: {layer}")

    intersecting = regions_intersecting_bbox(bbox, rdlp_gdf)
    if len(intersecting) > 1:
        # Final review finding: a 10x10 km tile near an RDLP border can
        # straddle two directorates. Only `layer`'s wydzielenia get fetched
        # below -- the others' stands are missing from the result. Not
        # fixed by fetching every intersecting layer in this plan (that is
        # a real feature with its own design questions -- merging,
        # deduplicating boundary-straddling stands, cache-key changes --
        # deferred to its own plan); at minimum this makes the gap visible
        # instead of a silently incomplete result.
        others = [r for r in intersecting if layer_name_for_region(r) != layer]
        print(
            f"  Uwaga: kafel 10x10 km przecina granice {len(intersecting)} RDLP "
            f"({', '.join(intersecting)}) -- dane z {', '.join(others)} NIE sa pobierane, "
            f"wynik moze byc niepelny przy tej granicy."
        )

    def _cached_bdl_fetcher(layer, bbox_2180):
        if tile_path.exists():
            print(f"BDL tile cache hit: {tile_path}")
            return gpd.read_parquet(tile_path)
        print(f"BDL tile cache miss, fetching from WFS -> {tile_path}")
        gdf = fetch_bdl(layer, bbox_2180)
        save_bdl_tile(gdf, tile_id, cache_dir)
        return gdf

    def _weather_call_api(lat_, lon_, past_days):
        return _rate_limited(_default_open_meteo_call, lat_, lon_, past_days)

    def _climatology_call_api(lat_, lon_, start_year, end_year):
        return _rate_limited(_default_climatology_call, lat_, lon_, start_year, end_year)

    scored = run_poc(
        layer=layer, bbox_2180=bbox, profile=profile,
        bdl_fetcher=_cached_bdl_fetcher,
        weather_fetcher=functools.partial(fetch_weather_raw, call_api=_weather_call_api),
        climatology_fetcher=functools.partial(fetch_climatology_raw, call_api=_climatology_call_api),
    )
    print(f"run_poc: {len(scored)} wydzielenia, {int(scored['mask'].sum())} passing structural mask")

    print("Fetching GDOS protected areas...")
    gdos_gdf = fetch_protected_areas(bbox)

    print("Fetching OSM parking/roads/places (Overpass)...")
    osm_features = fetch_osm_features(bbox, profile)

    print("Detecting forest entrances...")
    forest_boundary = compute_forest_boundary(scored)
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

    out_dir = pathlib.Path(out_dir)
    scores_path = write_scores_json(enriched, day=day, out_path=out_dir / f"scores_{day}.json")
    stands_path = export_stand_geometries(enriched, out_dir / "stands_mvp.parquet")

    print("Grouping into search regions...")
    regions = group_into_regions(enriched, profile)
    regions_path = write_regions_json(regions, day=day, out_path=out_dir / f"regions_{day}.json")

    return {
        "layer": layer, "tile_id": tile_id, "stand_count": len(scored),
        "mask_passing": int(enriched["mask_full"].sum()),
        "region_count": len(regions),
        "scores_path": scores_path, "stands_path": stands_path, "regions_path": regions_path,
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    today = date.today().isoformat()
    day = args.date or today
    if args.date is not None and args.date != today:
        print(
            f"Uwaga: prognoza pogody odzwierciedla dzisiejsze okno Open-Meteo, "
            f"nie dokladnie dzien {args.date} -- patrz docs/projekt-borowik.md sec.7.2."
        )
    try:
        summary = run_trip_preparation(
            lat=args.lat, lon=args.lon, day=day, radius_km=args.radius_km,
            profile_path=args.profile, out_dir=pathlib.Path(args.out_dir), cache_dir=pathlib.Path(args.cache_dir),
        )
    except TripPreparationError as exc:
        print(f"Blad: {exc}")
        return 1
    print(
        f"Gotowe: {summary['region_count']} rejon(y), "
        f"{summary['mask_passing']}/{summary['stand_count']} wydzielen przechodzi maske."
    )
    print(f"Wyniki: {summary['scores_path']}, {summary['regions_path']}, {summary['stands_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
