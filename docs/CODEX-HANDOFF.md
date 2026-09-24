# Notatki przekazania dla Claude Code

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

