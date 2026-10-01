# Raport: dane z Bielefeld (plan 2.8) — wagi opadu w czasie i temperatura w ciągu dnia

Stan: 30.09.2026, gałąź `walidacja-bielefeld`. Model produkcyjny, profil, `pipeline/weather.py` i eksporty **bez zmian**. Reguły: `docs/WALIDACJA_BIELEFELD.md` (zatwierdzone, commit `b33412e` przed analizą); notatnik analizy zacommitowany przed jedynym przebiegiem (`f5fe253`).

## Wynik w skrócie

- **A (wagi opadu): „nierozstrzygnięte” → wg reguł bez zmian (K0 zostaje).** Model zliczeń wyraźnie woli K1 (ΔLL +6,3; lepsze w 9 z 10 lat), walidacja 2.5 też (tło a: +0,031, CI 0,006…0,066), ale w wzorze aplikacji na danych z Bielefeld K1 i K0 są nie do odróżnienia (+0,003), a dolna granica CI (−0,037) jest o 0,007 poniżej progu „nie gorsze” (−0,03). Wszystkie estymacje punktowe są po stronie K1; żadna nie jest po stronie K0.
- **Reguła „tylko 5–10 dni” (K3) nie ma poparcia:** jest najgorsza w obu miarach. Sygnał opadu rozkłada się na ok. 0–24 dni wstecz, bez wyraźnej przerwy w pierwszych dniach.
- **B (temperatura w ciągu dnia, eksploracyjnie): nic nie wskazuje, że wysokie TX szkodzą.** Wyższa temperatura ostatnich 5 dni (przy tej samej średniej z 20 dni) idzie w parze z **większą** liczbą owocników, ale to efekt średniej dobowej (TG), nie maksimów — TX nic nie dodaje ponad TG (analiza po wynikach, `17b`). Bez zmian modelu.

## Co zrobiono

1. **Dane** (etap 1): Zenodo V1.2 (doi 10.5281/zenodo.20591123) i wersja pierwsza (10.5281/zenodo.17881359) — `scripts/pobierz_bielefeld.py`, SHA-256, trwały zbiór `dane_walidacyjne/bielefeld/` (README: cytowanie, licencje CC BY 4.0 i E-OBS, opis kolumn, ograniczenia). E-OBS v33.0e dla okolic Bielefeld (`scripts/pobierz_eobs.py --obszary BI`, ok. 10,7 GB transferu, na dysku 9 MB; pliki polskie nietknięte), dzienna pogoda komórki 52,05 N / 8,45 E 1991–2024 w repozytorium.
2. **Kontrola wczytania** (`notebooks/17_bielefeld_wczytanie.py`): 1905 owocników, 4 w 2016, 354 w 2020, 85,8% dni zerowych w 05.08–21.11 — zgodnie z pracą. Model NB1 z rokiem jako efektem stałym (scipy) odtwarza wybór okien autorów: wszystkie stanowiska T20/P26 (optimum 13,7 °C), Site A P32, Site B P26. Własna pogoda E-OBS vs pogoda autorów: TG r = 0,9998 (średnia różnica −0,02 °C), RR r = 0,998 (+0,02 mm); interpolacja dwuliniowa bliżej, ale nie identycznie (inna wersja E-OBS u autorów).
3. **Obsługa zer:** dni wizyt nie ma w danych (autorzy wpisali 0 w każdy dzień bez rekordu). Miara (a) używa tylko dni z owocnikami jako „pozytywów”; model zliczeń (b) liczy na tygodniach kalendarzowych (każdy tydzień zawiera wizytę) z dziennymi predyktorami (średnia tygodnia = Σ μ dni; NB1 jest zamknięty na sumowanie).
4. **Analiza** (`notebooks/17_bielefeld.py`, wynik `notebooks/output/walidacja/17_bielefeld.json`), 41 s, bez sieci (0 nowych zapytań GBIF).
5. Przy okazji: zamrożone zbiory 2.4/2.5 skopiowane do `dane_walidacyjne/gbif_2_4_2_5/` (poza gitem) i zapisane w repozytorium z pseudonimami obserwatorów (`dane_walidacyjne/gbif_2_4_2_5_pseudonimy/`).

## A. Wagi opadu w czasie

Warianty (j = dni wstecz, 0 = dzień oceny): **K0** 0,5^(j/10), j 0–25 (aplikacja); **K1** j/5 dla j < 5, 1 dla 5–10, 0,5^((j−10)/10) do j = 35 (reguła właściciela); K2 równe wagi 0–25 (praca); K3 tylko 5–10 dni.

