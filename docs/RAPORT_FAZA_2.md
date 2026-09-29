# Raport Fazy 2 — kontrole wiarygodności i przygotowanie walidacji

Stan: 29.09.2026, gałąź `ulepszenia-faza2`. Zrealizowane: 2.0 (reguły zatwierdzone), 2.1, 2.2, 2.3, 2.4, 2.5, 2.6 oraz `scripts/zapisz_prognoze.py`. Nie ruszane na polecenie właściciela: 2.7, 2.8.

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 2.0 Reguły decyzyjne | ZATWIERDZONE (wersja 2, commit `6d9349a`, przed analizą) | `docs/WALIDACJA_REGULY.md`, doprecyzowania: `docs/WALIDACJA_IMPLEMENTACJA.md` |
| 2.1 Zapis własnych wyjść | DONE | `pipeline/field_data.py`, `scripts/sprawdz_dane_terenowe.py`, `docs/ZAPIS_WYJSC.md`, szablony w `dane_terenowe_szablony/`, przypomnienie w launcherze, `dane_terenowe/` w `.gitignore`; 4 testy |
| 2.2 Archiwum prognoz | DONE | `pipeline/forecast_archive.py`, wywoływane z `fetch_weather_raw`; `cache/archiwum_prognoz/prognoza_RRRR-MM-DD.parquet`; 3 testy |
| 2.3 Inwentaryzacja GBIF | DONE | `notebooks/10_gbif_inventory.py`, `notebooks/11_gbif_edulis_forest_coverage.py`; wyniki poniżej |
| 2.4 Kontrola przestrzenna H | DONE | wynik: „zgodne z modelem” (AUC 0,57 / 0,61), patrz niżej |
| 2.5 Kontrola czasowa F | DONE | wynik: „brak rozróżnienia”, bez czerwonej flagi, patrz niżej |
| 2.6 E-OBS lokalnie | DONE (bez zmiany produkcji) | `pipeline/eobs.py`, `scripts/pobierz_eobs.py`, `cache/eobs/` (12 plików, 456 MB); porównanie rozkładów percentyli ze stanem obecnym nie wykonane, więc produkcja pozostaje na ERA5 |
| `scripts/zapisz_prognoze.py` | DONE | 4 punkty w `dane_terenowe/punkty_prognozy.json`; harmonogram Windows do zainstalowania ręcznie wg `docs/ZAPIS_WYJSC.md` |
| 2.7, 2.8 | nie ruszane (decyzja właściciela) | 2.7 wymaga ≥ 30 dni archiwum z 2.2 (archiwum zaczęło się 28.09) |

Uwaga do 2.2: archiwum zapisuje prognozę przy każdym pobraniu z Open-Meteo (od dnia pobrania wzwyż, z `fetched_at` i `forecast_days`), jeden plik na dzień; punkty już zapisane danego dnia nie są nadpisywane. Punkt dopisany później tego samego dnia z cache dostaje znacznik czasu późniejszego przebiegu — dla 2.7 istotna jest data wydania (dzień), nie godzina. Archiwum leży poza `cache/weather_points`. Prognozy sprzed dziś (28.09) nie istnieją — licznik dni zaczyna się od dziś. W dni bez analizy prognozę zapisuje `scripts/zapisz_prognoze.py` (punkty w `dane_terenowe/punkty_prognozy.json`: Kieleczka, Lubliniec, Krupski Młyn, Będziemyśl; harmonogram Windows na 6:00 do zainstalowania ręcznie wg `docs/ZAPIS_WYJSC.md`, do tego czasu archiwum rośnie tylko przy analizach i ręcznych uruchomieniach skryptu).

## 2.3 Inwentaryzacja rekordów GBIF (bez testów skuteczności)

Źródło: fasety API GBIF (zapytania z 28.09.2026, `hasCoordinate=true`, `hasGeospatialIssue=false`). Wartości niepewności są **skumulowane** (≤ 100 m zawiera ≤ 25 m).

### Boletus edulis

