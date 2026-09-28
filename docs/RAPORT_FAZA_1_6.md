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
| 1.6.5 Łatwość szukania w karcie | DONE | `pipeline/searchability.py` + frontend `searchability_hint` |
| 1.6.6 Przebieg i raport | DONE | migawka „Kieleczka — faza 1.6”, `docs/porownania/faza1_6/` |

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

Nowa czysta funkcja `pipeline/searchability.py::searchability_hint(density_cd,
podszyt_species, podrost_species)` -- ponieważ zagęszczenie (`density_cd`)
warstw `PODSZ`/`PODR` jest 0% wypełnione (1.6.1), "gęstość" podszytu/podrostu
w praktyce oznacza tu ich OBECNOŚĆ (lista gatunków niepusta), nie policzoną
gęstość; zwarcie koron (`DRZEW`) jest jedyną naprawdę liczbową wartością
dostępną i używaną jako uzupełniający sygnał, gdy nie ma podszytu/podrostu.
Priorytety: podszyt+podrost > sam podszyt > sam podrost > gęste/luźne
zwarcie korony > brak sygnału (`None`, karta nic nie pokazuje).

Wpięte w `pipeline/export.py::build_details_record` (nowe pole
`searchability_hint` w `details_{day}.json`) -- czytane z istniejącego
`PackageStandDetails.podszyt_species`/`density_cd` (te same dane co karta od
2.1 B3) plus `podrost_species` z nowego `pipeline.bdl_extra_features`
(1.6.4). Nigdy nie wpływa na R ani sortowanie (obliczane już po scoringu,
tylko dla karty).

Frontend: `StandDetail.searchability_hint?: string | null` w
`frontend/src/model.ts` (opcjonalne pole, ten sam wzorzec co `veg_cover`/
`standdensity_index` -- starszy eksport bez tego pola nadal się wczytuje).
Renderowane w `packageSection()` (`frontend/src/main.ts`) jako wyróżniony
akapit na górze sekcji "Drzewostan i otoczenie". Karta rejonu używa tego
samego widoku szczegółów dla swojego wydzielenia-reprezentanta
(`view.top`, `enterRegionDetail` w `main.ts`), więc wskazówka pojawia się
automatycznie też przy przeglądaniu rejonu -- bez osobnej logiki po stronie
backendu dla poziomu rejonu.

Testy: `tests/test_searchability.py` (priorytety sygnałów, progi zwarcia,
brak sygnału, niesparsowalna wartość) + `tests/test_export.py`
(`searchability_hint` w `build_details_record`, w tym z `podrost_species`
z `extra_features_index`) + `frontend/src/model.test.ts` (walidacja pola
opcjonalnego, round-trip, odrzucenie złego typu). Backend: `pytest` 639/639.
Frontend: `npm run build` (tsc + vite) czysto, `npm run test` 75/75.

## 1.6.6 Przebieg końcowy i raport porównawczy

Przebieg Kieleczki (50,527 N, 18,605 E, promień 20 km, 2026-09-28 -- te same
parametry co 0.3/1.9/Faza 1.5), z ustawieniami domyślnymi po Fazie 1.6
(`age.update_to_analysis_year: true`, `host.lower_storeys_weight: 0.0`),
paczki BDL z `BDL/`, siatka GUS z cache. Cały przebieg z lokalnego cache
(pogoda, klimatologia, radar, GDOŚ, OSM, BDL) -- brak nowego zużycia budżetu
Open-Meteo poza kilkoma bieżącymi godzinami radaru. Migawka **„Kieleczka —
faza 1.6"** (`frontend/public/data/trips/kieleczka-faza-1-6-2026-09-28/`,
wpis w `index.json`); eksporty w `docs/porownania/faza1_6/`.

Wynik przebiegu: 19716 wydzieleń, 14399 w masce (identycznie jak w
poprzednich przebiegach Kieleczki 20 km -- Faza 1/1.5), 14631 ze składem z
paczki BDL (74,2%), 5085 z WFS, 5 rejonów, `age_update_missing_year_count=0`,
`host_lower_storeys_weight=0.0`.

### Wpływ 1.6.2 (korekta wieku) na ten przebieg

**Zero wydzieleń zmieniło przedział wieku lub przeszło przez próg maski.**
Ustalone bezpośrednio z danych: `a_year` (rok stanu z WFS) = **2026 dla
wszystkich 19716 wydzieleń** -- identyczny z rokiem analizy (2026-09-28), więc
`wiek_obecny = wiek_z_opisu + (2026 − 2026) = wiek_z_opisu` dla każdego
wydzielenia. Korekta jest tu matematycznym no-opem nie z powodu błędu w
kodzie (poprawność mechanizmu jest sprawdzona jednostkowo w
`tests/test_orchestrate.py` na syntetycznym wydzieleniu z `a_year=2020`,
gdzie realnie przechodzi próg maski), a dlatego że WFS w tym momencie jest
aktualny względem roku analizy. Efekt 1.6.2 będzie widoczny dopiero gdy
`a_year` z WFS/paczki zostanie w tyle za rokiem analizy (np. paczka
nieodświeżona po zmianie roku kalendarzowego, lub analiza z datą przyszłą
przekraczającą granicę roku) -- **to jest uczciwy wynik tego konkretnego
przebiegu, nie dowód, że funkcja nie działa.**

### Porównanie rankingu dla `host.lower_storeys_weight` (0 / 0,25 / 0,5)

