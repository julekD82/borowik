"""Plan wdrozenia Faza 3.1: zrodla danych punktow dostepu.

Trzy zrodla, kazde z wlasnym cache kafli 10 x 10 km w `cache/access_tiles/`
(osobno od glownego cache OSM -- inne zapytanie, inne pola):

* BDL, warstwa turystyczna (ArcGIS WFS `WFS_BDL_mapa_turystyczna`): parkingi
  lesne (`PARKING`) i miejsca postoju pojazdow (`MSC POST`);
* BDL, dojazdy pozarowe (ArcGIS WFS `WFS_BDL_dojazdy_pozarowe`): jednolity
  szkielet sieci drog lesnych (linie, numer dojazdu `nr_ppoz`);
* OSM (Overpass): drogi z tagami nawierzchni/dostepu i szlabany
  (`barrier=gate|lift_gate`).

Serwer ArcGIS BDL zwraca GeoJSON zadeklarowany jako UTF-8, ale faktycznie w
cp1250 (zweryfikowane 2026-09-29: "Lesny" z polskim znakiem psuje sie w
UTF-8), a kolejnosc osi w parametrze BBOX to N,E (jak w
`pipeline.tiles.wfs_bbox_param`), przy czym wspolrzedne w odpowiedzi to
[E, N].
"""
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, shape

from pipeline.osm import _bbox_2180_to_4326, model_overpass_statements, parse_osm_elements, select_model_elements
from pipeline.tiles import wfs_bbox_param

BDL_ARCGIS_BASE = "https://mapserver.bdl.lasy.gov.pl/arcgis/services"
TOURIST_SERVICE = "WFS_BDL_mapa_turystyczna"
TOURIST_AREA_LAYER = "Powierzchniowe_obiekty_rekreacyjno-wypoczynkowe_i_edukacyjne"
FIRE_SERVICE = "WFS_BDL_dojazdy_pozarowe"
FIRE_LAYER = "Dojazdy_pożarowe"

# tur_rec_pnt_cd -> nasz podtyp. Tylko te dwa kody to miejsca, gdzie staje auto.
PARKING_CODES = {"PARKING": "parking_lesny", "MSC POST": "miejsce_postoju"}

_PAGE_SIZE = 5000
_MAX_PAGES = 40


def _decode_bdl_bytes(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1250")


def _default_bdl_get(service: str, type_name: str, bbox, start_index: int) -> dict:
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": f"{service}:{type_name}", "outputFormat": "GEOJSON",
        "srsName": "urn:ogc:def:crs:EPSG::2180", "bbox": wfs_bbox_param(bbox),
        "count": _PAGE_SIZE, "startIndex": start_index,
    }
    resp = requests.get(
        f"{BDL_ARCGIS_BASE}/{service}/MapServer/WFSServer", params=params, timeout=(15, 60),
        headers={"User-Agent": "grzyby-borowik-poc/0.1 (research script)"},
    )
    resp.raise_for_status()
    return json.loads(_decode_bdl_bytes(resp.content))


def _fetch_bdl_features(service: str, type_name: str, bbox, get=None) -> list[dict]:
    """Wszystkie obiekty kafla; stronicowanie po objectid (serwer moze
    zignorowac startIndex -- wtedy konczymy, gdy strona nie wnosi nic nowego)."""
    get = get or _default_bdl_get
    seen, features = set(), []
    for page in range(_MAX_PAGES):
        data = get(service, type_name, bbox, page * _PAGE_SIZE)
        batch = data.get("features", [])
        fresh = [f for f in batch if f["properties"].get("objectid") not in seen]
        if not fresh:
            break
        for f in fresh:
            seen.add(f["properties"].get("objectid"))
        features.extend(fresh)
        if len(batch) < _PAGE_SIZE:
            break
    return features


def _empty(columns: dict) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(columns, geometry=[], crs="EPSG:2180")


