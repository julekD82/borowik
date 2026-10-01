# Borowik — nowy frontend (projekt)

Data: 30.09.2026. Gałąź: `nowy-frontend`. Status: projekt zatwierdzony w rozmowie z właścicielem (sekcje 1–3), do przeczytania przed planem wdrożenia.

Zastępuje interfejs opisany w `docs/archiwum/superpowers/specs/2026-09-24-borowik-frontend-design.md` i zmiany z `docs/archiwum/RAPORT_UI.md`. **Model (H, F, F_loc, P, R, maska, rejony) się nie zmienia.** Backend dostaje tylko dopisane pola eksportu.

## 1. Cel i ustalenia

Cel: na komputerze, przed wyjazdem, w mniej niż minutę odpowiedzieć sobie „czy jechać w tym tygodniu” i „do którego rejonu”, a potem móc przeanalizować dowolne wydzielenie. Szczegóły są pod ręką, ale nie na wierzchu.

Decyzje właściciela (30.09.2026):

| Temat | Decyzja |
|---|---|
| Główne urządzenie | komputer przed wyjazdem; telefon ma działać poprawnie, bez osobnego dopracowania |
| Używane funkcje | rejony i szczegóły, pojedyncze wydzielenia, przełącznik presji, mapa wilgotności, warstwy dostępu |
| Nieużywane | zapisane miejsca (usunąć), zapisane mapy/migawki (zostają, ale na dalszym planie) |
| Układ | A: wąski pasek u góry, panel boczny po lewej, duża mapa po prawej |
| Pojedyncze wydzielenie | karta w panelu bocznym (stos nawigacji z „←”), mapa zostaje odsłonięta |
| Mapa „Wynik” | 4 klasy procentowe jak w eksporcie KMZ |
| Mapa „Wilgotność” | ciągła skala 0–1 (jak dziś) |
| Panel pogody | fakty zamiast oceny, z normą opadu dla tej pory roku (E-OBS 1991–2020); bez słupków F |
| Technika | od nowa w Preact + `@preact/signals`; MapLibre zostaje |

Tło decyzji o pogodzie: słupki F używały wag opadu K0 (najmocniej dzisiejszy deszcz), więc F spadało z każdym dniem po deszczu. Analiza Bielefeld (`docs/RAPORT_BIELEFELD.md`) pokazała, że wpływ opadu rozkłada się mniej więcej równo na ok. 3 tygodnie wstecz. Zmiana wag w modelu (K1) jest osobną decyzją, planowaną po sezonie; ten projekt jej nie obejmuje.

## 2. Zakres

| Funkcja | W nowym interfejsie |
|---|---|
| Rejony i ich szczegóły | zakładka „Rejony” w panelu (domyślna, gdy rejony istnieją) |
| Pojedyncze wydzielenia | zakładka „Wydzielenia” oraz kliknięcie dowolnego wydzielenia na mapie |
| Przełącznik presji | nad zakładkami panelu; zmienia ranking listy, rejony i klasy mapy |
| Tryby mapy | „Wynik” i „Wilgotność”; osobny tryb „Wynik bez presji” znika (robi to przełącznik presji) |
| Warstwy dostępu + legenda | przycisk „Warstwy” na mapie, okienko z listą i legendą |
| Zapisane mapy (migawki) | lista „Analiza: …” w górnym pasku |
| Zapisane miejsca, zakładka „Zapisane” | usunięte; zostają „Nawiguj” i „Kopiuj współrzędne” |
| Duże hasło i nagłówek strony | usunięte |
| „O danych i ograniczeniach” | link w górnym pasku, okno dialogowe z odświeżoną treścią |
| Etykieta pewności („średnia”) | usunięta z kart (zawsze ta sama); informacja zostaje w „O danych” |
| Zdania uzasadnień z szablonów | usunięte z kart; zastępują je paski z opisem słownym i liczbami |

## 3. Układ i nawigacja

### 3.1 Komputer (≥ 800 px szerokości)

- **Górny pasek (ok. 48 px):** logo „Borowik”; opis analizy: nazwa migawki albo „Aktualna analiza”, promień, data; lista „Analiza: …” (aktualna + migawki z `data/trips/index.json`); link „O danych”.
- **Panel boczny (ok. 400 px, przewijany niezależnie od mapy), od góry:**
  1. panel pogody (rozdział 4), domyślnie zwinięty;
  2. przełącznik „Uwzględniaj presję grzybiarzy” (niedostępny, z wyjaśnieniem, gdy migawka nie ma `R_bez_presji`);
  3. zakładki „Rejony (N) | Wydzielenia (N)”;
  4. treść bieżącego widoku stosu nawigacji.
