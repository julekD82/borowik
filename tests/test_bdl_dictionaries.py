from pipeline.bdl_dictionaries import load_dictionaries

_FILES = {
    "f_area_type_dic.txt": "date_from\tdate_to\tarea_type_cd\tarea_type_name\n"
                            "01-01-2004\t31-12-2199\tZRĄB      \tzrąb                                    \n"
                            "01-01-2004\t31-12-2199\tD-STAN    \tdrzewostan                              \n",
    "f_density_dic.txt": "date_from\tdate_to\tdensity_cd\tdensity_name\n"
                          "01-01-2026\t\tPEŁ \tpełne                                             \n"
                          "01-01-2026\t\t0.4 \t0.4                                               \n",
    "f_storey_dic.txt": "date_from\tdate_to\tstorey_cd\tstorey_name\n"
                         "01-01-1970\t\tPODSZ     \tpodszyt                       \n",
    "f_tree_species_dic.txt": "date_from\tdate_to\tspecies_cd\tspecies_name\n"
                               "01-01-1970\t\tŚW       \tświerk pospolity\n"
                               "01-01-1970\t\tSO       \tsosna zwyczajna\n",
    "f_soil_subtype_dic.txt": "date_from\tdate_to\tsoil_subtype_cd\tsoil_subtype_name\n"
                               "01-01-1970\t\tBw    \tbrunatna wyługowana\n",
    "f_prot_categ_dic.txt": "date_from\tdate_to\tprot_category_cd\tprot_category_name\n"
                             "\t\tOCH USZK \ttrw. uszk na sk. dział.przem\n",
    "f_part_dic.txt": "date_from\tdate_to\tpart_cd\tpart_name\n"
                       "01-01-1970\t\t7  \tudział 70 %                   \n"
                       "01-01-1970\t\tMJS\tponiżej 5 % - miejscami       \n",
}


def _write_dictionary_package(package_dir, files=_FILES):
    package_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (package_dir / filename).write_text(content, encoding="utf-8")


def test_load_dictionaries_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_dictionaries(tmp_path / "does_not_exist") == {}


def test_load_dictionaries_returns_empty_dict_when_no_package_has_all_files(tmp_path):
    incomplete = tmp_path / "PKG"
    incomplete.mkdir()
    (incomplete / "f_area_type_dic.txt").write_text(_FILES["f_area_type_dic.txt"], encoding="utf-8")
    assert load_dictionaries(tmp_path) == {}


def test_load_dictionaries_loads_all_six_tables(tmp_path):
    _write_dictionary_package(tmp_path / "PKG_ONE")
    dictionaries = load_dictionaries(tmp_path)
    assert set(dictionaries) == {
        "area_type", "density", "storey", "tree_species", "soil_subtype", "prot_categ", "part",
    }
    assert dictionaries["part"]["7"] == "udział 70 %"
    assert dictionaries["part"]["MJS"] == "poniżej 5 % - miejscami"
    assert dictionaries["area_type"]["ZRAB"] == "zrąb"  # "Ą" -> "A", normalize_code
    assert dictionaries["area_type"]["D-STAN"] == "drzewostan"
    assert dictionaries["density"]["PEL"] == "pełne"  # "Ł" -> "L", normalize_code
    assert dictionaries["density"]["0.4"] == "0.4"
    assert dictionaries["storey"]["PODSZ"] == "podszyt"
    assert dictionaries["soil_subtype"]["Bw"] == "brunatna wyługowana"
    assert dictionaries["prot_categ"]["OCH USZK"] == "trw. uszk na sk. dział.przem"


def test_load_dictionaries_normalizes_diacritic_species_codes(tmp_path):
    # f_tree_species_dic uses the same raw diacritic codes as
    # f_storey_species's species_cd (e.g. "ŚW") -- must be normalized
    # to match pipeline.bdl_packages' already-normalized composition codes.
    _write_dictionary_package(tmp_path / "PKG_ONE")
    dictionaries = load_dictionaries(tmp_path)
    assert dictionaries["tree_species"]["SW"] == "świerk pospolity"
    assert dictionaries["tree_species"]["SO"] == "sosna zwyczajna"


def test_load_dictionaries_uses_first_package_with_complete_files(tmp_path):
    incomplete = tmp_path / "AAA_INCOMPLETE"
    incomplete.mkdir()
    (incomplete / "f_area_type_dic.txt").write_text(_FILES["f_area_type_dic.txt"], encoding="utf-8")
    _write_dictionary_package(tmp_path / "BBB_COMPLETE")
    dictionaries = load_dictionaries(tmp_path)
    assert dictionaries["storey"]["PODSZ"] == "podszyt"
