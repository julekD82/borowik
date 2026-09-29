# Raport Fazy 2 — kontrole wiarygodności i przygotowanie walidacji

Stan: 29.09.2026. Faza 2 (gałąź `ulepszenia-faza2`) jest scalona do `master`; zrealizowane: 2.0 (reguły zatwierdzone), 2.1, 2.2, 2.3, 2.4, 2.5, 2.6 oraz `scripts/zapisz_prognoze.py`. Nie ruszane na polecenie właściciela: 2.7, 2.8. Decyzja właściciela po walidacji (domyślny `habitat.age_mode: neutral`) jest wdrożona na gałęzi `ulepszenia-wiek` — patrz „Decyzje po walidacji”.

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

## 2.4 — analiza EKSPLORACYJNA: która część H niesie sygnał

**Eksploracyjna, po zobaczeniu wyników 2.4; nie wpływa na decyzje wg reguł 2.0** (bez uzasadnienia dla zmiany wag). Kod: `notebooks/14_eksploracja_h.py`. Te same zamrożone rekordy i tła co analiza główna 2.4 (od 2021 r.: 210 pozytywów, tło (a) 1024, tło (b) 329). Zbiory nie zawierały atrybutów wydzieleń, więc odtworzono je ponownym, małym zapytaniem BDL WFS per rekord (za zgodą właściciela; bez GBIF, bez nowego losowania). Kontrola: H odtworzone z atrybutów różni się od zamrożonego o ≤ 3·10⁻¹⁶, AUC(H) = 0,571 / 0,610 jak w 2.4. CI: bootstrap po obserwatorach, 1000 powtórzeń (w 2.4 było 2000).

| Miara | AUC vs tło (a) inne grzyby | AUC vs tło (b) rośliny/zwierzęta |
|---|---|---|
| H (całość) | 0,571 (0,529–0,609) | 0,610 (0,555–0,662) |
| S_host | 0,569 (0,530–0,609) | 0,577 (0,534–0,632) |
| S_site | 0,561 (0,503–0,601) | 0,628 (0,559–0,680) |
| S_age | 0,486 (0,446–0,538) | 0,498 (0,452–0,562) |
| udział sosny+świerka (SO, SW; z WFS: `part_cd`/10 dla panującego SO/SW, inaczej 0) | 0,571 (0,521–0,616) | 0,570 (0,516–0,630) |
| binarnie panujący SO lub SW | 0,549 (0,505–0,588) | 0,531 (0,484–0,583) |
| sam wiek (lata, po przeliczeniu na 2026; im więcej, tym wyższa wartość) | **0,403** (0,360–0,457) | **0,424** (0,373–0,485) |

Odczyt opisowy (bez wniosków o skuteczności): sygnał H pochodzi głównie ze składu gatunkowego (S_host) i siedliska (S_site); S_age nie odróżnia miejsc znalezisk od tła (≈ 0,49–0,50). Sam wiek ma AUC poniżej 0,5: wydzielenia ze znaleziskami są średnio **młodsze** niż tło, czyli w tych danych nie ma podstaw do zakładania, że starsze drzewostany są bardziej wiązane ze znaleziskami; krzywa S_age pozostaje więc hipotezą bez poparcia w tej próbie (mogą działać efekty dostępności: młodsze drzewostany są częściej przy drogach, oraz zmiana wieku względem „wiek z opisu”). Udział sosny+świerka jest tak samo informatywny jak cały S_host, ale to zbieżność w małej próbie. Wielokrotne testowanie: 7 miar × 2 tła bez korekty. WFS zawiera tylko gatunek panujący z `part_cd`, więc „udział sosny+świerka” to przybliżenie, nie skład z paczek.

## 2.4 — kody siedlisk i gatunków nieznane profilowi

Zliczenie w zamrożonych rekordach 2.4 od 2021 r. (rekordów z co najmniej jednym wydzieleniem w buforze przechodzącym maskę z tym kodem; jeden rekord może mieć kilka kodów). Profil nie był zmieniany.

| Kod | Rodzaj | Pozytywy | Tło (a) | Tło (b) |
|---|---|---|---|---|
| LGSW | siedlisko | 19 | 60 | 27 |
| LMGSW | siedlisko | 11 | 40 | 37 |
| BMGSW | siedlisko | 8 | 15 | 9 |
| BGSW | siedlisko | 0 | 3 | 0 |
| LGW | siedlisko | 0 | 3 | 7 |
| LLG | siedlisko | 0 | 2 | 3 |
| LMGW | siedlisko | 0 | 2 | 1 |
| BMGW | siedlisko | 1 | 0 | 0 |
| BMWYZW, BWG | siedlisko | 0 | 1 + 1 | 1 + 1 |
| BMGB | siedlisko | 0 | 1 | 0 |
| BST | gatunek | 0 | 1 | 0 |

