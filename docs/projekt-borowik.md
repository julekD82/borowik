# Borowik GIS — projekt systemu typowania miejsc owocnikowania *Boletus edulis*

> Wersja 2.0 · 2026-09-24 · dokument projektowy, zaktualizowany pod rzeczywisty sposób użycia (1–3 wyjazdy rocznie)
>
> Konwencja: **[Z]** = zweryfikowane (zapytanie do API / lektura źródła), **[L]** = literatura naukowa, **[E]** = wiedza ekspercka / prior do kalibracji, **[?]** = do sprawdzenia przy implementacji, **[K]** = zweryfikowane w tej sesji przez przegląd kodu repozytorium.
>
> **Zmiana względem wersji 1.0:** ta wersja nie projektuje systemu od zera. Zachowuje cały działający pipeline (sekcje 2–5, 8) i tylko zmienia to, co wynikało z błędnego założenia o częstym, regularnym użyciu: obowiązkowy dziennik terenowy, walidację na 10–20 znanych miejscówkach, ranking pojedynczych wydzieleń jako główny wynik zamiast rejonów, oraz brak jasnej odpowiedzi na pytanie „jak to w ogóle uruchomić przed wyjazdem”. Sekcja 0 opisuje różnicę; sekcja 6 opisuje, co z wersji 1.0 faktycznie powstało w kodzie.

---

## 0. Cel i sposób korzystania — dopasowanie do rzeczywistości

**Rzeczywisty wzorzec użycia:** wyjścia na grzyby maksymalnie 3 razy w roku, bez znajomości dobrych miejscówek, bez chęci prowadzenia regularnych obserwacji terenowych ani kalibrowania modelu. Aplikacja jest prywatna, ma wymagać minimalnej obsługi i działać poprawnie także po kilku miesiącach nieużywania.

**Konsekwencje dla projektu (szczegóły w kolejnych sekcjach):**

1. **Główny wynik to 3–5 rejonów poszukiwań, nie ranking pojedynczych wydzieleń.** Sekcja 5.6, 10.
2. **Analiza uruchamiana ręcznie przed wyjazdem, nie codziennie.** Nie ma powodu do harmonogramu, jeśli i tak nikt nie patrzy na wynik między wyjazdami. Sekcja 7, 9.
3. **Dziennik obserwacji, eksploracja terenowa i trenowanie modeli ML przechodzą z „obowiązkowe” na „opcjonalne, poza obecnym zakresem”.** Sekcja 16. Aplikacja musi działać i być użyteczna bez ani jednego wpisu w dzienniku.
4. **Walidacja modelu nie może zakładać znajomości 10–20 dobrych miejscówek** — nie są znane. Sekcja 6.3 i 13 opisują, co w tej sytuacji da się realistycznie zweryfikować (poprawność techniczna danych i rankingu, dostępność terenowa) i czego nie da się zweryfikować (rzeczywista skuteczność predykcji) do czasu zebrania własnych obserwacji.
5. **Interfejs ma mieć jeden prosty scenariusz** (lokalizacja → dzień → zasięg → ile chodzić / jak ważne unikanie tłumu → wynik), z rozsądnymi wartościami domyślnymi zamiast wielu suwaków wag modelu. Sekcja 10.
6. **Ocena dostępności i popularności miejsca jest rozbudowana**, bo przy rzadkich wyjazdach liczy się bardziej unikanie tłumu i praktyczny dojazd niż drobne różnice w rankingu siedliskowym. Sekcja 5.5.

**Co NIE się zmienia:** biologia (sekcja 2), analiza źródeł danych (sekcja 3), jednostka obliczeniowa „wydzielenie” (sekcja 4), struktura modelu maska→H→F→P→R (sekcja 5.1), architektura bez serwera/bazy danych w MVP (sekcja 7), zasada „ranking względny i klasy, nie fałszywa precyzja” (sekcja 5.7). Rzadkie użycie samo w sobie nie jest powodem do usuwania klimatologii, percentyli ani innych już działających, bardziej rozbudowanych obliczeń — one nie wymagają bieżącej obsługi, tylko jednorazowo napisanego kodu, który już istnieje i jest przetestowany (sekcja 6).

---

## 1. Najważniejsze wnioski

1. **Najmocniejszą, najtańszą i najdokładniejszą zmienną jest drzewostan z Banku Danych o Lasach.** Publiczny WFS BDL [Z] zwraca dla każdego wydzielenia Lasów Państwowych: typ siedliskowy lasu, gatunek panujący, jego udział, wiek, budowę drzewostanu i typ powierzchni. Robi to w ~0,5 s dla kwadratu 10×10 km. Z tego jednego źródła da się zbudować około 70% wartości MVP. **[K] Zaimplementowane i działające** (`pipeline/bdl.py`).
2. **„Fruiting score” jest najsłabszą częścią systemu i nie może udawać precyzji.** Nawet 10 lat niemal wyczerpującego monitoringu populacji *B. edulis* pod Bielefeld [L1] dało tylko ogólne prawidłowości: optimum ok. 13 °C i dodatni, liniowy wpływ opadu w oknach 3–4 tygodni. Nie powstała reguła typu „X mm → owocniki po Y dniach”. Fruiting pokazujemy więc w **4 klasach**, a nie jako liczbę 0–100.
3. **W promieniu 20 km pogoda różnicuje przestrzeń słabo** (temperatura prawie wcale, opad umiarkowanie, przy burzach mocno). Ranking *miejsc* w danym dniu wynika głównie z siedliska. Fruiting mówi przede wszystkim **„czy w ogóle warto jechać w tym tygodniu”** i **„w której części obszaru padało”**.
4. **Model multiplikatywny z bramkami (hard mask) i osobną warstwą niepewności**, zamiast trzech sumowanych score'ów. Doskonałe siedlisko bez warunków do owocnikowania to 0 szans, a nie 50/100. Presja ludzi to preferencja użytkownika (suwak), a nie biologia. **[K] Zaimplementowane** (`pipeline/scoring.py`, `pipeline/mvp.py`).
5. **Siatka 10 m to fałszywa precyzja.** Jednostką obliczeniową jest **wydzielenie leśne** (typowo 1–10 ha); dane pogodowe przypinamy do komórek 1–9 km. **Nowość w tej wersji:** dla *wyniku pokazywanego użytkownikowi* jednostką prezentacji jest **rejon** — grupa sąsiadujących obiecujących wydzieleń — a nie pojedyncze wydzielenie. Sekcja 5.6.
6. **Satelitarna wilgotność gleby (Sentinel-1 / CLMS SWI) jest dla lasu słaba**; lepszy jest prosty model bilansu wodnego (opad − ET0) z pojemnością wodną zależną od typu siedliska. Model bilansu w wersji uproszczonej (bez własnego „wiadra” per siedlisko) jest już policzony przez Open-Meteo/ERA5-Land i użyty. **[K]** (`pipeline/weather.py`, `cwb26`).
7. **NDVI/NDMI prawie nie przewidują tygodniowego owocnikowania**, ale są przydatne do wykrywania zrębów i zmian od ostatniej aktualizacji BDL. Poza zakresem obecnej wersji — patrz sekcja 17.
8. **GBIF/iNaturalist nie nadają się do trenowania modelu przestrzennego** (silny bias drogowy, 1164 rekordów w całej PL). Nadają się do fenologii (kiedy sezon), nie do lokalizacji (gdzie).
9. **Własne obserwacje terenowe byłyby najcenniejszymi danymi w projekcie, ale nie są warunkiem użyteczności.** Przy 1–3 wyjazdach rocznie zebranie próby wystarczającej do kalibracji modelu zajęłoby wiele lat. Dziennik jest więc **opcjonalny** (sekcja 16), a aplikacja musi działać dobrze na samych priorach eksperckich i publicznych danych.
10. **Obowiązkowa maska prawna:** rezerwaty, parki narodowe, uprawy do 4 m wysokości, drzewostany nasienne, okresowe zakazy wstępu (art. 26 ustawy o lasach). System, który poleca uprawę albo rezerwat, jest gorszy niż brak systemu. **[K] Zaimplementowane** (`pipeline/gdos.py`, `pipeline/zakazy.py`, `pipeline/habitat.py::passes_mask`), z zasadą fail-loud (błąd zapytania o zakaz przerywa działanie zamiast cicho zakładać brak zakazu — sekcja 5.7, punkt o pustej odpowiedzi).
11. **Sama odległość od oznaczonego parkingu jest niewystarczającą miarą presji ludzi.** Rozbudowana w tej wersji ocena „szacowanej dostępności dla odwiedzających” uwzględnia więcej wejść do kompleksu leśnego, zabudowę przy granicy lasu i sieć dróg — patrz sekcja 5.5. Obecna implementacja (`pipeline/pressure.py`, `pipeline/osm.py`) to pierwsza, uproszczona wersja tego pomysłu; rozbudowa jest priorytetem w planie dalszych kroków (sekcja 13).

**Źródła literaturowe:** patrz sekcja 22 (bez zmian względem wersji 1.0).

**Zasada krytyczna:** w Polsce brakuje ilościowych studiów produkcji *B. edulis* w borach sosnowych. Wszystkie progi w sekcji 5 to **priory do kalibracji**, nie fakty. Przy 1–3 wyjazdach rocznie kalibracja danymi terenowymi realistycznie nie nastąpi szybko — patrz sekcja 15 (ograniczenia skuteczności).

---

## 2. Problem biologiczny

*(Bez zmian względem wersji 1.0 — treść nie zależy od częstotliwości użycia aplikacji.)*

### 2.1 Taksonomia: co właściwie typujemy?

W polskiej praktyce grzybiarskiej „prawdziwek” to grupa gatunków o różnych preferencjach:

| Gatunek | Główni partnerzy | Uwagi |
|---|---|---|
| *Boletus edulis* s.str. (borowik szlachetny) | świerk, sosna, buk, dąb, brzoza, jodła | najszersza amplituda siedliskowa |
| *Boletus pinophilus* (b. sosnowy) | sosna, rzadziej świerk | bory, często wcześniej lub później w sezonie |
| *Boletus reticulatus* (b. usiatkowany) | dąb, buk, grab | cieplejszy, **wcześniejszy** (czerwiec–lipiec) |
| *Boletus aereus* (b. ciemnobrązowy) | dąb, buk | rzadki, ciepłe stanowiska |

**Wniosek projektowy:** profile gatunków trzymane w konfiguracji YAML (`profiles/boletus_edulis.yaml` [K]): partnerzy, siedliska, okno fenologiczne. Wybór gatunku w UI to w praktyce zmiana profilu — ten sam mechanizm obsłuży później kurki, podgrzybki czy rydze.

### 2.2 Zmienne: wartość predykcyjna i dostępność danych

Legenda: WP = wartość predykcyjna (W/Ś/N), Rozdz. = rozdzielczość, Trudn. = trudność pozyskania.

