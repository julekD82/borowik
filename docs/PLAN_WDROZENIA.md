# Borowik — plan wdrożenia ulepszeń

Wersja 8, 29.09.2026 (dodane Fazy 1.5, 1.6 i UI; przebudowane Fazy 2, 3 i 4). Plik przeznaczony do umieszczenia w `docs/PLAN_WDROZENIA.md` i realizacji przez Claude Code / Codex.
Kontekst techniczny: `docs/Borowik_opis_techniczny_i_walidacja.md` (numery rozdziałów [§] odnoszą się do tego dokumentu).

Fazy 0 i 1 są przeznaczone do pracy autonomicznej (noc 27/28.09). Faza 1.5 (opad z radaru ~1 km) i Faza 1.6 (pełniejsze dane BDL) również mogą być realizowane autonomicznie, po Fazie 1, w dowolnej kolejności. Fazy 2–6 wymagają decyzji właściciela lub danych terenowych i są realizowane w kolejnych sesjach.

---

## 0. Zasady pracy agenta (obowiązują we wszystkich fazach)

1. **Rano jest wyjazd.** Najważniejsze jest to, żeby rano istniał działający wynik dla Kieleczki. Dlatego Faza 0 (baseline na obecnym kodzie) jest wykonywana przed jakąkolwiek zmianą.
2. **Gałąź.** Pracuj na gałęzi `ulepszenia-faza1` utworzonej z bieżącego stanu. Nie zmieniaj `main`, nie pushuj, nie rób `git reset --hard`, `git clean`, force-push ani amend cudzych commitów. Jeden commit na zadanie, opis po polsku z numerem zadania (np. `1.3: paczki BDL w głównym przepływie`).
3. **Dane i cache.** Nie usuwaj ani nie nadpisuj istniejących plików cache, paczek BDL, eksportów w `notebooks/output/` ani migawek w `frontend/public/data/trips/`. Zmiana klucza cache = nowe pliki obok starych.
4. **Zmiana znaczenia wartości tylko za flagą.** Gdy zadanie zmienia sens liczby (np. normalizacja P), stare zachowanie zostaje dostępne przez parametr profilu/konfiguracji, a raport pokazuje porównanie przed/po.
5. **Nie stroić modelu pod wygląd mapy.** Nie zmieniaj wag H, progów klas F, krzywej sezonowości ani α, chyba że zadanie wprost tego wymaga. Saturacja „Bardzo dobre” to temat Fazy 4, nie nocy.
6. **Testy.** Każde zadanie kończy się dodanymi/zaktualizowanymi testami i przejściem pełnego zestawu: backend (`uv run pytest` lub odpowiednik z `pyproject.toml`) oraz frontend (skrypty testów i sprawdzenia TypeScript z `frontend/package.json`). Jeśli testów nie da się uruchomić z powodu środowiska, napraw środowisko bez zmiany wersji zależności w `uv.lock`; gdy się nie da — oznacz BLOCKED i opisz.
7. **Budżet API.** Open-Meteo w wersji darmowej: < 10 000 wywołań/dzień, 5 000/h, 600/min, koszt rośnie z liczbą dni/zmiennych i każdy punkt liczy się osobno. W nocy maksymalnie dwa pełne przebiegi analizy (baseline + końcowy) plus małe testy integracyjne na cache. Nie uruchamiaj backtestów, które pobierają pogodę z API.
8. **Blokady.** Gdy zadanie utknie (brak danych, niejasność, błąd zewnętrznego serwisu), oznacz je BLOCKED z powodem i przejdź do następnego. Nie pytaj właściciela w nocy — decyzję zapisz w raporcie.
9. **Raport.** Na bieżąco prowadź `docs/NOC_RAPORT.md`: status każdego zadania (DONE / BLOCKED / SKIPPED), podjęte decyzje, liczby przed/po, lista zmienionych plików. Na samej górze sekcja **„Na rano”** (maks. 15 linijek): którą migawkę użyć na wyjazd i dlaczego, oraz co trzeba wiedzieć.
10. **Język i dokumentacja.** Komunikaty, raport i opisy po polsku. Każda zmiana zachowania aktualizuje odpowiedni fragment README/CLAUDE.md, jeśli ten fragment ją opisuje.

---

## Faza 0 — zabezpieczenie wyjazdu (przed zmianami kodu)

**0.1 Środowisko.** Uruchom `uv sync` (lub odpowiednik), testy backendu i frontendu na obecnym kodzie. Zapisz wynik w raporcie jako punkt odniesienia (liczba testów, błędy). Znane ryzyko z [§17.1]: błędy ładowania bibliotek natywnych (NumPy, pyproj) w poprzednim środowisku.

**0.2 Lokalizacja paczek BDL.** Ustal, gdzie leżą rozpakowane paczki BDL (pytanie do właściciela na starcie sesji, jeśli nie da się ustalić z konfiguracji). Wypisz nadleśnictwa i daty paczek.

**0.3 Baseline dla Kieleczki.** Na obecnym kodzie (przed utworzeniem gałęzi lub na czystym `main`) uruchom pełną analizę:
- punkt startowy: Kieleczka, gm. Wielowieś — 50,527 N, 18,605 E (potwierdzić z właścicielem na starcie),
- promień: wg odpowiedzi właściciela (domyślnie 25 km),
- data: 2026-09-28,
- z paczkami BDL, jeśli obecny kod pozwala je wskazać.

Zapisz wynik jako migawkę launchera o nazwie **„Kieleczka 28.09 — baseline (stary kod)”** oraz skopiuj eksporty do `docs/porownania/baseline/`.

**0.4 Gałąź.** Utwórz `ulepszenia-faza1`.

**Akceptacja Fazy 0:** migawka baseline otwiera się w interfejsie; raport zawiera wynik testów i listę paczek.

---

## Faza 1 — noc: poprawki bez ryzyka biologicznego

Kolejność ma znaczenie: 1.1–1.2 dają narzędzia do porównań, 1.3–1.5 mają największy wpływ na ranking, 1.6–1.8 to spójność, 1.9 to przebieg końcowy.

### 1.1 Manifest uruchomienia
Każda analiza zapisuje `run_manifest_YYYY-MM-DD.json` obok pozostałych eksportów [§18.1]:
- identyfikator uruchomienia, commit, flaga „niezatwierdzone zmiany”, hash profilu,
- współrzędne, promień, data wyjazdu, data i godzina przygotowania,
- statusy źródeł: rzeczywiste ważone pokrycie radaru, czy nastąpił fallback do Open-Meteo, liczba pominiętych kafli OSM/GDOŚ, liczba sprawdzonych zakazów,
- liczniki: wydzielenia ogółem / w masce / ze składem z paczki / z WFS / z nieznanym kodem siedliska lub gatunku,
- źródło populacji (patrz 1.4) i tryb normalizacji presji (patrz 1.5).

Synchronizator frontendu kopiuje manifest razem z resztą; migawki launchera go przechowują.
**Akceptacja:** test integracyjny na cache tworzy manifest z kompletem pól; brak pola = błąd testu.

### 1.2 Eksport diagnostyczny
Nowy plik `diagnostics_YYYY-MM-DD.json` (lub parquet, jeśli rozmiar > 20 MB) z wartościami pośrednimi dla każdego wydzielenia [§13.2]: S_host, S_site, S_age, H, pct_CWB26, M, T, K_frost, G_season, F, q, F_loc, Demand, d_park, metoda odległości, P, maska strukturalna, status GDOŚ, status zakazu (z 1.6), id punktu pogody, id komórki klimatologii, źródło składu.
Frontend nie musi go czytać.
**Akceptacja:** test odtwarza R_final z diagnostyki bez żadnego wywołania sieci, tolerancja 1e-9, dla wszystkich rekordów przykładowego przebiegu.

