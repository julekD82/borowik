# Borowik — zapisane mapy (lista do porównywania analiz) — Design

> Spec brainstormed and approved section-by-section 2026-09-26. This document is
> what `writing-plans` argues from.

## Goal

Dziś aplikacja pokazuje dokładnie jeden, aktywny zestaw danych: cokolwiek
`npm run sync-data` ostatnio skopiowało do `frontend/public/data/`. Nowa
analiza (`pipeline.prepare_trip` + `sync-data`) nadpisuje poprzednią — nie ma
sposobu, żeby wrócić do wyników sprzed zmiany miejsca, promienia, dnia czy
algorytmu.

Ta funkcja dodaje możliwość **zapisania aktualnie wyświetlanej analizy pod
czytelną nazwą** (np. "Będziemyśl - 20km - 26.09") i **przełączania się
między zapisanymi analizami w przeglądarce**, żeby móc je porównywać —
bez ponownego uruchamiania pipeline'u.

## Kontekst / decyzje z brainstormingu

- **Pełne dane, nie zakładka.** Zapis kopiuje cały zestaw plików (nie tylko
  parametry uruchomienia) — po wybraniu wpisu z listy mapa i lista wydzieleń
  ładują się od razu, bez przeliczania.
- **Magazyn: pliki na dysku, nie `localStorage`/IndexedDB.** Aplikacja ma
  lokalny launcher (`launcher/launcher.pyw`) uruchamiający pipeline i serwer
  — to nie jest hostowana strona ograniczona do magazynu przeglądarki. Pliki
  przetrwają czyszczenie danych przeglądarki, są widoczne w Eksploratorze i
  pasują do już istniejącego wzorca `sync-data` (kopiowanie plików).
- **Nazwa ręczna, promień i dzień automatyczne.** Backend nie eksportuje
  dziś nazwy miejsca (zna tylko lat/lon) — użytkownik wpisuje ją sam w
  launcherze. Promień jest już polem w launcherze; dzień jest już polem
  `day` w każdym rekordzie `scores.json`, więc oba dają się odczytać
  automatycznie, bez zmian w pipeline.
- **Zapis to osobny przycisk w launcherze, nie automat przy każdym
  uruchomieniu.** Nie każde uruchomienie/eksperyment ma zaśmiecać listę.
- **W przeglądarce: panel wyboru nad mapą, nie osobny ekran startowy.**
  Aplikacja nadal startuje na ostatnio zsynchronizowanych danych ("Aktualna");
  dochodzi rozwijany panel "Zapisane mapy" do przełączania się bez
  wychodzenia z aplikacji.
- **Zapisane migawki są zamrożone.** Zmiana algorytmu/źródła danych (np.
  planowana zamiana opadów Open-Meteo na radar IMGW,
  `docs/superpowers/plans/2026-09-26-borowik-radar-opady-a1.md`) i ponowne
  uruchomienie analizy nie zmienia już zapisanych wpisów — to zamierzone,
  właśnie to umożliwia porównanie "przed/po". Warunek: nowe pola w
  `scores.json`/`model.ts` muszą pozostawać opcjonalne (dokładnie tak, jak
  plan A1 już robi z `rain_radar_coverage?: number | null`), żeby starsze
  zapisane migawki nadal się wczytywały pod nowszym kodem frontendu.

**Poza zakresem (YAGNI, świadomie pominięte):**
- Usuwanie/zmiana nazwy zapisanego wpisu z poziomu aplikacji lub launchera —
  na start wystarczy ręczne skasowanie folderu w Eksploratorze.
- Limit liczby zapisów / automatyczne sprzątanie starych wpisów.
- Synchronizacja zapisów między urządzeniami/przeglądarkami — to lokalne
  pliki na jednym dysku, tak jak reszta `public/data/`.

## Magazyn danych

`frontend/public/data/trips/<id>/` — kopia plików aktywnych w chwili
zapisu: `scores.json`, `stands.geojson` zawsze; `regions.json`,
`details.json` jeśli akurat istnieją (te dwa są już dziś opcjonalne w
`sync-data`).

