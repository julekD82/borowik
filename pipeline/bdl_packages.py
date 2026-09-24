import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.bdl import normalize_code

# part_cd_act carries real 10-100% shares (1-10, f_part_dic) alongside two
# trace codes -- MJS ("below 5%, in patches") and PJD ("below 5%, single
# trees") -- that are deliberately NOT quantified. Only numeric rows enter
# S_host: verified on the real Kedzierzyn package (plan 2.1 step B2
# research) that numeric part_cd_act sums to exactly 10 per D-STAN stand's
# DRZEW storey for 100% of 2674 stands, so summing just the numeric rows
# needs no renormalization -- MJS/PJD rows correctly contribute nothing.
_NUMERIC_PART_CD = re.compile(r"^\d+$")


@dataclass(frozen=True)
class PackageComposition:
    """DRZEW-storey species composition for one wydzielenie from a BDL data
    package (plan 2.1 step B2, docs/bdl-paczki-rozpoznanie.md). `species` is
    [(normalized species_cd, share 0-1), ...] -- share is part_cd_act/10,
    numeric rows only. The same species can appear more than once (distinct
    age cohorts within an uneven-aged stand, verified in B2 research) --
    that's real, not a bug, and score_host_composition sums it correctly."""

    species: list[tuple[str, float]]
    source_name: str
    package_date: str | None


def _parse_metadane(path: Path) -> dict[str, str]:
    """metadane.txt is `Klucz: Wartość` lines (CRLF, UTF-8, values often
    padded with trailing spaces) -- verified against the real Kedzierzyn
    package in B1/B2 research."""
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _load_one_package(package_dir: Path) -> dict[str, PackageComposition]:
    g_subarea = gpd.read_file(package_dir / "G_SUBAREA.shp")[["a_i_num", "adr_for"]]
    g_subarea["a_i_num"] = g_subarea["a_i_num"].astype(str)
    g_subarea["adr_for"] = g_subarea["adr_for"].astype(str)

    species = pd.read_csv(package_dir / "f_storey_species.txt", sep="\t", dtype=str, encoding="utf-8")
    species["storey_cd"] = species["storey_cd"].str.strip()
    species["species_cd"] = species["species_cd"].str.strip().map(normalize_code)
    species["part_cd_act"] = species["part_cd_act"].str.strip()
    drzew = species[species["storey_cd"] == "DRZEW"].copy()
    drzew = drzew[drzew["part_cd_act"].str.match(_NUMERIC_PART_CD, na=False)]
    drzew["share"] = drzew["part_cd_act"].astype(int) / 10.0
    drzew = drzew.rename(columns={"arodes_int_num": "a_i_num"})
    drzew["a_i_num"] = drzew["a_i_num"].astype(str)

    joined = drzew.merge(g_subarea, on="a_i_num", how="inner")

    metadane_path = package_dir / "metadane.txt"
    package_date = None
    if metadane_path.exists():
        package_date = _parse_metadane(metadane_path).get("Data wytworzenia danych")

    result = {}
    for adr_for, group in joined.groupby("adr_for"):
        result[adr_for] = PackageComposition(
            species=list(zip(group["species_cd"], group["share"])),
            source_name=package_dir.name,
            package_date=package_date,
        )
    return result


def load_packages(packages_dir: Path) -> dict[str, PackageComposition]:
    """Auto-discovers every unpacked BDL data package under `packages_dir`
    (plan 2.1 step B2) -- each subdirectory is one package (directory name
    is free-form, not parsed; in practice BDL_<rdlp>_<nadl>_<NAME>_<year>,
    see docs/bdl-paczki-rozpoznanie.md), keyed by `adr_for` so callers can
    look a wydzielenie up directly, the same field pipeline.bdl.fetch_bdl's
    WFS rows carry (verified byte-identical in B1 research).

    A missing or empty directory returns {} rather than raising -- no
    package for a search area is a normal, expected state (spec fallback
    requirement), not an error."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    index: dict[str, PackageComposition] = {}
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        # A subdirectory without the two files this module actually reads
        # isn't a (complete) package -- skip it rather than raise, same
        # "missing package data never breaks the run" spirit as an absent
        # packages_dir entirely (e.g. a partially-unzipped or unrelated
        # directory under cache/bdl_packages/).
        if not (package_dir / "G_SUBAREA.shp").exists() or not (package_dir / "f_storey_species.txt").exists():
            continue
        index.update(_load_one_package(package_dir))
    return index
