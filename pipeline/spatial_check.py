"""Faza 2.4: H rekordu GBIF z wydzielen BDL w buforze (logika bez IO; patrz notebooks/13_walidacja_2_4.py).

Zasady (docs/WALIDACJA_REGULY.md + WALIDACJA_IMPLEMENTACJA.md): H wazone powierzchnia czesci
wydzielen D-STAN wewnatrz bufora; wydzielenie niespelniajace maski = H 0; H liczone kodem produkcyjnym.
"""
from dataclasses import dataclass

from shapely.geometry import Point

from pipeline.age_update import update_age
from pipeline.habitat import compute_habitat, passes_mask, score_host, score_host_composition

MIN_BUFFER_M = 10.0
ANALYSIS_YEAR = 2026


@dataclass
class RecordH:
    forest: bool              # przynajmniej jedno wydzielenie D-STAN przecina bufor
    h: float | None           # srednia wazona powierzchnia (maska = 0); None gdy brak lasu
    masked: bool              # wszystkie wazone wydzielenia D-STAN nie przechodza maski
    unknown_code: bool        # wydzielenie przechodzace maske z nieznanym kodem siedliska/gatunku
    main_stand: str | None    # adr_for wydzielenia o najwiekszym przecieciu (deduplikacja)
    h_package: float | None = None  # wariant: sklad pelny z paczki, gdzie paczka pokrywa wydzielenie
    n_stands: int = 0


def stand_h(row, profile: dict, package_index: dict | None = None) -> tuple[float, bool, bool, float | None]:
    """(H z WFS, maska ok, nieznany kod, H ze skladu z paczki lub None) dla jednego wydzielenia."""
    row = row.copy()
    age, _ = update_age(row.get("spec_age"), row.get("a_year"), ANALYSIS_YEAR, True)
    row["spec_age"] = age
    if not passes_mask(row, profile):
        return 0.0, False, False, (0.0 if package_index is not None else None)
    unknown = (row.get("site_type") not in profile["site_scores"]
               or row.get("species_cd") not in profile["host_affinity"])
    h = compute_habitat(row, profile)
    h = 0.0 if h is None else float(h)
    h_pkg = None
    if package_index:
        package = package_index.get(row.get("adr_for"))
        if package is not None:
            s_host, _ = score_host_composition(package.species, profile)
            h_pkg = compute_habitat(row, profile, s_host=s_host)
            h_pkg = 0.0 if h_pkg is None else float(h_pkg)
    return h, True, bool(unknown), h_pkg


def record_h(stands, e: float, n: float, radius_m: float, profile: dict, package_index: dict | None = None) -> RecordH:
    """`stands`: GeoDataFrame w EPSG:2180 (kolumny BDL). e, n: punkt rekordu w 2180."""
    buf = Point(e, n).buffer(max(radius_m, MIN_BUFFER_M))
    total = h_sum = pkg_sum = pkg_total = 0.0
    any_ok = unknown = False
    best_area, main_stand, count = 0.0, None, 0
    for _, row in stands.iterrows():
        if row.get("area_type") != "D-STAN":
            continue
        area = row.geometry.intersection(buf).area
        if area <= 0:
            continue
        h, ok, unk, h_pkg = stand_h(row, profile, package_index)
        total += area
        h_sum += area * h
        count += 1
        any_ok |= ok
        unknown |= unk
        if h_pkg is not None:
            pkg_sum += area * h_pkg
            pkg_total += area
        if area > best_area:
            best_area, main_stand = area, row.get("adr_for")
    if total == 0:
        return RecordH(False, None, False, False, None)
    return RecordH(True, h_sum / total, not any_ok, unknown, main_stand,
                   (pkg_sum / total) if pkg_total > 0 and pkg_total >= 0.999 * total else None, count)