Przeliczone na tym samym przebiegu (te samo `S_host_drzew`/`H`/`F_loc`/`P`
z cache, wyłącznie `S_host` przeliczone realną funkcją
`blend_host_with_lower_storeys`, bez ponownego pobierania pogody) -- 14399
wydzieleń w masce prawnej, z czego **3812/45565 (8,4%) wydzieleń z paczką ma
jakąkolwiek warstwę niższą** (PODSZ/PODR/PRZES/...) do wykorzystania:

| waga | Spearman ρ (vs waga 0) | pokrycie top-20 | wydzieleń ze zmianą R (2 miejsca po przecinku) |
|---|---|---|---|
| 0,0 (domyślna) | 1,0000 | 20/20 | 0 / 14399 |
| 0,25 | 0,9995 | 18/20 | 665 / 14399 (4,6%) |
| 0,5 | 0,9978 | 18/20 | 665 / 14399 (4,6%) |

Ranking jest bardzo stabilny nawet przy w=0,5 (ρ > 0,997, 18/20 tych samych
wydzieleń w top-20) -- zmiana dotyka tylko wydzieleń z realnie obecną
warstwą niższą (8,4% wszystkich wydzieleń z paczką), a S_host_drzew (główny
składnik) jest niezmienione. Nie ma tu podstawy do zmiany domyślnej wagi z
0 -- pozostaje hipotezą do oceny dopiero po danych terenowych (Faza 2.2/5),
zgodnie z planem.

### Rozkład cech 1.6.4 w top-5% R vs cała maska (opisowo, bez wniosków o skuteczności)

Top-5% R (próg R ≥ 71,32) = 720 z 14399 wydzieleń w masce.

| Cecha | Cała maska | Top-5% R |
|---|---|---|
| Bonitacja gat. panującego: I / IA / II / III | 39,4% / 37,4% / 18,6% / 4,4% | 34,2% / 41,4% / 20,4% / 4,1% |
| Stan siedliska (degradation_cd): N1 | 45,0% | **93,8%** |
| Stan siedliska: Z1 | 32,8% | 5,1% |
| Pokrywa runa: ZAD / MSZC / SZAD | 46,9% / 13,6% / 29,3% | 49,4% / 26,2% / 21,8% |
| Obecny podszyt | 81,3% | 90,0% |
| Obecny podrost | 3,9% | 5,0% |
| Ma zaplanowane zabiegi (f_arod_cue) | 77,9% | 93,5% |
| Odległość do granicy oddziału, mediana | 73,5 m | 83,2 m |

Najbardziej zauważalna różnica -- `degradation_cd=N1` (hipotetycznie
"naturalne", patrz `docs/BDL_slownik_pol.md`) w top-5% R prawie dwukrotnie
częściej niż w całej masce. **To korelacja, nie dowód związku**: `H`/`R` nie
używa `degradation_cd` w żadnym wzorze -- N1 najpewniej współwystępuje z
innymi czynnikami, które realnie sterują R (np. typ siedliska/wilgotność,
które wpływają na S_site i M), a nie oddziałuje samodzielnie. Do sprawdzenia
metodą z Fazy 2.2 (test przestrzenny AUC z tłem GBIF), nie do wnioskowania
stąd.

**Metodologia:** `scratchpad` skrypty jednorazowe (poza repo) łączące
`diagnostics_2026-09-28.parquet` + `scores_2026-09-28.json` z tego przebiegu
i `pipeline.bdl_packages.load_packages(BDL)`; porównanie wag 1.6.3 używa
bezpośrednio produkcyjnych funkcji `blend_host_with_lower_storeys` i
`compute_ranking`, nie osobnego przeliczenia wzoru.

## Rulingi (decyzje bez pytania właściciela, zgodnie z zasadą 0.8)

- **1.6.6 przeliczenie wagi 1.6.3 bez ponownego przebiegu pogody:** ranking
  dla `host.lower_storeys_weight` 0,25/0,5 przeliczony z już wyeksportowanych
  `S_host`/`H`/`F_loc`/`P` (waga wpływa wyłącznie na `S_host`, więc `H_nowe =
  H_stare × (S_host_nowe/S_host_stare)^0,40`, potem `R` przez prawdziwe
  `compute_ranking`) -- zamiast trzech pełnych przebiegów `prepare_trip`.
  Szybsze, zero dodatkowego zużycia API, i matematycznie identyczne z pełnym
  przebiegiem dla wydzieleń w masce prawnej (H/F_loc/P nie zależą od wagi
  1.6.3). Koszt błędu: żaden dla tego wyniku -- gdyby kod `run_poc`
  liczył coś inaczej niż ten wzór, ujawniłoby to jedno z testów integracyjnych
  w `tests/test_orchestrate.py` (`test_run_poc_nonzero_weight_blends_lower_storey_composition`),
  które faktycznie przechodzą przez `run_poc`, nie przez ten wzór.
- **1.6.6 migawka i eksporty w git:** `frontend/public/data/*` jest objęte
  `frontend/.gitignore` (nigdy nie trafia do repo, potwierdzone
  `git check-ignore`) -- migawka „Kieleczka — faza 1.6” istnieje tylko
  lokalnie, jak wszystkie pozostałe migawki w `trips/`. `docs/porownania/faza1_6/`
  NIE jest ignorowane i zgodnie z precedensem z Fazy 1/1.5
  (`docs/porownania/baseline/`, `docs/porownania/faza1_5/` są w repo) --
  dodane do commitu.
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
