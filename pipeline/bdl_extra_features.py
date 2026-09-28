from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.bdl import normalize_code
from pipeline.compartment_boundary import compartment_boundary_features


@dataclass(frozen=True)
class ExtraStandFeatures:
    """Plan wdrozenia 1.6.4: BDL package fields that pass the >=50%
    fill-rate bar in docs/BDL_slownik_pol.md but have no ranking weight --
    diagnostics-only, exported for future evaluation (Faza 2.2/5/6), never
    read by pipeline.orchestrate/habitat/scoring/mvp (same structural "can't
    touch R" guarantee as pipeline.bdl_package_details/tie_break)."""

    veg_cover_cd: str | None
    site_class_cd: str | None  # bonitacja gatunku panujacego (DRZEW, sp_rank_order_act=1)
    density_cd: str | None  # zwarcie, warstwa DRZEW
    soil_subtype_cd: str | None
    degradation_cd: str | None  # stan/wariant siedliska -- no in-package dictionary, see słownik
    stand_struct_cd: str | None  # budowa pionowa drzewostanu -- no in-package dictionary
    podszyt_species: list[tuple[str, str]]  # (species_cd, raw part_cd_act) -- gęstość niedostępna (0% wypełnienia)
    podrost_species: list[tuple[str, str]]
    # Plan text asks for "wykonane/planowane z datami" -- the package only
    # has PLANNED indications (f_arod_cue), no execution table, and no date
    # finer than the whole package's a_year (rok_wskazan below). Recorded as
    # such, not inferred to have been carried out (docs/BDL_slownik_pol.md).
    zabiegi_planowane: list[dict]
    rok_wskazan: str | None
    dist_do_granicy_oddzialu_m: float | None
    dlugosc_granicy_z_oddzialem_m: float | None
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


def _clean(value):
    """A present cell can still be blank -- reads as pandas NaN (float), not
    "" (same isinstance-not-truthiness fix used throughout pipeline.bdl_*)."""
    return value if isinstance(value, str) and value.strip() else None


def _species_pairs(species_df: pd.DataFrame, storey_cd: str, g_subarea: pd.DataFrame) -> dict[str, list]:
    rows = species_df[species_df["storey_cd"] == storey_cd]
    joined = rows.merge(g_subarea, on="a_i_num", how="inner")
    return {
        adr_for: list(zip(g["species_cd"], g["part_cd_act"]))
        for adr_for, g in joined.groupby("adr_for")
    }


