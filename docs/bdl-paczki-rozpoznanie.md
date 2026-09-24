# Rozpoznanie: paczki danych BDL per nadleśnictwo (plan 2.1, krok B1)

> Data: 2026-09-24. Zakres: **rozpoznanie, nie integracja** — kod `pipeline/` nie
> został zmieniony. Referencje: `docs/projekt-borowik.md` §13.1 (plan 2.1, wiersz
> B1) i §3.1 "Do sprawdzenia w pierwszej kolejności (2.1)".

## Skrót wyniku

**Tak, portal BDL udostępnia paczki danych per nadleśnictwo z pełnym opisem
taksacyjnym** — w tym **pełny skład gatunkowy z udziałami per piętro**,
**zwarcie** i **typ/podtyp gleby**. To potwierdza nadzieję z §3.1: jeśli dane
rzeczywiście są wypełnione (patrz "Co założone, nie zweryfikowane" niżej), to
jest to największy możliwy zysk dla różnicowania H bez zgadywanych wag.

**Pobranie nie jest jednak samoobsługowym plikiem do kliknięcia** — wymaga
wypełnienia formularza (e-mail + zgoda RODO) i przyjścia linku pocztą.
Zgodnie z poleceniem zadania, przed wysłaniem tego formularza **zatrzymałem
się i zapytałem użytkownika**; otrzymałem zgodę i adres e-mail, złożyłem
wniosek dla Nadl. Kędzierzyn (RDLP Katowice, rok 2026), ale **e-mail ze
sposobem pobrania danych trafia na skrzynkę użytkownika, do której nie mam
dostępu** — sama zawartość paczki (rzeczywiste wartości pól, rozmiar pliku)
jest więc **nadal niezweryfikowana** i wymaga kroku po stronie użytkownika
(przesłania linku/pliku). Rekomendacja niżej jest oparta na oficjalnej
dokumentacji schematu, nie na przejrzeniu realnych danych.

## Co sprawdzone (źródła, bez logowania, bez scrapowania popupów)

Wszystko poniżej pobrane z jawnie linkowanych, publicznych dokumentów na
`bdl.lasy.gov.pl/portal/o-udostepnianiu` — **nie z wniosku interaktywnego**,
więc nie wymagało żadnej personalizacji ani zgody. Pliki zapisane w
`cache/bdl_research/` (poza repo, gitignored):

- `opisdanych_datadescription.zip` → `OpisDanych.pdf` (11 str., PL),
  `DataDescription.pdf` (EN), `ModelDanych_DataModel.pdf` (diagram ER) —
  pełny opis schematu pakietu danych.
- `katalog_informacji_udostepnianych_z_bdl.pdf` (2 str.) — skrócona lista
  udostępnianych informacji, potwierdza `OpisDanych.pdf`.
- `sektor-publiczny.pdf` (37 str.) — pełny tekst ustawy licencyjnej (patrz
  "Licencja" niżej), pobrany dla kompletności, nie analizowany strona po
  stronie (treść generycznej ustawy, nie specyficznej dla BDL).

### Format i sposób pobierania

- Pakiet = **pliki SHP** (geometria) + **pliki TXT** (opis taksacyjny,
  separator tabulacji, kodowanie nie zawsze poprawnie rozpoznawane — instrukcja
  BDL każe ręcznie ustawić UTF-8 przy wczytywaniu do QGIS).
- Pobranie **wymaga formularza interaktywnego**
  (`bdl.lasy.gov.pl/portal/wniosek`): e-mail (wymagany), rok danych
  (2015–2026), wybór jednego lub więcej nadleśnictw z drzewa RDLP →
  nadleśnictwo, opcjonalna warstwa granic zasięgów nadleśnictw, akceptacja
  warunków wykorzystania danych i zgoda RODO na przetwarzanie e-maila. **Nie
  ma logowania/konta** — to jednorazowy formularz, ale zawiera dane osobowe
  (e-mail) i zgodę RODO, więc zgodnie z poleceniem zadania zatrzymałem się i
  zapytałem, zanim go wysłałem.
- Po wysłaniu formularza: strona potwierdza *"Informacja o sposobie
  pobrania zamówionych danych została wysłana na podany w formularzu adres
  email"* — czyli **nie ma natychmiastowego pobrania w przeglądarce**, sam
  link/plik przychodzi mailem. Nie mam dostępu do tej skrzynki.
- Dla nadleśnictwa spoza standardowego pakietu (dane niestandardowe) trzeba
  złożyć osobny wniosek o ponowne wykorzystanie informacji sektora
  publicznego (`bdl@bdl.lasy.gov.pl`) — nie dotyczy standardowego pakietu
  taksacyjnego, którego dotyczy ten dokument.

### Tabele i pola (z `OpisDanych.pdf`, sekcja A)

**Tabele opisowe (TXT), klucz `arodes_int_num` + `a_year`:**

