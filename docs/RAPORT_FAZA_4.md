# Raport — Faza 4 (pogoda: przejrzystość, spójność, oszczędność API)

Gałąź: `ulepszenia-faza4` (z `master`, `c907883`). Nic nie było pushowane ani scalane, cache i dane nie były usuwane
(cache tylko przybył: kilka punktów pogody, 50 punktów archiwum ERA5). Progi klas F, krzywa sezonowości, α i wagi H
**nie zostały zmienione**. Wszystkie liczby: Kieleczka (50,527 N, 18,605 E), promień 25 km dla analiz 4.1–4.4
(129 653 wydzielenia → 29 953 w promieniu, 21 716 w masce), 29.09.2026.
Surowe wyniki: `docs/porownania/faza4/*.json`, skrypty: `scripts/faza4_*.py` (tylko z cache; jedyne wywołania API są opisane niżej).

## Status zadań

| Zadanie | Status | Decyzja wg reguły z planu |
|---|---|---|
| 4.1 Rzadsza siatka temperatury/ET0 | DONE | reguła **nie spełniona** → `weather.temp_grid_km` zostaje opcją, domyślnie bez zmian |
| 4.2 Spójność percentyli radar / ERA5 / E-OBS | DONE (E-OBS vs radar: BLOCKED, powód niżej) | mediana \|Δpct\| = 0,095 ≤ 0,10 → **mapowanie kwantylowe nie wdrożone** |
| 4.3 Nasycenie F — diagnoza i prezentacja | DONE | bez zmian w modelu; składniki + notka w panelu i karcie |
| 4.4 Panel 7 dni — agregacja | DONE | reguła (różnica > 0,05) spełniona → domyślnie `median_f_stands` |
| 4.5 Niepewność prognozy w interfejsie | DONE | progi w profilu `ui.*`, oznaczenia w panelu, udział prognozy w karcie |
| 4.6 Przebieg i raport | DONE | migawka „Kieleczka — faza 4” (promień 20 km jak w migawkach faz 1.6 i 3) |

## 4.1 Rzadsza siatka temperatury i ET0

Wdrożone: profil `weather.temp_grid_km` (`null` = dotychczasowe zachowanie: 5 km przy promieniu 25 km, skalowane z promieniem;
liczba = odstęp w km, bezwzględny). `pipeline.prepare_trip.weather_grid_spacing_m`; siatki 10 i 15 km są podzbiorami
siatki 5 km (siatka zakotwiczona w EPSG:2180), więc cache punktów jest wspólny. Opad z radaru jest liczony per wydzielenie
i od siatki nie zależy; rzadsza siatka zubaża tylko opad modelowy (uzupełnienia, prognoza).

Koszt jednego świeżego przebiegu (wzór Open-Meteo: punkty × dni/14 × zmienne/10; zmienne = 5 dziennych + 1 godzinowa;
pogoda główna 92 dni wstecz + 1, oś warunków 7 dni na punktach w promieniu):

| Wariant | Punkty (cały obszar / w promieniu) | Waga: pogoda + oś warunków | Względem obecnego |
|---|---|---|---|
| obecny (5 km) | 144 / 79 | 574 + 335 = **909** | — |
| 10 km | 49 / 19 | 195 + 81 = **277** | −70% |
| 15 km | 30 / 9 | 120 + 38 = **158** | −83% |

Jakość (21 716 wydzieleń w masce; „cel dziś” = dzień analizy, „cel +6” = prognoza 6 dni naprzód, z opadem modelowym):

| Wariant / cel | Spearman F | Spearman R | max \|ΔF\| | **p95 \|ΔF\|** | mediana \|ΔF\| | zmiana klasy F |
|---|---|---|---|---|---|---|
| 10 km / dziś | 0,941 | 0,959 | 0,191 | **0,114** | 0,010 | 2 157 (9,9%) |
| 15 km / dziś | 0,946 | 0,965 | 0,146 | **0,114** | 0,013 | 1 507 (6,9%) |
| 10 km / +6 dni | 0,950 | 0,956 | 0,156 | **0,063** | 0,010 | 2 353 (10,8%) |
| 15 km / +6 dni | 0,942 | 0,961 | 0,163 | **0,067** | 0,010 | 2 911 (13,4%) |

(R bez presji P, która od pogody nie zależy.)

**Przymrozki.** W horyzoncie 28.09–04.10 nie wystąpił żaden przymrozek (tmin z 3 dób ≥ 0 °C na żadnym punkcie siatki 5 km), więc
w żadnym wariancie żadne wydzielenie nie zyskuje ani nie traci przymrozku — ale ten test jest **pusty** (nie było czego zgubić);
o zachowaniu rzadszej siatki przy lokalnych przymrozkach ten przebieg nic nie mówi.

