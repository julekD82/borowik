# Rozpoznanie: paczki danych BDL per nadleśnictwo (plan 2.1, krok B1)

> Data: 2026-09-24. Zakres: **rozpoznanie, nie integracja** — kod `pipeline/` nie
> został zmieniony. Referencje: `docs/projekt-borowik.md` §13.1 (plan 2.1, wiersz
> B1) i §3.1 "Do sprawdzenia w pierwszej kolejności (2.1)".

## Skrót wyniku

**Tak — zweryfikowane na realnej paczce Nadl. Kędzierzyn (nie tylko na
dokumentacji schematu).** Portal BDL udostępnia paczki per nadleśnictwo z
pełnym opisem taksacyjnym: **pełny skład gatunkowy z udziałami per piętro
drzewostanu (98,3% wydzieleń ma >1 gatunek w warstwie drzew)**, **zwarcie
(88% wypełnienia)**, **podszyt jako osobna, dobrze wypełniona warstwa (78%
wydzieleń)** i **typ/podtyp gleby (98,7% wypełnienia)**. Pole `adr_for` w
paczce jest **bajt-w-bajt identyczne** ze stringiem z WFS dla tego samego
wydzielenia — join jest trywialny, bez żadnego przetwarzania. To w pełni
potwierdza nadzieję z §3.1: **to jest największy możliwy zysk dla
różnicowania H bez zgadywanych wag.**

**Rekomendacja: integrujemy w B2.**

## Jak dane zostały pozyskane

Pobranie paczki wymaga formularza interaktywnego
(`bdl.lasy.gov.pl/portal/wniosek`: e-mail + zgoda RODO + wybór roku i
nadleśnictwa; brak logowania/konta, ale są dane osobowe i zgoda). Zgodnie z
poleceniem zadania **zatrzymałem się przed wysłaniem formularza i zapytałem
użytkownika**. Użytkownik podał e-mail (`[adres e-mail usunięty]`) i zgodę;
wniosek złożony dla RDLP Katowice → Nadl. Kędzierzyn, rok 2026. Portal nie
daje pliku od razu — wysyła link e-mailem. Użytkownik przekazał ten link w
kolejnej wiadomości; paczka (`BDL_02_10_KEDZIERZYN_2026.zip`) pobrana stąd i
przeanalizowana. Wszystkie pliki (paczka + dokumentacja schematu pobrana
wcześniej z publicznego linku, bez formularza) leżą w `cache/bdl_research/`
— **poza repo, gitignored, nic z tego nie jest commitowane**.

## Format, rozmiar, zawartość

- **Rozmiar:** 1,26 MB spakowane, **4,9 MB rozpakowane** dla jednego
  nadleśnictwa (Kędzierzyn: 4137 wydzieleń/obiektów, w tym 2676 `D-STAN`).
  Rząd wielkości dla regionu domowego (~64 kafle 10×10 km z §8.1, kilka do
  kilkunastu nadleśnictw) to więc pojedyncze dziesiątki MB — nieistotne
  obciążenie w porównaniu do NMT/S2 z sekcji 7.1.
- **Format:** pliki `SHP`+`dbf`+`prj` (geometria: `G_SUBAREA`,
  `G_COMPARTMENT`, `G_FOREST_RANGE`, `G_INSPECTORATE`) + pliki `TXT`
  tabulator-separated (opis taksacyjny). **Kodowanie realnie UTF-8**
  (zweryfikowane `file`/pandas, nie tylko deklaracja w `.cpg`) — instrukcja
  BDL o ręcznej zmianie kodowania w QGIS dotyczy najwyraźniej tylko
  domyślnego wykrywania sterownika QGIS, nie samego pliku.
- **Metadane paczki** (`metadane.txt`): `Rok stanu danych: 2026`, `Data
  wytworzenia danych: 2026-06-23` — czyli to jest **migawka z czerwca**, nie
  gwarantowanie tak świeża jak WFS w danym dniu. Do uwzględnienia w
  `data_quality`/`confidence` (§10), jeśli paczka zostanie zintegrowana:
  potrzebne odświeżanie okresowe (wniosek ponownie, nie ma API), nie
  codzienne jak WFS.