| Zmienna | Co wiadomo (i skąd) | WP | Dane PL | Rozdz. przestrz. | Rozdz. czas. | Trudn. |
|---|---|---|---|---|---|---|
| **Gatunki drzew (mikoryza)** | Grzyb ektomikoryzowy z bardzo szerokim spektrum żywicieli iglastych i liściastych [L1]. Bez żywiciela EcM nie ma owocników (olsze, jesiony i klony praktycznie odpadają). | **W** | BDL WFS: gatunek panujący + udział [Z]. Pełny skład na wniosek / w pakietach LMN [?] | wydzielenie (ha) | aktualizacja roczna (stan na 1 I), inwentaryzacja co 10 lat | niska |
| **Typ lasu / siedlisko** | Prawdziwki w PL: przede wszystkim ubogie i średnio żyzne, kwaśne siedliska (bory i bory mieszane świeże, lasy mieszane świeże; w górach świerczyny i buczyny) [E]. Brak ilościowych polskich studiów. | **W** | BDL `site_type` (np. BMŚW, BŚW) [Z] | wydzielenie | ~10 lat | niska |
| **Wiek drzewostanu** | Sprzeczne wyniki. Hiszpania (*P. sylvestris*): maksimum w drzewostanach 60–70-letnich [L2]. Finlandia (*Picea abies*): maksimum **przed pierwszą trzebieżą**, czyli w drzewostanach młodych [L3]. Zgoda co do jednego: uprawy i młodniki są słabe. | **Ś** | BDL `spec_age` [Z] | wydzielenie | roczna | niska |
| **Zagęszczenie / zwarcie** | Drzewostany zbyt rzadkie i zbyt gęste były mniej produktywne [L2]. | Ś | BDL (pełny opis: zwarcie) [?]; CHM z LiDAR [Z-dostępność] | wydz. / 1 m | 10 lat / kampania LiDAR | średnia |
| **pH, typ gleby, C/N** | W Puszczy Białowieskiej produkcja grzybów zależała głównie od bogactwa gatunków, a to od pH i C/N gleby [L4]. Borowik preferuje gleby kwaśne i ubogie w N [E, ogólna ekologia EcM]. | Ś | Brak dobrych map pH dla lasów. SoilGrids 250 m to model słabo ograniczony w lasach. **Typ siedliska z BDL jest lepszym proxy żyzności.** | 250 m (SoilGrids) | statyczne | średnia |
| **Wilgotność gleby** | W sosnowych lasach Hiszpanii satelitarna wilgotność gleby dorównywała opadowi (r = 0,63–0,72) [L5]. | **W** (czasowo) | ERA5-Land / modele NWP (Open-Meteo) [Z]; CLMS SWI 1 km [Z] | 1–9 km | dobowa | niska |
| **Opady (suma okienna)** | Liczba owocników rosła liniowo z opadem skumulowanym w oknie ok. **26 dni** [L1]. Na roczną produkcję opad wpływa najsilniej [L5]. | **W** (czasowo) | IMGW stacje + radar [Z], Open-Meteo [Z] | 1–9 km | godz./dob. | niska |
| **Lag opad → owocniki** | Brak twardej wartości. Ostre okna 5-dniowe słabo wyjaśniały owocnikowanie [L1 v1]; lepiej działały okna 20–26 dni [L1 v2]. Popularne „10–14 dni po deszczu” to hipoteza. | Ś | pochodna opadu | — | — | kalibracja |
| **Temperatura (średnia okienna)** | Kwadratowe optimum ok. **13 °C** średniej dobowej z ~20 poprzednich dni [L1]. Brak owocników przy średniej 5-dniowej > 17,5 °C połączonej z brakiem opadu [L1 v1]. | **W** | IMGW, Open-Meteo | 2–9 km | dobowa | niska |
| **Temp. nocna / minimalna** | Wychłodzenie jako „wyzwalacz” to popularna teza. Mocnych danych dla *B. edulis* nie znalazłem. Pewne: przymrozek kończy sezon. | N–Ś | jw. | jw. | jw. | niska |
| **Temp. 7/14/21/30 dni** | Z [L1] wynika, że istotne są okna ~20 dni. Liczymy je wszystkie, ale MVP używa jednego okna 20-dniowego, żeby nie mnożyć skorelowanych zmiennych. | W (jedno okno) | jw. | | | |
| **Długość okresu suchego** | Konsekwencja bilansu wodnego. Jako osobna zmienna redundantna z wilgotnością gleby. | Ś | pochodna | | | |
| **VPD / ET0** | ET0 potrzebne do bilansu wodnego. VPD istotne raczej dla wysychania owocników niż ich powstawania [E]. | Ś (ET0) / N (VPD) | Open-Meteo [Z] | 2–9 km | godz. | niska |
| **Ekspozycja stoku** | Na nizinach nieistotna. W terenie urozmaiconym działa przez mikroklimat (N zatrzymuje wilgoć w suche lata, S ogrzewa się późną jesienią) [E]. | N (niziny) / Ś (góry) | NMT 1 m GUGiK [Z-dostępność] | 1–5 m | statyczne | średnia |
| **Nachylenie** | Pośrednio (odpływ wody, erozja); w Białowieży wśród predyktorów [L4]. | N | NMT | 1–5 m | stat. | średnia |
| **Wysokość n.p.m.** | Na nizinie ~0. W górach przesuwa fenologię (sezon wcześniej lub później) i zmienia skład drzewostanu. | N (niz.) / Ś (góry) | NMT | | | |
| **TWI / zagłębienia** | Proxy lokalnej wilgotności; sens w latach suchych [E]. | Ś | pochodna NMT | 5–10 m | stat. | średnia |
| **NDVI (rok poprzedni)** | Najlepszy predyktor *rocznej* produkcji w Hiszpanii (r = 0,41–0,6) [L5]. Dla prognozy tygodniowej nieprzydatny. | N (tydzień) / Ś (rok) | Sentinel-2 | 10 m | 5 dni (chmury!) | średnia |
| **NDMI / red edge – zmiany** | Wykrywanie zrębów, obumierania (kornik), trzebieży od ostatniej aktualizacji BDL. | **W** (maska) | Sentinel-2 | 10–20 m | sezonowo | średnia |
| **LAI** | Dubluje zwarcie i NDVI. | N | S2 / CLMS | 10–300 m | | |
| **Temperatura powierzchni (LST)** | Pod koronami mierzy temperaturę koron, nie ściółki. Rozdzielczość 100 m–1 km. | N | Landsat / MODIS | 100 m–1 km | | pomijamy |
| **Zręby, rębnie** | Wycięcie żywiciela oznacza utratę owocników na lata. Uprawy do 4 m są i tak objęte zakazem wstępu. | **W** (maska) | BDL (wiek, typ pow.), S2 change | wydz. | | niska |
| **Trzebieże** | Wynik niejednoznaczny. We włoskich jodłach silna trzebież buforowała negatywny wpływ ekstremów klimatycznych [L6]. | N–Ś | brak aktualnej historii zabiegów w WFS | | | |
| **Depozycja azotu** | Nadmiar N obniża owocnikowanie grzybów EcM [E, ogólna ekologia EcM]. | N | BDL WMS monitoring | regionalna | | poza zakresem |
| **Fenologia regionalna** | Kiedy w danym regionie zwykle jest sezon. | Ś | daty rekordów GBIF/iNat [Z] | region | — | niska |

**Źródła literaturowe:**
- [L1] Brejon Lamartinière & Hoffman (2025), *Predicting porcini…*, bioRxiv — 10 lat monitoringu, buczyna pod Bielefeld. v1: okna 5-dniowe, optimum 13,2 °C, brak owocników przy >17,5 °C i <1 mm/d. v2: temperatura z 20 dni, opad z 26 dni. **Preprint, jedna populacja, las bukowy** — do polskich borów sosnowych przenosić ostrożnie.
- [L2] Martínez-Peña et al. (2012), *Yield models for ectomycorrhizal mushrooms in P. sylvestris…* — 18 powierzchni, 15 lat, Hiszpania.
- [L3] Tahvanainen et al. (2016), *Modelling the yields of marketed mushrooms in Picea abies stands in eastern Finland*, FEM.
- [L4] Stojek, Gillerot, Jaroszewicz (2022), *Predictors of mushroom production in the European temperate mixed deciduous forest*, FEM 522 — Puszcza Białowieska.
- [L5] Collado et al. (2020), *Primary productivity and climate control mushroom yields in Mediterranean pine forests*, AFM; Karavani et al. (2018), AFM.
- [L6] *Combined impact of forest management and climate change on B. edulis productivity*, Italian J. Mycology.

---

## 3. Źródła danych — analiza

*(Bez zmian merytorycznych względem wersji 1.0; oznaczenia [K] dodane przy tym, co faktycznie podłączone w kodzie.)*

### 3.1 Lasy — Bank Danych o Lasach (zweryfikowane, [K] podłączone)

**Endpointy [Z]:**
- WFS (GeoServer): `https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows`, warstwy `BDL:RDLP_<nazwa>_wydzielenia` (17 RDLP), plus `Nadleśnictwa`, `Leśnictwa`, `RDLP`. **[K]** używane przez `pipeline/bdl.py`.
- OGC API Features: `https://ogcapi.bdl.lasy.gov.pl` (te same kolekcje).
- WMS/WMTS (tylko obraz): mapa drzewostanów, siedlisk, zbiorowisk roślinnych, **zakazów wstępu**, dojazdów pożarowych, monitoringu lasu, turystyczna.
- WFS turystyczny i dojazdów pożarowych (ArcGIS): `.../WFS_BDL_mapa_turystyczna/MapServer/WFSServer`, `.../WFS_BDL_dojazdy_pozarowe/...`. **Nie podłączone jeszcze** — patrz sekcja 5.5 i 13 (rozbudowa dostępności).
- Zakazy wstępu: ArcGIS REST MapServer (nie surowe WMS GetFeatureInfo) [K], `pipeline/zakazy.py`, warstwa 0, weryfikacja punktowa dla top-N wyników.

**Atrybuty wydzieleń w WFS [Z]:**

| Pole | Znaczenie | Przykład |
|---|---|---|
| `adr_for` | adres leśny | `08-01-1-01-108 -j -00` |
| `area_type` | typ powierzchni | `D-STAN` (drzewostan) |
| `site_type` | **siedliskowy typ lasu** | `BMŚW`, `BŚW` |
| `species_cd` | **gatunek panujący** | `SO` |
| `part_cd` | udział gatunku panującego (najpewniej w dziesiątych) [?] | `10` |
| `spec_age` | **wiek gatunku panującego** | `130` |
| `stand_stru` | budowa drzewostanu | `DRZEW` |
| `silvicult` | gospodarstwo | `Z`, `P-Z` |
| `forest_fun` | funkcja lasu | `GOSP` |
| `prot_categ` | kategoria ochronności | |
| `rotat_age` | wiek rębności | `100` |
| `sub_area` | powierzchnia [ha] | `2.54` |
| `a_year` | rok danych | `2026` |

Układ: EPSG:2180. **Uwaga na kolejność osi:** przy `urn:ogc:def:crs:EPSG::2180` BBOX podaje się jako `N_min,E_min,N_max,E_max`. **[K]** obsłużone w `pipeline/tiles.py::wfs_bbox_param`.

**Pomiar [Z]:** BBOX 10×10 km w RDLP Piła zwrócił 1904 wydzielenia, 1,6 MB GeoJSON, w 0,48 s.

**Czego w WFS brakuje:** pełnego składu gatunkowego (domieszki), zwarcia, bonitacji, wysokości, typu gleby i historii zabiegów. Te dane są w pełnym opisie taksacyjnym: widać go w popupie mapy BDL, a w wersji wektorowej jest w Leśnej Mapie Numerycznej nadleśnictwa. **Rekomendacja:** dla regionu domowego złożyć wniosek o udostępnienie informacji publicznej / ponowne wykorzystanie (formularz BDL albo nadleśnictwo) o LMN z opisami taksacyjnymi. **Nie scrapować popupów portalu.**

**Luka:** WFS obejmuje wydzielenia Lasów Państwowych. Lasy prywatne i gminne (ok. 1/5 lasów w PL) mają dane uproszczone albo brak danych. Dostają niższy confidence, a status prawny zbioru jest w nich mniej oczywisty.

### 3.2 Gleba

| Źródło | Ocena |
|---|---|
| SoilGrids 2.0 (ISRIC), 250 m, WCS | Model globalny, w lasach Polski słabo ograniczony pomiarami. **Pomijamy.** |
| LUCAS Topsoil (JRC) | Punkty głównie rolnicze, w lasach bardzo rzadkie. Pomijamy. |
| Mapa glebowo-rolnicza (IUNG) | Tylko grunty rolne. Nieprzydatna. |
| **Typ siedliska BDL** | Zawiera jednocześnie żyzność (B/BM/LM/L) i wilgotność (s/św/w/b). **Najlepsze proxy gleby. [K] Używane.** |
| Typ gleby z opisu taksacyjnego (LMN) | Poza obecnym zakresem, jeśli uda się pozyskać wniosek o LMN. |

### 3.3 Pogoda i opady

| Źródło | Rozdz. | Latencja | Historia | Uwagi |
|---|---|---|---|---|
| **IMGW API telemetria** `/api/data/meteo` [Z] | 788 stacji, 699 z opadem 10-min | bieżące | **brak** (tylko stan bieżący) | trzeba odpytywać co 10–60 min i archiwizować samemu; **poza obecnym zakresem** (wymaga stałej infrastruktury) |
| IMGW API synop `/api/data/synop` [Z] | ~60 stacji | godz. | brak | temperatura, wilgotność, opad |
| **IMGW radar** `/api/data/product` [Z] | kompozyt ~1 km | 5–10 min | **tylko najnowszy plik** | `COMPO_PAC` (akumulacja), `COMPO_SRI` (natężenie), HDF5. **Poza obecnym zakresem** — wymaga pollera działającego bez przerwy |
| IMGW archiwum dobowe (klimat, opad, synop) [Z] | posterunki opadowe | z opóźnieniem (miesiące) | od lat 50. | do kalibracji i klimatologii, nie do bieżących danych |
| IMGW COSMO 2,8 km GRIB [Z] | 2,8 km | 4×/dobę | prognoza | poza obecnym zakresem |
| **Open-Meteo** [Z, K] | ICON-D2 ~2 km (prognoza), ERA5/ERA5-Land 9–25 km (archiwum) | godz. | 1940– | jedna biblioteka: opad, Tmin/Tmax, ET0, VPD, wilgotność gleby 0–1 m, `past_days` do 92. **Darmowe tylko niekomercyjnie**, limit <10 000 wywołań/dobę, CC BY 4.0. **Używane w kodzie** (`pipeline/weather.py`, `openmeteo-requests`). |
| ERA5-Land (CDS) | 0,1° (~9 km) | ~5 dni | 1950– | klimatologia (percentyle); w kodzie pobierana przez Open-Meteo archive API, nie bezpośrednio z CDS |
| E-OBS | 0,1° | miesięczna | 1950– | użyte w [L1], dobre do analiz historycznych |
| GPM IMERG | 0,1° | 4 h – 3,5 mies. | 2000– | nad Polską gorsze od radaru + stacji. **Pomijamy.** |
| EUMETSAT H SAF | 3–25 km | NRT | | zgrubne. **Pomijamy.** |

