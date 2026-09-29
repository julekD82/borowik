"""Dziennik wyjsc: przypisanie punktow i sladu do wydzielen BDL, GPX i czas w wydzieleniach.

Geometria wydzielen: najpierw paczki BDL (G_SUBAREA.shp z katalogu paczek, patrz pipeline.local_config),
a dla punktow, ktorych zadna paczka nie pokrywa, kafle WFS (te same kafle 10 km i ten sam cache
`bdl_tiles_v2`, co w pipeline.search_area). Wydzielenie = wszystkie wielokaty o tym samym
`adr_for@a_year` (stand_id jak w reszcie potoku), zlaczone w jeden obiekt.
"""
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import LineString, Point

from pipeline.bdl import fetch_bdl
from pipeline.rdlp import fetch_rdlp_boundaries_cached
from pipeline.search_area import TILE_M, fetch_search_stands

TO_2180 = Transformer.from_crs(4326, 2180, always_xy=True)

MARGIN_M = 150.0            # zapas wokol punktow przy czytaniu paczek
GAP_S = 600.0               # przerwa miedzy punktami dluzsza niz 10 min nie liczy sie jako szukanie
MIN_CROSSING_M = 1.0        # krotszy przeciecie sladu z wydzieleniem nie liczy sie jako "przechodzi"
LOW_ACCURACY_M = 50.0       # punkty GPX gorsze niz to sa oznaczane
DEFAULT_ACCURACY_M = 25.0   # gdy brak dokladnosci GPS znaleziska
NO_STAND_LABEL = "(brak wydzielenia w danych BDL)"

# Nazwy nadlesnictw z polskimi znakami (jak FOREST_DISTRICTS we frontendzie); dla innych nazwa z paczki/WFS bez znakow.
DISTRICTS = {
    "02-03": "Brynek", "02-09": "Katowice", "02-10": "Kędzierzyn", "02-14": "Zawadzkie",
    "02-16": "Koszęcin", "02-19": "Lubliniec", "02-21": "Oleśno", "02-25": "Rudziniec",
    "02-29": "Strzelce Opolskie",
}
_NAME_RE = re.compile(r"^BDL_\d+_\d+_(.+)_\d{4}$")


# ---------------------------------------------------------------- nazwy

def district_name(code: str, source_name: str | None) -> str | None:
    """Nazwa nadlesnictwa: slownik z polskimi znakami albo z nazwy paczki `BDL_02_19_LUBLINIEC_2026`."""
    if code in DISTRICTS:
        return DISTRICTS[code]
    m = _NAME_RE.match(source_name or "")
    return m.group(1).replace("_", " ").title() if m else None


def stand_label(adr_for: str, district: str | None) -> str:
    """"Oddz. 96a · Nadl. Zawadzkie" (jak standName we frontendzie)."""
    parts = [p.strip() for p in adr_for.split("-")]
    if len(parts) < 6 or any(not p for p in parts[:5]):
        return f"Wydzielenie {adr_for.strip()}"
    where = f"Nadl. {district}" if district else f"nadl. {parts[0]}-{parts[1]}"
    return f"Oddz. {parts[4]}{parts[5]} · {where}"


# ---------------------------------------------------------------- indeks wydzielen

def to_2180(lon, lat):
    e, n = TO_2180.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.column_stack([np.atleast_1d(e), np.atleast_1d(n)])


