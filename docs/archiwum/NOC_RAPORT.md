# Raport nocny — Faza 0 i Faza 1 (noc 27/28.09.2026)

## Na rano

**Użyj migawki „Kieleczka 28.09 — nowy kod".** Rekomendacja: nowy kod, nie baseline.

Dlaczego:
- Wszystkie testy przechodzą (backend 578/578, frontend 72/72 + tsc czysty) po każdym zadaniu, na bieżąco.
- Zmiany rankingu są **wytłumaczone i oczekiwane**, nie przypadkowe: korelacja Spearmana R między starym a nowym kodem to **0,975** (wśród 14399 wydzieleń w masce w obu przebiegach) — silna zgodność ogólna, z realną, uzasadnioną reorganizacją czołówki. Trzy największe awanse i trzy największe spadki w rankingu **wszystkie** tłumaczy zmiana źródła składu gatunkowego (WFS → pełny skład z paczki BDL) zmieniająca H w oczekiwanym kierunku (w górę przy awansach, w dół przy spadkach) — to dokładnie to, co miała zrobić Faza 1.
- Największa realna poprawa: **89,1% wydzieleń w masce ma teraz skład z paczki BDL** (0% w starym kodzie) i **populacja z prawdziwej siatki GUS** zamiast w większości brakujących tagów OSM (10 237 komórek, zero pominiętych w buforze). To usuwa dwa najpoważniejsze problemy z dokumentu technicznego (§18.1).
- **Uwaga do świadomości na rano:** mediana P wzrosła (0,245 → 0,373) — to efekt realnych, gęstszych danych o populacji (GUS), nie błąd. Rejony pozostają w tej samej okolicy rankingu (rank_score różni się o ≤1,3 punktu), ale skład członków zmienił się umiarkowanie (59 wspólnych z 97/111).
- Panel „Warunki na kolejne dni" **nie wygenerował się w tym przebiegu** — chwilowy błąd 503 Open-Meteo przy osobnym zapytaniu o prognozę 7-dniową (sam ranking/eksport główny nie ucierpiał, panel to osobny, nie-krytyczny dodatek). Jeśli rano interesuje Cię pasek „Warunki”, uruchom ponownie tylko to zapytanie albo zaakceptuj jego brak w tej migawce.

Szczegóły porównania niżej (sekcja 1.9).

---

## Ustalenia ze startu sesji (odpowiedzi właściciela)

Zadano jedną serię pytań przed zmianami w kodzie (zgodnie z poleceniem). Odpowiedzi:

