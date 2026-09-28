import math

# Weights mirror the exponents already hardcoded in pipeline.habitat.compute_habitat
# (host/site/age) and pipeline.scoring.compute_fruiting (moisture/temperature);
# frost and the presja discount enter H/F/R with an implicit exponent of 1.
FACTOR_WEIGHTS = {
    "host": 0.40, "site": 0.35, "age": 0.25,
    "moisture": 0.6, "temperature": 0.4, "frost": 1.0,
    "pressure_factor": 1.0,
}

TEMPLATES = {
    "host": {
        "up": "gatunek panujący {species_cd} ma wysokie powinowactwo do borowika (S_host={value:.2f})",
        "down": "gatunek panujący {species_cd} słabo pasuje do borowika (S_host={value:.2f})",
        # Plan 2.1 step A4 (spec §5.3 "Poprawka wyjaśnień"): S_host blends a
        # species' own affinity with a neutral 0.5 "unknown admixture" in
        # proportion to part_cd (pipeline.habitat.score_host). When the
        # dominant species itself is a GOOD match (affinity >= the neutral
        # baseline) but only holds a partial share, a low composite S_host
        # reflects missing-domieszka-data dilution, not a poor species --
        # see _host_down_is_low_share below for exactly when this applies.
        "down_low_share": (
            "gatunek panujący {species_cd} dobrze pasuje do borowika, ale stanowi tylko "
            "{part_cd:.0f}/10 udziału w drzewostanie (S_host={value:.2f})"
        ),
    },
    "site": {
        "up": "siedlisko {site_type} sprzyja owocnikowaniu (S_site={value:.2f})",
        "down": "siedlisko {site_type} słabo sprzyja owocnikowaniu (S_site={value:.2f})",
    },
    "age": {
        "up": "wiek drzewostanu {age} lat jest w dobrym przedziale (S_age={value:.2f})",
        "down": "wiek drzewostanu {age} lat jest poza optymalnym przedziałem (S_age={value:.2f})",
    },
    "moisture": {
        # Plan 1.8f: the contribution being explained here is log(M) vs
        # log(area median M) -- THIS analysis's own median (spec §12: "po
        # maskowanych dodatnich wartościach"), not a long-term climatological
        # norm for the date. "Powyżej normy dla tej pory roku" claimed the
        # latter; M's own pct_CWB26 percentile already IS relative to the
        # 1991-2020 archive, but this sentence is about the spatial
        # comparison within the search, not that temporal one.
        "up": "wilgotność ostatnich 26 dni wyżej niż mediana dla tego obszaru (M={value:.2f})",
        "down": "wilgotność ostatnich 26 dni niżej niż mediana dla tego obszaru (M={value:.2f})",
    },
    "temperature": {
        "up": "temperatura blisko optimum dla owocnikowania (T={value:.2f})",
        "down": "temperatura odbiega od optimum dla owocnikowania (T={value:.2f})",
    },
    "frost": {
        "up": "brak istotnego ryzyka przymrozku (K_frost={value:.2f})",
        "down": "ryzyko przymrozku obniża szansę na owocniki (K_frost={value:.2f})",
    },
    "pressure_factor": {
        "up": "niska presja innych grzybiarzy w tej okolicy (P={P:.2f})",
        "down": "wysoka presja innych grzybiarzy w tej okolicy (P={P:.2f})",
    },
}


def g_season_note(g_season: float, profile: dict) -> dict | None:
    """Plan 2.1 "Zmiana 1": a flat, threshold-based note (NOT part of the
    ranked contributions/generate_explanation pool above) -- G_season is
    the same value for every stand in a run, so a log-contribution against
    an area median (like host/site/age/moisture/...) would always be 0 and
    never surface it. Returns None when g_season is at or above
    profile["phenology"]["g_season_note_threshold"] (no note needed)."""
    threshold = profile["phenology"]["g_season_note_threshold"]
    if g_season >= threshold:
        return None
    return {
        "factor": "g_season",
        "contribution": g_season - 1.0,
        "text": f"poza szczytem sezonu (G_season={g_season:.2f})",
    }


def compute_log_contributions(values: dict, area_medians: dict) -> dict:
    contributions = {}
    for factor, weight in FACTOR_WEIGHTS.items():
        value = values.get(factor)
        median = area_medians.get(factor)
        if value is None or median is None or value <= 0 or median <= 0:
            continue
        contributions[factor] = weight * (math.log(value) - math.log(median))
    return contributions


def _host_down_is_low_share(meta: dict, profile: dict) -> bool:
    """True when a "down" S_host contribution is explained by a good
    species diluted by a low part_cd share, rather than the species itself
    being a poor match (plan 2.1 step A4). `meta` needs `part_cd` and
    `host_affinity` (pipeline.habitat.host_affinity) -- callers that don't
    pass them (or pass a missing part_cd, e.g. BDL didn't report one) get
    False, i.e. the original wording, not a crash."""
    part_cd = meta.get("part_cd")
    affinity = meta.get("host_affinity")
    if part_cd is None or affinity is None:
        return False
    try:
        if math.isnan(part_cd):
            return False
    except TypeError:
        pass
    # part_cd == 10 means no admixture dilution occurred at all (score_host
    # returns the affinity unchanged); affinity below the neutral baseline
    # means the dominant species is the problem regardless of its share.
    return 0 < part_cd < 10 and affinity >= profile["unknown_host_affinity"]


def generate_explanation(contributions: dict, values: dict, meta: dict, profile: dict) -> list:
    cfg = profile["explanation"]
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    ups = [item for item in ranked if item[1] > 0][: cfg["max_positive"]]
    downs = sorted((item for item in ranked if item[1] < 0), key=lambda kv: kv[1])[: cfg["max_negative"]]

    entries = []
    for factor, contribution in ups + downs:
        direction = "up" if contribution > 0 else "down"
        template_key = direction
        if factor == "host" and direction == "down" and _host_down_is_low_share(meta, profile):
            template_key = "down_low_share"
        template = TEMPLATES[factor][template_key]
        fmt_args = {**meta, "value": values.get(factor, 0.0)}
        text = template.format(**fmt_args)
        entries.append({"factor": factor, "contribution": float(contribution), "text": text})
    return entries
