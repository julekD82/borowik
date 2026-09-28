# Raport nocny — Faza 0 i Faza 1 (noc 27/28.09.2026)

> W trakcie realizacji. Sekcja „Na rano" zostanie uzupełniona na końcu nocy
> (zadanie 1.9) — na razie tymczasowa rekomendacja poniżej.

## Na rano (tymczasowe, do aktualizacji po 1.9)

- Migawka do użycia rano: **jeszcze nieznana** — poczekaj na finalną wersję tej sekcji.
- Status w trakcie realizacji, patrz log zadań poniżej.

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

Patrz punkt 3 powyżej. `docs/bdl-paczki-rozpoznanie.md` potwierdza konwencję: `pipeline.bdl_packages.load_packages` auto-wykrywa podkatalogi `cache/bdl_packages/*/` zawierające `G_SUBAREA.shp` + `f_storey_species.txt`. Katalog wskazany przez właściciela (`BDL/`) ma dokładnie taką strukturę w każdym z 9 podkatalogów (zweryfikowano zawartość `BDL_02_25_RUDZINIEC_2026/`).

## Status zadań

| Zadanie | Status | Notatka |
|---|---|---|
| 0.1 | DONE | patrz wyżej |
| 0.2 | DONE | patrz wyżej |
| 0.3 | DONE | migawka „Kieleczka 28.09 — baseline (stary kod)”, eksporty w `docs/porownania/baseline/`. 19716 wydzieleń, 14399 w masce, 5 rejonów, 0% składu z paczek (kod nie umiał wskazać `BDL/`) |
| 0.4 | DONE | gałąź `ulepszenia-faza1` |
| 1.1 | DONE | `run_manifest_{day}.json`: id/commit/dirty/profile hash, statusy źródeł, liczniki. `population_source`/`pressure_normalization` — pola-zaślepki do 1.4/1.5 |
| 1.2 | DONE | `diagnostics_{day}.json`/`.parquet` (próg 20 MB na realnym pliku). Test kluczowy: R_final odtworzony z diagnostyki, tolerancja 1e-9. Przy okazji naprawiony realny (choć dotąd nieszkodliwy) błąd w `orchestrate.py`: `cell` (komórka klimatologii) była czytana tylko przy cache miss |
| 1.3 | DONE | `--bdl-packages-dir`, wybór najnowszej paczki wg daty (nie kolejności katalogów), flaga `sklad_niepelny` (suma < 0,9), raport pokrycia per nadleśnictwo. **Zweryfikowane na realnych danych**: `BDL/` (9 nadleśnictw RDLP Katowice) dla Kieleczki 20 km daje **89,1% pokrycia paczkami** wśród wydzieleń w masce (0% w baseline). 2 nadleśnictwa bez paczki: 02-06 (5 wydz.), 02-31 (1339 wydz., prawdopodobnie Gliwice). Baner w interfejsie (>20% WFS-only) **odłożony** — dane już w `manifest.json` (`wfs_only_share_of_masked`), ostrzeżenie na razie tylko w logu konsoli; sama zmiana frontendu to osobna, niewielka praca zostawiona na później z braku czasu w nocy |
| 1.4–1.9 | TODO | |

## Ruling: pole „w launcherze” dla ścieżki paczek BDL

Plan 1.3 wymaga ścieżki konfigurowalnej przez „parametr CLI, pole w launcherze **lub** wartość w konfiguracji lokalnej” (alternatywa, nie koniunkcja). Zrobiony `--bdl-packages-dir` (CLI) w pełni spełnia wymaganie. Nie dodano osobnego pola w GUI launchera (Tkinter) — koszt/czas nie uzasadniał tego przy już spełnionym wymaganiu. Koszt błędu: żaden (funkcjonalność dostępna, tylko mniej wygodna z GUI).
