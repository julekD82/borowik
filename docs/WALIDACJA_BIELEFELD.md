# Reguły analizy danych z Bielefeld (plan 2.8) — ZATWIERDZONE 30.09.2026

**Status: zatwierdzone przez właściciela z jedną zmianą (trzy wyniki reguły decyzji zamiast dwóch).** Ten plik jest commitowany **przed** jakąkolwiek analizą związku pogoda–owocniki (znacznik czasu w git = dowód, że reguł nie dopasowano do wyników). Obowiązują zasady ogólne z `docs/WALIDACJA_REGULY.md`: jeden przebieg analizy głównej, wszystko dodatkowe oznaczone jako eksploracyjne, żaden wynik nie zmienia modelu automatycznie — wynikiem jest rekomendacja do decyzji właściciela. Model produkcyjny, profil, `pipeline/weather.py` i eksporty bez zmian.

Dane: `dane_walidacyjne/bielefeld/` (opis i ograniczenia w tamtejszym README). Pogoda: E-OBS v33.0e (TG, TN, TX, RR), komórka zawierająca środek obszaru (52,062 N, 8,451 E → komórka 52,05 N, 8,45 E), lata 1991–2024; klimatologia percentyli 1991–2020 jak w aplikacji.

**Ważne zastrzeżenie:** parametry F (13 °C, okna 26/20 dni, kara 17,5 °C) pochodzą z tych danych. Test sprawdza **kształt wag opadu w czasie**, nie trafność F.

## Obsługa zer (dni bez wizyty)

Dni wizyt nie są znane; autorzy wpisali 0 w każdy dzień bez rekordu. Przyjęte:

- **Miara (a):** jednostką jest **dzień z owocnikami** (wizyta pewna). Dni kontrolne: wszystkie dni ±15 od dnia z owocnikami w tym samym sezonie i w okresie 1.08–30.11 (jak tło (a) w 2.5; dni kontrolne mogą być dniami bez wizyty — to tylko osłabia test, nie faworyzuje żadnego wariantu wag).
- **Miara (b), analiza główna:** **tygodnie kalendarzowe** (pon.–niedz., w granicach 1.08–30.11; niepełne tygodnie na brzegach zostają). Przy 2–4 wizytach w tygodniu każdy tydzień zawiera wizytę, więc suma tygodniowa to prawdziwa liczba znalezionych owocników. Model zachowuje dzienne predyktory: oczekiwana suma tygodnia = Σ μ_d dni tego tygodnia (NB1 ze wspólnym φ jest zamknięty na sumowanie, więc wiarygodność jest dokładna).
- **Miara (b), wrażliwość:** dni (jak u autorów, z „fałszywymi zerami”). Tylko opisowo.
- Opóźnienie liczone jest od **dnia wykrycia**, a owocnik wyrósł 0–4 dni wcześniej — prawdziwe opóźnienie wzrostu jest średnio o 1–2 dni krótsze niż widoczne w danych. Dotyczy wszystkich wariantów jednakowo, ale najbardziej K3 (wąskie okno 5–10 dni).

## A. Wagi opadu w czasie (pytanie główne)

Warianty ustalone z góry (j = liczba dni wstecz, 0 = dzień oceny):

| Wariant | w(j) | Zakres j |
|---|---|---|
| **K0** (obecne w aplikacji) | 0,5^(j/10) | 0–25 |
| **K1** (reguła właściciela) | j/5 dla j < 5; 1 dla 5 ≤ j ≤ 10; 0,5^((j−10)/10) dla j > 10 | 0–35 |
| K2 (z pracy) | 1 | 0–25 |
| K3 (tylko 5–10 dni) | 1 dla 5 ≤ j ≤ 10, poza tym 0 | 0–10 |

Porównanie główne: **K1 vs K0**. K2 i K3 opisowo. Wagi parametryzowane w `pipeline/eobs_fruiting.py` (nowa funkcja, domyślnie K0 = obecne zachowanie), nie w produkcji.

### (a) Wzór aplikacji

- F **bez G_season** jak w 2.5 (`pipeline/eobs_fruiting.py::variant_scores`): CWB = Σ w(j)·(RR − ET0), ET0 Hargreaves z TN/TX, percentyl CWB względem klimatologii 1991–2020 z dni ±15 dni roku **liczonej tymi samymi wagami**, M, T (tmean20, tmean5, p5), przymrozek (tmin3), klasa wilgotności siedliska 1, `soil_moisture_weight` = 0. Dla każdego wariantu zmienia się tylko CWB (i jego klimatologia).
- Metryka: dla każdego dnia z owocnikami ranga F wśród dni kontrolnych (`validation_stats.rank_of`); średnia ranga dla wariantu; **różnica sparowana K1 − K0** (ta sama lista dni).
- Wagi: każdy dzień z owocnikami liczy się raz (główne). Ważenie liczbą owocników — opisowo.
- 95% CI: bootstrap klastrowy **po latach** (`validation_stats.cluster_bootstrap_mean`, 2000 powtórzeń, ziarno 20260928). Uwaga: tylko 10 klastrów — CI jest przybliżony.
- Minimalna liczebność: ≥ 100 dni z owocnikami w ≥ 8 latach (stanowisko `All`). Poniżej: „brak wniosku”. (Jest 155 dni w 10 latach, ale w 2016 tylko 1 dzień.)

### (b) Model zliczeń