Nieznanych kodów jest 17,0% pozytywów (poniżej progu 20%, więc analiza główna ich nie pomijała). Prawie wszystkie to kody siedlisk z „G” w środku (prawdopodobnie warianty górskie, np. LGSW, LMGSW, BMGSW; interpretacja kodów do potwierdzenia w słowniku BDL, nie w profilu). Zaznaczam: takie wydzielenia dostają `unknown_site_score` z profilu.

Przebieg Kieleczki (manifesty w `docs/porownania/{nowy,faza1_5,faza1_6}/`): `unknown_site_count` = 0 i `unknown_species_count` = 0 (19 716 wydzieleń); problem kodów nieznanych dotyczy więc obszarów górskich/podgórskich z 2.4, nie Kieleczki.

## 2.4 — analiza EKSPLORACYJNA: wiek i tryb `habitat.age_mode`

**Eksploracyjna, po zobaczeniu wyników 2.4; nie wpływa na decyzje wg reguł 2.0.** Kod: `notebooks/15_eksploracja_wiek.py`, wyniki: `notebooks/output/walidacja/eksploracja_wiek.json` (poza repo). Te same zamrożone rekordy i atrybuty WFS co w poprzedniej analizie eksploracyjnej (od 2021 r.: 210 pozytywów, tło (a) 1024, tło (b) 329).

### (a) Rozkład wieku wydzieleń (po przeliczeniu na 2026, średnia ważona powierzchnią bufora)

| Klasa wieku | Pozytywy | Tło (a) inne grzyby | Tło (b) rośliny/zwierzęta |
|---|---|---|---|
| < 12 | 2 (1,0%) | 17 (1,7%) | 6 (1,8%) |
| 12–20 | 5 (2,4%) | 26 (2,5%) | 11 (3,3%) |
| 20–40 | 28 (13,3%) | 73 (7,1%) | 22 (6,7%) |
| 40–60 | 47 (22,4%) | 129 (12,6%) | 45 (13,7%) |
| 60–80 | 44 (21,0%) | 230 (22,5%) | 86 (26,1%) |
| 80–100 | 39 (18,6%) | 223 (21,8%) | 66 (20,1%) |
| 100–120 | 24 (11,4%) | 164 (16,0%) | 47 (14,3%) |
| > 120 | 21 (10,0%) | 162 (15,8%) | 46 (14,0%) |
| **mediana (Q1–Q3)** | **69,0 (46,9–91,3)** | **82,3 (61,0–107,0)** | **78,0 (59,2–104,3)** |

Podział na gatunek panujący (największe wydzielenie w buforze), tylko klasy z ≥ 20 rekordami: **sosna** pozytywy 40–60: 29, 60–80: 26, 80–100: 27 (mediana wieku 65,7; Q1–Q3 45,5–87,7; n = 118); tło (a) 20–40: 42, 40–60: 74, 60–80: 130, 80–100: 106, 100–120: 73, > 120: 50 (mediana 75,0); tło (b) 40–60: 21, 60–80: 40, 80–100: 33, 100–120: 20 (mediana 72,6). **Świerk**: w żadnej klasie nie ma ≥ 20 rekordów (pozytywy n = 17; tło (a) n = 54, mediana 70,8; tło (b) n = 45, mediana 72,0), więc rozkładu klasowego nie podaję. Odczyt opisowy: pozytywy są przesunięte ku młodszym klasom (20–60 lat: 36% wobec 20% w obu tłach) i rzadziej występują w drzewostanach > 100 lat (21% wobec 32% / 28%); podobnie wśród samych sosen (mediana 65,7 wobec 75,0 / 72,6). Nie oznacza to, że młodsze drzewostany są „lepsze”: możliwe jest skrzywienie dostępnością (młodsze drzewostany blisko dróg i osad, gdzie ludzie chodzą).

### (b) Przełącznik `habitat.age_mode` (`curve` / `neutral`; w chwili tej analizy domyślny był `curve`, od decyzji poniżej domyślny jest `neutral`)

