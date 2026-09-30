# Raport: nowy frontend Borowika (1.10.2026)

Projekt: `docs/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md`.
Plan: `docs/superpowers/plans/2026-10-01-borowik-nowy-frontend.md`.
Gałąź: `nowy-frontend`.

## Co zmieniono

- Interfejs zbudowany od nowa w Preact + sygnały (`frontend/src/index.tsx`, `components/`, `state/`, `domain/`, `data/`, `map/`).
- `index.html` wskazuje nowe wejście. Tymczasowe `nowy.html` usunięte.
- Model i ranking się nie zmieniły. Eksport dostał tylko nowe pola (niżej).
- Panel pogody pokazuje fakty zamiast oceny:
  - nagłówek „N dni po większym deszczu · X mm w 26 dni (norma Y)”;
  - trzy liczby (opad 26 dni, ostatni większy deszcz, temperatura 20 dni);
  - porównanie z normą E-OBS 1991–2020;
  - wykres dziennego opadu z oknem 26 dni;
  - po rozwinięciu: ostrzeżenia, pasmo temperatury i tabela 7 dni prognozy.
- Mapa ma dwa tryby:
  - **Wynik**: 4 klasy procentowe, te same co w KMZ; zgodność pilnuje wspólny przykład testowy z Pythonem.
  - **Wilgotność**: ciągła skala.
- Warstwy dostępu są w okienku „Warstwy” na mapie. Legenda jest w lewym dolnym rogu.
- Karty rejonu i wydzielenia mają:
  - paski Siedlisko / Pogoda / Spokój z opisami;
  - drzewostan z wiekiem i typem siedliska;
  - dojazd, dane, „Nawiguj” i „Kopiuj współrzędne”.
- Wydzielenie poza filtrami modelu dostaje kartę z powodami wykluczenia.

### Nowe pola eksportu

| Plik | Pole | Treść |
|---|---|---|
| `scores_*.json` | `mask_reason` | lista kodów: `not_dstan`, `no_age`, `too_young`, `excluded_species`, `gdos`, `zakaz` (pusta w masce) |
| `details_*.json` | `site_type` | `{code, label}` ze słownika BDL |
| `details_*.json` | `age_years` | wiek drzewostanu (liczba całkowita) |
| `conditions_*.json` | `lookback_days`, `daily` | 35 dni wstecz + prognoza: opad (radar/model/prognoza), temperatury |
| `conditions_*.json` | `rain26` | suma 26 dni, norma E-OBS 1991–2020 (±15 dni roku, komórki w promieniu), percentyl |
| `conditions_*.json` | `warnings` | przymrozek, upał z suszą, ulewa (z datami) |

Starsze migawki bez tych pól wczytują się normalnie (tryb zgodności).

## Dane do sprawdzenia

Za zgodą właściciela przeliczono bieżącą analizę:

```bash
prepare_trip --lat 50.6191 --lon 18.4611 --radius-km 20
npm run sync-data
```

Wynik (dzień 2026-10-01):
- 14 347 z 19 297 wydzieleń w masce, 5 rejonów;
- `daily`: 42 wiersze;
- opad 26 dni 55,9 mm przy normie 45,9 mm (percentyl 0,64, 16 komórek E-OBS);
- ostrzeżenia obecne;
- typ siedliska z nazwą;
- powody spoza filtrów: too_young 4735, not_dstan 2938, excluded_species 217.

## Lista kontrolna (Chrome, `http://127.0.0.1:5190`)

