# Notatki przekazania dla Claude Code

## 2026-09-29 — aktualne (33): Faza UI zrealizowana; gałąź `ulepszenia-ui`

Raport, lista kontrolna „stare pole → nowe miejsce” i zrzuty (przed/po, komputer i telefon): `docs/RAPORT_UI.md`, `docs/ui-zrzuty/`. **Model, F, R, H, α, progi bez zmian** (na prawdziwych danych Kieleczki: |Δ| H/F/F_loc/P/R = 0, `regions.json` identyczny). Nowe w eksporcie: `R_bez_presji` w `scores`, `regions_bez_presji_{day}.json` (ta sama procedura `group_into_regions` na `R_bez_presji`), w `details`: `habitat` (S_host/S_site/S_age/age_mode), `forest_district`, `access.pressure_contrib`; w `regions*.json`: `near_place`; w manifeście: `pressure_alpha`, `counts.region_count_bez_presji`. Frontend: przełącznik presji (`rankEntries`, `regionsNoPressure`), trzy paski, wiersze listy, zwinięte „Szczegóły”, zakładki Lista/Mapa na telefonie (`main.ts`, `model.ts`, `style.css`, testy `ui.test.ts`, `tests/test_ui_presja.py`). Testy: backend 794, frontend 123 + tsc + build. **Otwarte:** `details.json` urósł do ok. 44 MB; widok telefonu sprawdzony tylko w iframe 390 px na komputerze; nazwy nadleśnictw z polskimi znakami tylko dla RDLP Katowice; „koło X” zastąpione „X” (brak odmiany). `frontend/public/data` zawiera nowy eksport Kieleczki (kopia poprzedniego w `output/backup_public_data_przed_ui/`); starsze migawki nie mają nowych pól (przełącznik nieaktywny).

## 2026-09-29 — aktualne (32): Faza 4 (pogoda) zrealizowana; gałąź `ulepszenia-faza4`

Raport i decyzje wg reguł planu: `docs/RAPORT_FAZA_4.md`, surowe liczby `docs/porownania/faza4/`, skrypty `scripts/faza4_*.py`. **F, R, progi klas, α, wagi H bez zmian** (test przypięty `tests/test_faza4_r_niezmienione.py`). Nowe: profil `weather.temp_grid_km` (opcja, domyślnie `null` = jak dotąd; reguła 4.1 nie spełniona: p95 |ΔF| 0,11), `conditions.aggregation` (domyślnie `median_f_stands`, reguła 4.4 spełniona; `median_of_features` = stara metoda), `ui.forecast_uncertain_from_day`/`forecast_indicative_from_day` (4/8, dni naprzód), `conditions.heavy_rain_day_mm`. Nowe kolumny run_poc (tylko prezentacja): `p26_mm`, `cwb26_mm`, `cwb26_typical_mm`, `tmean20_c`, `tmean5_c`, `p5_mm`, `tmin3_c`, `tmin3_date`, `forecast_window_share`; `details_{day}.json` ma blok `weather`, `conditions_{day}.json` ma `components`, `uncertainty`, `frost_area_share`, `heavy_rain_area_share`, `F_by_aggregation` na każdy dzień. Mapowanie kwantylowe radar→ERA5 NIE wdrożone (4.2: mediana |Δpct| 0,095 ≤ 0,10, tuż pod progiem). **Otwarte:** panel 7 dni w trybie `radar.mode: stand` liczy z opadu modelu bez radaru → F panelu (0,45) ≠ mediana F wydzieleń (0,65); zob. raport 4.4.

## 2026-09-29 — aktualne (31): `habitat.age_mode: neutral` jest domyślny

Decyzja właściciela po walidacji Fazy 2 (szczegóły i uzasadnienie: `docs/RAPORT_FAZA_2.md`, sekcja „Decyzje po walidacji”), gałąź `ulepszenia-wiek`. S_age = 1 dla wydzieleń spełniających maskę wieku (maska < 12 lat bez zmian, brak kary > 120 lat); tryb `curve` dostępny przez `habitat.age_mode: curve` w profilu. Świadomie bez krzywej faworyzującej 20–60 lat (dopasowanie do analizy eksploracyjnej). Nowe przebiegi dają inne R/H niż eksporty sprzed zmiany (Kieleczka: Spearman R 0,95 względem `curve`) — porównując z migawkami sprzed 29.09, pamiętać o tym.

## 2026-09-29 — aktualne (30): Faza 2 zrealizowana (2.0–2.6); wyniki 2.4 i 2.5

Reguły `docs/WALIDACJA_REGULY.md` zatwierdzone przez właściciela (v2). **2.4: „zgodne z modelem”** (AUC(H) 0,571 vs inne grzyby, 0,611 vs rośliny/zwierzęta VII–XI; 210 rekordów od 90 obserwatorów; efekt mały). **2.5: „brak rozróżnienia”** (średnia ranga F bez G_season 0,529 / 0,527, CI obejmuje ok. 0,5; bez dodatkowej czerwonej flagi; 482 rekordy, E-OBS). 2.6: `pipeline/eobs.py`, `cache/eobs/` (12 plików). Nowe: `scripts/zapisz_prognoze.py` (harmonogram Windows do zainstalowania ręcznie, `docs/ZAPIS_WYJSC.md`), `pipeline/{eobs,eobs_fruiting,spatial_check,validation_stats,gbif_client}.py`, notatniki 10–13. 2.7/2.8 nie ruszane. Raport: `docs/RAPORT_FAZA_2.md`. `netCDF4` w `pyproject.toml`, `uv.lock` do przeliczenia (`uv lock`). Analiza eksploracyjna (`notebooks/14_eksploracja_h.py`): sygnał H głównie z S_host i S_site, S_age ≈ 0,5, sam wiek AUC 0,40–0,42 (znaleziska w młodszych wydzieleniach); kody nieznane w 2.4 to głównie siedliska „G” (LGSW, LMGSW, BMGSW), w Kieleczce 0 nieznanych. Eksploracyjnie także wiek (`notebooks/15_eksploracja_wiek.py`): pozytywy młodsze (mediana 69 vs 82/78 lat); nowy przełącznik `habitat.age_mode` (`curve` domyślny / `neutral`: S_age = 1 po masce), AUC(H) prawie bez zmian (0,574/0,615), na Kieleczce Spearman R 0,952 i 10/20 wspólnych w top-20 — domyślny tryb NIE zmieniony. Żadna zmiana wag H/F/α nie wynika automatycznie z tych wyników.

## 2026-09-28 — (29): Faza 2 (część autonomiczna: 2.1, 2.2, 2.3, projekt 2.0)

Gałąź `ulepszenia-faza2` (z `master` po scaleniu 1.6). Raport: `docs/RAPORT_FAZA_2.md`. Zrobione: **2.2** archiwum prognoz (`pipeline/forecast_archive.py`, hak w `fetch_weather_raw`, `cache/archiwum_prognoz/`, tylko-dopisujące); **2.1** walidator zapisów wyjść (`pipeline/field_data.py`, `scripts/sprawdz_dane_terenowe.py`, `docs/ZAPIS_WYJSC.md`, szablony `dane_terenowe_szablony/`, `/dane_terenowe/` w `.gitignore`, przypomnienie w launcherze); **2.3** inwentaryzacja GBIF (`notebooks/10_…`, `11_…`): 1167 rekordów B. edulis w PL, 360 z niepewnością ≤ 100 m, z tego 274 w lesie D-STAN od 110 obserwatorów; region Katowice ma tylko 52 rekordy ≤ 100 m. **2.0** (`docs/WALIDACJA_REGULY.md`) to projekt czekający na zatwierdzenie właściciela — **do tego czasu nie uruchamiać 2.4 ani 2.5**. Nie zrobione: 2.4–2.8, opcjonalny `scripts/zapisz_prognoze.py`. Testy: backend 646 (przed dopisaniem `test_forecast_archive`/`test_field_data` było 639); frontend nietknięty.

## 2026-09-28 — (28): Faza 1.5 — opad z radaru per wydzielenie (~1 km, ważony powierzchniowo)

Zrealizowany `docs/PLAN_WDROZENIA.md` sekcja "Faza 1.5", pełny raport w `docs/RAPORT_FAZA_1_5.md`, gałąź `ulepszenia-faza1-5` (z `ulepszenia-faza1`).

**Co się zmieniło:** opad (tylko opad — temperatura/ET0/klimatologia zostają na siatce pogodowej) jest teraz domyślnie liczony osobno dla każdego wydzielenia z siatki RainGRS ~1 km, ważony powierzchniowo przecięciem wielokąta wydzielenia z komórkami radaru (macierz rzadka, `pipeline.radar.build_stand_cell_weights`/`sample_stack_weighted`), zamiast jednej wspólnej średniej blokowej dla wielu wydzieleń na tym samym punkcie pogody. Nowy profil: `radar.mode: stand` (domyślnie, `block` = stare zachowanie nadal dostępne) i `radar.smoothing_km: 1` (filtr skrzynkowy NaN-aware przed próbkowaniem, wybrany empirycznie — patrz raport).

**Realna usterka wydajności znaleziona i naprawiona w trakcie oceny:** pierwsza wersja per-wydzieleniowej agregacji (`{sid: g for sid, g in df.groupby("stand_id")}`) materializowała osobny obiekt DataFrame na każde z 19716 wydzieleń Kieleczki — znany antywzorzec pandas, w praktyce ~5 GB pamięci i dziesiątki minut bez końca widocznego postępu. Naprawione wektorowo (`pipeline.weather.stand_precip_features_table` — reshape do macierzy i iloczyn macierzowy zamiast pętli po grupach); bez tej poprawki `radar.mode: stand` byłby praktycznie nieużywalny w realnej skali wyszukiwania.

**Walidacja na realnych danych (bez API — tylko cache lokalny):** porównanie ze stacjami Weathercloud dla `smoothing_km` 0–3 (wybrano 1); porównanie block vs stand na epizodzie burzowym 29.08–03.09 na wszystkich 19716 wydzieleniach Kieleczki (Spearman rho 0,933, różnice skoncentrowane i ograniczone, nie szum); pełny przebieg Kieleczka 20 km 2026-09-28 (`docs/porownania/faza1_5/` vs `docs/porownania/nowy/`): Spearman rho(R) = 0,9835, top-20 pokrywa się w 15/20, wszystkie największe awanse/spadki w rankingu tłumaczone realną zmianą pct_CWB26 (P niezmienione). Spójność percentyli (1.5.4) zmierzona i uznana za niewymagającą korekty — rozkład pct_CWB26 prawie identyczny w obu trybach.

**Testy:** backend `pytest` 596/596, frontend `npx vitest run` 72/72 + `tsc --noEmit` czysto.

**Otwarte:** ocena oparta na jednym przebiegu (Kieleczka, wrzesień, opad umiarkowany) i 4 stacjach Weathercloud — mała próba. Warto powtórzyć przy realnej okazji z wyraźniejszą konwekcją letnią i/lub innym promieniem wyszukiwania, zanim `smoothing_km`/`mode` zostaną uznane za w pełni skalibrowane (patrz też Faza 5 w planie — kalibracja dopiero po danych terenowych).

## 2026-09-27 — (27): A2 — model fazy wysypu NIE przeszedł bramki GBIF; wdrożono Plan-B (F na 7 dni + fakty o deszczu)

Zrealizowany plan `docs/superpowers/plans/2026-09-27-borowik-wysyp-a2.md`, wykonanie inline (Native, `superpowers:executing-plans`) w izolowanym worktree `.claude/worktrees/borowik-a2-flush` na gałęzi `worktree-borowik-a2-flush`.

**Model wypróbowany (Task 1-2, `pipeline/flush.py`, skończony i przetestowany, ale NIE wdrożony do produkcji):** deszcz >= `pulse_min_mm` (1 dzień przerwy dozwolony) uruchamia zegar termiczny (stopniodni od `t_base_c`, wolniej w zimne noce, mróz kończy falę) → krzywa Gaussa w stopniodniach (`dd_peak`/`dd_sigma`) → faza (przed_fala/poczatek/szczyt/starzeje_sie/po_fali) i okno szczytu.

**Bramka E3 (Task 3, `notebooks/06_backtest_flush.py`, 144 kombinacji siatki x 90 znalezisk GBIF, walidacja krzyżowa leave-one-year-out, bez sieci):** średnia trzymanego-poza-próbą rankingu = 0,548, WORSZE niż baza `rank_F_loc_no_gseason` = 0,626 (Wilcoxon p=0,041, istotne w ZŁYM kierunku). Nawet najlepsza kombinacja na całości danych (0,599) nie przebiła bazy. **BRAMKA NIEZALICZONA** — zgodnie z planem: stop i pytanie do użytkownika.

**Dwie diagnostyki (na żądanie użytkownika, `notebooks/08_flush_pulse_timing_diagnostic.py`, `notebooks/09_flush_pulse_timing_season_controlled.py`, bez kodu produkcyjnego) wyjaśniły dlaczego:** dni/stopniodni od ostatniego pulsu deszczu POZORNIE odróżniały 90 realnych znalezisk od losowych dni kandydackich (test KS p=0,006–0,0008) — ale tylko gdy kandydatów pulowano z całego sezonu (1.06–31.10). Po ograniczeniu kandydatów do ±15 dni wokół dnia-roku KAŻDEGO znaleziska (ten sam punkt/rok) efekt znika (KS p=0,12–0,84). Pozorny sygnał to konfundowanie sezonem (znaleziska są przesunięte w stronę chłodniejszej/późniejszej części sezonu, gdzie stopniodni akumulują się wolniej dla tego samego czasu), nie realny efekt "bliżej pulsu = lepiej" w obrębie tego samego sezonu.

**Decyzja użytkownika (Plan-B):** `pipeline/flush.py` (Tasks 1-2) i notatniki 06/08/09 zostają w repo jako zamrożony, udokumentowany eksperyment — nigdy nie importowane przez `prepare_trip`/frontend (jak dotąd nigdy nie importowane przez `orchestrate`/`scoring`/`mvp`/`habitat`). Sekcja `flush:` w profilu zachowuje oryginalne wartości `[E]` (bramka nigdy nie przeszła) z komentarzem o niepowodzeniu.

**Co wdrożono zamiast tego — nowy moduł `pipeline/conditions_timeline.py` (Task 4-7):** reużywa WYŁĄCZNIE detekcję pulsów deszczu z `pipeline.flush` (`detect_pulses`/`area_daily_weather`/`fmt_day_range` — nigdy zegara termicznego/modelu Gaussa) dla zdania z samymi faktami o ostatnich (do 2) większych deszczach (daty, realne mm, ile dni temu — bez przewidywania szczytu), plus REALNE F — te same składowe (M/T/K_frost/G_season, `pipeline.scoring`/`pipeline.weather`/`pipeline.phenology`, bez nowej kalibracji) co dają 0,626 w backteście GBIF, ale liczone tu z MEDIANY OBSZARU siatki pogodowej (mediana surowych cech, ranking wobec połączonej klimatologii wielu punktów) zamiast per punkt/wydzielenie jak w backteście (ranking per punkt wobec jego własnej komórki klimatologii) — to inna, osobno nie zwalidowana agregacja, nie dosłownie "ta sama, zwalidowana liczba" — liczone osobno dla każdego z 7 dni horyzontu (dziś..dziś+6), zamiast raz na całe wyszukiwanie. Poziom kafelka (0-3) to indeks klasy `fruiting_classes` (nowa `pipeline.scoring.classify_fruiting_level`), nie osobna tabela progów. Nowa sekcja profilu `conditions:` (osobna od zamrożonej `flush:`) niesie progi raportowania. Artefakt `flush_{day}.json`/`flush.json` → `conditions_{day}.json`/`conditions.json` (eksport, sync, archiwum, frontend) — "flush"/"wysyp" sugerowało obalone przewidywanie szczytu.

**Sprawdzenia na realnych danych przed wdrożeniem (ad hoc, nie commitowane):** (a) realne F na 7 dni (Będziemyśl 20 km, radar, na żywo) zmienia się o DWIE granice klas (0,803 "Bardzo dobre" dziś → 0,324 "Umiarkowane" +6d) — wystarczająco, wg własnego kryterium użytkownika ("mniej niż jedna klasa różnicy = bez kafelków"), by uzasadnić kafelki dzienne. (b) realne dwa ostatnie puls y deszczu (radar, mediana obszaru, bez mnożnika 0,848 — ten dotyczy tylko progu wykrywania, nie raportowanego mm): 21–22.09 28,5mm (5 dni temu), 11–12.09 20,3mm (15 dni temu).

**Realny bieg (Task 8, `--lat 50.0555 --lon 21.7889 --radius-km 20`, wszystko z cache):** `Warunki: Ostatni większy deszcz: 21–22.09 (27.9 mm), 5 dni temu · wcześniejszy deszcz: 11–12.09 (19.7 mm), 15 dni temu`. F na 7 dni: 0,787→0,736→0,647→0,538→0,429→0,354→0,297; poziomy 3,3,2,2,1,1,1. Wizualnie potwierdzone w przeglądarce (Chrome, viewport pełnej szerokości) — zdanie tylko-faktyczne, 7 kafelków z etykietami dni tygodnia i kropkami zgodnymi z JSON. Zmiana szerokości okna na ~375px nie odzwierciedliła się w zrzucie ekranu narzędzia przeglądarki (znane ograniczenie narzędzia, nie strony) — CSS kafelków używa `flex-wrap`, więc reflow jest strukturalnie zagwarantowany; poleganie na tym + czystym `vite build`/`tsc`.