| Tabela | Zawartość | Kluczowe pola |
|---|---|---|
| `F_ARODES` | adresy wydzieleń drzewostanowych | `adress_forest` (adres leśny), `arodes_typ_cd` |
| `F_SUBAREA` | opis wydzielenia | `area_type_cd`, `site_type_cd`, `moisture_cd`, `degradation_cd`, **`soil_subtype_cd`** (typ+podtyp gleby), `plant_comm_cd` (zespół roślinny), `stand_struct_cd`, `forest_func_cd`, `silviculture_cd`, `rotation_age`, `sub_area`, `veg_cover_cd`, `damage_degree`, `cause_cd` |
| `F_AROD_STOREY` | **warstwy (piętra) drzewostanu** | `storey_cd` (kod warstwy), **`density_cd`** (stopień zwarcia koron), `mixture_cd` (sposób zmieszania gatunków), `standdensity_index` (stopień zadrzewienia), `tree_stock_cd` (stopień zagęszczenia), `st_rank_order_act` (ranga warstwy) |
| `F_STOREY_SPECIES` | **gatunki w warstwie** | `storey_cd`, `sp_rank_order_act` (ranga gatunku w warstwie), `species_cd`, `species_age`, **`part_cd_act`** (udział gatunku), `site_class_cd` (bonitacja), `height`, `bhd` (pierśnica), `volume` (miąższość) |
| `F_AROD_CUE` | wskazówki gospodarcze | `measure_cd`, `urgency`, `cutting_nr`, `cutting_area`, `large_timber_perc` |
| `F_AROD_CATEGORY` | kategorie ochronności | `prot_category_cd`, `prot_rank_order` |
| `F_AROD_PROT_SITE` | siedliska przyrodnicze (Natura 2000-podobne) | `prot_site_cd`, `prot_site_state` |
| `F_INSPECTORATE` | nazwa nadleśnictwa | `inspectorate_name` |

**Tabele geometryczne (SHP):** `G_SUBAREA` (wydzielenia — **ma pole `adr_for`
wprost**, plus zdublowane atrybuty jak w WFS: `area_type`, `site_type`,
`silvicult`, `forest_fun`, `stand_stru`, `rotat_age`, `sub_area`,
`prot_categ`, `species_cd`, `part_cd`, `spec_age`, `a_year`),
`G_COMPARTMENT` (oddziały), `G_FOREST_RANGE` (leśnictwa), `G_INSPECTORATE`
(granica nadleśnictwa).

**Tabele słownikowe:** `f_forest_func_dic`, `f_prot_categ_dic`,
`f_area_type_dic`, `f_density_dic`, `f_mixture_dic`, `f_part_dic`,
`f_plant_comm_dic`, `f_site_type_dic`, `f_storey_dic`, `f_tree_species_dic`,
`f_prot_site_dic`, `f_silviculture_dic`, **`f_soil_subtype_dic`**. Kody w
tabelach głównych rozwijają się przez te słowniki — same wartości kodów
(np. konkretne `storey_cd`, `soil_subtype_cd`) nie są wymienione w
dokumentacji schematu, tylko w rzeczywistych plikach paczki.

Katalog (`katalog_informacji_udostepnianych_z_bdl.pdf`) opisuje to samo z
perspektywy użytkownika i dodatkowo wymienia dla każdego gatunku w warstwie:
nazwa, ranga, **udział**, wiek, wysokość, pierśnica, **zwarcie**,
**zmieszanie**, **zadrzewienie**, zagęszczenie, miąższość — potwierdza, że
"zwarcie" jest atrybutem **per gatunek w warstwie**, nie tylko per warstwa
zbiorczo.

### Odpowiedzi na pytania z §3.1