`frontend/public/data/trips/index.json` — lista metadanych, jeden wpis na
zapisaną analizę:
```json
[
  {
    "id": "bedziemysl-2026-09-26",
    "name": "Będziemyśl",
    "radiusKm": 20,
    "day": "2026-09-26",
    "lat": 50.0555,
    "lon": 21.7889,
    "savedAt": "2026-09-26T18:04:12+02:00"
  }
]
```
Najnowszy zapis na początku listy. `id` = slug(`name`) + `-` + `day` — ten
sam slug+dzień nadpisuje istniejący wpis (patrz niżej, potwierdzenie w
launcherze).

Oba miejsca leżą pod istniejącym `frontend/.gitignore` (`public/data/*`),
więc nic z tego nie trafia do repo — spójne z regułą "brak danych lokalnych
w repo" already governing `public/data/`.

## Launcher (`launcher/launcher.pyw`)

- Nowe pole tekstowe **"Nazwa miejsca"** w formularzu, obok istniejących
  lat/lon/promień. Zapamiętywane w `launcher_config.json` jak pozostałe
  pola (ostatnio użyta wartość, nie wymagane do uruchomienia analizy —
  tylko do zapisu).
- Nowy przycisk **"Zapisz do listy"** obok "Uruchom analizę i podgląd" /
  "Tylko podgląd" / "Zatrzymaj serwer".
- Działanie po kliknięciu:
  1. Walidacja: nazwa niepusta (trim); promień z pola Promień, ta sama
     walidacja 10–50 co dziś przy uruchamianiu analizy.
  2. Odczyt `frontend/public/data/scores.json`; jeśli plik nie istnieje lub
     jest pusty/niepoprawny → `messagebox.showerror` "Brak
     zsynchronizowanych danych do zapisania. Uruchom najpierw analizę i
     podgląd.", przerwij.
  3. `day` = `scores[0]["day"]`. `id` = slugify(nazwa) + "-" + day
     (slugify: lowercase, litery/cyfry/`-`, polskie znaki
     transliterowane — np. "Będziemyśl" → "bedziemysl").
  4. Jeśli `frontend/public/data/trips/<id>/` już istnieje →
     `messagebox.askyesno` "Wpis '<nazwa>' z dnia <day> już istnieje.
     Nadpisać?"; odmowa przerywa zapis bez zmian.
  5. Kopiuje `scores.json`, `stands.geojson` i — jeśli istnieją —
     `regions.json`, `details.json` do `trips/<id>/`.
  6. Wczytuje (lub tworzy pustą listę) `trips/index.json`, usuwa
     ewentualny istniejący wpis o tym samym `id`, wstawia nowy na
     początek, zapisuje z powrotem (ładne formatowanie, jak
     `launcher_config.json`).
  7. Log + status bar: "Zapisano '<nazwa> - <promień>km - <day>' do
     listy."
- Działa niezależnie od tego, czy dane powstały przez "Uruchom analizę" czy
  "Tylko podgląd" w tej samej sesji launchera — zapisuje to, co aktualnie
  jest zsynchronizowane w `public/data/`, nie wymaga świeżego uruchomienia
  w tej samej sesji.

## Frontend

`frontend/src/model.ts`:
- `loadData(basePath: string = "data/")` — dotychczasowe trzy `fetch()`
  (`scores.json`/`stands.geojson` wymagane, `regions.json`/`details.json`
  opcjonalne) budują URL z `${import.meta.env.BASE_URL}${basePath}${file}`
  zamiast na sztywno `data/`. Zachowanie przy braku/błędzie plików bez
  zmian.
- Nowy typ `TripMeta = { id: string; name: string; radiusKm: number; day:
  string; lat: number; lon: number; savedAt: string }`.
