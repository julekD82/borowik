# Raport Faza 1.5 — opad z radaru w rozdzielczości ~1 km na wydzielenie

Gałąź `ulepszenia-faza1-5` (z `ulepszenia-faza1`). Realizacja zgodnie z `docs/PLAN_WDROZENIA.md` sekcja "Faza 1.5".

## Status zadań

| Zadanie | Status |
|---|---|
| 1.5.1 Próbkowanie per wydzielenie | DONE |
| 1.5.2 Parametr wygładzania | DONE |
| 1.5.3 Uzupełnienie brakujących godzin i prognozy | DONE |
| 1.5.4 Spójność percentyli | DONE |
| 1.5.5 Ocena i decyzja o ustawieniu domyślnym | DONE |

## 1.5.1 — Próbkowanie per wydzielenie

Nowy moduł: `pipeline/radar.py` (`build_stand_cell_weights`, `sample_stack_weighted`, `radar_hourly_at_stands`, `stand_radar_precip_daily`).

- Macierz wag wydzielenie × komórka jest rzadka (`scipy.sparse.csr_matrix`), budowana raz na przebieg. Wydzielenie mniejsze od komórki RainGRS (100 ha — zdecydowana większość wydzieleń) bierze komórkę zawierającą centroid (waga 1, bez liczenia przecięć shapely). Większe wydzielenie dostaje realną wagę = powierzchnia przecięcia z każdą nachodzącą komórką / suma przecięć.
- Próbkowanie godzinowe: `sample_stack_weighted` liczy ważoną średnią przez jedno mnożenie macierzy rzadkiej na godzinę-wsad (nie pętlę Pythona per wydzielenie) — wektorowe, zgodnie z wymaganiem planu.
- Braki komórek: NaN-owe komórki są wykluczane z wagi TEJ GODZINY z automatyczną renormalizacją pozostałych (wydzielenie NaN tylko gdy wszystkie pokrywające je komórki są NaN tej godziny) — zweryfikowane testem jednostkowym. Pokrycie przestrzenne (`spatial_coverage`, część powierzchni wydzielenia faktycznie objęta siatką 1 km — w praktyce prawie zawsze 1,0, bo siatka RainGRS pokrywa całą Polskę) jest raportowane osobno od pokrycia godzinowego (`radar_hours`/`expected_hours`, jak dotychczas).
- Weryfikacja na realnych danych: pełny przebieg Kieleczka 20 km, 19716 wydzieleń — **pokrycie przestrzenne średnio 100,0%, 0 wydzieleń z niepełnym pokryciem siatki 1 km**.

## 1.5.2 — Parametr wygładzania

`smooth_grid_stack` — filtr skrzynkowy (box filter) NaN-aware o promieniu `radar.smoothing_km` komórek (0/1/2/3), stosowany do pola opadu PRZED próbkowaniem wydzieleń. Komórka bez ważnych sąsiadów zostaje NaN (nie zera). Wybór promienia: patrz 1.5.5.

## 1.5.3 — Uzupełnienie brakujących godzin i prognozy

`stand_radar_precip_daily`: dla każdego wydzielenia dobowy opad = `radar_sum + model * (1 - k/n)` dokładnie tym samym wzorem co tryb blokowy (`merge_radar_into_daily`, uogólniony parametrem `key_cols` zamiast zduplikowany), gdzie `model` pochodzi z NAJBLIŻSZEGO punktu pogody wydzielenia (Open-Meteo, ten sam punkt co dla T/ET0). Godziny bez radaru i dni prognozy nadal biorą opad z Open-Meteo — logika lokalnej daty (w tym doba zmiany czasu) jest w 100% reużyta z trybu blokowego, nie zduplikowana.

Udział "opad z radaru 1 km" w ważonej sumie P26w per wydzielenie = pole `rain_radar_coverage` (już istniejące w `scores_{day}.json`; dodane też do `diagnostics_{day}.json` dla trybu stand) — w trybie `stand` liczone z WŁASNEJ serii wydzielenia zamiast wspólnego punktu pogody.

