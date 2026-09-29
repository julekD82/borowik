"""Faza 3, ciag dalszy: diagnoza wjazdow, porownanie population_split none/huff
i stabilnosc rankingu wariantu huff. Tylko z cache (jak faza3_raport.py).

  1. wjazdy: podtypy/zrodla, udzial kazdego typu punktu i podtypu wjazdu w
     lacznej presji (suma presji surowej po wydzieleniach w masce), 5 losowych
     wjazdow z kazdego podtypu do kontrola_reczna.csv;
  2. none vs huff: S dobrane do tej samej mediany P co gravity, profil P przy
     Lublincu, udzial lasu z P > 0,5, Spearman P i R, top-20, rejony;
  3. stabilnosc huff: -30% / +30% jednego parametru naraz (S, zasieg i waga
     wjazdow, zasieg i waga parkingow, zasieg zbierania ludnosci): ile z top-20
     (>= 0,5 ha) i ile z 5 rejonow zostaje. NIE zmienia parametrow profilu.

    python scripts/faza3_huff_raport.py
"""
import copy
import dataclasses
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

import faza3_raport as base  # noqa: E402
from pipeline.access_points import build_access_set  # noqa: E402
from pipeline.access_pressure import build_access_model, compute_access_pressure  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402
from pipeline.regions import group_into_regions  # noqa: E402
from pipeline.scoring import compute_ranking  # noqa: E402

OUT_DIR = base.OUT_DIR
CENTROID_MATCH_M = 1600.0
MIN_AREA_M2 = 5000.0   # 0,5 ha: mniejsze wydzielenia interfejs chowa jako samodzielne cele
CAR_TYPES_RANGE = ("parking", "entrance", "gate", "road_fallback")


class Ctx:
    def __init__(self, cache_dir, profile):
        self.profile = profile
        self.cfg = profile["pressure"]["access_points"]
        self.alpha = profile["pressure"]["alpha_default"]
        data = base.load_all(pathlib.Path(cache_dir), profile)
        self.data = data
        self.stands = data["stands"]
        cent = self.stands.geometry.centroid
        self.xy = np.array([(c.x, c.y) for c in cent])
        self.mask = self.stands["mask"].values.astype(bool)
        self.area = self.stands.geometry.area.values
        self.p_grav = self.stands["P"].values.astype(float)
        self.aset = build_access_set(
            forest_boundary=data["forest"], sources=data["sources"], osm_parking=data["osm"].get("parking"),
            pop_points=data["pop"], tiles=data["tiles"], cfg=self.cfg)
        self.pop_xy = np.array([(g.x, g.y) for g in data["pop"].geometry])
        self.pop_vals = data["pop"]["population"].astype(float).values
        self.frame = self.stands[["stand_id", "geometry", "mask"]].copy()
        self.frame["mask_full"] = self.frame["mask"]
        self.target = float(np.median(self.p_grav[self.mask]))

    def model(self, cfg):
        return build_access_model(self.aset, self.pop_xy, self.pop_vals, cfg)

    def raw(self, model):
        return compute_access_pressure(self.xy, model)

    def fit_s(self, raw):
        return base.solve_s(raw[self.mask], self.target)

    def r_of(self, p):
        return np.array([compute_ranking(m, h, f, p=pp, alpha=self.alpha) for m, h, f, pp in
                         zip(self.stands["mask"], self.stands["H"], self.stands["F_loc"], p)])

    def regions(self, r):
        f = self.frame.copy()
        f["R_final"] = r
        g = group_into_regions(f, self.profile)
        return np.array([(row.geometry.centroid.x, row.geometry.centroid.y) for _, row in g.iterrows()]).reshape(-1, 2)

    def top20(self, r):
        ok = self.mask & (self.area >= MIN_AREA_M2)
        idx = np.where(ok)[0]
        return set(self.stands["stand_id"].values[idx[np.argsort(-r[idx])[:20]]])


