# Raport — Faza 1.6 (pełniejsze wykorzystanie danych BDL)

Gałąź: `ulepszenia-faza1-6` (z `master`, po scaleniu Fazy 1 i 1.5).
Prowadzony na bieżąco w trakcie realizacji (zasada 0.9 z `docs/PLAN_WDROZENIA.md`).

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 1.6.1 Inwentaryzacja paczek | DONE | `docs/BDL_slownik_pol.md` |
| 1.6.2 Aktualizacja wieku (korekta, za flagą) | w toku | |
| 1.6.3 Skład z niższych pięter (korekta, za flagą) | w toku | |
| 1.6.4 Cechy do diagnostyki (bez wagi w R) | w toku | |
| 1.6.5 Łatwość szukania w karcie | w toku | |
| 1.6.6 Przebieg i raport | w toku | |

## 1.6.1 Inwentaryzacja paczek

Zrobione na 9 realnie dostępnych paczkach (`BDL/BDL_02_*_2026/`, RDLP
Katowice, rok stanu 2026) — szczegóły i decyzje o progu 50% w
`docs/BDL_slownik_pol.md`. Skrót:
- Dobrze wypełnione (≥ 95%): `site_class_cd` (bonitacja gat. panującego),
  `soil_subtype_cd`, `degradation_cd`, `stand_struct_cd`, `veg_cover_cd`,
  geometria `G_COMPARTMENT`.
- Niezdatne (< 50% lub 0%): `plant_comm_cd` (zbiorowisko roślinne, ~0%),
  `tree_stock_cd` (zadrzewienie, 0%), `density_cd` na warstwach
  `PODSZ`/`PODR` (zagęszczenie podszytu/podrostu, 0%), `damage_degree`,
  `cause_cd`.
- Ograniczenie: `f_arod_cue` (zabiegi) ma tylko **planowane** wskazania, bez
  dokładnej daty (tylko rok paczki) — nie ma w paczce tabeli wykonanych
  zabiegów.

## Rulingi (decyzje bez pytania właściciela, zgodnie z zasadą 0.8)

Będą dopisywane w trakcie realizacji kolejnych zadań.
