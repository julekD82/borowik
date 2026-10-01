# Słownik pól paczek BDL — inwentaryzacja (Faza 1.6.1)

Data: 2026-09-28. Zakres: paczki nadleśnictw faktycznie dostępnych lokalnie
(`BDL/BDL_02_*_2026/`, RDLP Katowice, rok stanu danych 2026) — 9 paczek:
Brynek, Katowice, Kędzierzyn, Zawadzkie, Koszęcin, Lubliniec, Olesno,
Rudziniec, Strzelce Opolskie. Liczby wypełnienia poniżej to procent
wydzieleń `D-STAN` (rozpoznanych przez `area_type_cd == "D-STAN"` w
`f_subarea.txt`) mających niepustą wartość danego pola, per paczka.
Metodologia i surowe liczby: skrypt jednorazowy (nie w repo, patrz commit),
wynik w `bdl_inventory_result.csv` (poza repo, dane robocze).

Rok stanu danych (`a_year`) jest identyczny dla wszystkich sprawdzonych
paczek: **2026**, per wydzielenie i per paczka — to samo pole co `a_year` z
WFS (`pipeline/orchestrate.py`), już używane do `stand_id`.

## Pola trafiające do cech (≥ 50% wypełnienia)

| Tabela | Pole | Wypełnienie D-STAN (zakres po paczkach) | Słownik kodów | Użycie |
|---|---|---|---|---|
| `f_storey_species` | `site_class_cd` (na wierszu `DRZEW`, `sp_rank_order_act=1`) | 95,4–99,9% | brak w paczce (BDL: skala bonitacyjna I–V, z ew. `a`/`b`) | 1.6.4: bonitacja gatunku panującego (diagnostyka) |
| `f_arod_storey` | `density_cd` (warstwa `DRZEW`) | 86,1–93,7% | `f_density_dic.txt` (już wczytywany, `pipeline/bdl_dictionaries.py`) | już używane (karta, `S_host` niepowiązane); dodane też do diagnostyki 1.6.4 |
| `f_subarea` | `soil_subtype_cd` | 98,5–99,98% | `f_soil_subtype_dic.txt` (109 kodów; już wczytywany) | już używane (karta); dodane do diagnostyki. **Brak osobnego pola "typ gleby"** — paczka ma tylko połączony typ+podtyp w jednym kodzie |
| `f_subarea` | `degradation_cd` | 99,4–100% | **brak pliku słownika w paczce** — kody `N1/N2` (naturalne?), `Z1/Z2/Z3` (zniekształcone?), `D1` (zdegradowane/przekształcone?) rozpoznane tylko z konwencji nazewniczej BDL, **hipoteza, nie potwierdzone dokumentem** | 1.6.4: stan/wariant siedliska |
| `f_subarea` | `stand_struct_cd` | ~100% | brak w paczce (potwierdza wcześniejszy komentarz w `pipeline/export.py::build_details_record` o `stand_stru`); wartości widziane: `DRZEW`, `KO`, `KDO`, `2 PIĘTR` — tylko `2 PIĘTR` czytelne wprost, `KO`/`KDO` nierozpoznane (hipoteza: klasy odnowienia?) | 1.6.4: budowa pionowa drzewostanu |
| `f_subarea` | `veg_cover_cd` | 99,8–100% | brak w paczce (już rozpoznane i nazwane w `pipeline/tie_break.py::_VEG_COVER_LABELS`, z Instrukcji Urządzania Lasu) | już używane (tie-break, karta); dodane do diagnostyki 1.6.4 |
| `f_storey_species` (storey `PODSZ`, `PODR`) | `species_cd` + `part_cd_act` | PODSZ 78–90% wydzieleń ma tę warstwę, PODR rzadziej (patrz "inne piętra" niżej) | `f_tree_species_dic.txt`, `f_part_dic.txt` (już wczytywane) | 1.6.4: gatunki podszytu/podrostu (diagnostyka) — PODSZ już częściowo na karcie (`pipeline/bdl_package_details.py`); PODR dodane nowo |
| `f_arod_cue` | `measure_cd`, `urgency`, `cutting_area` | 82,3–94,1% wydzieleń D-STAN ma ≥ 1 wskazanie | `f_measure.txt` (kod→nazwa zabiegu) | 1.6.4: zabiegi gospodarcze — **tylko planowane, patrz ograniczenie niżej** |
| `G_COMPARTMENT` (geometria) | — | 100% (warstwa obecna we wszystkich 9 paczkach) | — | 1.6.4: odległość/długość granicy z oddziałem (geometria, nie tabela opisowa) |