Dodano do profilu (wtedy `habitat.age_mode: curve`, kod w `pipeline/habitat.py::score_age`): `neutral` daje S_age = 1 dla każdego wydzielenia przechodzącego maskę wieku (< 12 lat nadal odpada; również bez kary 0,9 dla > 120 lat). W tej analizie domyślny tryb nie był zmieniany (zmianę wprowadza dopiero decyzja właściciela poniżej). 4 nowe testy w `tests/test_habitat.py`.

- **AUC(H) na zamrożonych danych:** `neutral`: 0,574 (CI 0,528–0,611) vs tło (a), 0,615 (0,556–0,668) vs tło (b); `curve` (2.4): 0,571 i 0,610. Różnica pomijalna (o 0,003–0,005 na korzyść `neutral`, dużo poniżej szerokości CI).
- **Przebieg Kieleczki offline** (`docs/porownania/faza1_6`; R = 100·H·F_loc·(1 − αP), H bez S_age; bez zmiany F_loc, P i maski). Kontrola: odtworzone R w trybie `curve` równa się R z eksportu (maks. różnica 0,0) i odtworzone rejony mają te same rozmiary co zapisane (23/21/15/13/38):

| Miara | Wynik `neutral` względem `curve` |
|---|---|
| Spearman R (14 399 wydzieleń w masce) | 0,952 |
| wspólne w top-20 (wszystkie wydzielenia / tylko ≥ 0,5 ha) | 10 / 11 z 20 |
| rejony | 5 vs 5; wspólnych wydzieleń 78 ze 110 w rejonach `curve`; jeden rejon `curve` (21 wydzieleń) nie ma odpowiednika (0 wspólnych), pozostałe: 23/23, 15/15, 13/13 i 27/38 wspólnych |
| mediana H | 0,860 w obu trybach (mediana wydzieleń ma S_age = 1 już w `curve`) |

`neutral` zmienia więc ranking umiarkowanie (połowa top-20), głównie przez usunięcie kar za drzewostany młodsze niż 35 lat i starsze niż 120 lat. Wynik dotyczy jednego przebiegu (Kieleczka) i jest zależny od kształtu krzywej; nie jest oceną skuteczności żadnego trybu.

## Decyzje po walidacji

Decyzja właściciela (29.09.2026), wdrożona na gałęzi `ulepszenia-wiek`:

1. **`habitat.age_mode: neutral` staje się domyślny** (S_age = 1 dla wydzieleń spełniających maskę wieku). Tryb `curve` (dawna krzywa z `age_breakpoints`) zostaje dostępny przez profil. Maska < 12 lat bez zmian; przestaje obowiązywać także kara 0,9 dla drzewostanów > 120 lat. Zmiana obejmuje wszystko, co używa `score_age` (H, S_age w eksporcie i diagnostyce).
   **Uzasadnienie:**
   - S_age nie odróżnia miejsc znalezisk od tła (AUC 0,486 / 0,498, CI obejmują 0,5),
   - rozkład wieku znalezisk przeczy karze dla drzewostanów 12–35 lat (klasa 20–40 lat: 13,3% znalezisk wobec 7,1% i 6,7% w tłach),
   - to **usunięcie niepotwierdzonego założenia, nie dopasowanie nowej krzywej**; potwierdza to wcześniejsze stanowisko z `docs/projekt-borowik.md` (brak podstaw do penalizowania wieku 20–120 lat, funkcja „celowo płaska”).
   Skutek na Kieleczce (offline, z analizy eksploracyjnej): Spearman R 0,952 względem `curve`, 10 z 20 wspólnych w top-20, 78 ze 110 wydzieleń wspólnych w rejonach; AUC(H) na zamrożonych danych 0,574 / 0,615 (wobec 0,571 / 0,610).
2. **Świadomie NIE wprowadzamy krzywej faworyzującej 20–60 lat.** Byłoby to dopasowanie do analizy eksploracyjnej (te same dane, po zobaczeniu wyników, z możliwym skrzywieniem dostępnością — młodsze drzewostany blisko dróg). Ewentualne oceny wieku należą do Fazy 5 (dane terenowe z zerami).

Wpływ na analizy: wyniki 2.4 i 2.5 w tym raporcie były liczone przed tą zmianą; H w 2.4 (`curve`) i tryb `neutral` różnią się o ≤ 0,005 AUC. Manifest i diagnostyka nowych przebiegów odzwierciedlają tryb neutral (S_age = 1).

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
4. ~~`uv.lock`~~ — zrobione: `netCDF4` w `pyproject.toml` i `uv.lock` (`uv lock`, dodane tylko `cftime`, `netcdf4`, `networkx`; `uv` zainstalowany w `.venv` przez pip). `uv lock --check` bez zmian.