| Pytanie | Odpowiedź | Pewność |
|---|---|---|
| Pełny skład gatunkowy z udziałami (per piętro)? | **Tak** — `F_STOREY_SPECIES.part_cd_act` per `storey_cd` z `F_AROD_STOREY` | Wysoka (ze schematu); rzeczywiste wypełnienie nie zweryfikowane |
| Zwarcie? | **Tak** — `F_AROD_STOREY.density_cd` (+ `standdensity_index`, `tree_stock_cd`), także per gatunek wg katalogu | Wysoka |
| Podszyt? | **Prawdopodobnie tak** — `storey_cd` to kod z otwartego słownika `f_storey_dic`; przykład filtra w samej dokumentacji BDL (`storey_cd IN ('DRZEW','IP','IIP')` przy wyciąganiu gatunku panującego) sugeruje, że **istnieją inne kody warstw** poza tymi trzema — najpewniej `PODROST`/`PODSZYT`, zgodnie z nazwą pola "Warstwa: Nazwa" w katalogu. **Nie potwierdzone literalnie** — wymaga realnej paczki albo zawartości `f_storey_dic` | Średnia — wniosek pośredni, nie literalny cytat |
| Typ gleby? | **Tak** — `F_SUBAREA.soil_subtype_cd` (typ+podtyp gleby) + `f_soil_subtype_dic` | Wysoka |
| Łączenie z `adr_for` z WFS? | `G_SUBAREA` ma pole `adr_for` **o identycznej nazwie** jak w WFS (`pipeline/bdl.py`). Format stringa (spacje, myślniki) nie zweryfikowany na realnym rekordzie — WFS i paczka pochodzą z tego samego systemu źródłowego (SILP), więc bezpośrednie dopasowanie stringów jest prawdopodobne, ale **do potwierdzenia na próbce** | Średnia |
| Licencja / warunki ponownego wykorzystania | Ustawa z 11.08.2021 o otwartych danych i ponownym wykorzystywaniu informacji sektora publicznego (Dz.U. 2021 poz. 1641, zm. 2022 poz. 1700). Formularz wniosku wymaga zaakceptowania: (1) informowania o źródle, czasie wytworzenia i pozyskania danych, (2) przekazywania danych dalej w formie pierwotnej, (3) informowania operatora o dalszym przetworzeniu. Brak wzmianki o zakazie użytku komercyjnego w samych warunkach formularza (w przeciwieństwie np. do iNaturalist/CC BY-NC) | Wysoka (tekst z formularza) |
| Rozmiar paczki | **Nieustalone** — wymaga faktycznego pobrania (patrz niżej) | Brak danych |

## Co złożone, ale nie dokończone

Wniosek na `bdl.lasy.gov.pl/portal/wniosek` **złożony w tej sesji**, za
zgodą i z adresem e-mail podanym przez użytkownika:

- E-mail: `[adres e-mail usunięty]` (podany przez użytkownika w tej rozmowie)
- Rok: 2026
- Zakres: RDLP KATOWICE → Nadl. KĘDZIERZYN (obszar testowy z zadania,
  odpowiada prefiksowi `adr_for` `02-10-...` już widocznemu w
  `cache/bdl_tiles_v2` z wcześniejszych przebiegów projektu)
- Warstwa granic zasięgów nadleśnictw: nieodznaczona (niepotrzebna do tej
  weryfikacji)
- Portal potwierdził wysłanie instrukcji pobrania na podany e-mail.

**Nie mam dostępu do tej skrzynki e-mail**, więc nie mogłem dokończyć
pobrania samej paczki ani zweryfikować rzeczywistych wartości pól,
kodowania plików TXT ani rozmiaru pliku. **Żaden plik z rzeczywistymi
danymi nadleśnictwa Kędzierzyn nie został pobrany ani zapisany.**

## Co założone, nie zweryfikowane

- Rzeczywiste wypełnienie `F_STOREY_SPECIES`/`F_AROD_STOREY` dla realnego
  nadleśnictwa — dokumentacja opisuje *strukturę*, nie *kompletność* danych.
  Możliwe, że część wydzieleń ma tylko gatunek panujący wypełniony (tak jak
  dziś w WFS), a reszta pól jest pusta lub rzadko uzupełniana.
- Dokładne kody `storey_cd` (czy `PODSZYT`/`PODROST` faktycznie istnieją
  jako osobne wartości, i czy mają wypełniony skład gatunkowy).
- Format i zgodność stringa `adr_for` między WFS a `G_SUBAREA` (spacje,
  wielkość liter, końcowe `-00`).
- Rozmiar pobranej paczki dla jednego nadleśnictwa (wpływa na to, czy dla
  17 RDLP / ~430 nadleśnictw pobranie regionu domowego jest praktyczne).
- Czy pakiet jest aktualizowany tak samo jak WFS (`a_year` = rok bieżący)
  czy z opóźnieniem.

## Rekomendacja

**Warunkowo: integrujemy w B2**, pod warunkiem potwierdzenia na realnej
paczce (Nadl. Kędzierzyn albo inne), że `F_STOREY_SPECIES` rzeczywiście
zawiera wypełniony skład gatunkowy z udziałami dla więcej niż
pojedynczych wydzieleń — dopiero to jest dowodem, że warto zastąpić
"nieznaną domieszkę 0,5" (§5.3) realnymi danymi. Schemat danych **w pełni
pokrywa** to, czego brakuje w WFS (skład gatunkowy per piętro, zwarcie, typ
gleby) i jest to jedyne zidentyfikowane źródło, które może rozbić płaskowyż
745 wydzieleń z R ≥ 90 (§0.1) bez nowych, zgadywanych wag eksperckich —
dokładnie tak, jak przewidywano w §3.1.

**Następny krok (poza zakresem B1):** użytkownik sprawdza skrzynkę
`[adres e-mail usunięty]`, pobiera paczkę Nadl. Kędzierzyn i przekazuje
plik/link — dopiero wtedy można dokończyć weryfikację (rzeczywiste wartości,
rozmiar, zgodność `adr_for`) i podjąć ostateczną decyzję B2. Do tego czasu
rekomendacja pozostaje warunkowa.
