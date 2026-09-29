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
| 4.4 Panel 7 dni — agregacja | DONE (po poprawce panelu przeliczone) | reguła (różnica > 0,05) **niespełniona** (max 0,043) → zostaje `median_of_features` |
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

**Poprawka po pierwszej wersji raportu (spójność panelu z mapą).** Pierwsza tabela (niżej, „przed poprawką”) była policzona z osi czasu warunków opartej na
surowym opadzie modelu Open-Meteo i puli komórek klimatologii; panel dawał dziś F ≈ 0,45, a mediana F wydzieleń na mapie wynosiła 0,647. Po poprawce
oś czasu liczy opad **tak jak wydzielenia** (seria per wydzielenie: radar RainGRS scalony z modelem dla dni przeszłych, model dla prognozy; średnia
ważona powierzchnią wydzieleń w masce przy najbliższym punkcie pogody), a percentyl każdego punktu względem historii **własnej komórki** klimatologii
(`prepare_trip.stand_precip_to_points`, `apply_point_precip`, `conditions_timeline(point_clim_cells=…)`). Wynik na przebiegu Kieleczka 20 km:
**panel dziś 0,636, mediana F wydzieleń w masce 0,641** (różnica 0,005; wymagane ≤ 0,02).

Tabela **po poprawce** (przebieg przez launcher, 20 km, 7 dni; kolumny = metody agregacji zapisane w `conditions_{day}.json`):

| Dzień | mediana cech (dotychczasowa) | mediana F po punktach | mediana F po wydzieleniach | średnia F ważona powierzchnią | max różnica |
|---|---|---|---|---|---|
| 29.09 | 0,636 | 0,636 | 0,636 | 0,632 | 0,004 |
| 30.09 | 0,556 | 0,542 | 0,542 | 0,559 | 0,017 |
| 01.10 | 0,457 | 0,463 | 0,463 | 0,485 | 0,028 |
| 02.10 | 0,377 | 0,381 | 0,376 | 0,407 | 0,031 |
| 03.10 | 0,311 | 0,311 | 0,306 | 0,343 | 0,037 |
| 04.10 | 0,278 | 0,282 | 0,282 | 0,311 | 0,033 |
| 05.10 | 0,261 | 0,272 | 0,277 | 0,304 | 0,043 |

**Decyzja (reguła: zmiana metody tylko gdy różnice > 0,05 w którymś dniu): reguła NIEspełniona (max 0,043), więc wcześniejsza decyzja o `median_f_stands`
NIE obowiązuje** — opierała się na różnicy 0,086, która wynikała z błędu panelu (opad modelu), nie z samej metody agregacji. Domyślnie wraca
`conditions.aggregation: median_of_features` (dotychczasowa). Pozostałe metody dostępne w profilu i w `F_by_aggregation`. Test spójności z mapą
(`tests/test_panel_spojnosc_z_mapa.py`) sprawdza wprost `median_f_stands` (jak w poleceniu) i pokazuje, że bez poprawki panel rozjeżdża się z mapą
o > 0,02; dla domyślnej metody dzień 0 również zgadza się z mapą (0,636 vs 0,641 na przebiegu rzeczywistym).

Przed poprawką (opad modelu, pula komórek; przebieg 25 km): 29.09 0,452 / 0,452 / 0,462 / 0,501 (max 0,049) … 02.10 0,237 / 0,235 / 0,247 / 0,321 (max 0,086) … 05.10 0,173 / 0,172 / 0,177 / 0,232 (max 0,060) — patrz `docs/porownania/faza4/nasycenie_agregacja.json`.

**Lokalne zjawiska.** Panel ma udział powierzchni lasu z przymrozkiem (tmin3 < 0 °C) i z silnym opadem dobowym (≥ 15 mm). W tym przebiegu oba wynoszą 0% w każdym dniu
(brak przymrozków i silnych opadów prognozowanych w horyzoncie) — mechanizm przetestowany tylko na danych syntetycznych.

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

## Poprawki przed scaleniem

