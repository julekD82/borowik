# Raport — Faza 3 (presja grzybiarzy v2: punkty dostępu)

Gałąź: `ulepszenia-faza3`, worktree `.claude/worktrees/faza3`.
**Baza = `master`**: sprawdzone `git merge-base --is-ancestor` — Fazy 1, 1.5 i 1.6 są scalone
(merge `aa0a6cd`, „Merge branch 'ulepszenia-faza1-6' into master”). Nic nie było pushowane,
`master` i gałąź `ulepszenia-faza2` nie były ruszane.

Dane współdzielone z drugą sesją (Faza 2) podłączone jako dowiązania `mklink /J`: `cache/`
(w nim siatka GUS, BDL kafle, OSM, GDOS, radar) i `BDL/` (paczki). W dowiązaniach nic nie
usuwano ani nie czyszczono; do `cache/` doszedł tylko nowy podkatalog `cache/access_tiles/`
(źródła punktów dostępu, których druga sesja nie używa).

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| 3.1 Dane punktów dostępu | DONE, z odstępstwem | Parkingi, wjazdy, szlabany, fallback, osiedla, sieć dróg leśnych, nawierzchnia z OSM, publiczna/zamknięta. **BDOT10k `OT_SKDR_L` (materialNawierzchni) i relacje OSM `route=bicycle`: BLOCKED** — patrz niżej |
| 3.2 Atrakcyjność punktu | DONE | `A_k`, `A_norm_k` (normalizacja bezwzględna), korytarz po sieci drogowej |
| 3.2b Podział ludności (Huff) | DONE | `pressure.access_points.population_split: huff` (domyślny) / `none`; patrz „Ciąg dalszy” |
| 3.3 Zasięg oddziaływania | DONE | jądro `max(0, 1−(d/R)²)²`, parametry startowe właściciela w profilu; odległość w linii prostej (wariant po sieci duktów: opcjonalny, nie zrobiony) |
| 3.4 Łączenie w P | DONE | suma po punktach, korytarz jako jeden składnik, `P = 1 − exp(−raw/S)`, `S` dobrane offline (huff 0,1385; none 7,0); wkład każdego typu i punkt o największym wkładzie w diagnostyce |
| 3.5 Mapa i karta wydzielenia | DONE | eksporty `access_points_{day}.geojson` i `forest_roads_{day}.geojson`, warstwy w legendzie, popup, karta, synchronizator i migawki |
| 3.6 Kontrola i raport | DONE | ten dokument + `docs/porownania/faza3/` |

Stary model dostępny przez `pressure.model: gravity` (profil `profiles/boletus_edulis.yaml`);
domyślnie `access_points`. Gdy przebieg nie ma **żadnego** punktu dostępu (np. wszystkie
źródła zawiodły), `pipeline.mvp` wraca do `gravity`, a manifest to zapisuje
(`pressure_model_used`, `access_points.reason`). Brak danych nie oznacza cicho „brak presji”.

## Co zostało zbudowane

- `pipeline/access_data.py` — pobieranie i osobny cache kafli (`cache/access_tiles/`):
  BDL turystyczny (ArcGIS WFS `WFS_BDL_mapa_turystyczna`, kody `PARKING` i `MSC POST`),
  dojazdy pożarowe BDL (`WFS_BDL_dojazdy_pozarowe`), OSM (drogi z `surface`, `tracktype`,
  `access`, `motor_vehicle` oraz `barrier=gate|lift_gate`). Ustalone empirycznie:
  główny WFS BDL (GeoServer) **nie** ma tych warstw; ArcGIS zwraca JSON zadeklarowany jako
  UTF‑8, w rzeczywistości cp1250; `BBOX` w kolejności N,E, współrzędne w odpowiedzi [E,N].
  Błąd kafla jest raportowany, nie cache'owany; po pierwszym błędzie OSM dalsze pobieranie
  OSM jest wstrzymane.