### 1.3 Paczki BDL w głównym przepływie
Problem: eksport z 27.09 ma 100% składu z WFS mimo istnienia kodu paczek [§1, §18.1].
- Ustal przyczynę (brak ścieżki w przepływie launchera? brak dopasowań kluczy? inny katalog?) i opisz w raporcie.
- Ścieżka do katalogu paczek konfigurowalna: parametr CLI, pole w launcherze, wartość w konfiguracji lokalnej (nie w repo, jeśli zawiera ścieżki prywatne).
- Gdy ten sam adres występuje w kilku paczkach — wybór najnowszej wg daty z metadanych paczki, nie wg kolejności wczytania [§5.1].
- Kontrola sumy udziałów od dołu: suma < 0,9 → flaga `sklad_niepelny` w diagnostyce i manifeście. **Bez automatycznej renormalizacji** — tylko policz i zaraportuj, ile takich wydzieleń jest.
- Raport pokrycia: lista nadleśnictw w promieniu analizy i odsetek wydzieleń w masce ze składem z paczki; lista nadleśnictw bez paczki.
- Interfejs: ostrzeżenie w banerze, gdy > 20% wydzieleń w masce ma skład tylko z WFS.

**Akceptacja:** przebieg dla Kieleczki ma skład z paczek dla wszystkich nadleśnictw, dla których paczki istnieją (raport podaje odsetek); testy wyboru najnowszej paczki i flagi `sklad_niepelny`.

### 1.4 Populacja: siatka GUS zamiast brakującej populacji OSM
Problem: miejscowość OSM bez tagu `population` dostaje 0 i znika z presji [§5.4, §9.1].
- Loader siatki kilometrowej NSP 2021 (zasób GUS nr 24532, eksport geojson/shp/csv) z pliku wskazanego w konfiguracji. Każde oczko = punkt w centroidzie z liczbą ludności; oczka ukryte ze względu na tajemnicę statystyczną traktuj jako brak (nie zero) i zlicz w manifeście.
- Zasięg: populacja z bufora wokół koła wyszukiwania (domyślnie +30 km, parametr), żeby miasta tuż poza kaflami były uwzględnione.
- Fallback, gdy pliku GUS brak: miejscowości OSM bez populacji dostają wartość domyślną wg klasy (hamlet / village / town / city — wartości w profilu, opisane jako zgrubne), źródło zapisane w manifeście jako `osm_z_imputacja`.
- Nie zmieniaj wzoru Demand poza źródłem punktów populacji.

**Akceptacja:** testy obu ścieżek; w raporcie porównanie Demand i P dla Kieleczki: stare vs nowe źródło populacji.

### 1.5 Presja w skali bezwzględnej
Problem: `Demand_norm = Demand / max(Demand w analizie)` — najbardziej obleganie miejsce w głuszy wygląda jak las pod miastem, a wyniki z różnych wyszukiwań są nieporównywalne [§9.1].
- Nowy tryb `pressure.normalization: absolute` (domyślny po tej zmianie): `Demand_norm = Demand / (Demand + D_half)`, gdzie `D_half` jest stałą w profilu.
- Dobór `D_half` na noc: tak, by mediana P w przebiegu testowym Będziemyśl (z cache) była zbliżona do obecnej; zapisz wartość i uzasadnienie w raporcie jako **tymczasową, nieskalibrowaną**.
- Tryb `local` zachowuje stare zachowanie.

**Akceptacja:** testy obu trybów; w raporcie rozkład P (min / mediana / max) dla Kieleczki w obu trybach.

### 1.6 Stan sprawdzeń dostępności
Rozdziel „sprawdzono, brak blokady”, „nie sprawdzono” i „źródło zawiodło” [§5.5, §18.1]:
- pole `zakaz_status ∈ {brak, zakaz, nie_sprawdzono, blad}` oraz `gdos_status ∈ {brak, blokada, kafel_pominiety}` w eksporcie,
- w karcie wydzielenia/rejonu dyskretna informacja „zakazów nie sprawdzono”, gdy dotyczy,
- informacja, że zakazy są sprawdzane na dzień przygotowania, nie na dzień wyjazdu.

**Akceptacja:** testy z zastąpionym źródłem (sukces, błąd, brak sprawdzenia).

### 1.7 Etykieta pewności, która coś znaczy
Obecnie zawsze „ŚREDNIA” [§12]. Zachowaj górny limit modelu (ŚREDNIA — model nie jest skalibrowany), ale obniżaj do NISKA, gdy wystąpi którykolwiek z realnych braków:
- pusta klimatologia lub mniej niż 50% ważnych wartości w oknie,
- rzeczywiste pokrycie radaru < 0,5 przy włączonym radarze (fallback),
- pominięty kafel OSM lub GDOŚ w otoczeniu wydzielenia,
- nieznany kod siedliska lub gatunku panującego,
- `sklad_niepelny`.

Lista przyczyn trafia do eksportu i do podpowiedzi w interfejsie.
**Akceptacja:** testy każdej przyczyny; w raporcie rozkład etykiet dla Kieleczki.

### 1.8 Poprawki spójności
Każdy punkt: minimalny test reprodukcyjny, dopiero potem poprawka [§18.4].
- a) **Daty w backteście 03** (UTC a Europe/Warsaw). Sprawdź na wierszach cache. Jeśli jest przesunięcie — popraw i przelicz backtest z cache (bez API). Stare i nowe wyniki (średnia ranga, mediana, kwartyle) w raporcie. Jeśli przeliczenie wymaga API — tylko poprawka kodu, przeliczenie BLOCKED.
- b) **Doba zmiany czasu**: wspólny test dla scalenia radaru, `with_local_date` i opisu deszczu na 2026-03-29 i 2026-10-25; ujednolić obsługę.
- c) **Próg epizodu deszczu w panelu** zależny od rzeczywistego pokrycia radaru w oknie epizodu, a nie od flagi włączenia radaru.
- d) **NaN w oknie klimatologii**: jawna obsługa; percentyl liczony tylko z ważnych wartości; za mało wartości → 0,5 + przyczyna w pewności (1.7).
- e) **Klucze cache**: dodać `past_days`, zakres lat klimatologii i numer wersji formatu. Nowe klucze, stare pliki zostają.
- f) **Teksty**: pomoc `--date`, README frontendu (grupowanie, data), CLAUDE.md (dawny worktree), stały opis „rozdzielczość ok. 2 km”, uzasadnienia sugerujące „powyżej normy” tam, gdzie chodzi o porównanie z medianą obszaru.

**Akceptacja:** testy a–e; teksty zgodne z kodem.

### 1.9 Przebieg końcowy i raport porównawczy
- Pełna analiza Kieleczki na nowym kodzie z tymi samymi parametrami co 0.3. Migawka **„Kieleczka 28.09 — nowy kod”**, eksporty w `docs/porownania/nowy/`.
- Raport porównawczy w `docs/NOC_RAPORT.md`:
  - top-20 wydzieleń (≥ 0,5 ha) i rejony: przed / po,
  - korelacja Spearmana R przed/po,
  - ile wydzieleń zmieniło źródło składu, jak zmienił się rozkład H i P,
  - trzy największe awanse i spadki w rankingu z wyjaśnieniem, która składowa się zmieniła.
- Sekcja **„Na rano”**: rekomendacja, której migawki użyć, i dlaczego. Jeśli nowy kod budzi wątpliwości — rekomenduj baseline.

### 1.10 (opcjonalne, jeśli zostanie czas) Suwak α w interfejsie
Suwak 0–0,6 (domyślnie 0,3) przeliczający R po stronie przeglądarki z eksportowanych H, F_loc, P i maski. Sortowanie i rejony liczone z R z Pythona pozostają bez zmian; przy α ≠ 0,3 widoczna informacja, że rejony pochodzą z domyślnego α.
**Akceptacja:** testy modelu interfejsu; zgodność z R z eksportu przy α = 0,3.

**Definicja ukończenia nocy:** wszystkie zadania 0.x i 1.1–1.9 mają status DONE lub BLOCKED z powodem, pełne testy przechodzą, istnieją obie migawki i sekcja „Na rano”.

---

## Faza 1.5 — opad z radaru w rozdzielczości ~1 km

Cel: opad (i tylko opad) liczony osobno dla każdego wydzielenia z siatki RainGRS ~1 km, zamiast jednej średniej z bloku 5 km (przy promieniu 25 km) [§5.3, §6]. Temperatura, ET0 i klimatologia zostają na obecnych siatkach. Dane radarowe to publiczne pliki IMGW, więc zmiana nie zwiększa zużycia limitu Open-Meteo.

