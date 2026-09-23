import requests

# ArcGIS REST query on the BDL periodic-access-ban MapServer, used instead of
# raw WMS GetFeatureInfo pixel math (see plan Global Constraints for the
# layer-id [?] verified 2026-09-23: WMS GetCapabilities lists this layer at
# index 3, the REST MapServer listing at index 0 -- 0 is what this module's
# query URL actually hits, re-verify via Step 5 before relying on it).
DEFAULT_ZAKAZY_URL = "https://mapserver.bdl.lasy.gov.pl/ArcGIS/rest/services/WMS_zakazy_wstepu_do_lasu/MapServer"
DEFAULT_LAYER_ID = 0


def build_zakazy_query_url(lat: float, lon: float, layer_id: int = DEFAULT_LAYER_ID,
                             base_url: str = DEFAULT_ZAKAZY_URL) -> str:
    req = requests.Request(
        "GET",
        f"{base_url}/{layer_id}/query",
        params={
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
        },
    )
    return req.prepare().url


def _default_zakazy_call(lat: float, lon: float) -> dict:
    """Thin IO boundary; not unit tested (network), see Step 5 manual
    verification."""
    resp = requests.get(build_zakazy_query_url(lat, lon), timeout=30)
    resp.raise_for_status()
    return resp.json()


def check_periodic_ban(lat: float, lon: float, call_api=None) -> bool:
    """True if a periodic access ban polygon covers (lat, lon) right now."""
    call_api = call_api or _default_zakazy_call
    data = call_api(lat, lon)
    return len(data.get("features", [])) > 0
