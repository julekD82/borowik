# Raport — Faza 1.6 (pełniejsze wykorzystanie danych BDL)

Gałąź: `ulepszenia-faza1-6` (z `master`, po scaleniu Fazy 1 i 1.5).
Prowadzony na bieżąco w trakcie realizacji (zasada 0.9 z `docs/PLAN_WDROZENIA.md`).

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 1.6.1 Inwentaryzacja paczek | DONE | `docs/BDL_slownik_pol.md` |
| 1.6.2 Aktualizacja wieku (korekta, za flagą) | DONE | `pipeline/age_update.py`, wpięte w `pipeline/orchestrate.py` |
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

## 1.6.2 Aktualizacja wieku

Nowy `pipeline/age_update.py::update_age(spec_age, a_year, analysis_year, enabled)`,
wpięty w `pipeline/orchestrate.py::run_poc` przed `passes_mask`/`compute_habitat`
(korekta obejmuje maskę wieku i S_age, zgodnie z wymogiem planu). Config
`age.update_to_analysis_year` (domyślnie `true`) w `profiles/boletus_edulis.yaml`.
Status per wydzielenie (`age_update_status`: `skorygowano`/`wylaczona`/
`brak_roku_stanu`) w `diagnostics_{day}.json`; liczniki
`age_update_enabled`/`age_update_missing_year_count` w `run_manifest_{day}.json`
(`counts`).

Testy: `tests/test_age_update.py` (funkcja czysta: wyłączona, przesunięcie,
brak `a_year`/NaN, brak `spec_age`, przekroczenie progu maski) +
`tests/test_orchestrate.py` (integracja: młode wydzielenie z 2020 realnie
przechodzi maskę w 2026 gdy włączone, zostaje odrzucone gdy wyłączone, brak
`a_year` nie crashuje i jest zliczony).

## Rulingi (decyzje bez pytania właściciela, zgodnie z zasadą 0.8)

- **1.6.2 źródło "rok stanu opisu":** plan dopuszcza pierwszeństwo metadanych
  paczki nad `a_year` WFS. `pipeline/bdl_packages.py` nie parsuje dziś
  per-wydzieleniowego `a_year` z paczki (tylko skład gatunkowy), a
  `a_year` z WFS jest już niezawodnie obecne na każdym wierszu (używane do
  `stand_id`) i identyczne z `a_year` w paczce dla sprawdzonych wydzieleń
  (weryfikacja B1: `docs/bdl-paczki-rozpoznanie.md`). Użyto wyłącznie
  `a_year` z WFS jako źródła roku stanu, bez dodawania drugiej ścieżki przez
  metadane paczki. Koszt błędu: żaden znany przypadek realnych danych, w
  którym `a_year` WFS różniłby się od roku stanu paczki dla tego samego
  wydzielenia; gdyby się pojawił, korekta wieku użyłaby nieco innego roku
  niż paczka, nie inny kierunek błędu.
