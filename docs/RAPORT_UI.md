# Raport — Faza UI (czytelny interfejs i przełącznik presji)

Gałąź `ulepszenia-ui` (z `master`), 29.09.2026. Plan: `docs/PLAN_WDROZENIA.md`, sekcja „Faza UI”.
Model, wagi, α, progi klas i profil **bez zmian**. Nie pushowano, nie scalano, nie usuwano cache ani danych.

## Status zadań

| Zadanie | Status | Uwagi |
|---|---|---|
| UI.1 Przełącznik presji (backend + frontend) | **DONE** | `R_bez_presji`, drugi zestaw rejonów, przełącznik z pamięcią lokalną, stare migawki obsłużone |
| UI.2 Paski Siedlisko / Pogoda / Spokój | **DONE** | trzy paski „więcej = lepiej”, rozwijane do składowych, karta rejonu ma te same paski |
| UI.3 Porządek w treści | **DONE** (z dwoma odstępstwami niżej) | nazwy, lista jednowierszowa, karta z „Szczegółami”, pasek pogody ze słupkami |
| UI.4 Telefon (390 px) | **DONE** | zakładki Lista / Mapa, brak poziomego przewijania (scrollWidth = clientWidth = 374) |
| UI.5 Akceptacja | **DONE** | testy, sprawdzenie na prawdziwych danych, lista kontrolna, zrzuty |

## UI.1 — przełącznik presji

**Backend**
- `pipeline/mvp.py`: kolumna `R_bez_presji = compute_ranking(mask, H, F_loc, p=0, alpha=0)` = `100·H·F_loc`, liczona po sprawdzeniu zakazów okresowych (ta sama maska co `R_final`, zakaz zeruje oba).
- `pipeline/export.py`: `scores.json` ma `R_bez_presji` (obok H, F_loc, P, mask, R — sprawdzone, brakowało tylko tego pola). `details.json` ma nowy blok `habitat` (S_host, S_site, S_age, tryb wieku), `forest_district` i `access.pressure_contrib` (wkład typów punktów w surową presję). `regions_*.json` ma opcjonalne `near_place` (najbliższa miejscowość OSM).
- `pipeline/prepare_trip.py`: rejony liczone **dwa razy tą samą procedurą** `group_into_regions` — z `R_final` (jak dotąd) i z `R_bez_presji` podstawionym w miejsce `R_final`. Drugi zestaw trafia do `regions_bez_presji_{day}.json`. Manifest: `pressure_alpha`, `counts.region_count_bez_presji`.
- `frontend/scripts/sync-data.mjs` i `launcher/trip_archive.py` (`TRIP_FILES`) przenoszą `regions_bez_presji.json` (plik opcjonalny, walidowany jak `regions.json`, stary usuwany, gdy nowego brak).

**Frontend**
- Przełącznik „Uwzględniaj presję grzybiarzy” (domyślnie włączony, pamięć w `localStorage` pod `borowik.pressure.v1`, odczyt/zapis w try/catch).
- Przełącza: sortowanie wydzieleń, listę rejonów (drugi zestaw), kolory mapy (percentyle `R_bez_presji`), wynik w wierszu i karcie, uzasadnienie („Dlaczego tutaj” pomija wiersz o presji), legendę mapy.
- Stara migawka bez `R_bez_presji` albo bez `regions_bez_presji.json`: przełącznik nieaktywny z komunikatem „Niedostępne w tej migawce — starszy eksport nie ma wyników bez presji.” (zrzut `po-pulpit-stara-migawka-przelacznik-nieaktywny.jpg`, migawka „Kieleczka — faza 4”).
- Maska prawna i strukturalna w obu trybach ta sama (test `test_r_bez_presji_is_zero_for_periodic_ban_like_r_final`, `rankEntries` nie wpuszcza wydzieleń spoza maski).

## UI.5 — przy włączonej presji nic się nie zmieniło (dowody)