| | Polska | RDLP Katowice + 25 km |
|---|---|---|
| Rekordów | 1167 | 150 |
| niepewność ≤ 25 m | 196 | 38 |
| ≤ 100 m | 360 | 52 |
| ≤ 1000 m | 614 | 83 |
| brak wartości niepewności | 277 | 36 |
| z iNaturalist | 1073 (92%) | 144 (96%) |
| różnych obserwatorów (pole `recordedBy`) | 341 | 69 |
| udział 5 najaktywniejszych | 41% | 39% |

Rekordy ≤ 100 m w Polsce (360): 153 obserwatorów, wszystkie z pełną datą; lata: 2015–2021 po 1–14 rekordów, 2022: 30, 2023: 38, **2024: 110, 2025: 101**, 2026: 40 (59% w dwóch latach).

Położenie tych 360 rekordów względem BDL (zapytania WFS z buforem 150 m, `notebooks/11_…`): **274 w lesie D-STAN (76%), 85 bez wydzieleń BDL** (prawdopodobnie lasy prywatne/poza zasięgiem BDL), 1 w innych wydzieleniach; 274 rekordy pochodzą od **110 różnych obserwatorów**. Rozróżnienie „paczki / tylko WFS” nie zostało policzone — paczki są tylko dla nadleśnictw właściciela. Dla regionu Katowice nie liczono pokrycia leśnego (52 rekordy ≤ 100 m, poniżej progu 100 już przed filtrem leśnym).

### Tło „inne grzyby” i „niegrzybowe” (potrzebne w 2.4/2.5)

| Tło | Polska: rekordów | ≤ 100 m | obserwatorów | RDLP Katowice + 25 km: rekordów | ≤ 100 m | obserwatorów |
|---|---|---|---|---|---|---|
| Grzyby ogółem (zawiera B. edulis) | 328 488 | 32 609 | 6538 | 39 925 | 5094 | 1268 |
| Rośliny | 6 617 769 | 1 008 627 | 29 609 | 1 255 613 | 160 803 | 7244 |
| Zwierzęta | 9 951 048 | 386 543 | 44 385 | 1 510 508 | 54 171 | 8925 |

Tła są liczne, więc ich liczebność nie ogranicza testów; ograniczeniem jest liczba rekordów borowika. Pełne rozkłady roczne i miesięczne: `notebooks/output/gbif_inventory.json` (poza repo).

### Werdykt wobec progów z projektu 2.0 (wszystko warunkowe do jego zatwierdzenia)

- **2.4 (≥ 100 rekordów ≤ 100 m w lesie z danymi BDL, ≥ 30 obserwatorów):** próg **spełniony dla całej Polski** (274 rekordy, 110 obserwatorów) — uruchamiać **po zatwierdzeniu 2.0**; **niespełniony dla samego regionu Katowice** (52 rekordy ≤ 100 m). Test ma więc sens jako ogólnopolski, nie jako kontrola regionu właściciela. Przed uruchomieniem trzeba pobrać wydzielenia BDL także dla lasów poza paczkami właściciela (składy z WFS), więc H w tym teście opiera się głównie na składzie WFS, nie paczkach.
- **2.5 (≥ 150 rekordów z pełną datą, ≥ 5 lat):** próg **spełniony** (1167 rekordów w Polsce; wśród rekordów ≤ 100 m 360 z pełną datą z 12 lat). Uruchamiać po zatwierdzeniu 2.0, po uwzględnieniu skrzywienia czasowego (59% w latach 2024–2025).

## 2.4 Kontrola przestrzenna H (wynik analizy głównej)

Jeden przebieg według `docs/WALIDACJA_REGULY.md`; kod: `notebooks/13_walidacja_2_4.py`, `pipeline/spatial_check.py`. Wyniki: `notebooks/output/walidacja/2_4_wynik.json` (poza repo).

- Pozytywy: 360 rekordów *B. edulis* ≤ 100 m → 246 w lesie D-STAN → 229 po deduplikacji → **210 od 2021 roku od 90 obserwatorów** (progi ≥ 100 rekordów i ≥ 30 obserwatorów spełnione). Rekordy w wydzieleniach niespełniających maski (H = 0): 2. Nieznany kod siedliska/gatunku: 17,0% (< 20%, więc nie pomijano).
- H ze składu WFS dla wszystkich rekordów.

