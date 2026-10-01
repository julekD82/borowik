# Borowik szczegółowy opis aplikacji i jej walidacji

Dokument do analizy i planowania ulepszeń przez AI

Stan przeglądu: 27 września 2026 roku. Wersja kodu: `111ce2e9e4df5bf6453723a5a45e2d4243744f42`. Autor opracowania: Codex na podstawie lokalnego kodu, konfiguracji, dokumentacji rozwoju i zapisanych wyników.

## 1 Najważniejsze ustalenia

Borowik jest lokalną aplikacją wspierającą wybór lasów do poszukiwania prawdziwków. Łączy charakterystykę drzewostanu z pogodą, sezonowością, ograniczeniami przestrzennymi oraz przybliżoną dostępnością dla innych odwiedzających. Wynikiem jest ranking wydzieleń leśnych i do pięciu niewielkich rejonów poszukiwań. Dodatkowy panel przedstawia warunki na siedem dni oraz informacje o ostatnich większych deszczach.

To deterministyczny model ekspercki. Aplikacja nie wykorzystuje wytrenowanej sieci neuronowej, modelu językowego ani klasyfikacji zdjęć grzybów. Wagi i progi zapisano w konfiguracji oraz kodzie. Nie przewiduje liczby owocników, kilogramów zbioru ani prawdopodobieństwa udanego wyjazdu. Wynik R = 80 nie oznacza 80% szans na znalezienie borowików.

Najlepiej udokumentowany wynik biologiczny to średnia pozycja dnia rzeczywistego znaleziska wśród dni porównawczych: 0,626 dla wariantu pogodowego bez krzywej sezonowej, na 90 obserwacjach GBIF. To częściowe sprawdzenie zależności czasowej. Nie waliduje jakości wyboru wydzieleń, siedliska H, presji P ani całego rankingu R. Nie istnieje udokumentowana, niezależna terenowa miara skuteczności całej aplikacji. [S01, S02, S13]

Radar poprawił zgodność opadów z czterema lokalnymi stacjami w krótkim porównaniu. Nie oznacza to automatycznie równie dużej poprawy trafności miejsc grzybowych. Model fazy wysypu po deszczu został przetestowany, wypadł gorzej niż punkt odniesienia i nie został wdrożony. Obecne kafelki siedmiodniowe korzystają z istniejącego wskaźnika F, a nie z odrzuconego modelu fal. [S12–S16]

W dostępnym eksporcie z 27.09.2026 jest 4703 wydzieleń, z czego 3656 przechodzi maskę. Aż 3648 z tych 3656 ma etykietę „Bardzo dobre”. Wszystkie kwalifikujące się wydzielenia w tym eksporcie mają skład drzew określony jako `wfs`, nie `paczka`. Funkcja pełnego składu BDL istnieje w kodzie, lecz nie została użyta w tym konkretnym wyniku. To istotne rozróżnienie między możliwościami aplikacji a faktycznie wykorzystanymi danymi. [S17]

## 2 Jak rozumieć dowody w dokumencie

**Implementacja** oznacza zachowanie wynikające z odczytanego kodu i konfiguracji. **Wynik zapisany** oznacza liczbę ponownie wyliczoną z lokalnego eksportu, bez ponownego pobierania danych. **Wynik historyczny** pochodzi z notatek o wcześniejszych uruchomieniach; w tym przeglądzie nie odtwarzano całego eksperymentu. **Hipoteza do sprawdzenia** jest wnioskiem z analizy, a nie potwierdzonym błędem terenowym. **Propozycja** nie jest częścią działającej aplikacji.

Kolejność wiarygodności przy ustalaniu obecnego działania: kod i aktywny profil, następnie aktualny eksport, następnie najnowsze notatki przekazania, na końcu starsze specyfikacje i plany. Starsze dokumenty zawierają opisy funkcji już zmienionych. Ten dokument opisuje stan zastany; nie zmienia modelu ani danych aplikacji.

Oznaczenia [S01]–[S22] prowadzą do mapy źródeł w rozdziale 20. Ścieżki są podane względem katalogu projektu, aby dokument pozostawał użyteczny po przeniesieniu na inny komputer. Nie są to odwołania do niezweryfikowanych odpowiedzi AI z innych rozmów. Zewnętrzne źródła danych opisano jako źródła wykorzystywane przez kod; ich bieżącej dostępności nie testowano ponownie w internecie.

## 3 Cel zakres i sposób użycia

### 3.1 Pytania na które aplikacja odpowiada

Aplikacja porządkuje miejsca według pytania „które dostępne w danych lasy w zadanym promieniu warto rozważyć”. Wydzielenie jest administracyjnym wielokątem BDL, a nie jednorodnym płatem grzybni. Rejon jest zbiorem wysoko ocenionych wydzieleń położonych blisko siebie. Część pogodowa odpowiada na pytanie o sprzyjające warunki, nie o wiek konkretnych owocników.

Profil nosi nazwę „prawdziwki (grupa Boletus edulis)”, natomiast statystyki GBIF pobierano dla nazwy `Boletus edulis`. Rozbieżność pomiędzy szeroką grupą użytkową a pojedynczą nazwą taksonomiczną jest ograniczeniem interpretacji sezonowości i walidacji. W repozytorium znajduje się jeden główny profil gatunkowy. [S01, S13]

### 3.2 Uruchamianie

Launcher Windows jest napisany w Pythonie z Tkinter. Uruchamia obliczenia, synchronizuje pliki wynikowe i otwiera lokalny interfejs w przeglądarce. Frontend to TypeScript, Vite i MapLibre, bez własnego serwera API modelu i bez kont użytkowników. Standardowy adres podglądu to `http://127.0.0.1:5173`. Model nie jest liczony przy każdym przesunięciu mapy; frontend czyta przygotowane pliki. [S18, S19]

Wejście obejmuje szerokość i długość geograficzną WGS84, promień 10–50 km, profil oraz opcjonalną datę. Domyślny promień CLI wynosi 25 km. Domyślna data to dzień uruchomienia. Datę przeszłą odrzuca się; maksymalny termin to dziś + 15 dni, czyli 16 dni prognozy licząc dzień bieżący. Flaga `--no-radar` pozostawia opad wyłącznie z Open-Meteo. [S02]

Aktualny kod rzeczywiście liczy pogodę do daty wyjazdu. Tekst pomocy `--date` nadal błędnie mówi, że data jest tylko etykietą. To nieaktualny opis, nie zachowanie obecnego przepływu.

### 3.3 Ograniczenia funkcjonalne

Brak systemu zgłoszeń terenowych, rozpoznawania gatunków ze zdjęć, automatycznego uczenia na wynikach wyjazdów, ciągłego monitoringu i pełnego trybu offline. Zapisane punkty w przeglądarce nie przechowują całej aplikacji ani podkładu mapy. Aplikacja nie wyznacza wiarygodnego dojazdu samochodem pod konkretne wejście.

## 4 Architektura i kolejność obliczeń

Przepływ główny przebiega następująco. [S02–S12, S18]

1. Współrzędne zostają przeliczone na metry w EPSG:2180. Koło wyszukiwania jest pokrywane stałą siatką kafli 10 × 10 km. Dla każdego pobierane są odpowiednie warstwy RDLP.
2. Pobierane lub odczytywane z cache są geometrie i atrybuty BDL. Dane z kilku kafli zostają połączone i deduplikowane. Do oceniania pozostają wydzielenia, których centroid leży wewnątrz koła. Ich pełne wielokąty są zachowywane.
3. Opcjonalnie wczytywane są już rozpakowane lokalne paczki BDL, zawierające m.in. pełny skład gatunkowy. Główna ścieżka nie pobiera ich automatycznie.
4. Powstają siatki punktów pogody i klimatologii. Pobierane jest 92 dni historii bieżącej pogody oraz prognoza kończąca się w dniu wyjazdu. Dla norm klimatycznych wykorzystywany jest okres 1991–2020.
5. Opady z ostatniego okna do 30 dni są zastępowane lub uzupełniane pomiarami RainGRS. Temperatura, ET0 i wilgotność gleby nadal pochodzą z Open-Meteo.
6. Dla wydzieleń liczone są maska strukturalna, H, M, T, K_frost, G_season, F, F_loc i wstępne R.
7. Oddzielnie powstaje siedmiodniowa oś warunków dla obszaru, zakotwiczona w dniu uruchomienia, oraz opis ostatnich deszczów. Ten krok nie zmienia rankingu wydzieleń.
8. Dochodzą warstwy GDOŚ i OSM. Liczone są presja P i R_final. Dla 25 wstępnie najlepszych pozycji może zostać zastosowana odległość sieciowa. Następnie dla 50 aktualnie najlepszych sprawdzane są bieżące zakazy okresowe.
9. Powstają etykiety pewności i szablonowe uzasadnienia. Wczytuje się dodatkowy klucz rozstrzygania remisów.
10. Wydzielenia są grupowane w rejony. Osobno przygotowuje się informacje o drzewostanie i sąsiedztwie.
11. Eksport JSON i geometrii jest synchronizowany do frontendu. Przeglądarka sortuje i wyświetla dane. Użytkownik może zapisać punkty lub migawkę całej analizy.

Obliczenia H/F/P są wykonywane w Pythonie. JavaScript nie jest drugim niezależnym modelem biologicznym, ale ma własne reguły prezentacji: klasy, zaokrąglanie, filtr powierzchni, sortowanie i agregacje.

## 5 Źródła danych i ich faktyczne wykorzystanie

### 5.1 Bank Danych o Lasach

WFS BDL: `https://wfs.bdl.lasy.gov.pl/geoserver/BDL/ows`. Kod wysyła `GetFeature` WFS 2.0, pobiera kolejne strony po 1000 obiektów. RDLP wybierana jest przestrzennie; wyszukiwanie przecinające granice dyrekcji obejmuje więcej niż jedną warstwę. [S03]

Najważniejsze pola to `adr_for` jako adres wydzielenia, `a_year` jako rok warstwy, `area_type`, `species_cd`, `part_cd`, `site_type`, `spec_age` i geometria. Identyfikator wyniku ma postać `adr_for@a_year`. Kody z polskimi znakami są normalizowane do kluczy ASCII profilu, np. ŚW → SW i BMŚW → BMSW. Udział `part_cd` jest zamieniany na liczbę; błąd konwersji daje brak wartości.

Warstwa WFS zapewnia gatunek panujący i jego udział, a nie pełny skład gatunkowy. Paczki BDL uzupełniają ten brak. Łączenie odbywa się przez `a_i_num`/`arodes_int_num`, a ostatecznie przez `adr_for`. Duplikaty mapowania geometria–adres są usuwane przed dołączeniem składu. Do H wchodzi tylko piętro `DRZEW`. Udziały liczbowe `part_cd_act` są dzielone przez 10; oznaczenia śladowe `MJS` i `PJD` nie otrzymują arbitralnych udziałów i są pomijane w sumie. [S04]

Suma udziałów ponad 1 + 1e-9 powoduje odrzucenie składu danego wydzielenia i powrót do WFS. Nie ma analogicznego wymagania, by suma była bliska 1 od dołu: niepełna suma może zaniżyć S_host. Gdy ten sam adres wystąpi w kilku katalogach paczek, później wczytany katalog nadpisuje wcześniejszy; kod nie wybiera explicite najnowszej daty metadanych. To miejsca do kontroli jakości danych, nie dowód, że aktualne wyniki są z tego powodu błędne.