- **Licencja** (plik `warunki_wykorzystania.txt` w samej paczce, identyczny
  tekst co w formularzu): ustawa z 11.08.2021 o otwartych danych i
  ponownym wykorzystywaniu informacji sektora publicznego (Dz.U. 2021 poz.
  1641, zm. 2022 poz. 1700). Obowiązek: (1) podać źródło, czas wytworzenia
  i pozyskania, (2) przekazywać dalej w formie pierwotnej, (3) informować
  DGLP/operatora BDL o przetworzeniu (e-mail na `bdl@bdl.lasy.gov.pl`).
  Brak odpowiedzialności cywilnoprawnej LP/operatora. Brak wzmianki o
  zakazie użytku komercyjnego.

## Tabele i pola — zweryfikowane na realnych danych

Wszystkie tabele z dokumentacji schematu (`OpisDanych.pdf`) są obecne w
paczce dokładnie tak, jak opisane; poniżej tylko to, co dodaje realna
zawartość ponad sam schemat.

**`f_arod_storey.txt` — 13 kodów warstw, z realnym `f_storey_dic.txt`:**

| `storey_cd` | Znaczenie | Wydzieleń D-STAN z tą warstwą (z 2676) |
|---|---|---|
| `DRZEW` | warstwa drzew (główny drzewostan) | 2674 (99,9%) |
| **`PODSZ`** | **podszyt** | **2086 (78%)** |
| `PRZES` | przestoje, nasienniki, przedrosty | 874 (33%) |
| `PODR` | podrost | 190 (7%) |
| `PODS` | podsadzenia pod osłoną | 95 (4%) |
| `PODRII` | podrost o charakt. II piętra | 33 (1%) |
| `NAL` | nalot | 8 |
| `IP`, `IIP` | piętro pierwsze/drugie | po 2 |
| `PLANT`, `SAMOS`, `ZADRZEW`, `ZAKRZEW` | plantacja choinkowa, samosiew, zadrzewienie, zakrzewienie | 0 w tej próbce |

**Podszyt istnieje jako osobna warstwa i jest dobrze wypełniony** — §3.1
pytał o to wprost, odpowiedź jest **tak**, nie tylko "prawdopodobnie" jak w
poprzedniej wersji tej notatki (przed dostępem do realnej paczki).
`density_cd` (zwarcie) na warstwie `DRZEW`: **wypełnione dla 87,8%**
wydzieleń D-STAN.

**`f_storey_species.txt` — skład gatunkowy, warstwa `DRZEW` (2674
wydzieleń, 21 459 wierszy gatunek×wydzielenie):**

- Tylko **46 wydzieleń (1,7%) ma dokładnie 1 gatunek** w warstwie drzew —
  **98,3% ma więcej**, mediana ok. 6–8 gatunków na wydzielenie, ogon do
  39 gatunków w jednym wydzieleniu.
- `part_cd_act` (udział) i `species_age` (wiek gatunku) wypełnione w
  **100%** wierszy warstwy `DRZEW`.
- Najczęstsze gatunki w `DRZEW`: DB, BRZ, SO, ŚW, OL, DB.C, MD, BK, LP,
  CZM, JW, GB, WZ, OS, KL — niemal wszystkie mają już wpisy w
  `profiles/boletus_edulis.yaml::host_affinity` (uzupełnione w kroku A1).
- Gatunek o `sp_rank_order_act = 1` w warstwie `DRZEW` **zgadza się w
  100% (2681/2681 porównanych wydzieleń)** z `species_cd`/`part_cd` z
  `G_SUBAREA` (odpowiednik `species_cd`/`part_cd` z WFS) — potwierdza, że
  ranga 1 to dokładnie "gatunek panujący", ta sama definicja co dziś w
  `pipeline/habitat.py::score_host`.
