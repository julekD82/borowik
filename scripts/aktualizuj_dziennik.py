"""Dziennik wyjść: dopisuje do dane_terenowe/dziennik_wyjsc.xlsx nowe wyjścia i znaleziska z eksportów Shroomera.

Eksporty leżą w dane_terenowe/shroomer/surowe/<podkatalog>/ (trips.csv, routes.csv, finds.csv, car_locations.csv)
i nigdy nie są edytowane. Dziennik jest źródłem prawdy dla poprawek i notatek.

Zasady:
- rozpoznawanie po id z Shroomera: wiersz już obecny w dzienniku nie jest ponownie dopisywany ani zmieniany
  (żadna wartość uzupełniona ręcznie nie jest nadpisywana),
- wyjścia i znaleziska, których nie ma już w najnowszym eksporcie, tylko dostają znacznik w kolumnie
  „stan w Shroomerze” (wrócą do „aktualne”, jeśli pojawią się ponownie),
- przeliczane są wyłącznie kolumny tylko do odczytu (liczniki znalezisk i borowików, w tym w arkuszu
  „Wydzielenia na trasie”); pola uzupełnione przez użytkownika, także w kolumnach tylko do odczytu, zostają,
- dla wyjść: czas trwania i plik GPX (dane_terenowe/trasy/, z czasami punktów; punkty z dokładnością > 50 m
  oznaczone); dla znalezisk: lat, lon, dokładność GPS, wydzielenie BDL (paczki, a gdzie ich brak — WFS),
  „blisko granicy”; arkusz „Wydzielenia na trasie”: czas w każdym wydzieleniu, przez które przechodzi ślad,
- przed zapisem powstaje kopia dziennik_wyjsc.xlsx.bak; jeśli plik jest otwarty w Excelu, skrypt nic nie zmienia.

Uruchomienie (potrzebne geopandas z .venv projektu):
    .venv/Scripts/python.exe scripts/aktualizuj_dziennik.py [--dry-run] [--katalog dane_terenowe]
Jeśli dziennika jeszcze nie ma, zostanie utworzony.
"""
import argparse
import csv
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

TZ = ZoneInfo("Europe/Warsaw")
S_WYJ, S_ZNAL, S_TRASA, S_LISTY = "Wyjścia", "Znaleziska", "Wydzielenia na trasie", "Listy"
AKTUALNE = "aktualne"
MAX_ROW_VALIDATION = 3000  # listy rozwijane obejmują wiersze do tego numeru

RO, FILL, META = "ro", "fill", "meta"
# (nagłówek, szerokość, rodzaj, opcjonalna lista rozwijana / podpowiedź)
WYJ_COLS = [
    ("id wyjścia", 38, RO),
    ("data", 11, RO),
    ("start", 8, RO),
    ("koniec", 8, RO),
    ("nazwa (Shroomer)", 26, RO),
    ("notatka (Shroomer)", 30, RO),
    ("długość trasy [km]", 11, RO),
    ("znalezisk ogółem [szt.]", 12, RO),
    ("w tym borowików [szt.]", 12, RO),
    ("powód wyboru", 16, FILL, ["aplikacja", "znane miejsce", "przypadek", "mieszane"]),
    ("ślady innych grzybiarzy", 15, FILL, ["brak", "pojedyncze", "liczne"]),
    ("widziani ludzie", 11, FILL, ["tak", "nie"]),
    ("wilgotność ściółki", 15, FILL, ["sucho", "lekko wilgotno", "mokro"]),
    ("stan owocników", 17, FILL, ["głównie młode", "mieszane", "głównie stare", "brak"]),
    ("inne grzyby", 11, FILL, ["brak", "mało", "dużo"]),
    ("migawka Borowika", 26, FILL, "Tekst: id lub nazwa zapisanej migawki z dnia wyjścia "
                                   "(frontend/public/data/trips/index.json)."),
    ("z pamięci", 10, FILL, ["tak", "nie"]),
    ("uwagi", 44, FILL, "Tekst dowolny."),
    ("stan w Shroomerze", 34, META),
    ("eksport", 12, META),
    ("czas trwania [min]", 12, RO),
    ("plik GPX", 40, RO),
]
ZNAL_COLS = [
    ("id", 38, RO),
    ("data", 11, RO),
    ("godzina", 8, RO),
    ("id wyjścia", 38, RO),
    ("gatunek (Shroomer)", 24, RO),
    ("nazwa łacińska (Shroomer)", 26, RO),
    ("liczba", 8, RO),
    ("waga [g]", 9, RO),
    ("gatunek poprawiony", 26, FILL, "GATUNKI"),
    ("stan w Shroomerze", 34, META),
    ("eksport", 12, META),
    ("lat", 11, RO),
    ("lon", 11, RO),
    ("dokładność GPS [m]", 11, RO),
    ("wydzielenie", 30, RO),
    ("stand_id", 30, RO),
    ("odl. od granicy wydzielenia [m]", 14, RO),
    ("blisko granicy", 10, RO),
]
TRASA_COLS = [
    ("id wyjścia", 38, RO),
    ("data", 11, RO),
    ("wydzielenie", 30, RO),
    ("stand_id", 30, RO),
    ("czas w wydzieleniu [min]", 13, RO),
    ("borowików [szt.]", 11, RO),
    ("znalezisk ogółem [szt.]", 12, RO),
    ("uwagi", 46, RO),
]
# kolumny dodane po pierwszej wersji dziennika: brakujące w istniejącym pliku są dopisywane na końcu arkusza
NOWE_KOLUMNY = {
    S_WYJ: {"czas trwania [min]", "plik GPX"},
    S_ZNAL: {"lat", "lon", "dokładność GPS [m]", "wydzielenie", "stand_id", "odl. od granicy wydzielenia [m]",
             "blisko granicy"},
}
NOTE_ONLY_FINDS = "tylko znaleziska — ślad nie przechodzi przez to wydzielenie (albo brak śladu)"
GPX_DIR = "trasy"

FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_GREY = Font(name=FONT, size=10, color="595959")
F_DEL = Font(name=FONT, size=10, color="C00000")
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_HEAD_FILL = Font(name=FONT, size=10, bold=True, color="000000")
FILL_RO = PatternFill("solid", fgColor="F2F2F2")
FILL_IN = PatternFill("solid", fgColor="FFF2CC")
FILL_H_RO = PatternFill("solid", fgColor="44546A")
FILL_H_IN = PatternFill("solid", fgColor="FFC000")
FILL_H_META = PatternFill("solid", fgColor="7F7F7F")

PL_ALFABET = "aąbcćdeęfghijklłmnńoóprsśtuwyzźż"


def pl_key(s):
    return [PL_ALFABET.find(c) if c in PL_ALFABET else ord(c) + 100 for c in s.casefold()]


# ---------------------------------------------------------------- odczyt eksportów

def norm(v):
    v = (v or "").strip()
    return "" if v.lower() == "null" else v


def parse_ts(s):
    """'2026-09-20 12:46:17.721+00' -> aware datetime (czas lokalny Europe/Warsaw)."""
    s = norm(s)
    if not s:
        return None
    m = re.match(r"(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d(?::?\d\d)?)?$", s)
    if not m:
        raise ValueError(f"nieznany format czasu: {s!r}")
    d, t, frac, tz = m.groups()
    frac = (frac or "0").ljust(6, "0")[:6]
    if tz in (None, "Z"):
        tz = "+00:00"
    elif len(tz) == 3:
        tz += ":00"
    elif len(tz) == 5:
        tz = tz[:3] + ":" + tz[3:]
    return datetime.fromisoformat(f"{d}T{t}.{frac}{tz}").astimezone(TZ)


def num(s):
    s = norm(s)
    if not s:
        return None
    x = float(s)
    return int(x) if x == int(x) else x


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def list_exports(surowe):
    return sorted(p for p in surowe.iterdir() if p.is_dir() and (p / "trips.csv").exists())


def load_exports(exports):
    """Zwraca (trips, finds, ids_najnowszy). Dane każdego id pochodzą z najnowszego eksportu, w którym występuje."""
    trips, finds, routes = {}, {}, {}
    for ex in exports:
        for r in read_csv(ex / "trips.csv"):
            trips[r["id"]] = (r, ex.name)
        for r in read_csv(ex / "finds.csv"):
            finds[r["id"]] = (r, ex.name)
        rp = ex / "routes.csv"
        if rp.exists():
            for r in read_csv(rp):
                routes[r["trip_id"]] = r
    latest = exports[-1]
    latest_trips = {r["id"] for r in read_csv(latest / "trips.csv")}
    latest_finds = {r["id"] for r in read_csv(latest / "finds.csv")}
    return trips, finds, routes, latest.name, latest_trips, latest_finds


# ---------------------------------------------------------------- skoroszyt

def write_header(ws, i, col):
    name, width, kind = col[0], col[1], col[2]
    c = ws.cell(1, i, name)
    c.font = {RO: F_HEAD, FILL: F_HEAD_FILL, META: F_HEAD}[kind]
    c.fill = {RO: FILL_H_RO, FILL: FILL_H_IN, META: FILL_H_META}[kind]
    c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.column_dimensions[get_column_letter(i)].width = width
    if kind == FILL:
        hint = col[3]
        if isinstance(hint, list):
            hint = "Do uzupełnienia. Wybierz z listy: " + " / ".join(hint) + "."
        elif hint == "GATUNKI":
            hint = "Do uzupełnienia. Puste = bez zmiany gatunku z Shroomera."
        else:
            hint = "Do uzupełnienia. " + hint
        c.comment = Comment(hint, "Borowik", width=260, height=90)


