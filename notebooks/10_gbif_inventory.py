"""Plan 2.3: inwentaryzacja rekordow GBIF (Boletus edulis, PL i region wlasciciela).

Tylko liczenie (fasety GBIF, limit=0) -- ZADNYCH testow skutecznosci modelu.
Cel: rozstrzygnac, czy kontrole 2.4/2.5 w ogole maja sens wobec progow z
docs/WALIDACJA_REGULY.md. Zapytania sa lekkie (bez pobierania rekordow),
odpowiedzi cache'owane w .cache/gbif_inventory/ (poza repo).

Region: RDLP Katowice + bufor 25 km (przyblizony, uproszczony wielokat).
Odleglosc rekordow od lasow z danymi BDL NIE jest liczona tutaj -- patrz raport.

Run: .venv/Scripts/python.exe notebooks/10_gbif_inventory.py
"""
import hashlib
import json
import pathlib
import time

import geopandas as gpd
import requests
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

API = "https://api.gbif.org/v1/occurrence/search"
CACHE = pathlib.Path(".cache/gbif_inventory")
OUT = pathlib.Path("notebooks/output/gbif_inventory.json")
INAT_DATASET = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
BOLETUS = {"scientificName": "Boletus edulis"}
FUNGI = {"taxonKey": 5}
PLANTAE, ANIMALIA = {"taxonKey": 6}, {"taxonKey": 1}
BASE = {"country": "PL", "hasCoordinate": "true", "hasGeospatialIssue": "false"}
UNC_BINS = {"<=25 m": "0,25", "<=100 m": "0,100", "<=1000 m": "0,1000"}
FACET_LIMIT = 100000


def query(params: dict) -> dict:
    """Zapytanie z cache na dysku (klucz = hash parametrow)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(5):
        r = requests.get(API, params=params, timeout=120)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data), encoding="utf-8")
        time.sleep(0.3)
        return data
    raise RuntimeError("GBIF: zbyt wiele odpowiedzi 429")


def region_wkt(buffer_m: float = 25000, simplify_m: float = 1500) -> str:
    gdf = gpd.read_parquet("cache/rdlp_boundaries.parquet")
    row = gdf[gdf["id"] == "RDLP.2"]  # Katowice
    geom = row.geometry.union_all().buffer(buffer_m).simplify(simplify_m)
    geom = gpd.GeoSeries([geom], crs=gdf.crs).to_crs(4326).iloc[0]
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    poly = orient(Polygon(geom.exterior.coords), sign=1.0)  # GBIF: kontur przeciwnie do ruchu wskazowek zegara
    return poly.wkt


def count(params: dict) -> int:
    return query({**params, "limit": 0})["count"]


def facet(params: dict, name: str, limit: int = FACET_LIMIT) -> list[tuple[str, int]]:
    data = query({**params, "limit": 0, "facet": name, "facetLimit": limit, "facetMincount": 1})
    return [(c["name"], c["count"]) for f in data["facets"] for c in f["counts"]]


def describe(label: str, taxon: dict, extra: dict) -> dict:
    p = {**BASE, **taxon, **extra}
    total = count(p)
    out = {"etykieta": label, "razem": total,
           "niepewnosc": {name: count({**p, "coordinateUncertaintyInMeters": rng}) for name, rng in UNC_BINS.items()}}
    out["niepewnosc"]["brak_wartosci"] = total - count({**p, "coordinateUncertaintyInMeters": "0,10000000"})
    out["inaturalist"] = count({**p, "datasetKey": INAT_DATASET})
    out["rok"] = dict(sorted(facet(p, "YEAR")))
    out["miesiac"] = dict(sorted(facet(p, "MONTH"), key=lambda kv: int(kv[0])))
    observers = sorted(facet(p, "RECORDED_BY"), key=lambda kv: -kv[1])
    out["obserwatorzy"] = {
        "rozni": len(observers), "rekordow_z_obserwatorem": sum(n for _, n in observers),
        "udzial_top5": (sum(n for _, n in observers[:5]) / total) if total else None,
        "uwaga": "fasety recordedBy: rekordy bez pola sa pominiete; pisownie tego samego obserwatora moga sie roznic",
    }
    return out


def main() -> None:
    wkt = region_wkt()
    sets = []
    for scope, extra in [("Polska", {}), ("RDLP Katowice + 25 km", {"geometry": wkt})]:
        sets.append({"zakres": scope, "wpisy": [
            describe("Boletus edulis", BOLETUS, extra),
            describe("Grzyby ogolem (tlo: inne grzyby, zawiera B. edulis)", FUNGI, extra),
            describe("Rosliny (tlo niegrzybowe)", PLANTAE, extra),
            describe("Zwierzeta (tlo niegrzybowe)", ANIMALIA, extra),
        ]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sets, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in sets:
        print(f"\n== {s['zakres']} ==")
        for e in s["wpisy"]:
            print(f"{e['etykieta']}: {e['razem']} rek., niepewnosc {e['niepewnosc']}, iNat {e['inaturalist']}, "
                  f"obserwatorow {e['obserwatorzy']['rozni']}, top5 {e['obserwatorzy']['udzial_top5']}")


if __name__ == "__main__":
    main()