### (a) Wzór aplikacji — F bez G_season z E-OBS, ranga dnia z owocnikami wśród dni ±15 (1.08–30.11)

155 dni z owocnikami w 10 latach (minimum 100 / 8 — spełnione). 95% CI: bootstrap po latach (10 klastrów).

| Wariant | Średnia ranga (95% CI) | Ważona liczbą owocników (opisowo) | Różnica względem K0 (95% CI) |
|---|---|---|---|
| **K0** | 0,581 (0,546–0,612) | 0,587 | — |
| **K1** | 0,584 (0,553–0,609) | 0,580 | **+0,003 (−0,037…+0,042)** |
| K2 (opisowo) | 0,590 (0,542–0,628) | 0,621 | +0,009 (−0,025…+0,036) |
| K3 (opisowo) | 0,555 (0,508–0,600) | 0,488 | −0,026 (−0,064…+0,014) |

Wszystkie warianty F odróżniają dni z owocnikami od sąsiednich dni (0,55–0,59, CI powyżej 0,5) — wyraźniej niż na GBIF (0,53), ale **to nie jest niezależna walidacja F**: optimum 13 °C, okna i kara za upał pochodzą z tych danych.

### (b) Model zliczeń — NB1, tygodnie (183), rok jako efekt stały, „zostaw jeden rok”

| Wariant | LL „zostaw jeden rok” | ΔLL względem K0 | β opadu (±SE), na mm/dobę | Optimum T20 |
|---|---|---|---|---|
| **K0** | −355,6 | — | 0,354 ± 0,077 | 13,8 °C |
| **K1** | −349,3 | **+6,3** (lepsze w 9 z 10 lat; jedyny gorszy rok 2018: −0,11) | 0,498 ± 0,089 | 13,8 °C |
| K2 (opisowo) | −348,7 | +6,9 | 0,518 ± 0,092 | 13,8 °C |
| K3 (opisowo) | −360,0 | −4,4 | 0,131 ± 0,048 | 13,8 °C |

ΔLL K1 − K0 w poszczególnych latach: 2015 +1,33; 2016 +0,26; 2017 +0,89; 2018 −0,11; 2019 +0,90; 2020 +1,09; 2021 +1,05; 2022 +0,78; 2023 +0,03; 2024 +0,09. Wrażliwość na danych dziennych (z „fałszywymi zerami”): ΔLL K1 − K0 = +3,6 (ten sam kierunek).

### Warunek 3 — walidacja 2.5 na zamrożonym zbiorze GBIF (Polska)

K0 odtwarza rangi z 2.5 dokładnie (maks. różnica 10⁻¹⁶ na 476 rekordach); dni tła (b) z cache zapytań GBIF z 28.09.

| Tło | N | Średnia ranga K0 | Średnia ranga K1 | Różnica K1 − K0 (95% CI) | „Nie gorsze” (≥ −0,010 i dolna ≥ −0,030) |
|---|---|---|---|---|---|
| (a) wszystkie dni ±15 | 476 | 0,529 | 0,559 | **+0,031 (+0,006…+0,066)** | tak |
| (b) dni z innymi grzybami ≤ 20 km | 269 | 0,527 | 0,543 | +0,016 (−0,016…+0,065) | tak |

To jedyny w tej analizie sprawdzian na danych **niezależnych** od parametrów F — i w tle (a) K1 jest lepsze od K0 z CI powyżej zera. Uwaga: tło (a) jest zawyżone (ludzie chodzą do lasu, gdy spodziewają się grzybów, np. kilka dni po deszczu), więc część tej przewagi może odzwierciedlać zachowanie grzybiarzy, a nie grzybów.

### Werdykt wg reguł: **„nierozstrzygnięte”**

| Warunek | Wynik | Spełniony? |
|---|---|---|
| 1. ΔLL > 2 i ≥ 6/10 lat | +6,3; 9/10 | tak |
| 2. cały CI (a) > 0 | −0,037…+0,042 | nie |
| 3. 2.5 nie gorsze w obu tłach | +0,031 / +0,016 | tak |
| „K1 gorsze”: ΔLL < −2 albo cały CI (a) < 0 | nie | — |
| „K1 nie gorsze”: ΔLL ≥ −2 i dolna granica CI (a) ≥ −0,03 i warunek 3 | dolna granica −0,037 | **nie** (o 0,007) |