- NB1 (Var = μ(1 + φ), jak `nbinom1` u autorów), log μ_d = α_rok + β_P·P_w(d) + β_1·T20(d) + β_2·T20(d)², gdzie P_w = Σ w(j)·RR(d−j) / Σ w(j) (średnia ważona opadu, mm/dobę; jak `rollP` u autorów, ale z wagami wariantu), T20 = średnia TG z 20 dni. Tygodnie: y_tydz ~ NB1(Σ μ_d, φ).
- **Rok jako efekt stały** (nie losowy): glmmTMB nie jest dostępny, a statsmodels nie ma NB GLMM. Implementacja w `pipeline/bielefeld.py` (scipy, bez nowych zależności). Sprawdzone: ten model odtwarza wybór okien autorów (`notebooks/17_bielefeld_wczytanie.py`: All T20/P26, optimum 13,7 °C).
- Porównanie: **log-wiarygodność „zostaw jeden rok”** (10 lat). Dopasowanie na 9 latach; dla pominiętego roku β i φ z dopasowania, a α_rok wyznaczane na pominiętym roku (jeden parametr, jednakowo dla wszystkich wariantów — mierzy rozkład owocników **w sezonie**, bo poziomu roku pogoda w tym modelu i tak nie przewiduje). ΔLL = Σ_lata [LL(K1) − LL(K0)]; raportowane także ΔLL dla każdego roku.

### Opisowo: profil opóźnienia

Opad w przedziałach 0–4, 5–9, …, 30–34 dni wstecz (7 średnich) jako osobne predyktory w modelu (b) (tygodnie) razem z T20 i T20²; współczynniki z 95% CI (Wald z hesjanu). Pokazuje, gdzie leży sygnał opadu. Autorzy testowali tylko okna kończące się w dniu obserwacji — okna przesunięte są tu nowe.

### Reguła decyzji (zatwierdzona)

Warunki:

1. (b) ΔLL_LOYO(K1 − K0) > **2** i K1 lepsze w **≥ 6 z 10** pominiętych lat;
2. (a) cały 95% CI różnicy średniej rangi K1 − K0 **> 0**;
3. **nie gorsze w 2.5** (`notebooks/12_walidacja_2_5.py`, zamrożony zbiór `2_5_zbior_zamrozony.csv`, SHA-256 `6a048d63df698bd2bed82d57b47e837fc6bb366f90519534855e625fadf6622e`; dni tła (b) z cache zapytań GBIF z 28.09) w **obu tłach**: średnia ranga F bez G_season z K1 minus z K0 ≥ **−0,010** (estymacja punktowa) i dolna granica 95% CI tej różnicy (bootstrap jak w 2.5: suma przedziałów po latach i po komórkach) ≥ **−0,030**.

Trzy wyniki (sprawdzane w tej kolejności; pierwszy spełniony rozstrzyga):

- **„K1 lepsze”** — warunki 1, 2 i 3 → mocna rekomendacja K1.
- **„K1 gorsze”** — ΔLL_LOYO(K1 − K0) < −2 **albo** cały 95% CI (a) < 0 → bez zmian (K0 zostaje).
- **„K1 nie gorsze”** — ΔLL_LOYO(K1 − K0) ≥ −2 **oraz** dolna granica 95% CI (a) ≥ −0,03 **oraz** warunek 3 → K1 można wdrożyć jako zmianę opartą na założeniach (reguła właściciela „5–10 dni” + praca: opad nie działa od razu), wyraźnie oznaczoną jako **niepotwierdzoną danymi**. Uzasadnienie właściciela: K0 (najmocniej liczy się dzisiejszy deszcz) nie pochodzi z pracy ani z danych, więc nie ma powodu dawać mu przewagi domyślnej.

Doprecyzowania dopisane przy zapisie reguł (przed analizą): (i) „K1 gorsze” jest sprawdzane przed „nie gorsze”, bo definicje nakładają się, gdy cały CI (a) leży w przedziale [−0,03; 0); (ii) jeśli żaden wynik nie jest spełniony (np. zawodzi tylko warunek 3), wynik to **„nierozstrzygnięte”** → bez zmian, z opisem, który warunek zawiódł; (iii) poniżej minimalnej liczebności (a) — „brak wniosku”.

K2/K3 nie są kandydatami do rekomendacji w tym przebiegu (opisowo). Żadna zmiana nie jest wdrażana automatycznie.

## B. Temperatura w ciągu dnia (pytanie eksploracyjne)

Model bazowy: (b) na tygodniach, T20 kwadratowo + opad wg wariantu z A: **K1, jeśli wynik A to „K1 lepsze” albo „K1 nie gorsze”**, inaczej K0. Dodawana **po jednej** cecha:

1. średnia TX z 5 dni,
2. liczba dni z TX > 20 °C w ostatnich 7 dniach,
3. średnia TN z 7 dni,
4. średni zakres dobowy (TX − TN) z 7 dni.

Raport: ΔLL_LOYO względem modelu bazowego i znak współczynnika. **Bez zmian modelu**; uwaga o wielokrotnym testowaniu (4 cechy) i o tym, że optimum 13 °C wyznaczono na tych samych danych. Kontekst: test nocnych temperatur na GBIF (`notebooks/16_eksploracja_temp_nocne.py`) nie wykazał sygnału.

## Czego ten test nie pokazuje (do raportu)

Jeden bukowy las w NW Niemczech; 10 sezonów (10 klastrów); parametry F z tej samej pracy; E-OBS 0,1° bez wilgotności gleby; brak dni wizyt i identyfikatorów owocników; stanowiska dokładane w kolejnych latach (efekt roku pochłania poziom, nie zmianę w sezonie); opóźnienie widziane od dnia wykrycia.