- Podszyt (`PODSZ`) ma **własny, częściowo inny skład gatunkowy**: CZM,
  BRZ, **KRU** (kruszyna), CZM.P, ŚW, DB, BK, **JRZ** (jarząb — inny kod niż
  `JB` widziany w `species_cd` z WFS/A1; do wyjaśnienia przy integracji,
  czy to ten sam gatunek pod innym kodem czy inny słownik), DB.C, OL. Kilka
  z tych kodów (`KRU`, `JRZ`) **nie ma jeszcze wpisu w profilu** — istotne
  tylko jeśli B2 zdecyduje się używać podszytu w scoringu, nie dla samej
  warstwy `DRZEW`.

**`f_subarea.txt` — typ gleby:** `soil_subtype_cd` wypełnione dla **98,7%**
wydzieleń D-STAN (2676 sprawdzonych). Najczęstsze podtypy w Kędzierzynie:
`Bw`, `RDb`, `Bgw`, `RDw`, `OGb`, `OGw`, `Gw`, `MRms`, `Pog`, `MDbr` —
rozwijane przez `f_soil_subtype_dic.txt` (110 kodów łącznie).

**Join z `adr_for` — zweryfikowany bajt-w-bajt na realnym wydzieleniu:**
wydzielenie `02-10-1-05-317   -d   -00` (to samo, które posłużyło jako
przykład w §5.3 "Poprawka wyjaśnień"/kroku A4: BK, 4/10 udziału) ma w
`G_SUBAREA` z paczki **dokładnie ten sam string** `adr_for`, ten sam
`species_cd=BK`, `part_cd=4`, `site_type=LMW`, co w cache WFS
(`cache/bdl_tiles_v2`) tego projektu. **Zero przetwarzania stringów
potrzebne do joina.**

## Co nadal nie sprawdzone / do decyzji w B2

- Czy inne nadleśnictwa (spoza Kędzierzyna) mają podobnie wysokie
  wypełnienie, czy Kędzierzyn jest akurat lepiej opisany niż przeciętna.
  Jedna próbka to nie dowód dla całej Polski.
- Znaczenie kodów `KRU`/`JRZ` (podszyt) względem istniejących kodów
  profilu — do ustalenia przed użyciem składu podszytu w H.
- Strategia odświeżania: paczka to migawka (tu: z czerwca), nie ma API do
  automatycznego pobierania jak WFS — pobieranie przez wniosek e-mail
  najwyżej okresowo (rocznie?), nie da się wpiąć w codzienny cron.
- Czy `part_cd_act` sumuje się do 10 w obrębie jednej warstwy (nie
  sprawdzone arytmetycznie) — istotne dla wzoru `S_host = Σ udział_i ×
  powinowactwo_i` z §5.3.

## Rekomendacja

**Integrujemy w B2.** Uzasadnienie, teraz oparte na realnych danych, nie
tylko na schemacie:
1. Skład gatunkowy z udziałami jest **faktycznie i gęsto wypełniony**
   (98,3% wydzieleń ma >1 gatunek, 100% wypełnienia `part_cd_act`) — to
   bezpośrednio zastępuje "nieznaną domieszkę 0,5" z §5.3 realnymi danymi,
   dla niemal każdego wydzielenia, nie tylko wybranych przypadków.
2. Zwarcie i typ gleby też są dobrze wypełnione (88% i 98,7%) — dodatkowe
   kandydatki na cechy H poza pierwotnym zakresem §3.1.
3. Join z `adr_for` jest bezkosztowy (identyczny string).
4. To jedyne zidentyfikowane źródło, które może rozbić płaskowyż 745
   wydzieleń z R ≥ 90 (§0.1) bez nowych, zgadywanych wag eksperckich.

**Zakres B2 (poza tym dokumentem, do osobnego planu):** sparsować pełny
skład `F_STOREY_SPECIES` (warstwa `DRZEW`) per wydzielenie, zastąpić
`unknown_host_affinity` realnym `Σ udział_i × powinowactwo_i`, obsłużyć
wydzielenia bez paczki (fallback na dzisiejszy WFS-owy `species_cd`/
`part_cd`), zdecydować co z podszytem (informacja na karcie vs. wpływ na
H — pytanie analogiczne do "domieszki z sąsiedztwa" z §5.3 pkt 2/3),
ustalić harmonogram odświeżania paczek per nadleśnictwo w regionie domowym.