Zwarcie, podszyt, typ gleby, budowa drzewostanu, kategoria ochronności i sąsiedztwo trafiają do kart informacyjnych. Nie są dodatkowymi wagami H. Pokrycie gleby i wskaźnik zadrzewienia mają ograniczony wpływ przez kolejność przy remisach, opisany w rozdziale 11.

Etykieta sąsiedztwa wymaga rzeczywistej wspólnej granicy o długości co najmniej 20 m. Pokazywane są sąsiednie obiekty inne niż D-STAN, drzewostany z innym gatunkiem panującym oraz młodniki poniżej 20 lat. Zwykły sąsiad tego samego gatunku, który nie jest młodnikiem, nie stanowi wyróżniającej etykiety. Obliczenia wykorzystują szerszy kontekst kafli, aby krawędź koła wyszukiwania nie tworzyła sztucznego sąsiedztwa.

### 5.2 Open Meteo

Źródło bieżące: `https://api.open-meteo.com/v1/forecast`. Pobierane zmienne dobowe: suma opadu, średnia, minimalna i maksymalna temperatura na 2 m oraz `et0_fao_evapotranspiration`. Zmienna godzinowa: `soil_moisture_9_to_27cm`, uśredniana dobowo. Strefa czasowa zapytania to Europe/Warsaw. [S05]

Źródło historyczne: `https://archive-api.open-meteo.com/v1/archive`. Klimatologia 1991–2020 zawiera bilans CWB26 i wilgotność gleby z warstwy 7–28 cm. Osobna funkcja pobiera pełne historyczne serie pogody używane w backtestach.

Dokumentacja projektu nazywa bieżącą pogodę NWP około 2 km, a archiwum ERA5-Land. W rzeczywistych zapytaniach nie ma parametru `models`, wymuszającego konkretny model. Dlatego dokładnej rodziny modelu i jego rozdzielczości nie należy uważać za zagwarantowane na podstawie samego kodu. Brakuje też utrwalonych metadanych modelu dla każdego pobrania.

ET0 jest dostarczane przez API. Aplikacja nie wylicza lokalnie pełnego równania FAO Penmana–Monteitha. Maksimum dobowe temperatury jest pobierane, lecz nie wchodzi do aktualnego wzoru F. Wilgotność gleby nadal jest pobierana i jej percentyl bywa liczony, ale aktywna waga tej zmiennej wynosi zero.

### 5.3 Radar IMGW RainGRS

Kod korzysta z publicznych plików godzinowych ESRI ASCII oraz dobowych archiwów tar pod ścieżkami `Arch/Nowcasting/rain_grs/grs_60_asc` i `Oper/Nowcasting/rain_grs/grs_60_asc` serwisu `danepubliczne.imgw.pl`. Przyjęto siatkę EPSG:2180 i interpretację znacznika pliku jako końca godziny akumulacji. Notatki opisują empiryczną kontrolę tych założeń, bez znalezienia jednoznacznej oficjalnej specyfikacji obu cech. [S06, S15]

Surowa siatka ma nominalnie 1 km. Dla każdego punktu pogody kod oblicza średnią przestrzenną komórek radaru w kwadracie o boku równym odstępowi punktów pogodowych. Brakujące komórki są pomijane w średniej. Oznacza to, że kompletność godzin nie jest tym samym co kompletność przestrzenna bloku.

Godzina trafia do daty lokalnej odpowiadającej jej początkowi, czyli znacznikowi końca minus jedna godzina. Oczekiwana liczba godzin lokalnej doby wynosi 23, 24 albo 25 zależnie od zmiany czasu. W cache radar jest kwantowany do setnych milimetra jako uint16; to precyzja zapisu, nie dokładność pomiaru opadu.

### 5.4 OSM

Overpass dostarcza parkingi, geometrie dróg i punkty miejscowości z populacją. Uwzględnione klasy miejscowości: city, town, village i hamlet. Brakująca populacja jest uzupełniana wartością klasy miejscowości; szczegóły w 9.1. Drogi podstawowej oceny dostępności to trunk, primary, secondary, tertiary, unclassified i residential. Sieć tras zawiera dodatkowo track. [S09]

Same klasy dróg nie gwarantują nawierzchni, publicznej dostępności ani możliwości postoju. Parser nie zachowuje reguł `access`, `motor_vehicle`, barier czy `surface`. Presja opiera się zatem na wybranych typach dróg, a nie zweryfikowanej sieci legalnego dojazdu samochodem. Parking będący drogą/poligonem OSM jest upraszczany do punktu reprezentatywnego.

### 5.5 Ograniczenia przestrzenne i zakazy

GDOŚ WFS `https://sdi.gdos.gov.pl/wfs`: warstwy `GDOS:Rezerwaty` i `GDOS:ParkiNarodowe`. Każde przecięcie wielokąta wydzielenia z taką geometrią blokuje całe wydzielenie. Jest to reguła modelu przestrzennego, nie indywidualna analiza wszystkich wyjątków prawnych. [S10]

Zakazy okresowe są sprawdzane w ArcGIS REST BDL, warstwa 0 usługi `WMS_zakazy_wstepu_do_lasu`, zapytaniem o punkt centroidu. Sprawdzany jest stan bieżący, także gdy wynik dotyczy wyjazdu w przyszłości. Dla obiektu, którego tylko fragment objęto zakazem poza centroidem, taka kontrola może go nie wykryć. Nie ma pełnego sprawdzania wszystkich wydzieleń ani wszystkich rodzajów ograniczeń.

### 5.6 GBIF oraz dane walidacyjne

GBIF służy do statycznej sezonowości oraz eksperymentów oceny modelu. Rekordy znalezisk nie są dodawane do rankingu jako mapa „pewnych miejsc”. Źródłowe zapytanie o sezonowość wykonano według notatek 25.09.2026. Cztery stacje Weathercloud służyły do porównania opadów, nie są źródłem produkcyjnego F. Prywatnych współrzędnych stacji nie trzeba udostępniać AI do zrozumienia modelu. [S01, S13, S15]

## 6 Rozdzielczość przestrzenna i czasowa

Odstęp punktów skaluje się liniowo z promieniem r podanym w kilometrach:

`s_pogoda = 5000 m × r / 25`

`s_klimatologia = 20000 m × r / 25`

| Promień wyszukiwania | Punkty pogody i bok bloku radaru | Punkty klimatologii |
|---|---|---|
| 10 km | 2 km | 8 km |
| 20 km | 4 km | 16 km |
| 25 km | 5 km | 20 km |
| 50 km | 10 km | 40 km |

Punkty leżą na siatce zakotwiczonej w układzie EPSG:2180. Wydzielenie otrzymuje pogodę najbliższego punktu względem centroidu, bez interpolacji między punktami. Punkt pogodowy jest z kolei przypisany do najbliższego punktu klimatologii. Jeden punkt może obsługiwać wiele wydzieleń. [S02, S05, S07]

Wniosek: kontury wydzieleń mogą być szczegółowe, ale informacja pogodowa nie jest precyzyjna na poziomie każdego małego płatu. Zmiana promienia może zmienić przypisania siatki, rozmiar uśredniania radaru, rozkład norm oraz presję. Ta sama lokalizacja może więc uzyskać inny wynik w wyszukiwaniu 10 i 50 km, nawet bez zmiany terminu.

Cechy opadowe mają okno 26 dni, temperatury 20 i 5 dni, przymrozku 3 dni. Wynik jest dobowy. Nie ma prognozy godzinowej owocnikowania. Dane „dzisiaj” mogą łączyć zakończone pomiary radarowe z modelem dla pozostałej części doby; nie są w całości pomiarem zakończonego dnia.

## 7 Pełna definicja maski oraz siedliska H

### 7.1 Maska

Maska strukturalna jest prawdziwa, jeśli `area_type == D-STAN`, wiek nie jest `None` i nie jest mniejszy od 35 (próg z profilu, wcześniej 12 — patrz 7.4), a gatunek z listy wykluczeń nie stanowi co najmniej 8/10 udziału. To dokładny sens warunków kodu; pełna walidacja NaN i typów wejściowych wymaga osobnej kontroli. [S01, S07]

Lista gatunków wykluczających przy dominacji co najmniej 80%: OL, JS, KL, WZ, AK, JW, OL.S, WB, CZM.P, JB, CZM, KSZ, CZR, SL.A, GR, KL.PE, WZ.S. Wierzba WB ma małe niezerowe powinowactwo przy domieszce, a mimo to wyklucza przy dominacji. Maska nadal bazuje na polach WFS, nawet gdy S_host jest liczone z paczki.

Maska pełna dodaje wykluczenie przez GDOŚ i pozytywny wynik sprawdzonego zakazu okresowego. Brak sprawdzenia zakazu nie staje się wykluczeniem. Powierzchnia poniżej 0,5 ha nie wyklucza przez maskę: to późniejszy filtr listy pojedynczych celów.

### 7.2 Gatunki drzew

Jeżeli dostępny jest pełny skład:

`S_host = suma po gatunkach i z (u_i × a_i)`

`u_i = liczbowy udział part_cd_act / 10`

Jeżeli dostępny jest tylko gatunek panujący:

`u = part_cd / 10`

`S_host = u × a_gatunek + (1 − u) × 0,5`

Brak udziału oznacza u = 0, a zatem neutralne S_host = 0,5. Nieznany kod gatunku otrzymuje powinowactwo 0,5. Pełny skład nie jest automatycznie renormalizowany.

| Powinowactwo a | Kody gatunków w aktywnym profilu |
|---|---|
| 1,0 | SO, SW |
| 0,9 | BK |
| 0,8 | DB, DB.S, DB.B, JD |
| 0,7 | BRZ |
| 0,6 | SO.C, SO.WE |
| 0,4 | DB.C |
| 0,3 | GB, MD, DG, LP |
| 0,2 | OS, TP, TP.C |
| 0,1 | WB |
| 0,0 | OL, JS, KL, WZ, AK, JW, OL.S, CZM.P, JB, CZM, KSZ, CZR, SL.A, GR, KL.PE, WZ.S |

Są to wartości profilu eksperckiego, nie wyniki estymacji częstości borowików w poszczególnych gatunkach lasu. Przykład: 70% sosny i 30% nierozpoznanej domieszki w WFS daje 0,85; pełny skład 70% sosny i 30% świerka daje 1,0. Pełniejsze dane mogą zwiększać liczbę remisów na najwyższej ocenie, zamiast ją zmniejszać.

### 7.3 Typ siedliskowy i klasa wilgotności

| Kody siedlisk | S_site | Klasa wilgotności |
|---|---|---|
| BMSW, BMWYZ | 1,00 | 1 świeże |
| BSW, LMSW, LMWYZ | 0,85 | 1 świeże |
| BMW, BW, LMW, LMWYZW | 0,65 | 2 wilgotne |
| LSW, LWYZS | 0,60 | 1 świeże |
| BS | 0,45 | 0 suche |
| LW, LWYZW | 0,40 | 2 wilgotne |
| BMB, BB, LMB | 0,15 | 3 bagienne |
| OL, OLJ, OLJWYZ | 0,00 | 3 bagienne |
| LL, LLWYZ | 0,00 | 2 wilgotne |
| Kod nieznany | 0,50 | 1 świeże |