def polish_header(ws, cols):
    for i, col in enumerate(cols, 1):
        write_header(ws, i, col)
    ws.row_dimensions[1].height = 42
    ws.freeze_panes = "A2"


def _validated_columns(ws):
    """Numery kolumn objętych jakąkolwiek listą rozwijaną w arkuszu."""
    cols = set()
    for dv in ws.data_validations.dataValidation:
        for rng in dv.sqref.ranges:
            cols.update(range(rng.min_col, rng.max_col + 1))
    return cols


def add_validations(ws, cols, species_range):
    """Dodaje listy rozwijane w żółtych kolumnach, które ich jeszcze nie mają. Po zapisie w Excelu lista gatunków
    (odwołanie do innego arkusza) trafia do rozszerzenia x14, którego openpyxl nie wczytuje — ten krok ją odtwarza."""
    covered = _validated_columns(ws)
    for i, col in enumerate(cols, 1):
        if col[2] != FILL or i in covered:
            continue
        opts = col[3]
        letter = get_column_letter(i)
        rng = f"{letter}2:{letter}{MAX_ROW_VALIDATION}"
        if isinstance(opts, list):
            dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"', allow_blank=True,
                                showErrorMessage=True, errorTitle="Niedozwolona wartość",
                                error="Wybierz wartość z listy: " + ", ".join(opts) + ".")
        elif opts == "GATUNKI":
            dv = DataValidation(type="list", formula1=species_range, allow_blank=True,
                                showErrorMessage=True, errorStyle="warning", errorTitle="Gatunek spoza listy",
                                error="Tego gatunku nie ma na liście (arkusz Listy). Zostawić mimo to?")
        else:
            continue
        dv.add(rng)
        ws.add_data_validation(dv)


def new_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = S_WYJ
    polish_header(ws, WYJ_COLS)
    add_validations(ws, WYJ_COLS, None)
    wz = wb.create_sheet(S_ZNAL)
    polish_header(wz, ZNAL_COLS)
    add_validations(wz, ZNAL_COLS, f"={S_LISTY}!$A$2:$A$300")
    polish_header(wb.create_sheet(S_TRASA), TRASA_COLS)
    wl = wb.create_sheet(S_LISTY)
    wl.sheet_properties.tabColor = "A6A6A6"
    wl["A1"] = "gatunki (lista dla „gatunek poprawiony”)"
    wl["A1"].font = F_HEAD
    wl["A1"].fill = FILL_H_RO
    wl.column_dimensions["A"].width = 34
    legenda = [
        "Legenda",
        "Żółte kolumny (pomarańczowy nagłówek) — do uzupełnienia przez Ciebie.",
        "Szare kolumny (ciemny nagłówek) — z Shroomera, nie edytuj; przy kolejnym eksporcie nie są nadpisywane.",
        "Kolumny „stan w Shroomerze” i „eksport” ustawia skrypt scripts/aktualizuj_dziennik.py.",
        "Arkusz „Wydzielenia na trasie” jest w całości z obliczeń (tylko do odczytu).",
        "Kolumna A (gatunki) zasila listę „gatunek poprawiony”; możesz dopisać własny gatunek na końcu.",
        "Opis i zasady: docs/ZAPIS_WYJSC.md.",
    ]
    for i, t in enumerate(legenda, 1):
        c = wl.cell(i, 3, t)
        c.font = Font(name=FONT, size=10, bold=(i == 1))
    wl.column_dimensions["C"].width = 100
    return wb


def headers(ws):
    return {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}


def check_headers(ws, cols):
    """Zwraca {nagłówek: numer kolumny}. Kolumny z NOWE_KOLUMNY, których jeszcze nie ma, są dopisywane na końcu
    (istniejące kolumny i wiersze nie są ruszane); brak jakiejkolwiek innej kolumny to błąd."""
    h = headers(ws)
    nowe = NOWE_KOLUMNY.get(ws.title, set())
    missing = [c[0] for c in cols if c[0] not in h and c[0] not in nowe]
    if missing:
        sys.exit(f"Arkusz „{ws.title}”: brak kolumn {missing}. Nie zmieniaj nazw nagłówków w pierwszym wierszu.")
    for col in cols:
        if col[0] in h:
            continue
        i = max(h.values()) + 1
        write_header(ws, i, col)
        h[col[0]] = i
        for r in range(2, last_data_row(ws) + 1):
            style_ro(ws.cell(r, i))
    return h


def last_data_row(ws):
    for r in range(ws.max_row, 1, -1):
        if ws.cell(r, 1).value not in (None, ""):
            return r
    return 1


