import pandas as pd
import yaml


def load_profile(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def host_affinity(species_cd: str, profile: dict) -> float:
    """The raw per-species affinity (spec §5.3 table), before blending with
    the "unknown admixture" default -- exposed separately so callers (e.g.
    pipeline.explain's S_host wording) can distinguish a genuinely poor
    species match from a good species diluted by a low part_cd share, which
    score_host's returned composite alone cannot (2.1 step A4)."""
    return profile["host_affinity"].get(species_cd, profile["unknown_host_affinity"])


def score_host(species_cd: str, part_cd: int, profile: dict) -> float:
    affinity = host_affinity(species_cd, profile)
    # part_cd arrives from the BDL WFS via pd.to_numeric(errors="coerce"), so a
    # missing/unparseable value is NaN. `part_cd or 0` does NOT catch that (NaN
    # is truthy), and the NaN then propagates through H all the way into R --
    # test it explicitly instead.
    share = 0.0 if part_cd is None or pd.isna(part_cd) else float(part_cd) / 10.0
    return share * affinity + (1 - share) * profile["unknown_host_affinity"]


def score_host_composition(composition: list[tuple[str, float]], profile: dict) -> tuple[float, int]:
    """S_host = Sigma udzial_i * powinowactwo_i from a real BDL package's
    DRZEW-storey species composition (plan 2.1 step B2, replacing the
    panujacy+unknown_host_affinity blend when a package is available --
    see pipeline.bdl_packages.load_packages). `composition` is
    [(species_cd, share 0-1), ...]; verified on real packages (B2 research)
    that the numeric shares already sum to ~1.0 per stand, so no
    renormalization here.

    A species_cd missing from the profile falls back to
    unknown_host_affinity (same neutral default as an unquantified WFS
    admixture) and is counted rather than silently absorbed -- callers
    surface that count as a diagnostic (orchestrate.run_poc's
    package_unknown_species_count), not an error."""
    total = 0.0
    unknown = 0
    for species_cd, share in composition:
        affinity = profile["host_affinity"].get(species_cd)
        if affinity is None:
            affinity = profile["unknown_host_affinity"]
            unknown += 1
        total += share * affinity
    return total, unknown


def score_site(site_type: str, profile: dict) -> tuple[float, int]:
    entry = profile["site_scores"].get(site_type)
    if entry is None:
        return profile["unknown_site_score"], profile["unknown_site_moisture_cls"]
    value, moisture_cls = entry
    return float(value), int(moisture_cls)


def score_age(age: int | None, profile: dict) -> float | None:
    cfg = profile["age_breakpoints"]
    if age is None or age < cfg["mask_below"]:
        return None
    for seg in cfg["segments"]:
        if seg["from"] <= age < seg["to"]:
            span = seg["to"] - seg["from"]
            frac = (age - seg["from"]) / span if span else 0.0
            return seg["value_from"] + frac * (seg["value_to"] - seg["value_from"])
    last = cfg["segments"][-1]
    if age >= last["to"] and age <= 120:
        return last["value_to"]
    return cfg["above_120"]


def compute_habitat(row: dict, profile: dict, s_host: float | None = None) -> float | None:
    """`s_host` lets a caller (orchestrate.run_poc) pass an already-resolved
    S_host -- e.g. from score_host_composition when a BDL package covers
    this wydzielenie (plan 2.1 step B2) -- instead of the WFS
    panujacy+part_cd fallback computed below. `None` (the default)
    preserves the exact pre-B2 behaviour for every existing caller/test."""
    weights = profile["weights"]
    if s_host is None:
        s_host = score_host(row["species_cd"], row.get("part_cd", 10), profile)
    s_site, _moisture_cls = score_site(row["site_type"], profile)
    s_age = score_age(row.get("spec_age"), profile)
    if s_age is None:
        return None
    return (s_host ** weights["host"]) * (s_site ** weights["site"]) * (s_age ** weights["age"])


def passes_mask(row: dict, profile: dict) -> bool:
    if row.get("area_type") != "D-STAN":
        return False
    if row.get("spec_age") is None or row["spec_age"] < profile["age_breakpoints"]["mask_below"]:
        return False
    species = row.get("species_cd")
    if species in profile["zero_affinity_mask_species"] and (row.get("part_cd") or 0) >= 8:
        return False
    return True
