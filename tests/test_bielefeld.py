import pathlib

import numpy as np
import pandas as pd
import pytest

from pipeline import bielefeld as bf


def _raw(days=10, counts_all=None, sites=("All", "Site_A", "Site_B")):
    """Mala tabela w formacie pliku autorow (Environmental_fruiting_data_jun8.csv)."""
    dates = pd.date_range("2020-08-01", periods=days, freq="D")
    counts_all = counts_all if counts_all is not None else [0] * days
    rows = []
    for s in sites:
        for i, d in enumerate(dates):
            n = counts_all[i] if s == "All" else (1 if (s == "Site_A" and counts_all[i] > 1) else 0)
            rows.append({"Temp": 10.0 + i, "Date": d.strftime("%Y-%m-%d"), "Precip": float(i % 3),
                         "date": d.strftime("%Y-%m-%d"), "year": 2020, "rollT_2": 0.0, "rollP_2": 0.0,
                         "Mnb": n, "month": d.month, "site": s})
    return pd.DataFrame(rows)


def test_write_validation_tables_is_deterministic(tmp_path):
    raw = _raw(4, [0, 3, 0, 2])
    p1 = bf.write_validation_tables(raw, tmp_path / "a")
    p2 = bf.write_validation_tables(raw.sample(frac=1, random_state=1), tmp_path / "b")
    for k in p1:
        assert pathlib.Path(p1[k]).read_bytes() == pathlib.Path(p2[k]).read_bytes()
    lines = pathlib.Path(p1["owocniki"]).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "data,stanowisko,nowe_owocniki,wizyta"
    assert lines[1] == "2020-08-01,All,0," and lines[2] == "2020-08-02,All,3,1"
    back = pd.read_csv(p1["pogoda_autorow"])
    assert list(back.columns) == ["data", "tg", "rr"] and len(back) == 4


def test_centroid_from_dms():
    lat, lon = bf.CENTROID
    assert lat == pytest.approx(52 + 3 / 60 + 42.2 / 3600)
    assert lon == pytest.approx(8 + 27 / 60 + 3.3 / 3600)


def test_daily_counts_marks_zero_days_as_unknown_visit():
    d = bf.daily_counts(_raw(4, [0, 3, 0, 2]))
    assert list(d.columns) == ["data", "stanowisko", "nowe_owocniki", "wizyta"]
    alls = d[d["stanowisko"] == "All"].reset_index(drop=True)
    assert alls["nowe_owocniki"].tolist() == [0, 3, 0, 2]
    # owocniki > 0 => wizyta pewna; zero => nie wiadomo (autorzy wpisali 0 takze w dni bez wizyty)
    assert alls["wizyta"].tolist()[1] is True and alls["wizyta"].tolist()[3] is True
    assert alls["wizyta"].isna().tolist() == [True, False, True, False]
    assert set(d["stanowisko"]) == {"All", "Site_A", "Site_B"}


def test_daily_counts_rejects_non_integer_or_negative():
    raw = _raw(3, [0, 1, 0])
    raw["Mnb"] = raw["Mnb"].astype(float)
    raw.loc[1, "Mnb"] = 1.5
    with pytest.raises(ValueError):
        bf.daily_counts(raw)
    raw.loc[1, "Mnb"] = -1
    with pytest.raises(ValueError):
        bf.daily_counts(raw)


def test_authors_weather_one_row_per_day():
    w = bf.authors_weather(_raw(5))
    assert list(w.columns) == ["tg", "rr"] and len(w) == 5
    assert w.index[0] == pd.Timestamp("2020-08-01") and w["tg"].iloc[2] == 12.0


def test_authors_weather_must_agree_across_sites():
    raw = _raw(3)
    raw.loc[raw["site"] == "Site_B", "Temp"] += 1.0
    with pytest.raises(ValueError):
        bf.authors_weather(raw)