Wymaga ukończonych zadań 1.1 (manifest) i 1.2 (eksport diagnostyczny), żeby dało się porównać wersje. Może być realizowana autonomicznie według zasad z sekcji 0, na nowej gałęzi `ulepszenia-faza1-5` utworzonej z `ulepszenia-faza1`.

Przesłanki: porównanie ze stacjami [§14.3] było robione na pojedynczej komórce radaru, a RainGRS miał tam MAE 0,27–0,93 mm/dobę wobec 1,04–1,65 dla Open-Meteo (4 stacje, 11 dób). To wstępnie przemawia za wartością lokalną, ale próba jest mała.

**1.5.1 Próbkowanie per wydzielenie.** Dla każdego wydzielenia suma godzinowa z komórek radaru przecinających jego wielokąt (średnia ważona powierzchnią przecięcia); wydzielenia mniejsze od komórki biorą komórkę zawierającą centroid. Braki komórek raportowane jako pokrycie przestrzenne, osobno od pokrycia godzinowego. Implementacja wektorowa (np. prekomputowana macierz wag wydzielenie × komórka, rzadka), żeby czas analizy nie rósł drastycznie.

**1.5.2 Parametr wygładzania.** `radar.smoothing_km ∈ {0, 1, 2, 3}` — filtr przestrzenny pola opadu przed próbkowaniem (0 = surowe 1 km). Chroni przed artefaktami radaru (zakłócenia, cienie wiązki) i przed przesadną ostrością pojedynczej komórki burzowej. Wartość domyślna ustalana w 1.5.5.

**1.5.3 Uzupełnienie brakujących godzin i prognozy.** Godziny bez radaru oraz dni prognozowane nadal biorą opad z Open-Meteo z najbliższego punktu pogody (rozdzielczość gruba), według obecnego wzoru scalenia [§8.1]. W diagnostyce: udział „opad z radaru 1 km” w ważonej sumie P26w dla każdego wydzielenia. Przy wyjeździe za kilka dni większa część okna to prognoza — to ograniczenie, nie błąd.

**1.5.4 Spójność percentyli.** Suma z 1 km ma większą zmienność niż średnia z bloku, a klimatologia pochodzi z produktu gruboziarnistego. Porównanie wprost zawyża skrajne percentyle (jedna komórka burzowa → 99. percentyl). Rozstrzygnąć w tej kolejności:
- zmierzyć problem: rozkład pct_CWB26 dla 1 km vs dla bloku na tych samych danych,
- jeśli różnica jest istotna: percentyl nadal z CWB bloku (jak dziś), a lokalną odchyłkę 1 km od średniej bloku dodać jako osobną, ograniczoną korektę (np. ±0,1 do pct_m, parametr w profilu),
- dopiero przy dalszych problemach: mapowanie kwantylowe (Faza 4.2).

**1.5.5 Ocena i decyzja o ustawieniu domyślnym.** Porównanie na przebiegach Będziemyśl i Kieleczka oraz na jednym historycznym epizodzie burzowym z archiwum RainGRS (lato 2026):
- ile wydzieleń zmienia klasę F / F_loc, korelacja Spearmana R z wersją blokową,
- mapa różnic F (czy wzór wygląda jak pasy opadu, czy jak szum i artefakty radaru),
- powtórzenie porównania ze stacjami Weathercloud [§14.3] dla wygładzań 0/1/2/3 km — tym razem z jawną obsługą braków (brak ≠ 0 mm).

Nowy tryb staje się domyślny, jeśli wybrane wygładzenie daje MAE nie gorsze niż obecny blok, a mapa różnic nie jest zdominowana przez artefakty. W przeciwnym razie zostaje jako opcja `radar.mode: stand` obok `radar.mode: block`.

**Akceptacja:** testy próbkowania (wielokąt, małe wydzielenie, braki komórek, doba zmiany czasu), wpis w manifeście i diagnostyce, raport w `docs/RAPORT_FAZA_1_5.md` z rekomendacją.

**Oczekiwany efekt:** największy przy opadach burzowych (czerwiec–sierpień), mały przy frontalnych opadach jesiennych, które są przestrzennie gładkie. Przy obecnym nasyceniu M w mokrym okresie zmiana rankingu może być niewielka — to nie jest powód do zmiany progów.

---

## Faza 1.6 — pełniejsze wykorzystanie danych BDL

Cel: wykorzystać pola paczek BDL, które dziś trafiają tylko do kart informacyjnych albo w ogóle nie są czytane [§5.1, §7]. Dwie zmiany (1.6.2, 1.6.3) to korekty oczywistych braków i mogą zmienić H. Wszystkie pozostałe pola trafiają **wyłącznie do eksportu diagnostycznego, bez wagi w R**, do czasu oceny w Fazie 2.4 i Fazie 5.

Wymaga ukończonych zadań 1.2 (eksport diagnostyczny) i 1.3 (paczki w głównym przepływie). Może być realizowana autonomicznie według zasad z sekcji 0, na gałęzi `ulepszenia-faza1-6` utworzonej z ostatniej ukończonej gałęzi. Raport w `docs/RAPORT_FAZA_1_6.md`.

**1.6.1 Inwentaryzacja paczek.** Dla paczek z nadleśnictw, których używa właściciel:
- lista tabel i pól, typ, słownik kodów (z paczki lub `pipeline/bdl_dictionaries.py`),
- wypełnienie każdego pola w wydzieleniach D-STAN, w podziale na nadleśnictwa,
- rozkład wartości dla pól kategorycznych, zakres dla liczbowych,
- data opisu taksacyjnego (rok stanu) per wydzielenie lub per paczka.

Wynik: `docs/BDL_slownik_pol.md` z tabelą pól i ich wypełnieniem. Pola wypełnione w mniej niż 50% wydzieleń D-STAN oznaczyć jako niezdatne do cech. Jeśli któregoś pola z listy w 1.6.4 w paczkach nie ma, zapisać to wprost.

**1.6.2 Aktualizacja wieku (korekta, za flagą).** Wiek z opisu taksacyjnego nie jest dziś przeliczany na rok analizy [§7.4]. Nowy parametr `age.update_to_analysis_year: true` (domyślny po zmianie): `wiek_obecny = wiek_z_opisu + (rok_analizy − rok_stanu_opisu)`. Rok stanu brać z metadanych paczki lub pola daty opisu; gdy brak — z `a_year` warstwy WFS; gdy i tego brak — bez korekty i flaga w diagnostyce. Stare zachowanie przez `false`. Korekta dotyczy S_age i maski wieku (< 12 lat).

**1.6.3 Skład z niższych pięter (korekta, za flagą).** Dziś do S_host wchodzi tylko piętro `DRZEW` [§5.1]. Nowy parametr `host.lower_storeys_weight` (domyślnie 0 = stare zachowanie; w raporcie wyniki dla 0, 0,25 i 0,5). Wariant liczony: `S_host = (1 − w) × S_host_drzew + w × S_host_niższe`, gdzie `S_host_niższe` liczone tym samym wzorem z udziałów gatunków w piętrach niższych (II piętro, podrost, przestoje — zgodnie ze słownikiem z 1.6.1); gdy brak niższych pięter — `S_host_niższe = S_host_drzew`. **Wartość domyślna pozostaje 0** do oceny w Fazie 2.4 i 5 — to jest hipoteza, nie korekta błędu.

**1.6.4 Cechy do diagnostyki (bez wagi w R).** O ile istnieją w paczkach i przechodzą próg wypełnienia z 1.6.1, dodać do eksportu diagnostycznego:
- typ pokrywy gleby / runa i zbiorowisko roślinne (także z warstwy mapy fitosocjologicznej BDL, jeśli dostępna lokalnie lub przez WFS),
- bonitacja gatunku panującego,
- zwarcie koron i zadrzewienie,
- typ i podtyp gleby,
- stan / wariant siedliska (naturalne, zniekształcone, przekształcone),
- budowa pionowa drzewostanu,
- podszyt i podrost: gatunki i zagęszczenie,
- zabiegi gospodarcze z datami, **z rozróżnieniem wykonane / planowane** (jeśli paczka ma tylko planowane — zapisać, bez wnioskowania, że zostały wykonane),
- dla każdego wydzielenia: długość granicy z **granicą oddziału** (linie oddziałowe w terenie to zwykle przecinki i dukty) oraz odległość centroidu od najbliższej linii oddziałowej.

