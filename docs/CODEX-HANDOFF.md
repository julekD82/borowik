# Notatki przekazania dla Claude Code

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