Zero S_site daje H = 0, ale niekoniecznie `mask = false`. To wyjaśnia możliwość pozycji przechodzącej maskę, lecz z zerowym rankingiem. Normalizacja kodu to transliteracja, nie inteligentne dopasowanie dowolnego typu górskiego lub wyżynnego.

### 7.4 Wiek

Wiek a jest wyrażony w latach:

`a < 35 lub a = None: S_age = brak, H = brak`

Próg maski to `age_breakpoints.mask_below` z profilu: 35 lat od 01.10.2026, wcześniej 12. To decyzja właściciela po wyjeździe do młodych drzewostanów, oparta na założeniu, a nie na danych (`docs/RAPORT_FAZA_2.md`, „Decyzje po walidacji”, punkt 3). Przy progu 35 lat dwa poniższe przedziały 12–35 lat nie są używane; zostają w profilu na wypadek powrotu do progu 12.

`12 ≤ a < 20: S_age = 0,3 + 0,3 × (a − 12) / 8`

`20 ≤ a < 35: S_age = 0,6 + 0,4 × (a − 20) / 15`

`35 ≤ a ≤ 120: S_age = 1`

`a > 120: S_age = 0,9`

Powstaje szeroki płaskowyż wieku 35–120 lat oraz skok po 120. Brak terenowej kalibracji uzasadniającej dokładność tych granic dla badanego regionu. Wiek z pola źródłowego nie jest w formule automatycznie zwiększany o liczbę lat od wykonania opisu.

### 7.5 Agregacja H

`H = S_host^0,40 × S_site^0,35 × S_age^0,25`

To ważona średnia geometryczna przy poprawnych składowych 0–1. Wartość zero jednej składowej zeruje H. Wagi sumują się do 1, a ich sens jest ekspercki. Wzór nie opisuje biomasy grzybni ani udziału powierzchni rzeczywiście zasiedlonej.

## 8 Pełna definicja pogody i owocnikowania

### 8.1 Scalenie opadu

Niech P_model oznacza modelowaną sumę dobową, P_radar sumę dostępnych godzin pomiaru, k liczbę godzin z radarem, a n oczekiwaną liczbę godzin doby. [S06]

`P_doba = P_radar + P_model × (1 − k/n)`

`radar_frac = k/n`

Przy k = n wynik jest wyłącznie radarowy. Przy k = 0 pozostaje cały opad z modelu. Uzupełnienie zakłada, że brakująca część doby ma udział w opadzie modelowym proporcjonalny do czasu. To uproszczenie może zawieść przy krótkiej burzy i nierównomiernym rozkładzie deszczu.

Współczynnik 0,848 NIE mnoży produkcyjnych sum opadu, CWB ani wartości mm w opisie deszczu. Używany jest do obniżenia progu wykrywania większego deszczu w panelu warunków przy włączonym radarze.

### 8.2 Okno pamięci wilgoci

Dla dnia t i opóźnienia j w dniach:

`w_j = 0,5^(j/10), j = 0,…,25`

`P26w(t) = suma j=0…25 z [w_j × P(t−j)]`

`ET026w(t) = suma j=0…25 z [w_j × ET0(t−j)]`

`CWB26(t) = P26w(t) − ET026w(t)`

Opad z dnia t ma wagę 1, sprzed 10 dni 0,5, a sprzed 20 dni 0,25. Jest to suma ważona w milimetrach, bez dzielenia przez sumę wag. Jeżeli szereg jest krótszy, funkcja wykorzystuje dostępny fragment. CWB26 jest wskaźnikiem bilansu opad minus referencyjna ewapotranspiracja, nie modelem magazynowania wody w glebie. Nie uwzględnia pojemności wodnej, spływu, infiltracji, korzeni ani intercepcji konkretnego drzewostanu. [S05]

Inne cechy: P5 to zwykła suma opadu z ostatnich pięciu dni; Tmean20 i Tmean5 to średnie temperatury; Tmin3 to najmniejsza dobowa temperatura minimalna z trzech dni. `days_since_p10` liczy odstęp od ostatniego dnia z co najmniej 10 mm, ale nie wchodzi do F i nie jest obecną logiką opisu epizodów deszczu.

### 8.3 Percentyle

Wartość CWB26 jest porównywana z historią najbliższej komórki klimatologii z lat 1991–2020, dla dni roku odległych o najwyżej 15 dni od daty wyjazdu. Okno jest zawijane na przełomie roku z długością 365 dni.

`pct(x) = [liczba wartości historycznych < x + 0,5 × liczba wartości = x] / N`

Jest to `scipy.stats.percentileofscore(..., kind="mean") / 100`. Przy pustej historii kod zwraca 0,5. Nie jest to informacja o średnich warunkach zaobserwowanych w terenie, tylko wartość zastępcza. Lata przestępne nie mają osobnej korekty. Braki NaN w niepustym szeregu wymagają kontroli; sama gałąź pustego okna ich nie rozwiązuje. [S05, S07]

### 8.4 Wilgotność M

`pct_m = (1 − w_sm) × pct_CWB26 + w_sm × pct_SM`

`w_sm = 0,0`

`M = 1 / {1 + exp[−(pct_m − 0,50) / 0,10]}`

Obecnie pct_m = pct_CWB26. Wcześniej stosowano w_sm = 0,5. Wyłączono tę składową, ponieważ bieżącą wilgotność gleby porównywano z klimatologią innego modelu i nieidentycznej warstwy głębokości. W obserwowanym przypadku dawało to bardzo niskie percentyle i sztuczne bloki przestrzenne. Waga zero oznacza wyłączenie sygnału, a nie naprawę pomiarów wilgotności. [S01, S08, S16]

| pct_m | M | F przy T = 1, K_frost = 1, G_season = 1 |
|---|---|---|
| 0,15 | 0,029 | 0,120 |
| 0,35 | 0,182 | 0,360 |
| 0,50 | 0,500 | 0,660 |
| 0,70 | 0,881 | 0,927 |
| 0,90 | 0,982 | 0,989 |

To wyliczone scenariusze wzoru, nie wyniki pomiaru skuteczności. Funkcja szybko nasyca się w górnej części skali, co sprzyja dużej liczbie podobnych ocen podczas mokrego okresu.

### 8.5 Temperatura i przymrozek

`T_baza = exp{−(Tmean20 − 13)^2 / (2 × 4^2)}`

Jeżeli jednocześnie `Tmean5 > 17,5°C` i `P5 < 5 mm`, to `T = 0,3 × T_baza`; w przeciwnym razie `T = T_baza`. Równość na progach nie uruchamia kary.

`K_frost = 0,2`, gdy `Tmin3 < −2°C`.

`K_frost = 0,6`, gdy `−2°C ≤ Tmin3 < 0°C`.

`K_frost = 1`, gdy `Tmin3 ≥ 0°C`.

Temperatura dotyczy 2 m nad gruntem według modelu, nie temperatury ściółki. Produkcyjny model nie spowalnia dojrzewania za każdą chłodną noc powyżej zera; taki mechanizm występował w eksperymencie odrzuconym.

### 8.6 Sezonowość

Liczby GBIF dla stycznia–grudnia: `[1, 0, 0, 0, 2, 25, 118, 243, 471, 350, 58, 2]`, łącznie 1270. Każdy miesiąc jest dzielony przez maksimum 471. Powstałe wartości przypisuje się do 15. dnia miesiąca, interpoluje liniowo pomiędzy tymi datami z zawinięciem roku, a wynik ogranicza od dołu do 0,05. [S01, S08]

`G_season(d) = max[0,05; interpolacja_liniowa(d, liczby_miesięczne/471)]`

Współczynnik jest taki sam dla wszystkich wydzieleń danej analizy. Nie zależy od regionu, wysokości, gatunku drzew ani aktualnego przesunięcia sezonu. Rekordy GBIF opisują obserwacje, na które wpływa intensywność zbierania i zgłaszania; nie są bezpośrednim pomiarem częstości owocnikowania.

### 8.7 Warunki regionalne i lokalne

`F = G_season × M^0,6 × T^0,4 × K_frost`

Następnie wybierany jest mnożnik siedliskowy q na podstawie pct_m i klasy wilgotności c:

| Warunek | Suche c = 0 | Świeże c = 1 | Wilgotne c = 2 | Bagienne c = 3 |
|---|---|---|---|---|
| pct_m < 0,3 | 0,60 | 0,90 | 1,20 | 1,00 |
| 0,3 ≤ pct_m ≤ 0,8 | 1,00 | 1,00 | 1,00 | 1,00 |
| pct_m > 0,8 | 1,15 | 1,00 | 0,85 | 0,70 |

`F_loc = min[1; max(0; F × q)]`

W suchym okresie część siedlisk wilgotnych dostaje premię, a suche karę. W bardzo mokrym okresie kierunek częściowo się odwraca. Przeskoki przy 0,3 i 0,8 są dyskretne, nie wygładzone. Obcięcie do 1 może spłaszczać górny zakres.

Klasy F i F_loc: poniżej 0,20 „Słabe warunki”; od 0,20 do poniżej 0,45 „Umiarkowane”; od 0,45 do poniżej 0,70 „Dobre”; od 0,70 „Bardzo dobre” w normalnym zakresie 0–1. Kod ostatniej klasy ma techniczną granicę 1,01. To etykiety wskaźnika, bez walidacji jako progów prawdopodobieństwa.

## 9 Presja dostępność i wynik końcowy

### 9.1 Presja P

Aktywny profil ustawia `pressure.model: access_points`. Presja trafia do wydzielenia wyłącznie przez **punkty dostępu** do lasu, a ludność jedynie „zasila” te punkty. Ludność dzielona jest między punkty modelem probabilistycznym Huffa w wariancie `population_split: two_stage`. Dawny model grawitacyjny od centroidu wydzielenia pozostaje w kodzie jako tryb porównawczy i awaryjny, opisany na końcu tego podrozdziału. Model użyty w danym przebiegu zapisuje manifest (`pressure_model_used`), a każde wydzielenie kolumnę `pressure_model`. Wszystkie parametry poniżej są hipotezą właściciela zapisaną w profilu (`pressure.access_points`) i są **nieskalibrowane**. [S09]

**Punkty dostępu.** Typy punktów, w EPSG:2180:

- `parking` — wszystkie parkingi i miejsca postoju z BDL oraz `amenity=parking` z OSM, jeśli leżą najwyżej 200 m od lasu; duplikaty w promieniu 100 m są usuwane, a pierwszeństwo ma BDL;
- `entrance` — wjazd do lasu, rozpoznawany w trzech sytuacjach:
  - droga publiczna przecina granicę lasu, a najwyżej 60 m od przecięcia zaczyna się dukt lub droga leśna;
  - dukt przecina granicę lasu najwyżej 300 m od drogi publicznej;
  - koniec duktu leży najwyżej 20 m od drogi publicznej;
