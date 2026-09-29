"""Faza 2.4/2.5: wspolne narzedzia statystyczne (AUC, rangi, bootstrap klastrowy, werdykt wg regul).

Reguly: docs/WALIDACJA_REGULY.md, szczegoly wykonania: docs/WALIDACJA_IMPLEMENTACJA.md.
"""
import numpy as np
import pandas as pd

SEED = 20260928
N_BOOT = 2000


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney: P(pos > neg) + 0.5 P(pos == neg). NaN gdy brak pozytywow/negatywow."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    neg_sorted = np.sort(neg)
    lower = np.searchsorted(neg_sorted, pos, side="left")
    upper = np.searchsorted(neg_sorted, pos, side="right")
    return float(((lower + upper) / 2).sum() / (len(pos) * len(neg)))


def rank_of(value: float, controls: np.ndarray) -> float:
    """Ranga wartosci wsrod porownywanych dni (razem z nia): udzial nizszych + 0.5 * remisy."""
    values = np.append(np.asarray(controls, float), value)
    return float((values < value).mean() + 0.5 * (values == value).mean())


def dedupe(df: pd.DataFrame, key_cols: list[str], observer_col: str = "observer") -> pd.DataFrame:
    """Jeden rekord na (obserwator + key_cols). Rekordy bez obserwatora nie sa deduplikowane."""
    has = df[observer_col].notna() & (df[observer_col].astype(str).str.strip() != "")
    kept = df[has].drop_duplicates([observer_col, *key_cols])
    return pd.concat([kept, df[~has]]).sort_index()


def cluster_bootstrap(stat_fn, df: pd.DataFrame, cluster_col: str, n_boot: int = N_BOOT,
                      seed: int = SEED) -> tuple[float, float]:
    """Percentylowy 95% CI: losowanie klastrow (unikalnych wartosci cluster_col) ze zwracaniem,
    stat_fn(df_probki) -> liczba. Powtorzenia bez wyniku (NaN) sa pomijane."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in df.groupby(cluster_col)}
    keys = list(groups)
    values = []
    for _ in range(n_boot):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        sample = pd.concat([groups[keys[i]] for i in pick], ignore_index=True)
        v = stat_fn(sample)
        if np.isfinite(v):
            values.append(v)
    if not values:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def union_ci(cis: list[tuple[float, float]]) -> tuple[float, float]:
    """Suma przedzialow (konserwatywnie): dolna = min dolnych, gorna = max gornych."""
    return min(c[0] for c in cis), max(c[1] for c in cis)


def verdict(cis_by_background: dict[str, tuple[float, float]], null: float = 0.5) -> str:
    """Trzy wyniki z gory: 'czerwona flaga' (caly CI < null w ktoryms tle), 'zgodne z modelem'
    (caly CI > null w kazdym tle), inaczej 'brak rozroznienia'."""
    if any(np.isnan(lo) or np.isnan(hi) for lo, hi in cis_by_background.values()):
        return "brak wniosku"
    if any(hi < null for lo, hi in cis_by_background.values()):
        return "czerwona flaga"
    if all(lo > null for lo, hi in cis_by_background.values()):
        return "zgodne z modelem"
    return "brak rozroznienia"


def cluster_bootstrap_mean(values, clusters, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """Szybki bootstrap klastrowy sredniej (95% CI percentylowy): losuje klastry ze zwracaniem."""
    values = np.asarray(values, float)
    codes, uniq = pd.factorize(pd.Series(clusters))
    sums = np.bincount(codes, weights=values, minlength=len(uniq))
    counts = np.bincount(codes, minlength=len(uniq)).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n_boot, len(uniq)))
    means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