def style_row(ws, r, cols):
    for i, col in enumerate(cols, 1):
        c = ws.cell(r, i)
        kind = col[2]
        c.font = F_GREY if kind in (RO, META) else F_BASE
        c.fill = FILL_IN if kind == FILL else FILL_RO
        c.alignment = Alignment(vertical="top", wrap_text=col[0] in ("notatka (Shroomer)", "uwagi", "migawka Borowika"))


def empty(v):
    return v is None or v == ""


def style_ro(c, fmt=None):
    c.font, c.fill = F_GREY, FILL_RO
    c.alignment = Alignment(vertical="top")
    if fmt:
        c.number_format = fmt


def set_ro(ws, r, h, name, value, fmt=None):
    c = ws.cell(r, h[name])
    c.value = value
    style_ro(c, fmt)


def put(ws, r, h, name, value, fmt=None):
    c = ws.cell(r, h[name], value)
    if fmt:
        c.number_format = fmt


def mark_state(ws, h, latest_ids, latest_name, deleted_text, stats_key, stats):
    """Ustawia „stan w Shroomerze” dla wierszy pochodzących z Shroomera; zwraca liczbę nowo oznaczonych."""
    idc, ec, sc = 1, h["eksport"], h["stan w Shroomerze"]
    for r in range(2, last_data_row(ws) + 1):
        if ws.cell(r, ec).value in (None, ""):
            continue  # wiersz dopisany ręcznie, nie z Shroomera
        rid = ws.cell(r, idc).value
        cur = ws.cell(r, sc)
        if rid in latest_ids:
            if cur.value != AKTUALNE:
                if cur.value:
                    stats[stats_key + "_przywrocone"] += 1
                cur.value, cur.font = AKTUALNE, F_GREY
        else:
            txt = deleted_text(rid, latest_name)
            if not (cur.value or "").startswith(txt.split(" (")[0]):
                stats[stats_key + "_oznaczone"] += 1
                cur.value = f"{txt} (eksport {latest_name})"
            cur.font = F_DEL

_GEO = None


def geo():
    """Moduł geometrii (geopandas) ładowany dopiero, gdy jest potrzebny."""
    global _GEO
    if _GEO is None:
        try:
            from pipeline import dziennik_geo as g
        except ImportError as e:
            sys.exit(f"Brak biblioteki geograficznej ({e}). Uruchom skrypt interpreterem z .venv projektu: "
                     r".venv\Scripts\python.exe scripts\aktualizuj_dziennik.py")
        _GEO = g
    return _GEO


def eff_species(wz, hz, r):
    """Gatunek obowiązujący: „gatunek poprawiony”, a gdy pusty — gatunek z Shroomera."""
    fixed = str(wz.cell(r, hz["gatunek poprawiony"]).value or "").strip()
    return fixed or str(wz.cell(r, hz["gatunek (Shroomer)"]).value or "").strip()


def is_deleted(wz, hz, r):
    return str(wz.cell(r, hz["stan w Shroomerze"]).value or "").startswith("usunięte")


def fill_routes(ww, hw, trips, routes, base, stats, dry_run):
    """Długość trasy, czas trwania i plik GPX dla wyjść, które mają ślad w eksporcie (tylko puste pola)."""
    parsed = {}
    for r in range(2, last_data_row(ww) + 1):
        tid = ww.cell(r, 1).value
        if tid not in routes:
            continue
        if tid not in parsed:
            parsed[tid] = geo().parse_route(routes[tid])
        rt = parsed[tid]
        if rt is None:
            continue
        if empty(ww.cell(r, hw["długość trasy [km]"]).value) and rt["distance_m"] is not None:
            set_ro(ww, r, hw, "długość trasy [km]", round(rt["distance_m"] / 1000, 2), "0.00")
            stats["uzupelnione_dlugosci"] += 1
        if empty(ww.cell(r, hw["czas trwania [min]"]).value) and rt["duration_s"] is not None:
            set_ro(ww, r, hw, "czas trwania [min]", round(rt["duration_s"] / 60, 1), "0.0")
            stats["uzupelnione_czasy"] += 1
        rel = ww.cell(r, hw["plik GPX"]).value
        trip = trips.get(tid)
        if empty(rel):
            if not trip:
                continue
            start = parse_ts(trip[0]["started_at"])
            rel = f"{GPX_DIR}/{start:%Y-%m-%d_%H%M}_{tid[:8]}.gpx"
        if empty(ww.cell(r, hw["plik GPX"]).value) or not (base / rel).exists():
            if not dry_run:
                name = norm(trip[0].get("name")) if trip else ""
                geo().write_gpx(base / rel, f"{name or 'Wyjście'} {tid[:8]}", rt)
            set_ro(ww, r, hw, "plik GPX", rel)
            stats["nowe_gpx"] += 1
    return parsed


