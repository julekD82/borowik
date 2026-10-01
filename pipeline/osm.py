import geopandas as gpd
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point, LineString

_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _bbox_2180_to_4326(bbox_2180: tuple) -> tuple:
    n_min, e_min, n_max, e_max = bbox_2180
    corners = [(e_min, n_min), (e_min, n_max), (e_max, n_min), (e_max, n_max)]
    lons, lats = zip(*(_TO_4326.transform(e, n) for e, n in corners))
    return (min(lats), min(lons), max(lats), max(lons))  # south, west, north, east


def model_overpass_statements(bbox_str: str, profile: dict) -> str:
    cfg = profile["osm"]
    highway_re = "|".join(cfg["routing_highway_types"])
    place_re = "|".join(cfg["place_types"])
    return (
        f'node["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["amenity"="{cfg["parking_amenity"]}"]({bbox_str});'
        f'way["highway"~"^({highway_re})$"]({bbox_str});'
        f'node["place"~"^({place_re})$"]({bbox_str});'
    )


def build_overpass_query(bbox_4326: tuple, profile: dict) -> str:
    south, west, north, east = bbox_4326
    bbox_str = f"{south},{west},{north},{east}"
    return f'[out:json][timeout:25];({model_overpass_statements(bbox_str, profile)});out geom;'


def select_model_elements(elements: list[dict], profile: dict) -> list[dict]:
    """Elementy, ktore zwrociloby build_overpass_query -- do podzialu wyniku polaczonego zapytania
    (pipeline.access_data.fetch_osm_combined)."""
    cfg = profile["osm"]

    def wanted(el):
        tags, kind = el.get("tags", {}), el.get("type")
        if kind in ("node", "way") and tags.get("amenity") == cfg["parking_amenity"]:
            return True
        if kind == "way" and tags.get("highway") in cfg["routing_highway_types"]:
            return True
        return kind == "node" and tags.get("place") in cfg["place_types"]

    return [el for el in elements if wanted(el)]


def _element_representative_point(element: dict):
    """A single representative Point for a node or way. Nodes use their own
    lat/lon; ways use the centroid of their own linework -- Overpass
    `out geom;` (replacing `out center tags;`, Task 1 of the accessibility
    plan) no longer returns a `center` field."""
    if "lat" in element and "lon" in element:
        return Point(element["lon"], element["lat"])
    geometry = element.get("geometry")
    if not geometry:
        return None
    coords = [(pt["lon"], pt["lat"]) for pt in geometry]
    if len(coords) == 1:
        return Point(coords[0])
    return LineString(coords).centroid


def _way_linestring(element: dict):
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 2:
        return None
    return LineString([(pt["lon"], pt["lat"]) for pt in geometry])


def parse_osm_elements(elements: list[dict]) -> dict:
    parking_rows, road_rows, place_rows = [], [], []
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("amenity") == "parking":
            point = _element_representative_point(el)
            if point is not None:
                parking_rows.append({"osm_id": el["id"], "geometry": point})
        elif "highway" in tags:
            line = _way_linestring(el)
            if line is not None:
                road_rows.append({"osm_id": el["id"], "highway": tags["highway"], "geometry": line})
        elif "place" in tags:
            point = _element_representative_point(el)
            if point is None:
                continue
            population = pd.to_numeric(tags.get("population"), errors="coerce")
            place_rows.append({
                "osm_id": el["id"], "place": tags["place"], "name": tags.get("name", ""),
                # Plan 1.4: NaN (not 0.0) for a missing/non-numeric tag --
                # pipeline.population_grid.impute_osm_population fills this
                # with a class-based default when the GUS grid isn't in use;
                # collapsing it to 0.0 here would make that fallback see a
                # "real" zero-population place instead of a missing value
                # (spec S5.4: "miejscowosc bez populacji dostaje 0 i znika").
                "population": float(population) if not pd.isna(population) else float("nan"),
                "geometry": point,
            })
    return {
        "parking": gpd.GeoDataFrame(parking_rows, geometry="geometry", crs="EPSG:4326") if parking_rows
                    else gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326"),
        "roads": gpd.GeoDataFrame(road_rows, geometry="geometry", crs="EPSG:4326") if road_rows
                  else gpd.GeoDataFrame({"osm_id": [], "highway": []}, geometry=[], crs="EPSG:4326"),
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