**1. Paczki BDL w każdym przebiegu (dokończenie 1.3).** Przyczyna: `BDL/` (9 paczek nadleśnictw RDLP Katowice) leży w katalogu repo, ale domyślny katalog
paczek to `<cache>/bdl_packages` (nie istnieje), a launcher woła `python -m pipeline.prepare_trip --lat --lon --radius-km` bez `--bdl-packages-dir`
i nie ma pola/konfiguracji na tę ścieżkę — każdy przebieg z launchera miał więc 100% składu z WFS (tak samo migawki fazy 1.6/3/4). Naprawa:
`pipeline/local_config.py` — kolejność: `--bdl-packages-dir` > zmienna `BOROWIK_BDL_DIR` > `local_config.json` w katalogu repo (w `.gitignore`, poza repozytorium; klucz
`bdl_packages_dir`, ścieżka bezwzględna lub względem pliku) > `<cache>/bdl_packages`. Na tej maszynie `local_config.json` wskazuje `BDL/`. Brak katalogu daje jawne „UWAGA” w logu.
Baner z 1.3 **nie był zaimplementowany w interfejsie** (w NOC_RAPORT oznaczony jako odłożony; jedynie log konsoli) — dodany: interfejs czyta `manifest.json`
(`wfs_only_share_of_masked`) i pokazuje „Skład drzewostanu tylko z opisu WFS … dla X% wydzieleń w masce”, gdy > 20% (`wfsOnlyBanner`). Zweryfikowany w przeglądarce na
podmienionej wartości 35% (na prawdziwych danych baner słusznie się nie pokazuje: 10,9% < 20%; zrzuty `*_baner_wfs_35proc_test.jpg`, manifest przywrócony).
Test: `tests/test_local_config.py` (kolejność źródeł; `main([--lat --lon --radius-km])` jak launcher przekazuje do przebiegu skonfigurowany katalog) + przebieg na żywo niżej.

**2. Panel warunków spójny z mapą** — opis i tabela w 4.4.

## Wynik przebiegu (4.6)

Przebieg identyczny z tym, co robi launcher (`python -m pipeline.prepare_trip --lat 50.527 --lon 18.605 --radius-km 20`, bez żadnych dodatkowych parametrów,
potem `npm run sync-data`, potem zapis migawki funkcją launchera `save_trip`; GUI Tk nie było uruchamiane): log „Paczki BDL: 45565 wydzieleń z pełnym składem gatunkowym”.
Migawka **„Kieleczka — faza 4 (paczki)”** (`frontend/public/data/trips/kieleczka-faza-4-paczki-2026-09-29/`; poprzednia „Kieleczka — faza 4” zostaje jako wersja sprzed poprawek).

- **Skład z paczek: 89,1% wydzieleń w masce** (14 399 w masce; WFS-only 10,9% → poniżej progu banera). Nadleśnictwa: 02-03 100%, 02-16 100%, 02-19 99,9%, 02-14 97,1%, 02-25 95,8%, 02-29 90,9%;
  **bez paczki: 02-31 (1339 wydzieleń) i 02-06 (5)**.
- **F panelu vs mediana mapy (dziś): 0,636 vs 0,641** (mediana R 47,6; 5 rejonów).
- Zmiana H/R względem migawek sprzed poprawki jest oczekiwana (skład z paczek zamiast WFS); F i F_loc niezmienione — F jest niezależne od składu, a poprzednia migawka miała identyczne F/F_loc (0 różnic).

**Przeglądarka (zrzuty w `docs/porownania/faza4/zrzuty/`).** Komputer 1536 px: panel z dniami (dni od 4. naprzód wyszarzone „prognoza niepewna”), składniki, notka; karta rejonu z sekcją „Pogoda w tym miejscu”.
Telefon: okno przeglądarki nie dało się zwęzić narzędziem, więc widok 375 px to ta sama aplikacja w ramce iframe o szerokości 390 px — bez poziomego przewijania (scrollWidth = clientWidth = 375),
panel, baner i karta czytelne, dni prognozy zawijają się do drugiego wiersza. Poprawka stylu po zrzucie komputerowym: nagłówek „Pogoda w tym miejscu” zmniejszony, baner wyrównany do panelu (bez ponownego zrzutu).
Karta wydzielenia (widok „Wydzielenia”/szczegóły) używa tej samej funkcji `weatherSection`; sprawdzona tylko na karcie rejonu.

## Testy

- Backend: `python -m pytest` → **778 passed** (przed Fazą 4: 748). Nowe: `test_faza4_r_niezmienione.py` (F/F_loc/R przypięte do kodu sprzed Fazy 4), `test_faza4_pogoda.py`
  (udział prognozy, składniki, karta pogody, agregacja opadu wydzieleń do punktów), `test_panel_spojnosc_z_mapa.py` (panel = mediana mapy ≤ 0,02, i że bez poprawki różnica > 0,02),
  `test_local_config.py` (ścieżka paczek BDL), rozszerzone `test_prepare_trip.py` i `test_conditions_timeline.py`. Dodany `tests/conftest.py`: testy nie czytają lokalnego
  `local_config.json` ani `BOROWIK_BDL_DIR` (bez tego testy wywołujące przebieg ładowały prawdziwe paczki BDL i wisiały — złapane przy pierwszym pełnym przebiegu po dodaniu konfiguracji).
- Frontend: `npx vitest run` → **98 passed** (w tym baner WFS i składniki pogody); `npx tsc --noEmit` czysto; `vite build` OK.
- Brak testu dla mapowania kwantylowego — nie wdrożone (reguła 4.2).