- `gate` — szlaban OSM na drodze leśnej, najwyżej 300 m od drogi publicznej; wjazdy i szlabany deduplikuje się w promieniu 150 m, a pierwszeństwo ma szlaban;
- `road_fallback` — punkty co 500 m na drogach asfaltowych najwyżej 200 m od lasu, tworzone tylko w kaflach z co najmniej 1 km² lasu, w których nie znaleziono żadnego wjazdu ani szlabanu;
- `settlement` — oczka siatki GUS 1 km z ludnością, których kwadrat sięga najwyżej 200 m od lasu; powstają tylko wtedy, gdy przebieg dostał plik siatki GUS.

Drogi leśne, czyli zamknięte drogi OSM i dojazdy pożarowe BDL, dostają klasę nawierzchni i tworzą sieć korytarzy.

**Źródło ludności.** Z plikiem siatki GUS NSP 2021 (`--population-grid-path`) punktami ludności są środki oczek 1 km. Bez niego kod bierze miejscowości OSM, a brakującą populację uzupełnia wartością klasy: hamlet 50, village 500, town 5000, city 50 000. Manifest zapisuje wtedy `population_source: osm_z_imputacja`. Ludność pochodzi z miejscowości w obrębie kafli przebiegu. Skupisko ludzi tuż poza nimi nie jest uwzględniane.

**Jądro odległości.** Wszędzie używane jest to samo gładkie jądro bez twardego progu:

`k(d; R) = max(0; 1 − (d/R)²)²`

**Etap 1: sposób dotarcia.** Dla punktu ludności j w odległości d_las_j od lasu:

`p_walk_j = 0,5 × max(0; 1 − d_las_j / 1,5 km)`

Udział pieszy jest dzielony między osiedla przy lesie w zasięgu 1,5 km, proporcjonalnie do `w_t × k(d)`, bez opcji zewnętrznej. Gdy w zasięgu pieszym nie ma osiedla, ten udział przechodzi do „autem”. Reszta ludności, `1 − p_walk_j`, jedzie autem.

**Etap 2: podział Huffa między punkty samochodowe.** Punktami samochodowymi są `parking`, `entrance`, `gate` i `road_fallback`. Udział punktu k w ludności punktu j:

`u_jk = w_k × k(d_jk; 20 km) / [suma po k′ z (w_k′ × k(d_jk′; 20 km)) + c]`

Wagi typów: parking 1,0, wjazd 0,6, szlaban 0,6, fallback 0,4. Opcja zewnętrzna c = 0,77 („nie jadę do tego lasu”) sprawia, że suma udziałów jednego punktu ludności jest mniejsza od 1. Przykład z komentarza profilu: jedyny parking w odległości 15 km dostaje 19,9% ludności oczka. Atrakcyjność punktu to liczba osób:

`A_k = suma po j z (Pop_samochodem_j × u_jk)`

W tym wariancie waga typu działa tylko w podziale, nie w sumie presji. `A_norm = A / (A + 500)` służy wyłącznie do klas atrakcyjności na mapie i nie wchodzi do P.

**Korytarze dróg leśnych.** Atrakcyjność przenosi się z punktów dostępu po sieci dróg leśnych:

`A_odcinek = max po k z [A_k × 0,5^(d_sieć,k / 3 km)] × mnożnik nawierzchni`

Mnożniki nawierzchni: twarda 1,0, żwir i ubita 0,8, nieznana 0,5, gruntowa 0,3. Punkt jest dołączany do sieci, jeśli leży najwyżej 150 m od węzła. Wartość liczy jeden przebieg Dijkstry ze źródłem wspólnym dla wszystkich punktów. Każdy punkt ma przesunięcie startowe `λ × ln(skala / A_k)`, gdzie `λ = 3 km / ln 2`. Węzły to wierzchołki zaokrąglone do 1 m, a drogi przecinające się bez wspólnego wierzchołka nie są łączone. Wynikiem są próbki korytarza co około 100 m, w przebiegu z 30.09.2026 było ich 54 620. Drogi nieosiągalne z żadnego punktu dostają zero.

**Presja wydzielenia.** Dla centroidu wydzielenia:

`raw = suma po typach t i punktach k w zasięgu R_t z [A_k × k(d_k; R_t)] + 0,4 × max po próbkach korytarza w 300 m z [A_odcinek × k(d; 300 m)]`

`P = 1 − exp(−raw / S)`, `S = 1997`

Zasięgi oddziaływania R_t: parking 3 km, wjazd i szlaban 2,5 km, fallback i osiedle 1,5 km. Korytarz wchodzi jako jeden składnik, maksimum po próbkach, a nie suma. Dwie równoległe drogi obok siebie nie oznaczają więc dwa razy więcej rowerzystów.

Od 30.09.2026 obowiązuje dolny próg presji od parkingu. Wydzielenie w zasięgu parkingu dostaje od niego co najmniej `700 × k(d; 3 km)` osób, liczone od najbliższego parkingu (maksimum, nie suma). Przy samym parkingu odpowiada to P ≈ 0,30.

S dobrano tak, aby mediana P w przebiegu testowym Kieleczki była zbliżona do mediany modelu grawitacyjnego (0,373). Jest to kalibracja skali między modelami, a nie względem pomiarów ruchu.

W eksporcie `details.json` każde wydzielenie ma w `access.pressure_contrib` wkład każdego typu punktu. Obok są odległości do najbliższego parkingu, wjazdu i utwardzonej drogi leśnej oraz punkt o największym wkładzie (`top_point_*`). Pole `d_park_m` w `scores.json` pozostaje przybliżeniem euklidesowym z modelu grawitacyjnego (`1,3 × min(d_parking, d_droga)`), a nie odległością do punktu dostępu.

**Stan przebiegu z 30.09.2026 (Zawadzkie, r = 20 km).** Z manifestu:

- 202 parkingi (97 BDL, 105 OSM), 1659 wjazdów i 107 szlabanów;
- 0 punktów fallback i 0 osiedli, bo przebieg nie dostał siatki GUS;
- ludność z OSM z imputacją.

Etap pieszy nie miał więc dokąd kierować ludności, a cała ludność trafiła do podziału samochodowego. Ponowne wyliczenie offline z cache tych samych 23 kafli dało 557 miejscowości z 203 226 mieszkańcami i 397 883 par miejscowość–punkt w zasięgu 20 km. Odtworzone `A_norm` zgadzają się z eksportem: korelacja 1,0, średnia różnica bezwzględna 0,0004. Opcja zewnętrzna zatrzymała tylko około 0,6% ludności, bo prawie każda miejscowość ma w zasięgu wiele punktów. Przy gęstej sieci wejść parametr c ma więc niewielki wpływ.

**Tryb grawitacyjny (porównawczy i awaryjny).** Używany przy `pressure.model: gravity` albo gdy przebieg nie ma żadnego punktu dostępu. W trybie `access_points` `P_gravity` i tak jest liczone i zapisywane do porównań.

`d_park = 1,3 × min(d_parking, d_droga)`

`Demand = suma j z [Pop_j / (1 + (d_j/10 km)²)]`

`Demand_norm = Demand / (Demand + 90 000)` przy domyślnym `normalization: absolute`; przy `local` jest to `Demand / max(Demand w analizie)`

`P = 1 − exp[−2 × Demand_norm × exp(−d_park/800 m)]`

Brak parkingów i dróg daje d_park = nieskończoność i P = 0. Tylko w tym trybie działa przeliczenie odległości sieciowej do wejść dla 25 najlepszych wydzieleń, opisane w 9.2.

Oba modele są nieskalibrowane. Nie wykorzystują rzeczywistych liczników odwiedzających, śladów GPS, informacji o zebranych grzybach ani natężenia ruchu rowerowego. Brak danych o punktach dostępu nie oznacza małej presji. Dlatego przebieg bez punktów przełącza się jawnie na model grawitacyjny, zamiast przyjąć P = 0.

### 9.2 Wejścia i sieć

Ten podrozdział opisuje wejścia i przeliczenie odległości sieciowej używane tylko w trybie grawitacyjnym. W domyślnym trybie `access_points` przeliczenie dla 25 najlepszych nie jest wykonywane. Eksport ma wtedy `distance_method: access_points` i `entrance_status: not_evaluated`, a punkty wejścia wyznacza reguła z 9.1.

Granica lasu powstaje z unii wszystkich D-STAN w szerszym kontekście pobranych kafli, z buforowaniem +40 m i następnie −40 m. Domknięcie ogranicza fałszywe wejścia na wąskich wewnętrznych przerwach. Przecięcia dróg z tą granicą są potencjalnymi wejściami. Odległość do parkingu najwyżej 50 m daje etykietę `confirmed`; pozostałe mają `potential`. „Confirmed” oznacza zgodność z geometrią parkingu OSM, nie wizytę terenową. [S09]

Graf jest nieskierowany. Węzły stanowią współrzędne kolejnych wierzchołków dróg, zaokrąglone do 0,001 m, a krawędzie mają długość odcinków. Drogi łączą się przez wspólne wierzchołki. Nie wykonuje się pełnego topologicznego rozcięcia każdej geometrycznej krzyżówki. Odległość to najkrótsza ścieżka Dijkstry plus odcinki prostoliniowe od centroidu i wejścia do najbliższych węzłów grafu.

Tę metodę stosuje się do 25 najwyższych wyników przed przeliczeniem odległości. Najbliższe wejście może mieć status tylko potencjalnego. Brak osiągalnej trasy pozostawia wcześniejszą odległość przybliżoną. Po zmianie odległości przeliczane są P i R, bez iteracyjnego zapewnienia, że nowa końcowa czołówka w całości ma tę samą metodę odległości.

### 9.3 Ranking

`R_final = 100 × H × F_loc × (1 − α × P)`, jeżeli maska pełna jest prawdziwa.

`R_final = 0`, jeżeli maska jest fałszywa lub wymagane H/F_loc są `None`.

Domyślne α = 0,3. API funkcji pozwala podać inne α, ale standardowy przebieg i aktualny interfejs nie oferują opisanego w dawnym projekcie suwaka 0–0,6. Nie należy przedstawiać suwaka jako wdrożonej funkcji.

Przykład obliczeniowy: H = 0,8, F_loc = 0,75, P = 0,4 oraz α = 0,3 dają R = 52,8. To umowny wynik preferencji. W modelu punktów dostępu P = 1 − exp(−raw/S) zbliża się do 1 bez górnego ograniczenia raw, więc kara przy α = 0,3 dąży do 30% wyniku biologicznego. Wydzielenie przy samym parkingu ma z samego dolnego progu co najmniej około 9% kary (P ≈ 0,30). W trybie grawitacyjnym, przy k = 2 i Demand_norm < 1, P nie przekracza około 0,865, a kara około 26%.

Wstępne pole `R` z `run_poc` nie zawiera jeszcze pełnego wzbogacenia. Eksport JSON pod nazwą `R` zapisuje końcowe `R_final`. Przy analizie notebooków trzeba rozróżniać te etapy.

## 10 Siedmiodniowy panel warunków

Panel ma własną agregację przestrzenną. Dla punktów pogodowych leżących wewnątrz koła liczy cechy osobno do każdego dnia od dziś do dziś + 6. Następnie bierze medianę CWB26, Tmean20, Tmean5, P5 i Tmin3 między punktami. Medianę CWB26 porównuje z połączoną historią punktów klimatologii wewnątrz koła, a nie z jedną odpowiadającą jej komórką. Z tych wartości liczy M, T, K_frost, G_season i F. [S12]

