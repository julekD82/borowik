"""Plan 2.1: walidacja wlasnych zapisow wyjsc (dane_terenowe/).

Tylko kontrola formalna i krotkie podsumowanie -- zadnej analizy skutecznosci
(to Faza 5). Katalog z prywatnymi danymi lezy poza repozytorium / w .gitignore.
"""
import csv
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUTING_COLUMNS = ["id_wyjscia", "data", "start", "koniec", "plik_gpx", "powod_wyboru", "id_migawki", "uwagi"]
FIND_COLUMNS = ["id_wyjscia", "lat", "lon", "gatunek", "liczba", "klasa_wieku"]
REASONS = {"aplikacja", "znane_miejsce", "przypadkowo", "mieszane"}
AGE_CLASSES = {"mlode", "dojrzale", "stare", "mieszane"}
OFF_TRACK_M = 300.0  # znalezisko dalej od sladu niz tyle -> ostrzezenie
GPX_GAP_S = 900  # luka miedzy sladem a czasem wyjscia, powyzej ktorej ostrzegamy
BOLETUS_NAMES = ("boletus edulis", "borowik", "prawdziwek")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    outings: int = 0
    hours: float = 0.0
    finds: int = 0
    boletus_count: int = 0


def _read_csv(path: Path, required: list[str], report: Report) -> list[dict]:
    if not path.exists():
        report.errors.append(f"Brak pliku {path.name}")
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            report.errors.append(f"{path.name}: brakuje kolumn {', '.join(missing)}")
            return []
        return list(reader)


def _parse_dt(day: str, hhmm: str) -> datetime | None:
    try:
        return datetime.strptime(f"{day.strip()} {hhmm.strip()}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def read_gpx(path: Path) -> list[tuple[datetime | None, float, float]]:
    """Punkty sladu: (czas lokalny Europe/Warsaw bez strefy albo None, lat, lon)."""
    points = []
    for el in ET.parse(path).getroot().iter():
        if el.tag.split("}")[-1] != "trkpt":
            continue
        t = None
        for child in el:
            if child.tag.split("}")[-1] == "time" and child.text:
                try:
                    t = (datetime.fromisoformat(child.text.strip().replace("Z", "+00:00"))
                         .astimezone(ZoneInfo("Europe/Warsaw")).replace(tzinfo=None))
                except ValueError:
                    t = None
        points.append((t, float(el.attrib["lat"]), float(el.attrib["lon"])))
    return points


def _dist_m(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742000 * math.asin(math.sqrt(a))


def _check_outing(row: dict, data_dir: Path, snapshot_ids: set | None, report: Report, tracks: dict) -> str | None:
    oid = (row.get("id_wyjscia") or "").strip()
    if not oid:
        report.errors.append("wyjscia.csv: wiersz bez id_wyjscia")
        return None
    start, end = _parse_dt(row["data"], row["start"]), _parse_dt(row["data"], row["koniec"])
    if start is None or end is None or end <= start:
        report.errors.append(f"{oid}: niepoprawna data/start/koniec (RRRR-MM-DD, GG:MM, koniec po starcie)")
    else:
        report.hours += (end - start).total_seconds() / 3600
    report.outings += 1
    if row["powod_wyboru"] not in REASONS:
        report.errors.append(f"{oid}: powod_wyboru musi byc jednym z {sorted(REASONS)}")
    mig = (row.get("id_migawki") or "").strip()
    if not mig:
        report.warnings.append(f"{oid}: brak id_migawki (nie da sie wskazac rankingu z tego dnia)")
    elif snapshot_ids is not None and mig not in snapshot_ids:
        report.errors.append(f"{oid}: migawka '{mig}' nie istnieje na liscie zapisanych map")
    gpx = (row.get("plik_gpx") or "").strip()
    if not gpx:
        report.warnings.append(f"{oid}: brak sladu GPX (nie da sie policzyc czasu w wydzieleniach)")
        return oid
    gpx_path = data_dir / gpx
    if not gpx_path.exists():
        report.errors.append(f"{oid}: brak pliku GPX {gpx}")
        return oid
    try:
        pts = read_gpx(gpx_path)
    except (ET.ParseError, KeyError, ValueError):
        report.errors.append(f"{oid}: nieczytelny GPX {gpx}")
        return oid
    tracks[oid] = pts
    times = [p[0] for p in pts if p[0] is not None]
    if not times:
        report.warnings.append(f"{oid}: GPX bez znacznikow czasu")
    elif start and end and ((min(times) - start).total_seconds() > GPX_GAP_S
                            or (end - max(times)).total_seconds() > GPX_GAP_S):
        report.warnings.append(f"{oid}: slad GPX nie pokrywa czasu wyjscia (luka > 15 min)")
    return oid


def validate(data_dir: Path, trips_dir: Path | None = None) -> Report:
    data_dir = Path(data_dir)
    report = Report()
    outings = _read_csv(data_dir / "wyjscia.csv", OUTING_COLUMNS, report)
    finds = _read_csv(data_dir / "znaleziska.csv", FIND_COLUMNS, report)

    snapshot_ids = None
    if trips_dir is not None and (Path(trips_dir) / "index.json").exists():
        snapshot_ids = {e["id"] for e in json.loads((Path(trips_dir) / "index.json").read_text(encoding="utf-8"))}

    tracks: dict[str, list] = {}
    seen: set[str] = set()
    for row in outings:
        oid = _check_outing(row, data_dir, snapshot_ids, report, tracks)
        if oid is None:
            continue
        if oid in seen:
            report.errors.append(f"{oid}: zdublowane id_wyjscia")
        seen.add(oid)

    for row in finds:
        oid = (row.get("id_wyjscia") or "").strip()
        if oid not in seen:
            report.errors.append(f"znaleziska.csv: nieznane id_wyjscia '{oid}'")
            continue
        try:
            lat, lon, n = float(row["lat"]), float(row["lon"]), int(row["liczba"])
        except ValueError:
            report.errors.append(f"{oid}: niepoprawne lat/lon/liczba w znalezisku")
            continue
        if row["klasa_wieku"] not in AGE_CLASSES:
            report.errors.append(f"{oid}: klasa_wieku musi byc jednym z {sorted(AGE_CLASSES)}")
        report.finds += 1
        if any(name in row["gatunek"].lower() for name in BOLETUS_NAMES):
            report.boletus_count += n
        pts = tracks.get(oid)
        if pts and min(_dist_m(lat, lon, p[1], p[2]) for p in pts) > OFF_TRACK_M:
            report.warnings.append(f"{oid}: znalezisko ({lat}, {lon}) lezy > {OFF_TRACK_M:.0f} m od sladu")
    return report


def summary_lines(report: Report) -> list[str]:
    lines = [f"Wyjsc: {report.outings}, godzin: {report.hours:.1f}, znalezisk: {report.finds}, "
             f"borowikow (sztuk): {report.boletus_count}"]
    lines += [f"BLAD: {e}" for e in report.errors] + [f"uwaga: {w}" for w in report.warnings]
    return lines
