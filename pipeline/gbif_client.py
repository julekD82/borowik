"""Cienki klient GBIF do walidacji 2.4/2.5: zapytania cache'owane na dysku (.cache/gbif_inventory/)."""
import hashlib
import json
import math
import time
from pathlib import Path

import requests
from shapely.geometry import Polygon

API = "https://api.gbif.org/v1/occurrence/search"
CACHE = Path(".cache/gbif_inventory")
BASE = {"country": "PL", "hasCoordinate": "true", "hasGeospatialIssue": "false"}
BOLETUS = {"scientificName": "Boletus edulis"}
FUNGI_TAXON_KEY = 5
PLANTAE_TAXON_KEY = 6
ANIMALIA_TAXON_KEY = 1
PAGE = 300
MAX_OFFSET = 100000  # limit GBIF search API


def query(params: dict, get=requests.get) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(6):
        try:
            r = get(API, params=params, timeout=(10, 60))
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError):
            time.sleep(15 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data), encoding="utf-8")
        time.sleep(0.25)
        return data
    raise RuntimeError("GBIF: zbyt wiele nieudanych prob (429 / blad polaczenia)")


def fetch_all(params: dict) -> list[dict]:
    """Wszystkie rekordy zapytania (musi dawac < 100 000 wynikow)."""
    records, offset = [], 0
    while True:
        d = query({**params, "limit": PAGE, "offset": offset})
        records += d["results"]
        if d["endOfRecords"] or offset + PAGE >= MAX_OFFSET:
            return records
        offset += PAGE


def count(params: dict) -> int:
    return query({**params, "limit": 0})["count"]


def circle_wkt(lat: float, lon: float, radius_km: float, n: int = 24) -> str:
    """Wielokat (n-kat) o promieniu radius_km; kontur przeciwnie do ruchu wskazowek zegara (wymog GBIF)."""
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    pts = [(lon + dlon * math.cos(2 * math.pi * i / n), lat + dlat * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return Polygon(pts).wkt


def facet_dates(params: dict) -> dict[str, int]:
    """Liczba rekordow na dzien (fasety EVENT_DATE, pierwsze 10 znakow = data)."""
    data = query({**params, "limit": 0, "facet": "EVENT_DATE", "facetLimit": 200, "facetMincount": 1})
    out: dict[str, int] = {}
    for f in data.get("facets", []):
        for c in f["counts"]:
            day = c["name"][:10]
            out[day] = out.get(day, 0) + c["count"]
    return out


def slim(record: dict) -> dict:
    return {
        "key": record["key"], "lat": record["decimalLatitude"], "lon": record["decimalLongitude"],
        "unc": record.get("coordinateUncertaintyInMeters"), "date": record.get("eventDate"),
        "year": record.get("year"), "month": record.get("month"), "day": record.get("day"),
        "observer": record.get("recordedBy"), "dataset": record.get("datasetKey"),
        "species": record.get("species") or record.get("scientificName"),
    }