def _read_packages(packages_dir: Path, xy: np.ndarray) -> gpd.GeoDataFrame:
    """Wielokaty z paczek BDL w poblizu punktow (czytane z filtrem bbox); kolumny adr_for, a_year, nazwa."""
    from pyogrio import read_info

    frames = []
    for pkg in sorted(p for p in Path(packages_dir).glob("*") if (p / "G_SUBAREA.shp").exists()):
        shp = pkg / "G_SUBAREA.shp"
        minx, miny, maxx, maxy = read_info(shp)["total_bounds"]
        near = xy[(xy[:, 0] >= minx - MARGIN_M) & (xy[:, 0] <= maxx + MARGIN_M)
                  & (xy[:, 1] >= miny - MARGIN_M) & (xy[:, 1] <= maxy + MARGIN_M)]
        if not len(near):
            continue
        bbox = (near[:, 0].min() - MARGIN_M, near[:, 1].min() - MARGIN_M,
                near[:, 0].max() + MARGIN_M, near[:, 1].max() + MARGIN_M)
        g = gpd.read_file(shp, bbox=bbox, columns=["adr_for", "a_year"])
        if not len(g):
            continue
        # CS92 z paczek to ten sam uklad co EPSG:2180 (inna tylko nazwa w .prj).
        g = g.set_crs(2180, allow_override=True)
        g["nazwa"] = pkg.name
        frames.append(g)
    if not frames:
        return gpd.GeoDataFrame({"adr_for": [], "a_year": [], "nazwa": []}, geometry=[], crs=2180)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=2180)


class StandIndex:
    """Wydzielenia (jedna geometria na stand_id) z szybkim wyszukiwaniem po punkcie i odcinku."""

    def __init__(self, stands: gpd.GeoDataFrame):
        self.stands = stands.reset_index(drop=True)
        self.geoms = list(self.stands.geometry)
        self.ids = list(self.stands["stand_id"])
        self.tree = STRtree(self.geoms) if self.geoms else None
        self._boundaries = {}

    def __len__(self):
        return len(self.geoms)

    def label(self, i: int) -> str:
        return self.stands.at[i, "label"]

    def locate(self, x: float, y: float) -> int | None:
        if self.tree is None:
            return None
        hits = self.tree.query(Point(x, y), predicate="intersects")
        return int(min(hits)) if len(hits) else None

    def boundary_distance(self, x: float, y: float, i: int) -> float:
        if i not in self._boundaries:
            self._boundaries[i] = self.geoms[i].boundary
        return float(self._boundaries[i].distance(Point(x, y)))


def build_index(xy: np.ndarray, packages_dir: Path | None, cache_dir: Path, fetcher=fetch_bdl,
                rdlp: gpd.GeoDataFrame | None = None, log=print) -> StandIndex:
    """Indeks wydzielen wokol punktow `xy` (N x 2, EPSG:2180: E, N).

    Punkty pokryte wielokatem z paczki uzywaja paczek; dla reszty pobierane sa (lub czytane z cache)
    kafle WFS 10 km. Wydzielenie znane z paczki nie jest nadpisywane wersja z WFS."""
    xy = np.asarray(xy, dtype=float)
    pk = _read_packages(packages_dir, xy) if packages_dir and Path(packages_dir).is_dir() else \
        gpd.GeoDataFrame({"adr_for": [], "a_year": [], "nazwa": []}, geometry=[], crs=2180)
    covered = np.zeros(len(xy), dtype=bool)
    if len(pk):
        pts = gpd.points_from_xy(xy[:, 0], xy[:, 1])
        covered[pk.sindex.query(pts, predicate="intersects")[0]] = True
    frames = [pk[["adr_for", "a_year", "nazwa", "geometry"]]] if len(pk) else []
    uncovered = xy[~covered]
    if len(uncovered):
        tiles = sorted({(math.floor(n / TILE_M) * TILE_M, math.floor(e / TILE_M) * TILE_M) for e, n in uncovered})
        tiles = [(s, w, s + TILE_M, w + TILE_M) for s, w in tiles]
        log(f"  wydzielenia z WFS/cache dla {len(uncovered)} punktów poza paczkami ({len(tiles)} kafli 10 km)")
        rdlp = rdlp if rdlp is not None else fetch_rdlp_boundaries_cached(cache_dir)
        wfs, _ = fetch_search_stands(tiles, rdlp, cache_dir, fetcher)
        if len(wfs):
            if len(pk):
                have = set(zip(pk["adr_for"], pk["a_year"].astype(str)))
                wfs = wfs[[(a, str(y)) not in have for a, y in zip(wfs["adr_for"], wfs["a_year"])]]
            if "nazwa" not in wfs:
                wfs = wfs.assign(nazwa=None)
            frames.append(wfs[["adr_for", "a_year", "nazwa", "geometry"]])
    if not frames:
        return StandIndex(gpd.GeoDataFrame({"stand_id": [], "adr_for": [], "label": []}, geometry=[], crs=2180))
    allf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=2180)
    allf["adr_for"] = allf["adr_for"].astype(str)
    allf["stand_id"] = allf["adr_for"] + "@" + allf["a_year"].astype(str)
    d = allf.dissolve(by="stand_id", aggfunc={"adr_for": "first", "nazwa": "first"}).reset_index()
    d["label"] = [
        stand_label(a, district_name("-".join(a.split("-")[:2]), n)) for a, n in zip(d["adr_for"], d["nazwa"])
    ]
    return StandIndex(d[["stand_id", "adr_for", "label", "geometry"]])