- `pipeline/access_points.py` — klasyfikacja dróg (publiczna / zamknięta, nawierzchnia:
  twarda / kruszywo / ubita / gruntowa / nieznana), parkingi (BDL + OSM ≤ 200 m od lasu,
  dedupe 100 m, pierwszeństwo BDL), wjazdy (`crossing_public` z kontynuacją duktu ≤ 60 m,
  `crossing_track` z drogą publiczną ≤ 300 m, `junction`), szlabany (na drodze leśnej,
  ≤ 300 m od drogi publicznej; dedupe 150 m, szlaban wygrywa), fallback dla kafli bez wjazdów,
  osiedla (oczka GUS ≤ 200 m od lasu), nadpisywanie korektami właściciela, nawierzchnia
  dojazdów pożarowych z najbliższej drogi OSM z opisem (≤ 20 m).
- `pipeline/access_pressure.py` — `A_k`, korytarz po sieci (najkrótsza ścieżka z przesunięciami
  startowymi, spadek o połowę co 3 km, mnożnik nawierzchni 1,0 / 0,8 / 0,8 / 0,5 / 0,3),
  presja per wydzielenie, odległości do karty.
- `pipeline/access_export.py`, `pipeline/mvp.py`, `pipeline/prepare_trip.py`, `pipeline/export.py`
  — eksport, wpięcie modelu, manifest, `details_{day}.json` (pole `access`), diagnostyka.
- Frontend: `frontend/src/map.ts`, `model.ts`, `main.ts`, `style.css`,
  `frontend/scripts/sync-data.mjs`; `launcher/trip_archive.py` (migawki).

## Dane Kieleczki (promień 20 km, 23 kafle 10 × 10 km)

Źródło: pobranie 2026‑09‑29 (0 kafli z błędem w BDL i OSM), reszta z cache przebiegu 1.6.

| Typ / źródło | Liczba |
|---|---|
| parking BDL (wszystkie to `MSC POST`, `PARKING` brak w tym obszarze) | 148 |
| parking OSM (≤ 200 m od lasu, po deduplikacji) | 230 |
| wjazd (OSM) | 1693 |
| szlaban (OSM) | 153 |
| osiedla przy lesie (oczka GUS) | 921 |
| fallback (droga asfaltowa) | 0, kafle z fallbackiem: 0 |
| odcinki dróg: zamknięte drogi leśne (OSM) / dojazdy pożarowe BDL / publiczne | 11266 / 15683 / 2041 |

Liczniki trafiają do `run_manifest_{day}.json` (`access_points.points_by_type_source` itd.).

## Kontrola pokrycia nawierzchni (BDL + OSM)

Sieć korytarza (zamknięte drogi leśne + dojazdy pożarowe) ma 8926 km. Nawierzchnia znana
(z tagów OSM, dla dojazdów pożarowych przez dopasowanie do najbliższej drogi OSM) dla
**63,8%** długości; dla dojazdów pożarowych BDL 78,8% z 3954 km. W komórkach 2 × 2 km
(501 komórek z ≥ 1 km sieci) udział znanej nawierzchni: mediana 62%, kwartyle 34% / 80%,
10. percentyl 0%; **88 z 501 komórek (18%) ma poniżej 20% znanej nawierzchni**. Mapa:
`docs/porownania/faza3/mapa_pokrycia_nawierzchni.html` (zielone ≥ 60%, żółte 30–60%,
czerwone < 30%), tabela: `pokrycie_nawierzchni_kafle_2x2.csv`.

**Wrażliwość na „nawierzchnię nieznaną”** (mediana P w masce / udział powierzchni z P > 0,5
/ Spearman względem bazy 0,5): jak utwardzona (mnożnik 1,0): 0,375 / 32,1% / 0,9999;
baza 0,5: 0,372 / 31,8% / 1; jak gruntowa (0,3): 0,370 / 31,6% / 0,99998.
Wniosek: w tym obszarze klasyfikacja nawierzchni **prawie nie zmienia** P (korytarz to
niewielki składnik sumy), więc nierówne pokrycie tagów OSM nie wypacza wyniku. To wniosek
dla Kieleczki i tych parametrów, nie ogólny.

