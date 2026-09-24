# Notatki przekazania dla Claude Code

## 2026-09-24 — aktualne: grupowanie przywrócone, przełącznik Rejony/Wydzielenia w UI, naprawiony limit Open-Meteo

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

