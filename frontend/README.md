# Borowik — frontend

Lokalna, statyczna aplikacja według `docs/archiwum/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md`: Preact, TypeScript, Vite i MapLibre. Nie ma serwera API; interfejs czyta pliki przygotowane przez `pipeline.prepare_trip`.

## Uruchomienie

W katalogu głównym repozytorium:

```powershell
# Nowa analiza — wymaga dostępu do źródeł danych. Nie jest potrzebna,
# jeżeli chcesz obejrzeć już przygotowane i zsynchronizowane wyniki.
& .\.venv\Scripts\python.exe -m pipeline.prepare_trip --lat 53.1509 --lon 16.7382

Set-Location frontend
npm.cmd ci
npm.cmd run sync-data
npm.cmd run dev
```

Otwórz adres podany przez Vite (domyślnie http://127.0.0.1:5173). Serwer nasłuchuje lokalnie. Żeby otworzyć aplikację na innym komputerze lub telefonie w tej samej sieci, zaznacz w launcherze „Udostępnij w sieci lokalnej” (ustawienie jest zapamiętywane) i uruchom serwer od nowa; launcher wypisze adres w sieci (np. `http://192.168.18.7:5173`; działa adres IP, nazwa komputera nie). Robi to skrypt `npm run dev:lan` (`vite --host 0.0.0.0`). Serwer nie ma hasła, więc używaj go tylko w zaufanej sieci; przy pierwszym uruchomieniu Windows może zapytać o zaporę — zezwól Node.js dla sieci prywatnej. Grupowanie w rejony jest aktywne: przełącznik „Rejony” / „Wydzielenia” nad listą/mapą (zapamiętywany w `localStorage`) pokazuje domyślnie rejony, gdy analiza je ma, z opcją przejścia do pojedynczych wydzieleń. Nie trzeba przeliczać istniejącej analizy — wystarczy synchronizacja ocen i geometrii.

Powyższe polecenia są dla PowerShell. Nazwa modułu to dokładnie `pipeline.prepare_trip`, bez ukośnika przed `_`.

Wymagany Node.js >=22.12 (sprawdzono Node 24). `npm run build` sprawdza TypeScript i tworzy `dist/`; `npm run preview` wyświetla wersję produkcyjną. Hosting jest poza zakresem tej iteracji.

## Synchronizacja danych

Promień nowej analizy rzeczywiście działa: dodaj do polecenia Pythona `--radius-km 25` (domyślnie 25 km, zakres 10–50 km). Analiza obejmuje wydzielenia ze środkiem w kole o podanym promieniu. Większy promień oznacza więcej pobrań i dłuższe pierwsze uruchomienie. Zmiana promienia wymaga nowej analizy i ponownego `sync-data`; przesuwanie lub oddalanie mapy nie rozszerza danych. Stan backendu i instrukcje dla Claude Code: `../docs/archiwum/CODEX-HANDOFF.md`.

`npm run sync-data` kopiuje z `../notebooks/output/` do `public/data/`:

- najnowszy `scores_YYYY-MM-DD.json` → `scores.json`,
- `stands.geojson` w EPSG:4326 → `stands.geojson`,
- opcjonalnie, gdy plik dla tego samego dnia istnieje: `regions_{day}.json` → `regions.json` (rejony), `details_{day}.json` → `details.json` (skład/sąsiedztwo), `conditions_{day}.json` → `conditions.json` (panel warunków 7 dni), `run_manifest_{day}.json` → `manifest.json` (parametry i statusy źródeł tego uruchomienia). Brak któregoś z tych plików nie jest błędem — odpowiadająca część interfejsu po prostu się nie pokazuje, a stary plik z poprzedniej synchronizacji jest usuwany, żeby nie mieszać danych z różnych dni.

Można podać inny katalog: `npm run sync-data -- C:/sciezka/do/output`.

Skrypt weryfikuje daty i powiązania identyfikatorów przed zastąpieniem plików. Nie cofa się bez ostrzeżenia do starszej analizy, jeśli najnowszy zestaw jest niekompletny. Nie wykonuj synchronizacji w czasie, gdy Python zapisuje wynik. Geometrie mają stałą nazwę — po zmianie lokalizacji trzeba synchronizować cały komplet. Identyfikatory nie wykryją zmiany geometrii przy zachowaniu tych samych ID; manifest jednego uruchomienia pozostaje możliwym ulepszeniem.

Starszy GeoParquet można jednorazowo przekonwertować z katalogu głównego:

```powershell
.venv/Scripts/python.exe -c "import geopandas as gpd; from pipeline.export import export_stand_geometries_geojson; export_stand_geometries_geojson(gpd.read_parquet('notebooks/output/stands_mvp.parquet'), 'notebooks/output/stands.geojson')"
```

Przygotowane lokalne dane, `node_modules/` i `dist/` są ignorowane przez Git. Nowy checkout wymaga eksportu/synchronizacji. Nowe uruchomienia `prepare_trip` generują GeoJSON automatycznie obok dotychczasowego GeoParquet i zawierają `d_park_m` w wynikach.

## Zachowanie interfejsu

- Wszystkie wydzielenia z `mask=true` i skończonym `R` sortowane są malejąco po R (backendowe `R_final`), przy remisie po ID. Brak limitu top-N, minimalnej powierzchni grupy ani odrzucania niskich/zerowych ocen.
- Strony po 30 pozycji; mapa pokazuje wszystkie kwalifikujące się oryginalne poligony, kolorowane oceną R. Jeden znacznik wskazuje wybór. Bez łączenia geometrii.
- Klasy F mają progi identyczne z profilem YAML: `<0.20`, `<0.45`, `<0.70`, pozostałe do 1. Baner używa mediany F wydzieleń przechodzących maskę. Jest to jawnie opisana agregacja na potrzeby UI.
- Karta pokazuje informacje konkretnego wydzielenia. H nazwano niskim/średnim/wysokim potencjałem według pomocniczych progów UI 0.4/0.7, nie jako skalibrowane prawdopodobieństwo.
- Kliknięcie karty lub poligonu wybiera wydzielenie; mapa ustawia właściwą stronę listy. Przycisk szczegółów otwiera pełny wynik wydzielenia.
- Zapis w `localStorage` obejmuje nazwę, dzień analizy, współrzędne, klasę i uzasadnienie. Klucz uwzględnia ID i współrzędne. Zachowano schemat `borowik.saved-regions.v1`, aby wcześniejsze zapisy rejonów pozostały dostępne. Można przeglądać i usuwać zapisy. Błędy zapisu są pokazywane użytkownikowi.
- Pasek „Zapisane mapy” nad listą/mapą pozwala przełączać się między „Aktualną” (dane z `data/`, zawsze dostępne) a analizami zapisanymi przez launcher (`frontend/public/data/trips/<id>/`, wymienione w `data/trips/index.json`). Zapisany wpis jest zamrożoną migawką: ponowna analiza tego samego miejsca nie zmienia wcześniej zapisanych wpisów. Zapis/usuwanie wpisów odbywa się w launcherze/Eksploratorze, nie w przeglądarce.
- Podkład OpenFreeMap oraz fonty Google wymagają internetu; fonty mają systemowy fallback. Przy awarii podkładu nadal działają granice i lista. Przy braku WebGL pozostaje lista.

## Warunki na kolejne dni

Pasek „Warunki” pokazuje 7 kafelków (dziś..dziś+6). Poziom 0–3 to klasa F z profilu (`fruiting_classes`) tego dnia — ta sama formuła wilgotności/temperatury (M/T/K_frost/G_season) co reszta interfejsu, ale liczona z MEDIANY OBSZARU siatki pogodowej zamiast per wydzielenie/punkt — to inna, osobno nie zwalidowana agregacja niż backtestowe 0,626 (patrz `docs/archiwum/CODEX-HANDOFF.md` note (27)). To **nie** osobny, skalibrowany model fazy wysypu (ten został wypróbowany i odrzucony — też note (27)). Pierwszy kafelek to dziś (dane zmierzone); kolejne używają prognozy temperatury/opadu. Zdanie nad kafelkami podaje wyłącznie fakty o ostatnim większym deszczu (daty, suma mm, ile dni temu) — nie przewiduje szczytu wysypu. `conditions.json` jest opcjonalny jak `regions.json`/`details.json`: brak pliku = tylko baner „Warunki w obszarze” bez kafelków, uszkodzony plik = głośny błąd.

## Źródła danych

Opady z ostatnich 30 dni: radar IMGW-PIB RainGRS (1 km, godzinowy), uzupełniany modelem Open-Meteo. Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy; dane zostały przetworzone (sumy dobowe, od Fazy 1.5 domyślnie ważone powierzchniowo na wielokącie każdego wydzielenia — `docs/archiwum/RAPORT_FAZA_1_5.md` — a nie uśredniane blokowo na całej siatce pogodowej; tryb blokowy nadal dostępny przez `radar.mode: block` w profilu).

## Ważne ograniczenia danych / uwagi do specyfikacji

1. **Punkt orientacyjny nie jest wejściem.** Eksport ma status wejścia, ale nie jego współrzędne. Znacznik i Google Maps wskazują przybliżony centroid wybranego wydzielenia, opisany wprost jako punkt orientacyjny. Nie nazywamy go parkingiem ani potwierdzonym startem.
2. **`d_park_m` nie oznacza dojazdu samochodem.** Dla `network` to dystans po sieci z odcinkami dojścia; dla `euclidean` — oszacowanie od najbliższej drogi/parkingu ×1,3. Starsze eksporty mogą nie zawierać tego pola; UI pokazuje wtedy brak danych. Nie odtwarzamy wartości ani nie zmieniamy starych wyników fikcyjnymi liczbami.
3. **Zapis lokalny nie zapewnia pełnego offline.** Zachowany tekst działa w otwartej aplikacji i wraca przy kolejnym uruchomieniu, ale sam `localStorage` nie przechowuje aplikacji ani kafli. PWA/service worker pozostają poza zakresem.
4. **Data eksportu (`--date`) to realna data wyjazdu, nie tylko etykieta.** Pogoda jest pobierana z prognozą do tej daty (do 15 dni naprzód), nie zawsze „na teraz”. Zakazy okresowe są jednak zawsze sprawdzane na dzień przygotowania analizy, nie na dzień wyjazdu — karta wydzielenia mówi o tym wprost. Backend sprawdza zakaz tylko dla top-50 wg rankingu; każde wydzielenie ma pole `zakaz_status` (`brak` / `zakaz` / `nie_sprawdzono` / `blad`) i `gdos_status` (`brak` / `blokada` / `kafel_pominiety`) w eksporcie — karta pokazuje dyskretną notatkę, gdy `zakaz_status` to `nie_sprawdzono` lub `blad`.
5. Model nieskalibrowany, brak osobnych S_host/S_site/S_age, szczegółów pogody i metadanych pobrania; `P=0` może wynikać z braku danych o dostępności. Pokazujemy ograniczenia, a nie pomiar tłoku.
6. Istniejące teksty uzasadnień z `nan` pozostają niezmienione zgodnie ze specyfikacją; poprawka generatora jest osobnym zadaniem backendu.

## Weryfikacja

```powershell
npm.cmd test
npm.cmd run build
# Z katalogu głównego:
.venv/Scripts/python.exe -m pytest -q
```

Testy obejmują granice klas F, łączenie identyfikatorów, błędne/mieszane daty, maskę, dobór uzasadnień, odległość zero/brak danych, nawigację, trwałość i uszkodzenie zapisów oraz spójność synchronizowanych plików. Backend testuje reprojekcję i eksport odległości. Ręcznie sprawdzono realną mapę, szczegóły, zapis po odświeżeniu i układ 390 px. Nie dodano Playwright/Cypress do projektu.

Dokumentacja użytych bibliotek: [MapLibre GeoJSONSource](https://maplibre.org/maplibre-gl-js/docs/API/classes/GeoJSONSource/), [OpenFreeMap quick start](https://openfreemap.org/quick_start/).

## Warstwy punktów dostępu (Faza 3)

Gdy analiza używa modelu `pressure.model: access_points`, `pipeline.prepare_trip` zapisuje też `access_points_{day}.geojson` (parkingi, wjazdy, szlabany, osiedla przy lesie: typ, źródło, atrakcyjność) i `forest_roads_{day}.geojson` (drogi publiczne, zamknięte drogi leśne i dojazdy pożarowe BDL: nawierzchnia, źródło, atrakcyjność). `npm run sync-data` kopiuje je jako `access_points.json` i `forest_roads.json` (opcjonalne, jak `regions.json`; stara kopia jest usuwana, gdy nowy dzień jej nie ma). Legenda mapy ma przełączniki: parkingi (P; ciemny odcień BDL, jasny OSM), wjazdy i szlabany (szlaban osobnym, czerwonym znacznikiem), drogi leśne (kolor wg nawierzchni: twarda / kruszywo / ubita / nieznana / gruntowa; linia ciągła = publiczna, przerywana = zamknięta droga leśna; grubość wg atrakcyjności), dojazdy pożarowe BDL (domyślnie wyłączone — gęste), osiedla przy lesie (domyślnie wyłączone) i półprzezroczysta warstwa P (domyślnie wyłączona). Wybór jest zapamiętywany w `localStorage`. Kliknięcie punktu lub drogi pokazuje typ, źródło i atrakcyjność (niska / średnia / wysoka). Karta wydzielenia podaje najbliższy parking, wjazd lub szlaban, utwardzony dukt oraz element o największym wpływie na P (dane z `details.json`, pole `access`). Brak plików warstw = brak przełączników, reszta interfejsu działa jak dotąd. Etykieta „P” na parkingach wymaga glifów podkładu; bez podkładu zostają same kółka.

## Interfejs Fazy UI (przełącznik presji, paski, telefon)

Szczegóły i lista kontrolna „stare pole → nowe miejsce”: `../docs/archiwum/RAPORT_UI.md`.

- **Przełącznik „Uwzględniaj presję grzybiarzy”** (nad listą; domyślnie włączony, pamięć w `localStorage` pod `borowik.pressure.v1`) przełącza sortowanie wydzieleń (`R` ↔ `R_bez_presji = 100·H·F_loc`), listę rejonów (`regions.json` ↔ `regions_bez_presji.json`), kolory mapy, wynik w karcie i uzasadnienie. Migawka bez `R_bez_presji` albo bez `regions_bez_presji.json` (starsze eksporty) ma przełącznik nieaktywny z komunikatem. `sync-data` i launcher przenoszą `regions_bez_presji.json` (opcjonalny).
- **Karta**: nagłówek → trzy paski „więcej = lepiej” (Siedlisko = H, Pogoda = F_loc, Spokój = 1 − P) rozwijane do składowych (S_host/S_site/S_age, M/T/K_frost, do 3 punktów o największym wkładzie w presję) → fakty (parking, wjazd, dukt, powierzchnia) → Zapisz / Nawiguj → zwinięte „Szczegóły” z wszystkim, co było na dawnej karcie i w widoku szczegółów. Osobnego widoku „Szczegóły wydzielenia” już nie ma.
- **Nazwy**: „Oddz. 96a · Nadl. Zawadzkie” (adres leśny + słownik nadleśnictw RDLP Katowice w `model.ts`, inne z `details.forest_district` lub kod), „Rejon 1 · Łaziska” (najbliższa miejscowość OSM z `regions*.json → near_place`, bez odmiany).
- **Pasek pogody**: jedno zdanie + 7 słupków F (wysokość = F, „?” od 4. dnia, „~” od 8.), reszta w zwiniętych „Szczegółach pogody”.
- **Telefon (≤ 760 px)**: zakładki „Lista / Mapa”, dotknięcie wydzielenia na mapie pokazuje jego kartę na liście, przycisk „Na mapie” w karcie wraca do mapy. Do sprawdzania układu w Chrome na komputerze użyj ramki iframe o szerokości 390 px (okno przeglądarki nie zawsze da się zwęzić).

### Tryby kolorowania mapy

Trzy przyciski w legendzie: „Wynik”, „Wynik bez presji” (zsynchronizowane z przełącznikiem presji) i „Wilgotność” (kolor według składowej M z `scores.json`, skala bezwzględna 0–1, wszystkie wydzielenia, poza maską jaśniej; zmienia tylko kolory mapy). Wybór w `localStorage` (`borowik.map-color.v1`). Migawka bez `M` — przycisk Wilgotność nieaktywny z komunikatem. Opis i testy: `../docs/archiwum/RAPORT_UI.md`, dodatek.