## Porównanie gravity vs access_points (Kieleczka, 19 716 wydzieleń, 14 399 w masce)

Dane wejściowe: geometrie i H/F/P/R z przebiegu 1.6 (`docs/porownania/faza1_6`),
rekonstrukcja R z tych samych H/F_loc i P zgadza się z zapisanym R co do 0,0
(`R_recompute_check_max_abs_diff_vs_1_6`).

| Miara (maska) | gravity | access_points |
|---|---|---|
| mediana P | 0,373 | 0,372 (S dobrane) |
| średnia P | 0,379 | 0,389 |
| udział powierzchni lasu z P > 0,5 | 32,3% | **31,8%** |
| Spearman P (gravity vs access) | | 0,747 |
| Spearman R | | 0,960 |
| top‑20 wydzieleń wspólnych | | **5 / 20** |
| rejony (5) z tych samych lokalizacji ≤ 1,6 km | | 4 / 5 |

**Odsetek powierzchni z P > 0,5 wynosi 31,8%, próg ostrzegawczy (~70%) nie jest przekroczony.**
Uwaga: ta liczba jest wynikiem także doboru `S` (mediana została zrównana z modelem gravity), więc
mówi o *rozkładzie*, nie o poziomie bezwzględnym.

Kontrole sensowności:
- Wydzielenia dalej niż 3 km od każdego punktu i dalej niż 0,3 km od każdej drogi leśnej:
  **1** takie wydzielenie, jego P = 0 (0 naruszeń).
- Brak skoków na granicach zasięgów: różnica P między sąsiadami (centroidy ≤ 200 m):
  99. percentyl 0,059 (gravity 0,106), maksimum 0,109 (gravity 0,458). Jądro jest gładkie
  (test jednostkowy).
- Pas lasu przy Lublińcu (wydzielenia ≤ 8 km od centrum, odległość od najbliższego dużego
  osiedla, średnie P access / gravity): 0–0,5 km: 0,49 / 0,63; 0,5–1 km: 0,57 / 0,66;
  1–2 km: 0,50 / 0,52; 2–3 km: 0,37 / 0,39; 3–5 km: 0,42 / 0,38; > 5 km: 0,51 / 0,44.
  **Kryterium „presja nie na kilometry w głąb” jest spełnione tylko częściowo**: P przy osiedlu
  spada (0,57 → 0,37 do 3 km), ale dalej rośnie z powrotem, bo las jest gęsto usiany parkingami
  i wjazdami z dużą atrakcyjnością (ludność w promieniu 20 km). Do rozważenia przed
  kalibracją: niższy zasięg zbierania ludności dla wjazdów albo wagi zależne od odległości
  do miasta. Nie stroiłem automatycznie.

### Zasięg poprzeczny dróg leśnych 0,3 / 0,5 / 1,0 km

| Zasięg | Powierzchnia lasu w zasięgu dróg | Powierzchnia z P > 0,5 | Mediana P |
|---|---|---|---|
| 0,3 km | **95,4%** | 31,8% | 0,372 |
| 0,5 km | 99,3% | 32,0% | 0,374 |
| 1,0 km | 99,8% | 32,4% | 0,377 |

Potwierdza to obawę z planu: przy siatce dróg co ok. 1–1,5 km (dojazdy pożarowe BDL plus
OSM) nawet 0,3 km obejmuje 95% powierzchni, więc **korytarze dróg leśnych praktycznie nie
różnicują** wydzieleń w tym obszarze; presja rozróżnia się głównie przez parkingi, wjazdy
i osiedla. Zasięg 0,3 km zostaje jako najostrożniejszy.

### 10 wydzieleń z największym wzrostem P i 10 z największym spadkiem