Testy (`tests/test_ui_presja.py`, `frontend/src/ui.test.ts`):
- `R_bez_presji = 100·H·F_loc` dla wydzieleń w masce, 0 poza maską; `R_bez_presji ≥ R_final`.
- `R_final` z presją = `compute_ranking(..., alpha)` (wzór bez zmian).
- `group_into_regions` daje **te same** rejony, gdy do ramki doda się kolumnę `R_bez_presji` (`test_regions_with_pressure_ignore_the_new_column`); rejony bez presji wybierają własne klastry (`test_regions_without_pressure_use_the_same_procedure_on_r_bez_presji`).
- Frontend: `rankEntries(joinData(...), true)` = `joinData(...)` (kolejność i `r`), przełączenie tam i z powrotem przywraca dokładnie ten sam ranking, `joinRegions` z presją wybiera to samo „najlepsze wydzielenie”.
- Wartości przypięte z Fazy 4 (`test_faza4_r_niezmienione.py`) nadal przechodzą.

Na prawdziwych danych (Kieleczka, 20 km, 29.09; nowy przebieg tym samym poleceniem co launcher, do `output/ui_kieleczka`, porównany z eksportem z 22:07 sprzed zmian):
- 19 716 wydzieleń: maks. |Δ| dla H, F, F_loc, P i **R = 0,0**; maska identyczna.
- `R_bez_presji − 100·H·F_loc` w masce: 0,0; poza maską wszędzie 0.
- `regions.json` (z presją): identyczne `stand_ids` i `rank_score` co przed zmianą (5 rejonów).
- Bez presji: 5 rejonów o innym składzie i kolejności (pierwszy: Wierchlesie 83,0; z presją pierwszy: Jaźwina 83,5) — różnice widać w przełączniku (zrzuty `po-pulpit-rejon-z-presja.jpg` i `…-bez-presji.jpg`).

## UI.2 — paski

- Trzy paski w kolejności Siedlisko (H), Pogoda (F_loc), Spokój (1 − P), wszystkie „więcej = lepiej”, wartości wyłącznie z eksportu.
- Ocena słowna: Siedlisko niskie/średnie/wysokie (progi 0,4 / 0,7 jak dotychczasowa klasa H), Pogoda — klasa F_loc z tych samych progów co dotąd („słabe warunki / umiarkowane / dobre / bardzo dobre”), Spokój niski/średni/wysoki. Dokładna wartość: podpowiedź (`title`) po najechaniu oraz pierwszy wiersz po dotknięciu/rozwinięciu paska.
- Rozwinięcie: Siedlisko → skład drzewostanu (S_host), typ siedliska (S_site), wiek (S_age; w trybie `neutral` „nie wpływa na wynik”); Pogoda → wilgotność (M), temperatura (T), przymrozek (K_frost) + zdania z 4.3; Spokój → do 3 typów punktów o największym wkładzie (parking / wjazd lub szlaban / osiedle / droga leśna…), z odległością tam, gdzie eksport ją ma, i nazwą największego elementu.
- Przy wyłączonej presji pasek Spokój jest wyszarzony z opisem „nie uwzględniony”.
- Karta rejonu: te same paski; wartości **najlepszego wydzielenia rejonu** (opisane w Szczegółach), ranking rejonu to jak dotąd mediana wyniku najlepszych wydzieleń.
- Nad paskami: „Wynik = siedlisko × pogoda × spokój”.

## UI.3 — porządek w treści

- Nazwy: wydzielenie „Oddz. 96a · Nadl. Zawadzkie” (adres leśny; pełny identyfikator, kod nadleśnictwa, leśnictwo, oddział, pododdział w Szczegółach). Rejon „Rejon 1 · Jaźwina” (najbliższa miejscowość OSM).
- Lista: jeden wiersz na pozycję — miejsce, nazwa, wynik, trzy mini-paski, powierzchnia i odległość od punktu startu (z manifestu) w jednej linii; maks. 2 linijki tekstu.
- Karta: nagłówek → paski → 2–4 fakty (parking, wjazd, utwardzony dukt, powierzchnia / liczba wydzieleń) → przyciski (Zapisz, Nawiguj, na telefonie także „Na mapie”) → zwinięte „Szczegóły”.
- Jedna ocena klasy: zamiast trzech („Bardzo dobre”, „Wysoki potencjał”, „Warunki teraz”) — słowa przy paskach. „Model nieskalibrowany” i „ranking nie jest prawdopodobieństwem” raz w stopce panelu i w Szczegółach.
- Pasek pogody u góry: jedno zdanie + 7 słupków F (wysokość = F, kolor = poziom, „?” i kreskowanie od 4. dnia, „~” i wyszarzenie od 8. dnia — progi z profilu, 4.5); reszta tekstu w zwiniętych „Szczegółach pogody”.
- Żargon (M=0.93, S_site=1.00) tylko w Szczegółach i rozwinięciach pasków.