| Analiza | Tło | AUC(H) | 95% CI (bootstrap po obserwatorach) | n tła |
|---|---|---|---|---|
| **główna (od 2021)** | (a) inne grzyby w lesie | 0,571 | 0,529–0,609 | 1024 |
| **główna (od 2021)** | (b) rośliny/zwierzęta VII–XI | 0,611 | 0,557–0,661 | 329 |
| wariant: wszystkie lata | (a) | 0,569 | 0,533–0,609 | 1104 |
| wariant: wszystkie lata | (b) | 0,635 | 0,581–0,685 | 522 |

**Wynik wg reguł: „zgodne z modelem”** (cały CI > 0,5 w obu tłach). Siła efektu jest jednak niewielka (AUC 0,57–0,61): H jest wyższe w miejscach znalezisk borowika niż w tle, ale słabo rozróżnia. Wariant z paczkami BDL (Katowice, opisowo): tylko 4 rekordy pozytywne z pokryciem paczek, więc wynik nie niesie informacji (AUC 0,43 / 0,41 przeciw tłu (a) dla WFS / paczek, 0,50 / 0,53 dla tła (b)).

Odstępstwa i uwagi wykonawcze:
- Tło (b) ma 329 rekordów w lesie zamiast limitu 5 × 246, bo rośliny i zwierzęta rzadko leżą w lesie D-STAN przy przyjętym rozmiarze próbki kandydatów. Próbka (b) jest więc mniejsza niż zaplanowano; CI to uwzględnia.
- Próbkowanie tła (b) zmieniono przed liczeniem AUC (400 stron × 300 rekordów na królestwo, offsety do 20 000 zamiast 1200 stron i 100 000) z powodu nieużywalnie wolnych zapytań GBIF; zapisane w `docs/WALIDACJA_IMPLEMENTACJA.md`. Próbka pochodzi więc z początku kolejności GBIF w komórce rok × miesiąc, co nie jest pełną losowością.
- Przebieg był kilkukrotnie przerywany błędami sieci GBIF (żaden nie dotarł do liczenia metryk); wznawiany z cache, bez zmiany kryteriów.

## 2.5 Kontrola czasowa F (wynik analizy głównej)

Jeden przebieg (E-OBS, wariant główny: F bez G_season); kod: `notebooks/12_walidacja_2_5.py`, `pipeline/eobs_fruiting.py`. Pierwsza próba uruchomienia przerwała się błędem sieci przed obliczeniem jakiejkolwiek metryki.

- Rekordy: 1167 w GBIF → 614 z niepewnością ≤ 1000 m i pełną datą → 561 w zakresie E-OBS (wykluczone 53 rekordy z 2026 roku, bo E-OBS v33.0e kończy się 31.12.2025) → **482 po deduplikacji** → 476 z pełnym oknem pogodowym (tło a), 11 lat; tło (b): 269 rekordów, pominięto 207 (< 3 dni kontrolne z innymi grzybami w promieniu 20 km).

| Wariant | Tło (a): średnia ranga (95% CI) | Tło (b): średnia ranga (95% CI) |
|---|---|---|
| **F bez G_season (główny)** | **0,529 (0,501–0,554)** | **0,527 (0,485–0,567)** |
| F z G_season | 0,540 (0,513–0,564) | 0,528 (0,488–0,568) |
| sam kalendarz | 0,551 (0,537–0,572) | 0,522 (0,496–0,552) |
| samo M | 0,510 (0,478–0,534) | 0,517 (0,479–0,557) |
| sama T | 0,553 (0,530–0,583) | 0,540 (0,504–0,578) |
| model stały (referencja) | 0,500 | 0,500 |

Różnica (F bez G_season − sam kalendarz): tło (a) −0,023 (−0,063…0,013), tło (b) +0,005 (−0,044…0,051).