Każda cecha ma w słowniku z 1.6.1 krótki opis i hipotezę, dlaczego mogłaby mieć znaczenie (np. „bór z borówką vs z trawą”, „słabsza bonitacja — możliwe silniejsze owocnikowanie grzybów mikoryzowych”), jawnie oznaczoną jako hipoteza.

**1.6.5 Łatwość szukania w karcie (prezentacja, nie ranking).** W karcie wydzielenia i rejonu krótka informacja praktyczna na podstawie podszytu, podrostu i zwarcia, np. „gęsty podszyt — trudne szukanie”. Nie wpływa na R ani sortowanie.

**1.6.6 Przebieg i raport.** Przebieg Kieleczki z ustawieniami domyślnymi po 1.6.2 (i `lower_storeys_weight = 0`), migawka **„Kieleczka — faza 1.6”**. W raporcie:
- ile wydzieleń zmieniło przedział wieku lub przeszło przez próg maski dzięki 1.6.2, zmiana rozkładu H,
- porównanie rankingu dla `lower_storeys_weight` 0 / 0,25 / 0,5 (Spearman, zmiany w top-20),
- rozkład nowych cech w top-5% R vs w całej masce — **tylko opisowo**, bez wniosków o skuteczności.

**Akceptacja:** słownik pól z wypełnieniem; testy korekty wieku (brak roku stanu, wiek przekraczający próg), testy wariantu pięter (brak niższych pięter, suma udziałów); cechy z 1.6.4 obecne w diagnostyce; R niezmienione przez 1.6.4 i 1.6.5 (test porównujący R przed/po przy wyłączonych 1.6.2 i 1.6.3).

---

## Faza 2 — kontrole wiarygodności i przygotowanie walidacji

**Czego ta faza nie da.** Dane GBIF zawierają tylko znaleziska: nie wiadomo, gdzie i kiedy szukano bez skutku, ani ile czasu na to poświęcono. Na takich danych **nie da się rzetelnie zmierzyć, czy aplikacja wskazuje miejsca z większą liczbą borowików.** Faza 2 ma trzy skromniejsze cele:
1. wykryć rażące błędy modelu (np. H odwrotnie związane ze znaleziskami),
2. zacząć zbierać dane, które pozwolą na prawdziwą walidację (własne wyjścia, archiwum prognoz),
3. przygotować infrastrukturę pogodową bez limitów API.

Wynik żadnego testu z tej fazy nie jest podstawą do zmiany wag H, progów F ani α, poza regułami zapisanymi z góry w 2.0. Raport w `docs/RAPORT_FAZA_2.md` zawiera obowiązkową sekcję „Czego te testy nie pokazują”.

**Kolejność i tryb pracy:**

| Zadanie | Kiedy | Tryb |
|---|---|---|
| 2.0 Reguły decyzyjne | przed 2.3 i 2.4 | agent pisze projekt, **właściciel zatwierdza** |
| 2.1 Format zapisu własnych wyjść | od razu (sezon trwa) | autonomicznie |
| 2.2 Archiwum prognoz | od razu (każdy dzień zwłoki to utracone dane) | autonomicznie |
| 2.3 Inwentaryzacja rekordów GBIF | od razu, tanio | autonomicznie |
| 2.4 Kontrola przestrzenna H | tylko jeśli 2.3 spełni próg z 2.0 | autonomicznie po zatwierdzeniu 2.0 |
| 2.5 Kontrola czasowa F | tylko jeśli 2.3 spełni próg z 2.0 | autonomicznie po zatwierdzeniu 2.0 |
| 2.6 E-OBS lokalnie | gdy będzie czas | autonomicznie |
| 2.7 Weryfikacja prognoz | po zebraniu ≥ 30 dni archiwum z 2.2 | autonomicznie |
| 2.8 Bielefeld | opcjonalnie, najniższy priorytet | autonomicznie |

### 2.0 Reguły decyzyjne zapisane z góry

Przed uruchomieniem 2.4 i 2.5 agent przygotowuje `docs/WALIDACJA_REGULY.md`, a właściciel go zatwierdza. Plik jest commitowany **przed** analizą (znacznik czasu w git jest dowodem, że reguł nie dopasowano do wyników). Dla każdego testu:
- pytanie i hipoteza,
- dane i filtry (dokładnie jakie),
- metryka i sposób liczenia przedziału ufności,
- minimalna liczebność próby — poniżej niej wynik to „brak wniosku”, bez względu na liczby,
- reguła decyzji: jaki wynik prowadzi do jakiego działania. Domyślnie jedyne działanie to „przegląd składowej w osobnej sesji z właścicielem”; żaden wynik nie zmienia modelu automatycznie.

Zmiana reguł po zobaczeniu wyników jest niedozwolona. Jeśli reguła okazała się źle sformułowana, zapisuje się to w raporcie, a poprawiona reguła dotyczy dopiero następnej, nowej próby danych.

Proponowane progi startowe (do zatwierdzenia):
- 2.4: co najmniej 100 rekordów B. edulis z niepewnością ≤ 100 m w lasach z danymi BDL, od co najmniej 30 różnych obserwatorów.
- 2.5: co najmniej 150 rekordów z pełną datą, z co najmniej 5 różnych lat.
- Czerwona flaga (przegląd składowej): cały 95% przedział ufności AUC lub rangi poniżej 0,5.

### 2.1 Format zapisu własnych wyjść

Właściciel już zapisuje wyniki wyjść. Cel: ujednolicić zapis tak, żeby po sezonie lub dwóch dało się go zaimportować (Faza 5) bez ręcznej rekonstrukcji.

- Katalog `dane_terenowe/` **poza repozytorium** lub w `.gitignore` (dokładne lokalizacje są prywatne).
- Jedno wyjście = jeden wpis w `dane_terenowe/wyjscia.csv` + opcjonalny ślad GPX:
  - `id_wyjscia`, `data`, `start`, `koniec` (godziny),
  - `plik_gpx` (ślad z telefonu, np. Locus, Strava, oś czasu Google) — **najważniejsze pole**: pozwala policzyć czas w każdym wydzieleniu, także tam, gdzie nic nie znaleziono,
  - `powod_wyboru` ∈ {`aplikacja`, `znane_miejsce`, `przypadkowo`, `mieszane`},
  - `id_migawki` — identyfikator migawki analizy z dnia wyjazdu (walidowany jest ranking widziany tamtego dnia, nie późniejszy),
  - `uwagi` (np. ślady innych grzybiarzy, rowery, wycinka).
- Znaleziska w `dane_terenowe/znaleziska.csv`: `id_wyjscia`, `lat`, `lon` (może być przybliżone), `gatunek`, `liczba`, `klasa_wieku` ∈ {`mlode`, `dojrzale`, `stare`, `mieszane`}.
- Skrypt `scripts/sprawdz_dane_terenowe.py`: walidacja plików (brakujące pola, GPX bez pokrycia czasowego, znaleziska poza śladem, nieistniejąca migawka) i krótkie podsumowanie (liczba wyjść, godzin, borowików). Bez żadnej analizy skuteczności — to Faza 5.
- W launcherze przypomnienie przy przygotowaniu analizy: „zapisz migawkę, jeśli jedziesz dziś do lasu”.
- Instrukcja dla właściciela w `docs/ZAPIS_WYJSC.md`: jak nagrać ślad, co zapisać po powrocie (≤ 2 minuty).

**Akceptacja:** szablony plików, skrypt z testami na przykładowych danych, instrukcja.

### 2.2 Archiwum prognoz

Przy każdej analizie aplikacja pobiera prognozę, ale jej nie przechowuje z datą wydania. Bez tego weryfikacja prognoz (2.7) jest niemożliwa, a darmowego archiwum prognoz z odpowiednią rozdzielczością może nie być.

- Każdy przebieg zapisuje surowe prognozy dobowe (opad, temperatury, ET0) z datą i godziną pobrania do `cache/archiwum_prognoz/` (format kolumnowy, np. parquet, jeden plik na dzień pobrania).
- Opcjonalnie: lekki skrypt `scripts/zapisz_prognoze.py` uruchamiany ręcznie lub z harmonogramu Windows raz dziennie dla kilku stałych punktów w ulubionych rejonach (≤ 10 punktów, zużycie API pomijalne).
- Nie usuwać archiwum przy czyszczeniu cache.

