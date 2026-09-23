import geopandas as gpd
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _bbox_2180_to_4326(bbox_2180: tuple) -> tuple:
    n_min, e_min, n_max, e_max = bbox_2180
    corners = [(e_min, n_min), (e_min, n_max), (e_max, n_min), (e_max, n_max)]
    lons, lats = zip(*(_TO_4326.transform(e, n) for e, n in corners))
    return (min(lats), min(lons), max(lats), max(lons))  # south, west, north, east


def build_overpass_query(bbox_4326: tuple, profile: dict) -> str:
    south, west, north, east = bbox_4326
    bbox_str = f"{south},{west},{north},{east}"
    cfg = profile["osm"]
    highway_re = "|".join(cfg["road_highway_types"])
    place_re = "|".join(cfg["place_types"])
    return (
        f'[out:json][timeout:25];'
        f'('
        f'node["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["highway"~"^({highway_re})$"]({bbox_str});'
        f'node["place"~"^({place_re})$"]({bbox_str});'
        f');'
        f'out center tags;'
    )


def _element_point(element: dict):
    if "lat" in element and "lon" in element:
        return Point(element["lon"], element["lat"])
    center = element.get("center")
    if center:
        return Point(center["lon"], center["lat"])
    return None


def parse_osm_elements(elements: list[dict]) -> dict:
    parking_rows, road_rows, place_rows = [], [], []
    for el in elements:
        tags = el.get("tags", {})
        point = _element_point(el)
        if point is None:
            continue
        if tags.get("amenity") == "parking":
            parking_rows.append({"osm_id": el["id"], "geometry": point})
        elif "highway" in tags:
            road_rows.append({"osm_id": el["id"], "highway": tags["highway"], "geometry": point})
        elif "place" in tags:
            population = pd.to_numeric(tags.get("population"), errors="coerce")
            place_rows.append({
                "osm_id": el["id"], "place": tags["place"], "name": tags.get("name", ""),
                "population": 0.0 if pd.isna(population) else float(population),
                "geometry": point,
            })
    return {
        "parking": gpd.GeoDataFrame(parking_rows, geometry="geometry", crs="EPSG:4326") if parking_rows
                    else gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326"),
        "roads": gpd.GeoDataFrame(road_rows, geometry="geometry", crs="EPSG:4326") if road_rows
                  else gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326"),
        "places": gpd.GeoDataFrame(place_rows, geometry="geometry", crs="EPSG:4326") if place_rows
                   else gpd.GeoDataFrame({"osm_id": [], "population": []}, geometry=[], crs="EPSG:4326"),
    }


def _default_overpass_call(query: str) -> dict:
    """Thin IO boundary; not unit tested (network), see Task 6 Step 5 manual
    verification. POST, not GET-with-huge-URL -- Overpass rejects/queues long
    GET query strings under load. A User-Agent is required: verified live
    2026-09-24, overpass-api.de's Apache front end returns a bare 406 Not
    Acceptable (before the request reaches the Overpass backend at all) for
    requests.post's default "python-requests/x.y" user agent."""
    resp = requests.post(
        DEFAULT_OVERPASS_URL, data={"data": query}, timeout=60,
        headers={"User-Agent": "grzyby-borowik-poc/0.1 (research script)"},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_osm_features(bbox_2180: tuple, profile: dict, call_api=None) -> dict:
    call_api = call_api or _default_overpass_call
    bbox_4326 = _bbox_2180_to_4326(bbox_2180)
    query = build_overpass_query(bbox_4326, profile)
    data = call_api(query)
    frames = parse_osm_elements(data.get("elements", []))
    return {name: gdf.to_crs("EPSG:2180") for name, gdf in frames.items()}