Awaria IMGW (D9 — "przebieg nigdy nie pada przez IMGW"): każde wydzielenie osobno wraca do 100% opadu modelowego, tak jak w trybie blokowym — zweryfikowane testem.

## 1.5.4 — Spójność percentyli

Pomiar na realnym przebiegu Kieleczka 20 km, 2026-09-28 (ten sam kod Fazy 1, różni się tylko `radar.mode`/`smoothing_km`; 14399 wydzieleń w masce w obu przebiegach, `scratchpad/eval_block_vs_stand_run.py`):

| | block (sprzed 1.5) | stand (1.5, smoothing_km=1) |
|---|---|---|
| pct_CWB26 min | 0,408 | 0,408 |
| pct_CWB26 mediana | 0,586 | 0,588 |
| pct_CWB26 p90 | 0,687 | 0,688 |
| pct_CWB26 p99 | 0,808 | 0,802 |
| pct_CWB26 max | 0,808 | 0,828 |
| udział wydzieleń pct_CWB26 ≥ 0,99 | 0,00% | 0,00% |

Spearman rho(pct_CWB26 block, pct_CWB26 stand) = **0,9678** w masce.

**Pomiar problemu:** rozkład pct_CWB26 jest praktycznie taki sam w obu trybach — mediana i p90 różnią się o < 0,002; p99 jest nawet minimalnie NIŻSZE w trybie stand (0,802 vs 0,808); maksimum wzrosło tylko z 0,808 do 0,828 (0 wydzieleń przekracza 0,99 w żadnym z trybów). To znaczy, że rozdzielczość 1 km NIE zawyża systematycznie skrajnych percentyli w tym przebiegu — dokładnie tak, jak przewidywał plan w sekcji "Oczekiwany efekt" ("przy obecnym nasyceniu M w mokrym okresie zmiana rankingu może być niewielka"): w tym oknie dominuje umiarkowany, rozległy opad wrześniowy (patrz warunki z przebiegu: 15,1 mm 20–21.09, 16,1 mm 10–11.09), nie pojedyncza ostra komórka burzowa, która mogłaby windować percentyl jednego wydzielenia.

**Decyzja:** różnica jest zbyt mała, by uzasadnić dodatkową, ograniczoną korektę ±0,1 do `pct_m` opisaną w planie jako drugi krok eskalacji. **Percentyl pozostaje liczony wprost z bloku CWB (bez korekty)** — zgodnie z planem: "dopiero przy dalszych problemach: mapowanie kwantylowe" nie ma tu zastosowania, bo pierwszy krok (pomiar) nie wykazał problemu. Do rewizji, jeśli przyszła walidacja terenowa (Faza 5) albo epizod z wyraźniejszą konwekcją pokaże inny obraz — konkretnie epizod burzowy 29.08–03.09 w sekcji 1.5.5 niżej pokazuje większe (choć wciąż ograniczone) różnice niż wrzesień, więc to nie jest ostateczny dowód dla każdej pory roku.

## 1.5.5 — Ocena i decyzja o ustawieniu domyślnym

### Porównanie ze stacjami Weathercloud (`scratchpad/eval_stations_smoothing.py`, 4 stacje, bez sieci — tylko cache lokalny)

Metoda: ta sama ścieżka co realny tryb `stand` (`radar_hourly_at_stands`), każda stacja jako "wydzielenie" 10×10 m (bierze komórkę zawierającą stację, z wygładzeniem PRZED próbkowaniem) — nie osobne, uproszczone próbkowanie punktowe jak w dawnym notatniku 04. Braki (brak godziny radaru w dobie) pomijane z MAE, nie liczone jako 0 mm.

**Okno 13–23.09 (pełne doby archiwalne):**