Nie ma tu H, presji ani lokalnej modulacji F_loc. Funkcja przekazuje dla gleby stały percentyl 0,5, bez znaczenia przy obecnej wadze zero. Gdyby w przyszłości włączono wagę gleby, panel i model wydzieleń rozeszłyby się metodologicznie, o ile nie zostanie zmieniony ten fragment.

Klasa 0–3 panelu wynika z tych samych granic F, które opisano wcześniej. To nie jest osobna skalibrowana prognoza fazy wysypu. Nie wolno przypisywać tej agregacji wyniku walidacji 0,626 z punktowego backtestu. Mediana cech, F z median i mediana F po wydzieleniach nie muszą być równe, ponieważ funkcje są nieliniowe.

Opis deszczu używa mediany dobowego opadu w obszarze. Mokry dzień ma co najmniej 1 mm; pojedynczy suchy dzień między mokrymi może należeć do jednego epizodu. Pod uwagę brane są do dwóch najnowszych epizodów o końcu w ostatnich 45 dniach. Próg sumy wynosi 15 mm bez radaru albo 15 × 0,848 = 12,72 mm przy jego włączeniu. W opisie pozostaje rzeczywista suma scalonych danych, bez mnożenia przez 0,848.

Detektor widzi dane tylko do dziś, więc prognozowany deszcz nie może połączyć się z epizodem historycznym. Dzisiejszy opad może jednak częściowo pochodzić z modelu. Również samo włączenie radaru obniża próg epizodu, nawet gdy radar ostatecznie zawiedzie i źródłem okaże się wyłącznie Open-Meteo. To hipoteza do kontroli zachowania przy awarii.

Pole `forecast = false` pierwszego kafelka znaczy „dzień bieżący”, a nie „100% pomiarów”. Dla daty wyjazdu innej niż dziś ranking dotyczy wyjazdu, lecz kafelki nadal startują od dnia przygotowania. Zapisane mapy zamrażają również tę oś: ich „dziś” jest dniem zapisanej analizy, nie dniem późniejszego oglądania.

## 11 Grupowanie sortowanie i prezentacja

### 11.1 Rejony

Kandydatami są wydzielenia przechodzące maskę, z R_final co najmniej równym kwantylowi 0,95 tej populacji. Ze względu na remisy może to być więcej niż dokładnie 5%. Każdy centroid kandydata jest potencjalnym środkiem okna. Wchodzą do niego tylko te wydzielenia, których cała geometria mieści się w promieniu 800 m. [S11]

`ocena_okna = suma wydzieleń i z [powierzchnia_i w ha × R_final_i]`

Okna rozpatrywane są zachłannie od najwyższej oceny. Przyjęty rejon musi zawierać co najmniej 5 ha kandydatów, a centroid jego rzeczywistej unii musi być odległy o co najmniej 3000 m od centroidów zaakceptowanych rejonów. Maksimum to pięć rejonów; brak spełnienia kryteriów może dać mniej lub zero. Geometria jest unią wydzieleń, nie pełnym kołem.

`rank_score_rejonu = mediana R_final najlepszych do 5 jego wydzieleń`

Ocena użyta do wyboru okna i ocena wyświetlana przy rejonie są więc różne. Identyfikatory region_1 itd. pochodzą z kolejności zachłannego wyboru; frontend dodatkowo sortuje po rank_score. Region_2 może pojawić się przed region_1. Konstrukcja daje średnicę do 1600 m, ale nie gwarantuje ciągłości dogodnej trasy przez wszystkie części rejonu.

### 11.2 Rozstrzyganie remisów

Podstawą sortowania pojedynczych wydzieleń jest R zaokrąglone do dwóch miejsc, następnie malejąco `tie_break`, następnie rosnąco identyfikator. W rejonie tie_break porządkuje listę członków, a nie zastępuje rank_score. [S11, S18]

`tie_break = 0,5 × preferencja_pokrycia + 0,5 × preferencja_zadrzewienia`

Pokrycie MSZC/MSZ/SCIO daje 1,0; ZAD/ZIEL daje 0,6; SZAD/SZCH/NAGA daje 0,2; brak lub kod nieznany daje 0,5. Preferencja zadrzewienia dla x: 1 przy 0,7 ≤ x ≤ 1,0; max(0, x/0,7) poniżej 0,7; max(0, 2−x) powyżej 1,0; brak daje 0,5.

To nieskalibrowana preferencja porządkowa, nie część H/F/R. Może zmienić wybór między bardzo bliskimi wynikami, mimo że numeryczne R pozostaje bez zmian. Python i JavaScript używają własnych konwencji zaokrąglania; zgodność przypadków dokładnie na połowie wymaga osobnego testu.

### 11.3 Interfejs

Domyślnie można oglądać rejony, jeżeli istnieją; przełącznik pozwala przejść do wydzieleń. Lista pojedynczych celów ukrywa powierzchnie poniżej 0,5 ha. Brak powierzchni w starszym eksporcie nie ukrywa pozycji. Małe obiekty pozostają w danych oraz mogą uczestniczyć w rejonach. Mapa używa geometrii wynikowych i podkładu OpenFreeMap. [S18]

Baner obszaru liczy nieważoną powierzchnią medianę F wszystkich wydzieleń z `mask = true` i skończonym F. Każde wydzielenie ma taki sam udział, więc rozdrobnienie administracyjne wpływa na agregację. Karta rejonu korzysta z najlepiej ustawionego członka do części informacji, np. F, P i punktu nawigacji. Nie wszystkie wyświetlane cechy są medianami rejonu.

Punkt nawigacji jest orientacyjnym środkiem wydzielenia. Współrzędne rzeczywistego wejścia z routingu nie są eksportowane do karty. Status `network` nie zmienia punktu orientacyjnego w zweryfikowany parking.

## 12 Pewność i wyjaśnienia

Wskaźnik jakości danych jest iloczynem kompletności składu, czynnika świeżości i czynnika pogodowego:

`DQ = kompletność × świeżość × pogoda`

Kompletność wynosi 1,0 dla składu z paczki, 0,7 dla rozpoznanego gatunku panującego WFS, 0,5 dla nierozpoznanego. Świeżość wynosi 1,0: nie ma aktywnej analizy zmian satelitarnych. Pogoda ma 0,9, gdy ważone pokrycie radarowe wynosi co najmniej 0,8, w przeciwnym razie 0,8. [S01, S10]

`coverage = suma(w_j × radar_frac_j) / suma(w_j)`

Pokrycie jest ważone czasem, nie udziałem radarowych milimetrów w całej sumie opadu. Klasy DQ: poniżej 0,40 niska, poniżej 0,70 średnia, do 1,01 wysoka. Końcowa pewność jest minimum klasy DQ i limitu modelu „SREDNIA”. Zatem nawet bardzo dobre dane nie dają obecnie „WYSOKA”. Przy obecnych czynnikach najmniejsze normalne DQ to 0,5 × 1 × 0,8 = 0,4, czyli już klasa średnia. Etykieta pewności może więc nie różnicować wyników w zwykłych ścieżkach.

Pewność nie jest przedziałem ufności i nie wynika z rozkładu błędów predykcji. Nie obejmuje systematycznie jakości wszystkich źródeł: brak OSM, pominięty kafel GDOŚ, stare geometrie, nieznany typ siedliskowy czy pusta klimatologia nie stanowią osobnych mnożników DQ.

Uzasadnienia są tworzone z szablonów, nie przez model językowy. Dla dodatnich składowych liczy się wkład względem mediany obszaru:

`wkład_i = w_i × [ln(składowa_i) − ln(mediana_obszaru_i)]`

Wagi: host 0,40; site 0,35; age 0,25; moisture 0,6; temperature 0,4; frost 1; pressure_factor 1. Mediany liczone są po maskowanych dodatnich wartościach. Wybierane są maksymalnie dwa dodatnie i dwa ujemne wkłady. G_season poniżej 0,5 ma dodatkową notatkę. Brakuje pełnego rozkładu wpływu lokalnej modulacji F_loc i efektu obcięcia do 1.

Dodatni wkład oznacza przewagę nad innymi miejscami w bieżącej analizie. Szablon opisujący go jako „powyżej normy” lub „niska presja” może brzmieć mocniej niż sam dowód. Po włączeniu pełnego składu również sformułowanie o gatunku panującym może nie tłumaczyć całej sumy składu. To obszar do przeglądu zgodności języka z obliczeniem.

## 13 Cache eksporty i powtarzalność

### 13.1 Przechowywanie danych

BDL, GDOŚ i OSM są przechowywane w lokalnych plikach per kafel; klimatologia i pogoda w plikach per punkt; radar w skompresowanych plikach per doba. BDL ma cache z warstwą RDLP w kluczu; OSM ma klucz zależny od konfiguracji. Pogoda używa w kluczu współrzędnych, dnia pobrania i długości prognozy. Klimatologia nie ma w kluczu daty ważności. [S03, S05, S06]

W typowych ścieżkach sprawdzane jest istnienie pliku, a nie jego wiek. Nie ma ogólnego TTL dla geometrii BDL, GDOŚ i OSM. Dobowy cache pogody może zachować starszą prognozę z tego samego dnia mimo późniejszego uruchomienia. Klucz pogody nie zawiera `past_days`, a klimatologii zakresu lat; obecny przepływ używa stałych wartości, lecz zmiana tych parametrów bez wersjonowania cache byłaby ryzykowna.

Przy awarii radaru następuje powrót do Open-Meteo z ostrzeżeniem. Błędne kafle GDOŚ i OSM mogą być pominięte, a analiza kontynuowana. Po pierwszej awarii niebuforowanego kafla OSM dalsze brakujące kafle w tym uruchomieniu są pomijane. Natomiast błędna odpowiedź sprawdzania zakazu okresowego zgłasza wyjątek, zamiast udawać brak zakazu.

### 13.2 Pliki wynikowe

| Plik | Zawartość i znaczenie |
|---|---|
| scores_YYYY-MM-DD.json | H, F, F_loc, P, końcowe R, maska, jakość, uzasadnienia, odległość, metoda, status wejścia, daty, powierzchnia, źródło składu, tie_break, pokrycie radaru |
| stands.geojson | Identyfikatory i pełne geometrie w EPSG:4326 do mapy |
| stands_mvp.parquet | W aktualnym eksporterze tylko identyfikator i geometria; nazwa nie oznacza pełnej tabeli składowych |
| regions_YYYY-MM-DD.json | Lista rejonów, rank_score, członkowie, centroid i dzień |
| details_YYYY-MM-DD.json | Skład, zwarcie, gleba, podszyt, sąsiedztwo i inne cechy opisowe |
| conditions_YYYY-MM-DD.json | Daty deszczu, sumy, panel siedmiu dni i data odniesienia |

Eksport ocen zamienia NaN na null i używa `allow_nan=False`. Synchronizator sprawdza strukturę, daty i relacje identyfikatorów przed podmianą plików. Pliki opcjonalne są usuwane, gdy nowa analiza ich nie ma, zamiast pozostawiać nieaktualne dane. To nie jest jednak kompletny manifest jednego uruchomienia ani atomowa publikacja całego zestawu pod unikalnym identyfikatorem.

