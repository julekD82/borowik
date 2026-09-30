import numpy as np
import pandas as pd

from pipeline.eobs_fruiting import rolling_features, variant_scores
from pipeline.habitat import load_profile
from pipeline.weather import _exp_weighted_sum


def _daily(n=60, rr=None):
    idx = pd.date_range("2020-06-01", periods=n, freq="D")
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "tg": 14.0 + rng.normal(0, 1, n), "tn": 9.0 + rng.normal(0, 1, n), "tx": 20.0 + rng.normal(0, 1, n),
        "rr": rng.gamma(0.5, 4, n) if rr is None else rr,
    }, index=idx)


def test_rolling_features_match_production_window_formulas():
    from pipeline.eobs import hargreaves_et0
    d = _daily()
    f = rolling_features(d, 50.5)
    i = 40
    et0 = hargreaves_et0(d["tn"], d["tx"], 50.5)
    expected = _exp_weighted_sum(d["rr"].iloc[: i + 1], 26) - _exp_weighted_sum(et0.iloc[: i + 1], 26)
    assert abs(f["cwb26"].iloc[i] - expected) < 1e-9
    assert abs(f["tmean20"].iloc[i] - d["tg"].iloc[i - 19: i + 1].mean()) < 1e-9
    assert abs(f["p5"].iloc[i] - d["rr"].iloc[i - 4: i + 1].sum()) < 1e-9
    assert abs(f["tmin3"].iloc[i] - d["tn"].iloc[i - 2: i + 1].min()) < 1e-9
    assert f["cwb26"].iloc[:25].isna().all()


def test_missing_day_in_window_gives_nan():
    d = _daily(100)
    d.iloc[35, d.columns.get_loc("rr")] = np.nan
    f = rolling_features(d, 50.5)
    assert np.isnan(f["cwb26"].iloc[40]) and not np.isnan(f["cwb26"].iloc[70])


def test_variant_scores_shape_and_constant_model():
    profile = load_profile("profiles/boletus_edulis.yaml")
    feat = pd.Series({"cwb26": 5.0, "tmean20": 14.0, "tmean5": 14.0, "p5": 5.0, "tmin3": 8.0})
    out = variant_scores(feat, 260, np.linspace(-20, 20, 50), profile)
    assert set(out) == {"F_bez_G_season", "F_z_G_season", "sam_kalendarz", "samo_M", "sama_T", "model_staly"}
    assert out["model_staly"] == 1.0 and 0 <= out["F_z_G_season"] <= 1.0


def test_precip_weights_variants():
    from pipeline.eobs_fruiting import precip_weights
    k0 = precip_weights()
    assert len(k0) == 26 and k0[0] == 1.0 and abs(k0[10] - 0.5) < 1e-12
    k1 = precip_weights("K1")
    assert len(k1) == 36
    assert k1[:5].tolist() == [0.0, 0.2, 0.4, 0.6, 0.8] and (k1[5:11] == 1.0).all()
    assert abs(k1[20] - 0.5) < 1e-12 and abs(k1[35] - 0.5 ** 2.5) < 1e-12
    assert (precip_weights("K2") == 1.0).all() and len(precip_weights("K2")) == 26
    k3 = precip_weights("K3")
    assert len(k3) == 11 and k3[:5].sum() == 0 and (k3[5:] == 1.0).all()
    import pytest
    with pytest.raises(ValueError):
        precip_weights("K9")


def test_rolling_features_default_is_k0_and_custom_weights_apply_to_cwb_only():
    from pipeline.eobs import hargreaves_et0
    from pipeline.eobs_fruiting import precip_weights
    d = _daily(80)
    base = rolling_features(d, 50.5)
    assert base.equals(rolling_features(d, 50.5, precip_weights("K0")))
    w = precip_weights("K1")
    f = rolling_features(d, 50.5, w)
    i = 60
    net = (d["rr"] - hargreaves_et0(d["tn"], d["tx"], 50.5)).to_numpy()
    expected = sum(w[j] * net[i - j] for j in range(len(w)))
    assert abs(f["cwb26"].iloc[i] - expected) < 1e-9
    assert f["cwb26"].iloc[:35].isna().all() and not np.isnan(f["cwb26"].iloc[35])
    assert f[["tmean20", "tmean5", "p5", "tmin3"]].equals(base[["tmean20", "tmean5", "p5", "tmin3"]])