Pełne tabele z wyjaśnieniem (który punkt, wkłady typów) w `raport_dane.json`
(`top10_wzrost_P`, `top10_spadek_P`), mapy różnic:
`mapa_roznic_P_kieleczka.html` i `mapa_roznic_P_lubliniec.html` (czerwone: presja rośnie,
niebieskie: maleje; czarne kółka: parkingi i szlabany).

- **Wzrost (P ≈ 0,2–0,3 → 0,7–0,85)**: wydzielenia 0,8–1,4 km od parkingów w nadleśnictwach
  Brynek, Zawadzkie i Lubliniec (identyfikatory `02-03-`, `02-14-`, `02-19-`; np. parking OSM `pk-osm-926794438`, BDL „Pod Stokiem”), obok kilku
  wjazdów i szlabanów; model gravity liczył od centroidu do najbliższej drogi i mocno
  zaniżał presję przy parkingach w gęstym lesie.
- **Spadek (P ≈ 0,75 → 0,13–0,19)**: wydzielenia 2–4 km od najbliższego wjazdu (głównie nadleśnictwa
  Rudziniec `02-25-` i Brynek `02-03-`), gdzie gravity dawał wysoką presję od ludności, a w modelu punktów
  dostępu jedyny wkład daje odległy wjazd w brzegu zasięgu 2,5 km.

## Ranking i rejony

Top‑20 zmienia się mocno (5 wspólnych z 20), Spearman R w masce 0,96. Rejony: 4 z 5 w tych
samych miejscach (≤ 1,6 km), piąty przesunięty. Listy rejonów przed/po są w
`raport_dane.json` (`regions`).

## Ręczna kontrola do przejrzenia przez właściciela

`docs/porownania/faza3/kontrola_reczna.csv`: 10 losowych wjazdów/szlabanów i 10 losowych
parkingów (ziarno 42) ze współrzędnymi i linkiem do widoku satelitarnego. Do sprawdzenia
z ortofotomapą Geoportalu (wpisać współrzędne WGS84 w wyszukiwarce). **Nieprzejrzane.**

## Stan techniczny i ograniczenia

- **BDOT10k `OT_SKDR_L` — BLOCKED.** WFS GUGiK (`.../PobieranieBDOT10k`) zwraca tylko indeks
  powiatów (warstwa `ms:BDOT10k_powiaty`) do pobrania paczek; dane są dostępne jako paczki
  powiatowe (GML/SHP/GPKG, setki MB na powiat), a pobranie ich nie było w tej sesji zatwierdzone.
  Nawierzchnia i kategoria zarządzania pochodzą więc z OSM (i dopasowania do dojazdów
  pożarowych BDL); odcinki bez opisu mają klasę „nieznana”. Kontrola pokrycia i wrażliwość
  powyżej pokazują skutek.
- Relacje OSM `route=bicycle` — nie zaimplementowane (zapytanie relacji jest kosztowne).
- Wariant odległości po sieci duktów — opcjonalny, nie zrobiony.
- Sieć dróg łączy odcinki tylko przez wspólne wierzchołki (zaokrąglone do 1 m); skrzyżowania
  bez wspólnego wierzchołka nie są łączone. Dojazdy pożarowe BDL i drogi OSM to osobne
  szkielety (łączą się przez punkty dostępu przypięte do sieci ≤ 150 m).
- `S` (huff 0,1385, none 7,0) i wszystkie parametry `pressure.access_points.*` są **nieskalibrowane** i wybrane
  jako hipoteza (plan 3.3); `S` dobrane tymczasowo do mediany P w gravity, jak `d_half` w 1.5.
- Populacja punktów dostępu z siatki GUS (bufor 30 km); przy braku siatki liczy się z
  miejscowości OSM z imputacją, ale osiedla przy lesie (typ `settlement`) wtedy nie powstają.
