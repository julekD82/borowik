# Walidacja 2.4 / 2.5 — decyzje implementacyjne (przed analizą)

Uzupełnienie `docs/WALIDACJA_REGULY.md` (zatwierdzone, commit `37c145c`). Dotyczy tylko szczegółów wykonania, które reguły pozostawiły otwarte; **nie zmienia progów, hipotez ani reguł decyzji**. Commit tego pliku poprzedza uruchomienie jakiejkolwiek analizy 2.4/2.5.

## Wspólne
- Ziarno losowania: 20260928. Bootstrap: 2000 powtórzeń, przedział percentylowy 2,5–97,5%.
- Zbiór rekordów po filtrach i deduplikacji jest zamrażany do pliku `notebooks/output/walidacja/*_zbior.csv` **przed** liczeniem metryk.
- Rekordy bez pola obserwatora (`recordedBy` puste) nie podlegają deduplikacji (każdy liczy się jako osobny obserwator) — konserwatywnie wobec niezależności.
- Metryki liczone jednym przebiegiem; wszystko, co dodane po zobaczeniu wyników, jest oznaczone „eksploracyjne”.

## 2.4
- **Rekord w lesie D-STAN z danymi BDL:** przynajmniej jedno wydzielenie D-STAN przecina bufor rekordu (promień = niepewność, min. 10 m). Zapytanie WFS z bboxem bufora; H liczone kodem produkcyjnym (`pipeline.habitat`, `pipeline.age_update`, profil `profiles/boletus_edulis.yaml`, wiek przeliczony na 2026), składem z WFS (`part_cd` + panujący).
- **H rekordu:** średnia ważona powierzchnią części wydzieleń D-STAN wewnątrz bufora; wydzielenie niespełniające maski ma H = 0 (jest w średniej). Rekord „w wydzieleniu niespełniającym maski” = wszystkie ważone wydzielenia D-STAN nie przechodzą maski (raportowane osobno).
- **Nieznany kod:** rekord oznaczony, gdy którekolwiek wydzielenie przechodzące maskę w buforze ma kod siedliska/gatunku spoza profilu. Jeśli > 20% rekordów borowika — analiza główna pomija te rekordy (także w tłach, tą samą regułą).
- **Wydzielenie rekordu do deduplikacji:** wydzielenie o największej powierzchni przecięcia z buforem (`adr_for`).
- **Tło (a) inne grzyby:** GBIF `taxonKey=5` (Fungi), Polska, niepewność ≤ 100 m, rok ≥ 2021, bez *Boletus edulis*. **Losowa próbka kandydatów** (warstwowo po latach i miesiącach, ziarno stałe) w liczbie wystarczającej, by po filtrze „las D-STAN” uzyskać do 5 × liczba borowików rekordów; z powodu kosztu zapytań WFS nie liczymy wszystkich ~25 tys. rekordów. Ta sama deduplikacja (obserwator + wydzielenie + rok).
- **Tło (b) niegrzybowe:** rośliny (`taxonKey=6`) i zwierzęta (`taxonKey=1`), po połowie próbki, miesiące VII–XI, niepewność ≤ 100 m, rok ≥ 2021, do 5 × liczba borowików po filtrze lasu; ta sama deduplikacja.
- **AUC:** Mann–Whitney (remisy = 0,5), pozytywy = borowiki, negatywy = tło. **Bootstrap po obserwatorach:** losowanie obserwatorów (klastrów) ze zwracaniem z sumy pozytywów i negatywów.
- **Wariant z paczkami (Katowice):** opisowo, tylko dla rekordów w RDLP Katowice, H ze składu pełnego z paczek BDL tam, gdzie paczka pokrywa wydzielenie.
- **Wariant „wszystkie lata”:** dodatkowy, oznaczony jako wariant (nie eksploracyjny — jest w regułach), obok głównej analizy od 2021.

## 2.5
- **Zbiór rekordów:** GBIF *B. edulis*, PL, pełna data zdarzenia, niepewność ≤ 1000 m, rok w zakresie pokrycia E-OBS z pełnym oknem klimatologii (rok ≤ 2025; rekordy 2026 wyłączone i policzone, bo E-OBS v33.0e kończy się 2025-12-31), ≥ 26 dni okna wstecz. Deduplikacja: obserwator + dzień + do 1 km.
- **Pogoda:** E-OBS, najbliższa komórka 0,1° dla współrzędnych rekordu. ET0 metodą Hargreaves-Samani z TN/TX (jedna metoda dla dnia znaleziska i klimatologii). Opad RR; TG/TN do T i przymrozku; wilgotność gleby niedostępna — `fruiting.soil_moisture_weight` = 0 w profilu, więc M zależy tylko od percentyla CWB26.
- **Klimatologia:** percentyl CWB26 dnia względem CWB26 z lat 1991–2020 w oknie ±`climatology.window_days` z profilu (ten sam kod `climatology_window_values`/`percentile_rank` co produkcja) — z tej samej komórki E-OBS.
- **Dni kontrolne:** dzień znaleziska ±15 dni (31 dni razem ze znaleziskiem). Ranga = udział dni kontrolnych z niższym F + 0,5 × remisy (dzień znaleziska wśród porównywanych).
- **Tło (a):** wszystkie dni okna. **Tło (b):** dzień znaleziska + dni okna, w których w promieniu 20 km (wielokąt 32-kątny) zgłoszono grzyby inne niż *B. edulis* (GBIF `taxonKey=5`, niepewność ≤ 1000 m); rekord z < 3 takimi dniami kontrolnymi jest w (b) pomijany.
- **Warianty:** główny = F bez G_season (`G_season = 1`, modulacja siedliskowa jak w notatniku 03: klasa wilgotności = 1). Porównawcze: F z G_season, sam kalendarz (`G_season(d)`), samo M, sama T, model stały (ranga = 0,5).
- **Bootstrap „po latach i lokalizacjach”:** dwa niezależne bootstrapy klastrowe — po roku i po komórce 0,1° — a przedział decyzyjny to ich suma (dolna = mniejsza z dolnych granic, górna = większa z górnych). Różnica (F bez G_season − sam kalendarz) liczona per rekord, ten sam sposób.

## Zmiana próbkowania tła (b) w 2.4 — 28.09.2026, przed obliczeniem jakiejkolwiek metryki AUC

Pierwotne losowanie (1200 stron po 300 rekordów na królestwo, offsety do 100 tys.) okazało się nieużywalnie wolne (ok. 3 zapytania GBIF/min przy głębokich offsetach). Zmieniono, **za zgodą właściciela**, na: **400 stron po 300 rekordów na królestwo, offsety tylko do 20 000** w komórce rok × miesiąc (VII–XI), 5 losowych rekordów ze strony; reszta bez zmian (kwota tła = 5 × liczba borowików w lesie, ziarno bez zmian). Ograniczenie offsetów oznacza próbkę z początku kolejności GBIF w komórce (nie jest to pełna losowość); do listy ograniczeń raportu. Żaden wynik 2.4 nie był w chwili zmiany policzony (przebieg przerwany na etapie losowania kandydatów tła).