def fetch_bdl_parkings(bbox, get=None) -> gpd.GeoDataFrame:
    """Parkingi lesne i miejsca postoju BDL w kaflu (EPSG:2180, punkty)."""
    rows = []
    for f in _fetch_bdl_features(TOURIST_SERVICE, TOURIST_AREA_LAYER, bbox, get):
        props = f["properties"]
        subtype = PARKING_CODES.get(props.get("tur_rec_pnt_cd"))
        if subtype is None or not f.get("geometry"):
            continue
        geom = shape(f["geometry"])
        rows.append({
            "source_id": str(props.get("objectid")), "subtype": subtype,
            "name": props.get("nzw_ob") or "",
            "geometry": geom if geom.geom_type == "Point" else geom.representative_point(),
        })
    if not rows:
        return _empty({"source_id": [], "subtype": [], "name": []})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:2180")


def fetch_bdl_fire_roads(bbox, get=None) -> gpd.GeoDataFrame:
    """Dojazdy pozarowe BDL w kaflu (EPSG:2180, LineString po rozbiciu
    MultiLineString), z numerem dojazdu `fire_no` (`nr_ppoz`)."""
    rows = []
    for f in _fetch_bdl_features(FIRE_SERVICE, FIRE_LAYER, bbox, get):
        props = f["properties"]
        geom = f.get("geometry")
        if not geom:
            continue
        parts = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        fire_no = (props.get("nr_ppoz") or "").strip()
        for part in parts:
            if len(part) >= 2:
                rows.append({
                    "source_id": str(props.get("objectid")), "fire_no": fire_no,
                    "geometry": LineString([(x, y) for x, y, *_ in part]),
                })
    if not rows:
        return _empty({"source_id": [], "fire_no": []})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:2180")


# --- OSM -------------------------------------------------------------------

_ROAD_TAG_COLUMNS = ("surface", "tracktype", "access", "motor_vehicle", "bicycle", "name", "ref")
# service bez parking_aisle/driveway/alley: nie miejskie zaulki, tylko drogi dojazdowe
SERVICE_EXCLUDED = ("parking_aisle", "driveway", "alley", "drive-through")


def access_overpass_statements(bbox_str: str, cfg: dict) -> str:
    osm = cfg["osm"]
    highway_re = "|".join(osm["highway_types"])
    barrier_re = "|".join(osm["barrier_types"])
    return (
        f'way["highway"~"^({highway_re})$"]["service"!~"^({"|".join(SERVICE_EXCLUDED)})$"]({bbox_str});'
        f'node["barrier"~"^({barrier_re})$"]({bbox_str});'
    )


def build_access_overpass_query(bbox_4326: tuple, cfg: dict) -> str:
    south, west, north, east = bbox_4326
    bbox_str = f"{south},{west},{north},{east}"
    return f'[out:json][timeout:60];({access_overpass_statements(bbox_str, cfg)});out geom;'


def select_access_elements(elements: list[dict], cfg: dict) -> list[dict]:
    """Elementy, ktore zwrociloby build_access_overpass_query (podzial wyniku polaczonego zapytania)."""
    osm = cfg["osm"]

    def wanted(el):
        tags = el.get("tags", {})
        if el.get("type") == "way":
            return tags.get("highway") in osm["highway_types"] and tags.get("service") not in SERVICE_EXCLUDED
        return el.get("type") == "node" and tags.get("barrier") in osm["barrier_types"]

    return [el for el in elements if wanted(el)]