Zgodnie z regułą (doprecyzowanie ii): **bez zmian**; zawiódł wyłącznie próg dolnej granicy CI w mierze (a). Nie zmieniam reguł po wynikach (zasada z `docs/WALIDACJA_REGULY.md`).

### Opisowo: profil opóźnienia (opad w przedziałach jako osobne predyktory, tygodnie)

| Dni wstecz | β na mm/dobę (95% CI Walda) |
|---|---|
| 0–4 | 0,078 (−0,046…0,201) |
| 5–9 | 0,106 (−0,017…0,228) |
| 10–14 | 0,116 (−0,032…0,263) |
| 15–19 | 0,093 (−0,078…0,265) |
| 20–24 | 0,162 (0,032…0,292) |
| 25–29 | −0,004 (−0,141…0,132) |
| 30–34 | 0,076 (−0,041…0,193) |

Sygnał opadu jest rozłożony na ok. 0–24 dni, bez wyraźnego maksimum w 5–10 dniach i bez zerowego efektu w dniach 0–4 (przedziały szerokie, przedziały opadu są ze sobą skorelowane). Model z 7 przedziałami przewiduje pominięte lata gorzej niż K0 (ΔLL −0,6) — za dużo parametrów na 10 sezonów. Pasuje to do obrazu z (b): długie, płaskie okno (K2, K1) > wagi malejące od dziś (K0) > wąskie okno 5–10 dni (K3). Pamiętać: opóźnienie liczone od dnia **wykrycia** (owocnik wyrósł 0–4 dni wcześniej).

## B. Temperatura w ciągu dnia (eksploracyjnie)

Model bazowy: tygodnie, T20 + T20² + opad K0 (wynik A to „nierozstrzygnięte”, więc wg reguł K0). Każda cecha dodana osobno.

| Cecha | ΔLL „zostaw jeden rok” | Lata lepiej | β (±SE) | Korelacja z T20 |
|---|---|---|---|---|
| średnia TX z 5 dni | +5,3 | 8/10 | +0,18 ± 0,05 na °C | 0,91 |
| liczba dni TX > 20 °C w 7 dniach | +3,5 | 7/10 | +0,31 ± 0,09 na dzień | 0,85 |
| średnia TN z 7 dni | +1,1 | 5/10 | +0,16 ± 0,08 na °C | 0,88 |
| średni zakres dobowy (TX − TN) z 7 dni | −1,3 | 7/10 | +0,09 ± 0,05 na °C | 0,69 |

**Analiza dodatkowa po zobaczeniu wyników** (`notebooks/17b_bielefeld_eksploracja.py`): średnia **TG** z 5 dni daje ten sam zysk co TX (ΔLL +5,5, 8/10 lat; korelacja TG5–TX5 = 0,97); dodanie TX ponad TG5 pogarsza przewidywanie (ΔLL +4,2 zamiast +5,5; współczynnik nadwyżki TX nad TG 0,13 ± 0,09). **Sygnał dotyczy więc ciepła ostatnich dni, nie maksimów dnia.**

Interpretacja ostrożna:
- Znak jest przeciwny do hipotezy „gorące popołudnia szkodzą”: przy tej samej średniej z 20 dni cieplejsze ostatnie dni idą w parze z **większą** liczbą owocników. Kara za upał w aplikacji (tmean5 > 17,5 °C przy opadzie z 5 dni < 5 mm) nie była tu osobno testowana; działałaby w 118 z 1220 dni monitoringu, a w tych dniach znaleziono tylko 2 owocniki (2 dni) — to zgodne z karą, a dodatni efekt ciepła dotyczy dni bez suszy.
- Możliwy artefakt końca sezonu: w listopadzie ostatnie dni są chłodniejsze od średniej z 20 dni, a zera po zakończeniu monitoringu (po mrozach) są w danych. Efekt roku tego nie usuwa.
- 4 cechy + analiza po wynikach = wielokrotne testowanie; optimum 13 °C wyznaczono na tych samych danych; brak sygnału nocnych temperatur w GBIF (`notebooks/16_…`) jest spójny z brakiem efektu TN/DTR tutaj.
- **Bez zmian modelu.** Jeśli właściciel chce to sprawdzać dalej, potrzebna jest niezależna próba (2.5 na nowych rekordach GBIF albo własne wizyty z Fazy 5) i reguła zapisana z góry.

## Rekomendacja do decyzji właściciela