**Odstępstwa od planu (świadome)**
1. „Rejon 1 · koło Łazisk” → **„Rejon 1 · Łaziska”**: nazwa miejscowości bez odmiany (nie ma w danych dopełniacza; automatyczna odmiana dawałaby błędy).
2. Nazwy nadleśnictw z polskimi znakami tylko dla dziewięciu nadleśnictw RDLP Katowice (słownik w `model.ts`, kody z nazw paczek BDL); dla innych z eksportu (`forest_district`, z nazwy paczki, bez polskich znaków) albo sam kod. Nazwy leśnictw nie ma w danych — jest tylko numer, w Szczegółach.

## UI.4 — telefon

Szerokość ≤ 760 px: nagłówek i wstęp skrócone; lista i mapa jako zakładki „Lista / Mapa” przyklejone u góry (przyciski 48 px, wiersze ≥ 64 px, paski ≥ 52 px, przyciski akcji 48 px); dotknięcie wydzielenia na mapie przełącza na listę z jego kartą; „Na mapie” w karcie przełącza na mapę i ustawia widok; przełączniki warstw mapy w jednej przewijanej linii. Przełącznik presji 56 px. Sprawdzone w ramce iframe 390 px (narzędzie przeglądarki nie zwęża okna): `scrollWidth = clientWidth = 374`, lista, karta, mapa z podświetleniem i zakładki działają. Przy okazji naprawiony błąd: podświetlenie rejonu/wydzielenia ustawione przed załadowaniem stylu mapy (mapa ukryta na zakładce ładuje się później) było gubione (`map.ts`, `style.load`).

## Lista kontrolna: stare pole → nowe miejsce

**Karta wydzielenia (lista) i widok „Szczegóły wydzielenia”**

| Stare pole | Nowe miejsce |
|---|---|
| Etykieta „PIERWSZY WYBÓR / WARTO ROZWAŻYĆ” | numer w rankingu (wiersz), „Miejsce N w rankingu” w Szczegółach |
| Tytuł „Wydzielenie {id}” | nazwa „Oddz. … · Nadl. …”; pełny id w Szczegółach → Identyfikator |
| Współrzędne pod tytułem | Szczegóły → „Punkt orientacyjny: …” |
| Plakietka klasy F („Bardzo dobre”) | słowo przy pasku Pogoda; Szczegóły → „Warunki regionalne F” |
| „Pewność: …” + przyczyny | Szczegóły → „Pewność oceny” |
| SIEDLISKO (klasa H) | słowo przy pasku Siedlisko; Szczegóły → „Siedlisko H · … potencjał” |
| WARUNKI TERAZ (klasa F) | pasek Pogoda; Szczegóły → „Warunki regionalne F” i „Pogoda lokalna F_loc” |
| „Dlaczego tutaj?” (2 powody) | Szczegóły → „Dlaczego tutaj” (pełna lista; bez wiersza o presji przy wyłączonej presji) |
| „Pogoda w tym miejscu” (opad, bilans, temperatura, przymrozek, F, udział prognozy) | rozwinięty pasek Pogoda (składowe M/T/K_frost + te same zdania); zastrzeżenie o pogodzie w Szczegółach |
| Dostęp (parking, wjazd, dukt, metoda, największy wpływ) | fakty na karcie; rozwinięty pasek Spokój; Szczegóły → „Dostęp i punkt orientacyjny” |
| „Punkt orientacyjny… Dojazd samochodem: brak danych” | Szczegóły → „Dostęp i punkt orientacyjny” |
| „Ranking wydzielenia … model nieskalibrowany”, P + objaśnienie | Szczegóły → „Wynik i model” (R z presją i bez, wzór z α, P, notatka o P) + stopka panelu |
| Zapisz miejsce / Nawiguj | przyciski karty (bez zmian) |
| Przycisk „Szczegóły wydzielenia” i osobny widok (R, H, F regionalne, F lokalne, P, Co wpływa na wynik) | zwinięte „Szczegóły” w karcie (wszystkie te wartości) |
| Drzewostan i otoczenie (skład, zwarcie, pokrycie gleby, zadrzewienie, podszyt, gleba, data paczki, wskazówka, budowa, ochronność, sąsiedztwo) | Szczegóły → „Drzewostan i otoczenie” |
| Zakres danych (filtry, data analizy, zakazy) | Szczegóły → „Zakres danych” |
| „Analiza: data” | stopka karty (bez zmian) |

