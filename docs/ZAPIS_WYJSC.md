# Zapis wyjść do lasu (≤ 2 minuty po powrocie)

Cel: po sezonie lub dwóch dało się zaimportować własne wyjścia (Faza 5) bez ręcznej rekonstrukcji. **Zapisuj także wyjścia bez znalezisk** — bez zer nie da się ocenić, czy aplikacja coś wskazuje.

## Przed wyjazdem
1. Przygotuj analizę w launcherze i kliknij **„Zapisz do listy”** (nazwa np. „Kieleczka 28.09”). Bez migawki nie wiadomo, jaki ranking widziałeś tamtego dnia. Launcher przypomina o tym po analizie.
2. Włącz nagrywanie śladu w telefonie (Locus, Strava, oś czasu Google — cokolwiek, co eksportuje GPX). Ślad jest **najważniejszym polem**: pozwala policzyć czas spędzony w każdym wydzieleniu, także tam, gdzie nic nie znaleziono.

## Po powrocie
1. Wyeksportuj ślad jako `.gpx` do `dane_terenowe/gpx/`.
2. Dopisz wiersz do `dane_terenowe/wyjscia.csv`:

| pole | znaczenie |
|---|---|
| `id_wyjscia` | dowolny unikalny napis, np. `2026-09-28-kieleczka` |
| `data`, `start`, `koniec` | `RRRR-MM-DD`, `GG:MM`, `GG:MM` (czas lokalny) |
| `plik_gpx` | ścieżka względem `dane_terenowe/`, np. `gpx/2026-09-28.gpx` |
| `powod_wyboru` | `aplikacja` / `znane_miejsce` / `przypadkowo` / `mieszane` |
| `id_migawki` | id zapisanej migawki z dnia wyjazdu (z `frontend/public/data/trips/index.json`) |
| `uwagi` | np. ślady innych grzybiarzy, rowery, wycinka |

3. Znaleziska dopisz do `dane_terenowe/znaleziska.csv`: `id_wyjscia`, `lat`, `lon` (mogą być przybliżone), `gatunek`, `liczba`, `klasa_wieku` (`mlode` / `dojrzale` / `stare` / `mieszane`).
4. Sprawdź: `python scripts/sprawdz_dane_terenowe.py`. Skrypt wypisuje błędy (brakujące pola, nieistniejąca migawka, brak GPX) i ostrzeżenia (ślad nie pokrywa czasu wyjścia, znalezisko dalej niż 300 m od śladu). Nie analizuje skuteczności.

## Zasady
- Szablony plików: `dane_terenowe_szablony/`. Skopiuj je do `dane_terenowe/`.
- `dane_terenowe/` jest w `.gitignore` — dokładne lokalizacje są prywatne, nie commituj ich.
- Sama migawka i GPX wystarczą, żeby wyjście dało się kiedyś zaimportować, nawet jeśli CSV uzupełnisz później.