- (Nieaktualne od „Ciągu dalszego”, gdzie przebieg na żywo wykonano.) Pierwotnie pełny przebieg `pipeline.prepare_trip` nie był uruchomiony:
  wymagałby nowego dnia danych pogodowych i radarowych z sieci (współdzielone limity z drugą
  sesją). Zamiast tego: (a) źródła punktów dostępu pobrane naprawdę i przepuszczone przez
  ten sam kod (`scripts/faza3_raport.py`) na wynikach przebiegu 1.6, (b) testy integracyjne
  `run_trip_preparation` z atrapami źródeł sprawdzają eksport, manifest, kartę i diagnostykę
  (`tests/test_search_area.py`). Eksport `access_points`/`forest_roads` z realnych danych
  wczytano w interfejsie (przełączanie warstw działa w przeglądarce).
- Rozmiary eksportu z realnych danych: `access_points` 0,75 MB (3145 punktów), `forest_roads`
  6,2 MB (28 990 odcinków, uproszczenie 4 m, limit 6 MiB). Rozmiar zależy głównie od liczby
  odcinków, nie od wierzchołków, więc właściwości są skrócone (klasę atrakcyjności liczy
  przeglądarka). Pliki nie są w repozytorium (odtwarza je `scripts/faza3_raport.py`).
- Strava: nie używana.

## Testy

Wynik pełnych przebiegów jest podany w rozmowie (backend `pytest`, frontend `vitest` + `tsc`).
Nowe testy: `tests/test_access_data.py`, `test_access_points.py`, `test_access_pressure.py`,
`test_access_export.py`, dodatki w `test_mvp.py` i `test_search_area.py`, `model.test.ts`,
`sync-data.test.mjs`.

## Jak powtórzyć

```
python scripts/faza3_fetch_access.py --lat 50.527 --lon 18.605 --radius-km 20   # pobranie do cache/access_tiles
python scripts/faza3_raport.py                                                    # raport offline z cache
```

---

# Ciąg dalszy (2026-09-29): wjazdy, Huff, stabilność, przebieg na żywo

Baza nadal `master` bez Fazy 2 (`ulepszenia-faza2` nie jest scalona). **Rebase na `master`
po scaleniu Fazy 2 jest jeszcze do zrobienia** (spodziewane konflikty: eksport, manifest,
launcher, diagnostyka). Liczby poniżej: Kieleczka, 19 716 wydzieleń, 14 399 w masce; skrypt
`scripts/faza3_huff_raport.py`, dane w `docs/porownania/faza3/raport_huff.json`.
Wcześniejsze sekcje tego raportu opisują wariant `none` (jedyny wtedy); po tym kroku domyślny
jest `huff`.

## 1. Diagnoza wjazdów

1693 wjazdy = **360** `crossing_public` (droga publiczna przecina las, w ≤ 60 m zaczyna się
dukt), **774** `crossing_track` (dukt przecina las, droga publiczna ≤ 300 m), **559** `junction`
(koniec duktu ≤ 20 m od drogi publicznej w lesie); wszystkie ze źródła OSM. Do tego 153 szlabany
(OSM), 148 parkingów BDL, 230 OSM, 921 osiedli GUS.

Udział w łącznej presji surowej (suma po wydzieleniach w masce):

| Typ / podtyp | none | huff |
|---|---|---|
| wjazd, razem | 61,2% | 27,8% |
| — crossing_public | 12,3% | 5,2% |
| — crossing_track | 26,9% | 12,9% |
| — junction | 22,1% | 9,6% |
| szlaban | 6,1% | 2,7% |
| parking, razem | 29,2% | 22,9% |
| — parking OSM | 13,3% | 12,9% |
| — parking BDL | 15,9% | 10,0% |
| osiedle przy lesie | 1,4% | **45,3%** |
| korytarz dróg leśnych | 2,2% | 1,3% |

Który typ jest największym składnikiem presji wydzielenia: w `none` parking 71%, wjazd 22%; w
`huff` osiedle 53%, parking 37%, korytarz 5%, wjazd 4%.