def compute_geo(ww, hw, wz, hz, wt, finds, parsed, stats):
    """Wydzielenie (BDL) dla znalezisk bez przypisania i czas śladu w wydzieleniach dla wyjść bez wierszy
    w arkuszu „Wydzielenia na trasie”. Zwraca listę nowych wierszy tego arkusza."""
    import numpy as np

    need_finds = []
    for r in range(2, last_data_row(wz) + 1):
        fid = wz.cell(r, 1).value
        if fid in finds and (empty(wz.cell(r, hz["lat"]).value) or empty(wz.cell(r, hz["wydzielenie"]).value)):
            f = finds[fid][0]
            try:
                need_finds.append((r, f, float(f["lat"]), float(f["lon"])))
            except (KeyError, ValueError):
                continue
    have_rows = {wt.cell(r, 1).value for r in range(2, last_data_row(wt) + 1)}
    need_trips = []
    for r in range(2, last_data_row(ww) + 1):
        tid = ww.cell(r, 1).value
        if tid not in have_rows and parsed.get(tid):
            need_trips.append((tid, parsed[tid]))
    if not need_finds and not need_trips:
        return []
    G = geo()
    parts = []
    if need_finds:
        parts.append(G.to_2180([x[3] for x in need_finds], [x[2] for x in need_finds]))
    tracks = {}
    for tid, rt in need_trips:
        lon, lat = zip(*rt["lonlat"])
        tracks[tid] = G.to_2180(lon, lat)
        parts.append(tracks[tid])
    from pipeline.local_config import resolve_bdl_packages_dir
    cache_dir = ROOT / "cache"
    print("Wydzielenia BDL: paczki + WFS...")
    idx = G.build_index(np.vstack(parts), resolve_bdl_packages_dir(None, cache_dir), cache_dir)
    for r, f, lat, lon in need_finds:
        a = G.assign_find(idx, lon, lat, num(f.get("accuracy_m")))
        set_ro(wz, r, hz, "lat", lat, "0.0000000")
        set_ro(wz, r, hz, "lon", lon, "0.0000000")
        set_ro(wz, r, hz, "dokładność GPS [m]", None if num(f.get("accuracy_m")) is None else round(num(f.get("accuracy_m")), 2), "0.0")
        set_ro(wz, r, hz, "wydzielenie", a["label"])
        set_ro(wz, r, hz, "stand_id", a["stand_id"])
        set_ro(wz, r, hz, "odl. od granicy wydzielenia [m]",
               None if a["boundary_m"] is None else round(a["boundary_m"], 1), "0.0")
        set_ro(wz, r, hz, "blisko granicy", None if a["near_boundary"] is None else ("tak" if a["near_boundary"] else "nie"))
        stats["znaleziska_z_wydzieleniem"] += 1
    labels = dict(zip(idx.ids, idx.stands["label"]))
    rows = []
    for tid, rt in need_trips:
        out = G.time_in_stands(idx, tracks[tid], rt["times_ms"], accuracies=rt["acc"])
        ids = sorted(set(out["touched"]) | set(out["seconds"]), key=lambda x: (-out["seconds"].get(x, 0.0), x))
        for sid in ids:
            rows.append({"trip": tid, "stand_id": sid, "label": labels[sid],
                         "minutes": round(out["seconds"].get(sid, 0.0) / 60, 1), "note": None})
        if out["unmatched_s"] > 0.5:
            rows.append({"trip": tid, "stand_id": "", "label": G.NO_STAND_LABEL,
                         "minutes": round(out["unmatched_s"] / 60, 1), "note": None})
        print(f"  wyjście {tid[:8]}: {len(ids)} wydzieleń, w wydzieleniach {out['counted_s'] / 60:.1f} min, "
              f"przerwy > 10 min (nie liczone): {out['gap_s'] / 60:.1f} min")
        stats["trasy_przeliczone"] += 1
    return rows