def _load_one_package(package_dir: Path) -> dict[str, ExtraStandFeatures]:
    g_subarea = gpd.read_file(package_dir / "G_SUBAREA.shp")[["a_i_num", "adr_for", "geometry"]]
    g_subarea["a_i_num"] = g_subarea["a_i_num"].astype(str)
    g_subarea["adr_for"] = g_subarea["adr_for"].astype(str)
    g_subarea = g_subarea.drop_duplicates(["a_i_num", "adr_for"])
    g_subarea_noattr = g_subarea[["a_i_num", "adr_for"]]

    subarea = pd.read_csv(package_dir / "f_subarea.txt", sep="\t", dtype=str, encoding="utf-8")
    subarea = subarea.rename(columns={"arodes_int_num": "a_i_num"})
    subarea["a_i_num"] = subarea["a_i_num"].astype(str)
    for col in ("veg_cover_cd", "soil_subtype_cd", "degradation_cd", "stand_struct_cd"):
        subarea[col] = subarea[col].str.strip().map(normalize_code)
    subarea_joined = subarea.merge(g_subarea_noattr, on="a_i_num", how="inner")
    subarea_by_stand = {
        row.adr_for: row for row in subarea_joined.itertuples()
    }

    species = pd.read_csv(package_dir / "f_storey_species.txt", sep="\t", dtype=str, encoding="utf-8")
    species["storey_cd"] = species["storey_cd"].str.strip()
    species["species_cd"] = species["species_cd"].str.strip().map(normalize_code)
    species["part_cd_act"] = species["part_cd_act"].str.strip().fillna("")
    species["sp_rank_order_act"] = species["sp_rank_order_act"].str.strip()
    species["site_class_cd"] = species["site_class_cd"].str.strip()
    species = species.rename(columns={"arodes_int_num": "a_i_num"})
    species["a_i_num"] = species["a_i_num"].astype(str)

    dominant = species[(species["storey_cd"] == "DRZEW") & (species["sp_rank_order_act"] == "1")]
    dominant_joined = dominant.merge(g_subarea_noattr, on="a_i_num", how="inner")
    bonitacja_by_stand = {
        adr_for: _clean(cd)
        for adr_for, cd in zip(dominant_joined["adr_for"], dominant_joined["site_class_cd"])
    }

    podszyt_by_stand = _species_pairs(species, "PODSZ", g_subarea_noattr)
    podrost_by_stand = _species_pairs(species, "PODR", g_subarea_noattr)

    storey = pd.read_csv(package_dir / "f_arod_storey.txt", sep="\t", dtype=str, encoding="utf-8")
    storey["storey_cd"] = storey["storey_cd"].str.strip()
    storey["density_cd"] = storey["density_cd"].str.strip()
    storey = storey.rename(columns={"arodes_int_num": "a_i_num"})
    storey["a_i_num"] = storey["a_i_num"].astype(str)
    drzew_storey = storey[storey["storey_cd"] == "DRZEW"].merge(g_subarea_noattr, on="a_i_num", how="inner")
    density_by_stand = {
        adr_for: _clean(cd)
        for adr_for, cd in zip(drzew_storey["adr_for"], drzew_storey["density_cd"])
    }

    cue = pd.read_csv(package_dir / "f_arod_cue.txt", sep="\t", dtype=str, encoding="utf-8")
    cue = cue.rename(columns={"arodes_int_num": "a_i_num"})
    cue["a_i_num"] = cue["a_i_num"].astype(str)
    cue_joined = cue.merge(g_subarea_noattr, on="a_i_num", how="inner")
    zabiegi_by_stand: dict[str, list] = {}
    rok_wskazan_by_stand: dict[str, str] = {}
    for adr_for, group in cue_joined.groupby("adr_for"):
        zabiegi_by_stand[adr_for] = [
            {
                "measure_cd": _clean(row.measure_cd.strip()) if isinstance(row.measure_cd, str) else None,
                "urgency": _clean(row.urgency.strip()) if isinstance(row.urgency, str) else None,
                "cutting_area": float(row.cutting_area) if _clean(row.cutting_area) else None,
            }
            for row in group.itertuples()
        ]
        rok_wskazan_by_stand[adr_for] = _clean(group["a_year"].iloc[0])

    compartment_path = package_dir / "G_COMPARTMENT.shp"
    boundary_by_stand: dict[str, tuple] = {}
    if compartment_path.exists():
        compartments = gpd.read_file(compartment_path)[["adr_for", "geometry"]]
        compartments["adr_for"] = compartments["adr_for"].astype(str)
        boundary_by_stand = compartment_boundary_features(g_subarea, compartments)

    metadane_path = package_dir / "metadane.txt"
    package_date = None
    if metadane_path.exists():
        package_date = _parse_metadane(metadane_path).get("Data wytworzenia danych")

    result = {}
    for adr_for in g_subarea["adr_for"]:
        sub_row = subarea_by_stand.get(adr_for)
        dist, shared_len = boundary_by_stand.get(adr_for, (None, None))
        result[adr_for] = ExtraStandFeatures(
            veg_cover_cd=_clean(sub_row.veg_cover_cd) if sub_row is not None else None,
            site_class_cd=bonitacja_by_stand.get(adr_for),
            density_cd=density_by_stand.get(adr_for),
            soil_subtype_cd=_clean(sub_row.soil_subtype_cd) if sub_row is not None else None,
            degradation_cd=_clean(sub_row.degradation_cd) if sub_row is not None else None,
            stand_struct_cd=_clean(sub_row.stand_struct_cd) if sub_row is not None else None,
            podszyt_species=podszyt_by_stand.get(adr_for, []),
            podrost_species=podrost_by_stand.get(adr_for, []),
            zabiegi_planowane=zabiegi_by_stand.get(adr_for, []),
            rok_wskazan=rok_wskazan_by_stand.get(adr_for),
            dist_do_granicy_oddzialu_m=dist,
            dlugosc_granicy_z_oddzialem_m=shared_len,
            source_name=package_dir.name,
            package_date=package_date,
        )
    return result


def load_extra_features(packages_dir: Path) -> dict[str, ExtraStandFeatures]:
    """Auto-discovers every unpacked BDL data package under `packages_dir`
    (same directories pipeline.bdl_packages.load_packages reads) and indexes
    plan 1.6.4's diagnostics-only features by adr_for. Missing/empty
    directory, or a subdirectory missing the required files, returns {} /
    skips it -- never raises, matching every other pipeline.bdl_* loader."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    index: dict[str, ExtraStandFeatures] = {}
    required = ("G_SUBAREA.shp", "f_subarea.txt", "f_storey_species.txt", "f_arod_storey.txt", "f_arod_cue.txt")
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        if not all((package_dir / name).exists() for name in required):
            continue
        index.update(_load_one_package(package_dir))
    return index