**Akceptacja:** test, że przebieg zapisuje prognozę z datą wydania; drugi przebieg tego samego dnia nie nadpisuje pierwszego.

### 2.3 Inwentaryzacja rekordów GBIF

Tanie zadanie rozstrzygające, czy 2.4 i 2.5 w ogóle mają sens. Bez żadnych testów skuteczności.

Dla B. edulis w Polsce i osobno w regionie właściciela (RDLP Katowice + bufor):
- liczba rekordów wg niepewności współrzędnych (≤ 25 m, ≤ 100 m, ≤ 1000 m, brak),
- wg źródła (iNaturalist, inne), roku, miesiąca,
- liczba różnych obserwatorów i udział rekordów od 5 najaktywniejszych,
- udział rekordów w lasach z danymi BDL (paczki / tylko WFS / poza lasem),
- to samo dla tła „inne grzyby w lesie” (potrzebne w 2.4 i 2.5).

Wynik: tabela w raporcie + werdykt wobec progów z 2.0 („2.4: uruchamiać / nie uruchamiać”).

### 2.4 Kontrola przestrzenna H (warunkowa)

Uruchamiana tylko po zatwierdzeniu 2.0 i spełnieniu progu z 2.3.

- Rekord B. edulis przypisany do wydzieleń w buforze równym niepewności współrzędnych (wartość H ważona powierzchnią w buforze, nie tylko wydzielenie z punktem).
- **Dwa tła, raportowane zawsze razem**, bo skrzywiają wynik w przeciwnych kierunkach:
  - inne grzyby w lesie (te same osoby, ten sam typ wyjścia — test „czym miejsca borowika różnią się od miejsc innych grzybów”),
  - obserwacje niegrzybowe w lesie (rośliny, owady, ptaki — test „czym miejsca borowika różnią się od miejsc, gdzie ludzie w ogóle bywają”).
- Metryka: AUC dla H; 95% przedział ufności bootstrap **po obserwatorach** (rekordy jednej osoby nie są niezależne).
- Tą samą metodą, opisowo: bonitacja, stan siedliska, pokrywa gleby, granica oddziału (Faza 1.6.4) oraz wariant `lower_storeys_weight` (1.6.3). Przy wielu cechach — wyraźna uwaga o wielokrotnym testowaniu; wyniki to ranking cech wartych sprawdzenia w Fazie 5, nie wagi.

### 2.5 Kontrola czasowa F (warunkowa)

Następca dawnego backtestu 03 [§14.2], uruchamiany tylko po zatwierdzeniu 2.0 i spełnieniu progu z 2.3.

- Poprawiona obsługa dat (1.8a), cechy pogodowe z E-OBS lub archiwum Open-Meteo (to samo źródło dla wszystkich wariantów).
- Dzień znaleziska porównywany z dniami kontrolnymi ±15 dni (usuwa większość efektu sezonu).
- **Dwa tła jako granice wyniku:**
  - wszystkie dni w oknie — wynik **zawyżony**, bo grzybiarze chodzą do lasu wtedy, gdy spodziewają się grzybów,
  - dni, w których w promieniu 20 km zgłoszono inne grzyby — wynik **zaniżony**, bo usuwa też ogólną reakcję grzybów na pogodę.
  Prawdziwa wartość leży gdzieś pomiędzy; raport podaje obie.
- Warianty porównywane: F bez G_season, sam kalendarz, samo M, sama T, model stały.
- Przedziały ufności bootstrap po latach i lokalizacjach.
- **Bez dostrajania parametrów F na tych danych.**

### 2.6 E-OBS lokalnie (infrastruktura)

Pobrać 0,1° TG/TN/TX/RR dla Polski (licencja: niekomercyjne badania i edukacja). Klimatologia i backtesty bez API. ET0 liczone jedną metodą (np. Hargreaves z TN/TX) w klimatologii i dla bieżących dni, żeby percentyle porównywały to samo. Przejście produkcji na E-OBS jako źródło klimatologii — dopiero po porównaniu rozkładów percentyli ze stanem obecnym.

### 2.7 Weryfikacja prognoz (po zebraniu archiwum)

Na archiwum z 2.2 (≥ 30 dni): błąd prognozy opadu, temperatur i końcowego F dla horyzontów 0/1/3/6/15 dni względem wartości obserwowanych (radar, E-OBS). Wynik praktyczny: od jakiego horyzontu interfejs powinien wyraźnie oznaczać F jako niepewne (np. wyszarzone kafelki). To jedyny test w tej fazie, który jest w pełni rzetelny — ale dotyczy pogody, nie grzybów.

### 2.8 Dane z Bielefeld (opcjonalne)

Zenodo, DOI 10.5281/zenodo.20591123 (V1.2, 08.06.2026; wersja pierwsza 10.5281/zenodo.17881359 — te same liczby owocników, inna pogoda), CC BY 4.0. **Status: zrealizowane 30.09.2026** — reguły `docs/WALIDACJA_BIELEFELD.md`, raport `docs/RAPORT_BIELEFELD.md` (wagi opadu: „nierozstrzygnięte”, bez zmiany F), dane trwałe `dane_walidacyjne/bielefeld/`. Aktualne F jest najpewniej zbudowane na wynikach tej pracy, więc to **wyłącznie kalibracja kształtu funkcji** (liniowy opad vs sigmoida percentyla, okna), nie walidacja. Jeden las bukowy w Niemczech. Każda zmiana F wynikająca z tej analizy musi dodatkowo nie pogorszyć wyniku 2.5 w żadnym z dwóch teł.

---

## Faza 3 — presja grzybiarzy v2: punkty dostępu

**Idea.** Presja trafia do wydzielenia wyłącznie przez **punkty dostępu**: parkingi, wjazdy do lasu, osiedla przy lesie i utwardzone drogi leśne. Ludność nie działa już na las bezpośrednio (jak dziś w modelu grawitacyjnym od centroidu wydzielenia [§9.1]), tylko **wzmacnia punkty dostępu** leżące blisko skupisk ludzi. Uzasadnienie: w lesie obowiązuje zakaz wjazdu poza wyznaczonymi drogami, więc auta stają na parkingach, przy wjazdach i szlabanach, a presja rozchodzi się od tych miejsc.

Obecny model zostaje dostępny przez `pressure.model: gravity`; nowy to `pressure.model: access_points`. Wzór R_final bez zmian. Wszystkie parametry poniżej są **nieskalibrowane** i trafiają do profilu.

Wymaga ukończonych Faz 1 (manifest, diagnostyka, siatka GUS, normalizacja bezwzględna) i 1.6. Raport w `docs/RAPORT_FAZA_3.md`.

### 3.1 Dane punktów dostępu