# ---------------------------------------------------------------- przypisanie znalezisk

def assign_find(index: StandIndex, lon: float, lat: float, accuracy_m: float | None) -> dict:
    """Wydzielenie znaleziska + odleglosc od granicy i znacznik "blisko granicy" (odl. < dokladnosc GPS,
    a gdy brak dokladnosci < 25 m)."""
    x, y = to_2180(lon, lat)[0]
    i = index.locate(x, y)
    if i is None:
        return {"label": NO_STAND_LABEL, "stand_id": None, "boundary_m": None, "near_boundary": None}
    dist = index.boundary_distance(x, y, i)
    limit = accuracy_m if accuracy_m else DEFAULT_ACCURACY_M
    return {"label": index.label(i), "stand_id": index.ids[i], "boundary_m": dist, "near_boundary": dist < limit}


# ---------------------------------------------------------------- slad

def parse_route(row: dict) -> dict | None:
    """Wiersz routes.csv -> {'lonlat': [(lon, lat)], 'times_ms': [int], 'acc': [float|None], ...}; None gdy nieczytelny."""
    try:
        coords = json.loads(row["track_geojson"])["coordinates"]
        times = [int(t) for t in json.loads(row["point_times_ms"])]
        acc = [None if a in (None, "") else float(a) for a in json.loads(row["point_accuracies"] or "[]")]
    except (KeyError, ValueError, TypeError):
        return None
    if len(coords) < 2 or len(coords) != len(times):
        return None
    if len(acc) != len(coords):
        acc = [None] * len(coords)
    def _f(k):
        try:
            return float(row[k])
        except (KeyError, ValueError, TypeError):
            return None
    return {
        "lonlat": [(float(c[0]), float(c[1])) for c in coords], "times_ms": times, "acc": acc,
        "distance_m": _f("distance_m"), "duration_s": _f("duration_s"),
    }


def snap_bad_points(xy: np.ndarray, times_ms: list[int], accuracies: list | None,
                    max_accuracy_m: float = LOW_ACCURACY_M) -> np.ndarray:
    """Pozycje punktow o dokladnosci gorszej niz `max_accuracy_m` zastepuje pozycja najblizszego w czasie dobrego
    punktu (czas odcinka trafia wiec do wydzielenia, w ktorym byl dobry punkt). Punkty bez podanej dokladnosci
    sa traktowane jak dobre. Gdy nie ma zadnego dobrego punktu, zwraca `xy` bez zmian."""
    xy = np.asarray(xy, dtype=float)
    if not accuracies:
        return xy
    bad = np.array([a is not None and a > max_accuracy_m for a in accuracies])
    if not bad.any() or bad.all():
        return xy
    t = np.asarray(times_ms, dtype=float)
    good_idx = np.flatnonzero(~bad)
    out = xy.copy()
    for i in np.flatnonzero(bad):
        out[i] = xy[good_idx[np.argmin(np.abs(t[good_idx] - t[i]))]]
    return out


