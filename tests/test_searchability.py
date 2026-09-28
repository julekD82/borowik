from pipeline.searchability import searchability_hint


def test_no_signal_returns_none():
    assert searchability_hint(density_cd=None, podszyt_species=[], podrost_species=[]) is None


def test_podszyt_and_podrost_present_gives_combined_hint():
    hint = searchability_hint(density_cd=None, podszyt_species=[("BRZ", "5")], podrost_species=[("BK", "3")])
    assert hint == "Gęsty podszyt i podrost — trudniejsze poruszanie się i szukanie."


def test_podszyt_only_gives_podszyt_hint():
    hint = searchability_hint(density_cd=None, podszyt_species=[("BRZ", "5")], podrost_species=[])
    assert hint == "Obecny podszyt — może utrudniać poruszanie się."


def test_podrost_only_gives_podrost_hint():
    hint = searchability_hint(density_cd=None, podszyt_species=[], podrost_species=[("BK", "3")])
    assert hint == "Obecny podrost — może utrudniać poruszanie się."


def test_dense_canopy_without_understory_gives_canopy_hint():
    hint = searchability_hint(density_cd="0.9", podszyt_species=[], podrost_species=[])
    assert hint == "Gęste zwarcie koron — mniej światła pod drzewostanem."


def test_sparse_canopy_without_understory_gives_canopy_hint():
    hint = searchability_hint(density_cd="0.2", podszyt_species=[], podrost_species=[])
    assert hint == "Luźne zwarcie koron — więcej światła pod drzewostanem."


def test_medium_canopy_without_understory_gives_no_hint():
    hint = searchability_hint(density_cd="0.5", podszyt_species=[], podrost_species=[])
    assert hint is None


def test_unparseable_density_is_ignored_not_crashed():
    hint = searchability_hint(density_cd="brak", podszyt_species=[], podrost_species=[])
    assert hint is None


def test_understory_signal_takes_priority_over_canopy():
    # Both signals present -- understory (podszyt/podrost) is the stronger
    # practical "trudne szukanie" cue, so it wins over the canopy note.
    hint = searchability_hint(density_cd="0.9", podszyt_species=[("BRZ", "5")], podrost_species=[])
    assert hint == "Obecny podszyt — może utrudniać poruszanie się."