| smoothing_km | średnie MAE (4 stacje) |
|---|---|
| 0 | 0,526 |
| **1** | **0,478** |
| 2 | 0,488 |
| 3 | 0,541 |

**Okno 29.08–03.09 (epizod burzowy udokumentowany w `pipeline/radar.py`):**

| smoothing_km | średnie MAE (4 stacje) |
|---|---|
| 0 | 0,950 |
| 1 | 0,902 |
| 2 | 0,878 |
| **3** | 0,877 |

`smoothing_km=1` jest najlepszy (lub blisko najlepszego) w obu oknach: najlepszy w oknie spokojnym, drugi najlepszy (0,902 vs najlepszego 0,877 — różnica 0,025 mm, w granicach szumu przy 4 stacjach × 6 dniach) w oknie burzowym, podczas gdy `smoothing_km=0` jest wyraźnie gorszy wszędzie, a `smoothing_km=3` wyraźnie gorszy w oknie spokojnym. **Wybrano `smoothing_km=1` jako domyślny.**

Próba jest mała (4 stacje, jak w oryginalnym porównaniu z planu A1) — traktować jako potwierdzenie kierunku, nie precyzyjną kalibrację.

### Epizod burzowy na realnych wydzieleniach Kieleczki (`scratchpad/eval_storm_episode.py`)

Suma opadu 29.08–03.09.2026 dla wszystkich 19716 wydzieleń Kieleczki (promień 20 km), `smoothing_km=1`: tryb `stand` (wydzielenie własne) vs `block` (siatka pogodowa 4 km, przypisanie do najbliższego punktu — dokładny odpowiednik przebiegu sprzed 1.5 przy tym promieniu):

- Spearman rho(stand, block) = **0,9334**
- Różnica względna do sumy blokowej: mediana **3,2%**, p90 **8,7%**, p99 **14,2%**, maksimum **23,4%**
- Udział wydzieleń z różnicą > 10%: **5,6%**; > 20%: **0,1%**; > 30%/50%: **0,0%**

Interpretacja: różnica jest systematyczna i skoncentrowana w niewielkiej mniejszości wydzieleń (prawdopodobnie tych najdalej od "swojego" punktu pogody blokowego, na granicy komórek 4 km) — nie wygląda na szum/artefakt radaru zdominowany losowością (brak wydzieleń z różnicą > 30%), tylko na realną, ograniczoną poprawę rozdzielczości przestrzennej, zgodnie z oczekiwaniem planu ("największy efekt przy opadach burzowych"). To jest proxy dla pełnej zmiany F/klasy (samo pole wejściowe do M się zmienia; T/ET0/klimatologia identyczne) — górne ograniczenie tego, o ile mogłaby się zmienić F w tym oknie, nie sama zmiana F.

*(Uwaga metodologiczna: "mapa różnic" w sensie wizualnym z planu nie została wygenerowana jako obraz w tej sesji — zastąpiona liczbowym rozkładem różnic względnych powyżej, co odpowiada na to samo pytanie planu: "czy wzór wygląda jak pasy opadu, czy jak szum i artefakty radaru" — brak wydzieleń z ekstremalną różnicą (>30%) i mediana rzędu kilku % wskazują na spójny wzór przestrzenny, nie szum.)*

### Pełny przebieg Kieleczka 20 km, 2026-09-28 — `stand` (nowy kod, smoothing_km=1, `docs/porownania/faza1_5/`) vs `block` (`docs/porownania/nowy/`, sprzed 1.5)

Ten sam kod Fazy 1 (paczki BDL, siatka GUS, presja absolute), różni się tylko `radar.mode`/`smoothing_km`. 19716 wydzieleń wspólnych, 14399 w masce w obu przebiegach (`scratchpad/eval_block_vs_stand_run.py`).