def test_descriptive_counts_range_and_zero_share():
    d = bf.daily_counts(_raw(10, [0, 0, 5, 0, 1, 0, 0, 0, 0, 0]))
    s = bf.descriptive(d)
    assert s["owocniki"] == 6 and s["dni"] == 10 and s["dni_z_owocnikami"] == 2
    assert s["udzial_dni_zerowych"] == pytest.approx(0.8)
    assert s["pierwszy_dzien_z_owocnikami"] == "2020-08-03" and s["ostatni_dzien_z_owocnikami"] == "2020-08-05"
    assert s["na_rok"] == {2020: 6}
    # zakres dat jak w pracy: tylko dni od pierwszego do ostatniego dnia z owocnikami (MM-DD)
    s2 = bf.descriptive(d, md_range=("08-03", "08-05"))
    assert s2["dni"] == 3 and s2["udzial_dni_zerowych"] == pytest.approx(1 / 3)


def test_rolling_mean_within_year_right_aligned():
    idx = pd.date_range("2019-12-30", "2020-01-04", freq="D")
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    r = bf.rolling_mean_within_year(s, 2)
    # 2019-12-31: srednia z (0, 1); 2020-01-01: pierwszy dzien roku -> NaN (okno nie przechodzi przez rok)
    assert r.loc["2019-12-31"] == 0.5 and np.isnan(r.loc["2020-01-01"]) and r.loc["2020-01-02"] == 2.5


def test_nb1_gradient_matches_finite_differences():
    rng = np.random.default_rng(0)
    n = 200
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y = rng.poisson(2.0, n).astype(float)
    theta = np.array([0.3, -0.2, np.log(0.7)])
    f, g = bf._nb1_negll_and_grad(theta, y, X)
    eps = 1e-6
    num = np.array([(bf._nb1_negll_and_grad(theta + eps * e, y, X)[0]
                     - bf._nb1_negll_and_grad(theta - eps * e, y, X)[0]) / (2 * eps) for e in np.eye(3)])
    assert np.allclose(g, num, rtol=1e-5, atol=1e-5)


def test_nb1_loglik_matches_scipy_negative_binomial():
    from scipy.stats import nbinom
    y, mu, phi = np.array([0.0, 1.0, 4.0, 10.0]), np.array([0.5, 2.0, 3.0, 8.0]), 1.5
    size = mu / phi
    expected = nbinom.logpmf(y, size, 1.0 / (1.0 + phi))
    assert np.allclose(bf.nb1_loglik(y, mu, phi), expected)


def test_fit_nb1_recovers_parameters_with_group_intercepts():
    rng = np.random.default_rng(42)
    n_per, years = 400, [0, 1, 2]
    x = rng.normal(size=n_per * len(years))
    year = np.repeat(years, n_per)
    alpha = np.array([-0.5, 0.5, 1.0])[year]
    mu = np.exp(alpha + 0.8 * x)
    phi = 1.2
    y = rng.negative_binomial(mu / phi, 1.0 / (1.0 + phi))
    fit = bf.fit_nb1(y, x[:, None], year)
    assert fit["converged"]
    assert fit["beta"][0] == pytest.approx(0.8, abs=0.08)
    assert fit["phi"] == pytest.approx(1.2, rel=0.25)
    assert fit["n_params"] == 3 + 1 + 1
    assert fit["aic"] == pytest.approx(2 * fit["n_params"] - 2 * fit["loglik"])
    mu_hat = bf.predict_nb1(fit, x[:, None], year)
    assert np.corrcoef(mu_hat, mu)[0, 1] > 0.98


def test_week_block_starts_on_monday():
    b = bf.week_block(pd.to_datetime(["2020-08-02", "2020-08-03", "2020-08-09", "2020-08-10"]))
    assert b.tolist() == ["2020-07-27", "2020-08-03", "2020-08-03", "2020-08-10"]


def test_weighted_precip_uses_lag_weights_and_normalises():
    idx = pd.date_range("2020-08-01", periods=6, freq="D")
    rr = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=idx)
    w = np.array([0.0, 1.0, 1.0])  # tylko 1-2 dni wstecz
    out = bf.weighted_precip(rr, w)
    assert np.isnan(out.iloc[1]) and out.iloc[2] == 1.5 and out.iloc[5] == 4.5
    rr.iloc[3] = np.nan
    assert np.isnan(bf.weighted_precip(rr, w).iloc[4])