**Decyzja (reguła: p95 \|ΔF\| ≤ 0,02 i brak zmiany przymrozku): NIE.** p95 = 0,114 (dziś) i 0,063–0,067 (+6) — kilkukrotnie ponad
progiem. Wariant zostaje opcją; domyślne zachowanie bez zmian. Uwaga: w F wariancja logarytmu to niemal w całości M (patrz 4.3), więc
ΔF pochodzi głównie z wilgotności (ET0 i uzupełnienia opadu modelem), nie z temperatury — nie rozkładałem tego dokładniej.

Wywołania API w tej sesji: dociągnięcie brakujących punktów siatek 10/15 km (fd1: 13+12 pkt) i prognozy 7-dniowej siatki 5 km
(65+13+12 pkt) ≈ 480 jednostek wagi; ERA5 do 4.2 ≈ 69. Razem ≈ 550 (limit dzienny 10 000).

## 4.2 Spójność percentyli (bieżące vs klimatologia)

**Zmierzone** na 50 punktach (co ~3. punkt siatki 5 km w promieniu 25 km), oknach 26 dni kończących się 22–28.09.2026
(radar RainGRS z cache, blok 10 × 10 km jak rozdzielczość ERA5-Land; ERA5 z Open-Meteo archive, koszt ≈ 69; klimatologia ERA5
z cache; ET0 z ERA5 w obu wariantach, więc różnica percentyla wynika wyłącznie z opadu). 350 par punkt–okno.

| Porównanie (P26w ważone wykładniczo) | mediana różnicy | stosunek | Spearman | mediana \|Δpct CWB26\| | p90 \|Δpct\| |
|---|---|---|---|---|---|
| radar − ERA5 | −6,3 mm (IQR −9,0…−3,1) | 0,84 | 0,69 | **0,095** | 0,18 |
| model Open-Meteo − ERA5 | −11,3 mm | 0,71 | 0,38 | 0,179 | 0,33 |
| model Open-Meteo − radar | −7,4 mm | 0,79 | 0,26 | 0,158 | 0,23 |

Zwykła suma 26 dni: radar 58,6 mm vs ERA5 76,6 mm (mediana różnicy −16 mm). Mediana percentyla: radar 0,68, ERA5 0,78.

**Decyzja (reguła: mediana \|Δpct_CWB26\| > 0,10 → mapowanie kwantylowe za flagą): NIE** — 0,095 ≤ 0,10, więc bez zmian i bez mapowania.
Wynik jest jednak tuż pod progiem, radar jest systematycznie „suchszy” od ERA5 (ok. −0,09 percentyla), a to okno mierzy tylko
jeden tydzień/jeden obszar — przy większym materiale reguła mogłaby wypaść inaczej. Ważniejsze odkrycie: **opad modelowy Open-Meteo jest
jeszcze suchszy względem ERA5 niż radar** (0,71 vs 0,84; mediana \|Δpct\| 0,18) — patrz 4.4.

Ograniczenia: 7 okien kończących się w kolejnych dniach nakłada się w ~20 z 26 dni (to praktycznie jedno niezależne okno); archiwum
radaru w cache ma dni z brakującymi godzinami (np. 19/24) — doby z ≥ 16 godzin są skalowane o oczekiwane/zaobserwowane godziny
(zakłada podobny opad w brakujących godzinach), doby poniżej 16 godzin odrzucone; ERA5 z archiwum Open-Meteo ma opóźnienie kilku dni.

**E-OBS vs radar: BLOCKED** — lokalne E-OBS kończą się na 2025, nie ma nakładania z radarem 2026. Zamiast tego (2.6, opisowo):
E-OBS vs ERA5 na dobowym archiwum z cache (135 punktów, lata 2018/2020/2022, koniec okna 1.08–31.10, 7 728 obserwacji P26w):
kwantyle 5/25/50/75/95 — ERA5: 8,5 / 17,7 / 28,0 / 42,1 / 67,1 mm; E-OBS: 6,5 / 14,1 / 23,5 / 37,1 / 64,4 mm; mediana stosunku E-OBS/ERA5 = 0,85,
Spearman 0,85, mediana \|różnicy percentyla\| ≈ 0,10. E-OBS (uśredniony zespół 0,1°) jest więc ok. 15% „suchszy” niż ERA5 w środku rozkładu,
podobnie jak radar. Produkcja bez zmian.

## 4.3 Nasycenie F — diagnoza i prezentacja

**Diagnoza** (bez zmian w modelu; rekonstrukcja F z składników zgadza się z eksportem z dokładnością 1e-9):