def update_trasa(wt, ht, ww, hw, wz, hz, new_rows, stats):
    """Dopisuje nowe wiersze arkusza „Wydzielenia na trasie” i przelicza w nim liczbę borowików i znalezisk
    (z arkusza Znaleziska, według gatunku obowiązującego). Znaleziska w wydzieleniu, przez które ślad nie
    przechodzi, dostają własny wiersz z zerowym czasem."""
    date_of = {ww.cell(r, 1).value: ww.cell(r, hw["data"]).value for r in range(2, last_data_row(ww) + 1)}
    total, boro, label = Counter(), Counter(), {}
    for r in range(2, last_data_row(wz) + 1):
        if is_deleted(wz, hz, r):
            continue
        key = (wz.cell(r, hz["id wyjścia"]).value, wz.cell(r, hz["stand_id"]).value or "")
        q = wz.cell(r, hz["liczba"]).value
        q = 1 if empty(q) else q
        total[key] += q
        if eff_species(wz, hz, r).casefold().startswith("borowik"):
            boro[key] += q
        label[key] = wz.cell(r, hz["wydzielenie"]).value or geo().NO_STAND_LABEL

    def append(trip, sid, lab, minutes, note):
        row = last_data_row(wt) + 1
        for i in range(1, len(TRASA_COLS) + 1):
            style_ro(wt.cell(row, i))
        set_ro(wt, row, ht, "id wyjścia", trip)
        set_ro(wt, row, ht, "data", date_of.get(trip), "yyyy-mm-dd")
        set_ro(wt, row, ht, "wydzielenie", lab)
        set_ro(wt, row, ht, "stand_id", sid or None)
        set_ro(wt, row, ht, "czas w wydzieleniu [min]", minutes, "0.0")
        set_ro(wt, row, ht, "uwagi", note)
        stats["nowe_wiersze_wydzielen"] += 1
        return row

    existing = {}
    for r in range(2, last_data_row(wt) + 1):
        existing[(wt.cell(r, 1).value, wt.cell(r, ht["stand_id"]).value or "")] = r
    for nr in new_rows:
        key = (nr["trip"], nr["stand_id"])
        if key not in existing:
            existing[key] = append(nr["trip"], nr["stand_id"], nr["label"], nr["minutes"], nr["note"])
    for key in total:
        if key not in existing:
            existing[key] = append(key[0], key[1], label[key], 0.0, NOTE_ONLY_FINDS)
    for key, r in existing.items():
        for name, val in (("borowików [szt.]", boro.get(key, 0)), ("znalezisk ogółem [szt.]", total.get(key, 0))):
            c = wt.cell(r, ht[name])
            if c.value != val:
                set_ro(wt, r, ht, name, val)
                stats["przeliczone_liczniki"] += 1


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--katalog", default=str(root / "dane_terenowe"), help="katalog dane_terenowe")
    ap.add_argument("--dry-run", action="store_true", help="tylko pokaż, co by się zmieniło")
    ap.add_argument("--przelicz-trasy", action="store_true",
                    help="wyczyść arkusz „Wydzielenia na trasie” i policz go od nowa (np. po zmianie reguł liczenia czasu)")
    args = ap.parse_args()

    base = Path(args.katalog)
    surowe = base / "shroomer" / "surowe"
    path = base / "dziennik_wyjsc.xlsx"
    if not surowe.is_dir():
        sys.exit(f"Brak katalogu z eksportami: {surowe}")
    exports = list_exports(surowe)
    if not exports:
        sys.exit(f"Brak eksportów (podkatalogów z trips.csv) w {surowe}")

    trips, finds, routes, latest_name, latest_trips, latest_finds = load_exports(exports)

    created = not path.exists()
    wb = new_workbook() if created else load_workbook(path)
    ww, wz, wl = wb[S_WYJ], wb[S_ZNAL], wb[S_LISTY]
    hw, hz = check_headers(ww, WYJ_COLS), check_headers(wz, ZNAL_COLS)
    stats = Counter()
    add_validations(ww, WYJ_COLS, None)
    add_validations(wz, ZNAL_COLS, f"={S_LISTY}!$A$2:$A$300")
    if S_TRASA not in wb.sheetnames:
        pos = wb.sheetnames.index(S_LISTY) if S_LISTY in wb.sheetnames else len(wb.sheetnames)
        polish_header(wb.create_sheet(S_TRASA, pos), TRASA_COLS)
        stats["nowy_arkusz_wydzielen"] += 1
    wt = wb[S_TRASA]
    ht = check_headers(wt, TRASA_COLS)
    if args.przelicz_trasy and last_data_row(wt) > 1:
        wt.delete_rows(2, wt.max_row)
        stats["arkusz_wydzielen_wyczyszczony"] += 1

    have_trips = {ww.cell(r, 1).value for r in range(2, last_data_row(ww) + 1)}
    have_finds = {wz.cell(r, 1).value for r in range(2, last_data_row(wz) + 1)}

    # --- nowe wyjścia
    new_trips = []
    for tid, (r, ex) in trips.items():
        if tid in have_trips:
            continue
        if norm(r.get("moje_wyjscie")).lower() == "false":
            stats["pominiete_cudze"] += 1
            continue
        if norm(r.get("status")) != "completed":
            stats["pominiete_niezakonczone"] += 1
            continue
        new_trips.append((parse_ts(r["started_at"]), tid, r, ex))
    new_trips.sort(key=lambda x: (x[0], x[1]))
    added_trip_ids = {t[1] for t in new_trips}

    row = last_data_row(ww)
    for start, tid, r, ex in new_trips:
        row += 1
        style_row(ww, row, WYJ_COLS)
        end = parse_ts(r.get("ended_at"))
        rt = routes.get(tid)
        dist = num(rt["distance_m"]) if rt else None
        put(ww, row, hw, "id wyjścia", tid)
        put(ww, row, hw, "data", start.date(), "yyyy-mm-dd")
        put(ww, row, hw, "start", start.time().replace(second=0, microsecond=0), "hh:mm")
        if end:
            put(ww, row, hw, "koniec", end.time().replace(second=0, microsecond=0), "hh:mm")
        put(ww, row, hw, "nazwa (Shroomer)", norm(r.get("name")) or None)
        put(ww, row, hw, "notatka (Shroomer)", norm(r.get("note")) or None)
        if dist is not None:
            put(ww, row, hw, "długość trasy [km]", round(dist / 1000, 2), "0.00")
        put(ww, row, hw, "stan w Shroomerze", AKTUALNE)
        put(ww, row, hw, "eksport", ex)
        stats["nowe_wyjscia"] += 1

    # --- nowe znaleziska (tylko z wyjść obecnych w dzienniku)
    known_trips = have_trips | added_trip_ids
    new_finds = []
    for fid, (r, ex) in finds.items():
        if fid in have_finds:
            continue
        if r["trip_id"] not in known_trips:
            stats["pominiete_znaleziska_bez_wyjscia"] += 1
            continue
        new_finds.append((parse_ts(r["found_at"]), fid, r, ex))
    new_finds.sort(key=lambda x: (x[0], x[1]))

    row = last_data_row(wz)
    for ts, fid, r, ex in new_finds:
        row += 1
        style_row(wz, row, ZNAL_COLS)
        put(wz, row, hz, "id", fid)
        put(wz, row, hz, "data", ts.date(), "yyyy-mm-dd")
        put(wz, row, hz, "godzina", ts.time().replace(microsecond=0), "hh:mm:ss")
        put(wz, row, hz, "id wyjścia", r["trip_id"])
        put(wz, row, hz, "gatunek (Shroomer)", norm(r.get("name_pl")) or norm(r.get("slug")) or None)
        put(wz, row, hz, "nazwa łacińska (Shroomer)", norm(r.get("name_latin")) or None)
        put(wz, row, hz, "liczba", num(r.get("quantity")))
        put(wz, row, hz, "waga [g]", num(r.get("weight_grams")))
        put(wz, row, hz, "stan w Shroomerze", AKTUALNE)
        put(wz, row, hz, "eksport", ex)
        stats["nowe_znaleziska"] += 1

    # --- oznaczenie usuniętych / przywróconych
    mark_state(ww, hw, latest_trips, latest_name, lambda rid, n: "usunięte w Shroomerze", "wyjscia", stats)
    mark_state(wz, hz, latest_finds, latest_name,
               lambda rid, n: "wyjście usunięte w Shroomerze" if rid_trip_gone(wz, hz, rid, latest_trips)
               else "usunięte w Shroomerze", "znaleziska", stats)

    # --- lista gatunków dla „gatunek poprawiony”: to, co już jest + wszystkie gatunki z eksportów
    species = {str(wl.cell(r, 1).value).strip() for r in range(2, wl.max_row + 1) if wl.cell(r, 1).value}
    export_species = {norm(r.get("name_pl")) or norm(r.get("slug")) for r, _ in finds.values()} - {""}
    stats["nowe_gatunki_na_liscie"] = len(export_species - species)
    for i, sp in enumerate(sorted(species | export_species, key=pl_key), 2):
        c = wl.cell(i, 1, sp)
        c.font = F_BASE

    # --- ślad: długość, czas trwania, GPX; wydzielenia znalezisk i śladu
    parsed = fill_routes(ww, hw, trips, routes, base, stats, args.dry_run)
    new_rows = compute_geo(ww, hw, wz, hz, wt, finds, parsed, stats)
    update_trasa(wt, ht, ww, hw, wz, hz, new_rows, stats)

    # --- kolumny tylko do odczytu: liczba znalezisk (bez pojedynczo usuniętych; z usuniętych wraz z wyjściem liczone)
    # i borowików, według gatunku obowiązującego („gatunek poprawiony”, a gdy pusty — z Shroomera)
    total, boro = Counter(), Counter()
    for r in range(2, last_data_row(wz) + 1):
        if is_deleted(wz, hz, r):
            continue
        trip = wz.cell(r, hz["id wyjścia"]).value
        q = wz.cell(r, hz["liczba"]).value
        q = 1 if q in (None, "") else q
        total[trip] += q
        if eff_species(wz, hz, r).casefold().startswith("borowik"):
            boro[trip] += q
    for r in range(2, last_data_row(ww) + 1):
        tid = ww.cell(r, 1).value
        for name, val in (("znalezisk ogółem [szt.]", total.get(tid, 0)), ("w tym borowików [szt.]", boro.get(tid, 0))):
            c = ww.cell(r, hw[name])
            if c.value != val:
                c.value = val
                stats["przeliczone_liczniki"] += 1

    for sheet, hh in ((ww, hw), (wz, hz), (wt, ht)):
        sheet.auto_filter.ref = f"A1:{get_column_letter(max(hh.values()))}{max(last_data_row(sheet), 2)}"

    # --- zapis
    print(f"Eksporty: {', '.join(e.name for e in exports)} (stan wzorcowy: {latest_name})")
    print(f"Nowe wyjścia: {stats['nowe_wyjscia']}, nowe znaleziska: {stats['nowe_znaleziska']}, "
          f"nowe gatunki na liście: {stats['nowe_gatunki_na_liscie']}")
    for k, label in [("wyjscia_oznaczone", "wyjścia oznaczone jako usunięte"),
                     ("znaleziska_oznaczone", "znaleziska oznaczone jako usunięte"),
                     ("wyjscia_przywrocone", "wyjścia przywrócone (znów w eksporcie)"),
                     ("znaleziska_przywrocone", "znaleziska przywrócone (znów w eksporcie)"),
                     ("pominiete_niezakonczone", "wyjścia pominięte (status inny niż completed)"),
                     ("pominiete_cudze", "wyjścia pominięte (moje_wyjscie = false)"),
                     ("pominiete_znaleziska_bez_wyjscia", "znaleziska pominięte (wyjście nie w dzienniku)"),
                     ("uzupelnione_dlugosci", "uzupełnione długości tras"),
                     ("uzupelnione_czasy", "uzupełnione czasy trwania"),
                     ("nowe_gpx", "zapisane pliki GPX (dane_terenowe/trasy/)"),
                     ("znaleziska_z_wydzieleniem", "znaleziska z przypisanym wydzieleniem"),
                     ("trasy_przeliczone", "trasy przeliczone na wydzielenia"),
                     ("nowe_wiersze_wydzielen", "nowe wiersze w „Wydzielenia na trasie”"),
                     ("przeliczone_liczniki", "przeliczone liczniki znalezisk")]:
        if stats[k]:
            print(f"  {label}: {stats[k]}")
    print_summary(ww, hw, wz, hz, wt, ht)
    if args.dry_run:
        print("--dry-run: nic nie zapisano.")
        return
    changed = created or any(stats.values())
    if not changed:
        print("Brak zmian, dziennik bez zapisu.")
        return
    tmp = path.with_name(path.stem + ".tmp.xlsx")
    wb.save(tmp)
    try:
        if path.exists():
            shutil.copy2(path, path.with_suffix(".xlsx.bak"))
        os.replace(tmp, path)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        sys.exit(f"Nie można zapisać {path.name} — plik jest otwarty w Excelu? Zamknij go i uruchom skrypt ponownie.")
    print(f"Zapisano: {path}")


