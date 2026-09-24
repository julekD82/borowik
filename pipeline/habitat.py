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


def compute_habitat(row: dict, profile: dict) -> float | None:
    weights = profile["weights"]
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