- **Mapa (reszta ekranu):** prawy górny róg: przełącznik „Wynik | Wilgotność” i przycisk „Warstwy”; lewy dolny: legenda aktywnego trybu; przycisk „pokaż cały obszar”; skala; przybliżanie.

### 3.2 Stos nawigacji panelu

- Rejony → karta rejonu (z listą jego wydzieleń) → karta wydzielenia.
- Wydzielenia → karta wydzielenia.
- Kliknięcie wydzielenia na mapie kładzie jego kartę na wierzch bieżącego stosu (z każdej zakładki), także dla wydzieleń spoza czołówki i spoza filtrów modelu.
- „←” wraca o jeden poziom; zmiana zakładki czyści stos do listy tej zakładki.
- Zmiana presji: listy i rejony przeliczają się; otwarta karta wydzielenia zostaje (z nowym wynikiem i miejscem w rankingu); otwarta karta rejonu wraca do listy rejonów, jeśli rejon nie istnieje w drugim wariancie.

### 3.3 Zachowanie mapy

- Wybór z listy (rejon, wydzielenie) przybliża mapę do jego granic.
- Kliknięcie na mapie, zmiana zakładki i zmiana trybu **nie zmieniają przybliżenia** (zachowanie z commitów `c25852b`, `23766b5`).
- Wybrane wydzielenie: wyraźny obrys; wybrany rejon: podświetlenie jego wydzieleń.
- Najechanie myszą: dymek z nazwą, wynikiem i klasą.

### 3.4 Telefon (< 800 px)

Panel i mapa jako dwie zakładki „Lista | Mapa” (jak dziś). Kliknięcie wydzielenia na mapie przełącza na „Lista” z jego kartą. Bez osobnego dopracowania układu.

### 3.5 Ustawienia zapamiętywane w przeglądarce

Presja, tryb mapy, włączone warstwy, ostatnia zakładka. Odczyt i zapis w `try/catch`; bez `localStorage` aplikacja działa z ustawieniami domyślnymi (presja włączona, tryb „Wynik”, zakładka „Rejony”, warstwy jak dziś w `ACCESS_LAYERS`).

## 4. Panel pogody

### 4.1 Zwinięty (domyślnie)

- Nagłówek z samymi faktami, bez słów oceniających, np. „6 dni po większym deszczu · 60 mm w 26 dni (norma 48)”. Brak większego deszczu w 45 dniach: „Brak większego deszczu od 45 dni · 12 mm w 26 dni (norma 48)”.
- Trzy liczby:
  - opad z 26 dni (z normą, jeśli jest),
  - dni od ostatniego większego deszczu, z datami i sumą epizodu (definicja epizodu jak dziś: `recent_rains`, próg `conditions.pulse_min_mm`, obniżony przy radarze),
  - średnia temperatura z 20 dni wobec optimum z profilu (`fruiting.temp_optimum_c`, dziś 13 °C).
- Mały wykres dziennego opadu (SVG): ok. 35 dni wstecz + horyzont prognozy; zaznaczone okno 26 dni; kreska „dziś”. Odcienie: pomiar (udział radaru ≥ 0,5), model bez radaru (pośredni), prognoza (jasny).
- Zdanie: „Więcej deszczu niż w X% lat 1991–2020 o tej porze (E-OBS)”, jeśli jest norma.

### 4.2 Rozwinięty

- Pasmo temperatury dobowej min.–maks. z linią optimum.
- Tabela dni prognozy: opad, maks., min. Dni od `ui.forecast_uncertain_from_day` oznaczone jako niepewne, od `ui.forecast_indicative_from_day` jako orientacyjne (jak dziś).
- Ostrzeżenia, tylko gdy wystąpią (z `warnings` w eksporcie): przymrozek; upał z suszą.
- Notka: „Wg danych z Bielefeld liczy się deszcz z ok. 3 tygodni wstecz, mniej więcej po równo. Pomiar opadu (radar IMGW) i norma (E-OBS, sieć stacji) to różne źródła — porównanie jest przybliżone.”

### 4.3 Stare migawki

Bez `daily`: panel pokazuje dotychczasowe zdanie `summary` o deszczu i średnią temperaturę z `days[0].components`, bez wykresu. Bez `rain26.normal_mm`: bez normy i bez zdania o procentach lat.

## 5. Mapa

### 5.1 Tryb „Wynik”