**Decyzja (bez zmian):**
- **Zaimplementowane [K]:** Open-Meteo (siatka punktów co ~5 km, forecast + archiwum + klimatologia percentyli 1991–2020, ta sama biblioteka dla obu).
- **Poza obecnym zakresem, do rozważenia dopiero jeśli okaże się realnym problemem:** własne archiwum IMGW (radar PAC + telemetria) — przy burzach konwekcyjnych różnice opadu w obrębie 20 km sięgają dziesiątek mm, model NWP tego nie odda. Wymaga jednak stale działającego pollera, co jest sprzeczne z zasadą „analiza uruchamiana przed wyjazdem” (sekcja 0, 7) — nie wdrażać bez konkretnego dowodu, że różnica ma znaczenie dla wyników.

**Zmienne pochodne liczone per komórka pogodowa [K, `pipeline/weather.py`]:** P1, P3, P5, P7, P14, P21, P30; P26w (suma ważona wykładniczo, półtrwanie 10 dni); CWB26 = P26w − ET026w; dni od opadu ≥10 mm; długość bieżącego okresu suchego; Tmean20, Tmean5, Tmin3; percentyle CWB26 i wilgotności gleby względem klimatologii ERA5-Land 1991–2020 dla ±15 dni od bieżącego dnia roku.

### 3.4 Wilgotność gleby

| Źródło | Ocena |
|---|---|
| CLMS Soil Water Index 1 km, dobowy, Europa [Z] | Pod zwartym lasem radar pasma C „widzi” głównie korony — jakość w pikselach leśnych niska. **Poza zakresem.** |
| CLMS Surface Soil Moisture 1 km | jak wyżej. **Poza zakresem.** |
| ERA5-Land / modele NWP (przez Open-Meteo) | Model, 9 km, spójny w czasie, bez dziur. **[K] Używane.** |
| Sentinel-1 samodzielnie | Duży wysiłek (kalibracja, speckle, las). **Poza zakresem.** |
| **Własny model „wiadra”** | Per komórka pogodowa × klasa wilgotności siedliska: fizycznie sensowny, ale wymaga kalibracji parametrów Wmax/k, których bez danych terenowych nie da się sensownie dostroić. **Poza obecnym zakresem** — dopiero jeśli CWB26 z Open-Meteo okaże się w praktyce niewystarczające. |

### 3.5 Satelita

| Źródło | Użycie | Dostęp |
|---|---|---|
| **Sentinel-2 L2A** (10/20 m) | kompozyty sezonowe NDVI/NDMI; **detekcja zmian** (zręby, kornik) od roku `a_year` z BDL | Element84 Earth Search (STAC, COG na AWS); Microsoft Planetary Computer; CDSE |
| Landsat 8/9 | dłuższa historia zmian (30 m) | USGS / Planetary Computer |
| Sentinel-1 | wilgotność: patrz wyżej. **Poza zakresem.** | CDSE |
| Gotowe produkty zmian | Hansen/GFW Tree Cover Loss (30 m, roczne); europejska mapa zaburzeń (Senf & Seidl, 30 m) | darmowe; tańsza alternatywa dla własnej detekcji |
| CLMS HRL Tree Cover Density / Dominant Leaf Type (10 m) | tylko poza lasami LP, gdzie brak BDL | CLMS |

**Werdykt (bez zmian):** dla owocnikowania tydzień-do-tygodnia NDVI/NDMI to prawie szum. Do utrzymania aktualności siedliska są cenne, ale **poza obecnym zakresem** — bieżąco działający pipeline (sekcja 6) nie ma jeszcze detekcji zmian S2, więc świeżość BDL jest dziś oceniana tylko po dacie `a_year`, bez potwierdzenia satelitarnego (widoczne w `confidence.py` jako stały czynnik 1,0 — patrz sekcja 11).

### 3.6 Teren

- **GUGiK NMT** 1 m i 5 m, bezpłatny od 2020 r. **Poza obecnym zakresem** — pipeline dziś nie pobiera NMT ani nie liczy TWI/ekspozycji/nachylenia.
- **Na nizinach teren prawie nic nie wnosi** (poza TWI i zagłębieniami w latach suchych). W górach i na pogórzu to istotny modyfikator — jeśli obszar poszukiwań jest górski, warto podnieść priorytet tego punktu w roadmapie (sekcja 13).

### 3.7 Presja ludzi i dostępność

| Źródło | Co daje | Status |
|---|---|---|
| OpenStreetMap (Overpass) | drogi, parkingi, miejscowości | **[K] Używane** — `pipeline/osm.py`, tylko `amenity=parking` i drogi utwardzone (trunk…residential), miejscowości z ludnością |
| OpenStreetMap — ścieżki, szlaki turystyczne (`highway=path/footway`, `route=hiking`) | infrastruktura turystyczna jako przesłanka popularności | **Nie podłączone** — patrz sekcja 5.5, priorytet w sekcji 13 |
| **BDOT10k** (GUGiK, bezpłatny) | pełniejsza sieć dróg (także leśnych) niż OSM w wielu regionach | Nie podłączone |
| BDL WFS turystyczny i dojazdy pożarowe [Z] | parkingi leśne, miejsca postoju, infrastruktura; drogi pożarowe (przejezdne) | Nie podłączone — dobry kandydat na „potwierdzone wejście” (sekcja 5.5) |
| Siatka ludności 1 km (Eurostat/GUS) | „popyt”: ile osób mieszka w zasięgu dojazdu | **Nie podłączone** — obecny model demand używa punktów miejscowości OSM z tagiem `population`, nie siatki gridowej; działa, ale jest zgrubniejsze |
| **Strava Heatmap / Global Heatmap** | **Nie używać.** Regulamin zabrania scrapowania i reużycia. | — |
| Dane telekomunikacyjne o ruchu | Niepubliczne. | — |

**Nie ma legalnych, publicznych danych o natężeniu ruchu grzybiarzy.** Presja to model grawitacyjny (populacja / czas dojazdu² × dostępność lokalna) bez walidacji — nazywany w tej wersji jawnie „szacowaną dostępnością dla odwiedzających”, nie pomiarem tłoku (sekcja 5.5).

### 3.8 Historyczne występowanie

- **GBIF** [Z]: 1300 rekordów *B. edulis* w PL, z czego 1164 z koordynatami, w tym **1073 z iNaturalist**. Bias drogowy.
- **Zastosowanie: [K] tylko fenologia** (rozkład dni roku), nie dane treningowe do lokalnego rankingu.

---

## 4. Jednostka analizy

*(Decyzja bez zmian — wydzielenie jako jednostka obliczeniowa. Nowość: sekcja 5.6 dodaje warstwę grupowania w rejony na potrzeby prezentacji wyniku, nie zmienia to, jak liczone jest H/F/R.)*

### 4.1 Porównanie

| Opcja | Plusy | Minusy | Werdykt |
|---|---|---|---|
| **A. Wydzielenie BDL** | Naturalna jednostka biologiczna. Bezpośrednio pasuje do najmocniejszych danych. Zrozumiała w terenie (numer oddziału na słupku). 1–10 ha to skala przeszukiwalna w 30–90 min. | Wewnątrz duże wydzielenia (>10 ha) są niejednorodne. Brak pokrycia lasów prywatnych. | **Rdzeń, [K] zaimplementowane** |
| B. Siatka 10×10 m | wygląda imponująco | Żadne dane dynamiczne nie mają tej rozdzielczości. **Czysta fałszywa precyzja.** | Nie |
| B. 20×20 m / 50×50 m / 100–250 m | kompromisy rastrowe | sztuczna precyzja siedliska, rozmywanie granic | Nie |
| **C. Hybryda: wydzielenie + mikrokomórki 25 m** | lokalne „gorące strefy” w terenie urozmaiconym | złożoność; wymaga NMT | Poza obecnym zakresem, tylko teren górski jeśli to Twój region |

### 4.2 Decyzja

- **Jednostka obliczeniowa i raportowa: wydzielenie** (`stand_id` = `adr_for` + `a_year`). **[K] Zaimplementowane.**
- **Jednostka prezentacji w głównym wyniku: rejon** (grupa sąsiadujących obiecujących wydzieleń, sekcja 5.6). **Do zaimplementowania.**
- **Pogoda:** komórki siatki pogodowej (Open-Meteo ~5 km). Wydzielenie dostaje wartości komórki najbliższej centroidowi. **[K]**
- **Teren:** poza obecnym zakresem (sekcja 3.6).
- **Lasy bez BDL:** fallback nieobsłużony w obecnym kodzie — poza obecnym zakresem, patrz sekcja 13.
- **Zasada w UI:** wynik na wielokącie wydzielenia / obrysie rejonu, nie jako gładka heatmapa.

---

## 5. Model scoringowy (bez ML)

### 5.1 Struktura

```
MASKA (0/1)      = legalne ∧ las z żywicielem EcM ∧ nie uprawa/zrąb
HABITAT H (0–1)  = „czy tu żyje grzybnia i ma warunki do owocnikowania w dobrym roku”
FRUITING F (0–1) = „czy warunki ostatnich ~3–4 tygodni sprzyjają owocnikowaniu”
TERAZ = H × F                 ← wynik biologiczny
DOSTĘPNOŚĆ DLA MNIE  = wygoda dojazdu i dojścia (filtr / informacja, nie mnożnik R)
POPULARNOŚĆ P (0–1)  = szacowana dostępność dla innych odwiedzających (presja)
RANKING R = 100 · MASKA · H · F · (1 − α·P),   α ∈ [0; 0,6] suwak, domyślnie 0,3
CONFIDENCE       = osobna oś, nigdy nie wchodzi do R
REJON            = grupa sąsiadujących wydzieleń z wysokim R (warstwa prezentacji nad R)
```

**Zmiana względem wersji 1.0:** rozdzielenie dawnego „P/A” (sekcja 4.5 w wersji 1.0) na dwie osobno nazwane i osobno pokazywane wielkości — **wygodę dojazdu dla mnie** (filtr, nie wpływa na R) i **szacowaną popularność rejonu** (wpływa na R przez α, tak jak dawniej). Powód: to są różne pytania („czy ja tam dojadę” vs „ile osób tam dojedzie”) i miksowanie ich w jedną liczbę myliło jedno z drugim. Szczegóły w sekcji 5.5.

**Uzasadnienie struktury (bez zmian):**
- **Iloczyn, nie suma:** brak żywiciela albo susza dają ~0. Suma dałaby wysokie wyniki w miejscach bez szans.
- **Log-addytywność:** log R = log H + log F + log(1−αP), na tym oparte jest proste wyjaśnianie (sekcja 5.8). **[K] Zaimplementowane** (`pipeline/explain.py`).
- To jest też struktura modelu occupancy (ψ × p) — gdyby kiedyś powstały dane do ML, model MVP i ML mówią tym samym językiem. To nie znaczy, że ML jest w planach bliskiego zakresu (sekcja 16).

### 5.2 Maska twarda (0/1)

| Warunek | Źródło | Status |
|---|---|---|
| Rezerwat przyrody, park narodowy | GDOŚ WFS | **[K] Zaimplementowane** (`pipeline/gdos.py`) |
| Uprawa < 4 m wysokości (proxy: `spec_age < 12`) | BDL | **[K] Zaimplementowane**, ale to **proxy, nie prawne potwierdzenie** — patrz zastrzeżenie niżej |
| Drzewostan nasienny, powierzchnia doświadczalna, ostoja | BDL (pełny opis) [?] | Nie podłączone (dane niedostępne przez WFS) |
| Okresowy zakaz wstępu | BDL, ArcGIS REST (zakazy wstępu) | **[K] Zaimplementowane**, fail-loud na błędzie zapytania (`ZakazyQueryError`), sprawdzane dla top-N wyników przy generowaniu rejonów |
| `area_type` ≠ drzewostan | BDL | **[K] Zaimplementowane** |
| Gatunek panujący bez EcM *B. edulis*, udział ≥ 8/10 | BDL | **[K] Zaimplementowane** |
| Zmiana w S2 od `a_year` (zrąb po aktualizacji BDL) | Sentinel-2 | Poza zakresem (sekcja 3.5) |