def parse_access_osm_elements(elements: list[dict]) -> dict:
    road_rows, gate_rows = [], []
    for el in elements:
        tags = el.get("tags", {})
        if el.get("type") == "node" and "barrier" in tags and "lat" in el:
            gate_rows.append({
                "osm_id": el["id"], "barrier": tags["barrier"], "access": tags.get("access"),
                "geometry": Point(el["lon"], el["lat"]),
            })
        elif "highway" in tags and el.get("geometry") and len(el["geometry"]) >= 2:
            row = {"osm_id": el["id"], "highway": tags["highway"],
                   "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]])}
            for col in _ROAD_TAG_COLUMNS:
                row[col] = tags.get(col)
            road_rows.append(row)
    road_cols = {"osm_id": [], "highway": [], **{c: [] for c in _ROAD_TAG_COLUMNS}}
    return {
        "roads": (gpd.GeoDataFrame(road_rows, geometry="geometry", crs="EPSG:4326") if road_rows
                  else gpd.GeoDataFrame(road_cols, geometry=[], crs="EPSG:4326")),
        "gates": (gpd.GeoDataFrame(gate_rows, geometry="geometry", crs="EPSG:4326") if gate_rows
                  else gpd.GeoDataFrame({"osm_id": [], "barrier": [], "access": []}, geometry=[], crs="EPSG:4326")),
    }


def fetch_access_osm(bbox_2180: tuple, cfg: dict, call_api) -> dict:
    query = build_access_overpass_query(_bbox_2180_to_4326(bbox_2180), cfg)
    data = call_api(query)
    frames = parse_access_osm_elements(data.get("elements", []))
    return {name: gdf.to_crs("EPSG:2180") for name, gdf in frames.items()}


def fetch_osm_combined(bbox_2180: tuple, profile: dict, cfg: dict, call_api) -> tuple[dict, dict]:
    """Jedno zapytanie Overpass zamiast dwoch (pipeline.osm.fetch_osm_features + fetch_access_osm):
    suma obu zapytan, wynik dzielony filtrami odwzorowujacymi kazde z nich -- te same dane, polowa
    zapytan do serwera publicznego (limity Overpass to najdluzsza czesc pierwszej analizy obszaru)."""
    south, west, north, east = _bbox_2180_to_4326(bbox_2180)
    bbox_str = f"{south},{west},{north},{east}"
    query = (f'[out:json][timeout:90];({model_overpass_statements(bbox_str, profile)}'
             f'{access_overpass_statements(bbox_str, cfg)});out geom;')
    elements = call_api(query).get("elements", [])
    model = parse_osm_elements(select_model_elements(elements, profile))
    access = parse_access_osm_elements(select_access_elements(elements, cfg))
    return ({n: g.to_crs("EPSG:2180") for n, g in model.items()},
            {n: g.to_crs("EPSG:2180") for n, g in access.items()})


# --- cache kafli -------------------------------------------------------------

TILE_M = 10000


def _tile_name(bbox) -> str:
    return f"E{bbox[1]}N{bbox[0]}S{TILE_M}"


def _write_tile_frames(tile_dir: Path, frames: dict) -> None:
    tile_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        temp = tile_dir / f"{name}.tmp.parquet"
        frame.to_parquet(temp)
        temp.replace(tile_dir / f"{name}.parquet")


def _cached_tile_frames(tile_dir: Path, names: tuple, fetch):
    """(frames, from_cache). Zapis atomowy; brak pliku = kafel niepobrany.
    Pusty wynik tez jest zapisywany (to poprawna odpowiedz, nie blad)."""
    if all((tile_dir / f"{n}.parquet").exists() for n in names):
        return {n: gpd.read_parquet(tile_dir / f"{n}.parquet") for n in names}, True
    frames = fetch()
    _write_tile_frames(tile_dir, frames)
    return frames, False


def access_osm_tile_dir(cache_dir, cfg: dict, bbox) -> Path:
    osm_key = hashlib.sha256(repr((cfg["osm"], "v1")).encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / "access_tiles" / "osm" / osm_key / _tile_name(bbox)


def combined_osm_fetcher(cache_dir, cfg: dict, call_api, fetch=None):
    """Fetcher dla pipeline.search_area.fetch_cached_osm: jedno zapytanie na kafel, ktore od razu
    zapisuje tez kafel warstw dostepu (load_access_sources czyta go potem z cache)."""
    def fetch_tile(bbox, profile):
        model, access = (fetch or fetch_osm_combined)(bbox, profile, cfg, call_api)
        _write_tile_frames(access_osm_tile_dir(cache_dir, cfg, bbox), access)
        return model
    return fetch_tile


def _merge(frames: list, crs="EPSG:2180") -> gpd.GeoDataFrame:
    frames = [f for f in frames if len(f)]
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs)
    key = merged.geometry.to_wkb()
    id_col = "osm_id" if "osm_id" in merged else "source_id" if "source_id" in merged else None
    subset = ([id_col] if id_col else []) + ["_k"]
    return merged.assign(_k=key).drop_duplicates(subset=subset).drop(columns="_k").reset_index(drop=True)


def load_access_sources(tiles, cache_dir, cfg: dict, osm_call_api, bdl_get=None) -> dict:
    """Pobiera (lub czyta z cache) wszystkie zrodla punktow dostepu dla kafli.

    Zwraca {"bdl_parkings", "fire_roads", "osm_roads", "osm_gates",
    "failed": {"bdl": [bbox..], "osm": [bbox..]}}. Kafel, ktorego pobranie
    zawiodlo, nie jest cache'owany i jest raportowany; po pierwszym bledzie
    OSM dalsze pobieranie OSM jest wstrzymane (jak fetch_cached_osm -- nie
    zasypujemy serwera publicznego)."""
    root = Path(cache_dir) / "access_tiles"
    parkings, fire, roads, gates = [], [], [], []
    failed = {"bdl": [], "osm": []}
    cache_hits = {"bdl": 0, "osm": 0}
    osm_give_up = False
    for index, bbox in enumerate(tiles, 1):
        name = _tile_name(bbox)
        try:
            frames, hit = _cached_tile_frames(
                root / "bdl" / name, ("parkings", "fire_roads"),
                lambda b=bbox: {"parkings": fetch_bdl_parkings(b, bdl_get),
                                "fire_roads": fetch_bdl_fire_roads(b, bdl_get)},
            )
            cache_hits["bdl"] += hit
            print(f"Dostep BDL {index}/{len(tiles)}: ({'cache' if hit else 'ArcGIS WFS'})", flush=True)
            parkings.append(frames["parkings"])
            fire.append(frames["fire_roads"])
        except Exception as exc:
            print(f"Dostep BDL {index}/{len(tiles)}: BLAD ({exc}) -- kafel pominiety", flush=True)
            failed["bdl"].append(bbox)
        osm_dir = access_osm_tile_dir(cache_dir, cfg, bbox)
        cached = all((osm_dir / f"{n}.parquet").exists() for n in ("roads", "gates"))
        if not cached and osm_give_up:
            print(f"Dostep OSM {index}/{len(tiles)}: pominiety (wczesniejszy blad)", flush=True)
            failed["osm"].append(bbox)
            continue
        try:
            frames, hit = _cached_tile_frames(
                osm_dir, ("roads", "gates"), lambda b=bbox: fetch_access_osm(b, cfg, osm_call_api),
            )
        except Exception as exc:
            print(f"Dostep OSM {index}/{len(tiles)}: BLAD ({exc}) -- wstrzymuje dalsze pobieranie OSM", flush=True)
            failed["osm"].append(bbox)
            osm_give_up = True
            continue
        cache_hits["osm"] += hit
        print(f"Dostep OSM {index}/{len(tiles)}: ({'cache' if hit else 'Overpass'})", flush=True)
        roads.append(frames["roads"])
        gates.append(frames["gates"])
    return {
        "bdl_parkings": _merge(parkings), "fire_roads": _merge(fire),
        "osm_roads": _merge(roads), "osm_gates": _merge(gates),
        "failed": failed, "cache_hits": cache_hits, "tile_count": len(tiles),
    }