def kept_regions(base_c, other_c):
    return int(sum(1 for c in base_c if len(other_c) and np.min(np.hypot(other_c[:, 0] - c[0], other_c[:, 1] - c[1])) <= CENTROID_MATCH_M))


def lubliniec_belt(ctx, model, p):
    st = model.points[model.points["type"] == "settlement"]
    big = st[st["weight_pop"] >= 500]
    if not len(big):
        return []
    d_town = cKDTree(np.array([(g.x, g.y) for g in big.geometry])).query(ctx.xy)[0]
    e, n = base.TO_2180.transform(base.LUBLINIEC[1], base.LUBLINIEC[0])
    near = np.hypot(ctx.xy[:, 0] - e, ctx.xy[:, 1] - n) <= 8000
    rows = []
    bins = [0, 500, 1000, 2000, 3000, 5000, 1e9]
    for lo, hi in zip(bins[:-1], bins[1:]):
        sel = near & (d_town >= lo) & (d_town < hi)
        if sel.sum():
            rows.append({"od_osiedla_m": f"{lo}-{hi if hi < 1e9 else 'inf'}", "wydzielen": int(sel.sum()),
                         "P": float(p[sel].mean()), "P_gravity": float(ctx.p_grav[sel].mean())})
    return rows


def contribution_shares(ctx, model, out):
    """Udzial typow i podtypow wjazdow w lacznej presji surowej w masce.
    Wklad kazdego typu/podtypu liczony osobno na modelu z podzbiorem punktow
    (A_norm policzone wczesniej, wiec wklad jest addytywny)."""
    m = ctx.mask
    total = float(out["access_raw"].values[m].sum())
    shares = {}
    for col in [c for c in out.columns if c.startswith("pcontrib_")]:
        shares[col[len("pcontrib_"):]] = float(out[col].values[m].sum() / total)
    pts = model.points
    sub = {}
    combos = pts[pts["type"].isin(["entrance", "gate", "parking"])].groupby(["type", "subtype", "source"]).size().index
    for t_, s_, src in combos:
        keep = ~((pts["type"] == t_) & ~((pts["subtype"] == s_) & (pts["source"] == src)))
        sub_model = dataclasses.replace(model, points=pts[keep].reset_index(drop=True))
        o = ctx.raw(sub_model)
        key = f"{t_}/{s_}/{src}"
        sub[key] = float(o[f"pcontrib_{t_}"].values[m].sum() / total)
    top_type = pd.Series(out["top_point_type"].values[m]).value_counts(normalize=True).to_dict()
    return {"udzial_w_presji_surowej_typ": shares, "udzial_podtypow": sub, "najczesciej_glowny_wklad_typ": top_type}