| # | Pozycja | Wynik | Jak sprawdzono |
|---|---|---|---|
| 1 | Brak hasła i nagłówka strony; mapa od góry | OK | zrzuty |
| 2 | Data analizy w pasku górnym | OK | „Aktualna analiza · 20 km · 1 października 2026” |
| 3 | Panel pogody | OK | nagłówek z faktami, 3 liczby, norma, wykres; rozwinięcie z ostrzeżeniami, pasmem temperatury (linia 13 °C) i tabelą 7 dni z niepewnymi dniami (`nowy-pulpit-pogoda-rozwinieta.jpg`) |
| 4 | Baner „skład tylko z WFS” | usunięty — **pytanie** | źródło składu jest w karcie wydzielenia, wiersz „Skład drzew” (np. „opis WFS (tylko gatunek panujący)” albo „paczka BDL z 23 czerwca 2026”); patrz pytania |
| 5 | „Analiza” w pasku górnym | OK | migawka Będziemyśl 26.09 wczytuje się; „Aktualna” wraca |
| 6 | Bez „Zapisane” / „Zapisz miejsce” | OK | na kartach są „Nawiguj” i „Kopiuj współrzędne” |
| 7 | Przełącznik presji | OK | przelicza rejony, klasy mapy i legendę („Wynik” / „Wynik bez presji”); stan zapamiętany; przełączenie ok. 80 ms |
| 8 | Zakładki z liczebnościami | OK | „Rejony (5)”, „Wydzielenia (14 347)” |
| 9 | Karta rejonu | OK | paski z mediany 5 najlepszych wydzieleń, dojazd rejonu, lista wydzieleń (`nowy-pulpit-karta-rejonu.jpg`) |
| 10 | Karta wydzielenia | OK | paski z opisami (np. „sosna 100% · Bór mieszany świeży · 67 lat”), drzewostan z wiekiem i siedliskiem, dojazd, dane (`nowy-pulpit-karta-wydzielenia.jpg`) |
| 11 | Bez „pewności” i zdań uzasadnień | OK | brak na kartach (także w starej migawce) |
| 12 | Tryby mapy Wynik / Wilgotność | OK, uwaga | 4 klasy jak w KMZ + „poza filtrami modelu”; wilgotność w skali ciągłej. Uwaga: przełączenie trybu przy dużym przybliżeniu przerysowuje mapę kafelkami, pełny obraz nawet po ponad 12 s (ograniczenia) |
| 13 | Okienko „Warstwy” | OK | przełączanie działa w przeglądarce (`nowy-pulpit-wilgotnosc-warstwy.jpg`); zapamiętanie wyboru pokrywa test `map-ui.test.tsx` |
| 14 | Legenda w lewym dolnym rogu | OK | zmienia się z trybem („Wilgotność (model)” ze skalą) i presją |
| 15 | Obrys wybranego wydzielenia, numery rejonów | OK | pomarańczowy obrys; znaczniki 1–5 z etykietami „Rejon N”; klik w znacznik otwiera kartę rejonu (test `map-ui.test.tsx`) |
| 16 | „Pokaż cały obszar” | OK | przybliża do całej analizy |
| 17 | „O danych” | OK | okno z treścią, podziękowaniem E-OBS i cytowaniem Cornes i in. 2018 |
| 18 | Lista/Mapa na telefonie | OK po poprawce | ramka 390 px: dwie zakładki „Lista” / „Mapa”. Znaleziono poziome przewijanie (pasek górny 507 px) i poprawiono. Przełączenie na kartę po kliknięciu na mapie pokrywają testy `store.test.ts` i `shell.test.tsx` |
| 19 | Nota o modelu na dole panelu | OK | „Model ekspercki, nieskalibrowany…” |
| 20 | Klik na mapie bez zmiany przybliżenia | OK | test `map-ui.test.tsx`; karta wydzielenia poza filtrami z powodami — test `cards.test.tsx` |

Stara migawka (Będziemyśl 26.09, bez pliku warunków):
- wczytuje się bez błędów w konsoli;
- panel pogody jest ukryty, bo migawka nie ma danych pogody;
- przełącznik presji i tryb Wilgotność są nieaktywne;
- karta wydzielenia działa, bez nowych pól.

## Poprawki znalezione w przeglądarce

Każda poprawka, z wyjątkiem CSS dla telefonu, ma test napisany przed zmianą (RED → GREEN).

1. **Przełącznik presji blokował stronę na ok. 3,3 s.** Przy każdej zmianie klas cała geometria (ok. 23 MB) szła od nowa do MapLibre.
   - Teraz geometria jest wysyłana raz na analizę.
   - Klasa i numer rejonu idą jako stan obiektu mapy (`feature-state`, `promoteId: "stand_id"`).
   - Przełączenie trwa ok. 80 ms.
