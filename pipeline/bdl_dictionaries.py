from pathlib import Path

import pandas as pd

from pipeline.bdl import normalize_code

# (filename, code column, name column) -- verified byte-identical across
# nadleśnictwa (plan 2.1 step B3 research: Kędzierzyn vs Głogów, all five
# tables compared with filecmp), so any one available package's copy is
# authoritative for the whole app; no per-package variant needed.
# area_type_dic also translates WFS's own area_type (not paczka-sourced)
# for neighbour labels (pipeline.neighbors) -- same table, dual use.
_DICTIONARY_SPECS = {
    "area_type": ("f_area_type_dic.txt", "area_type_cd", "area_type_name"),
    "density": ("f_density_dic.txt", "density_cd", "density_name"),
    "storey": ("f_storey_dic.txt", "storey_cd", "storey_name"),
    "tree_species": ("f_tree_species_dic.txt", "species_cd", "species_name"),
    "soil_subtype": ("f_soil_subtype_dic.txt", "soil_subtype_cd", "soil_subtype_name"),
    "prot_categ": ("f_prot_categ_dic.txt", "prot_category_cd", "prot_category_name"),
    # part_cd_act's own dictionary (10-100% AND the MJS/PJD trace codes,
    # see pipeline.bdl_packages) -- reused to render every species share
    # (DRZEW and PODSZ alike) as readable text instead of a bare fraction.
    "part": ("f_part_dic.txt", "part_cd", "part_name"),
}


# Nowy frontend: nazwa typu siedliskowego na karcie wydzielenia. Opcjonalny -- paczka bez
# tego pliku (albo testowa) dalej laduje pozostale slowniki.
_OPTIONAL_DICTIONARY_SPECS = {
    "site_type": ("f_site_type_dic.txt", "site_type_cd", "site_type_name"),
}


def _read_dictionary(path: Path, code_col: str, name_col: str) -> dict[str, str]:
    df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8")
    # Dictionary codes carry the same raw Polish diacritics as
    # f_storey_species's species_cd (e.g. "ŚW") -- normalize so lookups
    # against already-normalized codes (pipeline.bdl_packages,
    # pipeline.bdl.normalize_code) work without a second code form.
    codes = df[code_col].str.strip().map(normalize_code)
    names = df[name_col].str.strip()
    return dict(zip(codes, names))


def _load_dictionaries_from(package_dir: Path) -> dict[str, dict[str, str]]:
    dictionaries = {}
    for table_name, (filename, code_col, name_col) in _DICTIONARY_SPECS.items():
        dictionaries[table_name] = _read_dictionary(package_dir / filename, code_col, name_col)
    for table_name, (filename, code_col, name_col) in _OPTIONAL_DICTIONARY_SPECS.items():
        if (package_dir / filename).exists():
            dictionaries[table_name] = _read_dictionary(package_dir / filename, code_col, name_col)
    return dictionaries


def load_dictionaries(packages_dir: Path) -> dict[str, dict[str, str]]:
    """Loads the BDL code->name lookup tables (area_type, density, storey,
    tree_species, soil_subtype, prot_categ) from the first available
    package under `packages_dir` -- plan 2.1 step B3, used to render
    readable labels on a wydzielenie's card instead of raw codes.

    Missing packages_dir, or none of its subdirectories having a complete
    set of dictionary files, returns {} -- callers fall back to showing
    raw codes, never an error (same "no package data never breaks the
    run" spirit as pipeline.bdl_packages.load_packages)."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        if all((package_dir / filename).exists() for filename, _, _ in _DICTIONARY_SPECS.values()):
            return _load_dictionaries_from(package_dir)
    return {}