1. **Wg zatwierdzonych reguł: K0 zostaje** (wynik „nierozstrzygnięte”). Nie proponuję obchodzenia reguły.
2. Dla pełnego obrazu: dane nie przemawiają za K0 w żadnej mierze — K1 wygrywa w modelu zliczeń (9/10 lat) i na niezależnych danych polskich (2.5, tło a), a w wzorze aplikacji remisuje. Przegrana z regułą wynika z szerokości CI przy 10 sezonach. Jeśli właściciel uzna, że próg −0,03 był za ciasny dla 10 klastrów, zgodnie z `docs/WALIDACJA_REGULY.md` poprawiona reguła dotyczy **nowej próby danych** — np. ponowne 2.5 na rekordach GBIF z 2026 (po wydaniu wersji E-OBS obejmującej 2026) albo wyjścia z Fazy 5.
3. **Reguła „opad działa po 5–10 dniach” w wąskiej postaci (K3) jest nieuzasadniona** tymi danymi; jeśli K1 kiedyś wejdzie, to jako długie okno z łagodnym startem, nie okno 5–10 dni.
4. K2 (równe wagi z pracy) wypada najlepiej w modelu zliczeń, ale na tych samych danych, na których autorzy go wybrali — nie jest kandydatem bez niezależnego testu.
5. Temperatura w ciągu dnia: bez zmian; ewentualna hipoteza na przyszłość to „ciepło ostatnich 5 dni względem 20 dni”, nie TX.

## Czego ten test nie pokazuje

- **Jeden bukowy las w NW Niemczech** (siedlisko i klimat inne niż Kieleczka czy Podkarpacie); 15–29 stanowisk łącznie, bez współrzędnych.
- **10 sezonów = 10 klastrów** w bootstrapie; CI w (a) jest przybliżony i szeroki.
- **Parametry F pochodzą z tej pracy** (13 °C, okna 26/20, kara 17,5 °C) — dane nie walidują F, tylko porównują kształty wag opadu; K2 ma tu przewagę „z urzędu”.
- **E-OBS 0,1°** (ok. 7 × 11 km), bez wilgotności gleby; ET0 z Hargreaves-Samani; w aplikacji opad z radaru ~1 km.
- **Brak dni wizyt i identyfikatorów owocników**: zera w dniach bez wizyt nie są prawdziwymi zerami (obsłużone tygodniami w (b); w (a) dni kontrolne mogą być dniami bez wizyty), możliwe liczenie tego samego owocnika dwa razy.
- **Stanowiska dokładane w kolejnych latach**: efekt roku pochłania poziom, model porównuje tylko rozkład owocników **w sezonie**.
- Opóźnienie widziane od dnia **wykrycia**, nie wzrostu (0–4 dni różnicy).
- Warunek 3 (2.5) ma własne skrzywienia: tło (a) zawyżone, tło (b) zaniżone; remisy z nasycenia M.

## Pliki

- Reguły: `docs/WALIDACJA_BIELEFELD.md`; dane: `dane_walidacyjne/bielefeld/` (README), `dane_walidacyjne/gbif_2_4_2_5_pseudonimy/`.
- Kod: `scripts/pobierz_bielefeld.py`, `scripts/pobierz_eobs.py --obszary BI`, `scripts/kopiuj_zbiory_gbif.py`, `pipeline/bielefeld.py`, `pipeline/eobs.py` (`REGIONS`, `daily_bilinear`), `pipeline/eobs_fruiting.py` (`precip_weights`), notatniki `17_bielefeld_wczytanie.py`, `17_bielefeld.py`, `17b_bielefeld_eksploracja.py`.
- Wyniki (lokalnie, `notebooks/output/` w `.gitignore`): `17_bielefeld.json`, `17_bielefeld_rangi_a.csv`, `17_2_5_K0_K1_rangi.csv`, `17_okna_*.csv`, `17_bielefeld_wczytanie.json`, `17b_bielefeld_eksploracja.json`.
- Testy: `tests/test_bielefeld.py`, `tests/test_pobierz_bielefeld.py`, `tests/test_kopiuj_zbiory_gbif.py`, rozszerzenia `tests/test_eobs.py`, `tests/test_eobs_fruiting.py`.

Podziękowanie E-OBS: We acknowledge the E-OBS dataset from the EU-FP6 project UERRA (https://www.uerra.eu) and the Copernicus Climate Change Service, and the data providers in the ECA&D project (https://www.ecad.eu). Cornes et al. 2018, J. Geophys. Res. Atmos. 123, doi:10.1029/2017JD028200. Dane owocników: Brejon Lamartinière & Hoffman, Zenodo doi 10.5281/zenodo.20591123, CC BY 4.0.
