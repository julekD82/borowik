import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.bdl import normalize_code

_NUMERIC_PART_CD = re.compile(r"^\d+$")


@dataclass(frozen=True)
class PackageStandDetails:
    """Card-display-only detail for one wydzielenie, from a BDL data package
    (plan 2.1 step B3, docs/archiwum/bdl-paczki-rozpoznanie.md). Deliberately
    separate from pipeline.bdl_packages.PackageComposition (the S_host/H
    scoring path, B2) -- this module is never imported by
    pipeline.orchestrate/habitat/scoring/mvp, which is the structural
    guarantee that loading these details cannot change R/H (spec §5.3 pkt
    3: "bez wpływu na R").

    `drzew_species`/`podszyt_species` are [(normalized species_cd, raw
    part_cd_act), ...] -- part_cd_act is kept as the raw code ("7", "MJS",
    "PJD") for the caller to render through pipeline.bdl_dictionaries'
    "part" table, not converted to a share here. `drzew_species` mirrors
    PackageComposition's numeric-only filter (for the same displayed
    figure); `podszyt_species` keeps every row, MJS/PJD included, since
    the understory list is informational, not a weighted formula."""

    drzew_species: list[tuple[str, str]]
    density_cd: str | None
    podszyt_species: list[tuple[str, str]]
    soil_subtype_cd: str | None
    source_name: str
    package_date: str | None


def _parse_metadane(path: Path) -> dict[str, str]:
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _species_rows(species_df: pd.DataFrame, storey_cd: str, numeric_only: bool) -> pd.DataFrame:
    rows = species_df[species_df["storey_cd"] == storey_cd].copy()
    if numeric_only:
        rows = rows[rows["part_cd_act"].str.match(_NUMERIC_PART_CD, na=False)]
    return rows


def _load_one_package(package_dir: Path) -> dict[str, PackageStandDetails]:
    g_subarea = gpd.read_file(package_dir / "G_SUBAREA.shp")[["a_i_num", "adr_for"]]
    g_subarea["a_i_num"] = g_subarea["a_i_num"].astype(str)
    g_subarea["adr_for"] = g_subarea["adr_for"].astype(str)
    # Same real-data quirk as pipeline.bdl_packages: one wydzielenie can be
    # stored as several G_SUBAREA rows (Strzyzow 2026 package). Only the id
    # mapping matters here, so dedupe before any join.
    g_subarea = g_subarea.drop_duplicates(["a_i_num", "adr_for"])

    species = pd.read_csv(package_dir / "f_storey_species.txt", sep="\t", dtype=str, encoding="utf-8")
    species["storey_cd"] = species["storey_cd"].str.strip()
    species["species_cd"] = species["species_cd"].str.strip().map(normalize_code)
    # A present row can have a blank part_cd_act CELL (no share recorded --
    # common for podszyt, whose rows are kept unfiltered below) -- that
    # reads as pandas NaN (float), not "". "" keeps the row (still real
    # presence information) while staying JSON-safe, unlike NaN (real-data
    # finding, Będziemyśl verification: 30050 such PODSZ rows).
    species["part_cd_act"] = species["part_cd_act"].str.strip().fillna("")
    species = species.rename(columns={"arodes_int_num": "a_i_num"})
    species["a_i_num"] = species["a_i_num"].astype(str)

    drzew = _species_rows(species, "DRZEW", numeric_only=True).merge(g_subarea, on="a_i_num", how="inner")
    podszyt = _species_rows(species, "PODSZ", numeric_only=False).merge(g_subarea, on="a_i_num", how="inner")
    drzew_by_stand = {
        adr_for: list(zip(g["species_cd"], g["part_cd_act"]))
        for adr_for, g in drzew.groupby("adr_for")
    }
    podszyt_by_stand = {
        adr_for: list(zip(g["species_cd"], g["part_cd_act"]))
        for adr_for, g in podszyt.groupby("adr_for")
    }

    storey = pd.read_csv(package_dir / "f_arod_storey.txt", sep="\t", dtype=str, encoding="utf-8")
    storey["storey_cd"] = storey["storey_cd"].str.strip()
    storey["density_cd"] = storey["density_cd"].str.strip().map(normalize_code)
    storey = storey.rename(columns={"arodes_int_num": "a_i_num"})
    storey["a_i_num"] = storey["a_i_num"].astype(str)
    drzew_storey = storey[storey["storey_cd"] == "DRZEW"].merge(g_subarea, on="a_i_num", how="inner")
    # A present row can still have a blank density_cd/soil_subtype_cd CELL --
    # dtype=str reads that as pandas NaN (float), not "", so a plain isinstance
    # check (rather than truthiness, which NaN also passes) is what actually
    # normalizes it to None (real-data finding, Będziemyśl verification).
    density_by_stand = {
        adr_for: (cd if isinstance(cd, str) else None)
        for adr_for, cd in zip(drzew_storey["adr_for"], drzew_storey["density_cd"])
    }

    subarea = pd.read_csv(package_dir / "f_subarea.txt", sep="\t", dtype=str, encoding="utf-8")
    subarea["soil_subtype_cd"] = subarea["soil_subtype_cd"].str.strip().map(normalize_code)
    subarea = subarea.rename(columns={"arodes_int_num": "a_i_num"})
    subarea["a_i_num"] = subarea["a_i_num"].astype(str)
    subarea_joined = subarea.merge(g_subarea, on="a_i_num", how="inner")
    soil_by_stand = {
        adr_for: (cd if isinstance(cd, str) and cd else None)
        for adr_for, cd in zip(subarea_joined["adr_for"], subarea_joined["soil_subtype_cd"])
    }

    metadane_path = package_dir / "metadane.txt"
    package_date = None
    if metadane_path.exists():
        package_date = _parse_metadane(metadane_path).get("Data wytworzenia danych")

    all_adr_for = set(drzew_by_stand) | set(podszyt_by_stand) | set(density_by_stand) | set(soil_by_stand)
    result = {}
    for adr_for in all_adr_for:
        result[adr_for] = PackageStandDetails(
            drzew_species=drzew_by_stand.get(adr_for, []),
            density_cd=density_by_stand.get(adr_for),
            podszyt_species=podszyt_by_stand.get(adr_for, []),
            # soil_by_stand's own values are already None/non-empty-string.
            soil_subtype_cd=soil_by_stand.get(adr_for),
            source_name=package_dir.name,
            package_date=package_date,
        )
    return result


def load_package_details(packages_dir: Path) -> dict[str, PackageStandDetails]:
    """Auto-discovers every unpacked BDL data package under `packages_dir`
    (same directories pipeline.bdl_packages.load_packages reads) and
    indexes card-display detail by `adr_for`. Missing/empty directory or a
    subdirectory missing the required files returns {} / skips it, never
    raises -- a stand without a package simply has no entry, and callers
    (pipeline.export.write_details_json) render its card without this
    section rather than erroring."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    index: dict[str, PackageStandDetails] = {}
    required = ("G_SUBAREA.shp", "f_storey_species.txt", "f_arod_storey.txt", "f_subarea.txt")
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        if not all((package_dir / name).exists() for name in required):
            continue
        index.update(_load_one_package(package_dir))
    return index
