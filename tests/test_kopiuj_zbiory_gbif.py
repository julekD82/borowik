import importlib.util
import pathlib

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "kopiuj_zbiory_gbif", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "kopiuj_zbiory_gbif.py")
kz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kz)


def test_pseudonyms_are_sequential_and_shared_across_files():
    a = pd.DataFrame({"key": [1, 2, 3], "observer": ["Ala", "Olek", "Ala"], "observer_id": ["Ala", "Olek", "Ala"]})
    b = pd.DataFrame({"key": [4, 5, 6], "observer": [np.nan, "Olek", "Zenon"],
                      "observer_id": ["anon_4", "Olek", "Zenon"]})
    out, mapping = kz.pseudonymize({"a.csv": a, "b.csv": b})
    assert mapping == {"Ala": "obs_001", "Olek": "obs_002", "Zenon": "obs_003"}
    assert out["a.csv"]["observer"].tolist() == ["obs_001", "obs_002", "obs_001"]
    assert out["b.csv"]["observer_id"].tolist() == ["anon_4", "obs_002", "obs_003"]
    assert np.isnan(out["b.csv"]["observer"].iloc[0])
    assert a["observer"].tolist() == ["Ala", "Olek", "Ala"]  # wejscie nie jest zmieniane
    joined = pd.concat(out.values()).astype(str).to_numpy().ravel().tolist()
    assert not {"Ala", "Olek", "Zenon"} & set(joined)