def test_block_gradient_matches_finite_differences():
    rng = np.random.default_rng(3)
    n = 70
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y_blocks, codes = bf.block_totals(rng.poisson(1.0, n), np.repeat(np.arange(10), 7))
    theta = np.array([0.1, 0.4, np.log(1.3)])
    _, g = bf._nb1_negll_and_grad(theta, y_blocks, X, codes)
    eps = 1e-6
    num = np.array([(bf._nb1_negll_and_grad(theta + eps * e, y_blocks, X, codes)[0]
                     - bf._nb1_negll_and_grad(theta - eps * e, y_blocks, X, codes)[0]) / (2 * eps) for e in np.eye(3)])
    assert np.allclose(g, num, rtol=1e-5, atol=1e-5)


def test_block_fit_recovers_daily_effect_and_reports_se():
    rng = np.random.default_rng(7)
    days = 7 * 120
    x = rng.normal(size=days)
    year = np.repeat([0, 1, 2, 3], days // 4)
    mu = np.exp(np.array([-1.0, 0.0, 0.3, -0.5])[year] + 0.7 * x)
    phi = 0.8
    y = rng.negative_binomial(mu / phi, 1.0 / (1.0 + phi))
    blocks = np.repeat(np.arange(days // 7), 7)
    fit = bf.fit_nb1(y, x[:, None], year, blocks=blocks, se=True)
    assert fit["converged"] and fit["n"] == days // 7
    assert fit["beta"][0] == pytest.approx(0.7, abs=3 * fit["beta_se"][0])
    assert 0.01 < fit["beta_se"][0] < 0.3


def test_loyo_prefers_true_covariate_over_noise():
    rng = np.random.default_rng(11)
    days = 7 * 100
    x, noise = rng.normal(size=days), rng.normal(size=days)
    year = np.repeat(np.arange(5), days // 5)
    y = rng.negative_binomial(np.exp(0.8 * x) / 0.5, 1 / 1.5)
    blocks = np.repeat(np.arange(days // 7), 7)
    good = bf.loyo(y, x[:, None], year, blocks)
    bad = bf.loyo(y, noise[:, None], year, blocks)
    assert list(good["grupa"]) == [0, 1, 2, 3, 4] and good["converged"].all()
    assert (good["ll"] - bad["ll"]).sum() > 10


def test_heldout_alpha_absorbs_year_level():
    fit = {"beta": np.array([0.5]), "phi": 1.0}
    z = np.linspace(-1, 1, 50)
    y = np.round(np.exp(2.0 + 0.5 * z))
    ll, a = bf.heldout_loglik(fit, y, z[:, None])
    assert a == pytest.approx(2.0, abs=0.1) and np.isfinite(ll)


def test_write_eobs_cell_and_compare_weather(tmp_path):
    idx = pd.date_range("2020-08-01", periods=3, freq="D")
    daily = pd.DataFrame({"tg": [10.0, 11.5, np.nan], "tn": [5.0, 6.0, 7.0], "tx": [15.0, 16.0, 17.0],
                          "rr": [0.0, 2.25, 1.0]}, index=idx)
    path = bf.write_eobs_cell(daily, tmp_path)
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "data,tg,tn,tx,rr" and lines[2] == "2020-08-02,11.50,6.00,16.00,2.25"
    assert lines[3].startswith("2020-08-03,,")
    authors = pd.DataFrame({"tg": [10.5, 12.0, 9.0], "rr": [0.0, 2.25, 1.0]}, index=idx)
    c = bf.compare_weather(daily, authors)
    assert c["tg"]["n"] == 2 and c["tg"]["srednia_roznica"] == pytest.approx(-0.5)
    assert c["rr"]["korelacja"] == pytest.approx(1.0) and c["rr"]["maks_roznica_bezwzgledna"] == 0.0
