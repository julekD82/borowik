# Raport Fazy 2 — kontrole wiarygodności i przygotowanie walidacji

Stan: 28.09.2026, gałąź `ulepszenia-faza2`. Zrealizowane: 2.1, 2.2, 2.3 i projekt 2.0 (do zatwierdzenia). Nie zrealizowane: 2.4–2.8 (patrz „Następne kroki”).

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 2.0 Reguły decyzyjne | PROJEKT — czeka na zatwierdzenie | `docs/WALIDACJA_REGULY.md`; **nie commitować analizy przed zatwierdzeniem** |
| 2.1 Zapis własnych wyjść | DONE | `pipeline/field_data.py`, `scripts/sprawdz_dane_terenowe.py`, `docs/ZAPIS_WYJSC.md`, szablony w `dane_terenowe_szablony/`, przypomnienie w launcherze, `dane_terenowe/` w `.gitignore`; 4 testy |
| 2.2 Archiwum prognoz | DONE | `pipeline/forecast_archive.py`, wywoływane z `fetch_weather_raw`; `cache/archiwum_prognoz/prognoza_RRRR-MM-DD.parquet`; 3 testy |
| 2.3 Inwentaryzacja GBIF | DONE | `notebooks/10_gbif_inventory.py`, `notebooks/11_gbif_edulis_forest_coverage.py`; wyniki poniżej |
| 2.4–2.8 | nie rozpoczęte | 2.4/2.5 wymagają zatwierdzenia 2.0; 2.7 wymaga ≥ 30 dni archiwum z 2.2 |

Uwaga do 2.2: archiwum zapisuje prognozę przy każdym pobraniu z Open-Meteo (od dnia pobrania wzwyż, z `fetched_at` i `forecast_days`), jeden plik na dzień; punkty już zapisane danego dnia nie są nadpisywane. Punkt dopisany później tego samego dnia z cache dostaje znacznik czasu późniejszego przebiegu — dla 2.7 istotna jest data wydania (dzień), nie godzina. Archiwum leży poza `cache/weather_points`. Prognozy sprzed dziś (28.09) nie istnieją — licznik dni zaczyna się od dziś. Aby zbierać dane w dni bez analizy, potrzebny jest opcjonalny skrypt harmonogramu (`scripts/zapisz_prognoze.py`, nie zrobiony).

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

## Czego te testy nie pokazują

- GBIF zawiera tylko znaleziska. Nie wiadomo, gdzie i kiedy szukano bez skutku, ani ile czasu na to poświęcono, więc **nie da się rzetelnie zmierzyć, czy aplikacja wskazuje miejsca z większą liczbą borowików**.
- Inwentaryzacja niczego nie mówi o jakości modelu; jest tylko warunkiem sensowności późniejszych kontroli.
- 92% rekordów to iNaturalist, a pięciu najaktywniejszych obserwatorów daje 41% rekordów w Polsce — rekordy jednej osoby nie są niezależne.
- Liczba obserwatorów pochodzi z pola `recordedBy` (pisownie tej samej osoby mogą się różnić; rekordy bez pola nie są liczone).
- Miejsca znalezisk zależą od tego, gdzie chodzą ludzie (drogi, parkingi), co jest skorelowane z P i z dostępnością.
- Rekordy ≤ 100 m są silnie skupione w latach 2024–2025.

## Następne kroki
1. **Właściciel zatwierdza lub poprawia `docs/WALIDACJA_REGULY.md`** (progi, ziarno losowania, definicja tła). Po zatwierdzeniu — commit reguł, dopiero potem 2.4 i 2.5.
2. Opcjonalnie `scripts/zapisz_prognoze.py` (harmonogram Windows, ≤ 10 punktów) — żeby archiwum rosło także w dni bez analizy; za 30 dni można uruchomić 2.7.
3. 2.6 (E-OBS lokalnie) — pobranie 0,1° dla Polski, niezależne od zatwierdzenia 2.0.