**Karta rejonu:** „Rejon region_N” → nazwa; id w Szczegółach; „N wydzieleń · współrzędne” → wiersz + Szczegóły; ranking rejonu (mediana) → Szczegóły; dostęp w całym rejonie (zakresy) → Szczegóły; „Zobacz wydzielenia w rejonie” → przycisk (bez zmian); reszta jak wyżej dla najlepszego wydzielenia.

**Pasek pogody u góry:** zdanie o deszczu → zdanie nad słupkami; kropki poziomów ●●○ → słupki (kolor = poziom, wysokość = F, podpowiedź z liczbą /100); „Warunki wilgotności: …”, składniki, „Lokalnie: …”, notka o niepewności, zastrzeżenie → „Szczegóły pogody”; „prognoza niepewna” / „orientacyjnie” → „?” / „~” + legenda w Szczegółach; „MODEL EKSPERCKI · NIESKALIBROWANY” → stopka panelu i Szczegóły.

Sprawdzone też skryptem w przeglądarce: w karcie wydzielenia, karcie rejonu i pasku pogody występują wszystkie kluczowe frazy z tabeli (brak brakujących).

## Testy

- Backend: `python -m pytest` → **794 passed** (było 778; +16 w `tests/test_ui_presja.py`; poprawiony jeden test kształtu karty dostępu o nowy klucz `pressure_contrib`).
- Frontend: `npx vitest run` → **123 passed** (było 98; +23 `ui.test.ts`, +2 w `sync-data.test.mjs`); `npx tsc --noEmit` czysto; `vite build` OK.

## Zrzuty ekranu (`docs/ui-zrzuty/`)

Przed: `przed-pulpit-gora.jpg`, `przed-pulpit-rejon.jpg`, `przed-pulpit-wydzielenia.jpg`, `przed-telefon-gora.jpg`, `przed-telefon-lista.jpg`.
Po: `po-pulpit-gora.jpg`, `po-pulpit-rejon-z-presja.jpg`, `po-pulpit-rejon-bez-presji.jpg`, `po-pulpit-pasek-spokoj-rozwiniety.jpg`, `po-pulpit-wydzielenie-szczegoly.jpg`, `po-pulpit-szczegoly-wynik.png`, `po-pulpit-stara-migawka-przelacznik-nieaktywny.jpg`, `po-telefon-gora.jpg`, `po-telefon-karta-rejonu.jpg`, `po-telefon-mapa.jpg`.
Zrzuty „przed” zrobione na tych samych wartościach modelu (H, F, P, R identyczne — patrz wyżej).

## Ograniczenia i uwagi

- `details.json` urósł z ok. 36 do ok. 44 MB (blok `habitat`, `pressure_contrib`, `forest_district` na każde wydzielenie, zapis z wcięciami). Do rozważenia: zapis bez wcięć albo rozdzielenie pliku.
- Pasek „Spokój” pokazuje 1 − P, ale do wyniku presja wchodzi jako `(1 − α·P)` z α = 0,3; „Wynik = siedlisko × pogoda × spokój” to opis poglądowy, dokładny wzór jest w Szczegółach. Paski nie sumują się więc dokładnie do wyniku.
- Widok telefonu sprawdzony w ramce 390 px w Chrome na komputerze, nie na fizycznym telefonie (dotyk, klawiatura ekranowa, `100dvh` na paskach przeglądarki mobilnej — do sprawdzenia w terenie).
- Ostatnie dane (Kieleczka 29.09) w `frontend/public/data` zostały zastąpione nowym eksportem (te same wartości modelu + nowe pola); poprzednie pliki skopiowane do `output/backup_public_data_przed_ui/`. Migawki w `data/trips/` niezmienione (starsze nie mają nowych pól — przełącznik jest tam nieaktywny; nowa migawka powstanie przy następnym „Zapisz mapę” w launcherze).

## Dodatek (30.09): trzy tryby kolorowania mapy