- **Parkingi:** warstwa turystyczna BDL (parkingi leśne, miejsca postoju pojazdów) + OSM `amenity=parking` w odległości ≤ 200 m od lasu. Deduplikacja w promieniu 100 m (pierwszeństwo BDL).
- **Wjazdy do lasu:** przecięcia dróg publicznych z granicą lasu (już liczone dla wejść [§9.2]), zachowane tylko tam, gdzie wewnątrz lasu jest kontynuacja drogi (dukt, track, droga leśna). Dodatkowo OSM `barrier=gate` / `lift_gate` na drodze leśnej w odległości ≤ 300 m od drogi publicznej — szlaban to miejsce, gdzie auto faktycznie staje. Deduplikacja w promieniu 150 m.
- **Fallback bez wjazdów:** jeśli w danym kaflu nie da się wyznaczyć wjazdów (brak danych o duktach), źródłem jest cała droga asfaltowa w pobliżu lasu. Kafle z fallbackiem liczone w manifeście.
- **Osiedla przy lesie:** oczka siatki GUS z ludnością (lub zabudowa BDOT10k) w odległości ≤ 200 m od lasu. Ludzie wchodzą tu pieszo, bez auta. **Ten typ jest celowy:** część presji przy miastach jest prawdziwa i nie powinna zniknąć, tylko nie rozlewać się na kilometry.
- **Sieć dróg leśnych — baza: dojazdy pożarowe BDL.** Oficjalna warstwa BDL o jednolitym pokryciu całego lasu państwowego (w Lasach Lublinieckich regularna siatka co ok. 1–1,5 km). Stanowi szkielet sieci, niezależny od tego, jak dokładnie dany rejon jest zmapowany w OSM.
- **Nawierzchnia dróg leśnych:** BDOT10k `OT_SKDR_L` z `materialNawierzchni` ∈ {masa bitumiczna, beton, płyty betonowe, kostka, bruk, tłuczeń, żwir} (pobierane per powiat, bezpłatne); uzupełnienie OSM `surface`, `tracktype=grade1/grade2`, relacje `route=bicycle`. Nawierzchnia jest **atrybutem** odcinka sieci, a nie warunkiem jego istnienia: odcinek dojazdu pożarowego bez opisu nawierzchni ma klasę „nieznana”, nie „brak drogi”.
- **Droga publiczna czy zamknięta droga leśna.** Asfalt w lesie nie zawsze oznacza dojazd autem: wiele asfaltowych dróg leśnych jest zamkniętych szlabanem i służy głównie rowerzystom. Rozróżnienie: kategoria zarządzania z BDOT10k (publiczna vs wewnętrzna), tagi OSM `access`, `motor_vehicle`, `highway` (track vs unclassified/tertiary i wyższe), szlaban na wjeździe. Droga publiczna → źródło punktów dostępu dla aut; zamknięta droga leśna → korytarz rowerowy (3.3).
- **Nawierzchnia dróg publicznych** (do rozróżnienia asfaltu) z BDOT10k, uzupełniana tagami OSM.
- **Korekty właściciela (najwyższy priorytet).** Plik `dane_terenowe/korekty_dostepu.geojson` (poza repozytorium): drogi potwierdzone w terenie z nawierzchnią, parkingi nieoficjalne, szlabany, drogi nieprzejezdne. Korekta nadpisuje dane z BDL, BDOT10k i OSM w swoim miejscu. Właściciel ma już w innym narzędziu warstwę „potwierdzona w terenie” — przewidzieć import z GeoJSON.

**Akceptacja:** liczniki każdego typu i źródła w manifeście; testy deduplikacji, filtra wjazdów (z duktem / bez duktu), szlabanów, fallbacku, rozróżnienia droga publiczna / zamknięta droga leśna i nadpisywania przez korekty właściciela.

**Kontrola pokrycia OSM.** Kompletność tagów nawierzchni w OSM jest bardzo nierówna (część rejonów opisana gęsto, sąsiednie wcale). Jeśli model karze za „utwardzoną drogę” tylko tam, gdzie ktoś ją opisał w OSM, lasy gorzej zmapowane wyjdą sztucznie spokojne. W raporcie: mapa i tabela udziału odcinków sieci BDL ze znaną nawierzchnią w podziale na oddziały lub kafle 2 × 2 km; analiza wrażliwości: P przy nawierzchni „nieznana” traktowanej jak utwardzona vs nieutwardzona.

### 3.2 Atrakcyjność punktu (wzmocnienie ludnością)

Każdy punkt dostępu k dostaje atrakcyjność zależną od ludności w zasięgu dojazdu:

`A_k = Σ_j Pop_j × g(d_jk)`,  `A_norm_k = A_k / (A_k + A_half)`

- Pop_j z siatki GUS (Faza 1.4), d_jk na start w linii prostej (później opcjonalnie po sieci drogowej).
- Zasięg funkcji g zależny od typu: parking i wjazd ~20 km (dojazd autem), utwardzona droga leśna ~8 km (rower), osiedle przy lesie — tylko ludność samego osiedla i oczek w promieniu ~1,5 km (pieszo).
- `A_half` stała w profilu, normalizacja bezwzględna (nie względem maksimum analizy).
- **Droga leśna jako korytarz rowerowy** dziedziczy atrakcyjność od punktów, z których się na nią wjeżdża, **po sieci dróg, nie w linii prostej**: `A_odcinek = max_k (A_norm_k × h(d_sieć_k))`, gdzie `d_sieć_k` to odległość wzdłuż sieci od punktu dostępu k, a `h` spada o połowę co ok. 3 km (parametr). Mnożnik nawierzchni: twarda 1,0, kruszywo/ubita 0,8, nieznana 0,5, gruntowa 0,3 (parametry). Przy gęstej siatce dróg to właśnie odległość od wjazdu po sieci, a nie sama bliskość jakiejkolwiek drogi, odróżnia miejsca obleganie od spokojnych.
- Opcjonalnie (3.2b, po pierwszym raporcie): podział ludności między konkurujące punkty dostępu (model Huffa) — mieszkańcy miasta rozkładają się na wiele parkingów.

### 3.3 Zasięg oddziaływania

Parametry startowe (propozycja właściciela):

| Typ punktu | Waga typu w_t | Zasięg R_t |
|---|---|---|
| Parking | 1,0 | 3,0 km |
| Wjazd do lasu / szlaban | 0,6 | 2,5 km |
| Droga asfaltowa (fallback bez wjazdów) | 0,4 | 1,5 km |
| Osiedle przy lesie | 0,6 | 1,5 km |
| Droga leśna (korytarz rowerowy) | 0,4 | 0,3 km od drogi (poprzecznie) |

- **Bez twardej granicy:** wpływ spada łagodnie do zera na granicy zasięgu, np. `k(d) = max(0, 1 − (d/R_t)²)²`. Wydzielenie w 2,99 km i w 3,01 km od parkingu ma niemal taką samą presję.
- Odległość: na start od centroidu wydzielenia w linii prostej; wariant po sieci duktów (routing już istnieje [§9.2]) jako opcja do porównania w raporcie.
- **Zasięg poprzeczny dróg leśnych zmniejszony z 1,0 do 0,3 km.** Przy siatce dróg co ok. 1–1,5 km zasięg 1 km obejmowałby praktycznie cały las i presja przestałaby cokolwiek rozróżniać. Rowerzysta zsiada i szuka zwykle w pasie kilkuset metrów od drogi. W raporcie porównać 0,3 / 0,5 / 1,0 km, z odsetkiem powierzchni lasu, na którą dociera wpływ dróg.

### 3.4 Łączenie w P

`Presja_surowa = Σ_k w_t(k) × A_norm_k × k(d_k)`,  `P = 1 − exp(−Presja_surowa / S)`

- Suma, nie maksimum: wydzielenie przy trzech parkingach jest bardziej obciążone niż przy jednym; nasycenie przez `S` zapobiega wartościom bez ograniczeń.
- `S` dobrane tak, żeby mediana P w przebiegu Kieleczki była zbliżona do obecnej (tymczasowo, jak w 1.5).
- W diagnostyce: wkład każdego typu punktu oraz identyfikator punktu o największym wkładzie.

### 3.5 Mapa i karta wydzielenia

- Eksport: `access_points_YYYY-MM-DD.geojson` (punkty: typ, źródło, atrakcyjność) i `forest_roads_YYYY-MM-DD.geojson` (linie: nawierzchnia, źródło, publiczna/zamknięta, atrakcyjność, numer dojazdu pożarowego BDL). Uproszczenie geometrii i limit rozmiaru; synchronizator i migawki je obejmują.
- Warstwy mapy włączane w legendzie:
  - parkingi — ikona „P”, inny odcień dla BDL i OSM,
  - wjazdy do lasu — mały znacznik; szlaban osobnym symbolem,
  - drogi leśne — linia, kolor wg nawierzchni (twarda / kruszywo / ubita / nieznana), grubość wg atrakcyjności; zamknięte drogi leśne odróżnione od publicznych,
  - dojazdy pożarowe BDL — osobna warstwa, domyślnie wyłączona (jest gęsta),
  - korekty właściciela — osobny symbol „potwierdzone w terenie”,
  - osiedla przy lesie — opcjonalnie, domyślnie wyłączone,
  - opcjonalnie półprzezroczysta warstwa P.
- Kliknięcie w punkt lub drogę: typ, źródło, atrakcyjność (niska / średnia / wysoka).
- Karta wydzielenia: „najbliższy parking X m, wjazd Y m, utwardzony dukt Z m” oraz który punkt najbardziej odpowiada za presję.