- 29.09: F mediana 0,647; klasy: Umiarkowane 5,0%, Dobre 57,6%, Bardzo dobre 37,4%. Nasycenia dzisiaj nie ma.
- Historia z cache: 25.09 „Bardzo dobre” 49,5%, 26.09 49,5%, **27.09 99,8%** (to było nasycenie z zadania), 28.09 55,2%, 29.09 37,4%.
- **Co powoduje**: udział M w wariancji log F ≈ **99,97%**; T ≈ 0,99 (95% wydzieleń T > 0,97, 99,9% > 0,9), K_frost = 1 (brak przymrozków),
  G_season stałe 0,88. F w praktyce = 0,88 · M^0,6 — a M to sigmoida percentyla bilansu wodnego, więc gdy percentyl przekracza ~0,7
  (jak 27.09), całość wpada w „Bardzo dobre”. Temperatura we wrześniu nie różnicuje wcale.
- **Czułość ±10% jednego parametru** (liczba z 21 716 wydzieleń zmieniających klasę): `moisture_midpoint` −10%: 5 247, +10%: 8 133;
  `temp_optimum_c` −10%: 2 683, +10%: 290; `moisture_slope` 733 / 656; `temp_sigma_c` 14 / 54; G_season (mnożnik) −10%: 6 758, +10%: 4 284;
  progi wilgotnościowe siedliska, kara upałowa i przymrozkowa — 0 (dziś nie działają). Klasa jest więc czuła praktycznie tylko na
  punkt środkowy sigmoidy wilgotności, optimum temperatury i sezonowość — czyli na nieskalibrowane parametry.
- Progów klas **nie zmieniono**.

**Prezentacja** (tylko interfejs, bez wpływu na R; `tests/test_faza4_r_niezmienione.py` przypina F/F_loc/R z kodu sprzed Fazy 4):
karta wydzielenia (`details_{day}.json` → `weather`; sekcja „Pogoda w tym miejscu”): opad z 26 dni w mm; bilans wodny z 26 dni
„X mm, typowo o tej porze Y mm (percentyl Z)” (bilans = opad minus parowanie, bo z takiej wielkości liczony jest percentyl;
klimatologia nie przechowuje samego opadu); średnia temperatura 20 dni z optimum; przymrozek tak/nie z siłą, minimum i datą; F jako liczba;
stała notka „Ocena pogody nie została potwierdzona…”. Panel warunków: te same składniki dla dnia dzisiejszego (mediana obszaru) i ta sama notka.

## 4.4 Panel 7 dni — agregacja

Cztery metody policzone na tym samym przebiegu (fd7, 79 punktów w promieniu, wagi = powierzchnia/liczba wydzieleń w masce przy najbliższym punkcie):

| Dzień | mediana cech (obecna) | mediana F po punktach | mediana F po wydzieleniach | średnia F ważona powierzchnią | max różnica |
|---|---|---|---|---|---|
| 29.09 | 0,452 | 0,452 | 0,462 | 0,501 | 0,049 |
| 30.09 | 0,363 | 0,361 | 0,377 | 0,433 | 0,072 |
| 01.10 | 0,288 | 0,287 | 0,297 | 0,371 | 0,084 |
| 02.10 | 0,237 | 0,235 | 0,247 | 0,321 | 0,086 |
| 03.10 | 0,197 | 0,196 | 0,209 | 0,280 | 0,084 |
| 04.10 | 0,184 | 0,183 | 0,191 | 0,256 | 0,073 |
| 05.10 | 0,173 | 0,172 | 0,177 | 0,232 | 0,060 |

**Decyzja (reguła: zmiana metody tylko gdy różnice > 0,05 w którymś dniu): reguła spełniona (max 0,086)**, więc zmiana jest dozwolona.
Wybrano **`median_f_stands`** (mediana F po wydzieleniach w masce) — ta sama statystyka, co „mediana dla wydzieleń” pokazywana w interfejsie,
odstaje od dotychczasowej wartości o ≤ 0,014, odporna na pojedyncze punkty. Średnia ważona powierzchnią (odstająca o 0,05–0,09) odrzucona:
średnia jest podatna na skośność, a wagi czynią z kilku punktów przy dużych lasach całość panelu. Poprzednia metoda zostaje dostępna
(`conditions.aggregation: median_of_features`), a `conditions_{day}.json` zawiera `F_by_aggregation` dla wszystkich czterech.

**Lokalne zjawiska.** Panel dostał udział powierzchni lasu z przymrozkiem (tmin3 < 0 °C) i z silnym opadem dobowym (≥ 15 mm) w każdym dniu.
W tym przebiegu oba wynoszą 0% (brak przymrozków i silnych opadów w horyzoncie), więc nic nie zostało „ukryte”, ale i nic nie zostało pokazane;
mechanizm jest przetestowany na danych syntetycznych (przymrozek na 25% powierzchni przy medianie tmin3 powyżej zera).