- Klasy wśród wydzieleń z `mask = true`, wg R (presja włączona) albo `R_bez_presji` (wyłączona): 1 = najlepsze 5%, 2 = 5–20%, 3 = 20–50%, 4 = reszta.
- Definicja identyczna z `pipeline/phone_kmz.py::classify_by_percentile` (`CLASS_THRESHOLDS = {1: 0.05, 2: 0.20, 3: 0.50}`), łącznie z obsługą remisów. Zgodność pilnuje wspólny plik testowy (rozdział 9).
- Kolory: klasa 1 ciemnozielony, 2 zielony, 3 jasnozielony, 4 prawie niewidoczny szary. Wydzielenia z `mask = false`: tylko cienki obrys.
- Rejony: wydzielenia członkowskie obrysowane grubszą linią, znacznik z numerem w środku rejonu.

### 5.2 Tryb „Wilgotność”

Ciągła skala 0–1 dla składowej M (obecne `MOISTURE_STOPS`, skala bezwzględna), wszystkie wydzielenia. Legenda: „Wilgotność w modelu (bilans opadu i parowania z 26 dni; w obecnym modelu najmocniej liczy się ostatni deszcz). Może różnić się od wymowy panelu pogody.” Migawki bez `M`: przycisk trybu nieaktywny.

### 5.3 Warstwy

Okienko „Warstwy” z listą `ACCESS_LAYERS` (Parkingi, Wjazdy i szlabany, Drogi leśne, Dojazdy pożarowe BDL, Osiedla przy lesie, Presja P) i legendą symboli oraz nawierzchni. Warstwy bez danych w migawce są ukryte. Rysowanie warstw przejęte z obecnego `map.ts`.

## 6. Karty

### 6.1 Karta rejonu

- Nagłówek: „Rejon N · {najbliższa miejscowość}”, wynik rejonu (`rank_score`), liczba wydzieleń, łączna powierzchnia, odległość od środka analizy.
- Trzy paski jako **mediana 5 najlepszych wydzieleń rejonu** (w bieżącym wariancie presji), tj. ta sama podstawa co `rank_score`: Siedlisko (H), Pogoda (F_loc), Spokój (1 − P). Przy wyłączonej presji pasek Spokój ma stan „nie uwzględniony”, jak w karcie wydzielenia.
- Dojazd w całym rejonie: zakresy odległości do parkingów i wjazdów (obecne `regionAccessSummary`).
- Lista wydzieleń rejonu (wynik malejąco), klik otwiera kartę wydzielenia.
- Przyciski: „Nawiguj” (Google Maps do środka rejonu), „Kopiuj współrzędne”.

### 6.2 Karta wydzielenia

- Nagłówek: „Oddz. {oddział}{pododdział} · Nadl. {nadleśnictwo}”, powierzchnia, odległość od środka analizy, „#k z N” w bieżącym wariancie (N = liczba wydzieleń z `mask = true`, kolejność jak dziś: wynik zaokrąglony, potem `tie_break`, potem identyfikator), wynik.
- „Dlaczego taki wynik” — trzy paski ze słowem i liczbą:
  - Siedlisko (H) + skład w skrócie, typ siedliska, wiek;
  - Pogoda (F_loc) + opad 26 dni wydzielenia (`weather.p26_mm`), wilgotność M, temperatura 20 dni;
  - Spokój (1 − P) + główne źródło presji (`access.pressure_contrib`); przy wyłączonej presji: „nie uwzględniony”.
- „Drzewostan”: skład z udziałami (paczka lub gatunek panujący z WFS), wiek, typ siedliska, gleba, zwarcie, pokrywa gleby, podszyt, sąsiedztwo, wskazówka o przejściu (`searchability_hint`).
- „Dojazd”: parking, wjazd, utwardzony dukt (odległości), punkt o największym wkładzie presji.
- „Dane”: kod wydzielenia, adres leśny (leśnictwo, oddział, pododdział), źródło składu i jego data, data analizy.
- Przyciski: „Nawiguj” (środek wydzielenia), „Kopiuj współrzędne”.

### 6.3 Wydzielenie poza filtrami modelu

Nagłówek jak wyżej, zamiast wyniku: „Nie spełnia filtrów modelu” i powody z `mask_reason` (po polsku), potem dostępne sekcje „Drzewostan”, „Dojazd”, „Dane”. Bez pasków.

## 7. Zmiany w eksporcie (backend)

Tylko dopisane pola; istniejące pola i ich znaczenie bez zmian. Model, ranking i progi bez zmian.

### 7.1 `conditions_{day}.json` / `conditions.json`