**Testy:** `pytest` 490 passed (było 448 przed A2: +8 Task1, +16 Task2 (`test_flush.py`, eksperyment), +15 Task4 (6 `test_scoring.py` + 9 `test_conditions_timeline.py`), +2 Task5 (`test_export.py`/`test_prepare_trip.py`), +1 Task6 (`test_trip_archive.py`)); frontend `npm test` 65 passed (51 `model.test.ts` + 14 `sync-data.test.mjs`, +4/+3 z Task7/Task6), `npx tsc --noEmit` czysto, `npx vite build` czysto.

**Otwarte:** (a) E1 (tylko poziom obszaru, mediana w promieniu) pozostaje bez zmian — rejony osobno, jeśli kiedyś potrzebne. (b) Model pulsu z Task 1-2 mógłby zostać powtórnie zbadany z warunkiem stanu wilgotności gleby PRZED pulsem (obecny model go ignoruje) — nie robione w tej sesji, eksperyment zamrożony. (c) Presja B z dróg leśnych nadal nieukończona (patrz wcześniejsze notatki).

## 2026-09-27 — (26): dwa błędy w M znalezione po A1 — percentyle per komórka klimatologii + wilgotność gleby z innego modelu

Porównanie eksportów 26.09 (Open-Meteo) / 27.09 (radar) i dodatkowy bieg `--no-radar` z 27.09 (katalog roboczy, poza repo) pokazały, że M miało tylko ~9 różnych wartości na 3656 wydzieleń mimo 71 używanych punktów pogodowych.

**Błąd 1 — percentyle cache'owane per komórka klimatologii (od `43b5a80`, 2026-09-24).** `run_poc` liczył `pct_cwb26`/`pct_sm` z wiersza pogody PIERWSZEGO wydzielenia trafiającego do komórki klimatologii (16 km przy promieniu 20 km) i używał ich dla wszystkich punktów pogody w tej komórce. Naprawa: historia klimatologii nadal cache'owana per komórka (`history_by_cell`), percentyle per punkt pogody (`percentiles_by_point`). Test: `test_run_poc_moisture_percentiles_follow_each_weather_point_not_the_climatology_cell`. **„Skok M przy dł. 21,72” z notatek (23)/(25) to była granica komórek klimatologii, nie artefakt opadu.**

**Błąd 2 — wilgotność gleby porównywana z klimatologią z innego modelu.** Po naprawie 1 rozkład per punkt (Będziemyśl 20 km, 144 punkty, 27.09, radar): percentyl bilansu wodnego z radaru jednolity 0,49–0,81 (mediana 0,66); bieżąca wilgotność gleby Open-Meteo (API prognozy, 9–27 cm) 0,135–0,27 m³/m³ vs mediana klimatologii ERA5-Land (archiwum, 7–28 cm) ~0,22–0,33 → `pct_sm` 0,00–0,04 prawie wszędzie, ~0,48 w blokach ~10 km z wartością 0,226. M = f(średnia obu) było więc sterowane blokami gleby modelu (M 0,2 vs 0,72). Wcześniejsze „północny blok najlepszy” (M 0,94 → 0,80 z radarem) wynikało z tego, że pierwsze wydzielenie komórki trafiło w taki blok. **Decyzja użytkownika (wariant 1):** nowy klucz profilu `fruiting.soil_moisture_weight: 0.0` (0,5 = dawna równa średnia), wspólna funkcja `pipeline.scoring.moisture_percentile` używana przez `score_moisture` i przez `pct_m` w `run_poc` (modulacja siedliskowa) oraz w `notebooks/03_backtest_gbif.py`. Do rewizji w A2 (własny bilans wody).

**Efekt (bieg z radarem 27.09 po obu zmianach, katalog roboczy):** F 0,69–0,86 (mediana 0,82), klasy: Bardzo dobre 3648, Dobre 8 — M z samego opadu jest wysokie wszędzie (wrzesień powyżej normy, zgodnie ze stacjami). R ≥ 80: 25, R ≥ 70: 494, maks. 85,4. Rejony: 1 (50,1433, 21,8033 — ten sam co dawny rejon 1) 80,5; nowy 2 (50,194, 21,623) 80,5; 4 (50,165, 21,778) 78,2; 3 (50,161, 21,609) 77,8; 5 (50,198, 21,689) 75,4. Przestrzennie: północ (szer. 50,1–50,25) F ~0,82–0,86, pogórze ~0,75–0,79.

**Otwarte:** (a) F znów prawie jednolite („Bardzo dobre” 99,8%) — kalibracja `moisture_midpoint` 0,50 (notatka (22)) była robiona, gdy `pct_sm` było systematycznie zaniżone przez błąd 2; zmiana wymaga zgody użytkownika. Różnicowanie w czasie ma dać A2. (b) Stosunek radar/ERA5 0,848 (notatka (25)) nadal obniża `pct_cwb26`. (c) Commit zmian i nadpisanie eksportu/frontendu — patrz rozmowa 2026-09-27.

## 2026-09-27 — aktualne (25): A1 — opady z radaru IMGW RainGRS

Zrealizowany plan `docs/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md`, wykonanie inline (Native, `superpowers:executing-plans`) w izolowanym worktree `.claude/worktrees/borowik-radar-opady-a1` na gałęzi `worktree-borowik-radar-opady-a1`. Cel: zastąpienie modelowanych opadów Open-Meteo pomiarem z radaru IMGW-PIB RainGRS dla ostatnich 30 dni, z Open-Meteo jako uzupełnieniem luk i prognozą — bez zmiany temperatury/ET0/wilgotności gleby/klimatologii/współczynników scoringu.

**Uwaga o numeracji:** plan zakładał, że ta notatka będzie "(24)" — w międzyczasie do master trafił plan zapisanych map, który zajął numer (24) jako pierwszy. Ta notatka jest więc (25).

**Co powstało:**
- Nowy moduł `pipeline/radar.py` — parsowanie siatki ESRI ASCII (`parse_grs_asc`, odrzuca HTML zamiast pliku), pobieranie archiwum (`.tar`, dobowe, od 2018, opóźnienie ~2-3 dni) i plików bieżących (`.asc`, ostatnie ~30 h) z cache per-dzień w `cache/radar_grs/*.npz` (skwantowane uint16 centi-mm, ~4-5 MB/dobę dla całej Polski), agregacja godzin do dób lokalnych (Europe/Warsaw, z uwzględnieniem DST) i scalanie z ramką dobową Open-Meteo z proporcjonalnym uzupełnieniem brakujących godzin (`merge_radar_into_daily`) oraz `make_radar_weather_fetcher` — owija dowolny `weather_fetcher` o tym samym sygnaturze, więc `pipeline.orchestrate.run_poc` nie zmienił interfejsu.
- `pipeline/weather.py::compute_weather_features` — nowa cecha `rain_radar_coverage` (wykładniczo ważony udział P26w pochodzący z radaru, 0 gdy brak `radar_frac`).
- `pipeline/orchestrate.py::run_poc` — eksportuje `rain_radar_coverage` per wydzielenie i `diagnostics["radar_coverage_mean"]`.
- `pipeline/confidence.py` — nowy czynnik jakości `pogoda_radar_1km: 0,9` (zamiast `pogoda_nwp_2km: 0,8`) gdy `rain_radar_coverage >= radar.min_coverage_for_quality` (0,8); nowy powód `weather_radar`.
- `profiles/boletus_edulis.yaml` — nowa sekcja `radar:` (`enabled`, `window_days: 30`, `min_coverage_for_quality: 0.8`).
- `pipeline/export.py` — nowe pole `rain_radar_coverage` w `SCORE_FIELDS`.
- `pipeline/prepare_trip.py` — `build_weather_fetcher` (owija bazowy fetcher radarem, `half_size_m = grid_spacing_m / 2`), nowa flaga CLI `--no-radar` (opady tylko z Open-Meteo, np. do porównania), `run_trip_preparation(..., use_radar: bool = True)`, nowy print `Opady z radaru IMGW: srednie pokrycie okna P26w NN%`.
- Frontend: `Stand.rain_radar_coverage?: number | null` w `model.ts` (ten sam wzorzec opcjonalnego pola co `G_season`/`tie_break`), link do IMGW w oknie "Warto wiedzieć", sekcja "Źródła danych" w `frontend/README.md`.

**Task 0 — ustalenia CRS/znacznika czasu:** sprawdzono `https://danepubliczne.imgw.pl/pl/repository` i stronę RainGRS w Laboratorium Modelowania Meteorologicznego CMOK IMGW-PIB — **nie znaleziono** oficjalnego opisu produktu podającego wprost układ współrzędnych siatki ani czy znacznik czasu pliku to początek czy koniec godziny akumulacji. Brak sprzeczności z założeniami (`EPSG:2180`, znacznik = koniec godziny) w tym, co udało się znaleźć — założenia zweryfikowano empirycznie w Task 7 (patrz niżej), obie się potwierdziły.

**Task 7 — walidacja (dane na żywo, 2026-09-27):**
- Porównanie z 4 stacjami Weathercloud (`notebooks/04_radar_vs_stations.py`, dane stacji w `cache/stations/weathercloud_2026-09.yaml`, poza repo), 13-23.09.2026 (doby z pełnymi 24 godzinami archiwum), znacznik = koniec godziny: MAE radaru 0,93/0,27/0,54/0,37 mm/d (S1/S2/S3/S4) vs Open-Meteo 1,41/1,12/1,04/1,65 — radar wyraźnie dokładniejszy dla wszystkich 4 stacji, zgodnie ze spike'iem z 2026-09-26 (różnice ≤ 0,02 mm). Wariant "znacznik = początek godziny" dał nieco WYŻSZE sumaryczne MAE (2,15 vs 2,11) — `GRS_TIMESTAMP_IS_HOUR_END` pozostaje `True`, bez zmian w kodzie.
- Sprawdzenie D1 (`notebooks/05_radar_era5_bias.py`): stosunek sumy opadu radaru do ERA5-Land (Open-Meteo archive) na siatce Będziemyśl 20 km (144 punkty), 2025-08-01..2025-09-30, dla 59 dni z pełnym pokryciem radaru na punkt: **0,848** (suma radar 13985 mm, ERA5 16494 mm; per-punkt: średnia 0,853, odch. std 0,104, zakres 0,635-1,147) — tuż poniżej progu akceptacji planu (0,85-1,15), o 0,002. Zgodnie z regułą D1 zatrzymano się i zapytano użytkownika; **decyzja: zaakceptować odchylenie bez zmiany kodu** (różnica w granicach szumu przy n=59 dni, kierunek zgodny z porównaniem stacyjnym). Do rewizji, jeśli rozkład M z realnego biegu wygląda nierealistycznie, albo przy walidacji A2 na GBIF.
- **Uwaga recenzenta (do sprawdzenia przy A2):** ten sam recenzent zauważył, że dowód na "kierunek zgodny z porównaniem stacyjnym" wyżej opiera się tylko na MAE (błąd bezwzględny), nie na sumach radar/stacja wprost — notebook 04 wypisuje też `suma obs=`/`radar=` dla każdej stacji (13-23.09: S1 46,4/39,3, S2 31,6/31,3, S3 33,2/35,6, S4 34,2/35,2 mm), które są bliżej siebie niż radar/ERA5 (0,848) — sugeruje to, że to klimatologia ERA5 może być systematycznie "mokrzejsza" niż lokalna rzeczywistość w tym rejonie, a nie że radar jest "zbyt suchy". Wart ponownego podniesienia przy A2.

**Task 8 — realny bieg Będziemyśl 20 km, przed/po (2026-09-27, `notebooks/output/no_radar` vs `notebooks/output/`):**
- Radar: `Radar IMGW (RainGRS): biezace 2, brak 1, cache 28 dob`, `Opady z radaru IMGW: srednie pokrycie okna P26w 82%`.
- Rozkład klas F (3656 wydzieleń przechodzących maskę, identyczne w obu biegach): **przed** (Open-Meteo) Bardzo dobre 1808, Dobre 863, Umiarkowane 985. **Po** (radar) Bardzo dobre 1808 (bez zmian), Dobre 3 (z 863!), Umiarkowane 1845 — radar w tym konkretnym biegu/okresie systematycznie "suchszy" (zgodne z D1: stosunek 0,848), duża część wydzieleń "Dobre" spadła do "Umiarkowane"; klasa "Bardzo dobre" nietknięta.
- R ≥ 85: 0 w obu biegach (bez zmian).
- 5 rejonów: identyczny skład wydzieleń w każdym z 5 rejonów przed/po (9/12/3/4/3 wydzieleń), `rank_score` spadł jednolicie o ok. 5 punktów w każdym (79,83→74,65, 77,83→72,77, 76,74→71,76, 75,68→70,76, 73,66→68,87) — efekt niższego F z radaru, nie zmiana grupowania.
- Skok M ok. lon 21,72 (artefakt siatki Open-Meteo zgłoszony 2026-09-26): **nie zniknął** — pasmo zachodnie (lon 21,60-21,71) średnia M 0,278→0,168 (przed/po), pasmo wschodnie (lon 21,73-21,85) 0,746→0,655; względny skok podobny lub nieco większy z radarem. Wygląda na to, że skok NIE jest wyłącznie artefaktem modelu opadu Open-Meteo (klimatologia/percentyle nadal z ERA5, D2 — być może stamtąd), albo odzwierciedla realną zmienność terenową (pogórze). Nierozstrzygnięte — do sprawdzenia przy A2 lub jeśli wpłynie na rekomendacje.
- Dane zsynchronizowane do frontendu (`npm run sync-data`) z biegu z radarem.

**Testy:** 439 (402 na starcie planu → 439, +37 nowych w `test_radar.py`/`test_weather.py`/`test_orchestrate.py`/`test_confidence.py`/`test_export.py`/`test_prepare_trip.py`), wszystkie bez sieci. Frontend: 58 (56→58, +2 w `model.test.ts`), `tsc --noEmit` czysto.

**Błąd znaleziony i naprawiony podczas wykonania (Task 6):** `run_trip_preparation`'s nowy domyślny `use_radar=True` sprawił, że 3 istniejące testy w `tests/test_search_area.py` (wołające `run_trip_preparation` bezpośrednio, bez wyłączenia radaru) zaczęły robić prawdziwe, niezamockowane zapytania HTTP do `danepubliczne.imgw.pl` — jeden pełny bieg testów trwał **6 godzin 6 minut** zamiast ok. 20 sekund, bo IMGW bywa wolny, a nie nieosiągalny (więc `RadarUnavailableError`'s fallback się nie uruchamiał). Naprawione: `use_radar=False` w tych 3 wywołaniach + strażnik w `configure_sources` rzucający natychmiast, jeśli dojdzie do prawdziwego zapytania radarowego (zamienia ewentualny przyszły regres z wielogodzinnego zawieszenia na błąd w ~3 sekundy).

**Otwarte kwestie / następny krok:**
- Wilgotność gleby nadal liczona z opadu Open-Meteo, nie radaru (świadome, D2) — do rewizji w A2 (model wysypu/flush).
- Próbkowanie przestrzenne radaru per punkt siatki pogodowej (średnia blokowa), nie per wydzielenie — możliwe doprecyzowanie później.
- Skok M przy lon 21,72 nierozwiązany (patrz wyżej) — może nie być artefaktem Open-Meteo.
- Następny krok wg planu: **A2** (model fazy wysypu, licząc od konkretnego opadu, z uwzględnieniem nocnej temperatury) oraz osobno **B** (presja z rowerów/pieszych po duktach leśnych — patrz notatka (23) niżej).

## 2026-09-26 — aktualne (24): zapisane mapy (lista do porównywania analiz)

Zrealizowany plan `docs/superpowers/plans/2026-09-26-borowik-saved-maps.md` (spec: `docs/superpowers/specs/2026-09-26-borowik-saved-maps-design.md`), wykonanie inline (Native, `superpowers:executing-plans`) w izolowanym worktree `.claude/worktrees/borowik-saved-maps` na gałęzi `worktree-borowik-saved-maps`. Cel: zapisanie aktualnie wyświetlanej analizy pod nazwą (np. "Będziemyśl - 20km - 26.09") i przełączanie się między zapisanymi analizami w przeglądarce, bez ponownego uruchamiania pipeline'u.