Wnioski:
- W `none` wjazdy dominowały (61%), bo każdy z 1693 punktów zbierał całą ludność w promieniu
  20 km (A_norm wjazdu ma medianę 0,70, czyli nasycone: wjazdy nie różnią się atrakcyjnością).
  Najliczniejsze były `crossing_track` (774) i `junction` (559), a nie asfaltowe
  `crossing_public`. Podtyp `junction` (koniec duktu przy drodze) jest najsłabiej uzasadniony
  („dukt kończy się przy drodze” nie znaczy „tu ktoś zaparkuje”); do decyzji, czy go zostawić.
- Do przejrzenia z ortofotomapą: `kontrola_reczna.csv` ma teraz po 5 losowych wjazdów z każdego
  podtypu (`wjazd_crossing_public`, `wjazd_crossing_track`, `wjazd_junction`) oprócz
  wcześniejszych 10 wjazdów i 10 parkingów. **Nieprzejrzane.**

## 2. `population_split`: huff vs none

Huff: ludność każdego oczka GUS dzielona między punkty samochodowe (parking, wjazd, szlaban,
fallback) w zasięgu dojazdu proporcjonalnie do `w_t × g(d)`, suma udziałów oczka = jego
ludność (test jednostkowy). Osiedla przy lesie (pieszo) bez podziału. `S` dobrane osobno do tej
samej mediany P co gravity (0,373): **huff S = 0,1385**, none S = 6,96 (w profilu 7,0).

| Miara (maska) | gravity | none | huff |
|---|---|---|---|
| mediana P | 0,373 | 0,373 | 0,373 |
| udział lasu z P > 0,5 (cały las) | 32,3% | 32,0% | **33,8%** |
| Spearman P vs gravity | | 0,747 | 0,785 |
| Spearman R vs gravity | | 0,960 | 0,951 |
| top-20 wspólnych z gravity | | 5 | 5 |
| rejony (5) zachowane vs gravity (≤ 1,6 km) | | 4 | 3 |

huff vs none: Spearman P 0,835, Spearman R 0,964, **top-20 wspólnych 19/20**, rejony 4/5.

Profil P przy Lublińcu (wydzielenia ≤ 8 km od centrum, średnie P wg odległości od najbliższego
dużego osiedla; te same pasy co wcześniej):

| Pas | wydz. | gravity | none | huff |
|---|---|---|---|---|
| 0–0,5 km | 14 | 0,63 | 0,49 | **0,97** |
| 0,5–1 km | 67 | 0,66 | 0,58 | **0,92** |
| 1–2 km | 384 | 0,52 | 0,50 | 0,72 |
| 2–3 km | 460 | 0,40 | 0,37 | 0,37 |
| 3–5 km | 1021 | 0,38 | 0,42 | 0,32 |
| > 5 km | 118 | 0,44 | 0,51 | 0,42 |

Przy `huff` presja przy Lublińcu maleje z odległością prawie monotonicznie (0,97 → 0,32) i
nie rośnie z powrotem w głębi lasu, więc kryterium „nie na kilometry w głąb” jest spełnione
lepiej niż w `none` (tam 0,37 → 0,51).

**Ważny skutek uboczny, do decyzji właściciela.** Podział zmniejsza `A_k` punktów samochodowych
(mediana A_norm: parking 0,78 → 0,03, wjazd 0,70 → 0,01), a `a_half` zostało bez zmian (zgodnie z
poleceniem dobrano tylko `S`), bo osiedla nie są dzielone (A_norm osiedla mediana 0,13, p90
0,46). Stąd w `huff` osiedla są największym składnikiem presji (45%) i głównym źródłem
presji dla 53% wydzieleń, a parkingi i wjazdy mają mały udział. Dobór `a_half` dla typów
samochodowych (np. z mediany A po podziale) albo wagi osiedli nie był robiony. Wynik `huff`
trzeba czytać jako „presja od miast i osiedli przy lesie, z poprawką na parkingi”, nie jako
równowagę parkingi/osiedla.

