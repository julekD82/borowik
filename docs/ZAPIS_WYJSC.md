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

## Dziennik wyjść (`dane_terenowe/dziennik_wyjsc.xlsx`)

Dziennik to jedno miejsce, w którym łączysz eksport z Shroomera z własnymi obserwacjami. **Źródłem prawdy dla poprawek i notatek jest dziennik.** Surowe eksporty (`dane_terenowe/shroomer/surowe/<data>/`: `trips.csv`, `routes.csv`, `finds.csv`, `car_locations.csv`) są tylko wejściem — nie edytuje się ich; każdy nowy eksport wrzucaj do nowego podkatalogu.

### Arkusze
- **Wyjścia** — jeden wiersz na wyjście (id z Shroomera). Szare kolumny z Shroomera (data i godziny lokalne, nazwa, notatka, długość trasy w km, liczba znalezisk ogółem i borowików w sztukach) są tylko do odczytu. Żółte kolumny wypełniasz sam, z list rozwijanych:

| kolumna | wartości |
|---|---|
| powód wyboru | aplikacja / znane miejsce / przypadek / mieszane |
| ślady innych grzybiarzy | brak / pojedyncze / liczne |
| widziani ludzie | tak / nie |
| wilgotność ściółki | sucho / lekko wilgotno / mokro |
| stan owocników | głównie młode / mieszane / głównie stare / brak |
| inne grzyby | brak / mało / dużo |
| migawka Borowika | tekst: nazwa zapisanej mapy z dnia wyjścia (patrz niżej) |
| z pamięci | tak / nie (patrz niżej) |
| uwagi | tekst |

- **Znaleziska** — jeden wiersz na wpis z Shroomera (data, godzina, id wyjścia, gatunek polski i łaciński, liczba, waga). Żółta kolumna **gatunek poprawiony** ma listę wszystkich gatunków z eksportów; pusta oznacza „bez zmiany”. Gatunek spoza listy da się wpisać po potwierdzeniu ostrzeżenia (albo dopisz go w arkuszu Listy).
- **Listy** — lista gatunków dla „gatunek poprawiony” i legenda.

**„Migawka Borowika” — prostymi słowami.** Za każdym razem, gdy w launcherze przygotujesz analizę i klikniesz „Zapisz do listy”, aplikacja zapamiętuje, jaki ranking wydzieleń pokazywała *tamtego dnia* (to jest migawka). Bez niej nie da się później uczciwie ocenić, czy aplikacja dobrze wskazywała miejsca, bo prognoza i ranking zmieniają się z dnia na dzień. W tym polu wpisz **nazwę tej zapisanej mapy**, z której korzystałeś przed wyjściem, np. „Kieleczka_29_09” (nazwy widać na liście zapisanych map w aplikacji i w `frontend/public/data/trips/index.json`, pole `name`). Jeśli wyszedłeś bez zapisanej mapy, zostaw puste.

**„Z pamięci” — prostymi słowami.** „nie” = wyjście zapisane na bieżąco (Shroomer włączony w lesie, więc godziny, ślad i znaleziska są rzeczywiste). „tak” = uzupełniasz wyjście dopiero po powrocie albo po kilku dniach z pamięci (godziny, miejsca i liczby są przybliżone). Dzięki temu przy analizie można oddzielić dokładne wyjścia od odtworzonych.

Liczba borowików to suma sztuk we wpisach, których **gatunek obowiązujący** zaczyna się od „Borowik”. Gatunek obowiązujący to „gatunek poprawiony”, a gdy ta kolumna jest pusta — gatunek z Shroomera. Liczniki (w „Wyjściach” i w „Wydzieleniach na trasie”) skrypt przelicza przy każdym uruchomieniu, więc uwzględniają Twoje poprawki gatunków.

### Kolumny i arkusz z geometrią (tylko do odczytu)
Skrypt dopisuje je na końcu arkuszy, nie ruszając Twoich kolumn ani wierszy:

- **Wyjścia:** `czas trwania [min]` (z zapisu trasy w Shroomerze) i `plik GPX` — ścieżka względem `dane_terenowe/` do pliku wygenerowanego z `routes.csv` (`dane_terenowe/trasy/RRRR-MM-DD_GGMM_<id>.gpx`, czasy punktów w UTC). Punkty z dokładnością GPS gorszą niż 50 m mają w GPX komentarz `niska dokladnosc GPS` i w rozszerzeniu `low_accuracy = true`; wszystkie punkty mają `accuracy_m`. Długość trasy jest w kolumnie `długość trasy [km]`. Istniejącego pliku GPX skrypt nie nadpisuje.
- **Znaleziska:** `lat`, `lon`, `dokładność GPS [m]` (z Shroomera), `wydzielenie` (czytelna nazwa „Oddz. 129a · Nadl. Brynek”), `stand_id` (`adr_for@rok`, ten sam identyfikator co w reszcie aplikacji), `odl. od granicy wydzielenia [m]` i `blisko granicy` (tak, gdy odległość od granicy wydzielenia jest mniejsza niż dokładność GPS znaleziska; gdy dokładności brak — mniejsza niż 25 m; wtedy wydzielenie jest mniej pewne).
- **Wydzielenia na trasie** (nowy arkusz, w całości z obliczeń): dla każdego wyjścia wszystkie wydzielenia, przez które przechodzi ślad, `czas w wydzieleniu [min]`, `borowików [szt.]` i `znalezisk ogółem [szt.]` w tym wydzieleniu. Wydzielenia bez znalezisk są wypisane (z zerami). Czas odcinka między dwoma punktami śladu dzieli się na wydzielenia proporcjonalnie do długości odcinka w każdym z nich; **przerwy dłuższe niż 10 minut między punktami nie liczą się** (to nie jest szukanie). Punkty śladu z dokładnością GPS gorszą niż 50 m (w GPX zostają, ale oznaczone) nie wyznaczają położenia: do liczenia czasu ich pozycję zastępuje najbliższy w czasie dobry punkt. Wydzielenie ze znaleziskiem, przez które ślad nie przechodzi (np. znalezisko 10 m od śladu, po drugiej stronie granicy), ma własny wiersz z czasem 0 i adnotacją. Wiersz „(brak wydzielenia w danych BDL)” zbiera czas i znaleziska poza jakimkolwiek wydzieleniem.