2. **Po otwarciu karty panel zostawał przewinięty w środku.** Teraz każda zmiana widoku (lista, rejon, wydzielenie) zaczyna od góry.
3. **Przy zmianie analizy pasek górny mieszał nazwę nowej migawki z datą poprzedniej.** Podczas wczytywania pokazuje „Wczytywanie analizy…”.
4. **Na telefonie (390 px) strona przewijała się w poziomie.** Lista analiz ma teraz stałą szerokość 260 px. Zmiana tylko w CSS: lista zwęża się na wolne miejsce, a napis „Analiza” zostaje dla czytników ekranu.
   - Sprawdzone pomiarem w przeglądarce: szerokość dokumentu 507 → 390 px.
   - Brak testu jednostkowego: jsdom nie liczy układu strony.

## Testy

- `pytest`: 902 passed.
- `vitest`: 219 passed (15 plików).
- `tsc --noEmit`: bez błędów.
- `npm run build`: bez błędów. Ostrzeżenie o dużym pakiecie (MapLibre) jak wcześniej.

## Zrzuty (`docs/ui-zrzuty/`)

- `nowy-pulpit-pogoda-rozwinieta.jpg`: rozwinięty panel pogody i cały obszar z rejonami i warstwami dostępu.
- `nowy-pulpit-karta-rejonu.jpg`: karta rejonu 1 z paskami i dojazdem.
- `nowy-pulpit-karta-wydzielenia.jpg`: karta najlepszego wydzielenia z obrysem na mapie.
- `nowy-pulpit-wilgotnosc-warstwy.jpg`: tryb Wilgotność z legendą i okienkiem „Warstwy”, w trakcie przerysowywania kafelków.
- `nowy-pulpit-rejony-pierwsze-rysowanie.jpg`: lista rejonów tuż po wczytaniu. Mapa jest jeszcze pusta, bo pierwsze rysowanie trwa kilka sekund.

Zrzutów widoku telefonu nie ma. W trakcie tej części rozszerzenie Chrome się rozłączyło, a sesja przełączyła się na inną przeglądarkę, która nie widzi lokalnego serwera. Układ telefonu sprawdzono pomiarami w ramce 390 px przed rozłączeniem.

## Ograniczenia

- **Model bez zmian.** Mapa wilgotności pokazuje M z wagami K0. Najmocniej liczy się ostatni deszcz, więc mapa może różnić się od wymowy panelu pogody; legenda to mówi.
- **Pierwsze rysowanie mapy trwa kilka sekund** po wczytaniu lub zmianie analizy, bo MapLibre kafelkuje ok. 23 MB geometrii (19 297 wielokątów). Strona w tym czasie odpowiada.
- **Zmiana trybu mapy** (Wynik ↔ Wilgotność) przy dużym przybliżeniu przerysowuje kafelki stopniowo: pełny obraz nawet po ponad 12 s. Wątek główny nie jest blokowany (brak długich zadań), ale przez chwilę część mapy ma stare kolory.
  - Możliwa poprawka na później: kafle wektorowe zamiast jednego GeoJSON albo przełączanie trybu przez stan obiektu, jak przy presji.
- **`details.json` ma ok. 45 MB.** Parsowanie w przeglądarce trwa ok. 0,3 s. Plik wczytuje się w tle po liście i mapie.

## Decyzje doprecyzowane w trakcie

- Kliknięcie wydzielenia na mapie zastępuje kartę wydzielenia na wierzchu stosu, zamiast dokładać kolejną. „Wróć” prowadzi do listy albo karty rejonu.
- Przełączenie presji zamyka kartę rejonu. Rejony z presją i bez niej mają te same identyfikatory (`region_1`…), ale to inne rejony.
- Domyślnie włączone warstwy dostępu (parkingi, wjazdy, drogi leśne) zostały bez zmian. Test Fazy 3.5 przypina je jako decyzję; patrz pytania.

## Pytania do właściciela

1. **Baner „skład tylko z WFS”.** Nowy interfejs go nie ma; źródło składu widać w karcie wydzielenia. Przywrócić baner dla analiz bez paczki BDL?
2. **Domyślne warstwy dostępu.** W widoku całego obszaru setki punktów parkingów i wjazdów zasłaniają klasy wydzieleń (zrzut z rozwiniętą pogodą). Czy domyślnie wyłączyć punkty i drogi (włączać je dopiero przy karcie lub przybliżeniu)? Wybór użytkownika i tak jest zapamiętywany.
3. **Wydajność mapy.** Czy czas pierwszego rysowania i zmiany trybu (kilka–kilkanaście sekund przy 20 km) jest do przyjęcia, czy warto zaplanować kafle wektorowe?
