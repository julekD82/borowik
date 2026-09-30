"""Plan 2.8 -- EKSPLORACJA PO ZOBACZENIU WYNIKOW notebooks/17_bielefeld.py (nie decyzyjnie, poza regulami).

Pytanie: czy dodatni efekt sredniej TX z 5 dni (czesc B) dotyczy temperatur maksymalnych, czy po prostu
ciepla ostatnich dni (srednia TG z 5 dni; w aplikacji jest juz tmean5)? Ten sam model bazowy co w B
(tygodnie, T20 + T20^2 + P_K0), log-wiarygodnosc "zostaw jeden rok".

Run: .venv/Scripts/python.exe notebooks/17b_bielefeld_eksploracja.py
"""
import importlib.util
import json
import pathlib
from datetime import date

from pipeline import bielefeld as bf
from pipeline.eobs import EobsStore

spec = importlib.util.spec_from_file_location("nb17", "notebooks/17_bielefeld.py")
nb17 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb17)


def main() -> None:
    store = EobsStore("cache", region="BI")
    daily = store.daily(*store.cell(*bf.CENTROID), date(1990, 12, 1), date(2025, 12, 31))
    f = nb17.model_frame(daily, nb17.load_counts())
    f["TG_mean5"] = daily["tg"].rolling(5).mean().reindex(f.index)
    f["TX_minus_TG_5"] = f["TX_mean5"] - f["TG_mean5"]
    base = nb17.loyo_ll(f, nb17.design(f, ["P_K0"]))
    out = {"model_bazowy": "T20 + T20^2 + P_K0 (tygodnie)"}
    for extra in (["TG_mean5"], ["TX_mean5"], ["TG_mean5", "TX_mean5"], ["TG_mean5", "TX_minus_TG_5"]):
        X = nb17.design(f, ["P_K0"], extra)
        d = nb17.loyo_ll(f, X) - base
        fit = bf.fit_nb1(f["y"], X, f["rok"], f["tydzien"], se=True)
        out[" + ".join(extra)] = {
            "dLL_LOYO": round(float(d.sum()), 3), "lat_lepiej": int((d > 0).sum()),
            "beta": [round(float(b), 4) for b in fit["beta"][-len(extra):]],
            "se": [round(float(s), 4) for s in fit["beta_se"][-len(extra):]]}
    out["korelacja_TG_mean5_TX_mean5"] = round(float(f["TG_mean5"].corr(f["TX_mean5"])), 3)
    path = pathlib.Path("notebooks/output/walidacja/17b_bielefeld_eksploracja.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
