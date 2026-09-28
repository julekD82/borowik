# Raport — Faza 1.6 (pełniejsze wykorzystanie danych BDL)

Gałąź: `ulepszenia-faza1-6` (z `master`, po scaleniu Fazy 1 i 1.5).
Prowadzony na bieżąco w trakcie realizacji (zasada 0.9 z `docs/PLAN_WDROZENIA.md`).

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 1.6.1 Inwentaryzacja paczek | DONE | `docs/BDL_slownik_pol.md` |
| 1.6.2 Aktualizacja wieku (korekta, za flagą) | DONE | `pipeline/age_update.py`, wpięte w `pipeline/orchestrate.py` |
| 1.6.3 Skład z niższych pięter (korekta, za flagą) | DONE | `host.lower_storeys_weight`, domyślnie 0 |
| 1.6.4 Cechy do diagnostyki (bez wagi w R) | DONE | `pipeline/bdl_extra_features.py`, `pipeline/compartment_boundary.py` |
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

## 1.6.3 Skład z niższych pięter

`pipeline/bdl_packages.py::PackageComposition` ma nowe pole `species_lower`
(pulowany skład numerycznych udziałów ze wszystkich pięter poza `DRZEW` --
`PODSZ`/`PODR`/`PRZES`/itd., zob. `docs/BDL_slownik_pol.md`). Nowa funkcja
`pipeline.habitat.blend_host_with_lower_storeys(s_host_drzew, species_lower,
weight, profile)`: `S_host = (1-w)*S_host_drzew + w*S_host_nizsze`, gdzie
`S_host_nizsze` to średnia ważona powinowactwa znormalizowana przez sumę
udziałów (nie surowa suma ważona jak dla `DRZEW`) -- konieczne, bo
zsumowane piętra niższe mogą dać sumę != 1 (np. `PODSZ` + `PRZES` razem).
Brak pięter niższych = `S_host_nizsze = S_host_drzew` (no-op przy każdym
`w`). Config `host.lower_storeys_weight` (domyślnie `0.0`) w
`profiles/boletus_edulis.yaml`; przy `0.0` `S_host` jest bit-w-bit taki sam
jak przed 1.6.3 (zweryfikowane testem).

Wpięte w `pipeline/orchestrate.py::run_poc` zaraz po `score_host_composition`
na DRZEW; licznik `host_lower_storeys_weight` w `.attrs["diagnostics"]`
(do manifestu/raportu). Porównanie 0 / 0,25 / 0,5 na realnym przebiegu --
w sekcji 1.6.6 niżej.

Testy: `tests/test_bdl_packages.py` (parsowanie `species_lower`, wyłączenie
kodów MJS/PJD, pusta lista gdy brak pięter niższych) +
`tests/test_habitat.py` (`blend_host_with_lower_storeys`: no-op przy w=0,
no-op przy braku danych, normalizacja sumy != 1, blend przy w pośrednim,
zliczanie nieznanych gatunków) + `tests/test_orchestrate.py` (integracja
end-to-end przez `run_poc`).

## 1.6.4 Cechy do diagnostyki

Nowe moduły, oba czytane WYŁĄCZNIE przez `pipeline/prepare_trip.py`
(nigdy przez `orchestrate`/`habitat`/`scoring`/`mvp` -- ta sama strukturalna
gwarancja co `pipeline.tie_break`/`pipeline.bdl_package_details`):

- `pipeline/compartment_boundary.py::compartment_boundary_features` --
  odległość centroidu wydzielenia od granicy oddziału (`G_COMPARTMENT`) i
  długość części granicy wydzielenia leżącej na granicy oddziału. Join
  wydzielenie→oddział po prefiksie `adr_for` (pierwsze 5 segmentów rozdzielonych
  `-`), zweryfikowany bajt-w-bajt na realnej paczce Kędzierzyn (3301/3301
  wydzieleń D-STAN trafiło do jakiegoś oddziału) -- szybszy i pewniejszy niż
  join przestrzenny.