**Co powstało:**
- `launcher/trip_archive.py` — czysta logika (bez GUI, w pełni TDD'owana, `tests/test_trip_archive.py`): `slugify`/`trip_id`, `read_index`/`write_index`/`upsert_entry`, `read_day`, `copy_trip_files`, `trip_exists`, `save_trip`. Kopiuje `scores.json`/`stands.geojson`/opcjonalnie `regions.json`/`details.json` z `frontend/public/data/` do `frontend/public/data/trips/<id>/` i dopisuje wpis do `frontend/public/data/trips/index.json`.
- `launcher/launcher.pyw` — nowe pole „Nazwa miejsca” i przycisk „Zapisz do listy” (`on_save_trip`), z potwierdzeniem nadpisania istniejącego wpisu.
- Frontend: `loadData(basePath)` (parametryzacja dotychczasowych trzech `fetch()`), `TripMeta`/`parseTrips`/`formatTripLabel`/`loadTrips` w `model.ts`; pasek „Zapisane mapy” nad mapą w `main.ts` (`renderTripsPanel`, przełączanie przez `initialize(basePath, tripId)`, `retry` wraca do tego samego celu).

**Czysto addytywne:** zero zmian w `pipeline/` i zero zmian w kształcie jakiegokolwiek dotychczas eksportowanego pola — cały mechanizm opiera się na kopiowaniu już zsynchronizowanych plików. Zapisane migawki są zamrożone: nowa analiza tego samego miejsca nie zmienia wcześniej zapisanych wpisów (zweryfikowane ręcznie w przeglądarce z syntetycznymi danymi, zob. plan Task 5).

**Świadomie pominięte (YAGNI):** usuwanie/zmiana nazwy zapisanego wpisu z poziomu aplikacji (na razie: ręcznie w Eksploratorze), limit liczby zapisów, synchronizacja między urządzeniami.

**Do sprawdzenia przy okazji kolejnej sesji (nie naprawione, poza zakresem tego planu):** w `npm run dev` serwer Vite odpowiada na brakujący `public/data/*.json` stroną `index.html` (HTTP 200 SPA-fallback) zamiast 404 — `loadData`'s sprawdzanie `response.ok` dla opcjonalnych `regions.json`/`details.json` bierze to za "plik jest, ale niepoprawny" zamiast "pliku nie ma". W realnym przepływie (`npm run sync-data` zawsze pisze oba pliki, bo grupowanie jest aktywne) nigdy się nie objawia — znalezione tylko przy budowaniu syntetycznych danych testowych bez `regions.json`.

## 2026-09-26 — aktualne (23): pierwsza obserwacja terenowa, porównanie radar/stacje, decyzje A1/A2/B — **następny krok: plan A1**

**Następna sesja:** wykonać `docs/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md` (zacząć od Task 0 — decyzje D1–D4 do potwierdzenia + niezacommitowane `pipeline/weather.py`/`notebooks/03_backtest_gbif.py`). **Tryb wykonania wybrany przez użytkownika: Native** (`superpowers:executing-plans`, inline, jeden recenzent całej gałęzi na końcu), model `opusplan`. Kod w tej sesji **nie był zmieniany** (tylko ten plan + notatka).

**Obserwacja terenowa 2026-09-26 (sobota, ~11–13, rejon 1 z eksportu 2026-09-26, wejście od południa od Bratkowic):** 2 h marszu, ok. 10 grzybów wyraźnie starych (głównie podgrzybki, 2 koźlarze) + 2 małe (~3 cm), w tym 1 borowik. W rejonie 1 widoczne ślady innych grzybiarzy — wg użytkownika dojeżdżają rowerami duktami leśnymi. Wnioski użytkownika (przyjęte):
1. Model F ocenia „czy warunki sprzyjają teraz”, nie „w której fazie jest wysyp” — potrzebny model czasu owocnikowania liczony od konkretnego opadu, z temperaturą (także nocną). Obecnie noce wchodzą tylko przez `tmin3` (przymrozek), `tmean20` to średnia dobowa.
2. Presja P liczy tylko parkingi/drogi utwardzone (`osm.road_highway_types` celowo bez `track`) — nie widzi rowerzystów/pieszych z pobliskich wsi wchodzących duktami.

**Decyzje użytkownika (2026-09-26):**
- **A (model wysypu):** wariant „faza wysypu na dziś + ocena kolejnych dni”. Podzielony na **A1** (źródło opadów: radar) → **A2** (model wysypu). Relacja A2 do R (osobny wskaźnik vs. zastąpienie F) — **jeszcze nierozstrzygnięta**, rekomendacja: osobny wskaźnik + oś czasu, R bez zmian do czasu walidacji na GBIF.
- **Źródło opadów:** radar IMGW RainGRS jako główne źródło opadów z przeszłości; Open-Meteo uzupełnia luki i daje prognozę.
- **B (presja: rowery/piesi po duktach):** osobny podprojekt, później.

**Radar IMGW — ustalenia (sprawdzone na żywo):** publiczny produkt RainGRS (radar + deszczomierze, godzinowy, 1 km, ESRI ASCII) — pliki bieżące ~30 h + archiwum dobowych tarów od 2018 (opóźnienie ~2–3 dni), bez klucza. **Sekcja 3.3 `docs/projekt-borowik.md` („tylko najnowszy plik, wymaga pollera”) jest nieaktualna** — do poprawy w A1 Task 8. Szczegóły, URL-e i pułapki (HTML zamiast 404, brak godzin 19–23 UTC w archiwum przed 13.09, `date` Open-Meteo = północ lokalna w UTC) w sekcji „Decyzje projektowe” planu A1.

**Porównanie opadów (spike, 2026-09-26):** 4 niezależne stacje Weathercloud (S1 ok. 3–4 km od rejonu 1, S2 Będziemyśl, S3 pogórze na południu, S4 zachód od Sędziszowa; dane dobowe w `cache/stations/weathercloud_2026-09.yaml`, poza repo — lokalizacje prywatnych stacji). MAE dobowe 13–23.09 (pełne godziny radaru):

| Stacja | radar RainGRS | Open-Meteo | suma obs / radar / OM (mm) |
|---|---|---|---|
| S1 | 0,91 | 1,41 | 46,4 / 39,4 / 36,3 |
| S2 | 0,28 | 1,12 | 31,6 / 31,5 / 43,9 |
| S3 | 0,55 | 1,04 | 33,2 / 35,6 / 42,6 |
| S4 | 0,38 | 1,65 | 34,2 / 35,2 / 51,6 |

29.08–12.09 (radar bez 5 h/dobę): MAE radar 0,58–1,31 vs OM 1,68–2,70. Open-Meteo przegapił burze 29.08/31.08/03.09 (stacje 4–15 mm, OM 0–2 mm) i dał fałszywe opady 03.09 (S4 7,7 mm), 05.09, 15.09; 21.09 przy S4 30 mm vs stacja 17,3. Trafność „dzień ≥2 mm”: radar 14/15 i 11/11, OM 11–13/15 i 9–11/11.

**Obserwacja o przestrzennym M (eksport 2026-09-26, Będziemyśl 20 km):** M nie jest jednolite — 0,94 w północnym bloku lasów Głogowa (1808 wydzieleń, wszystkie 5 rejonów), 0,43 na zachodzie, 0,21–0,29 na pogórzu. Ostry skok 0,43→0,94 ok. dł. 21,72 wygląda na granicę komórek modelu Open-Meteo; radar za 13–23.09 pokazuje różnice rzędu 10–25% (31,5–39 mm). A1 Task 8 ma sprawdzić, czy skok znika.

**Odpowiedzi dla użytkownika w tej sesji (kontekst, nie kod):** rekomendacja wyjazdu do rejonu 1 od południa (Bratkowice) zamiast od DW987/Ostrów; pogoda: ~30 mm 21–22.09 (model) — dziś 4.–5. dzień po opadzie, szczyt drugiej fali szacowany ~30.09–5.10. Serwisy grzybiarzy (grzyby.pl 24.09): na południu jesienny wysyp „w ciągu tygodnia–dwóch”; zgłoszenia z Przemyśla 25–26.09 (liczne prawdziwki).

## 2026-09-25 — aktualne (22): fenologia (G_season), kalibracja wilgotności, tie-break pokrycia/zadrzewienia

Zrealizowany plan `docs/superpowers/plans/2026-09-25-borowik-fenologia-wilgotnosc-tiebreak.md` (przegląd użytkownika 2026-09-25, wykonanie inline, TDD krok po kroku, 10 zadań implementacyjnych + to podsumowanie). Trzy niezależne zmiany, każda addytywna względem H/R_final:

**1. G_season (fenologia z GBIF).** Nowy moduł `pipeline/phenology.py::compute_g_season(target_doy, profile)` — statyczna krzywa sezonowości Boletus edulis dla Polski (GBIF, zapytanie na żywo 2026-09-25: `api.gbif.org/v1/occurrence/search?country=PL&scientificName=Boletus%20edulis&limit=0&facet=month&facetLimit=12`, n=1270 rekordów z miesiącem — liczby zweryfikowane, dokładnie zgodne z liczbami podanymi w przeglądzie użytkownika), zapisana statycznie w `profiles/boletus_edulis.yaml` (`phenology.gbif_monthly_counts`), interpolowana liniowo między środkami miesięcy (dzień 15), bez dodatkowego wygładzania (krzywa surowa jest już jednomodalna, dodatkowe wygładzanie zmiękczyłoby realny, ostry spadek po wrześniu — uzasadnienie w docstringu). Dolny limit 0,05. Wpięty w `pipeline/orchestrate.py::run_poc` (zastępuje sztywne `g_season=1.0` w wywołaniu `compute_fruiting`), eksportowany per wydzielenie (`G_season` w `scores_{day}.json`), z notatką w wyjaśnieniach („poza szczytem sezonu (G_season=X,XX)") gdy < 0,5 (`pipeline/explain.py::g_season_note`, `pipeline/mvp.py`).

**2. Kalibracja wilgotności.** `profiles/boletus_edulis.yaml`: `fruiting.moisture_midpoint` 0,35 → 0,50 (`moisture_slope` bez zmian, zgodnie z instrukcją). Tabela scenariuszy (T=1, G_season=1) przed/po:

```
                    przed (0,35)              po (0,50)
percentyl 0,15      M=0,119 F=0,279 Umiark.   M=0,029 F=0,120 Słabe
percentyl 0,35      M=0,500 F=0,660 Dobre     M=0,182 F=0,360 Umiark.
percentyl 0,50      M=0,818 F=0,886 B.dobre   M=0,500 F=0,660 Dobre
percentyl 0,70      M=0,971 F=0,982 B.dobre   M=0,881 F=0,927 B.dobre
percentyl 0,90      M=0,996 F=0,998 B.dobre   M=0,982 F=0,989 B.dobre
```

**3. Tie-break (pokrycie gleby + zadrzewienie).** Nowy moduł `pipeline/tie_break.py` (wzorem `pipeline/bdl_package_details.py` z B3) — **nigdy nie importowany przez `pipeline/orchestrate.py`, `pipeline/habitat.py`, `pipeline/scoring.py`, `pipeline/mvp.py`** (strukturalna, nie tylko testowana, gwarancja zerowego wpływu na H/R_final). `compute_tie_break(veg_cover_cd, standdensity_index) -> float` 0–1: preferencja pokrycia gleby (MSZC/MSZ/ŚCIO > ZAD/ZIEL > SZAD/SZCH/NAGA — znaczenia zweryfikowane przez dwa niezależne wyszukiwania web, zgodne z „Wykazem skrótów i symboli stosowanych w opisach taksacyjnych" Instrukcji Urządzania Lasu; w paczce BDL brak własnego słownika dla `veg_cover_cd`, potwierdzone nieobecne we wszystkich 5 paczkach) uśredniona z preferencją pośredniego zadrzewienia (plateau [0,7; 1,0] = 1,0, liniowy spadek do 0 poza tym zakresem — realne dane Będziemyśla: mediana 0,9, IQR 0,7–1,0, 92,9% ≤ 1,5). Używany **wyłącznie** jako drugi klucz sortowania: R_final zaokrąglony do 2 miejsc po przecinku (precyzja dobrana na realnym eksporcie — 2 miejsca grupuje tylko bliskie remisy, maks. grupa 4/500 w czołówce, vs. zaokrąglenie do pełnego punktu dające grupy po 67 — zbyt grube, przytłoczyłoby własny sygnał R), potem `tie_break` malejąco — w `pipeline/regions.py::_summarize_cluster` (kolejność `stand_ids` rejonu) i w `frontend/src/model.ts::joinData` (lista „Wydzielenia"). Wpięty w `pipeline/prepare_trip.py` **przed** `group_into_regions` (wymóg kolejności). Karta (`details_{day}.json`): nowe pola `veg_cover` (forma słowna) i `standdensity_index` obok istniejącego `density`/„Zwarcie" (`frontend/src/main.ts::packageSection`).

**Weryfikacja na realnych danych** (bez sieci, Będziemyśl 20 km, target_date 2026-09-25, cache/weather_points + cache/climatology_points + cache/bdl_tiles_v2 + cache/bdl_packages — 144/144 punktów pogody i 16/16 klimatologii z cache, zero zapytań sieciowych):
- Rozkład klas F: **przed** (moisture_midpoint=0,35, G_season na sztywno 1,0 — odtworzone przez tymczasowe monkeypatch `pipeline.orchestrate.compute_g_season` na potrzeby porównania) **100% „Bardzo dobre" (3656/3656)** — dokładnie odtwarza zgłoszony problem. **Po** wszystkich trzech zmianach: Bardzo dobre 1811 (49,5%), Dobre 1534 (42,0%), Umiarkowane 311 (8,5%) — realna, sensowna dyferencjacja zamiast jednej klasy. `fruiting_classes` **nie zmienione** — rozkład po zmianie wygląda dobrze, korekta nie była potrzebna.
- Top-20 (po R_final): 18/20 wydzielen wspólnych z „przed" — ranking w większości zachowany (te same warunki pogodowe/G_season działają w przybliżeniu jednolicie na cały obszar), z niewielkimi przetasowaniami.
- Kolejność członków rejonu z tie_break widoczna na żywo: rejon 2 (13 członków) — pierwsze 5: R=87,59/tb=1,00, R=87,59/tb=1,00, R=87,59/tb=0,80, R=87,59/tb=0,80, R=87,59/tb=0,73 — wydzielenia związane remisem przy R (zaokrąglonym) uporządkowane realnie przez tie_break, nie przez arbitralną kolejność indeksu przestrzennego jak wcześniej.

Testy: 372 Python (352 przed tym planem → 372, +20: nowe `test_phenology.py` (5), `test_tie_break.py` (13), rozszerzenia `test_orchestrate.py`/`test_explain.py`/`test_mvp.py`/`test_export.py`/`test_regions.py`/`test_prepare_trip.py`/`test_scoring.py`), wszystkie bez sieci. Frontend: 49 (44 → 49, +5 w `model.test.ts`), `tsc --noEmit` czysto, `vite build` OK.

**Nie ruszono:** `pipeline/habitat.py` (H, score_host/score_site/score_age/passes_mask) — zero zmian; `fruiting_classes` — bez zmian (rozkład po kalibracji wilgotności wygląda dobrze); `moisture_slope` — bez zmian zgodnie z jawną instrukcją użytkownika.

## 2026-09-25 — aktualne (21): B3 — karta wydzielenia: skład, sąsiedztwo, budowa/ochronność

Zrealizowany krok B3 z planu 2.1 (`docs/projekt-borowik.md` §5.3 "Różnicowanie H" pkt 3) — **wyłącznie prezentacja na karcie**, zero wpływu na H/F/R. Po B2 (notatki (19)/(20)) było to jedyne, co zostało z "Różnicowania H"; decyzja z (20) — dalszego różnicowania nie robimy bez danych terenowych, C4 (domieszka z sąsiedztwa jako tie-breaker w H) skreślone w §13.1.

**Co zrobione:**
- Nowy `pipeline/bdl_dictionaries.py::load_dictionaries(packages_dir)` — słowniki (area_type, density, storey, tree_species, soil_subtype, prot_categ, part) z pierwszej dostępnej paczki; zweryfikowane bajt-w-bajt identyczne między nadleśnictwami, więc jedna paczka wystarcza. Brak paczek → `{}` (surowe kody, bez błędu).
- Nowy `pipeline/bdl_package_details.py::load_package_details(packages_dir)` — pełny skład warstwy `DRZEW` (nie tylko S_host), `density_cd`, podszyt (**wszystkie** wiersze, łącznie z `MJS`/`PJD` — informacyjne, nie wzór), `soil_subtype_cd`, per `adr_for`. Celowo osobny moduł od `pipeline/bdl_packages.py` (B2/S_host) — nigdy nie importowany przez `orchestrate.py`/`habitat.py`/`scoring.py`/`mvp.py`, co jest **strukturalną** (nie tylko testową) gwarancją zerowego wpływu na R/H.
- Nowy `pipeline/neighbors.py::find_neighbor_labels(target_row, context_stands, dictionaries)` — sąsiedzi ze wspólną granicą ≥ 20 m (`geom.boundary.intersection`, **nie** % obwodu — duże wydzielenie stykające się krótkim odcinkiem z wieloma małymi nie dostaje fałszywych etykiet). Nie-`D-STAN` → nazwa z `area_type_dic`; `D-STAN` o innym gatunku panującym lub wieku < 20 lat → etykieta ("drzewostan {gatunek}" / "młodnik {gatunek} ({wiek} lat)"); ten sam gatunek i wiek ≥ 20 → pominięty. Wejście: `context_stands` (pełny fetch z kafli, nie promień) — ta sama logika co istniejące `compute_forest_boundary`, żeby granica promienia nie tworzyła sztucznych sąsiadów.
- `pipeline/export.py::write_details_json` — nowy, **osobny plik `details_{day}.json`** (nie w `scores_{day}.json`): realny `scores_2026-09-25.json` (Będziemyśl, 4703 rekordy, 6,58 MB) urósłby o szacunkowo 35-55%, mimo że karta szczegółów jest oglądana rzadko. Ten sam wzorzec "opcjonalny plik, brak = brak sekcji" co `regions_{day}.json`.
- `pipeline/prepare_trip.py` — nowy blok po `group_into_regions` (już po całym scoringu): słowniki + szczegóły paczki + sąsiedztwo dla `enriched`, `write_details_json`, `details_path` w summary/printach.
- **Test regresyjny jawny**: `tests/test_prepare_trip.py::test_b3_detail_card_step_does_not_change_r_or_h` — migawka `enriched["R_final"]`/`["H"]` przed i po dokładnie tej sekwencji wywołań co w `prepare_trip.py`, `pandas.testing.assert_series_equal`.
- Frontend: `StandDetail`/`SpeciesShare` w `model.ts`, `parseData`/`loadData` — `details.json` opcjonalny, ten sam wzorzec co `regions.json` (walidacja kształtu + spójność dnia + `stand_id` musi być znany, brak pliku = brak sekcji, nie błąd). `main.ts::renderDetail` — nowe sekcje "Drzewostan i otoczenie" (skład gatunkowy z udziałami, zwarcie, podszyt, typ gleby, "Graniczy z", budowa drzewostanu, kategoria ochronności), zastępują placeholder "Domieszki gatunkowe: brak danych". `frontend/scripts/sync-data.mjs` — `details_{day}.json` → `details.json`, ten sam wzorzec co regions (walidacja + usunięcie nieaktualnego pliku, gdy nowy dzień go nie ma).

**Dwa realne błędy znalezione i naprawione podczas weryfikacji na Będziemyślu** (nie na syntetycznych fixture'ach — realne paczki ujawniły przypadki, których nie było w testach jednostkowych):
1. Pusta komórka `density_cd`/`soil_subtype_cd` w istniejącym wierszu `f_arod_storey`/`f_subarea` czyta się jako pandas `NaN` (float), nie `None` — poprzedni kod (`if soil else None` / brak zabezpieczenia dla density) traktował `NaN` jako "obecne" (bo `bool(nan) is True`), więc trafiało nieprzetworzone do `json.dumps(allow_nan=False)` i wywalało **cały** eksport. Naprawa: `isinstance(cd, str)` zamiast prawdziwościowego sprawdzenia.
2. Wiersze `PODSZ` (podszyt) bez numerycznego filtra (celowo, dla kompletności listy) mają w realnych danych **30 050** wierszy z pustym `part_cd_act` (gatunek obecny, bez zmierzonego udziału) — też `NaN`, ten sam crash. Naprawa: `.fillna("")` na `part_cd_act` przy wczytywaniu; frontend (`speciesList` w `main.ts`) pomija teraz pusty nawias z udziałem, gdy go nie ma, zamiast pokazywać "gatunek ()".

Oba przypadki dodane jako testy regresyjne w `tests/test_bdl_package_details.py` (puste komórki w istniejącym wierszu — różne od braku wiersza, już pokrytego wcześniej).

**Weryfikacja na realnych danych** (bez sieci — `pipeline.search_area` z jawnie rzucającym "no-network fetcherem", jak w B2; bez pełnego `prepare_trip`, zgodnie z planem): Będziemyśl 20 km, 4149 wydzieleń D-STAN w promieniu, wszystkie pokryte paczką (5 paczek już w `cache/bdl_packages/`). Słowniki: 199 area_type, 194 tree_species, 109 soil_subtype itd. Sąsiedztwo policzone dla wszystkich 4149 w 4,6 s (3324 mają ≥1 etykietę sąsiada). `details_2026-09-25.json` wygenerowany: 3,92 MB / 4149 rekordów (~945 B/rekord — zgodne z szacunkiem z planu). Istniejący `scores_2026-09-25.json` (6,58 MB, 4703 rekordy) **niezmieniony** — B3 nigdy go nie dotyka (strukturalnie, nie tylko w tym przebiegu).

Testy: 340 (312→340: +28 — `test_bdl_dictionaries.py`, `test_bdl_package_details.py`, `test_neighbors.py` nowe pliki, rozszerzenia `test_export.py`/`test_prepare_trip.py`), wszystkie bez sieci. Frontend: 39 (28→39 w `model.test.ts` + 11 w `sync-data.test.mjs`, w tym 4 nowe dla `details.json`), `tsc --noEmit` czysto, `vite build` OK.

**Nie zweryfikowano w przeglądarce na żywo** — środowisko sandboxa: `Claude in Chrome` nie miał dostępu do `localhost` serwera deweloperskiego uruchomionego w tej samej sesji (błąd sieciowy w karcie mimo że `curl` z shella widział serwer poprawnie). Zamiast tego: `tsc --noEmit` czysto, `vite build` bez błędów, pełne testy jednostkowe (w tym 6 nowych w `test_export.py` sprawdzających dokładny kształt rekordu) i wygenerowany realny `details.json` skopiowany do `frontend/public/data/` (poza repo, `.gitignore`) na wypadek, gdyby użytkownik chciał sam otworzyć `npm run dev` i zerknąć na kartę.

**Nie ruszono:** `pipeline/orchestrate.py`/`habitat.py`/`scoring.py`/`mvp.py`/`bdl_packages.py` (S_host, B2) — zero zmian. Rejony, pogoda, dalsze różnicowanie H (C4, skreślone).

## 2026-09-25 — aktualne (20): naprawa B2 — powielone wiersze G_SUBAREA dawały H > 1

Pierwszy pełny przebieg Będziemyśl 20 km (z 5 paczkami BDL) dał H do 1,499 i R do 100,2 dla 26 wydzieleń w promieniu (137 w paczkach). Przyczyna: paczka Strzyżów 2026 ma 262 powielone wiersze w `G_SUBAREA.shp` (to samo `a_i_num`/`adr_for`, osobne poligony); `pipeline/bdl_packages.py` łączył skład gatunkowy z każdym wierszem, więc udziały sumowały się do 2–10. Pozostałe 4 paczki bez duplikatów; mapowanie `a_i_num`↔`adr_for` wszędzie 1:1.

Naprawa: `drop_duplicates(["a_i_num", "adr_for"])` przed joinem + zabezpieczenie — wydzielenie z sumą udziałów > 10/10 jest pomijane (fallback na WFS) z głośnym `UWAGA` w konsoli. Testy: powielona geometria, suma > 10/10 (312 passed). Na realnych paczkach: 13 574 wydzieleń, maks. suma udziałów 1,0, maks. S_host 1,0, nic nie odrzucone.

Przebieg po naprawie (z cache, tylko zakazy na żywo): 3 656 w masce, R ≥ 90: 76, R ≥ 85: 249, H maks. 1,0. Rejony 1–3 bez zmian, 4–5 lekko przesunięte (zawyżone wydzielenia Strzyżowa podnosiły próg top 5%). Wszystkie rejony: sosna na BMŚW, Nadl. Głogów (4 rejony) i Tuszyma. Siedlisko `LWYZS` (pogórze, buk/jodła) ma medianę R 53 vs 79,5 dla BMŚW — obserwacja z sekcji 0.2 planu potwierdzona, wartość S_site bez zmian do czasu weryfikacji terenowej. Frontend zsynchronizowany.

## 2026-09-25 — aktualne (19): B2 — pełny skład gatunkowy z paczek BDL do S_host

Zrealizowany krok B2 z planu 2.1 (`docs/projekt-borowik.md` §13.1, §5.3 "Różnicowanie H" pkt 1), na podstawie rozpoznania B1. Przed planem implementacji pokazane i przeanalizowane liczby z realnej paczki Kędzierzyn (patrz `docs/bdl-paczki-rozpoznanie.md`, sekcja "B2 — wdrożenie"); plan skorygowany przez użytkownika trzy razy (kody gatunków, dodatkowa weryfikacja płaskowyżu, zmiana obszaru testowego na Będziemyśl) przed akceptacją.

**Co zrobione:**
- Nowy `pipeline/bdl_packages.py::load_packages(packages_dir)` — auto-wykrywa paczki BDL pod `cache/bdl_packages/*/` po polu `adr_for` (join z `G_SUBAREA.shp`), zwraca `adr_for -> PackageComposition` (skład warstwy `DRZEW`, tylko wiersze z liczbowym `part_cd_act` — kody `MJS`/`PJD` z `f_part_dic` to "poniżej 5%, niezmierzone" i celowo nie wchodzą do sumy). Brak katalogu/pustej paczki → `{}`, bez błędu.
- `pipeline/habitat.py::score_host_composition` — `Σ udział_i × powinowactwo_i` z realnego składu; nieznany gatunek → `unknown_host_affinity` + licznik diagnostyczny (nie błąd). `compute_habitat` dostał opcjonalny `s_host` override (`None` = dokładnie dawne zachowanie).
- `pipeline/orchestrate.py::run_poc` — nowy `package_index` param; per wydzielenie sprawdza `package_index.get(adr_for)` i wybiera S_host z paczki albo z WFS (mieszany przebieg możliwy, przetestowany). Nowe kolumny `s_host_source`/`s_host_package_date`, nowe diagnostyki `package_stand_count`/`package_unknown_species_count`.
- `pipeline/confidence.py` — `s_host_source == "paczka"` → nowy czynnik `kompletnosc_pelny_sklad = 1,0` i powód `species_full_composition`; **"tylko gatunek panujący" znika** dla wydzieleń z paczką. Wynikowa klasa nadal capped `SREDNIA` (`model_confidence_cap`, bez zmian fazy 1-4) — zmienia się tylko uzasadnienie.
- `pipeline/export.py` — `s_host_source`/`s_host_package_date` w `scores_{day}.json`.
- `pipeline/prepare_trip.py` — `load_packages(cache_dir / "bdl_packages")` wołane automatycznie, przekazywane do `run_poc`; print liczby wykrytych wydzieleń z paczki.
- `profiles/boletus_edulis.yaml` — 8 nowych kodów gatunków (`CZM`, `KSZ`, `CZR`, `SL.A`, `GR`, `KL.PE`, `WZ.S` → 0,0; `TP.C` → 0,2 jak `TP`), rozwiązanych jednoznacznie przez `f_tree_species_dic.txt` samej paczki (nazwa + łacińska), nie zgadywane; dopisane też do `zero_affinity_mask_species` (poza `TP.C`). Poprawiony komentarz przy `CZM.P` (to *Prunus serotina*, "czeremcha późna", nie "pospolita" — `CZM` to prawdziwa pospolita; wartości 0,0 bez zmian). Nowy `confidence.data_quality_factors.kompletnosc_pelny_sklad` i `confidence.reasons.species_full_composition`.

**Zakres — tylko S_host:** do H wchodzi wyłącznie skład warstwy `DRZEW`. Zwarcie, podszyt, typ gleby — **nie do H** (brak zwalidowanych wag), najwyżej pola informacyjne na karcie w B3.

**Region testowy zmienił się w trakcie tego kroku** (notatka (18) niżej) — Kędzierzyn posłużył tylko do testu formatu (B1) i wstępnych liczb; **weryfikacja końcowa zrobiona na Będziemyślu, 20 km** (patrz (18)), z 5 paczkami już pobranymi w `cache/bdl_packages/` (Głogów, Strzyżów, Tuszyma, Dębica, Kolbuszowa — pokrycie 4054/4149 = 97,7% wydzieleń D-STAN w promieniu).

**Weryfikacja na realnych danych** (bez sieci — `pipeline.search_area` + `cache/bdl_tiles_v2`, testowany "no-network fetcher" jawnie rzuca wyjątkiem, gdyby próbował sięgnąć po sieć; bez pełnego `prepare_trip` — porównanie nie potrzebuje pogody/OSM), przez **prawdziwy kod pipeline'u** (nie ręczny skrypt): dla n=3778 wydzieleń D-STAN Będziemyśla (po masce wieku, pokrytych paczką):
- S_host średnia 0,740→0,806, H średnia 0,721→0,747.
- **S_host = 1,0 dokładnie: 743→861 (+118).** **H ≥ 0,95: 472→601 (+129).** H ≥ 0,90: 746→966 (+220).
- **Potwierdzona hipoteza użytkownika: płaskowyż rośnie, nie maleje** — zero wydzieleń wypadło z S_host=1,0 (czysty gatunek o powinowactwie 1,0 przy `part_cd=10` dawał 1,0 już wcześniej), nowe dołączają tam, gdzie gatunek panujący WFS miał `part_cd<10`, ale reszta udziału z paczki to inne gatunki o powinowactwie 1,0 (np. SO+ŚW). **Wzór bez zmian** — to obserwacja do zanotowania na przyszłość (dalsze dostrajanie wag), nie problem do naprawy teraz.

Testy: 310 (280→310, +30: `test_bdl_packages.py` nowy plik + rozszerzenia `test_habitat.py`/`test_confidence.py`/`test_orchestrate.py`/`test_export.py`/`test_profile_coverage.py`), wszystkie bez sieci (syntetyczne fixture'y, nie realne paczki).

**Dokumentacja pobierania paczek:** nowa sekcja w `docs/bdl-paczki-rozpoznanie.md` ("Jak pobrać i rozpakować kolejną paczkę") — formularz, `cache/bdl_packages/<nazwa>/`, auto-wykrywanie po `adr_for`. **Przypomnienie z notatki (18): nigdy nie wpisywać e-maila użytkownika do żadnego pliku w repo.**

**Nie ruszono:** podszyt/zwarcie/gleba do H (B3 najwyżej), pobieranie kolejnych paczek poza już obecnymi 5, rejony/pogoda/R (poza zakresem tego kroku).

## 2026-09-25 — aktualne (18): region docelowy zmieniony na Będziemyśl (Podkarpacie), 20 km

Decyzja użytkownika: pierwsze wyjazdy testowe z **Będziemyśla** (50.0555, 21.7889, gm. Sędziszów Małopolski), **promień 20 km**. Od B2 wszystkie kryteria z planu 2.1 sprawdzać na tym obszarze, nie na Kieleczce: `prepare_trip --lat 50.0555 --lon 21.7889 --radius-km 20`.

Rozpoznanie (tylko BDL WFS, 22 kafle już w `cache/bdl_tiles_v2`; Open-Meteo, GDOŚ, OSM jeszcze niepobrane): RDLP Krosno + Kraków, 4 153 wydzielenia D-STAN, 0 kodów spoza profilu. Nadleśnictwa: Głogów 2 328, Strzyżów 738, Tuszyma 736, Dębica 179, Kolbuszowa 172. Paczki BDL do B2: Głogów, Strzyżów, Tuszyma (92% obszaru). Szczegóły i obserwacja o `LWYZS` (S_site 0,6 na pogórzu): `docs/projekt-borowik.md` sekcja 0.2.

Usunięto adres e-mail użytkownika z `docs/bdl-paczki-rozpoznanie.md` i z notatek (16) poniżej — nie wpisywać danych osobowych do repo.

## 2026-09-24 — aktualne (17): B1 — potwierdzone na realnej paczce Kędzierzyn (zastępuje notatkę (16))

Ta notatka **zastępuje** poprzednią (16) co do stanu weryfikacji — tamta miała rekomendację warunkową (tylko ze schematu dokumentacji), bez dostępu do realnych danych. Użytkownik przesłał link do pobrania paczki (BDL wysłał go na podany e-mail); paczka `BDL_02_10_KEDZIERZYN_2026.zip` pobrana i przeanalizowana (`cache/bdl_research/kedzierzyn/`, poza repo). Pełne dane: `docs/bdl-paczki-rozpoznanie.md` (przepisana z realnymi liczbami).

**Kluczowe potwierdzenia na realnych danych (nie tylko schemat):**
- Skład gatunkowy z udziałami per piętro: **98,3% wydzieleń D-STAN ma >1 gatunek w warstwie `DRZEW`** (mediana ~6-8 gatunków), `part_cd_act`/`species_age` wypełnione w 100% wierszy. Gatunek `sp_rank_order_act=1` zgadza się w 100% (2681/2681) z `species_cd`/`part_cd` z `G_SUBAREA` (= WFS) — ranga 1 to dokładnie dzisiejsze "gatunek panujący".
- Podszyt (`PODSZ`) to potwierdzona, osobna warstwa (13 kodów w `f_storey_dic`: DRZEW, IP, IIP, NAL, PLANT, PODR, PODRII, PODS, **PODSZ**, PRZES, SAMOS, ZADRZEW, ZAKRZEW) — obecna dla **78% wydzieleń D-STAN**, z częściowo innym składem gatunkowym (CZM, BRZ, KRU, CZM.P, ŚW, DB, BK, JRZ, DB.C, OL — `KRU`/`JRZ` nie mają jeszcze wpisu w profilu).
- Zwarcie (`density_cd` na warstwie `DRZEW`): wypełnione dla 87,8% wydzieleń D-STAN.
- Typ gleby (`soil_subtype_cd`): wypełnione dla 98,7% wydzieleń D-STAN.
- **Join z `adr_for` zweryfikowany bajt-w-bajt** na tym samym realnym wydzieleniu co przykład z A4 (`02-10-1-05-317   -d   -00`, BK 4/10, LMW) — identyczny string w paczce i w `cache/bdl_tiles_v2` (WFS). Zero przetwarzania potrzebne do joina.
- Rozmiar: 1,26 MB spakowane / 4,9 MB rozpakowane dla jednego nadleśnictwa (4137 obiektów, 2676 D-STAN) — nieistotne obciążenie dla regionu domowego.
- Paczka to migawka (`metadane.txt`: dane wytworzone 2026-06-23), nie codziennie odświeżana jak WFS — brak API, tylko wniosek e-mail.
- Licencja (plik `warunki_wykorzystania.txt` w paczce, identyczny tekst co w formularzu wniosku): ustawa z 11.08.2021 o otwartych danych..., wymóg atrybucji + przekazywania w formie pierwotnej + informowania o przetworzeniu; brak zakazu komercyjnego.

**Rekomendacja zmieniona z warunkowej na: integrujemy w B2**, bez zastrzeżeń — dane są gęsto i realnie wypełnione, nie tylko strukturalnie udokumentowane. Zakres B2 (do osobnego planu): sparsować pełny skład `F_STOREY_SPECIES`/`DRZEW` per wydzielenie, zastąpić `unknown_host_affinity=0.5` realnym ważonym składem, fallback na dzisiejszy WFS dla wydzieleń bez paczki, decyzja co z podszytem (informacja na karcie vs. wpływ na H), harmonogram odświeżania paczek.

## 2026-09-24 — aktualne (16): B1 — rozpoznanie paczek BDL per nadleśnictwo (bez zmian w kodzie)

Zrealizowany krok B1 z planu 2.1 (`docs/projekt-borowik.md` §13.1, kryterium z §3.1 "Do sprawdzenia w pierwszej kolejności"). To rozpoznanie — `pipeline/` nie zostało dotknięte. Pełna notatka: `docs/bdl-paczki-rozpoznanie.md`.

**Wynik:** portal `bdl.lasy.gov.pl` udostępnia paczki per nadleśnictwo (SHP + TXT) z pełnym opisem taksacyjnym. Ze schematu danych (`OpisDanych.pdf`, pobrany bez logowania z publicznego linku na `/portal/o-udostepnianiu`, zapisany w `cache/bdl_research/` — poza repo): **`F_STOREY_SPECIES.part_cd_act`** daje pełny skład gatunkowy z udziałami **per piętro drzewostanu** (`F_AROD_STOREY.storey_cd`), **`F_AROD_STOREY.density_cd`** to zwarcie, **`F_SUBAREA.soil_subtype_cd`** to typ+podtyp gleby. `G_SUBAREA` ma pole `adr_for` identyczne z WFS (`pipeline/bdl.py`), więc join wygląda na bezpośredni. Podszyt jako osobna warstwa — prawdopodobne (wniosek pośredni z przykładu filtra w dokumentacji BDL, `storey_cd IN ('DRZEW','IP','IIP')` sugeruje istnienie innych kodów), nie potwierdzone literalnie.

**Licencja:** ustawa z 11.08.2021 o otwartych danych i ponownym wykorzystywaniu informacji sektora publicznego (Dz.U. 2021 poz. 1641, zm. 2022 poz. 1700) — obowiązek atrybucji źródła/daty, przekazywania dalej w formie pierwotnej, informowania o przetworzeniu; brak jawnego zakazu użytku komercyjnego w warunkach formularza.

**Pobranie wymaga formularza (e-mail + zgoda RODO), nie jest samoobsługowym plikiem do kliknięcia** — zgodnie z poleceniem zadania zatrzymałem się przed wysłaniem i zapytałem użytkownika. Użytkownik podał swój e-mail i zgodę; **wniosek złożony** dla Nadl. Kędzierzyn (RDLP Katowice, rok 2026, obszar testowy — `adr_for` prefiks `02-10-...` już widoczny w `cache/bdl_tiles_v2`). Portal potwierdził wysyłkę instrukcji pobrania na ten e-mail. **Nie mam dostępu do tej skrzynki** — sama zawartość paczki (rzeczywiste wypełnienie pól, format `adr_for`, rozmiar pliku) pozostaje niezweryfikowana; żaden plik z danymi nadleśnictwa nie został pobrany.

**Rekomendacja: warunkowo integrujemy w B2**, pod warunkiem potwierdzenia na realnej paczce, że `F_STOREY_SPECIES` faktycznie ma wypełniony skład gatunkowy dla więcej niż pojedynczych wydzieleń (dokumentacja opisuje strukturę, nie kompletność danych). To jedyne zidentyfikowane źródło mogące rozbić płaskowyż 745 wydzieleń z R ≥ 90 (§0.1) bez nowych zgadywanych wag.

**Następny krok (poza B1):** użytkownik sprawdza swoją skrzynkę, pobiera paczkę i przekazuje plik/link do dokończenia weryfikacji przed ostateczną decyzją B2.

## 2026-09-24 — aktualne (15): A4 — filtr małych wydzieleń + poprawka wyjaśnień S_host

Zrealizowany krok A4 z planu 2.1 (`docs/projekt-borowik.md` §13.1, opis §5.2 i §5.3 "Poprawka wyjaśnień").

**Część 1 — filtr < 0,5 ha:**
- Sprawdzone: powierzchnia nie była w eksporcie (`stands.geojson` ma tylko `stand_id`+geometrię; `scores_{day}.json` żadnego pola powierzchni). Dodane `area_ha` do `SCORE_FIELDS`/`build_score_record` (`pipeline/export.py`), liczone z geometrii EPSG:2180 (`geometry.area / 10000`) — to samo źródło co `pipeline.regions`' własne `area_ha`, nie pole BDL `sub_area` (nieużywane, potencjalnie nieaktualne). Pole zawsze obecne w nowych eksportach (nie jest maską, więc każde wydzielenie je dostaje).
- **Decyzja: próg w jednym miejscu frontendu (`MIN_STANDALONE_AREA_HA` w `frontend/src/model.ts`), nie w profilu YAML.** Uzasadnienie: to wartość czysto prezentacyjna, nigdy nie wchodzi do scoringu Pythona (H/F/R/rejony) — umieszczenie jej w profilu sugerowałoby, że wpływa na wynik, i wymagałoby dodatkowego pola eksportu tylko po to, żeby przenieść liczbę, której backend i tak nigdy nie używa.
- `frontend/src/model.ts`: `Score.area_ha?: number | null` (opcjonalne — **stare eksporty bez tego pola dalej się ładują**, `parseData` waliduje je tylko gdy obecne, tak jak istniejące `d_park_m`). Nowa `isStandaloneTarget(score)`: brak/`null` `area_ha` → nie ukrywaj (nieznana powierzchnia ≠ za mała).
- `frontend/src/main.ts`: `visibleEntries()` filtruje `isStandaloneTarget` **tylko w płaskiej liście "Wydzielenia"** (`!regionFilterId`) — przeglądanie członków konkretnego rejonu (`regionFilterId` ustawiony) pokazuje wszystkich członków bez filtra, zgodnie z wymaganiem "nadal liczą się w rejonach". Poprawione też liczniki w nagłówku/tytule mapy (`entries.length` → `visible.length`), które wcześniej pokazywałyby łączną liczbę nawet gdy lista poniżej jest przefiltrowana. Mapa (`setData`) pozostaje bez zmian — nadal pokazuje wszystkie poligony, zgodnie z istniejącą zasadą UI.

**Część 2 — poprawka wyjaśnień S_host (`pipeline/explain.py`):**
- Nowa `pipeline.habitat.host_affinity(species_cd, profile)` — surowe powinowactwo gatunku, wydzielone z `score_host` (który nadal blenduje je z neutralnym 0,5 wg `part_cd`). Bez tego `pipeline/explain.py` nie miał dostępu do samego powinowactwa, tylko do już wymieszanego S_host.
- `pipeline/mvp.py`: `meta` przekazywane do `generate_explanation` dostało `part_cd` i `host_affinity` (poprzednio brakowało obu).
- `pipeline/explain.py`: nowy szablon `host.down_low_share` + `_host_down_is_low_share(meta, profile)` — dla ujemnego wkładu "host" rozróżnia: gatunek panujący z powinowactwem ≥ 0,5 (neutralna wartość "nieznanej domieszki") przy `0 < part_cd < 10` → "gatunek panujący {sp} dobrze pasuje do borowika, ale stanowi tylko X/10 udziału (S_host=...)"; w przeciwnym razie (powinowactwo < 0,5, albo `part_cd == 10` czyli brak rozcieńczenia) → oryginalne "słabo pasuje". Przykład z audytu (BK 4/10, S_host=0,66) był dokładnie tym pierwszym przypadkiem — buk ma powinowactwo 0,9, więc "słabo pasuje" było mylące. Brak `part_cd`/`host_affinity` w `meta` (stare wywołania) → zachowanie bez zmian, bez wyjątku.

**Weryfikacja:** 280 testów Python (279→280, TDD na każdym kroku: `host_affinity`, `area_ha` w eksporcie, `_host_down_is_low_share` z osobnymi przypadkami BK-4/10 vs GB-10/10 vs DB.C-6/10 vs brak meta), 31 testów frontendu (29→31: `isStandaloneTarget`, walidacja opcjonalnego `area_ha` w `parseData`), `tsc --noEmit` i `vite build` bez błędów. **Ręczna weryfikacja w przeglądarce nie była możliwa w tej sesji** — połączona przeglądarka Chrome działa na innej maszynie niż lokalny dev-server (`127.0.0.1` po stronie przeglądarki nie wskazuje na ten komputer) — nie testowano wizualnie, tylko automatycznymi testami + build.

**Nie ruszono w tym kroku:** reszta planu 2.1 (B1–B3, C1, C3).

## 2026-09-24 — aktualne (14): A3 — pogoda liczona do dnia wyjazdu + porządki (C2)

Zrealizowany krok A3 z planu 2.1 (`docs/projekt-borowik.md` §13.1, opis §3.3 "Prognoza do dnia wyjazdu" i §5.4 "Zmiany w F"), plus przy okazji C2 (usunięcie martwych zmiennych pogodowych). Plan implementacji pokazany i zaakceptowany przez użytkownika przed pisaniem kodu.

**Przyczyna:** `--date` był tylko etykietą nazwy pliku — `pipeline/weather.py` zawsze pytał Open-Meteo o `forecast_days=1` (tylko dziś), a `pipeline/orchestrate.py` liczył percentyle klimatologii dla dnia roku `date.today()`, niezależnie od `--date`. Planując wyjazd za kilka dni użytkownik dostawał więc warunki "na teraz".

**Kluczowe ustalenie z kodu (bez którego zmiana byłaby dużo większa):** `pipeline.weather.compute_weather_features` już liczy każde okno jako `.iloc[-N:]` na chronologicznie posortowanym `daily_df` — czyli kończy się na *ostatnim* wierszu pobranych danych, jakikolwiek by nie był. Wystarczyło więc poprawnie ustawić `forecast_days`, żeby dzień wyjazdu był ostatnim pobranym dniem — P26w, CWB26, Tmean20, Tmean5, Tmin3 i wilgotność gleby dostały poprawne okno "za darmo", bez osobnej logiki "koniec okna".

**Zweryfikowane pojedynczym zapytaniem na żywo** (nie zgadywane, `api.open-meteo.com/v1/forecast`, NIE `archive-api` — limit dzienny archive API nadal wyczerpany, forecast API działa): `past_days=5, forecast_days=16` → 21 ciągłych dziennych wierszy, bez luki, bez NaN. Potwierdza, że `forecast_days` faktycznie steruje długością prognozy i że parsowanie odpowiedzi (`_parse_open_meteo_response`) nie wymaga zmian.

**Zmiany:**
- `pipeline/weather.py`: `_default_open_meteo_call`/`fetch_weather_raw` dostały parametr `forecast_days` (zamiast zahardkodowanego `1`). **Cache per punkt:** klucz (`_fetch_with_point_cache`'s `suffix`) zmieniony z `date.today().isoformat()` na `f"{date.today().isoformat()}_fd{forecast_days}"` — dwa przebiegi tego samego dnia z różnym `--date` (różnym `forecast_days`) nie dzielą już wpisu cache. **C2:** `compute_weather_features` przestała liczyć/zwracać `p1, p3, p7, p14, p21, p30, dry_spell_days` (martwa pętla `dry_mask`/`dry_spell` usunięta); zostały `p5` (kara upałowa), `p26w`, `cwb26`, `tmean5`, `tmean20`, `tmin3`, `days_since_p10` (tylko do banera, zgodnie z §5.4).
- `pipeline/orchestrate.py`: `run_poc(..., target_date=None)` — domyślnie dziś (bez zmian zachowania bez `--date`). `forecast_days = max(1, (target_date - dzis).days + 1)` przekazywane do `weather_fetcher`. Percentyle klimatologii liczone dla `target_date.timetuple().tm_yday`, nie `date.today()`. Nowa kolumna `stands["forecast_days"]` (stała dla całego przebiegu) i wpis w `diagnostics`.
- `pipeline/export.py`: `SCORE_FIELDS` += `forecast_days` — trafia do `scores_{day}.json` (pole "ile dni okna to prognoza" do przyszłego banera; UI pozostaje poza zakresem, zgodnie z zadaniem).
- `pipeline/prepare_trip.py`: **walidacja w `parse_args`** — `--date` w przeszłości albo dający `forecast_days > 16` → `parser.error(...)` z czytelnym komunikatem (**decyzja użytkownika: przerwij, bez cichego liczenia "na dziś"**). `main()` przekazuje sparsowaną datę jako `target_date` do `run_trip_preparation` → `run_poc`; usunięty nieaktualny już print `"Uwaga: prognoza pogody odzwierciedla dzisiejsze okno..."`.
- `notebooks/01_poc.py`, `notebooks/02_mvp.py`: drobna mechaniczna poprawka `_weather_call_api` (nowy parametr `forecast_days=1`), żeby nie zostały po cichu zepsute (nie są testowane, ale rzucałyby `TypeError` przy następnym ręcznym uruchomieniu).

**Testy (bez sieci, na sztucznej prognozie):** nowe testy w `tests/test_weather.py` (przekazywanie `forecast_days` do `call_api`; cache rozróżnia różne `forecast_days` tego samego dnia — dwa wywołania z tym samym `cache_dir`/punktami, różnym `forecast_days` → `call_api` wywołane dwa razy), `tests/test_orchestrate.py` (`run_poc` z `target_date` w przyszłości → `forecast_days` przekazane poprawnie i wyeksponowane per wydzielenie; percentyle klimatologii szukane dla dnia roku *daty wyjazdu* — syntetyczna klimatologia z sygnałem sezonowym tylko wokół dnia roku `target_date`, zamrożone "dziś" przez `monkeypatch` na `pipeline.orchestrate.date`, `empty_climatology_count == 0` dowodzi że użyto właściwego dnia roku), `tests/test_prepare_trip.py` (`parse_args` odrzuca datę w przeszłości i > 16 dni w przyszłości, akceptuje dokładnie na granicy 16 dni). 273 testy Python przechodzą (264→273, +9).

**Nie ruszono w tym kroku:** rejony (A2, zrobione), G_season/stałe okno sezonu (C3), frontendowy baner "X dni to prognoza" (pole w eksporcie gotowe, UI opcjonalne).

## 2026-09-24 — aktualne (13): A2 — przebudowa rejonów (kończy z jednym-rejonem-na-cały-las)

Zrealizowany krok A2 z planu 2.1 (`docs/projekt-borowik.md` §13.1, algorytm z §5.6 "Nowa definicja rejonu (2.1)", liczby z §0.1). Plan implementacji pokazany i zaakceptowany przez użytkownika przed pisaniem kodu (na wyraźną prośbę).

**Przyczyna:** algorytm 2.0 (`_assign_clusters`: bufor 250 m + `unary_union`) łączy łańcuchowo dowolnie długi ciąg sąsiadujących top-25% wydzieleń bez górnego ograniczenia rozmiaru — stąd rejon 1 = 4 747 wydzieleń / ~187 km² przy realnym przebiegu 25 km (§0.1).

**Zaproponowana i zaakceptowana uproszczona wersja algorytmu z §5.6** (zamiast przesuwnej siatki okien 1×1 km / przesunięcie 500 m): każdy kandydat (top ~5%, nie top 25%) jest potencjalnym "nasieniem" rejonu; `score(nasiono) = Σ(powierzchnia_ha × R_final)` po kandydatach, których **cała geometria** (nie tylko centroid) mieści się w kole o promieniu `radius_m` wokół centroidu nasiona; zachłanny wybór malejąco po `score`, odrzucając nasiona zbyt blisko (< `min_separation_m`) już przyjętego rejonu lub z sumą powierzchni < `min_area_ha`. Ponieważ każde okno ma tę samą powierzchnię, dzielenie przez nią w formule z §5.6 nie zmienia rankingu — więc to jest ten sam ranking bez kodu do wyrównywania siatki.

**Dwie poprawki znalezione dopiero przy weryfikacji na realnych danych (nie zgadywane, sprawdzone na cache):**
1. **Przynależność po centroidzie nie wystarcza.** Duże/wydłużone wydzielenia (do ~27 ha, własna przekątna do ~900 m w realnych danych) mają centroid blisko nasiona, ale poligon wystaje poza promień — dawało to rejony o prawdziwej średnicy >2 km mimo promienia 800 m. Naprawa: `pipeline.regions._region_members` wymaga, żeby **cała** geometria kandydata mieściła się w buforze wokół nasiona (`sindex.query(seed_buffer, predicate="contains")`), co z nierówności trójkąta gwarantuje średnicę rejonu ≤ `2 × radius_m` niezależnie od kształtu/rozmiaru pojedynczych wydzieleń.
2. **Odległość między rejonami trzeba sprawdzać po faktycznym centroidzie wybranego rejonu, nie po punkcie nasiona.** Test na syntetycznym ciągłym lesie (patrz niżej) złapał realne naruszenie progu 3 km (2861 m zamiast ≥3000 m) — członkostwo bywa asymetryczne (nasiono widzi sąsiadów tylko z jednej strony), więc faktyczny centroid unii dryfuje od punktu nasiona. Naprawa: sprawdzenie `min_separation_m` liczone jest na `summary["geometry"].centroid` już zbudowanego rejonu (dokładnie ten sam punkt, który potem zapisuje `write_regions_json` jako `centroid_lat/lon`), nie na surowym punkcie nasiona.

**Zmiany:**
- `pipeline/regions.py`: usunięty `_assign_clusters` (bufor + `unary_union`, źródło błędu 2.0). Nowe `_region_members` (przynależność przez pełną geometrię, nie centroid) i `_density_score`. `_summarize_cluster`/`select_candidates` bez zmian. `group_into_regions` przepisane na zachłanny wybór nasion opisany wyżej.
- `profiles/boletus_edulis.yaml` (`regions:`): `top_pct` 0,25→0,05; `buffer_m` usunięte, zastąpione `radius_m: 800.0` (gwarantuje średnicę ≤1600 m), nowe `min_area_ha: 5.0`, `min_separation_m: 3000.0`; `top_n_per_region`/`max_regions` bez zmian.
- `tests/test_regions.py`: usunięte 3 testy `_assign_clusters`; nowe testy `_region_members` (w tym test wprost odtwarzający błąd nr 1 — wydłużone wydzielenie z centroidem blisko, ale geometrią poza promieniem), odrzucenia po `min_area_ha`/`min_separation_m`; przepisane testy `group_into_regions` na jawne, lokalne nadpisania `regions:` (niezależne od strojonych domyślnych wartości); **wymagany test na syntetycznym ciągłym lesie** (siatka 31×31 wydzieleń, 6 km rozpiętości, wszystkie w masce z wysokim R) — potwierdza >1 rejon, żaden rejon nie obejmuje wszystkich kandydatów, prawdziwa średnica (convex hull, max odległość par punktów — nie przekątna bounding-boxa, bo ta zawyża i dała fałszywy alarm przy pierwszym podejściu z promieniem liczonym po centroidzie) ≤ 2000 m; ten sam test złapał błąd nr 2.

**Weryfikacja kryterium ukończenia** (bez nowego pobierania z sieci — użyty już zapisany na dysku wynik przebiegu 25 km, `notebooks/output/scores_2026-09-24.json` + `stands.geojson`, ten sam co audyt §0.1, przepuszczony przez prawdziwy `pipeline.regions.group_into_regions`): **5 rejonów**, prawdziwa średnica 1425–1536 m (≤2000 m), powierzchnia kandydatów 79,7–102,9 ha (≥5 ha), odległość między faktycznymi centroidami 3,28–25,3 km (≥3 km). Format `regions_{day}.json` sprawdzony przez `write_regions_json` — te same pola co wcześniej (`region_id, rank_score, stand_count, stand_ids, centroid_lat, centroid_lon, day`), frontend/`sync-data.mjs` bez zmian. 264 testy Python przechodzą (262→264).

**Nie ruszono w tym kroku:** pogoda, `--date` (A3) — zgodnie z zakresem zlecenia.

## 2026-09-24 — aktualne (12): A1 — kody siedlisk wyżynnych i gatunków w profilu

Zrealizowany krok A1 z planu 2.1 (`docs/projekt-borowik.md` §13.1, wartości z §5.3 "Uzupełnienie 2.1").

**Sprawdzenie przed zmianą (bez nowego pobierania z sieci — limit archive-api nadal wyczerpany):** wszystkie kody `site_type`/`species_cd` spoza profilu wypisane z `cache/bdl_tiles_v2` (30 kafli, 43 908 zdeduplikowanych wydzieleń). Kody siedlisk zgadzają się dokładnie z audytem §0.1 (`LWYZS` 899, `LWYZW` 822, `LMWYZW` 213, `LMWYZ` 170, `LLWYZ` 7, `OLJWYZ` 5, `BMWYZ` 1). Sprawdzone w źródłach zewnętrznych (encyklopedialesna/Wikipedia typologia siedlisk, nie zgadywane): dla „Las wyżynny” wilgotność to pojedyncza litera-sufiks (Ś/W), dla „Bór/Las mieszany wyżynny” brak sufiksu = świeży (domyślny), „W” = wilgotny — to wyjaśnia pozornie „obcięte” kody (np. `LWYZS` zamiast `LWYZSW`) i potwierdza mapowania z planu bez zmian.

Kody gatunków: znaleziono jeden kod spoza planu — `JB` (jarząb, 1 wydzielenie) — obok znanych z audytu (`DB.C` 110, `JW` 66, `SO.C` 31, `SO.WE` 12, `OL.S` 4, `WB` 2, `CZM.P` 2). Plan nazywał `CZM.P` tylko w kategorii zbiorczej „inne pojedyncze” (zakres 0,0–0,2, bez liczby) i nie wymieniał `JB` wcale — zgodnie z instrukcją użytkownika zapytano zamiast zgadywać. **Decyzja użytkownika:** `CZM.P` i `JB` → 0,0, do maski (jak `OL`/`JS`/`KL`/`WZ`/`AK` — rodzaje *Prunus*/*Sorbus* to mikoryza arbuskularna, nie ektomikoryza).

**Zmiany:**
- `profiles/boletus_edulis.yaml`: 7 kodów siedlisk wyżynnych w `site_scores` (wartości = odpowiednik nizinny tej samej żyzności/wilgotności, zgodnie z planem) i 8 kodów gatunków w `host_affinity` (`SO.C`/`SO.WE` 0,6; `DB.C` 0,4; `JW`/`OL.S`/`CZM.P`/`JB` 0,0; `WB` 0,1). `zero_affinity_mask_species` rozszerzone o `JW, OL.S, WB, CZM.P, JB` — zgodnie z jawną instrukcją zadania (`WB` ma niezerowe powinowactwo 0,1 jako domieszka, ale maskuje wydzielenie, gdy jest gatunkiem panującym ≥80%).
- `tests/test_profile_coverage.py`: `BDL_SITE_TYPES`/`BDL_SPECIES` rozszerzone o surowe (z polskimi znakami) formy nowych kodów — TDD: 15 nowych przypadków czerwone przed zmianą profilu, zielone po.

**Weryfikacja kryterium ukończenia** (bez nowego przebiegu sieciowego — ten sam limit): `unknown_site_count` i `unknown_species_count` policzone na realnym zbiorze z cache przez `pipeline.habitat.passes_mask` — **0 i 0 z 31 879 wydzieleń w masce (0,000%)**, dużo poniżej progu < 1%. 262 testy Python przechodzą (247 → 262: +15 nowych w tym kroku, reszta z prac między sesjami).

**Nie ruszono w tym kroku:** rejony (A2), pogoda/`--date` (A3) — zgodnie z zakresem zlecenia.

## 2026-09-24 — aktualne (11): audyt wyników i plan 2.1 (tylko dokumentacja, bez zmian w kodzie)

Audyt realnego eksportu 25 km (50.5318, 18.6055) opisany w `docs/projekt-borowik.md` sekcja 0.1. Nowa kolejność prac: sekcja 13.1 (A1–A4 naprawy, B1–B3 różnicowanie H, C1–C4 walidacja/porządki).

Kluczowe ustalenia: czołówka = wyłącznie SO na BMSW (745 wydzieleń z R ≥ 90), rejon 1 = 4 747 wydzieleń / ~187 km², ~2 300 wydzieleń na fallbacku 0,5 przez brakujące kody wyżynne (`LWYZS`, `LWYZW`, `LMWYZW`, `LMWYZ`…) i gatunki (`DB.C`, `JW`, `SO.C`…), `--date` nie wpływa na pogodę, confidence stałe.

Decyzje użytkownika: używa tylko na komputerze (hosting/telefon/PMTiles wycofane); routing i wejścia zamrożone; krawędzie lasu nie do H, najwyżej informacja na karcie. Następny krok: A1 (profil YAML), potem A2 (rejony).

## 2026-09-24 — aktualne (10): potwierdzone — dzienny limit archive-api.open-meteo.com wyczerpany

Użytkownik zgłosił, że klimatologia przestała pobierać dane. Sprawdzone bezpośrednim zapytaniem (`curl`), nie zgadywane:

```
archive-api.open-meteo.com: {"error":true,"reason":"Daily API request limit exceeded. Please try again tomorrow."}
api.open-meteo.com (bieżąca pogoda): HTTP 200 -- działa normalnie
```

To osobny, endpoint-specyficzny limit dzienny (nie globalny na cały Open-Meteo) — archive API (klimatologia) jest wyczerpane, forecast API (pogoda) nie. Brak publicznego dashboardu do sprawdzania zużycia z wyprzedzeniem na darmowym planie bez klucza API; jedyny sposób to próba na żywo. Reset "jutro" (prawdopodobnie północ UTC).

Prawdopodobna przyczyna: skumulowane zużycie z wielu przebiegów testowych tego samego dnia (sekcje (2)-(9) niżej) — nawet nieudane/częściowe przebiegi zużywały budżet archive API przed padnięciem na innym błędzie. Po dzisiejszych poprawkach (rzadsza siatka, mniejszy batch, skalowanie z promieniem) pojedynczy przyszły przebieg powinien zużywać znacznie mniej tego budżetu.

## 2026-09-24 — aktualne (9): rozdzielczość siatki pogody/klimatologii skalowana z promieniem

Pytanie użytkownika: przy `--radius-km 25` siatka pogody/klimatologii ma tę samą, stałą rozdzielczość co przy 15km — czy mniejszy promień nie mógłby "wykorzystać" tego samego budżetu punktów na mniejszym obszarze, czyli dostać dokładniejszą siatkę zamiast po prostu mniej punktów?

**Odpowiedź: tak, to miało sens.** `WEATHER_GRID_SPACING_M`/`CLIMATOLOGY_GRID_SPACING_M` (`pipeline/orchestrate.py`) są teraz zdefiniowane przy `REFERENCE_RADIUS_KM = 25.0` (domyślny promień CLI), a `pipeline.prepare_trip._radius_scaled_spacing` skaluje oba liniowo z rzeczywistym promieniem przed przekazaniem do `run_poc`.

**Zweryfikowane na prawdziwym `tile_bbox_2180`:**
```
radius=10km: pogoda 2.0km -> 144 pkt, klimatologia 8.0km -> 25 pkt
radius=15km: pogoda 3.0km -> 144 pkt, klimatologia 12.0km -> 16 pkt
radius=25km: pogoda 5.0km -> 144 pkt, klimatologia 20.0km -> 20 pkt
radius=50km: pogoda 10.0km -> 144 pkt, klimatologia 40.0km -> 20 pkt
```
Liczba punktów (czyli koszt API) zostaje w przybliżeniu stała w całym zakresie 10-50km, zamiast rosnąć z powierzchnią obszaru (dawniej: klimatologia rosłaby z 20 punktów przy 25km do ~80 przy 50km — 4x powierzchnia).

**Świadomy kompromis:** cache per-punkt (`_fetch_with_point_cache`) teraz pomaga między powtórzonymi przebiegami dla TEGO SAMEGO promienia/lokalizacji, ale nie między różnymi promieniami — inny odstęp siatki oznacza inne wyrównane punkty. Przebiegi przy stałym promieniu (typowy przypadek: iterowanie nad jedną lokalizacją/dniem) nie są tym dotknięte.

Printy postępu pokazują teraz też realny odstęp siatki: `"Siatka pogodowa: N punktow (odstep X.X km), ..."`. 247 testów Python przechodzi.

## 2026-09-24 — aktualne (8): OSM przestaje odpytywac Overpass po pierwszym błędzie kafla

Rozszerzenie poprzedniej zmiany (sekcja niżej) na wyraźną prośbę użytkownika: skoro jeden kafel OSM (po wyczerpaniu własnych prób w `_osm_call_api`) się nie uda, to Overpass albo sieć są w tym momencie niedostępne dla całego przebiegu — dalsze próby per kafel tylko dłużej biją w ten sam, już przeciążony publiczny serwer, bez realnej szansy powodzenia.

**Zmiana:** `fetch_cached_osm` w `pipeline/search_area.py` ma teraz flagę `give_up` — pierwsza nieudana próba ją ustawia, i każdy kolejny NIEZCACHOWANY kafel jest pomijany bez próby wywołania API (trafia od razu na listę `failed`). Kafle już w cache nadal są normalnie serwowane (nie wymagają sieci). Zastosowano tylko dla OSM, nie dla GDOS — użytkownik poprosił konkretnie o OSM; GDOS nadal próbuje każdy kafel osobno (ma już własny krótki retry, 3 próby/5s). Ta sama logika "poddaj się po pierwszym błędzie" dałaby się łatwo dodać też do GDOS, jeśli okaże się potrzebna.

245 testów Python przechodzi.

## 2026-09-24 — aktualne (7): błędy GDOS/OSM przestały być fatalne

Po dodaniu cache per-kafel (sekcja niżej) użytkownik odpalił `--radius-km 25` jeszcze raz. Pogoda i klimatologia: **100% z cache** (dowód, że wyrównanie siatki działa). GDOS doszło do kafla 18/30, potem `requests.exceptions.ConnectionError` (surowy `ProtocolError`, bez kodu HTTP w ogóle — inny rodzaj awarii niż 429/504 z Overpass). Użytkownik zapytał: czy GDOS jest w ogóle potrzebny i czy można pominąć nieudany kafel zamiast wywalać cały przebieg.

**Czy GDOS jest potrzebny:** tak — `gdos_blocked` (z `mark_gdos_blocked` w `pipeline/gdos.py`) bezpośrednio wchodzi do `mask_full = mask & ~gdos_blocked` w `pipeline/mvp.py`. To jest maska prawna (rezerwaty/parki narodowe), nie kosmetyka.

**Decyzja użytkownika o fallbacku:** wydzielenia z nieudanego kafla są traktowane jak brak ochrony (optymistycznie — tak jak dziś przy pustej odpowiedzi), ale **głośno**, nie po cichu — zgodnie z ustalonym wcześniej w tym projekcie zasadą "brak danych ≠ bezpiecznie" (patrz pierwotny brief projektu: "empty-ban-response ≠ no-ban"). Świadomy kompromis: więcej wyników, ale bez gwarancji pełnej weryfikacji prawnej w obszarze nieudanego kafla.

**Naprawa:**
- `pipeline/search_area.py::fetch_cached_gdos`/`fetch_cached_osm` łapią teraz wyjątek per-kafel, pomijają go (BEZ cachowania porażki — przejściowy błąd sieci ma być ponowiony przy następnym uruchomieniu, nie na stałe potraktowany jako "brak danych"), i zwracają dodatkową listę `failed`.
- `pipeline/prepare_trip.py` drukuje jawne `UWAGA:` z liczbą pominiętych kafli i czego to dotyczy (maska prawna dla GDOS, dokładność dystansu/popularności dla OSM), plus `gdos_failed_tile_count`/`osm_failed_tile_count` w zwracanym `summary`.
- GDOS dostał własny krótki retry (`_is_transient_network_error`, `_gdos_call_api`: 3 próby, 5s backoff) — wcześniej nie miał żadnego retry, w przeciwieństwie do Overpass/Open-Meteo. Brak udokumentowanej polityki limitów dla GDOS (w przeciwieństwie do Overpass/Open-Meteo), więc dopasowanie jest szerokie: dowolny `requests.exceptions.RequestException`.

Testy: przepisany test "błąd w późniejszym kaflu" (GDOS już nie jest fatalny, więc stara przesłanka testu była nieaktualna) na dwa: jeden potwierdza że błąd kafla GDOS nie przerywa przebiegu i jest raportowany, drugi że naprawdę fatalny błąd (teraz: `check_periodic_ban`) nadal chroni poprzedni eksport. Nowe testy cache/skip/retry dla obu funkcji cache. 243 testy Python przechodzą.

To już szósta iteracja poprawek z tego samego live-runu 25km, i pierwsza gdzie awaria NIE powinna już przerywać całego przebiegu — tylko obniżyć jego kompletność w konkretnym obszarze, z jawnym ostrzeżeniem.

## 2026-09-24 — aktualne (6): cache per-kafel dla GDOS i OSM + sprawdzone limity Overpass

Po naprawie 504 (sekcja niżej) użytkownik odpalił `--radius-km 25` jeszcze raz. Doszło dalej niż poprzednio, ale na kaflu 8/30 Overpass wyczerpał wszystkie 6 prób (429/504 na przemian, ~150s backoffu) i się poddał. Użytkownik poprosił: sprawdź dokładnie limity Overpass i czy warto dodać cachowanie.

**Sprawdzone limity (nie zgadywane):**
- `wiki.openstreetmap.org/wiki/Overpass_API`: <10000 zapytań/dzień i <1GB/dzień dla ręcznego użycia; **podzielone przez 100 dla regularnie uruchamianego skryptu** (~100/dzień, ~10MB/dzień) — nasz przebieg robi 30 zapytań OSM na jedno wywołanie, więc kilka wywołań dziennie już zbliża się do tego nieoficjalnego, ale zalecanego progu.
- `dev.overpass-api.de/overpass-doc/en/preface/commons.html`: publiczna instancja ma endpoint `GET /api/status` zwracający tekstowo `"Rate limit: N"` (dostępne sloty) w linii 3, a jeśli wszystkie sloty zajęte — od linii 6 czas do zwolnienia każdego slotu. To pozwoliłoby czekać dokładnie tyle ile trzeba zamiast ślepego retry — **rozważone i świadomie odłożone**: dodaje kolejne zapytanie do tego samego, przeciążonego serwera i wymaga parsowania tekstowego protokołu, przy niepewnej korzyści krańcowej ponad to, co daje cache.
- Ogólny wniosek: publiczna instancja overpass-api.de sama się opisuje jako przeciążona ("this server is overloaded... do not expect high reliability. Use alternatives if possible.") — retry z backoffem łagodzi, ale nie eliminuje ryzyka porażki dla pojedynczego kafla przy dużym obciążeniu serwera.

**Naprawa — cache per-kafel (główna dźwignia):** `pipeline/search_area.py` zyskuje `fetch_cached_gdos`/`fetch_cached_osm`, dokładnie ten sam wzorzec co istniejący cache BDL w `fetch_search_stands` (sprawdź plik → `(cache)`/`(WFS)`/`(Overpass)` w logu → pobierz i zapisz atomowo przy braku). OSM dodatkowo kluczowany hashem konfiguracji `profile["osm"]` (zapytanie zależy od tych ustawień). Efekt: **przebieg przerwany w połowie można uruchomić ponownie i wznowi się za kaflem, który już się udał** — nie trzeba od nowa bić w Overpass za wszystkie 30 kafli. Dwa nakładające się wyszukiwania (inny promień/środek) też reużywają dane GDOS/OSM dla wspólnych kafli, tak jak już działo się dla BDL.

Testy: nowe w `tests/test_search_area.py` (reużycie kafla, pobranie tylko nowego kafla przy częściowym pokryciu, osobny cache OSM per konfiguracja profilu). Istniejąca asercja "jedno wywołanie na kafel na przebieg" w teście integracyjnym promienia zaktualizowana — teraz sumaryczna liczba wywołań GDOS/OSM w dwóch nakładających się przebiegach równa się liczbie kafli WIĘKSZEGO promienia (mniejszy przebieg jest podzbiorem, więc jego kafle są reużyte z cache). 237 testów Python przechodzi.

**Nadal niezweryfikowane w pełni na żywo** — to piąta iteracja poprawek z tego samego live-runu 25km. Warto spróbować ponownie; teraz nawet gdyby znów padło na jakimś kaflu, ponowne uruchomienie powinno zacząć od miejsca przerwania, nie od zera.

## 2026-09-24 — aktualne (5): Overpass 504 — kolejny błąd z tego samego live-runu

Po naprawie 429 (sekcja niżej) użytkownik odpalił `--radius-km 25` jeszcze raz. Pogoda, klimatologia (z nowym cache per-punkt) i `run_poc` przeszły bez błędu. Ale na kaflu 1/30 GDOS/OSM: `requests.exceptions.HTTPError: 504 Server Error: Gateway Timeout` — inny kod błędu niż poprzednio (429), więc `_is_overpass_rate_limit` (dopasowywał tylko 429/406) go nie łapał i nie próbował ponownie.

**Sprawdzone źródło**: strona autora Overpass API (`olbricht.nrw/command_line.html`) wprost opisuje 504 jako "wysyłane gdy serwer ma już tak duże obciążenie, że nie może wykonać zapytania... w większości przypadków najlepiej spróbować ponownie później" — to udokumentowana sytuacja do retry, nie problem z kształtem naszego zapytania (to samo zapytanie działało wcześniej w izolowanym teście, patrz komentarz `routing_highway_types` w `profiles/boletus_edulis.yaml`).

**Naprawa**: `_is_overpass_rate_limit` przemianowane na `_is_overpass_retryable`, dopasowuje teraz też 504 (obok 429/406), z tym samym 30s backoff. Test `test_is_overpass_retryable_matches_429_406_and_504` w `tests/test_prepare_trip.py`. 233 testy Python przechodzą.

**To już czwarty błąd z rzędu wyłapany dopiero na żywym, pełnym przebiegu 25 km** (po dwóch Open-Meteo i pierwszym Overpass 429). Warto odpalić jeszcze raz — wejścia do lasu i eksport końcowy nadal nie zostały przetestowane na żywo w tym przebiegu.

## 2026-09-24 — aktualne (4): cache per-punkt dla pogody i klimatologii (nie tylko BDL)

Użytkownik zauważył: BDL ma widoczny cache per-kafel (`(cache)` w logach), a pogoda/klimatologia — mimo dwóch napraw wyżej — nie miały żadnego widocznego ani realnie reużywalnego cache między przebiegami.

**Dlaczego stary mechanizm nie działał:** `fetch_weather_raw`/`fetch_climatology_raw` miały tylko `requests_cache` (cache na poziomie pojedynczego zapytania HTTP). Dwa problemy: (1) `make_grid()` liczył punkty względem narożnika bboxa, który zależy od promienia/środka wyszukiwania — dwa nakładające się, ale różne wyszukiwania prawie nigdy nie dawały identycznych współrzędnych punktów; (2) nawet gdyby dawały, Open-Meteo batchuje wiele punktów w jedno zapytanie HTTP — jeden różniący się punkt unieważnia cache całej paczki.

**Naprawa:**
- `pipeline/weather.py::make_grid` — punkty wyrównane do stałej, absolutnej kraty w EPSG:2180 (wielokrotności `spacing_m` od początku układu), a nie względem narożnika bboxa. To ten sam trik co wyrównanie kafli 10km dla BDL w `pipeline/search_area.py`. Punkty mogą teraz wystawać do jednego `spacing_m` poza krawędź bboxa (nie są już przycinane do `n_max`/`e_max`).
- Nowe `_fetch_with_point_cache` w `pipeline/weather.py`: cache per-punkt na dysku (parquet), sprawdzany PRZED wywołaniem `call_api` — pobierane batchem są tylko brakujące punkty. Print w stylu BDL: `"N/M z cache, pobieranie K..."`.
- `fetch_weather_raw`/`fetch_climatology_raw` dostały opcjonalny `cache_dir` (podpięty pod istniejący `--cache-dir` z `prepare_trip.py`).
- **TTL pogody: do końca dnia** (decyzja użytkownika — klucz cache zawiera dzisiejszą datę ISO, więc jutro to automatycznie cache miss; pogoda to ruchome okno kończące się "teraz", wczorajszy cache dawałby nieaktualne "bieżące" warunki).
- **Klimatologia: bez wygasania** (30-letnie archiwum historyczne się nie zmienia, klucz cache nie zawiera daty).

Nowe testy w `tests/test_weather.py` (bez sieci): wyrównanie siatki (dwa nakładające się, ale przesunięte o wartość NIE będącą wielokrotnością `spacing_m` bboxy muszą dzielić punkty), reużycie cache między wywołaniami, pobieranie tylko nowych punktów przy częściowym pokryciu, wygaśnięcie cache pogody następnego dnia (zamockowane `date.today()`), brak wygaśnięcia dla klimatologii. 233 testy Python przechodzą.

## 2026-09-24 — aktualne (3): naprawa Overpass 429 — kolejny błąd z tego samego live-runu

Po dwóch naprawach Open-Meteo (sekcja niżej) użytkownik odpalił `--radius-km 25` ponownie. Pogoda i klimatologia **przeszły bez błędu** (dowód, że poprzednie dwie naprawy zadziałały). `run_poc` policzył 30120 wydzieleń. Ale przy pobieraniu OSM/Overpass per-kafel (30 kafli) pojawił się nowy błąd na kaflu 3/30: `requests.exceptions.HTTPError: 429 Client Error: Too Many Requests for url: https://overpass-api.de/api/interpreter`.

**Przyczyna:** `pipeline/osm.py::_default_overpass_call` robił gołe `requests.post` bez żadnego retry/backoff, a pętla w `run_trip_preparation` wywoływała go 30 razy pod rząd bez żadnej pauzy między zapytaniami.

**Sprawdzone źródło** (`wiki.openstreetmap.org/wiki/Overpass_API`, polityka użytkowania publicznej instancji overpass-api.de): *"If you receive an HTTP error code such as 429 or 406, pause for 30 seconds before making a new request."* Ta sama strona: limit "10000 zapytań/dzień, <1GB/dzień" dla ręcznego użycia, podzielony przez 100 dla regularnie uruchamianego skryptu (~100/dzień); zalecenie "cache and rate-limit calls", "avoid running multiple scripts in parallel".

**Naprawa:** `pipeline/prepare_trip.py::_rate_limited` uogólniony z twardo wpisanego `except OpenMeteoRequestsError` na parametr `should_retry` (predykat). Dodano `_is_overpass_rate_limit` (429/406) obok przemianowanego `_is_open_meteo_rate_limit` (który teraz też explicite wyklucza komunikat "too much data" — to nie jest błąd przejściowy, retry nic by nie dał). Overpass dostaje 30s backoff (z dokumentacji) + lekkie 1s pacing między kaflami (niepotwierdzone w dokumentacji, defensywne). Nowe testy jednostkowe dla `_rate_limited`/obu predykatów w `tests/test_prepare_trip.py` (bez sieci, `time.sleep` zamockowany).

**Nadal niezweryfikowane na żywo w całości** — to jest trzeci błąd z rzędu wyłapany dopiero na żywym, pełnym przebiegu 25 km; nie wiadomo, czy po tej poprawce cały przebieg (GDOS, wejścia do lasu, eksport) dojdzie do końca bez kolejnej niespodzianki. Warto odpalić jeszcze raz.

## 2026-09-24 — aktualne (2): druga naprawa Open-Meteo — limit danych na zapytanie (klimatologia)

Ta notatka **zastępuje** poniższą co do stanu limitu Open-Meteo. Batching (opisany niżej) naprawił błąd limitu liczby zapytań, ale przy ponownym uruchomieniu `--radius-km 25` przez użytkownika ujawnił się **inny, nowy błąd**: `OpenMeteoRequestsError: Your API call requests too much data. Please reduce the number of variables, locations and/or weather models.` — to osobny, natychmiastowy błąd limitu **objętości danych na pojedyncze zapytanie**, nie limitu licznika zapytań.

**Sprawdzone źródła (nie zgadywane):**
- `open-meteo.com/en/pricing` (źródło pierwotne): darmowy plan = 600/min, 5000/godz., 10000/dzień, 300000/mies. Cytat: *"Requests for data covering more than 10 weather variables or extending over a period of more than 2 weeks for a single location are considered multiple API calls."* Przykład: 2 tygodnie + 15 zmiennych = 1,5 "wywołania".
- Oficjalna dokumentacja **nie podaje** dokładnego wzoru łączącego lokalizacje × dni × zmienne — [GitHub issue #485](https://github.com/open-meteo/open-meteo/issues/485) potwierdza, że użytkownicy Open-Meteo też się tego domagają i nie dostali odpowiedzi.
- Najbliższe półoficjalne źródło: blog Open-Meteo na Substacku (`openmeteo.substack.com/p/weather-data-for-multiple-locations`) podaje wzór wagowy: `weight = nLokalizacji × (nDni / 14) × (nZmiennych / 10)`.
- Wyliczenie dla naszego przypadku: klimatologia pyta o 30 lat (~10950 dni) × 3 zmienne (2 daily + 1 hourly) → waga **jednego punktu** ≈ (10950/14) × (3/10) ≈ **235**. Batch 50 punktów w jednym zapytaniu (rozmiar użyty wcześniej dla lżejszego zapytania o bieżącą pogodę) → waga ≈ 50 × 235 ≈ **11750** w jednym zapytaniu — to właśnie padło z błędem „too much data" na żywo.

**Naprawa (dwie niezależne warstwy):**
1. `pipeline/orchestrate.py`: klimatologia jest teraz pobierana na **osobnej, rzadszej siatce** niż bieżąca pogoda (`CLIMATOLOGY_GRID_SPACING_M = 20000` m, vs `grid_spacing_m = 5000` m domyślnie dla pogody) — klimatologia zmienia się przestrzennie znacznie wolniej niż bieżąca pogoda, więc redukcja rozdzielczości ~10x jest uzasadniona merytorycznie, nie tylko jako obejście limitu. Każda komórka pogodowa mapowana jest na najbliższy punkt klimatologiczny przez `_nearest_climatology_cell` (`gpd.sjoin_nearest`, ten sam wzorzec co `pipeline/validate.py`). Cache percentyli (`percentiles_by_cell`) kluczowany jest teraz po (rzadszej) komórce klimatologicznej, więc więcej wydzieleń dzieli ten sam wynik.
2. `pipeline/weather.py`: nowa, mniejsza stała `_OPEN_METEO_CLIMATOLOGY_BATCH_SIZE = 10` (osobna od `_OPEN_METEO_BATCH_SIZE = 50` używanej dla bieżącej pogody) — dodatkowy margines bezpieczeństwa niezależny od redukcji siatki, żeby żadne pojedyncze zapytanie nie zbliżało się do zaobserwowanej granicy awarii (~11750 wagi).
3. `pipeline/prepare_trip.py`: dopisany print rozmiaru siatki klimatologii obok istniejącego printu siatki pogodowej.

**Nadal niezweryfikowane na żywo**: limit dzienny/godzinowy darmowego planu był wyczerpany w momencie commitu, więc pełne `--radius-km 25` (a tym bardziej maksymalne 50 km) nie zostało ponownie uruchomione po tej poprawce. Wyliczenia wagi (patrz wyżej) sugerują, że przy nowych ustawieniach domyślnych mieści się to bezpiecznie w limitach, ale to wciąż wyliczenie na podstawie półoficjalnego wzoru, nie potwierdzenie z realnego przebiegu.

Testy: `tests/test_orchestrate.py` — dwa nowe testy (`test_run_poc_fetches_climatology_on_a_coarser_grid_than_weather`, `test_run_poc_defaults_climatology_grid_coarser_than_weather_grid`) potwierdzają mniejszą liczbę punktów klimatologii niż pogody. 222 testy Python przechodzą.

Przy okazji odkryto i skomitowano **trzeci przypadek** nigdy niezakomitowanej pracy Codexa: `pipeline/search_area.py` (cały moduł promienia wyszukiwania — `search_tiles`/`merge_frames`/`within_radius`/`fetch_search_stands`, od którego zależy `prepare_trip.py` i `tests/test_search_area.py`) był plikiem `??` (nieśledzonym) mimo że testy go używające były już zacommitowane. Podobnie `pipeline/export.py` (pole `d_park_m`, `export_stand_geometries_geojson`) i poprawki `pipeline/rdlp.py` (`.covers()` zamiast `.contains()`, poprawne CRS dla przecięcia bbox) — wszystko opisane w sekcji „Promień" niżej, ale nigdy niezacommitowane. Teraz w git.

## 2026-09-24 — aktualne: grupowanie przywrócone, przełącznik Rejony/Wydzielenia w UI, naprawiony limit Open-Meteo (częściowo — patrz sekcja wyżej)

Ta notatka **zastępuje** poniższą sekcję „grupowanie wyłączone" — użytkownik ponownie poprosił o widok rejonów, więc grupowanie wróciło do aktywnego przepływu. Sekcja poniżej (o wyłączeniu) pozostaje jako historia decyzji, nie jako aktualny stan.

### Limit Open-Meteo (błąd zgłoszony przez użytkownika na żywo)

Przy `--radius-km 25` pojawiał się `OpenMeteoRequestsError: Hourly API request limit exceeded`. Przyczyna: `fetch_weather_raw`/`fetch_climatology_raw` w `pipeline/weather.py` wysyłały **jedno zapytanie HTTP na każdy punkt siatki** zamiast batchować.

- Naprawiono: `_default_open_meteo_call`/`_default_climatology_call` przyjmują teraz listę punktów `(lat, lon)` i zwracają listę odpowiedzi, z zapytaniem współdzielonym (przecinkowe listy `latitude`/`longitude`) w porcjach po `_OPEN_METEO_BATCH_SIZE = 50` (wartość ostrożna, nie zweryfikowana na realnym dużym batchu — limit API wciąż był wyczerpany w momencie commitu).
- `pipeline/prepare_trip.py`, `notebooks/01_poc.py`, `notebooks/02_mvp.py`: zamknięcia `_weather_call_api`/`_climatology_call_api` zaktualizowane pod nowy podpis.
- Testy: `tests/test_weather.py` — nowe testy batchowania (wszystkie punkty w jednym wywołaniu `call_api`, obsługa pojedynczego punktu).
- **Nie zweryfikowano na żywo** ponownego uruchomienia `--radius-km 25` po naprawie — limit godzinny był nadal wyczerpany. Warto przetestować po zresetowaniu limitu.

### Grupowanie w rejony — przywrócone

- `pipeline/prepare_trip.py`: `run_trip_preparation` ponownie woła `group_into_regions` i `write_regions_json` po `enrich_with_mvp_layers`; `region_count`/`regions_path` znów są w podsumowaniu CLI.
- `pipeline/regions.py`, `pipeline/export.py` (`build_region_record`, `REGION_FIELDS`) nie były zmieniane — po prostu podłączone z powrotem do wywołania.
- `frontend/scripts/sync-data.mjs`: opcjonalna synchronizacja `regions_{day}.json` z tą samą datą co `scores`/`stands`, z walidacją transakcyjną (`stand_ids` każdego rejonu musi być podzbiorem zsynchronizowanych geometrii) przed podmianą plików docelowych; usuwa nieaktualny `regions.json`, gdy najnowszy eksport nie ma rejonów.
- `tests/test_search_area.py`: zdjęto asercję „grupowanie musi być wyłączone" (była specyficzna dla poprzedniej decyzji), dodano pozytywne sprawdzenie spójności `regions_path`/`region_count`.

### Frontend: przełącznik Rejony / Wydzielenia

- `frontend/src/model.ts`: typy `Region`/`RegionView`, `joinRegions(regions, entries)` (łączy rejon z jego wydzieleniami-członkami, `top` = człon z najwyższym R). `parseData`/`loadData` przyjmują opcjonalny `regions.json` — brak pliku lub sieciowy błąd fetch = pusty widok rejonów (nie błąd), ale plik obecny i niepoprawny = błąd.
- `frontend/src/map.ts`: dodane metody `selectGroup`/`highlightGroup`/`focusStands` (addytywnie, nie ruszały istniejących `select`/`highlight`/`focusStand` — ten plik nie ma testów, WebGL).
- `frontend/src/main.ts`: segmentowy przełącznik „Rejony” / „Wydzielenia” obok nawigacji Odkrywaj/Zapisane. Zapamiętuje wybór w `localStorage` (`borowik.view-mode.v1`); domyślnie Rejony przy pierwszej wizycie, jeśli `regions.json` ma jakiekolwiek rejony, inaczej Wydzielenia. „Zobacz wydzielenia w rejonie” filtruje istniejący widok listy/mapy do `stand_ids` danego rejonu (ten sam komponent karty/szczegółów co dotychczas), z linkiem powrotnym. Mapa pokazuje **cały** zestaw wydzieleń niezależnie od trybu (`setData` się nie zmienia) — tryb wpływa tylko na to, co jest podświetlone/przypięte (`select` dla jednego wydzielenia vs `selectGroup` dla członków rejonu).
- Weryfikacja: 29 testów frontendowych, `tsc --noEmit` + `vite build` bez błędów, ręczna kontrola w przeglądarce (Chrome, przez claude-in-chrome) — przełączanie Rejony↔Wydzielenia, wejście w rejon i powrót, kliknięcie na mapie w trybie rejonów przewija do właściwej karty rejonu. 220 testów Python.
- Wcześniej frontend (poza kilkoma plikami dotkniętymi przy innych commitach) **nie był w ogóle w git** — `package.json`, `index.html`, `tsconfig.json`, `storage.ts`, `README.md`, `IMPLEMENTATION.md`, `.gitignore` istniały tylko na dysku od czasu, gdy Codex je zbudował. Skomitowane teraz osobnym commitem przed commitem przełącznika.

## 2026-09-24 — grupowanie wyłączone na życzenie użytkownika (zastąpione powyżej)

Ta decyzja zastępuje wcześniejszy projekt widoku rejonów. Główny wynik to pojedyncze wydzielenia.

- `pipeline/prepare_trip.py` i `notebooks/02_mvp.py` nie wywołują grupowania ani eksportu rejonów. CLI nie zwraca `region_count/regions_path`. Scoring i filtry pozostają bez zmian.
- `pipeline/regions.py`, jego testy, ustawienia profilu i stare eksporty pozostawiono do ewentualnego przywrócenia; nie są używane w aktywnym przepływie.
- Frontend pobiera tylko oceny i geometrie. Synchronizacja wybiera najnowszy `scores_YYYY-MM-DD.json`, kontroluje ID w `stands.geojson` i ignoruje pliki rejonów (nawet nowsze/uszkodzone).
- Lista obejmuje każde wydzielenie z `mask=true` i skończonym R, również niskim/zerowym. Sortowanie malejąco R, potem ID. Strony po 30 pozycji; mapa obejmuje wszystkie kwalifikujące się poligony.
- Karty, szczegóły, zapis i współrzędne nawigacji dotyczą konkretnego wydzielenia. Mapa nie sumuje geometrii; jeden znacznik wyboru. Zmiana wyboru nie przesyła ponownie całego GeoJSON. Usunięto zależności Turf.
- Schemat zapisów `borowik.saved-regions.v1` zachowano, aby nie utracić zapisanych wcześniej rejonów. Nowe tytuły zawierają ID wydzielenia.
- Zsynchronizowano istniejący eksport użytkownika: 1189 wydzieleń, 820 kwalifikuje się do rankingu. Bez nowej analizy sieciowej.
- Weryfikacja: 218 testów Python, 20 testów frontendu i poprawny build produkcyjny. W przeglądarce sprawdzono 820 wyników, szczegóły, drugą stronę listy i mapę osobnych poligonów; konsola bez błędów. Pozostają wcześniejsze ostrzeżenia testu CRS i rozmiaru bundla MapLibre.

Więcej widocznych wydzieleń nie oznacza pełnej weryfikacji zakazów/wejść: nadal sprawdzane są dla top-N. Ograniczenia danych opisane poniżej obowiązują.

## 2026-09-24 — frontend i rzeczywisty promień analizy

Prace wykonano w `.claude/worktrees/borowik-faza2-mvp-backend`, nie na starszym `master` w nadrzędnym katalogu. Zmiany pozostają w katalogu roboczym; niniejsza notatka nie oznacza scalenia ani utworzenia commita.

### Frontend (wcześniejszy etap)

- `frontend/`: Vite + TypeScript + MapLibre + Turf, na podstawie `docs/superpowers/specs/2026-09-24-borowik-frontend-design.md`.
- Karty i obrysy rejonów, panel wydzieleń, klasy F, H, pewność i powody, zapis lokalny i Google Maps, układ mobilny, obsługa błędów/pustych wyników.
- `pipeline/export.py`: `export_stand_geometries_geojson` (EPSG:4326) i `d_park_m` w wynikach. `prepare_trip` eksportuje GeoJSON obok GeoParquet.
- `frontend/scripts/sync-data.mjs`: kontrolowana synchronizacja jednego kompletnego zestawu wyników.
- Sprawdzone: 19 testów JS, budowanie produkcyjne i ręczna kontrola w przeglądarce, w tym 390 px i zapis po odświeżeniu. Backend przed zmianą promienia: 207 testów.
- Szczegółowe uwagi: `frontend/README.md` i `frontend/IMPLEMENTATION.md`. Punkty orientacyjne nie są współrzędnymi wejść. Zapis lokalny nie jest PWA/offline. Stare wyniki nie zyskują automatycznie odległości.

### Promień — zmiana zlecona przez użytkownika

**Problem:** `--radius-km` przyjmował 10–50 km (domyślnie 25), ale był usuwany przez `del radius_km`. Faktycznie przetwarzano jeden kwadrat 10×10 km. Teraz parametr rzeczywiście steruje obszarem.

- Nowy `pipeline/search_area.py`: siatka kafli 10 km wyrównana do EPSG:2180, wybór kafli przecinających koło przez dokładny dystans punkt–prostokąt; brak przybliżonego bufora koła.
- Wydzielenie należy do analizy, jeśli **centroid jego pełnego poligonu leży w promieniu** od punktu w EPSG:2180. Geometrii nie przycinamy; skraj poligonu może wystawać poza koło. To promień przestrzenny, nie dystans jazdy.
- BDL pobierany z **każdej RDLP przecinającej każdy kafel**, nie wyłącznie dyrekcji punktu centralnego. Deduplikacja `adr_for + a_year` przed scoringiem.
- Nowy cache `cache/bdl_tiles_v2/<sha256-warstwy[:16]>/E…N…S10000.parquet`, zapis przez plik tymczasowy i replace. Nie używamy starego cache kafli centrowanych: brakowało w nim wiarygodnego klucza warstwy/siatki. Stare pliki pozostawiono.
- GDOŚ i OSM są pobierane osobno per kafel (zamiast jednego wielkiego zapytania), łączone i deduplikowane przed wzbogaceniem wyników. Powtarzające się miejscowości nie zwiększają sztucznie popytu. Deduplikacja OSM uwzględnia ID i geometrię, zachowując różne punkty node/way z tym samym numerem.
- Scoring, normalizacja presji, top-N routing/zakazy i grupowanie są wspólne dla całego obszaru. Brak rankingu normalizowanego osobno w każdym kaflu.
- Granica lasu do wykrywania wejść korzysta ze wszystkich pobranych drzewostanów, przed filtrem promienia, żeby brzeg koła nie tworzył fałszywych wejść.
- `pipeline/orchestrate.py`: klimatologia grupowana per komórka, percentyle liczone raz per komórka zamiast ponownego skanowania całego archiwum dla każdego wydzielenia. Formuły scoringu niezmienione.
- `pipeline/rdlp.py`: poprawne przeliczanie CRS w przecięciu z bbox; `covers` dla lokalizacji dokładnie na granicy.
- Walidacja skończonych współrzędnych WGS84; postęp BDL, pogody, klimatologii i GDOŚ/OSM. Podsumowanie ma `radius_km`, `tile_count`, `layers`; dawne pojedyncze `tile_id` usunięto (brak odbiorców poza dawnym kodem CLI).

### Testy i zakres weryfikacji promienia

Końcowy wynik: **218 passed**, jedno istniejące ostrzeżenie `test_validate` o `sjoin_nearest` w geograficznym CRS. Polecenie: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`. Testy nie wymagają sieci. `git diff --check` bez błędów białych znaków.

`tests/test_search_area.py`: pokrycie koła, stała siatka, rzeczywisty filtr promienia, zachowanie pełnych poligonów, dwie RDLP, deduplikacja, cache, błędy źródeł, walidacja wejścia i pełny przepływ dla 10/20 km z eksportem JSON/GeoJSON/Parquet. W integracji podmieniono wyłącznie zewnętrzne źródła; scoring, wzbogacanie, grupowanie i eksport są rzeczywiste.

Testy nie uruchamiają dużego pobierania sieciowego. Nie wykonano pełnej analizy 25–50 km na żywych serwisach i nie podmieniono istniejących wyników użytkownika. Nadal obowiązują limity API; pierwsza duża analiza może być długotrwała i pamięciochłonna. Frontend używa nadal zwykłego GeoJSON, co przy 50 km może wymagać późniejszego PMTiles.

### Uruchomienie użytkownika (PowerShell)

```powershell
cd C:\Users\<uzytkownik>\Documents\Grzyby\.claude\worktrees\borowik-faza2-mvp-backend
& .\.venv\Scripts\python.exe -m pipeline.prepare_trip --lat 50.5318 --lon 18.6055 --radius-km 25
cd frontend
npm.cmd run sync-data
# Odśwież działający frontend albo uruchom:
npm.cmd run dev
```

### Nadal otwarte / nie zmieniono w tej iteracji

- `--date` pozostaje etykietą eksportu; pogoda jest bieżąca, G_season nadal stałe 1.
- Zakazy sprawdzane dla top 50, routing dla top-N z profilu — globalnie, nie dla wszystkich wydzieleń dużego obszaru. Nie deklarować pełnej weryfikacji prawnej rejonu.
- Brak danych BDL dla lasów spoza pokrycia źródła; centrum poza RDLP odrzucane jak wcześniej. Brzeg obszaru pobrania może nadal ograniczać kontekst wejść/dróg.
- Cache BDL sprawdza istnienie pliku, nie wiek danych; brak nowej polityki odświeżania.
- Awaria źródła przerywa analizę, zanim zacznie się eksport. Sam zestaw plików nie ma jeszcze transakcyjnego manifestu publikacji (awaria dysku podczas eksportu może wymagać ponownego uruchomienia).
- Brak serwera uruchamiającego Python z przeglądarki, brak nowych suwaków w UI, brak hostingu i pełnego trybu offline.
- Nie zmieniać historycznych planów tak, jakby wcześniej obejmowały tę implementację. Aktualizacje stanu znajdują się tutaj oraz na początku `docs/projekt-borowik.md`.

## Faza 3 (presja v2: punkty dostępu) — stan z 2026-09-29, gałąź `ulepszenia-faza3`

Raport i liczby: `docs/RAPORT_FAZA_3.md`, materiały: `docs/porownania/faza3/`. Skrót dla kolejnej sesji:
- `pressure.model: access_points` (domyślny w profilu) liczy P z punktów dostępu (`pipeline/access_*.py`); `pressure.model: gravity` przywraca stary model. Kolumna `pressure_model` i manifest (`pressure_model_used`) mówią, który zadecydował; brak jakichkolwiek punktów dostępu = powrót do gravity z komunikatem.
- Źródła: ArcGIS WFS BDL (turystyczny: kody `PARKING`, `MSC POST`; dojazdy pożarowe) i osobne zapytanie Overpass (drogi z tagami nawierzchni, szlabany), cache w `cache/access_tiles/`. Główny WFS BDL tych warstw nie ma; ArcGIS zwraca cp1250 zamiast UTF‑8; BBOX w kolejności N,E.
- BDOT10k (`OT_SKDR_L`) i relacje `route=bicycle` NIE są zaimplementowane (BLOCKED, patrz raport).
- `saturation_s: 7.0` i wszystkie `pressure.access_points.*` to nieskalibrowana hipoteza. Zasięg poprzeczny dróg leśnych 0,3 km i tak obejmuje ~95% lasu Kieleczki, więc korytarze prawie nie różnicują wydzieleń.
- Testy integracyjne `run_trip_preparation` muszą mockować `pipeline.prepare_trip._default_bdl_get` i `_default_overpass_call` (patrz `configure_sources` w `tests/test_search_area.py`), inaczej wychodzą do sieci.
- Pełny przebieg `prepare_trip` z modelem `access_points` na żywych danych pogodowych jeszcze nie był uruchomiony (raport liczono offline z cache i wyników 1.6).
- Faza 3, ciąg dalszy: `population_split: huff` (domyślny; ludność oczka dzielona między punkty samochodowe), `saturation_s` jest słownikiem `{huff, none}` (osobne S do tej samej mediany P). W huff osiedla dominują presję (45%), bo `a_half` typów samochodowych nie był ponownie dobrany — decyzja właściciela. Rebase na `master` po scaleniu Fazy 2 nadal do zrobienia. Szczegóły: `docs/RAPORT_FAZA_3.md` („Ciąg dalszy”).
- Faza 3, rebase i `huff_all` (2026-09-29): `ulepszenia-faza3` jest po rebase na `master` (Faza 2 i `ulepszenia-wiek` scalone). Domyślne `population_split: huff_all` (jednolity Huff z opcją zewnętrzną `external_option_c`, A w osobach, waga typu tylko w podziale, `saturation_s.huff_all`) — **wyzerowuje wpływ osiedli** (mediana A osiedla 0,75 osoby, bo oczko dzieli ludność między ~300 punktów); diagnoza i warianty naprawy w `docs/RAPORT_FAZA_3.md` („Ciąg dalszy 2”). Do decyzji właściciela przed kalibracją. `huff` i `none` dostępne przez profil. `junction` bez zmian do ręcznej kontroli.
- Faza 3, `two_stage` (2026-09-29): domyślne `population_split: two_stage` (etap 1: pieszo `p_walk_max·max(0,1−d_las/1,5 km)` reszta autem; etap 2: pieszo między osiedla bez c, autem jak `huff_all` z c). `saturation_s.two_stage` = 1997. Kryterium sensowności ustalone z góry: (a) spełnione, (b) niespełnione tylko w pasie > 5 km od osiedla przy Lublińcu (0,45 vs 0,35; 118 wydzieleń), stabilność top-20 min. 16/20. Zgodnie z decyzją właściciela NIE robiono przebiegu na żywo ani migawki i nie próbowano kolejnych wariantów. Szczegóły: `docs/RAPORT_FAZA_3.md` („Ciąg dalszy 3”). `two_stage` wymaga `pop_d_forest` w `build_access_model` (liczy je `pipeline.prepare_trip`).
- Faza 3 zamknięta (2026-09-29): `two_stage` zaakceptowany po kontroli pasa > 5 km (kryterium (b) uznane przez właściciela za źle zdefiniowane po obejrzeniu wyników — zapisane w raporcie jako zmiana oceny; kontrola: 118/118 wydzieleń ma główny punkt presji ≤ 2,5 km). `junction` do decyzji po ręcznej kontroli, BDOT10k i `route=bicycle` BLOCKED. Sekcja „Decyzje” w `docs/RAPORT_FAZA_3.md`.
