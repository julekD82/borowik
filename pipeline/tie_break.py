from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.bdl import normalize_code

# Plan 2.1 "Zmiana 4" (user review 2026-09-25): ordinal preference among
# BDL veg_cover_cd (pokrycie gleby) values, verified against the
# Instrukcja Urzadzania Lasu "Wykaz skrotow i symboli stosowanych w
# opisach taksacyjnych" glossary (no in-package dictionary exists for this
# field -- confirmed absent from every f_*_dic.txt under
# cache/bdl_packages/*/). Meanings: ZAD=zadarniona (turfed), SZAD=silnie
# zadarniona (heavily turfed), SZCH=silnie zachwaszczona (heavily weedy),
# ZIEL=zielna (herbaceous), SCIO=sciola (needle/leaf litter),
# MSZ=mszysta (mossy), MSZC=mszysto-czernicowa (moss-bilberry),
# NAGA=naga (bare ground). MSZC/MSZ/SCIO (undisturbed forest floor) tier
# highest, ZAD/ZIEL (grassy/herbaceous, some disturbance) mid,
# SZAD/SZCH/NAGA (heavily disturbed/bare) lowest -- [E] ordinal preference
# for sorting only, not a validated ecological weight, never blended into H/R.
_VEG_COVER_LABELS = {
    "ZAD": "zadarniona",
    "SZAD": "silnie zadarniona",
    "SZCH": "silnie zachwaszczona",
    "ZIEL": "zielna",
    "SCIO": "ścioła",
    "MSZ": "mszysta",
    "MSZC": "mszysto-czernicowa",
    "NAGA": "naga",
}
_VEG_COVER_TIERS = {
    "MSZC": 1.0, "MSZ": 1.0, "SCIO": 1.0,
    "ZAD": 0.6, "ZIEL": 0.6,
    "SZAD": 0.2, "SZCH": 0.2, "NAGA": 0.2,
}
_NEUTRAL = 0.5  # missing data -- never penalized, never preferred


@dataclass(frozen=True)
class TieBreakRaw:
    """Raw per-wydzielenie inputs for compute_tie_break, from a BDL data
    package (plan 2.1 "Zmiana 4"). Deliberately its own module/dataclass,
    never imported by pipeline.orchestrate/habitat/scoring/mvp -- the same
    structural guarantee pipeline.bdl_package_details (B3) already uses,
    so this data cannot silently affect H/R_final."""

    veg_cover_cd: str | None
    standdensity_index: float | None


def veg_cover_label(veg_cover_cd: str | None) -> str | None:
    """Word form of a veg_cover_cd for display (details_{day}.json / the
    frontend card) -- no BDL dictionary exists for this field, so the 8
    codes seen in real Będziemyśl data are hard-coded here (see
    _VEG_COVER_LABELS' own comment for the source)."""
    if veg_cover_cd is None:
        return None
    return _VEG_COVER_LABELS.get(normalize_code(veg_cover_cd), veg_cover_cd)


def _veg_cover_score(veg_cover_cd: str | None) -> float:
    if veg_cover_cd is None:
        return _NEUTRAL
    return _VEG_COVER_TIERS.get(normalize_code(veg_cover_cd), _NEUTRAL)


def _density_index_score(standdensity_index: float | None) -> float:
    """Intermediate zadrzewienie (stand density index, f_arod_storey.
    standdensity_index on the DRZEW storey) preferred over very sparse or
    very dense stands, per user brief 2026-09-25 (Martinez-Pena et al.
    2012: too-sparse or too-dense stands are less productive, optimum
    intermediate). Real Będziemyśl DRZEW-storey data (n=13576, 100%
    filled): median 0.9, IQR 0.7-1.0, 92.9% <= 1.5, only 0.2% >= 2.0 --
    plateau across [0.7, 1.0], linear falloff to 0 at the edges (0.0 on
    the low side, 2.0 on the high side) -- [E] plan decision, ordinal
    preference for sorting only, not a validated ecological weight."""
    if standdensity_index is None:
        return _NEUTRAL
    idx = standdensity_index
    if 0.7 <= idx <= 1.0:
        return 1.0
    if idx < 0.7:
        return max(0.0, idx / 0.7)
    return max(0.0, 1.0 - (idx - 1.0) / 1.0)