- `pipeline/bdl_extra_features.py::load_extra_features` -- pola z
  `docs/BDL_slownik_pol.md` z ≥ 50% wypełnienia: `veg_cover_cd`,
  `site_class_cd` (bonitacja gat. panującego, z wiersza `sp_rank_order_act=1`
  warstwy `DRZEW`), `density_cd` (zwarcie `DRZEW`), `soil_subtype_cd`,
  `degradation_cd` (stan siedliska), `stand_struct_cd` (budowa pionowa),
  `podszyt_species`/`podrost_species` (gatunki, bez zagęszczenia -- 0%
  wypełnienia, patrz słownik), `zabiegi_planowane` + `rok_wskazan` (z
  `f_arod_cue`, jawnie tylko planowane, bez dokładnej daty), plus granica
  oddziału z modułu wyżej. Zweryfikowane na wszystkich 9 realnych paczkach
  (56197 wydzieleń, bez błędów, ~40 s).

Cechy dopięte jako kolumny na `enriched` w `pipeline/prepare_trip.py` (po
`enrich_with_mvp_layers`, przed eksportem) i trafiają do
`diagnostics_{day}.json` (`pipeline/export.py::DIAGNOSTICS_FIELDS`); żadna
nie trafia do `scores_{day}.json` ani nie ma wagi w R.

Testy: `tests/test_compartment_boundary.py` (geometria syntetyczna: styk
granicy, wnętrze, brak dopasowanego oddziału, pusta warstwa) +
`tests/test_bdl_extra_features.py` (syntetyczna paczka: pola skalarne,
bonitacja z gatunku panującego, zwarcie, podszyt/podrost osobno, zabiegi
planowane, granica oddziału z warstwą i bez) +
`tests/test_prepare_trip.py::test_extra_features_step_does_not_change_r_or_h`
(regresja R/H, ten sam wzorzec co testy B3/tie_break) +
`tests/test_export.py` (pola w `DIAGNOSTICS_FIELDS`).

## 1.6.5 Łatwość szukania w karcie

Zaplanowane po 1.6.6 (frontend), patrz status w tabeli wyżej.

## Rulingi (decyzje bez pytania właściciela, zgodnie z zasadą 0.8)

- **1.6.4 pola pominięte:** `plant_comm_cd` (zbiorowisko roślinne),
  `tree_stock_cd` (zadrzewienie) i zagęszczenie warstw `PODSZ`/`PODR` NIE
  weszły do eksportu mimo że plan je wymienia wprost -- wszystkie ~0%
  wypełnienia w 9 sprawdzonych paczkach (`docs/BDL_slownik_pol.md`), a plan
  1.6.1 każe oznaczać pola poniżej 50% jako niezdatne. Koszt błędu: gdyby
  inne nadleśnictwo miało te pola wypełnione, funkcja i tak zwróciłaby dla
  niego `None` (brak parsowania) -- do rozszerzenia, jeśli 1.6.1 dla innego
  RDLP pokaże inny wynik.
- **1.6.4 "zabiegi z datami":** paczka nie ma dokładnej daty zabiegu, tylko
  rok całej paczki (`rok_wskazan`). Zapisane wprost jako ograniczenie
  (`docs/BDL_slownik_pol.md`), zamiast pomijać pole milczeniem lub zmyślać
  precyzję, której dane nie mają.
- **1.6.4 join z granicą oddziału po prefiksie `adr_for`, nie przestrzenny:**
  szybszy, deterministyczny, zweryfikowany na realnych danych (patrz wyżej).
  Koszt błędu: gdyby jakieś RDLP miało inny format `adr_for` (np. inną
  liczbę segmentów), join zwróciłby `(None, None)` dla tych wydzieleń
  zamiast błędnego dopasowania -- bezpieczny kierunek awarii.

- **1.6.3 normalizacja `S_host_nizsze`:** plan mówi "tym samym wzorem" co
  `S_host_drzew` (`Σ udział_i × powinowactwo_i`, bez normalizacji -- DRZEW
  nie normalizuje, bo `part_cd_act` sumuje się do 10 z definicji w obrębie
  jednej warstwy). Dla spulowanych pięter niższych ta sama suma może wyjść
  różna od 1 (kilka warstw naraz). Zdecydowałem znormalizować przez sumę
  udziałów (średnia ważona, nie suma ważona), żeby `S_host_nizsze` zostało
  porównywalnym wynikiem 0-1 jak `S_host_drzew`, zamiast np. przekroczyć 1
  przy dwóch pełnych warstwach. Przy dokładnie jednej pełnej warstwie
  (suma=1) wynik jest identyczny z niesnormalizowanym wzorem. Koszt błędu:
  przy `lower_storeys_weight=0` (domyślne) rulng nie ma żadnego wpływu na R
  -- dotyczy wyłącznie hipotetycznego trybu do oceny w Fazie 2.2.

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