W scores brakuje surowych M, T, K_frost, S_host, S_site, S_age, percentyli, przypisania do punktu pogody oraz statusów sprawdzenia zakazu. `stand_id` zawiera rok warstwy, ale nie datę pomiaru każdego atrybutu. Bez rozszerzonego eksportu nie da się w pełni odtworzyć przyczyny pojedynczej oceny tylko z plików frontendu.

### 13.3 Zapisane analizy

`localStorage` przechowuje wybrane punkty/opisy i preferencje widoku. Launcher zapisuje oddzielne migawki plików analizy w katalogach `frontend/public/data/trips/<id>/` z indeksem i metadanymi nazwy, promienia, współrzędnych oraz daty zapisu. Migawki służą do porównań, nie przeliczają się po zmianie profilu. Nie zawierają pełnej historii surowych źródeł. [S19]

## 14 Co rzeczywiście wiadomo o dokładności

### 14.1 Trafność całej rekomendacji

Nie ma udokumentowanego wyniku accuracy, precision, recall, AUC, odsetka udanych wyjazdów ani błędu liczby zebranych grzybów dla całej aplikacji. Brakuje systematycznych wizyt w miejscach wysoko i nisko ocenionych, także z wynikiem zerowym i z porównywalnym czasem poszukiwań. Nie można zatem uczciwie podać procentowej skuteczności Borowika.

### 14.2 Backtest pogodowy GBIF

Procedura w `notebooks/03_backtest_gbif.py`:

1. Pobranie polskich rekordów `Boletus edulis` z koordynatami i bez zgłoszonego problemu geoprzestrzennego.
2. Wymaganie dnia, miesiąca i roku oraz podanej niepewności współrzędnych nie większej niż 1000 m. To przybliżony filtr jakości lokalizacji, nie dowód braku ukrywania miejscówek.
3. Wybór obserwacji od 2015 roku, starszych od przyjętego opóźnienia archiwum. Limit próbki 200, losowanie warstwowe po roku ze stałym ziarnem 42, a następnie ograniczenie lat do 2023 ze względu na dostępny cache.
4. Ostateczny zapisany zbiór: 90 rekordów z lat 2016–2023. Liczebności: 2, 2, 4, 7, 9, 7, 36 i 23. Ponad połowa próbki pochodzi z dwóch ostatnich lat.
5. Lokalizacje są przyciągane do siatki pogody 5 km i klimatologii 200 km. Ta ostatnia jest znacznie rzadsza niż produkcyjna; stary komunikat „20km grid” w notebooku nie zgadza się ze stałą 200000 m.
6. Dla każdego punktu i roku liczone są wyniki dni kandydujących o numerach 152–304, odpowiadających 1 czerwca–31 października w roku nieprzestępnym, oraz dnia znaleziska. Przyjęta klasa wilgotności siedliska to 1, bez dopasowania do wydzielenia BDL.
7. Metryką jest ranga wyniku dnia znaleziska względem dni porównawczych z tego samego punktu i roku. Remisy otrzymują połowę udziału. Wartość referencyjna przy braku związku wynosi około 0,5.

`rank = udział dni o wyniku niższym + 0,5 × udział dni o wyniku równym`

Poniższe liczby przeliczono ponownie z lokalnego CSV, nie z ponownie pobranej pogody. [S13, S17]

| Wariant | Średnia ranga | Mediana | Znaleziska w górnym kwartylu | W dolnym kwartylu |
|---|---|---|---|---|
| F_loc z sezonowością | 0,677 | 0,711 | 41/90 = 45,6% | 4/90 = 4,4% |
| F_loc bez sezonowości | 0,626 | 0,693 | 40/90 = 44,4% | 13/90 = 14,4% |
| Sama wilgotność M | 0,617 | 0,644 | 38/90 = 42,2% | 11/90 = 12,2% |
| Sama temperatura T | 0,595 | 0,676 | 22/90 = 24,4% | 18/90 = 20,0% |

Wynik 0,626 oznacza średnie uplasowanie dnia obserwacji około 62,6. percentyla w danym porównaniu. Nie oznacza 62,6% udanych wskazań. Notebook oblicza również test Wilcoxona względem 0,5 i test t; ich wartości nie są zapisane w tym CSV i nie przedstawiono ich tu jako ponownie odtworzonych.

Ograniczenia: presence-only, brak obserwacji „szukano i nie znaleziono”, nieznany wysiłek, możliwe zależności między rekordami tego samego obserwatora/miejsca, mała próba, szerokie okno sezonu i przybliżenie klimatologii 200 km. Sezonowość pochodzi z tej samej rodziny danych GBIF, więc wynik z G_season jest częściowo kołowy. Wynik bez G_season usuwa tę bezpośrednią składową, ale nie gwarantuje całkowitego oddzielenia temperatury od kalendarza sezonu.

Nie jest to backtest produkcyjnego miksu radaru i prognozy. Historyczne cechy pochodzą z archiwum Open-Meteo. Nie testowano w tym eksperymencie jakości prognoz wydanych z kilkudniowym wyprzedzeniem. Nie ma wersjonowanego manifestu łączącego zapisany CSV z dokładnym profilem użytym w chwili generacji.

### 14.3 Radar wobec stacji

Udokumentowana kontrola z 27.09.2026 dotyczyła czterech stacji Weathercloud i okresu 13–23.09.2026, czyli 11 dób z pełnymi godzinami archiwum. Dla stacji próbkowano pojedynczą komórkę radaru, a nie blok 4 km produkcyjnej analizy 20 km. MAE oznacza średni błąd bezwzględny:

`MAE = (1/N) × suma |opad_oszacowany − opad_stacji|`

| Stacja | MAE RainGRS w mm na dobę | MAE Open Meteo w mm na dobę |
|---|---|---|
| S1 | 0,93 | 1,41 |
| S2 | 0,27 | 1,12 |
| S3 | 0,54 | 1,04 |
| S4 | 0,37 | 1,65 |

Są to wyniki historyczne z notatki (25), nie nowy pomiar. Starszy prototyp podawał minimalnie inne wartości. Wybrano późniejsze liczby odpowiadające wdrożonej ścieżce. Stacje są traktowane jako lokalny punkt odniesienia; nie ma tu udokumentowanej pełnej oceny jakości ich urządzeń ani niezależności od wszystkich źródeł użytych w produkcie radarowym.

Kod porównania zamienia brak obserwacji stacji lub brak doby radarowej na 0 w wybranych miejscach. Przy odtwarzaniu eksperymentu trzeba potwierdzić kompletność danych, aby brak nie stawał się sztucznie suchą dobą. Wynik nie daje podstaw do uogólnienia MAE na cały kraj, inne sezony i wszystkie typy opadów.

### 14.4 Radar wobec klimatologii

W historycznym porównaniu dla siatki Będziemyśl 20 km, 144 punktów i okresu sierpień–wrzesień 2025, wykorzystano 59 kompletnych dni. Stosunek sum radar/archiwum wyniósł 0,848; sumy po punktach i dniach około 13985 oraz 16494 mm. Nie są to sumy jednego deszczomierza. Stosunki punktowe: średnia 0,853, odchylenie 0,104, zakres 0,635–1,147. [S15, S16]

Plan zakładał akceptację 0,85–1,15; odchylenie poniżej dolnej granicy o 0,002 zaakceptowano decyzją użytkownika bez korekty opadów. To porównanie dwóch produktów, a nie wykazanie, który jest prawdą. Nadal istnieje ryzyko porównywania bieżącego CWB z innego źródła z historycznym rozkładem norm.

### 14.5 Jedna obserwacja terenowa

Notatka z 26.09.2026 opisuje około dwugodzinny spacer w poleconym rejonie, około dziesięciu starych grzybów, głównie podgrzybków i dwóch koźlarzy, oraz dwa małe owocniki, w tym jednego borowika. Zaobserwowano ślady innych grzybiarzy i wskazano ruch rowerowy po duktach. [S16]

To cenna obserwacja jakościowa: uwidoczniła różnicę między „warunki sprzyjają” a „trwa młoda fala” i ograniczenie presji. Nie jest reprezentatywną próbą do obliczenia skuteczności modelu ani dowodem nieskuteczności wszystkich rekomendacji.

## 15 Odrzucony model fazy wysypu

Eksperyment w `pipeline/flush.py` zakładał, że dostatecznie duży epizod deszczu uruchamia zegar termiczny. Detekcja pulsu dopuszczała jeden suchy dzień między mokrymi. Siła pulsu:

`strength = min[1; suma_opadu / (2 × próg_pulsu)]`

Po ostatnim mokrym dniu przyrost czasu termicznego wynosił:

`DD_doba = max(0; Tmean − T_base)`

Przy `Tmin < próg_chłodnej_nocy` przyrost mnożono przez 0,5. Mróz poniżej −1°C kończył falę. Natężenie fali opisano krzywą Gaussa:

`I_fala = strength × exp[−0,5 × ((DD − DD_peak)/DD_sigma)^2]`

Wynik wielu fal był ich maksimum, a wersja osi czasu mogła dodatkowo uwzględniać G_season. Fazy definiowano granicami DD_peak ± 0,5 DD_sigma i ± 2 DD_sigma. Możliwe było ekstrapolowanie okna szczytu z ostatniego tempa przyrostu. [S14]

Przeszukano 144 kombinacje: próg pulsu 10/15/20/25 mm, szczyt 60/80/100/130/160/200 stopniodni, szerokość 20/35/50, temperatura bazowa 4/6°C. Użyto tych samych 90 obserwacji GBIF i walidacji leave-one-year-out: parametry wybierano na pozostałych latach, wynik zapisywano dla wyłączonego roku.

Historyczny wynik poza próbą: średnia ranga 0,548, wobec 0,626 dla F_loc bez G_season. Sparowany Wilcoxon dla różnicy dał p = 0,041, w kierunku gorszego wyniku nowego modelu. Najlepsza kombinacja oceniana na całej próbie dawała 0,599. Warunek wdrożenia wymagał poprawy średniej oraz p < 0,10; nie został spełniony. Model zamrożono.

Diagnostyka porównująca odległość od pulsu między znaleziskami a dniami z całego sezonu dawała pozorny sygnał, KS p około 0,006–0,0008. Po ograniczeniu dni porównawczych do ±15 dni wokół daty każdego znaleziska efekt nie był istotny, p około 0,12–0,84. Interpretacja w notatkach: istotną rolę odgrywało pomieszanie z sezonem, bo chłodniejsze dni gromadzą stopniodni wolniej.

Wniosek ograniczony: ta wersja modelu i ten eksperyment nie uzasadniały wdrożenia. Nie jest to dowód, że czas po deszczu biologicznie nie ma znaczenia. Testy KS po zebraniu wielu zależnych dni do jednej puli mają ograniczenia; model nie uwzględniał stanu wody przed deszczem.

Kod eksperymentu pozostał w repozytorium. Produkcyjny panel importuje z niego pomocniczą detekcję opadów i formatowanie, ale nie krzywą Gaussa, zegar ani prognozę faz. Samo znalezienie importu `pipeline.flush` nie dowodzi używania odrzuconego modelu.

## 16 Historia rozwiązań odrzuconych zastąpionych i odłożonych

Poniższy rejestr rozdziela decyzje o jakości modelu od ograniczenia zakresu produktu. [S01, S16, S20–S22]

**Zastąpione po wykryciu błędu lub problemu:**