**Wynik wg reguł: „brak rozróżnienia”** (CI w tle (a) ledwie powyżej 0,5, w tle (b) obejmuje 0,5). **Dodatkowa czerwona flaga: nie** (CI różnicy nie leży w obu tłach poniżej zera). Poziom sygnału jest bardzo niski: żaden wariant nie przekracza średniej rangi 0,56, a sama temperatura i sam kalendarz wypadają nie gorzej niż pełny F. Zgodnie z regułami nie dostraja się F na tych danych; wynik jest materiałem do decyzji na sesji z właścicielem, nie podstawą zmiany.

Zastrzeżenia: tło (a) jest zawyżone (ludzie chodzą do lasu, gdy spodziewają się grzybów), tło (b) zaniżone; sygnał M pochodzi w praktyce z samego opadu (E-OBS nie ma wilgotności gleby, `soil_moisture_weight` = 0); ET0 z Hargreaves-Samani, nie z ERA5; klasa wilgotności siedliska przyjęta jako 1 (jak w notatniku 03).

## Czego te testy nie pokazują

- GBIF zawiera tylko znaleziska. Nie wiadomo, gdzie i kiedy szukano bez skutku, ani ile czasu na to poświęcono, więc **nie da się rzetelnie zmierzyć, czy aplikacja wskazuje miejsca z większą liczbą borowików**.
- Inwentaryzacja niczego nie mówi o jakości modelu; jest tylko warunkiem sensowności późniejszych kontroli.
- 92% rekordów to iNaturalist, a pięciu najaktywniejszych obserwatorów daje 41% rekordów w Polsce — rekordy jednej osoby nie są niezależne.
- Liczba obserwatorów pochodzi z pola `recordedBy` (pisownie tej samej osoby mogą się różnić; rekordy bez pola nie są liczone).
- Miejsca znalezisk zależą od tego, gdzie chodzą ludzie (drogi, parkingi), co jest skorelowane z P i z dostępnością.
- Rekordy ≤ 100 m są silnie skupione w latach 2024–2025.
- 2.4: tło (b) próbkowane z początku kolejności GBIF w komórkach rok × miesiąc i mniejsze niż planowano (329 zamiast limitu 1230 rekordów w lesie); H liczone z WFS, więc nie testuje pełnego składu z paczek.
- 2.5: wyniki oparte na E-OBS 0,1° (ok. 10 km), grubszej niż opad z radaru używany w produkcji; brak wilgotności gleby.
- 2.5 (a) **Mała moc testu dla M.** Dni kontrolne ±15 dni dzielą większość 26-dniowego okna (CWB26) z dniem znaleziska, więc M zmienia się między nimi niewiele i test ma z natury małą moc do wykrycia efektu wilgotności; „samo M ≈ 0,51” nie dowodzi braku znaczenia wilgotności.
- 2.5 (b) **Remisy z nasycenia M.** Przy nasyceniu M (wysoki percentyl CWB26 w mokrym okresie) wiele dni ma tę samą wartość, a remisy liczą się jako 0,5, co ściąga średnią rangę ku 0,5 niezależnie od jakości modelu.
- 2.5 (c) **G_season pochodzi z tych samych danych GBIF.** Krzywa sezonowości była dopasowana do rozkładu miesięcznego rekordów GBIF, więc wariant „sam kalendarz” (i F z G_season) ma przewagę i nie jest niezależnym testem; wariant główny bez G_season właśnie dlatego jest głównym.

## Następne kroki
1. Sesja z właścicielem: co robić z wynikiem 2.5 („brak rozróżnienia”) i słabym AUC w 2.4. Reguły nie przewidują automatycznej zmiany modelu.
2. Zainstalować harmonogram `Borowik-prognoza` (polecenie w `docs/ZAPIS_WYJSC.md`); po ≥ 30 dniach archiwum (od ok. 28.10) można uruchomić 2.7.
3. Porównać rozkłady percentyli E-OBS i ERA5, zanim produkcja przejdzie na E-OBS (reszta 2.6).
4. `netCDF4` dopisano do `pyproject.toml`, ale `uv.lock` wymaga przeliczenia poleceniem `uv lock` (w tym środowisku brak `uv` w PATH; pakiet zainstalowano przez pip w `.venv`).