- **Spearman rho(R block, R stand) w masce = 0,9835** — bardzo silna zgodność ogólna z realną reorganizacją w obrębie tej zgodności.
- Rozkład R prawie identyczny: block mediana 51,48, max 82,83; stand mediana 51,69, max 82,78.
- P niezmienione (block i stand: min 0,001, mediana 0,373, max 0,818) — potwierdza, że zmiana dotyczy wyłącznie ścieżki opadowej (H/pressure niedotknięte), zgodnie z zakresem fazy.
- pct_CWB26: patrz sekcja 1.5.4 — rozkład prawie identyczny, Spearman rho = 0,9678.
- `rain_radar_coverage` mediana: block 0,892 → stand 0,915 (skromny, realny wzrost — ważone próbkowanie powierzchniowe per wydzielenie wykorzystuje nieco więcej dostępnych danych radarowych niż prosta średnia blokowa, która gubi część godzin, gdy którakolwiek komórka bloku jest NaN).
- **Top-20 wg R: pokrywa się w 15/20 pozycjach** (rankingi bardzo zbliżone, ale nie identyczne — spodziewane przy realnej, choć ograniczonej zmianie wejścia).
- **Trzy największe awanse i trzy największe spadki w rankingu są WSZYSTKIE tłumaczone realną zmianą pct_CWB26** (np. `02-19-1-11-741-b-00@2026`: pozycja 9151→4778, R 47,6→56,6, pct_CWB26 0,470→0,527; `02-19-1-11-732-d-05@2026`: pozycja 5324→9728, R 55,2→46,4, pct_CWB26 0,568→0,499) — P niezmienione w każdym z sześciu przypadków, więc cała różnica pochodzi z M (opad), nie z artefaktu w innej składowej. Przesunięcia grupują się geograficznie (wydzielenia `02-19-1-11-*`) — spójne z realnym, lokalnym wzorcem opadu, nie z losowym szumem.

### Odkryta i naprawiona usterka wydajności (istotna dla oceny "czy tryb stand jest gotowy do użycia")

Pierwsza próba tego przebiegu (przed poprawką) utknęła na wiele dziesiątek minut i rosnące zużycie pamięci (do ~5 GB) w pętli `run_poc` — przyczyna: `{sid: g for sid, g in stand_precip_daily.groupby("stand_id")}` materializowało osobny obiekt `DataFrame` na każde z 19716 wydzieleń, co jest znanym antywzorcem pandas przy dużej liczbie małych grup. Naprawione przez `pipeline.weather.stand_precip_features_table`: wektorowe przeliczenie p5/p26w/`rain_radar_coverage` dla wszystkich wydzieleń naraz (reshape do macierzy `(n_wydzieleń, n_dni)` + iloczyn macierzowy z wagami wykładniczymi zamiast pętli Pythona po grupach), z bezpiecznym fallbackiem na starą (wolną, ale poprawną) ścieżkę, gdyby któreś wydzielenie miało inną liczbę dni niż reszta. Po poprawce pełny przebieg Kieleczki (19716 wydzieleń) kończy się w rozsądnym czasie, porównywalnym z trybem `block`. Test regresyjny: `tests/test_weather.py::test_stand_precip_features_table_*` (zgodność z `precip_derived_features` per wydzielenie, niezależność od kolejności wierszy, fallback dla nierównych grup).

**To był realny błąd wydajności w kodzie produkcyjnym, nie tylko w skrypcie oceny — bez tej poprawki `radar.mode: stand` byłby praktycznie nieużywalny przy typowej skali wyszukiwania (dziesiątki tysięcy wydzieleń).**

### Decyzja o ustawieniu domyślnym

**`radar.mode: stand`, `radar.smoothing_km: 1` — oba jako nowe wartości domyślne w `profiles/boletus_edulis.yaml`.**