## 3. Stabilność rankingu (huff): ±30% jednego parametru

Baza: `huff`, `S = 0,1385`. Top-20 = 20 najwyżej ocenionych wydzieleń w masce o powierzchni
≥ 0,5 ha (jak w interfejsie); „rejony” = ile z 5 bazowych rejonów ma odpowiednik (środek ≤ 1,6 km)
po zmianie. Parametry w profilu **nie zostały zmienione**.

| Parametr | −30%: top-20 / rejony | +30%: top-20 / rejony |
|---|---|---|
| S | 19 / 5 | 18 / 5 |
| zasięg wjazdów (wjazd i szlaban) | 16 / 5 | 15 / 4 |
| waga wjazdów (wjazd i szlaban) | 19 / 5 | 19 / 4 |
| zasięg parkingów | 19 / 5 | **14** / 5 |
| waga parkingów | 17 / 4 | 19 / 5 |
| zasięg zbierania ludności (parking, wjazd, szlaban) | 17 / 5 | 19 / 5 |

Top-20 zostaje w 14–19 wydzieleniach z 20, rejony w 4–5 z 5; Spearman R względem bazy ≥ 0,997 w
każdym wariancie. Najwrażliwsze: zasięg parkingów +30% (14/20) i zasięg wjazdów (15–16/20).
Zestaw rejonów jest w praktyce stabilny (co najwyżej jeden rejon zmienia się w części
wariantów), skład top-20 umiarkowanie stabilny.

## 4. Wiedza lokalna

`dane_terenowe/wiedza_lokalna.csv` **nie istnieje** (jest tylko `punkty_prognozy.json`), więc
porównanie P w obu modelach dla punktów „oblegane/spokojne” nie zostało zrobione. Gdy plik
się pojawi, wystarczy policzyć P (gravity i access_points huff) w tych punktach; wyniki z
prywatnych współrzędnych nie powinny trafiać do repozytorium.

## 5. Przebieg na żywo (2026-09-29)

`python -m pipeline.prepare_trip --lat 50.527 --lon 18.605 --radius-km 20 --bdl-packages-dir BDL
--population-grid-path <siatka GUS>`: przeszedł bez błędu, 19 716 wydzieleń, 14 399 w masce,
5 rejonów, radar 91% pokrycia okna, `population_source: gus_siatka`.
Manifest: `pressure_model_used: access_points`, `population_split: huff`, `S: 0,1385`, punkty
zgodne z raportem (148 / 230 / 1693 / 153 / 921), 0 kafli fallbacku, 0 kafli z błędem.
Mediana P w masce 0,3732; eksporty `access_points` 0,75 MB i `forest_roads` 6,2 MB.
Migawka „Kieleczka — faza 3” zapisana przez `launcher/trip_archive.save_trip` (w
`frontend/public/data/trips/`, poza repozytorium).
Sprawdzone w przeglądarce (dev server, dane z migawki): warstwy parkingów, wjazdów/szlabanów
i dróg leśnych widoczne i przełączane w legendzie; popup punktu (parking BDL: nazwa, źródło,
atrakcyjność niska); karta wydzielenia „Dostęp: najbliższy parking 1980 m · wjazd lub szlaban
1890 m · utwardzony dukt 2250 m” z elementem o największym wpływie na presję. Popup odcinka
drogi nie był klikany ręcznie (jest pokryty testem jednostkowym `attractivenessClass`).

## 6. BLOCKED (decyzja właściciela)

BDOT10k `OT_SKDR_L` i `route=bicycle` zostają BLOCKED, niski priorytet: klasyfikacja nawierzchni
prawie nie zmienia P (Spearman ≥ 0,9998 przy skrajnych założeniach).

## Testy (po tym kroku)

Backend `pytest`: 699 zaliczonych; nowe testy `population_split` w `tests/test_access_pressure.py`.
