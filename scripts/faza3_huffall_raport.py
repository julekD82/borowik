"""Faza 3: raport wariantu population_split: huff_all (decyzja wlasciciela
2026-09-29) na tle huff i gravity. Tylko z cache.

Zawartosc: udzial typow punktow w presji, profil P przy Lublincu, Spearman R,
top-20 i rejony wzgledem huff i gravity, udzial lasu z P > 0,5 oraz tabela
stabilnosci +-30% (S, zasieg i waga wjazdow, zasieg i waga parkingow, zasieg
zbierania ludnosci, c). NIE zmienia parametrow profilu.

    python scripts/faza3_huffall_raport.py
"""
import copy
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

import faza3_huff_raport as h  # noqa: E402
import faza3_raport as base  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402


def main() -> int:
    t0 = time.time()
    profile = load_profile("profiles/boletus_edulis.yaml")
    ctx = h.Ctx("cache", profile)
    out_dir = base.OUT_DIR
    report = {"stand_count": int(len(ctx.stands)), "mask_passing": int(ctx.mask.sum()),
              "gravity_median_P_mask": ctx.target, "c": ctx.cfg["external_option_c"]}

    variants = {}
    for split in ("huff", "huff_all"):
        cfg = copy.deepcopy(ctx.cfg)
        cfg["population_split"] = split
        model = ctx.model(cfg)
        out = ctx.raw(model)
        raw = out["access_raw"].values
        s_fit = ctx.fit_s(raw)
        p = 1.0 - np.exp(-raw / s_fit)
        variants[split] = {"cfg": cfg, "model": model, "out": out, "S": s_fit, "P": p, "R": ctx.r_of(p)}
        variants[split]["regions"] = ctx.regions(variants[split]["R"])
        print(f"{split}: S={s_fit:.4f} ({time.time() - t0:.0f}s)", flush=True)
    r_grav = ctx.r_of(ctx.p_grav)
    reg_grav = ctx.regions(r_grav)
    ha, hu = variants["huff_all"], variants["huff"]
    report["S_profile_huff_all"] = ctx.cfg["saturation_s"]

    report["porownanie"] = {}
    for split, v in variants.items():
        p, r = v["P"], v["R"]
        report["porownanie"][split] = {
            "S_fit": v["S"], "median_P_mask": float(np.median(p[ctx.mask])),
            "share_forest_area_P_gt_0_5": base.area_share(ctx.stands, p > 0.5),
            "spearman_P_vs_gravity_mask": float(spearmanr(ctx.p_grav[ctx.mask], p[ctx.mask])[0]),
            "spearman_R_vs_gravity_mask": float(spearmanr(r_grav[ctx.mask], r[ctx.mask])[0]),
            "top20_overlap_vs_gravity": len(ctx.top20(r_grav) & ctx.top20(r)),
            "regions_kept_vs_gravity": h.kept_regions(reg_grav, v["regions"]),
            "lubliniec_belt": h.lubliniec_belt(ctx, v["model"], p),
        }
    report["porownanie"]["huff_all_vs_huff"] = {
        "spearman_P_mask": float(spearmanr(hu["P"][ctx.mask], ha["P"][ctx.mask])[0]),
        "spearman_R_mask": float(spearmanr(hu["R"][ctx.mask], ha["R"][ctx.mask])[0]),
        "top20_overlap": len(ctx.top20(hu["R"]) & ctx.top20(ha["R"])),
        "regions_kept": h.kept_regions(hu["regions"], ha["regions"]),
    }
    report["udzialy_huff_all"] = h.contribution_shares(ctx, ha["model"], ha["out"])
    report["udzialy_huff"] = h.contribution_shares(ctx, hu["model"], hu["out"])
    pts = ha["model"].points
    report["A_osoby"] = {t: {q: float(v) for q, v in pts.loc[pts["type"] == t, "A"].describe(percentiles=[.1, .5, .9]).items()
                             if q in ("count", "10%", "50%", "90%", "max")}
                         for t in ("parking", "entrance", "gate", "settlement") if (pts["type"] == t).any()}
    report["regions_lista"] = {k: [[round(float(x)), round(float(y))] for x, y in c] for k, c in
                               (("gravity", reg_grav), ("huff", hu["regions"]), ("huff_all", ha["regions"]))}

    # --- stabilnosc +-30% ---------------------------------------------------------------------
    s0, base_top, base_reg = ha["S"], ctx.top20(ha["R"]), ha["regions"]

    def evaluate(label, cfg, s):
        raw = ctx.raw(ctx.model(cfg))["access_raw"].values
        p = 1.0 - np.exp(-raw / s)
        r = ctx.r_of(p)
        return {"parametr": label, "top20_zostaje": len(base_top & ctx.top20(r)),
                "rejony_zostaje": h.kept_regions(base_reg, ctx.regions(r)),
                "mediana_P_maska": float(np.median(p[ctx.mask])),
                "spearman_R_vs_baza": float(spearmanr(ha["R"][ctx.mask], r[ctx.mask])[0])}

    def mult(types, keys, field, f):
        for k in keys:
            types[k][field] *= f

    rows = []
    for label, kind in (("S", "S"), ("zasieg wjazdow (wjazd+szlaban)", "e_range"), ("waga wjazdow (wjazd+szlaban)", "e_w"),
                        ("zasieg parkingow", "p_range"), ("waga parkingow", "p_w"),
                        ("zasieg zbierania ludnosci", "pop"), ("c (opcja zewnetrzna)", "c")):
        for f in (0.7, 1.3):
            cfg = copy.deepcopy(ha["cfg"])
            s = s0
            if kind == "S":
                s = s0 * f
            elif kind == "e_range":
                mult(cfg["types"], ("entrance", "gate"), "range_m", f)
            elif kind == "e_w":
                mult(cfg["types"], ("entrance", "gate"), "weight", f)
            elif kind == "p_range":
                mult(cfg["types"], ("parking",), "range_m", f)
            elif kind == "p_w":
                mult(cfg["types"], ("parking",), "weight", f)
            elif kind == "pop":
                mult(cfg["types"], ("parking", "entrance", "gate", "road_fallback"), "attractiveness_range_km", f)
            elif kind == "c":
                cfg["external_option_c"] *= f
            row = evaluate(label, cfg, s)
            row["zmiana"] = f"{int(round((f - 1) * 100)):+d}%"
            rows.append(row)
            print(f"stab {label} {row['zmiana']}: top20 {row['top20_zostaje']}/20 rejony {row['rejony_zostaje']}/5 ({time.time() - t0:.0f}s)", flush=True)
    report["stabilnosc_huff_all"] = {"baza_S": s0, "wiersze": rows}

    pd.DataFrame({"stand_id": ctx.stands["stand_id"], "mask": ctx.mask, "P_gravity": ctx.p_grav,
                  "P_huff": hu["P"], "P_huff_all": ha["P"], "R_gravity": r_grav, "R_huff": hu["R"],
                  "R_huff_all": ha["R"], "top_type_huff_all": ha["out"]["top_point_type"]}
                 ).to_csv(out_dir / "roznice_P_huff_all.csv", index=False)
    report["czas_s"] = round(time.time() - t0, 1)
    (out_dir / "raport_huff_all.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print("GOTOWE", report["czas_s"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