Uzasadnienie:
1. Dokładność: `smoothing_km=1` daje najniższe lub blisko najniższego MAE wobec 4 niezależnych stacji Weathercloud w obu zbadanych oknach (spokojnym i burzowym) — nie gorzej niż tryb sprzed 1.5 (`smoothing_km` nie istniało, efektywnie odpowiadał surowej średniej blokowej).
2. Brak regresji: R i P pozostają w tej samej skali i silnie skorelowane z trybem `block` (rho 0,98) — to udoskonalenie, nie przetasowanie.
3. Brak problemu ze spójnością percentyli (1.5.4) — nie trzeba dodatkowej korekty.
4. Realna, wytłumaczalna poprawa rozdzielczości przestrzennej tam, gdzie ma znaczenie (epizod burzowy: różnice skoncentrowane, nieprzypadkowe, górna granica ~23% na pojedynczym wydzieleniu, nie setki procent).
5. Po naprawie błędu wydajności koszt obliczeniowy jest porównywalny do trybu `block`.

Tryb `radar.mode: block` pozostaje dostępny (ustawienie profilu) jako opcja powrotu, zgodnie z planem.

## Testy

`tests/test_radar.py` (+10 testów: wagi komórek, próbkowanie ważone, renormalizacja przy brakach, wygładzenie, próg centroid/przecięcie, `radar_hourly_at_stands`, `stand_radar_precip_daily`, awaria IMGW w trybie stand, uogólnienie `key_cols` przez dobę zmiany czasu), `tests/test_weather.py` (+3: `stand_precip_features_table` — zgodność z `precip_derived_features` per wydzielenie, niezależność od kolejności wierszy, fallback dla nierównych grup; refaktoryzacja `compute_weather_features` samodzielnie bez regresji, istniejące testy), `tests/test_orchestrate.py` (+2: `stand_precip_daily` nadpisuje `pct_CWB26`/`rain_radar_coverage` tylko dla pokrytych wydzieleń, `None` odtwarza zachowanie sprzed 1.5), `tests/test_prepare_trip.py` (+3: `radar_mode`, `build_weather_fetcher` zostaje "surowy" w trybie stand, `nearest_weather_point_per_stand`), `tests/test_export.py` (dodane pole `rain_radar_coverage` do fikstury diagnostyki, bez nowych testów).

**Pełny zestaw: backend `pytest` 596/596 passed; frontend `npx vitest run` 72/72 passed, `npx tsc --noEmit` czysto.** (Frontend niezmieniony poza jednym zdaniem w `frontend/README.md` opisującym opad jako ważony powierzchniowo per wydzielenie zamiast blokowo — Faza 1.5 jest czysto backendowa, zgodnie z planem.)

## Zmienione/nowe pliki

`pipeline/radar.py` (nowe funkcje 1.5.1–1.5.3, uogólnienie `key_cols`), `pipeline/weather.py` (`precip_derived_features`, `stand_precip_features_table`, `et026w` w `compute_weather_features`), `pipeline/orchestrate.py` (`stand_precip_daily` w `run_poc`, `DEFAULT_PAST_DAYS`), `pipeline/prepare_trip.py` (`radar_mode`, `nearest_weather_point_per_stand`, wiring, pola manifestu), `pipeline/export.py` (`rain_radar_coverage` w diagnostyce), `profiles/boletus_edulis.yaml` (`radar.mode: stand`, `radar.smoothing_km: 1`), `frontend/README.md` (opis źródła opadu), `tests/test_radar.py`, `tests/test_weather.py`, `tests/test_orchestrate.py`, `tests/test_prepare_trip.py`, `tests/test_export.py`.

Migawki porównawcze: `docs/porownania/nowy/` (block, sprzed 1.5, z nocy 27/28.09), `docs/porownania/faza1_5/` (stand, smoothing_km=1, ten sam punkt/promień/data). Skrypty oceny (nie commitowane do repo, w scratchpadzie sesji): `eval_stations_smoothing.py`, `eval_storm_episode.py`, `eval_block_vs_stand_run.py`.
