"""Faza 3: raport wariantu population_split: two_stage (decyzja wlasciciela
2026-09-29) na tle huff_all, huff i gravity. Tylko z cache.

KRYTERIUM SENSOWNOSCI ustalone PRZED obejrzeniem wynikow (sprawdzane, nie
stroimy pod nie):
  (a) P przy osiedlach "wyraznie wyzsze" niz 2-3 km w glab lasu: srednia P
      w pasach 0-0,5 i 0,5-1 km (wazona liczba wydzielen) >= P(2-3 km) + 0,10;
  (b) brak ponownego wzrostu dalej: P(3-5 km) i P(> 5 km) <= P(2-3 km) + 0,05.
Kryterium stabilnosci: top-20 (>= 0,5 ha) zostaje w >= 14 z 20 w kazdym
wariancie +-30% (p_walk_max, c, zasieg wjazdow, zasieg parkingow).

    python scripts/faza3_two_stage_raport.py
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

NEAR_MARGIN = 0.10
RISE_TOLERANCE = 0.05
STAB_MIN_TOP20 = 14


def criterion(belt: list) -> dict:
    by = {b["od_osiedla_m"]: b for b in belt}
    near_bands = [by[k] for k in ("0-500", "500-1000") if k in by]
    n = sum(b["wydzielen"] for b in near_bands)
    near = sum(b["P"] * b["wydzielen"] for b in near_bands) / n if n else float("nan")
    mid = by["2000-3000"]["P"]
    far35, far5 = by.get("3000-5000", {}).get("P"), by.get("5000-inf", {}).get("P")
    a = bool(near >= mid + NEAR_MARGIN)
    b = bool(far35 is not None and far35 <= mid + RISE_TOLERANCE and far5 is not None and far5 <= mid + RISE_TOLERANCE)
    return {"P_przy_osiedlu_0_1km": near, "P_2_3km": mid, "P_3_5km": far35, "P_powyzej_5km": far5,
            "a_wyraznie_wyzsze_przy_osiedlu": a, "b_brak_ponownego_wzrostu": b, "spelnione": a and b,
            "progi": {"margines_a": NEAR_MARGIN, "tolerancja_b": RISE_TOLERANCE}}


def main() -> int:
    t0 = time.time()
    profile = load_profile("profiles/boletus_edulis.yaml")
    ctx = h.Ctx("cache", profile)
    out_dir = base.OUT_DIR
    report = {"stand_count": int(len(ctx.stands)), "mask_passing": int(ctx.mask.sum()),
              "gravity_median_P_mask": ctx.target,
              "params": {k: ctx.cfg[k] for k in ("external_option_c", "walk_share_max", "walk_reach_km")}}
    d_forest = ctx.pop_d_forest
    report["oczka_GUS"] = {"razem": int(len(d_forest)), "do_1_5km_od_lasu": int(np.isfinite(d_forest).sum()),
                           "w_lesie_lub_przy_lesie_0m": int((d_forest == 0).sum())}

    variants = {}
    for split in ("two_stage", "huff_all", "huff"):
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
    ts = variants["two_stage"]
    report["S_fit_two_stage"] = ts["S"]
    report["S_profile_two_stage"] = ctx.cfg["saturation_s"]

    report["porownanie"] = {}
    for split, v in variants.items():
        p, r = v["P"], v["R"]
        belt = h.lubliniec_belt(ctx, v["model"], p)
        report["porownanie"][split] = {
            "S_fit": v["S"], "median_P_mask": float(np.median(p[ctx.mask])),
            "share_forest_area_P_gt_0_5": base.area_share(ctx.stands, p > 0.5),
            "spearman_P_vs_gravity_mask": float(spearmanr(ctx.p_grav[ctx.mask], p[ctx.mask])[0]),
            "spearman_R_vs_gravity_mask": float(spearmanr(r_grav[ctx.mask], r[ctx.mask])[0]),
            "top20_overlap_vs_gravity": len(ctx.top20(r_grav) & ctx.top20(r)),
            "regions_kept_vs_gravity": h.kept_regions(reg_grav, v["regions"]),
            "lubliniec_belt": belt,
        }
    belt_grav = None
    report["porownanie"]["gravity_belt_P"] = h.lubliniec_belt(ctx, ts["model"], ctx.p_grav)
    for other in ("huff_all", "huff"):
        o = variants[other]
        report["porownanie"][f"two_stage_vs_{other}"] = {
            "spearman_P_mask": float(spearmanr(o["P"][ctx.mask], ts["P"][ctx.mask])[0]),
            "spearman_R_mask": float(spearmanr(o["R"][ctx.mask], ts["R"][ctx.mask])[0]),
            "top20_overlap": len(ctx.top20(o["R"]) & ctx.top20(ts["R"])),
            "regions_kept": h.kept_regions(o["regions"], ts["regions"]),
        }
    report["kryterium_sensownosci"] = criterion(report["porownanie"]["two_stage"]["lubliniec_belt"])
    report["udzialy_two_stage"] = h.contribution_shares(ctx, ts["model"], ts["out"])
    report["udzialy_huff_all"] = h.contribution_shares(ctx, variants["huff_all"]["model"], variants["huff_all"]["out"])
    pts = ts["model"].points
    report["A_osoby"] = {t: {q: float(v) for q, v in pts.loc[pts["type"] == t, "A"].describe(percentiles=[.1, .5, .9]).items()
                             if q in ("count", "10%", "50%", "90%", "max")}
                         for t in ("parking", "entrance", "gate", "settlement") if (pts["type"] == t).any()}
    report["regions_lista"] = {k: [[round(float(x)), round(float(y))] for x, y in c] for k, c in
                               (("gravity", reg_grav), ("two_stage", ts["regions"]),
                                ("huff_all", variants["huff_all"]["regions"]), ("huff", variants["huff"]["regions"]))}

    # --- stabilnosc +-30% ------------------------------------------------------------------------
    s0, base_top, base_reg = ts["S"], ctx.top20(ts["R"]), ts["regions"]

    def evaluate(label, cfg):
        model = ctx.model(cfg)
        raw = ctx.raw(model)["access_raw"].values
        p = 1.0 - np.exp(-raw / s0)
        r = ctx.r_of(p)
        return {"parametr": label, "top20_zostaje": len(base_top & ctx.top20(r)),
                "rejony_zostaje": h.kept_regions(base_reg, ctx.regions(r)),
                "mediana_P_maska": float(np.median(p[ctx.mask])),
                "spearman_R_vs_baza": float(spearmanr(ts["R"][ctx.mask], r[ctx.mask])[0]),
                "kryterium_spelnione": criterion(h.lubliniec_belt(ctx, model, p))["spelnione"]}

    rows = []
    for label, kind in (("p_walk_max", "walk"), ("c (opcja zewnetrzna)", "c"),
                        ("zasieg wjazdow (wjazd+szlaban)", "e_range"), ("zasieg parkingow", "p_range")):
        for f in (0.7, 1.3):
            cfg = copy.deepcopy(ts["cfg"])
            if kind == "walk":
                cfg["walk_share_max"] *= f
            elif kind == "c":
                cfg["external_option_c"] *= f
            elif kind == "e_range":
                for k in ("entrance", "gate"):
                    cfg["types"][k]["range_m"] *= f
            elif kind == "p_range":
                cfg["types"]["parking"]["range_m"] *= f
            row = evaluate(label, cfg)
            row["zmiana"] = f"{int(round((f - 1) * 100)):+d}%"
            rows.append(row)
            print(f"stab {label} {row['zmiana']}: top20 {row['top20_zostaje']}/20 rejony {row['rejony_zostaje']}/5 kryt={row['kryterium_spelnione']} ({time.time() - t0:.0f}s)", flush=True)
    report["stabilnosc_two_stage"] = {"baza_S": s0, "min_top20_wymagane": STAB_MIN_TOP20, "wiersze": rows,
                                      "min_top20": min(r["top20_zostaje"] for r in rows)}

    pd.DataFrame({"stand_id": ctx.stands["stand_id"], "mask": ctx.mask, "P_gravity": ctx.p_grav,
                  "P_huff": variants["huff"]["P"], "P_huff_all": variants["huff_all"]["P"], "P_two_stage": ts["P"],
                  "R_gravity": r_grav, "R_two_stage": ts["R"], "top_type_two_stage": ts["out"]["top_point_type"]}
                 ).to_csv(out_dir / "roznice_P_two_stage.csv", index=False)
    report["czas_s"] = round(time.time() - t0, 1)
    (out_dir / "raport_two_stage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print("GOTOWE", report["czas_s"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