- Średnia 50/50 percentyli bilansu i gleby została zastąpiona wagą gleby zero z powodu niespójności modeli i przestrzennych artefaktów.
- Cache percentyli per komórka klimatologii zastąpiono cache per punkt pogody. Wcześniej pierwsze wydzielenie mogło narzucać M wszystkim punktom w dużej komórce.
- Grupowanie przez bufory i łączenie łańcuchowe zastąpiono ograniczonymi oknami. Stary algorytm tworzył na realnych danych rejon około 187 km² i 4747 wydzieleń.
- Odległość do centroidu drogi zastąpiono odległością do jej geometrii. Routing przyspieszono indeksem cKDTree i jednym Dijkstrą dla wielu wejść.
- Powielanie składu przez wieloczęściowe geometrie BDL naprawiono deduplikacją; dodano kontrolę udziałów ponad 100%, gdyż błąd pozwalał uzyskać H ponad 1.
- Brakujące kody drzew i siedlisk wyżynnych uzupełniono w profilu. Historyczny fallback 0,5 obejmował zbyt dużą część danych.
- Środek funkcji wilgotności przesunięto z 0,35 do 0,50, aby przeciętne warunki nie otrzymywały od razu bardzo wysokiej oceny. Była to korekta zachowania wskaźnika, nie kalibracja terenowego prawdopodobieństwa.
- Dawny brak faktycznego wpływu daty i ograniczenie analizy do jednego kafla zastąpiono pogodą do terminu wyjazdu i wielokaflowym kołem.

**Odrzucone jako bieżące składniki modelu:**

- Model fazy wysypu po deszczu nie przeszedł opisanej bramki GBIF.
- Dalsze różnicowanie H dodatkowymi wagami zwarcia, gleby lub podszytu odłożono z braku terenowej walidacji. Dane są informacyjne.
- Domieszka drzew z sąsiedztwa jako zastępstwo pełnego składu została skreślona po uzyskaniu prawdziwych paczek BDL, także z powodu braku uzasadnionej wagi.
- Krawędź lasu liczona z obwodu wydzielenia nie weszła do H. Audyt wykazał, że większość granic wydzieleń jest wewnętrzna; to zły zamiennik rzeczywistego skraju lasu.
- Sześć skorelowanych sum opadów jako oddzielne predyktory pominięto na rzecz jednego ważonego okna. P1/P3/P7/P14/P21/P30 i dry_spell_days usunięto jako martwe cechy; P5 pozostało potrzebne do kary upału.
- Track nie wchodzi do podstawowej odległości euklidesowej presji, bo wcześniejsze dodanie dróg leśnych spłaszczało tę cechę. Nadal występuje w routingu.
- Path/footway/bridleway nie weszły do obecnego pobierania sieci, ponieważ zapytania z path powodowały błędy Overpass na badanym kaflu. Jest to ograniczenie techniczne, nie twierdzenie o nieistotności ścieżek.

**Świadomie poza zakresem albo nadal niewdrożone:**

- Pełny routing wszystkich wydzieleń, model rowerzystów/pieszych po duktach oraz rzeczywisty pomiar tłoku.
- Własny model magazynu wody w glebie; satelitarna wilgotność SAR, Sentinel, NDVI/NDMI jako predyktory owocnikowania; LST, LAI, VPD i SoilGrids pH.
- Model wysokości, ekspozycji i rzeźby terenu; LiDAR i wysokości koron. Mogłyby być szczególnie istotne dla obszarów górskich, lecz nie są aktywne.
- Heatmapa 10–50 m, ze względu na pozorną precyzję przy znacznie rzadszych źródłach.
- Obowiązkowy dziennik, trening ML, PostGIS, FastAPI, konta, crowdsourcing, aplikacja natywna, hosting i pełne PWA offline.
- Automatyczny codzienny harmonogram i stale działający zbieracz danych. Docelowe użycie to ręczna analiza przed wyjazdem.

Nieaktualna jest starsza teza, że radar wymaga całorocznego własnego kolekcjonowania, bo dostępne archiwum zostało już wykorzystane w A1. Podobnie grupowanie było chwilowo wyłączone, ale w obecnym kodzie znów działa. Nie należy przywracać starych planów jako aktualnych wymagań.

## 17 Walidacja techniczna i stan bieżącego eksportu

### 17.1 Zakres testów

Testy Pythona obejmują wzory i progi, maskę, profile, pogodę, radar, daty, geometrię, pełne składy BDL, dostępność, rejony, eksport, archiwizowanie oraz integrację przepływu z zastępowanymi źródłami sieciowymi. Frontend testuje m.in. parsowanie, łączenie danych, klasy, sortowanie, opcjonalne pliki i synchronizację. [S21]

Historyczna notatka (27) podaje 490 testów Pythona i 65 testów frontendu po A2 Plan-B, a także poprawne sprawdzenie TypeScript i budowę frontendu. Bieżące uruchomienie podczas tego przeglądu potwierdziło 66 testów frontendu: 52 testy modelu interfejsu i 14 synchronizacji. Kontrola TypeScript zakończyła się poprawnie. Nie deklaruje się tutaj nowego pomyślnego pełnego uruchomienia backendu.

Próba uruchomienia lokalnego środowiska Pythona nie mogła wystartować jego interpretera. Próba użycia dostępnego interpretera z bibliotekami projektu zakończyła się 31 błędami podczas zbierania testów z powodu odmowy dostępu przy ładowaniu bibliotek natywnych, m.in. NumPy i pyproj. To blokada środowiska testowego; nie są to 31 negatywnych testów logiki aplikacji. Nie instalowano ani nie zmieniano zależności projektu dla potrzeb tego dokumentu.

Testy jednostkowe potwierdzają działanie implementacji zgodnie z przykładami, lecz nie potwierdzają poprawności biologicznych założeń. W szczególności sprawdzenie wzoru Gaussa lub progu 15 mm nie dowodzi, że rzeczywisty wysyp tak przebiega.

### 17.2 Kontrola zapisanych wyników z 27 września

Ponownie odczytano istniejące pliki; nie wykonano nowej analizy terenowej ani przeliczenia wszystkich źródeł. Kontekst Będziemyśl 20 km wynika z notatek; same scores nie przechowują kompletnego manifestu lokalizacji i parametrów uruchomienia. [S17]

Dodatkowo odtworzono końcowe R ze zapisanych H, F_loc, P i maski przy α = 0,3 dla wszystkich 4703 rekordów. Nie stwierdzono rozbieżności przy tolerancji bezwzględnej 1e-9. Potwierdza to zgodność końcowej arytmetyki eksportu z opisanym wzorem; nie weryfikuje poprawności wejściowych H, F_loc i P.

| Miara dla 3656 wydzieleń przechodzących maskę | Minimum | Mediana | Maksimum |
|---|---|---|---|
| H | 0,000 | 0,787 | 1,000 |
| F | 0,694 | 0,823 | 0,860 |
| F_loc | 0,694 | 0,823 | 0,860 |
| R | 0,000 | 57,403 | 85,444 |
| P | 0,00013 | 0,338 | 0,796 |

„Bardzo dobre” ma 3648 wydzieleń, „Dobre” 8. Wszystkie mają pewność średnią i źródło składu WFS. Odległość sieciową ma 25, przybliżoną 3631. Pokrycie radarowe w zapisanych rekordach wynosi około 86,17%; nie należy podstawiać tu starszej wartości 82% z wcześniejszego biegu.

Maksymalne R = 85,444 dotyczy wydzielenia o powierzchni około 0,116 ha. Jest ono ukrywane jako samodzielny cel przez filtr 0,5 ha. Pokazuje to, dlaczego maksimum eksportu nie musi odpowiadać pierwszej pozycji dostępnej listy użytkownika.

Siedem wartości F obszarowego zapisanych w conditions: 0,787; 0,736; 0,647; 0,538; 0,429; 0,354; 0,297, dla 27.09–03.10.2026. Ostatnie dwa epizody: 21–22.09 z 27,9 mm oraz 11–12.09 z 19,7 mm. Są to wyniki modelu i agregacji dostępne w pliku, nie późniejsze potwierdzenie rzeczywistego przebiegu pogody czy grzybów.

## 18 Najważniejsze kwestie do analizy przez kolejne AI

### 18.1 Priorytet pierwszy wiarygodność danych i odtwarzalność

**Manifest analizy.** Zapisać identyfikator uruchomienia, commit, pełny profil lub jego hash, współrzędne, promień, datę wyjazdu i pobrania, wersje źródeł, modele pogodowe, statusy fallback oraz pokrycie. Bez tego porównania między dniami mogą mieszać zmiany kodu, danych i źródeł.

**Eksport diagnostyczny.** Udostępnić składowe H/F, percentyle, punkt i komórkę klimatologii, źródło opadu, status kontroli zakazu i przyczyny braków. Warunek ukończenia: da się odtworzyć R z zapisanych wejść bez ponownego pobierania API.

**Stan dostępności.** Rozdzielić „sprawdzono brak blokady”, „nie sprawdzono” i „źródło zawiodło”. Obecne `mask = true` nie potwierdza kompletnego sprawdzenia. To szczególnie istotne przy top-50 i pomijaniu GDOŚ.

**Paczki BDL.** Sprawdzić, dlaczego aktualny eksport ma wyłącznie WFS, mimo wcześniejszych analiz z paczkami. Możliwe wyjaśnienia to brak paczek w aktualnym cache, inny katalog uruchomienia lub brak dopasowań; nie ustalono jednej przyczyny. Dodać kontrolę kompletności udziałów i wyboru wersji paczki po dacie.

### 18.2 Priorytet drugi uczciwa walidacja pogody i F

**Zgodność produktów.** Ocenić, jak różnica między radarem a historycznym produktem wpływa na percentyle CWB. Rozważyć porównanie w okresie wspólnym, warstwowanie regionalne i sezonowe, bez mechanicznego mnożenia wszystkiego przez 0,848.

**Walidacja sezonowo dopasowana.** Sprawdzić obecne F bez G_season na kontrolach ±15 dni, z grupowaniem po lokalizacji i roku. Porównać z prostymi bazami: sam kalendarz, samo M, sama T oraz model stały. Oddzielić wybór parametrów od końcowej próby testowej. Wniosek z diagnostyki pulsu nie zastępuje takiego testu dla całego F.

**Prognoza a rekonstrukcja.** Weryfikować osobno horyzonty 0, 1, 3, 6 i 15 dni na prognozach dostępnych w chwili wydania, a nie na późniejszej rekonstrukcji pogody. Obecny backtest historyczny tego nie mierzy.

**Panel obszarowy.** Porównać F z median cech z medianą F po punktach, po wydzieleniach oraz medianą ważoną powierzchnią lasu. Sprawdzić, czy agregacja nie ukrywa lokalnego przymrozku. Dopiero potem przypisywać panelowi zwalidowaną interpretację.

**Saturacja.** Obecne 99,8% etykiet „Bardzo dobre” uzasadnia analizę czułości, ale nie automatyczne wymuszanie równej liczby klas. Możliwe, że warunki w całym obszarze są podobne. Zmiana progu tylko po to, by mapa była bardziej kolorowa, nie dowodzi poprawy jakości.

### 18.3 Priorytet trzeci stabilność rankingu i dostępność