def print_summary(ww, hw, wz, hz, wt, ht):
    rows = list(range(2, last_data_row(ww) + 1))
    minutes = sum(ww.cell(r, hw["czas trwania [min]"]).value or 0 for r in rows)
    on_track = [r for r in range(2, last_data_row(wt) + 1)
                if wt.cell(r, ht["stand_id"]).value and wt.cell(r, ht["uwagi"]).value != NOTE_ONLY_FINDS]
    distinct = {wt.cell(r, ht["stand_id"]).value for r in on_track}
    finds_rows = range(2, last_data_row(wz) + 1)
    near = sum(1 for r in finds_rows if wz.cell(r, hz["blisko granicy"]).value == "tak")
    assigned = sum(1 for r in finds_rows if wz.cell(r, hz["blisko granicy"]).value in ("tak", "nie"))
    print("Podsumowanie dziennika:")
    print(f"  wyjść: {len(rows)}, łączny czas: {minutes:.0f} min ({int(minutes // 60)} h {int(minutes % 60)} min)")
    print(f"  wydzieleń na trasach: {len(on_track)} (wyjście × wydzielenie), w tym {len(distinct)} różnych")
    print(f"  znalezisk blisko granicy: {near} z {assigned} z przypisanym wydzieleniem (wpisów)")


def rid_trip_gone(wz, hz, find_id, latest_trips):
    """Czy wyjście tego znaleziska zniknęło z najnowszego eksportu."""
    for r in range(2, last_data_row(wz) + 1):
        if wz.cell(r, 1).value == find_id:
            return wz.cell(r, hz["id wyjścia"]).value not in latest_trips
    return False


if __name__ == "__main__":
    main()