## Pola uznane za niezdatne do cech (< 50% wypełnienia)

| Pole | Wypełnienie | Decyzja |
|---|---|---|
| `f_subarea.plant_comm_cd` (zbiorowisko roślinne) | 0,0–0,02% | **Niezdatne.** Praktycznie niewypełnione we wszystkich 9 sprawdzonych nadleśnictwach — nie tylko w Kędzierzynie. Mapa fitosocjologiczna BDL (WFS/warstwa lokalna) nie została sprawdzona — poza zakresem 1.6 (brak wskazanego lokalnego źródła). |
| `f_arod_storey.tree_stock_cd` (zadrzewienie) | 0,0% (wszystkie 9 paczek) | **Niezdatne.** Pole istnieje w schemacie, ale puste w praktyce. |
| `density_cd` na warstwach `PODSZ`/`PODR` (zagęszczenie podszytu/podrostu) | 0,0% | **Niezdatne.** "Gatunki" podszytu/podrostu są dobrze wypełnione, ale "zagęszczenie" — mimo że plan 1.6.4 prosi o oba — nie istnieje w danych. Zapisane wprost jako brak, nie pominięte milczeniem. |
| `f_subarea.damage_degree`, `f_subarea.cause_cd` | 10,5–66,1% (rozrzut, mediana ok. 25–40%) | Poniżej progu w większości sprawdzonych nadleśnictw — **niezdatne** (nie było zresztą na liście 1.6.4). |

## Ograniczenie: "zabiegi gospodarcze z datami"

Plan 1.6.4 prosi o zabiegi "z datami, z rozróżnieniem wykonane/planowane".
Rzeczywista zawartość paczki (`f_arod_cue.txt` — "wskazania cięć/zabiegów"):
**tylko planowane wskazania**, bez osobnej tabeli wykonanych zabiegów i bez
konkretnej daty — jedyna data to `a_year` całej paczki (2026, wspólny dla
całego nadleśnictwa). Diagnostyka opisuje to jawnie jako
`zabiegi_zrodlo: "wskazania_planowane"` z `rok_wskazania = a_year`, **bez
wnioskowania o wykonaniu ani o dokładnej dacie** — zgodnie z wymogiem planu
("jeśli paczka ma tylko planowane — zapisać, bez wnioskowania").

## Cechy z hipotezą (do 1.6.4, zaznaczone jawnie jako hipoteza w kodzie/eksporcie)

- **`site_class_cd` (bonitacja gatunku panującego)** — hipoteza: słabsza
  bonitacja (niższa jakość siedliska dla wzrostu drzew) może iść w parze z
  silniejszym owocnikowaniem grzybów mikoryzowych (mniejsza konkurencja o
  zasoby ze strony drzewa). Niepotwierdzone, do oceny w Fazie 2.2.
- **`degradation_cd` (stan siedliska)** — hipoteza: siedlisko naturalne
  (kod `N*`) sprzyja B. edulis bardziej niż zniekształcone/zdegradowane
  (`Z*`/`D*`) — zgodne z ogólną wiedzą mikoryzową, ale kody same w sobie są
  tu odczytane hipotetycznie (brak słownika w paczce), więc nawet kierunek
  etykiety jest niepewny.
- **`veg_cover_cd` (pokrywa runa)** — hipoteza z `pipeline/tie_break.py`:
  bór z borówką/mszysty (`MSZ`, `MSZC`) sprzyja szukaniu bardziej niż silnie
  zachwaszczony/zadarniony (`SZCH`, `SZAD`).
- **granica oddziału (odległość/długość)** — hipoteza z Fazy 6: linie
  oddziałowe (dukty, przecinki) to strefy światła/zaburzenia gleby, które
  mogą sprzyjać owocnikowaniu przy granicy wydzielenia.

## Nie sprawdzone / do dalszej oceny

- Czy wypełnienie w tych 9 nadleśnictwach (RDLP Katowice) jest reprezentatywne
  dla innych RDLP — jedna próbka regionalna, jak w B1 (`docs/archiwum/bdl-paczki-rozpoznanie.md`).
- Znaczenie dokładne kodów `degradation_cd` i `stand_struct_cd` (`KO`, `KDO`)
  — wymaga dokumentu `OpisDanych.pdf` BDL lub kontaktu z operatorem, poza
  zakresem tej sesji.
