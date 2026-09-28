import numpy as np
import pandas as pd

from pipeline import validation_stats as vs


def test_auc_perfect_reverse_and_ties():
    assert vs.auc([3, 4], [1, 2]) == 1.0
    assert vs.auc([1, 2], [3, 4]) == 0.0
    assert vs.auc([1, 1], [1, 1]) == 0.5
    assert np.isnan(vs.auc([], [1]))


def test_rank_of_counts_ties_as_half():
    assert vs.rank_of(5, [1, 2, 3]) == 0.875  # 3 nizsze + 0.5 (remis z soba) z 4 wartosci
    assert vs.rank_of(1, [1, 1, 1]) == 0.5


def test_dedupe_keeps_one_per_observer_key_and_all_anonymous():
    df = pd.DataFrame({"observer": ["a", "a", "b", None, None], "stand": [1, 1, 1, 1, 1], "year": [2024] * 5})
    out = vs.dedupe(df, ["stand", "year"])
    assert sorted(out["observer"].fillna("-").tolist()) == ["-", "-", "a", "b"]


def test_cluster_bootstrap_is_deterministic_and_brackets_the_mean():
    df = pd.DataFrame({"c": np.repeat(range(20), 5), "x": np.tile([0.6, 0.7, 0.8, 0.5, 0.9], 20)})
    lo, hi = vs.cluster_bootstrap(lambda d: d["x"].mean(), df, "c", n_boot=200)
    assert (lo, hi) == vs.cluster_bootstrap(lambda d: d["x"].mean(), df, "c", n_boot=200)
    assert lo <= 0.7 <= hi


def test_verdict_three_outcomes():
    assert vs.verdict({"a": (0.4, 0.48), "b": (0.6, 0.7)}) == "czerwona flaga"
    assert vs.verdict({"a": (0.55, 0.7), "b": (0.6, 0.7)}) == "zgodne z modelem"
    assert vs.verdict({"a": (0.55, 0.7), "b": (0.45, 0.7)}) == "brak rozroznienia"
    assert vs.verdict({"a": (float("nan"), float("nan"))}) == "brak wniosku"


def test_union_ci():
    assert vs.union_ci([(0.4, 0.6), (0.45, 0.7)]) == (0.4, 0.7)


def test_cluster_bootstrap_mean_is_deterministic_and_brackets_the_mean():
    vals = np.arange(100) / 100
    cl = np.repeat(range(20), 5)
    lo, hi = vs.cluster_bootstrap_mean(vals, cl, n_boot=300)
    assert (lo, hi) == vs.cluster_bootstrap_mean(vals, cl, n_boot=300)
    assert lo < vals.mean() < hi
