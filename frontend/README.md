# Borowik — frontend

Lokalna, statyczna aplikacja według `docs/superpowers/specs/2026-09-24-borowik-frontend-design.md`: Vite + TypeScript, MapLibre. Bez serwera API i frameworka UI.

## Uruchomienie

W katalogu roboczym Claude Code:

```powershell
Set-Location 'C:\Users\<uzytkownik>\Documents\Grzyby\.claude\worktrees\borowik-faza2-mvp-backend'

# Nowa analiza — wymaga dostępu do źródeł danych. Nie jest potrzebna,
# jeżeli chcesz obejrzeć już przygotowane i zsynchronizowane wyniki.
& .\.venv\Scripts\python.exe -m pipeline.prepare_trip --lat 53.1509 --lon 16.7382

Set-Location frontend
npm.cmd ci
npm.cmd run sync-data
npm.cmd run dev
```

Otwórz adres podany przez Vite (domyślnie http://127.0.0.1:5173). Serwer nasłuchuje lokalnie. Grupowanie jest wyłączone: lista i mapa przedstawiają pojedyncze wydzielenia. Nie trzeba przeliczać istniejącej analizy — wystarczy synchronizacja ocen i geometrii.

Powyższe polecenia są dla PowerShell. Nazwa modułu to dokładnie `pipeline.prepare_trip`, bez ukośnika przed `_`. Główny katalog `C:\Users\<uzytkownik>\Documents\Grzyby` zawiera starszą wersję backendu bez tego modułu; aktualna implementacja znajduje się we wskazanym katalogu Claude Code.

Wymagany Node.js >=22.12 (sprawdzono Node 24). `npm run build` sprawdza TypeScript i tworzy `dist/`; `npm run preview` wyświetla wersję produkcyjną. Hosting jest poza zakresem tej iteracji.

## Synchronizacja danych

Promień nowej analizy rzeczywiście działa: dodaj do polecenia Pythona `--radius-km 25` (domyślnie 25 km, zakres 10–50 km). Analiza obejmuje wydzielenia ze środkiem w kole o podanym promieniu. Większy promień oznacza więcej pobrań i dłuższe pierwsze uruchomienie. Zmiana promienia wymaga nowej analizy i ponownego `sync-data`; przesuwanie lub oddalanie mapy nie rozszerza danych. Stan backendu i instrukcje dla Claude Code: `../docs/CODEX-HANDOFF.md`.

`npm run sync-data` kopiuje z `../notebooks/output/` do `public/data/`:

- najnowszy `scores_YYYY-MM-DD.json` → `scores.json`,
- `stands.geojson` w EPSG:4326 → `stands.geojson`.

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

## Źródła danych

Opady z ostatnich 30 dni: radar IMGW-PIB RainGRS (1 km, godzinowy), uzupełniany modelem Open-Meteo. Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy; dane zostały przetworzone (sumy dobowe, średnie blokowe).

## Ważne ograniczenia danych / uwagi do specyfikacji

1. **Punkt orientacyjny nie jest wejściem.** Eksport ma status wejścia, ale nie jego współrzędne. Znacznik i Google Maps wskazują przybliżony centroid wybranego wydzielenia, opisany wprost jako punkt orientacyjny. Nie nazywamy go parkingiem ani potwierdzonym startem.
2. **`d_park_m` nie oznacza dojazdu samochodem.** Dla `network` to dystans po sieci z odcinkami dojścia; dla `euclidean` — oszacowanie od najbliższej drogi/parkingu ×1,3. Starsze eksporty mogą nie zawierać tego pola; UI pokazuje wtedy brak danych. Nie odtwarzamy wartości ani nie zmieniamy starych wyników fikcyjnymi liczbami.
3. **Zapis lokalny nie zapewnia pełnego offline.** Zachowany tekst działa w otwartej aplikacji i wraca przy kolejnym uruchomieniu, ale sam `localStorage` nie przechowuje aplikacji ani kafli. PWA/service worker pozostają poza zakresem.
4. **Data eksportu nie jest datą każdego źródła.** CLI pozwala nadać etykietę dnia, ale pobiera bieżące okno pogody. UI nie deklaruje „zakazy sprawdzone dziś” dla całego rejonu: backend sprawdza je tylko dla top-N, a eksport nie zawiera statusów per stand.
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