```json
{
  "daily": [
    {"date": "2026-08-26", "precip_mm": 0.0, "radar_share": 1.0,
     "tmin_c": 12.1, "tmax_c": 24.0, "forecast": false}
  ],
  "rain26": {
    "sum_mm": 59.6, "window_start": "2026-09-05", "window_end": "2026-09-30",
    "normal_mm": 48.0, "pct": 0.71,
    "normal_source": "E-OBS v33.0e, 1991–2020", "normal_cells": 4
  },
  "warnings": [
    {"type": "frost", "dates": ["2026-10-04"]},
    {"type": "heat_drought", "dates": []}
  ]
}
```

- `daily`: jeden wpis na lokalną dobę od `dziś − 35` do końca horyzontu; mediana obszaru po punktach pogody w kole (jak `area_daily_weather`, rozszerzone o `tmax_c`); `radar_share` = średni `radar_frac` punktów (0 bez radaru); `forecast = data > dziś`.
- `rain26.sum_mm`: mediana po punktach pogody zwykłej sumy opadu z 26 dni kończących się dziś (to samo co `p26_sum` w `compute_weather_features`).
- `rain26.normal_mm` i `pct`: z lokalnego E-OBS (`pipeline/eobs.py::EobsStore`, katalog `cache/eobs`): dla komórek E-OBS w kole wszystkie 26-dniowe sumy opadu z lat 1991–2020 kończące się w dniach roku odległych o ≤ 15 dni od dziś (z zawinięciem roku); `normal_mm` = mediana puli, `pct` = percentyl `sum_mm` w puli (`percentile_rank`, jak w pipeline). Brak plików E-OBS lub pusta pula: `normal_mm = null`, `pct = null`, analiza się nie przerywa (komunikat w logu).
- `warnings` (progi z profilu, bez nowych parametrów):
  - `frost`: dni od `dziś − 2` do końca horyzontu z medianą `tmin_c` < `fruiting.frost_tmin3_soft_c`;
  - `heat_drought`: dni od dziś do końca horyzontu, w których średnia temperatura z 5 dni > `fruiting.heat_penalty_tmean5_c` i suma opadu z 5 dni < `fruiting.heat_penalty_p5_mm` (mediana obszaru).

### 7.2 `details_{day}.json`

- `site_type`: `{"code": "BMSW", "label": "bór mieszany świeży"}` (nazwa ze słownika BDL, jeśli jest; inaczej sam kod).
- `age_years`: wiek użyty w modelu (z aktualizacją do roku analizy, jak `age_update_enabled`), liczba całkowita albo `null`.

### 7.3 `scores_{day}.json`

- `mask_reason`: lista kodów dla `mask = false`, pusta albo brak dla `mask = true`. Kody: `not_dstan`, `no_age`, `too_young`, `excluded_species`, `gdos`, `zakaz`. Warunki jak w `pipeline/habitat.py` (maska strukturalna) i w pełnej masce (GDOŚ, zakaz).

### 7.4 Synchronizacja

`frontend/scripts/sync-data.mjs` przyjmuje nowe pola jako opcjonalne (stare eksporty przechodzą bez zmian).

## 8. Architektura frontendu

- Stos: Vite + TypeScript + Preact (`preact`, `@preact/signals`, `@preact/preset-vite`), MapLibre GL bez zmian. Skrypty npm bez zmian (`dev`, `build`, `test`, `sync-data`).
- `src/state.ts`: jeden stan (sygnały): wczytana analiza i jej pochodne (połączone wpisy, klasy dla obu wariantów presji, widoki rejonów), wybrana analiza, presja, tryb mapy, warstwy, stos nawigacji, wybór, stan wczytywania/błędu; zapis ustawień (3.5).
- `src/data/`: wczytywanie i parsowanie plików (przeniesione z `model.ts`: `loadData`, `parseData`, `parseConditions`, `loadTrips` itd.), typy danych.
- `src/domain/`: czyste funkcje bez DOM, przeniesione z `model.ts` razem z testami: ranking i klasy, rejony, pogoda (mapowanie `daily`/`rain26`/`warnings` na treść panelu), dojazd, etykiety i nazwy, `mask_reason` → tekst. Funkcje nieużywane przez nowy interfejs (pewność, uzasadnienia, zapisane miejsca, tryb „Wynik bez presji”) są usuwane wraz z testami.
- `src/components/`: `TopBar`, `AnalysisPicker`, `AboutDialog`, `Sidebar`, `WeatherPanel` (+ `RainChart`), `PressureToggle`, `Tabs`, `RegionList`, `RegionCard`, `StandList`, `StandCard`, `ScoreBars`, `MapControls`, `LayersPopover`, `Legend`, `MobileTabs`, `LoadingState`, `ErrorState`.
- `src/map/`: nakładka na MapLibre przejęta z `map.ts` (źródła, warstwy, wyrażenia koloru dla klas i wilgotności, obrysy rejonów, podświetlenie, dymek, warstwy dostępu); komunikacja ze stanem przez metody (`setData`, `setMode`, `setSelection`, `fitTo`) i jedno wywołanie zwrotne kliknięcia.
- Wczytywanie: najpierw `manifest`, `scores`, `stands`, `regions*`, `conditions` (pierwszy widok); `details`, `access_points`, `forest_roads` w tle. Karta wydzielenia przed wczytaniem `details` pokazuje wynik i paski, sekcje szczegółów z „wczytuję szczegóły…”.
- Lista wydzieleń: stronicowana po 50, domyślnie tylko ≥ 0,5 ha (`isStandaloneTarget`), z przełącznikiem „pokaż też mniejsze”.