### 3.6 Kontrola i raport

- Mapa różnic P: `gravity` vs `access_points` dla Kieleczki i okolic Lublińca.
- 10 wydzieleń z największą zmianą P w każdą stronę, z wyjaśnieniem (który punkt dostępu).
- Kontrole sensowności: wydzielenia dalej niż 3 km od każdego punktu dostępu i dalej niż zasięg poprzeczny od każdej drogi leśnej mają P równe 0; **odsetek powierzchni lasu z P > 0,5 podany w raporcie** — jeśli przekracza ok. 70%, parametry są za szerokie i presja niczego nie rozróżnia (zgłosić, nie stroić automatycznie); pas lasu przy Lublińcu zachowuje presję przez osiedla przy lesie, ale nie na kilometry w głąb; brak skoków P na granicach zasięgów.
- Ręczna kontrola 10 losowych wjazdów i 10 parkingów z ortofotomapą (Geoportal) — lista w raporcie do przejrzenia przez właściciela.
- Porównanie rankingu top-20 i rejonów przed/po.

**Kalibracja:** brak. Parametry to hipoteza. Materiał do przyszłej kalibracji: pole `uwagi` w zapisie wyjść (Faza 2.1) — ślady innych grzybiarzy, rowery — oraz dane z aplikacji kolegi (Faza 5).

**Strava:** heatmapa wyłącznie do ręcznego oglądania; automatyczne użycie niedozwolone.

---

## Faza 4 — pogoda: przejrzystość, spójność i oszczędność API

**Kontekst po Fazach 1.5 i 2.** Opad z radaru per wydzielenie jest już zrobiony (1.5). Test 2.5 nie potwierdził ani nie obalił F: sam kalendarz i sama temperatura wypadły nie gorzej niż pełny F, a test miał małą moc dla wilgotności (M). Dlatego Faza 4 **nie stroi F pod lepsze wyniki** — nie ma na czym. Jej cele to:
1. przejrzystość: użytkownik widzi składniki pogody zamiast jednej nieprzejrzystej liczby,
2. spójność porównań (percentyle bieżące vs klimatologia z tego samego źródła),
3. mniejsze zużycie API,
4. uczciwe oznaczanie niepewności prognozy.

Progi klas F, krzywa sezonowości, α i wagi H pozostają bez zmian. Każda zmiana zmieniająca wartość F idzie za flagą, z raportem przed/po. Raport w `docs/RAPORT_FAZA_4.md`. Gałąź `ulepszenia-faza4` z `master`.

### 4.1 Rzadsza siatka temperatury i ET0

Opad pochodzi z radaru per wydzielenie, a temperatura i ET0 zmieniają się w przestrzeni łagodnie. Parametr `weather.temp_grid_km` (obecna wartość = dzisiejsze zachowanie; warianty 10 i 15 km), opad z Open-Meteo nadal używany do uzupełnień i prognozy według obecnego scalenia.

W raporcie dla Kieleczki: liczba wywołań Open-Meteo (koszt wg reguł Open-Meteo) przed/po, Spearman F i R, maksymalna i 95. percentyl |ΔF|, liczba wydzieleń zmieniających klasę F, osobno dni z przymrozkiem (czy rzadsza siatka nie gubi lokalnych przymrozków). **Reguła przyjęta z góry:** wariant staje się domyślny, jeśli 95. percentyl |ΔF| ≤ 0,02 i żadne wydzielenie nie traci ani nie zyskuje przymrozku w horyzoncie wyjazdu; inaczej zostaje jako opcja.

### 4.2 Spójność percentyli (bieżące vs klimatologia)

Bieżący CWB26 pochodzi z radaru (+ Open-Meteo), a klimatologia z ERA5 przez Open-Meteo. Wcześniej ta sama rozbieżność wymusiła wyłączenie wilgotności gleby.

- **Najpierw zmierzyć.** Na okresie, dla którego jest archiwum RainGRS w cache (co najmniej kilka tygodni, najlepiej lato–jesień 2026), dla ~50 punktów w obszarze Kieleczki porównać 26-dniowe sumy opadu: radar vs ERA5 vs E-OBS (lokalnie z 2.6). Raport: obciążenie (mediana różnicy), rozrzut, różnica percentyla CWB26 wyliczonego z radaru i z ERA5 dla tych samych dni.
- **Reguła przyjęta z góry:** mapowanie kwantylowe radar → ERA5 wdrażane (za flagą `weather.percentile_mapping: quantile`) tylko jeśli mediana |Δ pct_CWB26| > 0,10. W przeciwnym razie — raport i bez zmian.
- Bez mechanicznego mnożenia przez stały współczynnik.
- Przy okazji dokończyć 2.6: porównanie rozkładów percentyli E-OBS i ERA5 — opisowo, bez przełączania produkcji.

### 4.3 Nasycenie F — diagnoza i przejrzysta prezentacja

Problem: w eksporcie z 27.09 prawie wszystkie wydzielenia miały klasę „Bardzo dobre”, więc klasa nie niesie informacji.

- **Diagnoza** (bez zmian w modelu): rozkład F, M, T i K_frost na przebiegach w cache; który składnik powoduje nasycenie (M przy sigmoidzie percentyla, T, oba); analiza czułości — ile wydzieleń zmienia klasę przy ±10% każdego parametru F.
- **Progów klas nie zmieniamy** — test 2.5 nie daje do tego podstaw.
- **Prezentacja** w panelu pogody i karcie wydzielenia (bez wpływu na R):
  - składniki wprost, zrozumiale: „opad z ostatnich 26 dni: X mm, typowo o tej porze Y mm (percentyl Z)”, „średnia temperatura 20 dni: X °C (optimum ok. 13 °C)”, „przymrozek: tak/nie, kiedy”,
  - F jako liczba obok klasy,
  - krótka stała notka: „Ocena pogody nie została potwierdzona na danych o znaleziskach; traktuj ją jako orientację, nie prognozę wysypu.”

### 4.4 Panel 7 dni — agregacja

Porównać wartość panelu liczoną jako: F z median cech (obecnie), mediana F po punktach, mediana F po wydzieleniach, średnia F ważona powierzchnią lasu. Sprawdzić, czy agregacja nie ukrywa lokalnego przymrozku lub lokalnej burzy (odsetek powierzchni z przymrozkiem / z silnym opadem jako osobna informacja w panelu). Zmiana metody agregacji tylko jeśli różnice między metodami przekraczają 0,05 w którymkolwiek dniu przykładowych przebiegów; wybór uzasadniony w raporcie.

### 4.5 Niepewność prognozy w interfejsie

Do czasu weryfikacji prognoz (2.7, po ≥ 30 dniach archiwum): dni prognozy od 4. dnia wzwyż oznaczane w panelu jako „prognoza niepewna” (wyszarzone, z krótką notką), a dni ≥ 8 jako „orientacyjnie”. Progi horyzontu w profilu (`ui.forecast_uncertain_from_day`, `ui.forecast_indicative_from_day`), do aktualizacji po 2.7. Karta wydzielenia przy wyjeździe za ≥ 4 dni pokazuje udział prognozy w oknie 26 dni (z diagnostyki 1.5.3).

### 4.6 Przebieg i raport

Przebieg Kieleczki na nowym kodzie, migawka **„Kieleczka — faza 4”**. Raport: wyniki 4.1–4.4 z decyzjami wg reguł, zrzuty lub opis panelu i karty, liczba wywołań API przed/po.

**Akceptacja:** testy dla nowej siatki temperatury, mapowania (jeśli wdrożone), agregacji panelu, oznaczeń horyzontu i nowych pól karty; R niezmienione przez 4.3 i 4.5 (test); pełne testy backendu i frontendu.

---

## Faza UI — czytelny interfejs i przełącznik presji

Po Fazie 4 (panel pogody z 4.3/4.5 jest bazą). Cel: aplikacja pokazuje **wizualnie**, co wpływa na wynik, a tekst schodzi na drugi plan. Zasada: **nic nie jest usuwane, tylko chowane** — każda dzisiejsza informacja zostaje dostępna w rozwijanych „Szczegółach”. Gałąź `ulepszenia-ui` z `master`. Raport w `docs/RAPORT_UI.md` ze zrzutami ekranu (szerokość komputera i telefonu, przed/po).