def main() -> int:
    t0 = time.time()
    profile = load_profile("profiles/boletus_edulis.yaml")
    ctx = Ctx("cache", profile)
    cfg0 = ctx.cfg
    report = {"stand_count": int(len(ctx.stands)), "mask_passing": int(ctx.mask.sum()),
              "gravity_median_P_mask": ctx.target}

    # --- 2. none vs huff -------------------------------------------------------------------
    variants = {}
    for split in ("none", "huff"):
        cfg = copy.deepcopy(cfg0)
        cfg["population_split"] = split
        model = ctx.model(cfg)
        out = ctx.raw(model)
        raw = out["access_raw"].values
        s_fit = ctx.fit_s(raw)
        p = 1.0 - np.exp(-raw / s_fit)
        variants[split] = {"cfg": cfg, "model": model, "out": out, "raw": raw, "S": s_fit, "P": p, "R": ctx.r_of(p)}
        print(f"{split}: S={s_fit:.4f} ({time.time() - t0:.0f}s)", flush=True)
    r_grav = ctx.r_of(ctx.p_grav)
    reg_grav = ctx.regions(r_grav)
    for split, v in variants.items():
        v["regions"] = ctx.regions(v["R"])
    a_h = variants["huff"]["model"].points
    report["huff_A_norm"] = {t: {"mediana": float(a_h.loc[a_h["type"] == t, "A_norm"].median()),
                                 "p90": float(a_h.loc[a_h["type"] == t, "A_norm"].quantile(0.9))}
                             for t in ("parking", "entrance", "gate", "settlement") if (a_h["type"] == t).any()}
    a_n = variants["none"]["model"].points
    report["none_A_norm"] = {t: {"mediana": float(a_n.loc[a_n["type"] == t, "A_norm"].median()),
                                 "p90": float(a_n.loc[a_n["type"] == t, "A_norm"].quantile(0.9))}
                             for t in ("parking", "entrance", "gate", "settlement") if (a_n["type"] == t).any()}
    cmp_ = {}
    for split, v in variants.items():
        p, r = v["P"], v["R"]
        cmp_[split] = {
            "S_fit": v["S"],
            "median_P_mask": float(np.median(p[ctx.mask])),
            "share_forest_area_P_gt_0_5": base.area_share(ctx.stands, p > 0.5),
            "share_forest_area_P_gt_0_5_mask": base.area_share(ctx.stands[ctx.mask], p[ctx.mask] > 0.5),
            "spearman_P_vs_gravity_mask": float(spearmanr(ctx.p_grav[ctx.mask], p[ctx.mask])[0]),
            "spearman_R_vs_gravity_mask": float(spearmanr(r_grav[ctx.mask], r[ctx.mask])[0]),
            "top20_overlap_vs_gravity": len(ctx.top20(r_grav) & ctx.top20(r)),
            "regions_kept_vs_gravity": kept_regions(reg_grav, v["regions"]),
            "lubliniec_belt": lubliniec_belt(ctx, v["model"], p),
        }
    cmp_["huff_vs_none"] = {
        "spearman_P_mask": float(spearmanr(variants["none"]["P"][ctx.mask], variants["huff"]["P"][ctx.mask])[0]),
        "spearman_R_mask": float(spearmanr(variants["none"]["R"][ctx.mask], variants["huff"]["R"][ctx.mask])[0]),
        "top20_overlap": len(ctx.top20(variants["none"]["R"]) & ctx.top20(variants["huff"]["R"])),
        "regions_kept": kept_regions(variants["none"]["regions"], variants["huff"]["regions"]),
    }
    report["porownanie_none_huff"] = cmp_
    report["regions_lista"] = {k: [[round(float(x), 0), round(float(y), 0)] for x, y in c]
                               for k, c in (("gravity", reg_grav), ("none", variants["none"]["regions"]),
                                            ("huff", variants["huff"]["regions"]))}

    # --- 1. diagnoza wjazdow -------------------------------------------------------------------
    pts = variants["huff"]["model"].points
    report["wjazdy"] = {
        "liczba_wg_podtypu_i_zrodla": {f"{t}/{s}/{src}": int(n) for (t, s, src), n in
                                        pts[pts["type"].isin(["entrance", "gate"])].groupby(["type", "subtype", "source"]).size().items()},
        "wszystkie_punkty_wg_typu_zrodla": {f"{t}/{src}": int(n) for (t, src), n in pts.groupby(["type", "source"]).size().items()},
    }
    report["wjazdy"]["udzialy_huff"] = contribution_shares(ctx, variants["huff"]["model"], variants["huff"]["out"])
    report["wjazdy"]["udzialy_none"] = contribution_shares(ctx, variants["none"]["model"], variants["none"]["out"])

    rng = np.random.default_rng(42)
    manual_new = []
    for sub in ("crossing_public", "crossing_track", "junction"):
        sel = pts[(pts["type"] == "entrance") & (pts["subtype"] == sub)]
        if not len(sel):
            continue
        take = sel.iloc[rng.choice(len(sel), size=min(5, len(sel)), replace=False)]
        for _, r in take.iterrows():
            lon, lat = base.TO_4326.transform(r.geometry.x, r.geometry.y)
            manual_new.append({"rodzaj": f"wjazd_{sub}", "typ": r["type"], "podtyp": r["subtype"], "zrodlo": r["source"],
                               "id": r["point_id"], "nazwa": r["name"], "lat": round(lat, 6), "lon": round(lon, 6),
                               "widok_satelitarny": f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},250m/data=!3m1!1e3"})
    kr = OUT_DIR / "kontrola_reczna.csv"
    old = pd.read_csv(kr) if kr.exists() else pd.DataFrame()
    if len(old):
        old = old[~old["rodzaj"].astype(str).str.startswith("wjazd_")]
    pd.concat([old, pd.DataFrame(manual_new)], ignore_index=True).to_csv(kr, index=False, encoding="utf-8")

    # --- 3. stabilnosc huff -----------------------------------------------------------------------
    hv = variants["huff"]
    s0 = hv["S"]
    base_top = ctx.top20(hv["R"])
    base_regions = hv["regions"]

    def evaluate(label, cfg, s):
        model = ctx.model(cfg)
        raw = ctx.raw(model)["access_raw"].values
        p = 1.0 - np.exp(-raw / s)
        r = ctx.r_of(p)
        return {"parametr": label, "top20_zostaje": len(base_top & ctx.top20(r)),
                "rejony_zostaje": kept_regions(base_regions, ctx.regions(r)),
                "mediana_P_maska": float(np.median(p[ctx.mask])),
                "spearman_R_vs_baza": float(spearmanr(hv["R"][ctx.mask], r[ctx.mask])[0])}

    def scaled(mutator, factor):
        c = copy.deepcopy(hv["cfg"])
        mutator(c["types"], factor)
        return c

    def mult(types, keys, field, f):
        for k in keys:
            types[k][field] *= f

    tests = [
        ("S", lambda c, f: None, "S"),
        ("zasieg wjazdow (wjazd+szlaban)", lambda t, f: mult(t, ("entrance", "gate"), "range_m", f), None),
        ("waga wjazdow (wjazd+szlaban)", lambda t, f: mult(t, ("entrance", "gate"), "weight", f), None),
        ("zasieg parkingow", lambda t, f: mult(t, ("parking",), "range_m", f), None),
        ("waga parkingow", lambda t, f: mult(t, ("parking",), "weight", f), None),
        ("zasieg zbierania ludnosci", lambda t, f: mult(t, CAR_TYPES_RANGE, "attractiveness_range_km", f), None),
    ]
    stability = []
    for label, mut, kind in tests:
        for f in (0.7, 1.3):
            if kind == "S":
                cfg = copy.deepcopy(hv["cfg"])
                row = evaluate(label, cfg, s0 * f)
            else:
                row = evaluate(label, scaled(mut, f), s0)
            row["zmiana"] = f"{int(round((f - 1) * 100)):+d}%"
            stability.append(row)
            print(f"stab {label} {row['zmiana']}: top20 {row['top20_zostaje']}/20 rejony {row['rejony_zostaje']}/5 ({time.time() - t0:.0f}s)", flush=True)
    report["stabilnosc_huff"] = {"baza_S": s0, "top20_min_area_ha": 0.5, "wiersze": stability}

    pd.DataFrame({"stand_id": ctx.stands["stand_id"], "mask": ctx.mask, "P_gravity": ctx.p_grav,
                  "P_none": variants["none"]["P"], "P_huff": variants["huff"]["P"],
                  "R_gravity": r_grav, "R_none": variants["none"]["R"], "R_huff": variants["huff"]["R"],
                  "top_type_huff": variants["huff"]["out"]["top_point_type"]}).to_csv(OUT_DIR / "roznice_P_huff.csv", index=False)
    report["czas_s"] = round(time.time() - t0, 1)
    (OUT_DIR / "raport_huff.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print("GOTOWE", report["czas_s"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