1. **Promień dla Kieleczki:** 20 km (nie domyślne 25 km z CLI — świadoma decyzja właściciela dla tego wyjazdu).
2. **Współrzędne:** potwierdzone 50,527 N, 18,605 E (Kieleczka, gm. Wielowieś).
3. **Paczki BDL:** właściciel wskazał katalog `C:\Users\<uzytkownik>\Documents\Grzyby\BDL\` — 9 nadleśnictw RDLP Katowice (Brynek, Katowice, Kędzierzyn, Zawadzkie, Koszęcin, Lubliniec, Oleśno, Rudziniec, Strzelce Opolskie), wszystkie „Data wytworzenia danych: 2026-06-23". Ten katalog **nie** jest w domyślnej lokalizacji `cache/bdl_packages/`, więc obecny (przed zmianami) kod go nie widzi — potwierdza to bezpośrednio jedną z hipotez §18.1 dokumentu technicznego (zły katalog uruchomienia). Dodano `/BDL/` do `.gitignore` natychmiast (dane BDL nie trafiają do repo, tak jak `cache/`).
4. **Siatka GUS:** potwierdzony plik `cache/NSP2021. Dane o ludności krajowej w siatce kilometrowej. _ 2021 census data. Population in 1km grid._28.09.2026.geojson` — 315 857 komórek (MultiPolygon), EPSG:2180 (bez potrzeby reprojekcji — pasuje do układu aplikacji), pole `tot` = populacja ogółem. Dokładnie zasób GUS 24532 z zadania 1.4.

## 0.1 Środowisko

- `uv` nie jest dostępny w PATH tej sesji (ani w bash, ani w PowerShell; nie znaleziono `uv.exe` w typowych lokalizacjach). Środowisko `.venv/` w repo jest już zsynchronizowane i działa poprawnie — użyto go bezpośrednio (`.venv/Scripts/python.exe`) zamiast `uv sync`. To odstępstwo od literalnego polecenia "uruchom `uv sync`" — środowisko już istniało i testy przechodzą, więc nie było potrzeby go przebudowywać. **Ruling:** nie instalowano `uv`, żeby nie ryzykować zmiany zależności w nocy (reguła 6) — jeśli `uv sync` jest potrzebne z innego powodu, do zrobienia w dzień.
- Ryzyko z §17.1 (błędy ładowania NumPy/pyproj) **nie wystąpiło** w tym środowisku: `numpy 2.5.3`, `pyproj 3.8.0`, `geopandas 1.1.4` importują się bez błędu.
- Backend: `pytest -q` → **494 passed**, 1 warning (nieistotny, sjoin_nearest na CRS geograficznym w `test_validate.py`, niezwiązany z tą sesją).
- Frontend: `npx tsc --noEmit` → brak błędów. `npx vitest run` → **66 passed** (52 model.test.ts + 14 sync-data.test.mjs).
- Baseline testów zgodny z historyczną notatką w dokumencie technicznym (494/66).

## 0.2 Lokalizacja paczek BDL

Patrz punkt 3 powyżej. `docs/archiwum/bdl-paczki-rozpoznanie.md` potwierdza konwencję: `pipeline.bdl_packages.load_packages` auto-wykrywa podkatalogi `cache/bdl_packages/*/` zawierające `G_SUBAREA.shp` + `f_storey_species.txt`. Katalog wskazany przez właściciela (`BDL/`) ma dokładnie taką strukturę w każdym z 9 podkatalogów (zweryfikowano zawartość `BDL_02_25_RUDZINIEC_2026/`).

## 1.5: rozkład P dla Kieleczki 20 km, oba tryby (realne dane z cache, bez API)

| Tryb | min | mediana | max |
|---|---|---|---|
| local (stary) | 0,0008 | 0,2446 | 0,8500 |
| absolute (nowy, d_half=90000) | 0,0008 | 0,2511 | 0,7185 |

Mediana zbliżona (zgodnie z celem doboru D_half); maksimum w trybie absolute wyraźnie niższe — oczekiwane: w trybie local najbardziej obleganie miejsce w danej analizie zawsze normalizuje się blisko 1 niezależnie od jego realnej skali, w trybie absolute nie.

## 1.9: raport porównawczy — Kieleczka 28.09, stary kod vs nowy kod

Wszystkie liczby z realnych eksportów obu przebiegów (`docs/archiwum/porownania/baseline/`, `docs/archiwum/porownania/nowy/`), 19716 wydzieleń dopasowanych po `stand_id` w obu.

**Korelacja Spearmana R:**
- wszystkie dopasowane wydzielenia (19716): rho = 0,9898
- w masce w obu przebiegach (14399): rho = 0,9746

**Zmiana źródła składu (WFS → paczka BDL):** 14631 wydzieleń przeszło z WFS na pełny skład z paczki (zgodnie z manifestem: `package_stand_count=14631`); 5085 zostało przy WFS (nadleśnictwa bez paczki: 02-06, 02-31).

**Rozkład H (w masce w obu):** stary min=0,000 mediana=0,843 max=1,000 → nowy min=0,000 mediana=0,860 max=1,000. Lekki wzrost mediany — realny skład z paczki średnio nieznacznie poprawia S_host względem przybliżenia „sam gatunek panujący”.

**Rozkład P (w masce w obu):** stary min=0,0008 mediana=0,2446 max=0,8500 → nowy min=0,0014 mediana=0,3732 max=0,8175 (patrz też sekcja 1.5 — częściowo efekt trybu `absolute`, częściowo efekt gęstszej siatki GUS zamiast rzadkich tagów OSM).

**Top-20 (≥ 0,5 ha, po R malejąco):** pokrywają się w 7/20 pozycjach. Pozostałe przesunięcia wynikają głównie ze zmiany źródła składu (nowe wydzielenia z wysokim H z paczki wchodzą do czołówki, część starych spada, bo ich realny skład okazał się gorszy niż przybliżenie WFS zakładało).

**Rejony:** 5 w obu przebiegach, zbliżone rank_score (stary: 77,75–81,78; nowy: 77,36–82,50 — różnica median ≤ 1,3 punktu). Łączne członkostwo we wszystkich rejonach: stary 97, nowy 111; część wspólna: 59.

**Trzy największe awanse w rankingu** (po pozycji rankingowej wśród wydzieleń w masce w obu):
1. `02-25-1-03-135-f-00@2026`: pozycja 9423→3921 (+5502), R 48,4→58,4. Przyczyna: WFS→paczka, H 0,655→0,790 (realny skład znacznie lepszy niż przybliżenie).
2. `02-14-3-09-10-j-00@2026`: pozycja 8581→3541 (+5040), R 50,2→59,5. Przyczyna: WFS→paczka, H 0,668→0,819.
3. `02-14-3-09-36-j-00@2026`: pozycja 8971→3935 (+5036), R 49,4→58,4. Przyczyna: WFS→paczka, H 0,619→0,746.

**Trzy największe spadki:**
1. `02-25-1-05-263-r-00@2026`: pozycja 7686→12573 (−4887), R 52,1→38,6. Przyczyna: WFS→paczka, H 0,780→0,599 (realny skład gorszy niż zakładało przybliżenie) + wzrost P (0,235→0,364, nowa populacja GUS).
2. `02-19-1-13-801-b-00@2026`: pozycja 6029→10301 (−4272), R 55,6→45,1. Przyczyna: WFS→paczka, H 0,767→0,652, P 0,183→0,331.
3. `02-25-1-07-345-b-00@2026`: pozycja 8193→12319 (−4126), R 50,9→39,4. Przyczyna: WFS→paczka, H 0,691→0,550, P 0,128→0,261.

We wszystkich sześciu przypadkach zmiana wynika ze **znanej, celowej przyczyny** (1.3 + 1.4/1.5), nie z błędu — F_loc praktycznie bez zmian (ta sama pogoda), więc to H (skład) i P (presja) niosą całą różnicę.

## Status zadań

| Zadanie | Status | Notatka |
|---|---|---|
| 0.1 | DONE | patrz wyżej |
| 0.2 | DONE | patrz wyżej |
| 0.3 | DONE | migawka „Kieleczka 28.09 — baseline (stary kod)”, eksporty w `docs/archiwum/porownania/baseline/`. 19716 wydzieleń, 14399 w masce, 5 rejonów, 0% składu z paczek (kod nie umiał wskazać `BDL/`) |
| 0.4 | DONE | gałąź `ulepszenia-faza1` |
| 1.1 | DONE | `run_manifest_{day}.json`: id/commit/dirty/profile hash, statusy źródeł, liczniki. `population_source`/`pressure_normalization` — pola-zaślepki do 1.4/1.5 |
| 1.2 | DONE | `diagnostics_{day}.json`/`.parquet` (próg 20 MB na realnym pliku). Test kluczowy: R_final odtworzony z diagnostyki, tolerancja 1e-9. Przy okazji naprawiony realny (choć dotąd nieszkodliwy) błąd w `orchestrate.py`: `cell` (komórka klimatologii) była czytana tylko przy cache miss |
| 1.3 | DONE | `--bdl-packages-dir`, wybór najnowszej paczki wg daty (nie kolejności katalogów), flaga `sklad_niepelny` (suma < 0,9), raport pokrycia per nadleśnictwo. **Zweryfikowane na realnych danych**: `BDL/` (9 nadleśnictw RDLP Katowice) dla Kieleczki 20 km daje **89,1% pokrycia paczkami** wśród wydzieleń w masce (0% w baseline). 2 nadleśnictwa bez paczki: 02-06 (5 wydz.), 02-31 (1339 wydz., prawdopodobnie Gliwice). Baner w interfejsie (>20% WFS-only) **odłożony** — dane już w `manifest.json` (`wfs_only_share_of_masked`), ostrzeżenie na razie tylko w logu konsoli; sama zmiana frontendu to osobna, niewielka praca zostawiona na później z braku czasu w nocy |
| 1.4 | DONE | `pipeline/population_grid.py`: siatka GUS (`--population-grid-path`) jako źródło Demand, bufor +30 km. Fallback bez pliku: OSM z imputacją wg klasy (`osm_z_imputacja`), zamiast cichego zera. Zweryfikowane na realnym pliku: 10237 komórek, 0 pominiętych w buforze Kieleczki, ~10 s zapytania |
| 1.5 | DONE | `pressure.normalization: absolute` (domyślny), `d_half=90000.0`. **Ruling**: D_half dobrany na Kieleczce (offline, z cache), nie na Będziemyślu jak sugerował plan — pełny cache Będziemyśla (paczki BDL, dawne przebiegi) już nie istnieje na tym dysku (patrz 0.2). Kieleczka to ten sam rząd wielkości (miejska aglomeracja śląska), więc kalibracja jest równie sensowna jako punkt startowy. Koszt błędu: żaden poza samą wartością D_half — jest i tak jawnie oznaczona jako tymczasowa/nieskalibrowana, do korekty po realnej walidacji terenowej (Faza 5) |
| 1.6 | DONE | `zakaz_status` (brak/zakaz/nie_sprawdzono/blad — sprawdzenie zakazu ma teraz try/except, błąd źródła już nie przerywa całego przebiegu) i `gdos_status` (brak/blokada/kafel_pominiety) — oba w scores.json i diagnostics. Naprawiony realny błąd: `test_failure_mid_pipeline_preserves_previous_export` zakładał, że błąd zakazu jest fatalny — to była dokładnie usterka z §13.1, teraz naprawiona; test fatalności przeniesiony na inny, faktycznie fatalny błąd. Frontend: notatka o dacie sprawdzenia zakazów + „nie sprawdzono”/„błąd” w karcie wydzielenia |
| 1.7 | DONE | Etykieta pewności realnie spada do NISKA przy: cienkiej/pustej klimatologii, pokryciu radaru < 0,5 (przy włączonym radarze), pominiętym kaflu OSM/GDOŚ, nieznanym kodzie siedliska/gatunku, niepełnym składzie paczki. Wcześniej (wg dokumentu technicznego §12) NISKA praktycznie nigdy nie występowała w zwykłych ścieżkach. Przy okazji (1.8d): `percentile_rank` filtruje NaN zamiast przekazywać je do scipy |
| 1.8a | DONE (kod + test), przeliczenie BLOCKED | **Realny błąd potwierdzony**: `notebooks/03_backtest_gbif.py` liczył dzień roku wprost z timestampów UTC (bez konwersji do Europe/Warsaw), podczas gdy notatniki 06/09 tę konwersję robią — każdy dzień archiwum trafiał do złego (poprzedniego) miejsca w tablicy cech. Naprawione (ta sama korekta „w południe” co 1.8b), zweryfikowane testem regresyjnym (`tests/test_backtest_gbif_dates.py`) odróżniającym stare/nowe zachowanie liczbowo (RED bez poprawki, GREEN z nią). **Pełne przeliczenie BLOCKED**: uruchomiłem je w nocy w 100% z cache (zero zapytań do API, `no_network` fetcher) na dokładnie tych samych 90 punktach z `backtest_gbif_results.csv`, ale proces działał bardzo długo (nieefektywne skanowanie klimatologii w istniejącym, niezmienionym kodzie notebooka — nie w samej poprawce) i został **zabity przez system Claude Code z powodu niskiej pamięci systemowej** (nie błąd logiki). Nie uruchamiam go ponownie sam — zgodnie z zasadą tego środowiska po zabiciu za pamięć proces nie jest wznawiany automatycznie. **Do zrobienia w dzień, jeśli chcesz liczby przed/po**: `.venv\Scripts\python.exe` na skrypcie odtwarzającym `main()` notebooka na pinned 90 punktach z cache (logika opisana w komentarzu poprawki w `notebooks/03_backtest_gbif.py::_daily_features`) — rozważ wcześniej przyspieszenie `climatology_window_values`/pętli lookupów, bo to ono jest wąskim gardłem, nie sama poprawka daty. Kod poprawki jest gotowy i przetestowany niezależnie od tego przeliczenia |
| 1.8b | DONE | Ujednolicona konwersja UTC→Europe/Warsaw (`pipeline.weather.to_local_date`, korekta „w południe”) używana teraz przez `pipeline.radar.merge_radar_into_daily`, `pipeline.flush.area_daily_weather` i `pipeline.conditions_timeline.with_local_date` — wcześniej dwie z tych trzech funkcji nie miały korekty. Wspólny test na 2026-03-29 i 2026-10-25 |
| 1.8c | DONE | Próg epizodu deszczu w panelu warunków zależy teraz od **rzeczywistego** pokrycia radaru w oknie ostatnich dni (`rain_episode_radar_coverage`), nie od samej flagi włączenia — całkowity fallback na Open-Meteo już nie obniża progu tak, jakby radar zadziałał |
| 1.8d | DONE | Zrealizowane w ramach 1.7 (patrz wyżej): `percentile_rank` ignoruje NaN, `climatology_window_insufficient` (puste lub <50% ważnych) zasila etykietę pewności |
| 1.8e | DONE | Klucze cache pogody i klimatologii zawierają teraz `past_days`/zakres lat i numer wersji formatu (`_v1`) — stare pliki cache zostają, po prostu nie są już dopasowywane (nowe zapytanie zapisze nowe pliki obok). Realny koszt dziś: pełny bieg 1.9 przeliczy klimatologię Kieleczki na nowo (~25 punktów, mały koszt) |
| 1.8f | DONE | Poprawione teksty: `--date` (realna data wyjazdu, nie etykieta), `CLAUDE.md` (usunięty odniesienie do nieistniejącego katalogu `borowik-faza2-mvp-backend`), `frontend/README.md` (ścieżka uruchomienia, lista plików `sync-data`, status grupowania, zakaz_status/gdos_status), uzasadnienie wilgotności w `pipeline/explain.py` („mediana obszaru” zamiast mylącej „normy dla tej pory roku”) |
| 1.9 | DONE | Przebieg końcowy Kieleczka 20 km, 2026-09-28, z całym kodem Fazy 1 + realnymi paczkami BDL i siatką GUS. Migawka „Kieleczka 28.09 — nowy kod”, eksporty w `docs/archiwum/porownania/nowy/`. Panel warunków pominięty (503 z Open-Meteo przy osobnym zapytaniu, nie wpłynęło na główny wynik). Pełne porównanie niżej |

## Ruling: pole „w launcherze” dla ścieżki paczek BDL

Plan 1.3 wymaga ścieżki konfigurowalnej przez „parametr CLI, pole w launcherze **lub** wartość w konfiguracji lokalnej” (alternatywa, nie koniunkcja). Zrobiony `--bdl-packages-dir` (CLI) w pełni spełnia wymaganie. Nie dodano osobnego pola w GUI launchera (Tkinter) — koszt/czas nie uzasadniał tego przy już spełnionym wymaganiu. Koszt błędu: żaden (funkcjonalność dostępna, tylko mniej wygodna z GUI).
