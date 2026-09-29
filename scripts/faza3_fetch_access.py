"""Faza 3.1: jednorazowe pobranie zrodel punktow dostepu (BDL turystyczny,
dojazdy pozarowe, OSM drogi/szlabany) do cache/access_tiles dla kafli
podanego obszaru -- bez pogody, bez pozostalych zrodel. Sekwencyjnie,
z tymi samymi opoznieniami/ponowieniami co prepare_trip.

    python scripts/faza3_fetch_access.py --lat 50.527 --lon 18.605 --radius-km 20
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.access_data import _default_bdl_get, load_access_sources  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402
from pipeline.osm import _default_overpass_call  # noqa: E402
from pipeline.prepare_trip import (  # noqa: E402
    _is_overpass_retryable, _is_transient_network_error, _rate_limited,
)
from pipeline.search_area import search_tiles  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius-km", type=float, default=20.0)
    ap.add_argument("--cache-dir", default="cache")
    ap.add_argument("--profile", default="profiles/boletus_edulis.yaml")
    args = ap.parse_args()
    cfg = load_profile(args.profile)["pressure"]["access_points"]
    _, tiles = search_tiles(args.lat, args.lon, args.radius_km)
    osm_call = lambda q: _rate_limited(  # noqa: E731
        _default_overpass_call, q, should_retry=_is_overpass_retryable, backoff_s=30, pace_s=1.0)
    bdl_get = lambda *a: _rate_limited(  # noqa: E731
        _default_bdl_get, *a, should_retry=_is_transient_network_error, max_attempts=3, backoff_s=5, pace_s=0.3)
    out = load_access_sources(tiles, pathlib.Path(args.cache_dir), cfg, osm_call, bdl_get=bdl_get)
    print({k: len(out[k]) for k in ("bdl_parkings", "fire_roads", "osm_roads", "osm_gates")}, out["failed"])
    return 1 if (out["failed"]["bdl"] or out["failed"]["osm"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
