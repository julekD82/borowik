_DENSE_CANOPY = 0.8
_SPARSE_CANOPY = 0.3


def _parse_canopy(density_cd) -> float | None:
    try:
        return float(density_cd) if density_cd else None
    except (TypeError, ValueError):
        return None


def searchability_hint(density_cd, podszyt_species: list, podrost_species: list) -> str | None:
    """Plan 1.6.5: short practical note for the wydzielenie/region card,
    presentation only -- never read by pipeline.orchestrate/habitat/scoring
    (structural "can't touch R" guarantee, same as pipeline.tie_break).

    Built from whatever podszyt/podrost/zwarcie signal actually exists:
    density_cd on the PODSZ/PODR storeys themselves is 0% filled in every
    package checked (docs/BDL_slownik_pol.md), so understory "density" here
    means PRESENCE of podszyt/podrost species (not a quantified coverage),
    and canopy closure (DRZEW's own density_cd) is the only real density
    number available. Understory presence is the stronger practical cue and
    takes priority over a canopy-only note when both are present. `None`
    when there's no signal at all -- the card shows nothing rather than a
    manufactured "brak danych"."""
    has_podszyt = bool(podszyt_species)
    has_podrost = bool(podrost_species)
    if has_podszyt and has_podrost:
        return "Gęsty podszyt i podrost — trudniejsze poruszanie się i szukanie."
    if has_podszyt:
        return "Obecny podszyt — może utrudniać poruszanie się."
    if has_podrost:
        return "Obecny podrost — może utrudniać poruszanie się."
    canopy = _parse_canopy(density_cd)
    if canopy is not None and canopy >= _DENSE_CANOPY:
        return "Gęste zwarcie koron — mniej światła pod drzewostanem."
    if canopy is not None and canopy <= _SPARSE_CANOPY:
        return "Luźne zwarcie koron — więcej światła pod drzewostanem."
    return None