**Zastrzeżenie (wymagane rozróżnienie potwierdzone/ostrożny filtr/brak danych, patrz sekcja 15):**
- `spec_age < 12` jest **ostrożnym proxy**, nie prawnym potwierdzeniem, że drzewostan ma faktycznie poniżej 4 m wysokości. Wiek 12 lat nie gwarantuje konkretnej wysokości (zależy od gatunku, bonitacji, siedliska) — próg dobrany tak, by raczej nadmiarowo wykluczać niż nadmiarowo dopuszczać. Nie prezentować w UI jako „potwierdzony zakaz”, tylko jako „prawdopodobna uprawa — wykluczone ostrożnościowo”.
- **Pusta odpowiedź serwisu zakazów wstępu nie jest traktowana jako potwierdzenie braku zakazu** — `pipeline/zakazy.py` rozróżnia „zapytanie się powiodło i nie zwróciło żadnego poligonu” (rzeczywiście brak zakazu w tym punkcie) od „zapytanie się nie powiodło” (rzuca `ZakazyQueryError`, cały bieg pipeline'u przerywa się zamiast pokazać wynik z niepewnym statusem prawnym). Weryfikacja kodu **[K] potwierdza to zachowanie jest już poprawne**. Do doprecyzowania w UI: awaria źródła zakazów dla top-N wyników powinna zatrzymać cały bieg (bo to maska obowiązkowa), a nie tylko oznaczyć dany wynik jako niepewny — patrz sekcja 8.

### 5.3 HABITAT H

**H = S_host^0,40 · S_site^0,35 · S_age^0,25** — **[K] zaimplementowane w `pipeline/habitat.py`**, wagi i tabele w `profiles/boletus_edulis.yaml`, bez zmian względem wersji 1.0.

**S_host** = Σ udział_i × powinowactwo_i. W MVP znamy tylko gatunek panujący, więc reszta to „nieznana domieszka” z powinowactwem 0,5.

| Kod BDL | Gatunek | Powinowactwo [E] | Podstawa |
|---|---|---|---|
| SO | sosna zwyczajna | 1,0 | główny żywiciel w PL (także *B. pinophilus*) |
| ŚW | świerk | 1,0 | główny żywiciel [L3] |
| BK | buk | 0,9 | żywiciel [L1] |
| DB (DB.S, DB.B) | dęby | 0,8 | żywiciel; także *B. reticulatus* |
| JD | jodła | 0,8 | żywiciel [L6] |
| BRZ | brzoza | 0,7 | żywiciel |
| GB | grab | 0,3 | EcM, słabszy partner [E] |
| MD | modrzew | 0,3 | głównie specjaliści |
| DG | daglezja | 0,3 | gatunek obcy, słabo udokumentowane |
| LP | lipa | 0,3 | EcM, słabo udokumentowane |
| OS, TP | osika, topole | 0,2 | |
| OL, JS, KL, WZ, AK | olsza, jesion, klon, wiąz, robinia | 0,0 | brak EcM z *B. edulis* |

**Zastrzeżenie (brak danych o domieszkach, sekcja 15):** BDL WFS zwraca tylko gatunek panujący, nie pełny skład. „Nieznana domieszka” dostaje powinowactwo 0,5, czyli neutralne — celowo, żeby brak danych o drugim/trzecim gatunku w drzewostanie nie obniżał ani nie podnosił sztucznie H. To jest **łagodzenie**, nie rozwiązanie: drzewostan „SO 60% / OL 40%” i „SO 60% / ŚW 40%” dostają dziś ten sam wynik, mimo realnie różnego potencjału. W panelu szczegółów jawnie pokazywane jako „domieszki: brak danych” (już w projekcie UI wersji 1.0, sekcja 10).

**S_site**, z rozbiciem na żyzność i wilgotność:

| Siedlisko | S_site [E] | Klasa wilgotności `m` |
|---|---|---|
| BMŚW, BŚW | 1,0 / 0,85 | świeże (1) |
| LMŚW | 0,85 | świeże (1) |
| BMW, BW, LMW | 0,65 | wilgotne (2) |
| LŚW | 0,6 | świeże (1) |
| BS (bór suchy) | 0,45 | suche (0) |
| LW | 0,4 | wilgotne (2) |
| BMB, BB, LMB | 0,15 | bagienne (3) |
| OL, OLJ, LŁ | 0,0 (maska) | — |
| górskie: BWG, BMWYŻ, LMG, LG, LWYŻ… | 0,7–0,9 (do uzupełnienia) | wg sufiksu |

**S_age** (wiek gatunku panującego, `spec_age`), funkcja odcinkowo-liniowa:

```
wiek < 12        → maska (uprawa, proxy — patrz zastrzeżenie 5.2)
12–20            → 0,3 → 0,6 (liniowo)
20–35            → 0,6 → 1,0
35–120           → 1,0
>120             → 0,9
```

Uzasadnienie: zgoda literatury co do niskiej produkcji najmłodszych drzewostanów; sprzeczność co do wieku optymalnego (Finlandia [L3] vs Hiszpania [L2]) oznacza brak podstaw do penalizowania wieku 20–120. Funkcja celowo płaska.

**Poza obecnym zakresem:** S_density (zwarcie), S_micro (TWI), S_disturb (S2 change) — wymagają danych z sekcji 3.6/3.5, których pipeline dziś nie pobiera.

### 5.4 FRUITING F

**F = G_season · M^0,6 · T^0,4 · K_frost**, potem modulacja lokalna klasą wilgotności siedliska. **[K] Zaimplementowane w `pipeline/scoring.py`**, parametry w profilu YAML.

1. **G_season** — okno fenologiczne z rozkładu dat GBIF/iNat dla PL. *(W obecnym kodzie `run_poc` przekazuje G_season = 1,0 jako uproszczenie do czasu podłączenia rzeczywistego rozkładu GBIF — patrz sekcja 8, punkt do poprawy.)*
2. **M — wilgoć:** `P26w`, `CWB26 = P26w − ET026w`, `SM` (wilgotność gleby 9–27 cm), każda przeliczona na percentyl względem klimatologii komórki dla ±15 dni od bieżącego dnia roku (ERA5-Land 1991–2020). `M = logistic((mean(pct_CWB26, pct_SM) − 0,35)/0,1)`.
3. **T — temperatura:** `T = exp(−(Tmean20 − 13)²/(2·4²))`, kara ×0,3 jeśli `Tmean5 > 17,5°C` i `P5 < 5 mm`.
4. **K_frost** = 0,2 gdy Tmin3 < −2°C; 0,6 przy −2…0°C; inaczej 1.
5. **Modulacja lokalna wilgotnością siedliska** (interakcja H×F): w suche lata mnożnik faworyzuje siedliska wilgotniejsze, w mokre — suchsze. **Niezweryfikowana [E]**, dobry pierwszy kandydat do sprawdzenia w terenie (sekcja 15).

**Prezentacja F:** 4 klasy, bez liczby na mapie (`fruiting_classes` w profilu YAML, **[K] zaimplementowane**):

| F | Klasa |
|---|---|
| < 0,20 | „Słabe warunki” |
| 0,20–0,45 | „Umiarkowane” |
| 0,45–0,70 | „Dobre” |
| ≥ 0,70 | „Bardzo dobre” |

### 5.5 Dostępność — dwa osobne pytania

Sama odległość od oznaczonego parkingu jest niewystarczającą miarą ani wygody dojazdu, ani presji innych grzybiarzy. Rozdzielamy dwa pytania, które wersja 1.0 częściowo myliła:

#### 5.5.1 Wygoda mojego dotarcia (filtr, nie wchodzi do R)

Dojazd do punktu startowego i dojście do rejonu poszukiwań. Pokazywana użytkownikowi osobno przy każdej propozycji rejonu (sekcja 10): odległość/czas dojazdu do parkingu, długość dojścia pieszo do granicy rejonu, status weryfikacji punktu startowego (patrz niżej). Może być użyta jako **filtr** („maks. 2 km pieszo od auta”), ale nigdy nie mnoży R — inaczej rejon niedostępny wygrywałby tylko dlatego, że jest blisko, niezależnie od jakości siedliska, albo odwrotnie: dobry rejon przepadałby tylko dlatego, że jest odrobinę dalej.

#### 5.5.2 Szacowana popularność rejonu (wchodzi do R przez P i suwak α)

**Cel:** znajdować miejsca z możliwie małą liczbą innych grzybiarzy — ale nazywać wynik uczciwie: to jest **szacowana dostępność dla odwiedzających**, nie pomiar tłoku. Brak oznaczonego parkingu nie może automatycznie oznaczać małej liczby ludzi (może po prostu oznaczać brak danych o parkingu).

**Czynniki do uwzględnienia (rozbudowa względem wersji 1.0, do zaimplementowania — priorytet w sekcji 13):**
- **Różne potencjalne wejścia do kompleksu leśnego**, nie tylko oznaczone parkingi: każde przecięcie drogi publicznej/drogi leśnej z granicą lasu to *potencjalne* wejście, nie *potwierdzone*. Rozróżniać te dwa stany w danych i w UI.
- **Zabudowa i miejscowości przy granicy lasu**, z których można wejść pieszo bez samochodu — dziś model demand liczy tylko miejscowości z tagiem `population` w OSM w promieniu, bez rozróżnienia, czy dana miejscowość faktycznie styka się z lasem.
- **Dostęp po sieci dróg i ścieżek** — patrz niżej (routing).
- **Oznaczone szlaki i infrastruktura turystyczna** (`highway=path`, `route=hiking`, wiaty, tablice) jako pomocnicza przesłanka popularności — dziś nie pobierane (sekcja 3.7).
- **Bariery utrudniające dojście**, jeśli są dostępne w danych: rzeki bez mostu, ogrodzenia, tereny wojskowe. Nie ma dziś ich uwzględnienia; nawet prosta reguła „rzeka bez przecięcia z drogą w promieniu X m od wejścia = bariera” byłaby ulepszeniem, ale wymaga dodatkowego źródła (cieki wodne z OSM/BDOT10k) i nie jest wpisana w pierwszą iterację rozbudowy.

**Zasada dotycząca odległości:** liczyć **po dostępnej sieci dróg i ścieżek**, jeśli dane na to pozwalają, a nie w linii prostej. Obecna implementacja (`pipeline/pressure.py`) liczy odległość euklidesową do najbliższego parkingu/drogi utwardzonej i mnoży ją przez stały współczynnik 1,3 — to jest **przybliżenie zaakceptowane świadomie na czas MVP**, jawnie opisane w kodzie jako uproszczenie, nie jako rzeczywista trasa. Pełna analiza sieciowa (graf dróg + routing pieszy, np. lekki własny graf z OSM zamiast płatnego API) jest kosztowna obliczeniowo dla całego obszaru — **rozwiązanie na pierwszą wersję: liczyć routing tylko dla najlepszych kandydatów** (np. top 20–30 wydzieleń po R, przed grupowaniem w rejony), nie dla całego kafla. Jawnie opisać to uproszczenie w UI („dystans: linia prosta ×1,3” vs „dystans: po drogach”).

**Nie zakładać:**
- że droga widoczna na mapie dopuszcza ruch samochodów (drogi leśne bywają zamknięte szlabanem — dlatego `pipeline/osm.py` już dziś **[K] celowo wyklucza** `highway=track` z odległości do parkingu, zostawiając tylko drogi publiczne utwardzone);
- że każde przecięcie drogi z granicą lasu jest potwierdzonym wejściem — rozróżniać „potwierdzone” (oznaczony parking BDL/OSM) i „potencjalne” (samo przecięcie drogi z granicą lasu) w danych i w UI;
- że obecność jednego, oddalonego wejścia oznacza dobrą dostępność dla mnie — to inne pytanie niż popularność (5.5.1 vs 5.5.2).

**Ograniczenie wpływu na ranking:** preferencja spokojniejszych miejsc (suwak α) ma pomagać **wybierać między obiecującymi rejonami**, nie sprawiać, że słabo oceniony siedliskowo lub trudno dostępny teren wygrywa wyłącznie dzięki oddaleniu od wejść. Struktura `R = 100 · MASKA · H · F · (1 − α·P)` już to zapewnia matematycznie: P wpływa tylko multiplikatywnie na wynik, który i tak jest zerowany przez maskę i skalowany przez H·F — rejon o H·F bliskim zeru zostaje nisko w rankingu niezależnie od tego, jak bardzo odludny. Do przypilnowania przy rozbudowie: żeby nowe czynniki popularności (szlaki, zabudowa) nie zamieniły P w dominujący composite, który przy α=0,6 zacznie przeważać nad H·F w praktyce — warto przy wdrożeniu sprawdzić rozkład P na realnych danych (tak jak już raz zrobiono przy wykluczeniu `track` z `d_park`, patrz komentarz w `profiles/boletus_edulis.yaml`).

**Najprostsze rozwiązanie na pierwszą wersję (rekomendacja):** rozszerzyć dzisiejszy model o (a) punkty przecięcia dróg publicznych i ścieżek OSM z granicą lasu jako potencjalne wejścia (dane już pobierane przez Overpass, tylko nieużywane w ten sposób), (b) flagę „potwierdzone” dla wejść pokrywających się z parkingiem BDL/OSM, (c) routing tylko dla top-N kandydatów. Nie dodawać całorocznego monitoringu ruchu, scrapowania serwisów ani płatnych źródeł.

### 5.6 Grupowanie w rejony poszukiwań (nowość, do zaimplementowania)

Głównym wynikiem ma być **3–5 rejonów na wycieczkę**, nie ranking pojedynczych wydzieleń. Propozycja prostego algorytmu na pierwszą wersję:

1. Wybrać wydzielenia przechodzące maskę z R powyżej progu (np. top 25% w obszarze, jak dziś w UI — sekcja 5.7).
2. Połączyć w rejony sąsiadujące/bliskie wybrane wydzielenia (np. przez `unary_union` buforowanych geometrii z niewielkim buforem, tak jak grupuje się sąsiadujące poligony — standardowa operacja w GeoPandas/Shapely, bez nowej zależności).
3. **Nie premiować automatycznie największego lasu przez sumowanie punktów.** Wynik rejonu to **mediana lub najlepsze N wydzieleń** wewnątrz grupy (np. mediana R top-5 wydzieleń w rejonie), nie suma R po wszystkich wydzieleniach — suma faworyzowałaby rozległe kompleksy leśne niezależnie od tego, czy są jednorodnie dobre.
4. Odrzucić rejony będące w praktyce fragmentami tego samego kompleksu co już wybrany, lepiej oceniony rejon (np. odległość środków rejonów < X km i ten sam kompleks leśny → połącz, nie duplikuj).
5. Zwrócić top 3–5 rejonów po odległości od siebie i wyniku — nie tylko top 5 wydzieleń, które mogą być pięcioma sąsiadującymi fragmentami jednego miejsca.

To wymaga kodu (poza zakresem obecnego kroku dokumentacyjnego), ale jest zapisane tu jako konkretny, wykonalny plan — patrz sekcja 13, priorytet 1.

### 5.7 Liczby w UI a fałszywa precyzja

- Na mapie/w liście rejonów: **ranking względny** w bieżącym obszarze (top 5%, 10%, 25%) i klasy, nie „87/100” jako jedyna informacja.
- W panelu szczegółów: liczby 0–100 dopuszczalne z dopiskiem **„model ekspercki, nieskalibrowany”**.
- **Zastrzeżenie „top 5% w słabym regionie” (sekcja 15):** ranking procentowy jest zawsze *względny do bieżącego obszaru i dnia*. „Top 5%” w regionie, gdzie baner regionalny (sekcja 10) pokazuje słabe ogólne warunki F, nie oznacza dobrych warunków bezwzględnie — oznacza „najlepsze z tego, co słabe”. UI musi pokazywać oba razem: ranking względny **i** baner regionalny z klasą F dla całego obszaru, nigdy tylko ranking w oderwaniu od tego, czy w ogóle warto jechać.
- **Zastrzeżenie „nieskalibrowany wynik ≠ prawdopodobieństwo” (sekcja 15):** R i H/F nie są prawdopodobieństwem znalezienia grzyba. Nazywać je „szacowany potencjał” / „względny ranking”, nigdy „szansa X%” do czasu ewentualnej kalibracji na danych terenowych (sekcja 16), która przy 1–3 wyjazdach rocznie może nigdy nie nastąpić.

### 5.8 Wyjaśnienia

W modelu multiplikatywnym `log R` jest sumą wkładów. Wkład każdego czynnika liczony jako `log(czynnik) − log(mediana czynnika w obszarze)`, sortowany, generowane zdania z szablonów (2 plusy, 1–2 minusy). **[K] Zaimplementowane w `pipeline/explain.py`**, bez LLM-a, deterministycznie.

---

## 6. Stan implementacji (kroki 1–11) — ustalony na podstawie repozytorium

Poniższa tabela to wynik przeglądu kodu (`pipeline/*.py`, `notebooks/*.py`, `profiles/boletus_edulis.yaml`) i uruchomienia pełnego zestawu testów (`144 passed`) w tej sesji — nie deklaracja z wcześniejszych commitów.

| # | Krok z planu wersji 1.0 (sekcja 9) | Stan | Dowód w kodzie |
|---|---|---|---|
| 1 | Repo, `pyproject.toml`, struktura `pipeline/`, profil YAML | **Zrobione** | `pyproject.toml`, `profiles/boletus_edulis.yaml` |
| 2 | `fetch_bdl(tile)`: WFS GetFeature, BBOX, stronicowanie, GeoParquet | **Zrobione** | `pipeline/bdl.py`, `tests/test_bdl.py` |
| 3 | Parser `site_type` → żyzność/wilgotność, tabela powinowactwa | **Zrobione** | `pipeline/habitat.py`, `tests/test_habitat.py` |
| 4 | `fetch_weather`: Open-Meteo archiwum+prognoza, siatka punktów | **Zrobione** | `pipeline/weather.py`, `tests/test_weather.py` |
| 5 | Klimatologia ERA5-Land 1991–2020, percentyle ±15 dni | **Zrobione** | `pipeline/weather.py::climatology_window_values`, `percentile_rank` |
| 6 | Obliczenie H, F, R; mapa poglądowa | **Zrobione** (H, F, R w `run_poc`); mapa `folium`/`lonboard` — nie znaleziono w repo, prawdopodobnie tylko notebook interaktywny | `pipeline/orchestrate.py::run_poc` |
| 7 | Walidacja jakościowa na 10–20 znanych miejscach | **Zrobione jako mechanizm** (`pipeline/validate.py`, `notebooks/known_points.example.yaml`), **ale wymaga pliku `known_points.yaml`, którego użytkownik nie ma** — patrz sekcja 0 pkt 4 i sekcja 15 | `pipeline/validate.py`, `notebooks/02_mvp.py` (sprawdza `known_points_path.exists()`) |
| 8 | Maska: GDOŚ, uprawy, zakazy wstępu | **Zrobione**, z fail-loud na błędzie zapytania o zakazy | `pipeline/gdos.py`, `pipeline/zakazy.py`, `pipeline/habitat.py::passes_mask` |
| 9 | OSM: parkingi, drogi, demand z ludności | **Zrobione częściowo** — parkingi (`amenity=parking`) i drogi utwardzone tak; demand liczony z miejscowości OSM z tagiem `population`, nie z siatki gridowej Eurostat/GUS jak planowano; odległości euklidesowe ×1,3, nie po sieci dróg | `pipeline/osm.py`, `pipeline/pressure.py`, `tests/test_osm.py`, `tests/test_pressure.py` |
| 10 | Confidence i wyjaśnienia | **Zrobione** | `pipeline/confidence.py`, `pipeline/explain.py` |
| 11 | Eksport: `tippecanoe` → PMTiles; `scores_{date}.json` | **Częściowo zrobione.** `scores_{date}.json` — tak, w pełni działający eksport z bezpiecznym JSON (NaN→null). **PMTiles — nie.** Kod eksportuje tylko `stands_mvp.parquet` (id + geometria, GeoParquet), jawnie opisany w komentarzu jako *wejście do przyszłego kroku tippecanoe/PMTiles, poza zakresem obecnego planu*. Nie ma wywołania `tippecanoe`, nie ma pliku `.pmtiles` w repozytorium. | `pipeline/export.py` (`write_scores_json` — pełne; `export_stand_geometries` — tylko GeoParquet) |

**Co dodatkowo istnieje, a nie było punktem 1–11:** `pipeline/mvp.py::enrich_with_mvp_layers` — spina maskę GDOŚ+zakazy, presję, confidence i wyjaśnienia w jeden krok (to jest właściwie „Faza 2” z planu wersji 1.0, sekcja 9 kroki 8–11, zaimplementowana jako jedna funkcja); `notebooks/02_mvp.py` — działający end-to-end skrypt na **jednej zahardkodowanej lokalizacji** (Kieleczka, RDLP Katowice, `LAT, LON = 50.526944, 18.605000`), bez parametrów wejściowych (lokalizacja/dzień/promień), bez schedulera, bez frontendu.

**Czego nie ma wcale (sprawdzone: brak plików w repo):**
- **Frontendu.** Brak `vite.config`, `package.json`, plików `.html` — sekcje 6/9 planu wersji 1.0 (Vite + TypeScript + MapLibre) nie mają żadnego kodu. Cały interfejs użytkownika istnieje dziś tylko jako `print()` w notebooku i plik JSON.
- **PMTiles.** Patrz krok 11 wyżej.
- **CLI / parametryzacji.** Nie da się dziś uruchomić analizy dla innej lokalizacji bez edycji kodu w `notebooks/02_mvp.py`.
- **Harmonogramu** (Task Scheduler / GitHub Actions) — i tak niepotrzebny przy realnym wzorcu użycia (sekcja 0), ale wart odnotowania, że nie istnieje.
- **NMT/TWI, Sentinel-2, IMGW radar/telemetria, model wiadra** — zgodnie z planem wersji 1.0 były to elementy fazy 3+, nietknięte, bez zmian w tej wersji.

**Wniosek:** backend obliczeniowy (kroki 2–10) jest solidny, przetestowany (144 testy przechodzą) i gotowy do użycia jako biblioteka. To, czego naprawdę brakuje do „pierwszej użytecznej wersji” w rozumieniu sekcji 0, to: (a) grupowanie w rejony (sekcja 5.6), (b) rozbudowa dostępności (sekcja 5.5.2), (c) parametryzowalne, jednopoleceniowe uruchomienie (sekcja 7), (d) jakikolwiek frontend/wyświetlenie wyniku na telefonie (sekcja 10), (e) realistyczna metoda weryfikacji zamiast 10–20 znanych miejscówek (sekcja 15).

---

## 7. Architektura aplikacji i uruchamianie

### 7.1 Zasada (bez zmian)

Bez serwera bazodanowego i bez backendu webowego. Pipeline w Pythonie generuje pliki, statyczny frontend je wyświetla. PostGIS i FastAPI pojawiają się dopiero z danymi terenowymi i wieloma użytkownikami (faza obserwacji, sekcja 16) — a przy 1–3 wyjazdach rocznie może nigdy się to nie zdarzyć, i to jest w porządku.

### 7.2 Jak faktycznie uruchamiać analizę przed wyjazdem

Statyczny frontend sam nie uruchomi lokalnego Pythona — to wymaga jawnej decyzji, jej brak w wersji 1.0 był realną luką.

**Wybrana architektura (najprostsza pasująca do repozytorium):**

1. **Jedno polecenie na komputerze przed wyjazdem:** `uv run python -m pipeline.prepare_trip --lat 50.5 --lon 18.6 --date 2026-10-05 --radius-km 25 --max-walk-km 2 --avoid-crowds medium` (nazwa i parametry orientacyjne — do ustalenia przy implementacji, ale zasada: jedno wywołanie, wartości domyślne dla wszystkiego poza lokalizacją i dniem). Ten skrypt to w praktyce to, co dziś robi `notebooks/02_mvp.py`, tylko sparametryzowane zamiast zahardkodowane, plus krok grupowania w rejony (sekcja 5.6).
2. **Wynik: statyczne pliki** — zaktualizowany `stands.pmtiles` (przebudowywany tylko gdy zmienił się cache BDL dla danego obszaru, nie za każdym razem) + `regions_{date}.json` (rejony, każdy z listą pól z sekcji 10) + `scores_{date}.json` (szczegóły wydzieleń, widok dodatkowy).
3. **Wyświetlenie na telefonie — bez własnego backendu:** ponieważ strona jest w pełni statyczna, najprostszym sposobem pokazania jej na telefonie jest wdrożenie tych samych plików na już wybrany darmowy hosting statyczny (Cloudflare Pages / GitHub Pages, patrz sekcja 18 — koszt 0). Krok 1 kończy się więc (opcjonalnym, ale zalecanym) automatycznym `git push` / `wrangler pages deploy` do tego samego miejsca co poprzednio, a nie ręcznym kopiowaniem plików. Otwierasz ten sam adres URL na telefonie co zawsze. Nie jest to backend „dla przycisku Analizuj” — przycisku nie ma, jest jedno polecenie terminalowe uruchamiane ręcznie, a hosting służy wyłącznie do pokazania już policzonego wyniku.
4. **Zapis wybranego rejonu do użycia bez zasięgu:** najprostsze rozwiązanie na pierwszą wersję to (a) link „otwórz w mapach” generowany dla punktu startowego (`geo:` URI / link do Google Maps lub OsmAnd z współrzędnymi — eksport do istniejącej aplikacji mapowej, zero dodatkowego kodu offline), (b) zapisanie wybranego rejonu (nazwa, opis, współrzędne, uzasadnienie) w `localStorage` przeglądarki na telefonie, żeby tekst i współrzędne były dostępne offline po pierwszym otwarciu strony, nawet bez zasięgu — to nie wymaga backendu, bo aplikacja jest prywatna i jednoosobowa. Pełny tryb offline z buforowanymi kafelkami mapy to osobna, droższa funkcja (Workbox/PWA) — **poza obecnym zakresem**, nie zakładać jej budowy, dopóki (a)+(b) okażą się niewystarczające w praktyce.

**Dlaczego nie backend on-demand:** jedyny scenariusz wymagający serwera to przycisk „Analizuj” klikany z telefonu w terenie — a to nie jest rzeczywisty scenariusz użycia (sekcja 0: analiza robiona przed wyjazdem, na komputerze, ze stabilnym łączem). Dodanie FastAPI tylko po to, żeby uniknąć jednego polecenia w terminalu, byłoby budową infrastruktury pod nieistniejącą potrzebę.

**Dlaczego MapLibre, a nie Leaflet czy OpenLayers (bez zmian):** 25–150 tys. poligonów płynnie działa tylko jako kafle wektorowe (WebGL). `feature-state` pozwala zmieniać kolory bez przebudowy kafli przy każdym uruchomieniu. PMTiles to jeden plik, bez tile servera.

### 7.3 Diagram

```
PC, uruchamiane ręcznie przed wyjazdem (0-3x / rok, nie harmonogram)
┌───────────────────────────────────────────────────────────────────────┐
│ `uv run python -m pipeline.prepare_trip --lat .. --lon .. --date ..`  │
│                                                                        │
│   BDL WFS ─┐  GDOŚ ─┐  OSM Overpass ─┐  Open-Meteo ─┐  BDL zakazy ─┐   │
│            ▼         ▼                ▼              ▼             ▼   │
│      cache kaflowy (GeoParquet) ── scoring (mask→H→F→P→R) ── rejony   │
│                                              │                        │
│                          ┌───────────────────┴──────────────┐         │
│                          ▼                                  ▼         │
│              stands.pmtiles (rzadko)          regions_{date}.json,   │
│                                                scores_{date}.json      │
└───────────────────────────┬───────────────────────────────────────────┘
                             ▼ (deploy tych samych plików, bez zmiany kodu)
                 hosting statyczny (Cloudflare Pages / GitHub Pages), koszt 0
                             ▼
                 telefon: ta sama strona, otwarta w przeglądarce
                 (rejon zapisany w localStorage = dostępny offline)

Poza obecnym zakresem: PostgreSQL + PostGIS, FastAPI, PWA offline z kafelkami,
harmonogram — patrz sekcja 16, 17.
```

---

## 8. Strategia danych i cache

*(Bez istotnych zmian względem wersji 1.0 — zasady poprawne niezależnie od częstotliwości użycia. Zaktualizowano opis realnego stanu w kodzie.)*

### 8.1 Obszar

Kafle 10×10 km w siatce PUWG 1992 (EPSG:2180) przecinające okrąg o promieniu R wokół punktu. Domyślnie **R = 25 km**, suwak 10–50 km. Promień jest tylko filtrem widoku, przetwarzanie zawsze idzie per kafel — zmiana promienia nie wymusza ponownego pobierania. **[K]** `pipeline/tiles.py` obsługuje tworzenie bboxów per kafel; prekomputowany region domowy i cache wielu kafli jednocześnie nie są jeszcze zaimplementowane (dziś jeden kafel na uruchomienie notebooka).

### 8.2 Cache

**Rekomendowana hybryda (bez zmian):**
- Statyczne/półstatyczne: cache kaflowy `cache/{layer}/{version}/{tile_id}.parquet`. **[K] Częściowo zaimplementowane** — `pipeline/bdl.py::save_bdl_tile` zapisuje i odczytuje z cache po `tile_id`; GDOŚ, OSM i zakazy nie mają dziś własnego cache (pobierane na żywo przy każdym uruchomieniu — do rozważenia przy rozbudowie, bo GDOŚ i granice lasu zmieniają się rzadko, ale nie jest to pilne przy 1–3 uruchomieniach rocznie).
- Pogoda: siatka ~5 km na aktywny obszar. **[K] Zaimplementowane** w `pipeline/weather.py`, choć bez trwałego cache dnia na dysku poza `requests_cache` (`.cache/open_meteo*`).
- WFS BDL: BBOX per kafel, stronicowanie, klucz `(tile_id, a_year)`. **[K] Zaimplementowane.**

### 8.3 Zasady odświeżania danych i działanie przy brakach

| Grupa | Warstwy | Zasada odświeżania | Stan |
|---|---|---|---|
| **STATIC** | GDOŚ (rezerwaty, PN) | pobierane przy każdym uruchomieniu (rzadkie zmiany, koszt niski) | [K] |
| **SEMI-STATIC** | BDL wydzielenia | z cache; odświeżyć po przekroczeniu ustalonego wieku (np. >12 miesięcy — do wyboru przy implementacji, dziś brak automatycznej reguły wieku, tylko obecność/brak pliku w cache) | częściowo [K] |
| | OSM (parkingi, drogi, miejscowości) | pobierane na żywo przy każdym uruchomieniu (Overpass) — brak cache | [K], bez wieku cache |
| | BDL zakazy wstępu | **zawsze sprawdzane przy analizie przed wyjazdem**, nigdy z cache — to jest wymóg bezpieczeństwa prawnego, nie tylko świeżości | [K] |
| **DYNAMIC** | Open-Meteo (archiwum + prognoza) | pobierane przy każdej analizie (nie codziennie w tle) | [K] |
| **Wyniki** | H, F, P, R, rejony | liczone przy każdym uruchomieniu `prepare_trip` | H/F/R [K], rejony do zrobienia |

**Zasada przy awarii źródła (do doprecyzowania w implementacji, dziś spójne tylko dla zakazów):**
- **Zakazy wstępu:** awaria zapytania **przerywa cały bieg** dla dotkniętych wydzieleń (fail-loud, już zaimplementowane w `pipeline/zakazy.py`). Brak odpowiedzi nie oznacza braku zakazu.
- **GDOŚ, BDL, Open-Meteo, OSM:** dziś każdy z tych klientów rzuca wyjątek sieciowy wprost (`raise_for_status()`), co i tak zatrzymuje cały bieg — zachowanie zgrubnie bezpieczne (nie pokazuje wyniku na niepełnych danych), ale nieinformacyjne (użytkownik dostaje surowy traceback, nie komunikat w rodzaju „BDL nie odpowiada, spróbuj ponownie za chwilę”). Poprawa komunikatu błędu jest zadaniem UX, nie logiki — do sekcji 13.
- **Zasada ogólna do zachowania przy każdej przyszłej zmianie:** brak odpowiedzi źródła nigdy nie ma cichego fallbacku na wartość neutralną w kontekście *maski prawnej*. Poza maską prawną (np. brak danych o gatunkach domieszkowych, brak dokładnej odległości drogowej) fallback na wartość neutralną z jawną adnotacją w `confidence`/`explanation` jest akceptowalny i już częściowo zaimplementowany (`unknown_host_affinity: 0.5`, `percentile_rank` → 0,5 przy pustym oknie klimatologii).
- **Daty aktualności w UI:** panel szczegółów wersji 1.0 (sekcja 10) już projektował pokazywanie źródeł i rozdzielczości; do rozbudowy o wprost widoczną datę pobrania każdej warstwy („BDL: rok danych 2026, pobrano dziś” / „pogoda: dziś 06:12”), żeby użytkownik wiedział, czy patrzy na świeże dane bez zaglądania w kod.

---

## 9. Interfejs — uproszczony scenariusz

### 9.1 Podstawowy scenariusz (cel: jeden prosty przepływ, bez wielu suwaków wag modelu)

1. Wybierz lokalizację (GPS / klik / wyszukiwarka), dzień wyjścia i zasięg poszukiwań (suwak promienia, domyślnie 25 km).
2. Określ, ile chcesz chodzić (np. suwak „max. dojście pieszo”, domyślnie 2 km) i jak ważne jest unikanie popularnych wejść (np. suwak trzystopniowy „nie zależy mi / trochę / bardzo” zamiast surowego α — pod spodem to nadal ten sam parametr modelu, ale nazwany po ludzku).
3. Uruchom analizę — po stronie użytkownika to kliknięcie „Analizuj” w lokalnie uruchomionym poleceniu/skrypcie z kroku 7.2, nie wywołanie sieciowe.
4. Wybierz jedną z 3–5 propozycji rejonów i zapisz potrzebne informacje na telefonie (sekcja 7.2 pkt 4).

**Nie dodawać** osobnych suwaków dla wag H (host/site/age), parametrów logistycznej funkcji M, sigmy temperatury itd. — to są parametry modelu do kalibracji technicznej (sekcja 15), nie decyzje, które użytkownik powinien podejmować przed każdym wyjazdem. Mają rozsądne wartości domyśle w profilu YAML.

### 9.2 Główny widok: lista/mapa rejonów

Dla każdego z 3–5 proponowanych rejonów, karta zawierająca:

```
REJON 2 z 4 · okolice Nadl. Człopa                         Ranking: wysoki w obszarze
Warunki: DOBRE (klasa F) · Pewność: ŚREDNIA ▸ dlaczego?

[mapa: obrys rejonu na tle wydzieleń, punkt startowy]

Start: parking leśny przy drodze XYZ          [potwierdzony ✓ / niepotwierdzony ⚠]
Dojazd: 22 km, ~25 min · Dojście: 900 m pieszo (oszacowanie po drogach / w linii prostej — oznaczone)
Szacowana popularność: NISKA/ŚREDNIA/WYSOKA (nie pomiar tłoku — przesłanki: ... )

Dlaczego ten rejon:
  ▲ sosna i bór mieszany świeży na większości wydzieleń (siedlisko dobre)
  ▲ opad z ostatnich ~4 tygodni powyżej normy dla tej pory roku
  ▼ brak danych o domieszkach gatunkowych

Siedlisko (H): dobre · Warunki teraz (F): dobre                [zobacz szczegóły ▸]
Dane aktualne na: BDL 2026, pogoda dziś 06:12, zakazy sprawdzone dziś

[Zapisz rejon]  [Nawiguj do startu]  [Zobacz wydzielenia w rejonie ▸]
```

Pola wymagane (per instrukcja): rejon na mapie, punkt startowy ze statusem weryfikacji, orientacyjne dojście z informacją czy po drogach czy oszacowane, krótkie uzasadnienie, osobna ocena H i F, informacja o aktualności/niepewności, zapis i nawigacja. **Wszystko powyżej to specyfikacja do zaimplementowania** — dziś istnieje tylko jako dane (JSON) bez żadnej warstwy prezentacji.

**Baner regionalny u góry (bez zmian z wersji 1.0):** „Warunki w obszarze: DOBRE (opad 26 dni: 78. percentyl, Tśr 20 dni: 12,4°C)” — odpowiedź na „czy w ogóle jechać”, pokazywana zawsze razem z rankingiem względnym (sekcja 5.7).

### 9.3 Widok dodatkowy: wydzielenia i szczegóły modelu

Zachowuje panel szczegółów z wersji 1.0 (numer wydzielenia, S_host/S_site/S_age, rozbicie F, presja, wyjaśnienia log-wkładów, źródła i rozdzielczość) — przeniesiony do widoku „Zobacz wydzielenia w rejonie”, nie na główny ekran. Osoby, które chcą zobaczyć surowy model, mogą; domyślny ekran ich tym nie obciąża.

---

## 10. Niepewność

*(Bez zmian merytorycznych — struktura trzech wskaźników jest niezależna od częstotliwości użycia.)*

**1. Data quality (per wydzielenie, 0–1)** — iloczyn: kompletność drzewostanu (1,0 pełny skład LMN — nieosiągalne w obecnym zakresie / **0,7 tylko gatunek panujący WFS** — dzisiejszy stan / 0,3 brak BDL); świeżość BDL (1,0 brak sygnału zmiany S2 — dziś zawsze 1,0, bo S2 nie jest podłączone, więc to pole nie odróżnia realnie świeżych i nieaktualnych danych, patrz zastrzeżenie sekcja 15); pogoda (0,8 NWP ~2 km — dzisiejszy stan przez Open-Meteo).

**2. Model confidence (globalne):** **maks. „ŚREDNIA”**, bo model jest ekspercki i nieskalibrowany. **[K] Zaimplementowane jako stały pułap** w `profiles/boletus_edulis.yaml` (`model_confidence_cap: "SREDNIA"`). Pozostaje tak, dopóki nie ma kalibracji na danych terenowych (sekcja 16) — realistycznie może pozostać tak na stałe, i to jest w porządku (sekcja 15).

**3. Resolution disclosure:** lista źródeł z ich rozdzielczością przy każdym wyniku.

**Finalny confidence** = min(klasa z data quality, klasa modelu), NISKA/ŚREDNIA/WYSOKA z listą powodów. **[K] Zaimplementowane** w `pipeline/confidence.py`.

---

## 11. Ograniczenia skuteczności rekomendacji

To, co system może i czego nie może obiecać — do pokazania użytkownikowi wprost, nie tylko trzymania w dokumentacji projektowej:

1. **Wynik nie jest zweryfikowaną skutecznością.** Model jest złożeniem priorów eksperckich i ogólnej literatury mykologicznej (w większości nie z polskich borów sosnowych — patrz sekcja 2), nie modelem dopasowanym do żadnych obserwacji z Twojego regionu. Poprawność techniczna pipeline'u (dane się pobierają, ranking się liczy, testy przechodzą) **nie jest tym samym co zweryfikowana skuteczność przewidywania grzybów** — to dwa osobne twierdzenia, i dokument nie oznacza drugiego jako sprawdzone tylko dlatego, że sprawdzone jest pierwsze.
2. **Brak realistycznej ścieżki walidacji na znanych miejscówkach** (sekcja 0, 6, 13) — użytkownik ich nie zna. Możliwa do wykonania weryfikacja bez tej wiedzy: (a) techniczna poprawność danych — czy wydzielenia, siedliska i wiek zgadzają się z tym, co widać na mapie BDL/w terenie przy pierwszym wyjeździe; (b) sensowność rankingu — czy top rejony różnią się realnie siedliskiem/pogodą od dołu rankingu, a nie tylko szumem; (c) dostępność terenowa — czy zaproponowany punkt startowy i dojście faktycznie istnieją i są przejezdne/przechodne. Żadne z tych trzech nie potwierdza, że w rekomendowanych miejscach faktycznie rosną prawdziwki częściej niż gdzie indziej — to wymagałoby obserwacji terenowych, których projekt świadomie nie zakłada jako obowiązkowych (sekcja 16).
3. **„Top 5%” to ranking względny, nie gwarancja dobrych warunków** — patrz sekcja 5.7.
4. **Presja/popularność to szacunek, nie pomiar** — patrz sekcja 5.5.2.
5. **Fruiting F ma słabe podstawy naukowe nawet dla dobrze zbadanych populacji** (10 lat monitoringu w Niemczech dało tylko ogólne prawidłowości, sekcja 1 pkt 2) — dla Polski, gdzie nie ma analogicznych badań, F trzeba traktować jako grubą wskazówkę „czy w ogóle warto jechać w tym tygodniu”, nie jako precyzyjne okno.
6. **Model prawdopodobnie nigdy nie zostanie skalibrowany danymi terenowymi** przy realnym tempie 1–3 wyjazdów rocznie — sekcje GLM/occupancy/LightGBM z wersji 1.0 (dziś sekcja 16) pozostają teoretyczną możliwością, nie planem z terminem.

---

## 12. Zakres pierwszej użytecznej wersji

**Pytanie, na które odpowiada:** „Gdzie w promieniu ~20–25 km mam dziś największą szansę na dobre warunki dla prawdziwków, i gdzie jest z tego mało ludzi?” — z odpowiedzią w postaci 3–5 konkretnych rejonów z punktem startowym, a nie tabeli wydzieleń.

**Źródła (bez zmian względem MVP wersji 1.0, wszystkie już podłączone [K]):**
1. BDL WFS — wydzielenia.
2. Open-Meteo — archiwum + prognoza + klimatologia.
3. GDOŚ — rezerwaty i parki narodowe (maska).
4. BDL ArcGIS zakazy wstępu — okresowe zakazy, sprawdzane przed każdą analizą.
5. OSM (Overpass) — parkingi, drogi, miejscowości.
6. GBIF — do podłączenia realnie (dziś G_season zahardkodowane na 1,0, sekcja 5.4 pkt 1) → fenologia.

**Czego pierwsza użyteczna wersja NIE robi:** NMT, Sentinel, radar, SWI, ML, konta użytkowników, natywna aplikacja mobilna, pełny routing sieciowy dla wszystkich wydzieleń (tylko dla top-N kandydatów), pełny tryb offline z kafelkami mapy.

**Zakres prac do „pierwszej użytecznej wersji” (uzupełnienie ponad to, co już działa — szczegóły i kolejność w sekcji 13):**
1. Grupowanie wydzieleń w rejony (sekcja 5.6).
2. Rozbudowa oceny dostępności/popularności o potencjalne wejścia, zabudowę przy granicy lasu, routing dla top kandydatów (sekcja 5.5.2).
3. Parametryzowalne, jednopoleceniowe uruchomienie `prepare_trip` (sekcja 7.2).
4. Minimalny frontend (mapa + lista rejonów + panel szczegółów wydzielenia), wdrożony na darmowy hosting statyczny.
5. Podłączenie realnego G_season z GBIF zamiast stałej 1,0.
6. Zapis rejonu + link nawigacji + `localStorage` na telefonie.

---

## 13. Dalsze kroki — priorytety i kryteria ukończenia

| Priorytet | Krok | Dlaczego teraz | Kryterium ukończenia (mierzalne) |
|---|---|---|---|
| **1** | Grupowanie w rejony (5.6) | Bez tego główny wynik nadal jest tabelą wydzieleń, co wprost sprzeczne z celem projektu (sekcja 0) | Dla realnego kafla 10×10 km, top wydzielenia grupują się w ≤5 rejonów, żaden rejon nie jest wyłącznie fragmentem tego samego kompleksu co inny wynik top-5; test jednostkowy na syntetycznym zestawie wydzieleń z dwoma odległymi klastrami sprawdza, że każdy klaster trafia do osobnego rejonu |
| **2** | `prepare_trip` — parametryzacja i jedno polecenie (7.2) | Bez tego nie da się użyć aplikacji dla innej lokalizacji niż zahardkodowana w `notebooks/02_mvp.py` | Jedno wywołanie CLI z `--lat/--lon/--date/--radius-km` produkuje `regions_{date}.json` i `scores_{date}.json` dla dowolnej lokalizacji w Polsce bez edycji kodu |
| **3** | Rozbudowa dostępności/popularności (5.5.2): potencjalne wejścia z sieci dróg, flaga potwierdzone/niepotwierdzone, routing dla top-N | Bezpośrednio adresuje cel „mało ludzi”, dziś oparty tylko na odległości euklidesowej do parkingu | Dla top 20–30 wydzieleń policzona odległość po sieci dróg (nie euklidesowa); w danych i UI widoczne rozróżnienie „potwierdzone wejście” / „potencjalne wejście”; test jednostkowy pokrywa oba przypadki |
| **4** | Minimalny frontend (mapa rejonów + panel szczegółów) | Bez tego wynik istnieje tylko jako JSON w terminalu | Strona otwarta lokalnie w przeglądarce pokazuje ≥1 rejon na mapie z polami z sekcji 9.2, zbudowana z realnych danych z kroku 1–3 |
| **5** | Wdrożenie na hosting statyczny + telefon (7.2 pkt 3) | Domyka scenariusz „uruchamiam na komputerze, patrzę na telefonie” | Ta sama strona otwiera się na telefonie pod stałym adresem po jednym poleceniu na komputerze, bez ręcznego kopiowania plików |
| **6** | Zapis rejonu + link nawigacji + `localStorage` (7.2 pkt 4, 9.2) | Domyka scenariusz użycia bez zasięgu w terenie | Po zapisaniu rejonu i wyłączeniu Wi-Fi/danych, nazwa, współrzędne i uzasadnienie rejonu są nadal widoczne w przeglądarce na telefonie; link nawigacji otwiera zainstalowaną aplikację mapową z poprawnymi współrzędnymi |
| **7** | Podłączenie realnego G_season z GBIF | Dziś F liczy się bez modulacji fenologicznej (stała 1,0) — cichy błąd, nie tylko brakująca funkcja | `compute_fruiting` w realnym biegu dostaje G_season różne od 1,0 zależnie od dnia roku; test regresyjny porównuje wynik dla dnia w szczycie sezonu i poza sezonem |
| **8** | Komunikaty błędów źródeł danych (8.3) | Dziś awaria źródła kończy się surowym tracebackiem, nie komunikatem dla użytkownika | Sztuczna awaria każdego z 5 źródeł (mock zwracający błąd HTTP) kończy bieg czytelnym komunikatem wskazującym, które źródło zawiodło i że wynik nie został pokazany |
| — | (poza priorytetami 1–8, do rozważenia dopiero po ich ukończeniu) | | |
| 9 | Daty aktualności widoczne w UI (8.3) | Drobne UX, niezależne od reszty | Każda warstwa w panelu szczegółów pokazuje datę/wiek danych |
| 10 | Bariery (rzeki, ogrodzenia) w ocenie dostępności (5.5.2) | Wymaga dodatkowego źródła (cieki wodne), niepewna wartość dodana bez danych terenowych | Zdefiniowane dopiero po przetestowaniu priorytetu 3 w praktyce |
| 11 | Cache dla GDOŚ/OSM/zakazów (8.2) | Nie pilne przy 1–3 uruchomieniach rocznie | Odłożone, chyba że czas jednego uruchomienia okaże się w praktyce niewygodnie długi |

---

## 14. Celowo pominięte w pierwszej wersji

- **Siatka 10–50 m i heatmapa** (fałszywa precyzja); zamiast nich wielokąty wydzieleń i obrysy rejonów.
- **Codzienny harmonogram** (Task Scheduler / GitHub Actions cron) — analiza uruchamiana ręcznie przed wyjazdem (sekcja 0, 7).
- **Obowiązkowy dziennik obserwacji, protokół eksploracji terenowej, trening modeli ML** — przeniesione do sekcji 16 jako w pełni opcjonalne.
- **PostGIS, FastAPI, konta użytkowników, crowdsourcing, aplikacja natywna** — niepotrzebne bez wielu użytkowników i regularnych obserwacji terenowych.
- **Pełny routing sieciowy dla wszystkich wydzieleń w kaflu** — tylko dla top-N kandydatów (sekcja 5.5.2), reszta zostaje na przybliżeniu euklidesowym.
- **Pełny tryb offline z buforowanymi kafelkami mapy (PWA/Workbox)** — na start wystarcza link do istniejącej aplikacji mapowej + zapis tekstowy w `localStorage` (sekcja 7.2).
- **Sentinel-1 i własne przetwarzanie wilgotności z SAR, CLMS SWI, NDVI/NDMI jako predyktor owocnikowania, LST, LAI, VPD, SoilGrids pH, GPM IMERG, H SAF** — patrz sekcja 17.
- **NMT i pochodne terenowe** — poza zakresem, chyba że obszar poszukiwań jest górski (patrz sekcja 3.6).
- **GBIF/iNat jako dane lokalizacyjne** (tylko fenologia).
- **Scraping czegokolwiek** (popupy BDL, Strava, fora).
- **Sześć skorelowanych okien opadowych jako osobne cechy** (jedno okno ważone + percentyle).
- **Pełna historia zabiegów leśnych** (brak w publicznych danych).

---

## 15. Poza obecnym zakresem: ciągła obserwacja i ML (w pełni opcjonalne)

**Zasada:** aplikacja musi być użyteczna bez ani jednego wpisu w dzienniku. Nic poniżej nie jest wymagane do działania systemu opisanego w sekcjach 5–12.

### 15.1 Opcjonalny dziennik

Jeśli kiedyś zechcesz go prowadzić, ma być prosty: **data, miejsce, „nic / trochę / dużo”, notatka, ewentualnie punkt znaleziska.** To wszystko — bez formularzy badawczych, bez klasyfikacji stanu owocników, bez śladów presji, bez rejestrowania wysiłku szukania. Rozbudowane pola z wersji 1.0 (stan owocników młode/dojrzałe/stare/robaczywe, ślady presji, warunki szukania w skali 1–3) zostają opisane niżej jako **materiał referencyjny na wypadek, gdyby kiedyś powstała realna potrzeba kalibracji**, nie jako specyfikacja czegoś do zbudowania teraz.

### 15.2 Materiał referencyjny z wersji 1.0 (bez zmian treści, oznaczony jako nieaktywny)

Poniższe punkty opisują, jak wyglądałby pełny schemat zbierania danych do kalibracji modelu, **gdyby** kiedyś powstała ku temu potrzeba i możliwość (np. zmiana trybu użycia na częstszy). Nie jest to plan z terminem.

1. Jednostką obserwacji byłaby *wizyta w wydzieleniu z wysiłkiem*, nie znalezisko — wyprawa (track GPS) cięta na wizyty (wyprawa × wydzielenie); wizyta bez znalezisk to pełnoprawna obserwacja z wynikiem 0.
2. Zapisywane byłyby wszystkie znalezione gatunki grzybów, nie tylko borowiki, żeby rozdzielić „las nie owocnikuje” od „las owocnikuje, ale nie dla borowika”.
3. Eksploracja: ok. 15–20% wizyt w miejscach, których model *nie* poleca, żeby uniknąć pętli sprzężenia zwrotnego. Przy 1–3 wyjazdach rocznie oznaczałoby to jeden „marnowany” wyjazd na kilka lat — świadomy koszt, nie coś do egzekwowania teraz.
4. Modele w kolejności rosnącej złożoności: GLM Poisson/NegBin z offsetem (od ~100 wizyt) → occupancy dynamiczny (od ~2 sezonów) → GAM/LightGBM (od setek wizyt, ≥2 regiony). Przy realnym tempie zbierania danych próg 100 wizyt oznacza dziesiątki lat.
5. Zasady unikania leakage (czasowego, przestrzennego, historią) i biasu obserwacyjnego pozostają poprawne, gdyby kiedyś dane zaczęto zbierać — nie ma potrzeby ich zmieniać, tylko nie są dziś aktualne.

**Narzędzia terenowe, gdyby dziennik miał kiedyś powstać:** zwykły arkusz albo prosty plik tekstowy wystarczy na start (pole „data, miejsce, nic/trochę/dużo, notatka”); QField/Mergin Maps dopiero, gdyby prowadzenie dziennika stało się rzeczywistą, powtarzającą się praktyką.

---

## 16. Dalsze źródła danych poza zakresem

*(Bez zmian względem wersji 1.0 poza jaśniejszym oddzieleniem od planu wdrożenia — nic poniżej nie jest krokiem w sekcji 13.)*

- Całoroczne archiwizowanie radaru i telemetrii IMGW (sekcja 3.3) — wymaga stale działającej infrastruktury, sprzecznej z zasadą „uruchamiane przed wyjazdem” (sekcja 0).
- Sentinel i automatyczne wykrywanie zmian drzewostanu (sekcja 3.5).
- LiDAR, CHM i rozbudowane modelowanie terenu (sekcja 3.6).
- Własny model bilansu wodnego („wiadro”) per siedlisko (sekcja 3.4) — CWB26 z Open-Meteo już działa jako prostsza wersja tego samego pomysłu.
- Dodatkowe bazy danych i systemy orkiestracji (Prefect/Dagster) — niepotrzebne bez wielu źródeł wymagających koordynacji w czasie.

**Zasada przywracania:** przywrócenie którejkolwiek z tych funkcji powinno wynikać z konkretnego problemu, którego prostsze rozwiązanie (już zaimplementowane) nie rozwiązuje — nie z tego, że dana funkcja wygląda atrakcyjnie w dokumencie.

---

## 17. Koszty, limity, licencje

*(Bez zmian względem wersji 1.0.)*

| Źródło | Koszt | Limity | Licencja / uwagi |
|---|---|---|---|
| BDL (WFS/WMS/OGC API) | 0 | brak publikowanych; grzecznie: 1 równoległe zapytanie, cache | dane publiczne; podawać źródło „Bank Danych o Lasach” |
| GUGiK (NMT, NMPT, LiDAR, BDOT10k) | 0 (od 2020) | WCS: wycinki; masowo arkusze | podać źródło |
| IMGW-PIB | 0 | brak historii w API | wymagana formuła atrybucji — sprawdzić dokładne brzmienie w regulaminie, jeśli kiedyś podłączone |
| **Open-Meteo** | 0 **niekomercyjnie** | <10 000 wywołań/dobę, <5 000/h, <600/min | CC BY 4.0. Przy komercjalizacji potrzebny plan płatny albo self-hosted. Nieaktualne dla aplikacji prywatnej, ale zapisane na przyszłość. |
| Copernicus (CLMS, CDSE, ERA5) | 0 | CDSE: Sentinel Hub 10 000 PU/mies., openEO 10 000 kredytów/mies. | pełny i otwarty dostęp; atrybucja |
| Earth Search / Planetary Computer | 0 | fair use | dane Sentinel otwarte |
| OSM (Overpass) | 0 | nie masowo, lepiej Geofabrik PBF przy dużej skali | **ODbL: jeśli publikujesz bazę pochodną, obowiązuje share-alike** — nieaktualne dla prywatnej aplikacji |
| GBIF / iNaturalist | 0 | API: rozsądnie | licencje per rekord, część CC BY-NC |
| GDOŚ | 0 | | dane publiczne |
| Hosting | 0 (statyczny hosting: Cloudflare Pages / GitHub Pages) | | wystarcza dla prywatnej, jednoosobowej aplikacji — patrz sekcja 7.2 |
| Mapa podkładowa | 0 (OpenFreeMap / własne PMTiles Protomaps) | | |

**Ryzyko prawne i etyczne (bez zmian):** publiczna strona z „najlepszymi miejscami na prawdziwki” może zwiększyć presję na konkretne wydzielenia. **Aplikacja pozostaje prywatna.**

---

## 18. Technologie

| Warstwa | Stan | Uwagi |
|---|---|---|
| Język / env | **[K]** Python 3.12, `uv` | |
| GIS | **[K]** GeoPandas, Shapely 2, pyogrio, pyproj, scipy | Rasterio/rioxarray/xarray niepotrzebne bez NMT/S2 (sekcja 3.5–3.6) |
| Przechowywanie | **[K]** GeoParquet (`cache/`) | DuckDB spatial nie jest dziś używane bezpośrednio mimo wzmianki w architekturze wersji 1.0 — GeoPandas wystarcza na obecną skalę (jeden kafel na uruchomienie) |
| Pogoda | **[K]** `openmeteo-requests`, `requests-cache`, `retry-requests` | |
| OSM | **[K]** `requests` + ręczne zapytanie Overpass (nie `pyrosm`/`osmium`) | wystarczające dla parkingów/dróg/miejscowości; routing dla top-N (priorytet 3, sekcja 13) będzie wymagał dodatkowej biblioteki grafowej lub lekkiego własnego grafu z odpowiedzi Overpass |
| Kafle | Nie zaimplementowane | `tippecanoe` → PMTiles, priorytet dopiero po frontendzie (sekcja 12, 13) |
| Frontend | Nie zaimplementowane | Vite + TypeScript + MapLibre GL JS + `pmtiles`, priorytet 4 (sekcja 13) |
| Backend | Brak (zgodnie z zasadą, sekcja 7.1) | |
| Orkiestracja | Brak (niepotrzebna, sekcja 0/7.2) | |
| Jakość | **[K]** `pytest` (144 testy), `responses` do mockowania HTTP w testach | `pandera` wymieniane w wersji 1.0, nie znaleziono w zależnościach — do usunięcia z listy lub dodania, jeśli faktycznie potrzebne |

---

## 19. Schemat bazy danych (opcjonalny, dopiero jeśli powstanie warstwa obserwacji)

Poniższy schemat SQL jest materiałem referencyjnym z wersji 1.0 na wypadek, gdyby kiedyś powstała potrzeba PostGIS (sekcja 15/16) — **w obecnym zakresie dane żyją jako GeoParquet + JSON w `cache/` i `notebooks/output/`, bez bazy danych.**

```sql
-- ===== referencyjne / wersjonowanie =====
CREATE TABLE data_source (
  source_id     text PRIMARY KEY,
  version       text NOT NULL,
  fetched_at    timestamptz NOT NULL,
  spatial_res_m int,
  licence       text,
  attribution   text
);

CREATE TABLE tile (
  tile_id  text PRIMARY KEY,
  geom     geometry(Polygon, 2180) NOT NULL
);

-- ===== las =====
CREATE TABLE stand (
  stand_id     text PRIMARY KEY,
  adr_for      text NOT NULL,
  a_year       int  NOT NULL,
  nadl_name    text,
  area_type    text,
  site_type    text,
  fertility    text,
  moisture_cls smallint,
  species_cd   text,
  part_cd      smallint,
  spec_age     int,
  stand_stru   text,
  prot_categ   text,
  sub_area_ha  numeric,
  source       text REFERENCES data_source,
  geom         geometry(MultiPolygon, 2180) NOT NULL
);
CREATE INDEX ON stand USING gist (geom);

CREATE TABLE stand_species (
  stand_id text REFERENCES stand, storey text, species_cd text,
  share_tenths smallint, age int, height_m numeric,
  PRIMARY KEY (stand_id, storey, species_cd)
);

CREATE TABLE stand_static_features (
  stand_id        text PRIMARY KEY REFERENCES stand,
  s_host numeric, s_site numeric, s_age numeric, h_score numeric,
  legal_mask      boolean, mask_reason text,
  d_parking_m     int, d_road_m int, demand_idx numeric, p_score numeric,
  region_id       text,                                                     -- nowość: przynależność do rejonu
  entrance_status text,                                                     -- nowość: 'confirmed' / 'potential'
  twi_median numeric, twi_p75_share numeric, slope_deg numeric, aspect_deg numeric,
  s2_change_flag  boolean, s2_change_year int,
  weather_cell_id text,
  data_quality    numeric,
  computed_at     timestamptz
);

CREATE TABLE region (                                                        -- nowość, sekcja 5.6
  region_id text PRIMARY KEY, day date, profile text,
  geom geometry(MultiPolygon, 2180) NOT NULL,
  rank_score numeric,                                                        -- mediana top-N wydzieleń, nie suma
  start_point geometry(Point, 4326), start_point_status text,               -- 'confirmed' / 'estimated'
  access_note text, confidence text
);

-- ===== pogoda =====
CREATE TABLE weather_cell (
  cell_id text PRIMARY KEY, source text, res_m int,
  geom geometry(Point, 4326)
);
CREATE TABLE weather_daily (
  cell_id text REFERENCES weather_cell, day date,
  p_mm numeric, tmean numeric, tmin numeric, tmax numeric,
  et0_mm numeric, vpd_kpa numeric, sm_9_27 numeric,
  is_forecast boolean, source text,
  PRIMARY KEY (cell_id, day, source)
);
CREATE TABLE weather_features (
  cell_id text, day date,
  p1 numeric, p3 numeric, p7 numeric, p14 numeric, p21 numeric, p30 numeric,
  p26w numeric, cwb26 numeric, tmean5 numeric, tmean20 numeric, tmin3 numeric,
  days_since_p10 int, dry_spell_days int,
  pct_p26w numeric, pct_cwb26 numeric, pct_sm numeric,
  PRIMARY KEY (cell_id, day)
);

-- ===== wyniki =====
CREATE TABLE score_daily (
  stand_id text, day date, profile text,
  h numeric, f numeric, f_loc numeric, p numeric, r numeric,
  f_class smallint, rank_pct numeric,
  confidence text, confidence_reasons jsonb,
  explanation jsonb,
  model_version text,
  PRIMARY KEY (stand_id, day, profile)
);

-- ===== obserwacje terenowe (opcjonalne, sekcja 15) =====
CREATE TABLE trip (
  trip_id uuid PRIMARY KEY, observer text, start_ts timestamptz, end_ts timestamptz,
  track geometry(LineStringZ, 4326),
  notes text
);
CREATE TABLE visit (
  visit_id uuid PRIMARY KEY, trip_id uuid REFERENCES trip, stand_id text,
  result text,                                                              -- 'nic' / 'trochę' / 'dużo' (sekcja 15.1)
  notes text,
  find_point geometry(Point, 4326)
);
```

---

## 20. Największe ryzyka

1. **Model fruiting po prostu się myli.** Wiedza o krótkoterminowych wyzwalaczach *B. edulis* jest słaba [L1]. *Mitygacja:* klasy zamiast liczb, baner regionalny, jawne „nieskalibrowany” (sekcja 11).
2. **Priory siedliskowe nie pasują do Twojego regionu.** *Mitygacja:* techniczna weryfikacja poprawności danych i rankingu przy pierwszych wyjazdach (sekcja 11 pkt 2), bez złudzeń, że to potwierdza skuteczność.
3. **Za mało danych, żeby kiedykolwiek skalibrować model.** *Mitygacja:* zaakceptowane wprost jako trwały stan rzeczy (sekcja 15), nie problem do rozwiązania.
4. **Zmiany drzewostanu od ostatniej aktualizacji BDL** (zręby, kornik) niewykrywane bez S2 (poza zakresem). *Mitygacja:* jawna informacja o roku danych BDL w UI (sekcja 8.3 priorytet 9).
5. **Zmiana API** (BDL, IMGW, Open-Meteo, Overpass zmieniają endpointy). *Mitygacja:* warstwa adapterów już istnieje (`pipeline/*.py` z `call_api` jako punkt wstrzyknięcia), testy z mockami HTTP.
6. **Prawo i etyka:** polecanie terenów objętych zakazem. *Mitygacja:* maska obowiązkowa z fail-loud (sekcja 5.2), aplikacja prywatna.
7. **Scope creep:** wiele źródeł kusi. *Mitygacja:* sekcja 13 ma priorytety 1–8 i jawnie odkłada resztę (sekcja 14, 16, 17); żadna nowa warstwa bez konkretnego problemu, którego istniejące rozwiązanie nie rozwiązuje.
8. **Nowość — presja jako dominujący czynnik rankingu**, jeśli rozbudowa dostępności (priorytet 3) źle dobierze wagi. *Mitygacja:* sprawdzenie rozkładu P na realnych danych przed wdrożeniem, tak jak już raz zrobiono przy `track` w `pipeline/osm.py` (sekcja 5.5.2).

---

## Źródła (zweryfikowane w poprzednich sesjach)

- BDL — usługi OGC: https://www.bdl.lasy.gov.pl/portal/uslugi-ogc · WFS: https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows · OGC API: https://ogcapi.bdl.lasy.gov.pl
- IMGW-PIB dane publiczne: https://danepubliczne.imgw.pl/ (API `/api/data/synop`, `/api/data/meteo`, `/api/data/product`), regulamin: https://danepubliczne.imgw.pl/regulations
- Open-Meteo, warunki: https://open-meteo.com/en/terms
- CLMS Soil Water Index 1 km v2: https://land.copernicus.eu/en/products/soil-moisture/daily-soil-water-index-europe-1km-v2 · SSM 1 km: https://land.copernicus.eu/en/products/soil-moisture/daily-surface-soil-moisture-v1.0
- CDSE Sentinel Hub / openEO, limity: https://dataspace.copernicus.eu/ecosystem/services/sentinel-hub · https://documentation.dataspace.copernicus.eu/APIs/openEO/credit_usage.html
- GUGiK NMT WCS: https://geoforum.pl/news/30590/gugik-udostepnia-numeryczny-model-terenu-przez-wcs · https://www.gov.pl/web/gugik/nowa-usluga-wms-umozliwiajaca-pobieranie-nmt-o-interwale-siatki-5-m
- GBIF API (zapytania dla PL, taxonKey 5954958): https://api.gbif.org/v1/occurrence/search
- [L1] Brejon Lamartinière & Hoffman, *Predicting porcini…* (bioRxiv): https://www.biorxiv.org/content/10.64898/2025.12.12.693895v2 · dane: https://zenodo.org/records/17881340
- [L2] Martínez-Peña et al. 2012: https://www.researchgate.net/publication/237836204
- [L3] Tahvanainen et al. 2016: https://www.sciencedirect.com/science/article/abs/pii/S0378112715006751
- [L4] Stojek et al. 2022: https://www.sciencedirect.com/science/article/pii/S0378112722004455
- [L5] Collado et al. 2020: https://uvadoc.uva.es/bitstream/handle/10324/73839/Primary-productivity-and-climate-control-mushroom-_2020_Agricultural-and-For.pdf · Karavani et al. 2018: https://www.sciencedirect.com/science/article/abs/pii/S0168192317303441
- [L6] Italian J. Mycology: https://italianmycology.unibo.it/article/view/16464