def time_in_stands(index: StandIndex, xy: np.ndarray, times_ms: list[int], gap_s: float = GAP_S,
                   accuracies: list | None = None) -> dict:
    """Czas sladu w kazdym wydzieleniu.

    Punkty z dokladnoscia > 50 m (`accuracies`) nie wyznaczaja polozenia: patrz `snap_bad_points`.

    Czas kazdego odcinka miedzy sasiednimi punktami dzieli sie na wydzielenia proporcjonalnie do dlugosci
    odcinka w kazdym z nich. Odcinki z przerwa > `gap_s` nie licza sie do czasu (ich koncowe punkty nadal
    zaliczaja wydzielenie do "przechodzonych"). Zwraca {'seconds': {stand_id: s}, 'touched': {stand_id},
    'unmatched_s', 'gap_s', 'counted_s'}."""
    xy = snap_bad_points(xy, times_ms, accuracies)
    seconds = defaultdict(float)
    touched = set()
    unmatched = 0.0
    gap_total = 0.0
    located = [index.locate(x, y) for x, y in xy]
    touched.update(index.ids[i] for i in located if i is not None)
    for k in range(len(xy) - 1):
        dt = (times_ms[k + 1] - times_ms[k]) / 1000.0
        if dt <= 0:
            continue
        if dt > gap_s:
            gap_total += dt
            continue
        seg = LineString([tuple(xy[k]), tuple(xy[k + 1])])
        length = seg.length
        if length < 0.5:  # stoi w miejscu
            i = located[k]
            if i is None:
                unmatched += dt
            else:
                seconds[index.ids[i]] += dt
            continue
        parts = {}
        if index.tree is not None:
            for c in index.tree.query(seg, predicate="intersects"):
                inter = index.geoms[int(c)].intersection(seg).length
                if inter > 0:
                    parts[int(c)] = inter
        covered = sum(parts.values())
        denom = max(length, covered)
        unmatched += dt * max(0.0, length - covered) / denom
        for c, inter in parts.items():
            seconds[index.ids[c]] += dt * inter / denom
            if inter >= MIN_CROSSING_M:
                touched.add(index.ids[c])
    return {
        "seconds": dict(seconds), "touched": touched, "unmatched_s": unmatched, "gap_s": gap_total,
        "counted_s": sum(seconds.values()),
    }


# ---------------------------------------------------------------- GPX

def _iso_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def gpx_text(name: str, route: dict, low_accuracy_m: float = LOW_ACCURACY_M) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Borowik (scripts/aktualizuj_dziennik.py)" '
        'xmlns="http://www.topografix.com/GPX/1/1" xmlns:b="https://borowik.invalid/gpx/1">',
        f"<metadata><name>{escape(name)}</name><time>{_iso_utc(route['times_ms'][0])}</time></metadata>",
        f"<trk><name>{escape(name)}</name><trkseg>",
    ]
    for (lon, lat), t, a in zip(route["lonlat"], route["times_ms"], route["acc"]):
        low = a is not None and a > low_accuracy_m
        pt = f"<trkpt lat={quoteattr(f'{lat:.7f}')} lon={quoteattr(f'{lon:.7f}')}><time>{_iso_utc(t)}</time>"
        if low:
            pt += f"<cmt>niska dokladnosc GPS: {a:g} m (> {low_accuracy_m:g} m)</cmt>"
        if a is not None:
            pt += f"<extensions><b:accuracy_m>{a:g}</b:accuracy_m><b:low_accuracy>{'true' if low else 'false'}</b:low_accuracy></extensions>"
        lines.append(pt + "</trkpt>")
    lines.append("</trkseg></trk></gpx>")
    return "\n".join(lines) + "\n"


def write_gpx(path: Path, name: str, route: dict) -> int:
    """Zapisuje GPX (atomowo); zwraca liczbe punktow z dokladnoscia > 50 m."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(gpx_text(name, route), encoding="utf-8", newline="\n")
    tmp.replace(path)
    return sum(1 for a in route["acc"] if a is not None and a > LOW_ACCURACY_M)