Geometrię wydzieleń skrypt bierze z paczek BDL (katalog z `local_config.json`, `bdl_packages_dir`), a dla punktów, których żadna paczka nie pokrywa — z WFS BDL (kafle 10 km, ten sam cache `cache/bdl_tiles_v2/` co w analizie). Wydzielenie znalezisk i czas w wydzieleniach liczone są raz, przy pierwszym pojawieniu się danych; później skrypt tylko przelicza liczniki. Żeby przeliczyć czasy od nowa (np. po zmianie reguł), uruchom skrypt z `--przelicz-trasy` — czyści on i odtwarza wyłącznie arkusz „Wydzielenia na trasie”. Nazwa nadleśnictwa pochodzi ze słownika (dla paczek RDLP Katowice, z polskimi znakami) albo z nazwy paczki/WFS (bez polskich znaków).

### Aktualizacja po nowym eksporcie
1. Wrzuć eksport do nowego podkatalogu w `dane_terenowe/shroomer/surowe/` (np. `2026-10-05/`).
2. **Zamknij dziennik w Excelu**, potem: `.venv\Scripts\python.exe scripts/aktualizuj_dziennik.py` (`--dry-run` tylko pokazuje zmiany; wymaga geopandas i openpyxl, czyli interpretera z `.venv`). Skrypt wypisuje na końcu podsumowanie: liczba wyjść, łączny czas, liczba wydzieleń na trasach, znaleziska blisko granicy.
3. Skrypt: dopisuje nowe wyjścia (tylko zakończone, `status = completed`; wyjścia z `moje_wyjscie = false` pomija) i nowe znaleziska; **nie zmienia żadnego istniejącego wiersza poza kolumnami „stan w Shroomerze” i licznikami znalezisk**; dopisuje nowe gatunki do listy. Wyjście lub znalezisko, którego nie ma już w najnowszym eksporcie, dostaje znacznik „usunięte w Shroomerze (eksport …)” w kolumnie „stan w Shroomerze” — nie jest kasowane; wróci do „aktualne”, gdy pojawi się ponownie. Zmiany nazwy czy notatki w Shroomerze po pierwszym zaimportowaniu wyjścia nie są przenoszone — poprawiaj w dzienniku.
4. Przed każdym zapisem powstaje kopia `dziennik_wyjsc.xlsx.bak`. Najnowszy eksport traktowany jest jako pełny stan Shroomera (częściowy eksport oznaczy resztę jako usuniętą; kolejny pełny cofnie znaczniki).

Nie zmieniaj nazw nagłówków w pierwszym wierszu; kolejność kolumn i sortowanie możesz zmieniać. Excel przy zapisie przenosi listę rozwijaną „gatunek poprawiony” do rozszerzenia, którego skrypt nie odczytuje — skrypt odtwarza ją po każdym zapisie, więc lista zostaje. Wiersze dopisane ręcznie (bez wartości w kolumnie „eksport”) skrypt zostawia w spokoju.

Import dziennika do formatu analizy (`wyjscia.csv`, GPX) jest osobnym, jeszcze niewykonanym krokiem — robimy go po uzupełnieniu dziennika. Tabela `wyjscia.csv` poniżej opisuje format docelowy; wartości „powód wyboru” z dziennika (`znane miejsce`, `przypadek`) przy imporcie zostaną zmapowane na `znane_miejsce` / `przypadkowo`.

## Codzienny zapis prognozy (harmonogram Windows, 6:00)

Archiwum prognoz (`cache/archiwum_prognoz/`) rośnie przy każdej analizie, ale w dni bez analizy zapisuje je `scripts/zapisz_prognoze.py` (do 10 stałych punktów, ok. 1 zapytanie Open-Meteo dziennie).

1. Punkty: `dane_terenowe/punkty_prognozy.json` (prywatny, poza repo; wzór: `scripts/punkty_prognozy.example.json`). Pola: `nazwa`, `lat`, `lon`. Wstępnie: Kieleczka, Lubliniec, Krupski Młyn, Będziemyśl — **współrzędne Lublińca i Krupskiego Młyna są przybliżone (środek miejscowości); popraw na swoje miejsca**.
2. Test ręczny: `.venv\Scripts\python.exe scripts\zapisz_prognoze.py` — powinien powstać/uzupełnić się `cache\archiwum_prognoz\prognoza_RRRR-MM-DD.parquet`.
3. Instalacja harmonogramu (PowerShell, jednorazowo; ścieżkę katalogu projektu zamień na swoją):

```powershell
$repo = "C:\Users\<uzytkownik>\Documents\Grzyby"
$action = New-ScheduledTaskAction -Execute "$repo\.venv\Scripts\python.exe" -Argument "scripts\zapisz_prognoze.py" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "Borowik-prognoza" -Action $action -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` uruchomi zapis po włączeniu komputera, jeśli o 6:00 był wyłączony. Sprawdzenie: `Get-ScheduledTaskInfo -TaskName Borowik-prognoza`; usunięcie: `Unregister-ScheduledTask -TaskName Borowik-prognoza -Confirm:$false`. Archiwum nie usuwaj przy czyszczeniu cache.