**Wpływ promienia.** Porównać te same wydzielenia dla 10, 20, 25 i 50 km. Oddzielić skutki siatki pogodowej, bloków radaru, klimatologii, lokalnej normalizacji Demand i kompletności OSM.

**Top-25 routing.** Sprawdzić stabilność po przeliczeniu większej puli i po ewentualnym powtórzeniu wyboru. Dzisiejsze mieszanie metod może tworzyć skok jakości danych w pobliżu granicy rankingu. Nie usuwać mnożnika 1,3 bez porównania, bo zmieni to znaczenie P.

**Ruch pieszy i rowerowy.** Rozbudowa wymaga oddzielnego modelu dostępu, nie prostego dodania wszystkich track do aktualnego minimum odległości. Dane o populacji bez wpisanej liczby i drogi bez tagów dostępu należy traktować jako niepewność, nie jako pustkę.

**Rejony.** Ocenić ciągłość dojścia, stabilność kwantyla przy remisach oraz relację między oceną okna a medianą top-5. Analiza nie powinna zakładać, że pięć rejonów zawsze oznacza pięć niezależnych kompleksów leśnych.

### 18.4 Konkretne hipotezy techniczne do sprawdzenia

1. Daty w backteście 03 są numerowane z timestampów UTC, natomiast notebooki 06/09 jawnie konwertują je do Europe/Warsaw. Ponieważ źródło reprezentuje lokalną północ jako chwilę UTC, możliwy jest przesuw dnia między eksperymentami. Potrzebna jest weryfikacja na faktycznych wierszach cache; nie korygowano tu raportowanych wyników bez ponownego przeliczenia.
2. Scalenie radaru stosuje korektę daty o południe dla zmiany czasu, ale `with_local_date` i agregacja opisu opadu takiej korekty nie mają. Potrzebny wspólny test na dobie przejścia czasu letniego i zimowego.
3. Pusta klimatologia daje percentyl 0,5, lecz nie obniża osobno pewności. Braki NaN oraz niepełne okna mogą mieć inne zachowanie niż pusty zbiór.
4. Określenie „fakty o deszczu” wymaga metadanych rozróżniających opad zmierzony, uzupełniony i prognozowany, zwłaszcza dla dzisiaj.
5. Panel stosuje próg radarowy według flagi użycia, a nie uzyskanego pokrycia. Przypadek całkowitego fallbacku wymaga kontroli.
6. Teksty uzasadnień, etykieta wilgotności dla złożonego F, stały opis rozdzielczości około 2 km oraz dawne README mogą nie odpowiadać obliczeniom. Trzeba poprawić znaczenie, nie tylko wygląd.
7. Nie ma sprawdzenia sumy udziałów paczki bliskiej 1 od dołu ani pełnego wersjonowania cache przy zmianie parametrów; możliwe są ciche zmiany znaczenia wartości.

Każdy z tych punktów wymaga minimalnego testu reprodukcyjnego. Nie wszystkie są już udowodnionym błędem produkcyjnego wyniku z 27 września.

## 19 Instrukcja wykorzystania dokumentu przez AI

AI analizujące ulepszenia powinno traktować ten dokument jako opis konkretnego stanu kodu, a nie jako potwierdzoną teorię ekologii borowika. Najpierw należy odróżnić błąd obliczeniowy, słabą jakość wejścia, brak walidacji i świadomą decyzję produktową. Zmiana tych kategorii wymaga innych dowodów.

Przy każdej propozycji warto podać: problem i dowód, zmieniane pliki, przewidywany wpływ na H/F/P/R lub tylko prezentację, potrzebne dane, plan testu, miernik sukcesu i koszt utrzymania. Nie proponować dodatkowego złożonego źródła tylko dlatego, że jest dostępne. Najpierw sprawdzić, czy prostsza poprawka usuwa konkretny problem.

Priorytetem jest możliwość odtworzenia wyniku i oceny ulepszeń. Nie należy traktować 0,626 jako accuracy, etykiety „SREDNIA” jako przedziału ufności, nominalnego radaru 1 km jako rozdzielczości rekomendacji ani obecności modułu flush jako wdrożonej prognozy szczytu.

Jeżeli zaproponowano nowy model, porównanie powinno zachować tę samą próbę, warunki sezonowe i geografię oraz wyraźnie rozdzielić dostrajanie od testu. Nie reanimować zamrożonego modelu fali bez nowej hipotezy i nowego testu. Nie uznawać dopasowania do wyglądu pojedynczej mapy za potwierdzenie jakości biologicznej.

Docelowo ocenę skuteczności całej aplikacji mogłyby umożliwić wizyty o porównywalnym wysiłku w miejscach różnie ocenionych, również bez znalezisk. To opcjonalny kierunek badawczy, nie warunek korzystania z obecnego narzędzia. Bez takich danych trzeba pozostawić uczciwe ograniczenie: ranking ekspercki z częściową walidacją składowych.

## 20 Mapa źródeł do dalszej pracy

Poniższe lokalizacje wskazują główne źródła ustaleń. Nazwa funkcji jest trwalszym identyfikatorem niż numer linii po kolejnych zmianach. Stan odniesienia to commit podany na początku dokumentu, uzupełniony lokalnymi nieśledzonymi eksportami. `uv.lock`, `CLAUDE.md` oraz część publicznych danych frontendu miały lokalne różnice lub status nieśledzony już przy rozpoczęciu przeglądu.

- **S01** `profiles/boletus_edulis.yaml` — pełna aktywna konfiguracja, komentarze decyzji i parametry zamrożonego eksperymentu.
- **S02** `pipeline/prepare_trip.py` — `parse_args`, `_radius_scaled_spacing`, `build_weather_fetcher`, `run_trip_preparation`, `points_within_radius`.
- **S03** `pipeline/bdl.py`, `pipeline/rdlp.py`, `pipeline/search_area.py`, `pipeline/tiles.py` — pobieranie, normalizacja, promień, RDLP i cache kafli.
- **S04** `pipeline/bdl_packages.py`, `pipeline/bdl_package_details.py`, `pipeline/bdl_dictionaries.py`, `pipeline/neighbors.py` — skład i szczegóły BDL.
- **S05** `pipeline/weather.py` — `compute_weather_features`, `fetch_weather_raw`, `fetch_climatology_raw`, `climatology_window_values`, `percentile_rank`, zapytania API i cache punktów.
- **S06** `pipeline/radar.py` — `sample_stack`, `radar_daily_at_points`, `merge_radar_into_daily`, `make_radar_weather_fetcher` i założenia czasowe.
- **S07** `pipeline/habitat.py`, `pipeline/orchestrate.py` — maska, H, przypisanie punktów, percentyle, uruchomienie składowych.
- **S08** `pipeline/scoring.py`, `pipeline/phenology.py` — M, T, przymrozek, F, F_loc, ranking i interpolacja sezonowa.
- **S09** `pipeline/access_points.py`, `pipeline/access_pressure.py`, `pipeline/access_data.py`, `pipeline/population_grid.py`, `profiles/boletus_edulis.yaml` (`pressure.access_points`), `pipeline/pressure.py`, `pipeline/osm.py`, `pipeline/entrances.py`, `pipeline/routing.py`, `pipeline/mvp.py` — punkty dostępu, model Huffa, korytarze, P (oba tryby), wejścia, graf, top-N i R_final.
- **S10** `pipeline/gdos.py`, `pipeline/zakazy.py`, `pipeline/confidence.py`, `pipeline/explain.py` — wykluczenia, pewność i uzasadnienia.
- **S11** `pipeline/regions.py`, `pipeline/tie_break.py` — wybór rejonów, geometria i klucz remisów.
- **S12** `pipeline/conditions_timeline.py` — `recent_rains`, `build_conditions_timeline`, rozdzielenie panelu od rankingu.
- **S13** `notebooks/03_backtest_gbif.py` — filtr próby, siatki, konstrukcja rang i raport statystyczny.
- **S14** `pipeline/flush.py`, `notebooks/06_backtest_flush.py`, `notebooks/08_flush_pulse_timing_diagnostic.py`, `notebooks/09_flush_pulse_timing_season_controlled.py` — eksperyment i diagnostyki.
- **S15** `notebooks/04_radar_vs_stations.py`, `notebooks/05_radar_era5_bias.py` — protokoły porównań opadów; wartości historyczne także w S16.
- **S16** `docs/archiwum/CODEX-HANDOFF.md` — szczególnie notatki (27), (26), (25), (23), (22), (20), (19), (15), (14) i (13). Historia wyników i decyzji, nie jednolita aktualna specyfikacja.
- **S17** `notebooks/output/backtest_gbif_results.csv`, `scores_2026-09-27.json`, `regions_2026-09-27.json`, `conditions_2026-09-27.json` — lokalne artefakty wyników. Trzy nazwy JSON odnoszą się do tego samego katalogu `notebooks/output/`.
- **S18** `pipeline/export.py`, `frontend/src/model.ts`, `frontend/src/main.ts`, `frontend/src/map.ts`, `frontend/src/storage.ts`, `frontend/scripts/sync-data.mjs` — kontrakty danych i prezentacja.
- **S19** `launcher/launcher.pyw`, `launcher/trip_archive.py`, `frontend/package.json`, `pyproject.toml` — uruchomienie, migawki i stos technologiczny.
- **S20** `docs/archiwum/projekt-borowik.md` — uzasadnienia zakresu, zwłaszcza sekcje 0.1, 5, 11, 13–16; zawiera również opisy już zastąpione.
- **S21** `tests/`, `frontend/src/model.test.ts`, `frontend/scripts/sync-data.test.mjs` — testy techniczne; wynik ich uruchomienia opisano w rozdziale 17.
- **S22** `docs/archiwum/superpowers/plans/2026-09-27-borowik-wysyp-a2.md`, `2026-09-26-borowik-radar-opady-a1.md`, `2026-09-25-borowik-fenologia-wilgotnosc-tiebreak.md`, `docs/archiwum/bdl-paczki-rozpoznanie.md` — plany, bramki i rozpoznanie źródeł. Dwie skrócone nazwy datowane odnoszą się do tego samego katalogu `docs/archiwum/superpowers/plans/`.

### 20.1 Niespójności dokumentacji które trzeba pamiętać

README frontendu i CLAUDE.md nadal miejscami wskazują dawny worktree jako jedyną aktualną implementację, a część README mówi o wyłączonym grupowaniu i dacie będącej tylko etykietą. Przegląd dotyczył kodu obecnego w katalogu głównym Grzyby, gdzie grupowanie, prognoza do daty i panel warunków są zaimplementowane. Stare twierdzenia o braku danych szczegółowych również nie opisują wszystkich obecnych możliwości.

Notatki zawierają wyniki z kilku kolejnych wersji tego samego dnia, między innymi sprzed napraw percentyli i wyłączenia gleby. Ich liczb nie należy łączyć w jeden rzekomo aktualny przebieg. W rozdziale 17 podano osobno liczby odczytane z dostępnego końcowego eksportu.

W opisach historycznych słowo „kalibracja” bywa używane dla ręcznej zmiany progu lub oceny rozkładu wyników. Nie jest to równoważne kalibracji prawdopodobieństwa na niezależnych wynikach terenowych. To rozróżnienie powinno pozostać zachowane w każdej kolejnej analizie i prezentacji produktu.