Trzy przyciski w legendzie mapy: **Wynik** (jak dotąd z presją), **Wynik bez presji**, **Wilgotność** (składowa M, 0–1).

- **Synchronizacja a/b z przełącznikiem presji:** wybór „Wynik” / „Wynik bez presji” ustawia też przełącznik presji (lista, rejony, mapa), a przełącznik ustawia odpowiedni przycisk. Logika w jednym miejscu (`chooseColorMode`, `togglePressureControls` w `model.ts`), więc kontrolki nie mogą być sprzeczne.
- **Wilgotność zmienia tylko kolory mapy:** lista i rejony zostają w ostatnim trybie a/b. Decyzja o pogranicznym przypadku: gdy w trybie Wilgotność użytkownik ruszy przełącznik presji, mapa wraca do trybu a/b zgodnego z przełącznikiem (przełącznik, który nic nie zmienia na mapie, wyglądałby na zepsuty).
- **Skala bezwzględna 0–1** (nie percentyle): progi 0 / 0,25 / 0,5 / 0,75 / 1, paleta piaskowy → jasnozielony → niebieskozielony (`MOISTURE_STOPS`), ten sam kolor dla tego samego M w każdej analizie; brak M = szary. Legenda z progami i opisem: „Bilans opad − parowanie z 26 dni względem typowego dla tej pory roku. To nie pomiar wilgotności gleby.”
- **Wszystkie wydzielenia leśne:** źródło mapy zawiera geometrię wszystkich 19 716 wydzieleń z `stands.geojson` (wcześniej tylko 14 016 ocenionych). W trybach wyniku wydzielenia poza maską są filtrowane (jak dotąd), w trybie Wilgotność widoczne z mniejszą intensywnością (krycie 0,32 zamiast 0,8). Kliknięcie wydzielenia poza maską pokazuje komunikat, bo nie ma karty.
- **Dane:** `scores.json` ma `M` i `pct_CWB26` dla każdego wydzielenia (także poza maską; wartości z modelu, bez przeliczeń). Kieleczka 30.09: M dostępne dla 19 716/19 716, zakres 0,12–0,92. Stare migawki bez `M`: przycisk Wilgotność nieaktywny z komunikatem „Wilgotność: niedostępna w tej migawce (starszy eksport bez składowej M).” (zrzut `tryby-mapy-stara-migawka-bez-M.jpg`); analogicznie „Wynik bez presji” bez `R_bez_presji`.
- **Pamięć:** wybór trybu w `localStorage` pod `borowik.map-color.v1` (try/catch). Zapamiętana Wilgotność wraca po odświeżeniu (sprawdzone w przeglądarce); a/b zawsze idą za przełącznikiem presji.
- **Testy:** `frontend/src/ui.test.ts` (+10: synchronizacja a/b z przełącznikiem, Wilgotność nie rusza presji, przełącznik wyprowadza z trybu Wilgotność, stan początkowy i zapamiętany tryb, stare migawki bez M / bez R_bez_presji, walidacja `M`, skala bezwzględna: kolor zależy tylko od M, progi rosnące 0–1, treść opisu legendy), `tests/test_ui_presja.py` (+2: `M` i `pct_CWB26` w rekordzie, NaN → null, także poza maską). Backend 796 passed, frontend 133 passed, `tsc` i `vite build` bez błędów.
- **Zrzuty:** `tryby-mapy-a-wynik.jpg`, `…-b-wynik-bez-presji.jpg`, `…-c-wilgotnosc.jpg`, `…-c-wilgotnosc-telefon.jpg`, `…-c-legenda-telefon.jpg`, `…-stara-migawka-bez-M.jpg`. Na telefonie (iframe 390 px) przyciski mają 44 px, legenda ma maks. 58% wysokości mapy z przewijaniem, brak poziomego przewijania strony.
- **Uwagi:** eksport Kieleczki został przeliczony 30.09 (nowa pogoda), więc liczby w zrzutach dodatku różnią się od zrzutów z 29.09; `frontend/public/data` = ten nowy eksport (kopia poprzedniego w `output/backup_public_data_29_09_ui/`). Przy przełączaniu trybów źródło mapy jest odświeżane w całości (ok. 20 tys. wielokątów) — na słabszym sprzęcie może to chwilę potrwać.

