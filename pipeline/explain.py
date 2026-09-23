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
        "up": "wilgotność ostatnich 26 dni powyżej normy dla tej pory roku (M={value:.2f})",
        "down": "wilgotność ostatnich 26 dni poniżej normy dla tej pory roku (M={value:.2f})",
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


def compute_log_contributions(values: dict, area_medians: dict) -> dict:
    contributions = {}
    for factor, weight in FACTOR_WEIGHTS.items():
        value = values.get(factor)
        median = area_medians.get(factor)
        if value is None or median is None or value <= 0 or median <= 0:
            continue
        contributions[factor] = weight * (math.log(value) - math.log(median))
    return contributions


def generate_explanation(contributions: dict, values: dict, meta: dict, profile: dict) -> list:
    cfg = profile["explanation"]
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    ups = [item for item in ranked if item[1] > 0][: cfg["max_positive"]]
    downs = sorted((item for item in ranked if item[1] < 0), key=lambda kv: kv[1])[: cfg["max_negative"]]

    entries = []
    for factor, contribution in ups + downs:
        direction = "up" if contribution > 0 else "down"
        template = TEMPLATES[factor][direction]
        fmt_args = {**meta, "value": values.get(factor, 0.0)}
        text = template.format(**fmt_args)
        entries.append({"factor": factor, "contribution": float(contribution), "text": text})
    return entries