- Nowa `loadTrips(): Promise<TripMeta[]>` — `fetch("data/trips/index.json")`;
  brak pliku (404) lub błąd sieci → `[]`, nie wyjątek (dokładnie ta sama
  zasada co dziś dla `regions.json`/`details.json`: opcjonalny plik, jego
  brak nie jest błędem). Plik obecny, ale niepoprawny JSON/kształt → filtruje
  niepoprawne wpisy (ten sam wzorzec co `readSaved` w `storage.ts`), nie
  wywala całego ładowania.

`frontend/src/main.ts`:
- `initialize()` przyjmuje opcjonalny `basePath` (domyślnie `"data/"`) i
  używa go w wywołaniu `loadData(basePath)` — pozwala ponownie użyć całej
  istniejącej ścieżki ładowania/renderowania zarówno dla danych "na żywo",
  jak i dla zapisanej analizy.
- Przy starcie: `loadTrips()` równolegle z `loadData()`; wynik w module-level
  `savedTrips: TripMeta[]`.
- Nowy panel **"Zapisane mapy"** nad mapą/listą: pozycja "Aktualna"
  (`data/`, zawsze pierwsza) + wpisy `savedTrips` sformatowane jako
  `${name} - ${radiusKm}km - ${DD.MM}` (dzień skrócony z ISO, funkcja
  pomocnicza obok istniejącego `formatDate`). Aktywny wybór podświetlony.
- Klik na wpis → `initialize(`data/trips/${id}/`)`; klik "Aktualna" →
  `initialize()` (domyślny `basePath`). Błąd wczytania (uszkodzony/
  niekompletny zapis) pokazywany tym samym baneru błędu co dziś przy
  starcie — nie wywraca reszty panelu z listą zapisanych map.
- Stan wyboru (który wpis jest aktywny) trzymany w module-level zmiennej,
  nie w `localStorage` — przełączanie map nie musi przetrwać odświeżenia
  strony (odświeżenie wraca do "Aktualna", tak jak dziś).

## Testowanie

- **Vitest** (`frontend/src/model.test.ts`): `loadTrips` — brak
  `trips/index.json` (pusta lista, brak wyjątku), poprawny plik z 1–2
  wpisami, uszkodzony JSON, wpis z brakującym/złym polem (odfiltrowany).
  `loadData(basePath)` — istniejący zestaw testów przechodzi niezmieniony z
  domyślnym `basePath`; nowy test ładowania z innego `basePath` (fixture
  pod innym prefiksem URL w mocku `fetch`).
- **Launcher:** brak istniejącego zestawu testów Pythona dla GUI (sprawdzone
  — `tests/` nie zawiera nic dla `launcher/`), więc bez zmian względem
  obecnej praktyki: weryfikacja ręczna — zapis, nadpisanie z potwierdzeniem,
  odmowa nadpisania, próba zapisu bez zsynchronizowanych danych.
- **Manualnie w przeglądarce:** zapisać dwie różne analizy (np. dwa różne
  promienie tego samego miejsca) przez launcher, przełączyć się między nimi
  w panelu "Zapisane mapy" i "Aktualna", potwierdzić że mapa/lista/karta
  szczegółów pokazują właściwy zestaw dla każdego wyboru.

## Success criteria

- Kliknięcie "Zapisz do listy" w launcherze (po uprzednim "Uruchom analizę i
  podgląd" lub "Tylko podgląd") tworzy folder w `trips/` i wpis w
  `index.json` z poprawną nazwą/promieniem/dniem.
- Ponowne uruchomienie aplikacji (`npm run dev` / odświeżenie strony) nadal
  pokazuje "Aktualną" analizę jak dziś, plus panel "Zapisane mapy" z
  wcześniej zapisanymi wpisami.
- Wybór zapisanego wpisu w przeglądarce ładuje dokładnie te dane, które
  były aktywne w chwili zapisu — niezależnie od tego, co jest aktualnie w
  `data/` (czyli niezależnie od nowszych analiz uruchomionych później).
- Zapisanie tej samej nazwy+dnia drugi raz pyta o potwierdzenie nadpisania
  i, po potwierdzeniu, poprawnie zastępuje stary zapis.