## 9. Obsługa błędów i zgodność

- Brak `scores` lub `stands`: ekran błędu z „Spróbuj ponownie” (ta sama analiza).
- Pliki opcjonalne (`regions`, `regions_bez_presji`, `details`, `conditions`, `manifest`, `access_points`, `forest_roads`): brak → ukryte elementy, które ich potrzebują. Odpowiedź, która nie jest poprawnym JSON-em (np. `index.html` zwracany przez serwer Vite zamiast 404), jest traktowana jak brak pliku.
- Stare migawki bez nowych pól: panel pogody jak w 4.3, karta wydzielenia bez wieku/typu siedliska, wydzielenie poza filtrami bez listy powodów („powód nieznany w tej analizie”), tryb „Wilgotność” nieaktywny bez `M`, presja nieaktywna bez `R_bez_presji`.

## 10. Testy

- **Backend (pytest, bez sieci):** `daily` (zakres dat, mediany, `radar_share`, `forecast`), `rain26` (suma, norma i percentyl na syntetycznym E-OBS, brak E-OBS → `null`), `warnings` (oba typy, progi z profilu), `site_type`/`age_years` w details, `mask_reason` dla każdego warunku maski. Pełne `pytest`.
- **Frontend (vitest):** przeniesione testy czystych funkcji; klasy procentowe na wspólnym pliku testowym `tests/fixtures/klasy_percentyl.json` (generowanym z `classify_by_percentile` i czytanym też przez test Pythona); mapowanie danych pogody (z nowymi polami i bez nich); `mask_reason` → tekst; komponenty (`@testing-library/preact` + jsdom): karta rejonu (mediana 5 najlepszych), karta wydzielenia, karta poza filtrami, panel pogody (nowa i stara migawka), stos nawigacji. `tsc --noEmit` i `vite build` bez błędów.
- **Ręcznie w przeglądarce:** na prawdziwych danych (aktualna analiza i jedna stara migawka), szerokość komputera i ok. 390 px; zrzuty ekranu do `docs/archiwum/ui-zrzuty/` i raport z listą kontrolną „stare pole → nowe miejsce” (jak `docs/archiwum/RAPORT_UI.md`).

## 11. Wdrożenie i kryteria ukończenia

- Praca na gałęzi `nowy-frontend`. Nowy interfejs zastępuje stary w tym samym katalogu `frontend/`; launcher, skrypty npm i ścieżki danych bez zmian.
- Stary kod (`main.ts`, obecne `style.css`, `storage.ts`, części `model.ts`) usuwany dopiero, gdy lista kontrolna jest zielona.
- Niezacommitowane zmiany właściciela (tryb LAN w `launcher/launcher.pyw` i `frontend/package.json`, `frontend/README.md`, `docs/Borowik_opis_techniczny_i_walidacja.md`) nie są ruszane ani commitowane w ramach tej pracy.
- Dokumentacja: `frontend/README.md` (po uzgodnieniu z właścicielem, bo ma niezacommitowane zmiany), nowa notatka w `docs/archiwum/CODEX-HANDOFF.md`, raport z testów i zrzutów.
- Gotowe, gdy: wszystkie funkcje z rozdziału 2 działają na aktualnej analizie i starej migawce; testy backendu i frontendu przechodzą; `build` przechodzi; lista kontrolna i zrzuty są w raporcie.

## 12. Poza zakresem

- Zmiana wag opadu w modelu (K1) i przeliczenie klimatologii — osobna decyzja po sezonie.
- Osobny projekt interfejsu na telefon, tryb offline/PWA.
- Zapisane miejsca (usunięte), zarządzanie migawkami z poziomu aplikacji.
- Zmiany w eksporcie KMZ.
- Nowe składowe modelu i nowe źródła danych poza normą E-OBS w panelu pogody.