def compute_tie_break(veg_cover_cd: str | None, standdensity_index: float | None) -> float:
    """0-1 ordinal secondary sort key (plan 2.1 "Zmiana 4") -- ground cover
    tier averaged with the density-index preference curve above. Used
    EXCLUSIVELY as a secondary sort key (pipeline.regions._summarize_cluster,
    frontend/src/model.ts's joinData) among wydzielenia whose R_final is
    otherwise tied at 2 decimal places -- never blended into H or R_final
    itself (see this module's own docstring for the structural, not just
    tested, guarantee)."""
    return 0.5 * _veg_cover_score(veg_cover_cd) + 0.5 * _density_index_score(standdensity_index)


def tie_break_for_stand(adr_for: str, index: dict[str, TieBreakRaw]) -> float:
    """Convenience wrapper for pipeline/prepare_trip.py's per-row loop --
    a stand whose adr_for isn't covered by any downloaded BDL package
    (index miss) gets the same neutral 0.5 compute_tie_break(None, None)
    would return for missing fields, never a crash."""
    raw = index.get(adr_for)
    if raw is None:
        return compute_tie_break(None, None)
    return compute_tie_break(raw.veg_cover_cd, raw.standdensity_index)


def _load_one_package(package_dir: Path) -> dict[str, TieBreakRaw]:
    g_subarea = gpd.read_file(package_dir / "G_SUBAREA.shp")[["a_i_num", "adr_for"]]
    g_subarea["a_i_num"] = g_subarea["a_i_num"].astype(str)
    g_subarea["adr_for"] = g_subarea["adr_for"].astype(str)
    # Same real-data quirk as pipeline.bdl_packages/bdl_package_details:
    # one wydzielenie can be stored as several G_SUBAREA rows.
    g_subarea = g_subarea.drop_duplicates(["a_i_num", "adr_for"])

    subarea = pd.read_csv(package_dir / "f_subarea.txt", sep="\t", dtype=str, encoding="utf-8")
    subarea["veg_cover_cd"] = subarea["veg_cover_cd"].str.strip().map(normalize_code)
    subarea = subarea.rename(columns={"arodes_int_num": "a_i_num"})
    subarea["a_i_num"] = subarea["a_i_num"].astype(str)
    subarea_joined = subarea.merge(g_subarea, on="a_i_num", how="inner")
    # A present row can still have a blank veg_cover_cd CELL -- reads as
    # pandas NaN (float), not "" (same class of bug already fixed twice in
    # pipeline.bdl_package_details -- isinstance check, not truthiness).
    veg_cover_by_stand = {
        adr_for: (cd if isinstance(cd, str) and cd else None)
        for adr_for, cd in zip(subarea_joined["adr_for"], subarea_joined["veg_cover_cd"])
    }

    storey = pd.read_csv(package_dir / "f_arod_storey.txt", sep="\t", dtype=str, encoding="utf-8")
    storey = storey.rename(columns={"arodes_int_num": "a_i_num"})
    storey["a_i_num"] = storey["a_i_num"].astype(str)
    storey["storey_cd"] = storey["storey_cd"].str.strip()
    drzew_storey = storey[storey["storey_cd"] == "DRZEW"].merge(g_subarea, on="a_i_num", how="inner")
    density_index_by_stand: dict[str, float | None] = {}
    for adr_for, raw in zip(drzew_storey["adr_for"], drzew_storey["standdensity_index"]):
        density_index_by_stand[adr_for] = float(raw) if isinstance(raw, str) and raw.strip() else None

    all_adr_for = set(veg_cover_by_stand) | set(density_index_by_stand)
    return {
        adr_for: TieBreakRaw(
            veg_cover_cd=veg_cover_by_stand.get(adr_for),
            standdensity_index=density_index_by_stand.get(adr_for),
        )
        for adr_for in all_adr_for
    }


def load_tie_break_raw(packages_dir: Path) -> dict[str, TieBreakRaw]:
    """Auto-discovers every unpacked BDL data package under `packages_dir`
    (same directories pipeline.bdl_packages.load_packages /
    pipeline.bdl_package_details.load_package_details read) and indexes
    veg_cover_cd + standdensity_index by adr_for. Missing/empty directory,
    or a subdirectory missing the required files, returns {} / skips it,
    never raises -- pipeline.tie_break.tie_break_for_stand's neutral
    fallback handles the resulting misses."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    index: dict[str, TieBreakRaw] = {}
    required = ("G_SUBAREA.shp", "f_subarea.txt", "f_arod_storey.txt")
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        if not all((package_dir / name).exists() for name in required):
            continue
        index.update(_load_one_package(package_dir))
    return index