**Znalezisko poza planem (niezałatwione).** Panel dla dnia dzisiejszego daje F ≈ 0,45, a mediana F wydzieleń na mapie to 0,647 — różnica 0,2.
Prawdopodobna przyczyna (spójna z 4.2, nieweryfikowana bezpośrednio): w trybie `radar.mode: stand` oś czasu warunków liczy się z **surowego opadu modelu
Open-Meteo bez radaru**, który jest suchszy (0,71 × ERA5) niż radar (0,84 × ERA5), a percentyl dostaje sigmoida o stromości 0,10. Panel i mapa opisują więc ten
sam dzień różnymi liczbami. Nie zmieniałem tego (poza zakresem planu; zmieniłoby wartości panelu) — do decyzji właściciela.

## 4.5 Niepewność prognozy

Profil: `ui.forecast_uncertain_from_day: 4`, `ui.forecast_indicative_from_day: 8` (dni naprzód od dziś, dziś = 0; do aktualizacji po 2.7).
`conditions_{day}.json`: dla każdego dnia `days_ahead` i `uncertainty` (`ok` / `uncertain` / `indicative`), plus `uncertainty_thresholds`.
Panel wyszarza dni „prognoza niepewna” (opacity 0,6, etykieta) i „orientacyjnie” (0,45, przerywana ramka) i dodaje krótką notkę. Panel obejmuje
dni 0–6, więc „orientacyjnie” (≥ 8) pojawi się dopiero po wydłużeniu horyzontu (`conditions.horizon_days`). Karta wydzielenia przy wyjeździe za ≥ 4 dni pokazuje
„ok. X% oceny opadu pochodzi z prognozy” = wykładniczo ważony (jak P26w) udział okna 26 dni leżący w przyszłości
(`pipeline.weather.forecast_window_share`, kolumna `forecast_window_share`, także w `details.weather`). To udział z liczby dni prognozy, nie ten sam co
`rain_radar_coverage` (1.5.3), który mierzy udział radaru.

## 4.6 Przebieg i testy

Przebieg Kieleczki (promień 20 km, kod z tej gałęzi): zob. sekcja „Wynik przebiegu” poniżej. Testy: sekcja „Testy”.
Zmienione pliki: `pipeline/{prepare_trip,orchestrate,weather,conditions_timeline,export}.py`, `profiles/boletus_edulis.yaml`,
`frontend/src/{model,main}.ts`, `frontend/src/{model.test.ts,style.css}`, testy `tests/test_faza4_*.py`, `tests/test_{prepare_trip,conditions_timeline}.py`,
skrypty `scripts/faza4_*.py`.

## Wynik przebiegu (4.6)

`python -m pipeline.prepare_trip --lat 50.527 --lon 18.605 --radius-km 20 --out-dir output/faza4_kieleczka` (kod z gałęzi, 19 716 wydzieleń,
14 399 w masce, 5 rejonów), zsynchronizowany do frontendu i zapisany jako migawka **„Kieleczka — faza 4”** (`frontend/public/data/trips/kieleczka-faza-4-2026-09-29/`).
**R niezmienione:** porównanie z ostatnią migawką sprzed Fazy 4 (`kieleczka-29-09-2026-09-29`, ten sam dzień i promień) na 19 711 wspólnych wydzieleniach:
F, F_loc, R, P i H identyczne (0 różnic). Panel warunków tego przebiegu: agregacja `median_f_stands`, dzień 5 oznaczony `uncertain`;
karta wydzielenia ma blok `weather` (np. opad 55 mm/26 dni, bilans −1,0 mm przy typowym −3,6 mm, percentyl 0,56, 14,0 °C przy optimum 13 °C, przymrozek: brak, F 0,66).
Uwaga poza Fazą 4: przebieg nadal ma 100% składu z WFS (paczki BDL nie są w `cache/bdl_packages`, a launcher nie przekazuje `--bdl-packages-dir`) — jak w poprzednich migawkach.
Wygląd panelu i karty nie był sprawdzany w przeglądarce (tylko testy jednostkowe, `tsc`, `vite build`).

## Testy

- Backend: `python -m pytest` → **769 passed** (przed Fazą 4: 748). Nowe: `tests/test_faza4_r_niezmienione.py` (wartości F/F_loc/R przypięte do kodu sprzed
  Fazy 4 i niezależność od `ui.*`), `tests/test_faza4_pogoda.py` (udział prognozy w oknie, składniki, karta pogody), rozszerzone `tests/test_prepare_trip.py`
  (siatka temperatury, wagi punktów) i `tests/test_conditions_timeline.py` (agregacja, niepewność, JSON bez NaN).
- Frontend: `npx vitest run` → **97 passed** (nowe: oznaczenia niepewności, składniki i przymrozek, udział prognozy ≥ 4 dni, lokalne zjawiska); `npx tsc --noEmit` czysto; `vite build` OK.
- Brak testu dla mapowania kwantylowego — nie wdrożone (reguła 4.2).