Zastępuje opcjonalne zadanie 1.10 (suwak α).

### UI.1 Przełącznik presji grzybiarzy (backend + frontend)

- Eksport wydzieleń zawiera H, F_loc, P, maskę, R oraz `R_bez_presji = 100 · H · F_loc` (sprawdzić, dodać brakujące pola).
- Backend liczy rejony **dwa razy** tą samą procedurą: z presją (obecne) i bez presji (α = 0). Eksport obu zestawów (np. `regions` i `regions_bez_presji` albo osobny plik); synchronizator i migawki przenoszą oba. Stare migawki bez drugiego zestawu: przełącznik nieaktywny z krótką informacją.
- Frontend: przełącznik „Uwzględniaj presję grzybiarzy” (domyślnie włączony). Przełącza sortowanie wydzieleń, listę rejonów, kolory mapy i wynik w karcie. Wybór zapamiętany lokalnie (odczyt/zapis w try/catch).
- Maska prawna i strukturalna bez zmian w obu trybach.
- Testy: `R_bez_presji` = 100·H·F_loc; przy włączonym przełączniku ranking i rejony identyczne jak przed zmianą; poprawne przełączanie zestawów rejonów; stare migawki.

### UI.2 Rozbicie wyniku na paski

- Trzy główne paski, wszystkie w konwencji **„więcej = lepiej”**:
  - **Siedlisko** (H),
  - **Pogoda** (F_loc),
  - **Spokój** (1 − P) — zamiast mylącego „Dostępność dla innych odwiedzających (P)”.
- Nad paskami wynik końcowy i jedna linijka: „Wynik = siedlisko × pogoda × spokój”.
- Każdy pasek rozwijany do składowych:
  - Siedlisko → skład drzewostanu (S_host), typ siedliska (S_site), wiek (S_age; w trybie `neutral` opis „nie wpływa na wynik”),
  - Pogoda → wilgotność (M), temperatura (T), przymrozek (K_frost) — spójnie z opisem składników z 4.3,
  - Spokój → 2–3 punkty o największym wkładzie w presję, np. „parking Łaziska 192n · 2,4 km”, „wjazd · 2,1 km”, „osiedle · 0,8 km”.
- Przy paskach słowna ocena (np. niski / średni / wysoki); dokładna liczba po najechaniu lub dotknięciu.
- Przy wyłączonej presji pasek Spokój jest wyszarzony z opisem „nie uwzględniony”.
- Te same paski w karcie rejonu, liczone tą samą metodą co ranking rejonu (opisać w Szczegółach, np. „wartości najlepszego wydzielenia”).
- Paski wyłącznie z wartości modelu z eksportu, bez przeliczeń innymi wzorami.

### UI.3 Porządek w treści

- **Czytelne nazwy:** wydzielenie jako „Oddz. 96a · Nadl. Koszęcin” (z adresu leśnego; leśnictwo, jeśli dostępne), pełny identyfikator w Szczegółach. Rejon jako „Rejon 1 · koło Łazisk” (najbliższa miejscowość z OSM) zamiast `region_4`.
- **Lista po lewej:** jeden wiersz na pozycję: miejsce w rankingu, nazwa, wynik, trzy mini-paski, powierzchnia, odległość od punktu startu. Maksymalnie 2 linijki tekstu.
- **Karta:** nagłówek → paski → 2–4 kluczowe fakty jako krótkie etykiety (najbliższy parking, utwardzony dukt, powierzchnia, dojazd) → przyciski (Zapisz, Nawiguj). Wszystko inne („Dlaczego tutaj”, zakresy odległości, przyczyny etykiety pewności, uwagi metodyczne, ranking i dostępność) w zwiniętej sekcji „Szczegóły”.
- **Bez powtórzeń:** jedna ocena klasy zamiast trzech („Bardzo dobre”, „Wysoki potencjał”, „Warunki teraz”). Uwagi „model nieskalibrowany” i „ranking nie jest prawdopodobieństwem” — jedna krótka linijka w stopce i w Szczegółach, nie w każdej karcie.
- **Pasek pogody u góry:** jedno zdanie + 7 dni jako małe słupki F (z oznaczeniem niepewności z 4.5) zamiast kropek i długiego tekstu.
- Żargon (M=0.93, S_site=1.00) tylko w Szczegółach.

### UI.4 Telefon

Aplikacja jest używana w lesie, więc układ musi działać przy szerokości ok. 390 px: mapa na całą szerokość, lista i karta jako wysuwany panel od dołu albo zakładki; paski i przyciski wygodne do dotyku; brak poziomego przewijania strony.

### UI.5 Akceptacja

- Przy włączonej presji R, sortowanie i rejony identyczne jak przed zmianami (test).
- Każda informacja z dzisiejszej karty dostępna w nowej karcie (lista kontrolna w raporcie: stare pole → nowe miejsce).
- Pełne testy frontendu (vitest + tsc) i backendu; ręczne sprawdzenie w przeglądarce na szerokości komputera i telefonu; zrzuty ekranu w raporcie.

---

## Faza 5 — dane terenowe (aplikacja kolegi + własne wizyty)

**5.1 Kontrakt danych.** Aplikacja kolegi musi zapisywać **wizyty**, nie tylko znaleziska:
- czas startu i końca, ślad GPS lub przynajmniej obszar wizyty,
- gatunek, liczba, klasa wieku owocników (młode / stare),
- **wizyty z zerowym wynikiem**,
- powód wyboru miejsca: rekomendacja Borowika / znana miejscówka / losowo. Bez tego wynik będzie skażony tym, że ludzie chodzą w znane miejsca.

Prywatność: dokładne współrzędne tylko lokalnie; do analizy agregacja do `stand_id`.

**5.2 Import:** dane w formacie z 2.1 (własne wyjścia) i z aplikacji kolegi; mapowanie śladów GPS na wydzielenia BDL (czas w każdym wydzieleniu, także bez znalezisk); liczba borowików na godzinę jako miara. Porównanie z rankingiem z migawki z dnia wyjazdu, nie z bieżącym.

**5.3 Ocena:** zależność liczby na godzinę od decyli R oraz osobno H i P; GLM Poissona lub ujemny dwumianowy z log(czas) jako offset; rok jako efekt losowy. Analiza osobno dla `powod_wyboru = aplikacja` i pozostałych. Reguły decyzyjne zapisane z góry, jak w 2.0.

**5.4 Eksperyment parami (opcjonalny, gdy właściciel będzie miał czas):** aplikacja losuje parę wydzieleń w tym samym kompleksie, 1–2 km od siebie — jedno z górnych 5% R, jedno ze środka rankingu; równy czas szukania w każdym (np. 30 min), losowa kolejność, w „trybie eksperymentu” bez pokazywania, które jest które. Najbardziej rzetelny dostępny test; potrzeba rzędu kilkudziesięciu par.

**5.5 Kalibracja** wag H, krzywej wieku, α i parametrów presji — dopiero po ≥ 1 sezonie danych, z testem na wyłączonym roku.

---

## Faza 6 — hipotezy do sprawdzenia w terenie (nie do wdrożenia na ślepo)

- Odległość od rzeczywistego skraju lasu (granica unii D-STAN — już liczona dla wejść).
- Linie oddziałowe i dukty (światło, zaburzenie gleby) — cechy z Fazy 1.6.4.
- Granice młodnik / starodrzew.
- Pokrywa gleby, bonitacja, zwarcie i pozostałe cechy z Fazy 1.6.4.

Każda jako cecha w diagnostyce, oceniana na danych z Fazy 5, bez wagi w R do czasu wyniku.

---

## Czego nie robić

- Nie reanimować modelu fali [§15] bez nowej hipotezy i nowego testu.
- Nie dodawać satelitów, NDVI, SAR, LiDAR ani heatmapy 10–50 m przed walidacją H i P.
- Nie zmieniać progów klas po to, żeby mapa była bardziej zróżnicowana.
- Nie traktować rangi 0,626 jako skuteczności ani etykiety pewności jako przedziału ufności.
