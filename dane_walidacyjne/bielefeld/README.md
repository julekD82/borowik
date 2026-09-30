# Dane walidacyjne: monitoring *Boletus edulis* koło Bielefeld (2015–2024)

Trwała kopia danych do walidacji (plan 2.8). Pliki w tym katalogu odtwarza `scripts/pobierz_bielefeld.py` (pobranie z Zenodo, kontrola MD5/SHA-256, zapis tabel przez `pipeline/bielefeld.py::write_validation_tables`).

## Źródło i cytowanie

- Brejon Lamartinière E., Hoffman M. „Predicting porcini: a decade of sporocarp monitoring reveals the meteorological triggers of *Boletus edulis* fruiting in central European beech forests”. bioRxiv, doi [10.64898/2025.12.12.693895](https://doi.org/10.64898/2025.12.12.693895) (wersja z 08.06.2026).
- Dane i kod: Zenodo, doi [10.5281/zenodo.20591123](https://doi.org/10.5281/zenodo.20591123), „ebrejonl/Boletus_fruiting_triggers: Expansion of analysis V1.2”, 08.06.2026 (GitHub `ebrejonl/Boletus_fruiting_triggers`, commit `7967c6d`).
- Wersja pierwsza (tylko do porównania): Zenodo, doi [10.5281/zenodo.17881359](https://doi.org/10.5281/zenodo.17881359), 10.12.2025, plik `Data_ready.csv`.
- **Licencja: CC BY 4.0** (obie wersje). Pliki w tym katalogu to przekształcenie danych autorów (zmiana formatu i nazw kolumn, bez zmiany wartości).
- Pogoda w obu plikach pogodowych pochodzi z E-OBS. **Warunki E-OBS** (ECA&D data policy, 16.09.2019): wyłącznie niekomercyjne badania i edukacja; wyniki oparte na tych danych należy publikować bez zwłoki. **Wymagane podziękowanie** (strona E-OBS / Copernicus): „We acknowledge the E-OBS dataset from the EU-FP6 project UERRA (https://www.uerra.eu) and the Copernicus Climate Change Service, and the data providers in the ECA&D project (https://www.ecad.eu)”. **Wymagane cytowanie:** Cornes, R., G. van der Schrier, E.J.M. van den Besselaar, and P.D. Jones. 2018: An Ensemble Version of the E-OBS Temperature and Precipitation Datasets, J. Geophys. Res. Atmos., 123. doi:10.1029/2017JD028200.

## Pobranie

- Data pobrania: 30.09.2026.
- SHA-256 plików źródłowych (`cache/bielefeld/SHA256SUMS`):
  - `Boletus_fruiting_triggers-V1.2.zip` (712 920 B, MD5 Zenodo `a5299db56022af2620635a36274e811f`): `ee19dfc414676cbcd4993eca75ea77a9fd1607d18bc4e0bdb7094a4ab07ee07a`
  - `v1_Data_ready.csv` (99 934 B, MD5 `703a8d90c033197431cd7b6fd6743be5`): `a05879d10a2a21bc85238998bc11fee1156c038d5596d845ad1391f9825d94ca`
- Zawartość zipu: `Code_clean_Jun8.R` (analiza autorów), `Data/Environmental_fruiting_data_jun8.csv` (jedyny plik danych), `.gitignore`. Surowe dane z pojedynczymi owocnikami i współrzędnymi stanowisk (`Note_data_no_env_Nov21.csv`) **nie są publiczne** (teren prywatny) — tak piszą autorzy w kodzie.

## Pliki

### `owocniki_dzienne.csv` (3660 wierszy; SHA-256 `070b261482f0c45630720859eb4b5bcc00ef77de3064f0f897bedb458a3b6061`)

| Kolumna | Opis |
|---|---|
| `data` | dzień (RRRR-MM-DD), 1.08–30.11 w latach 2015–2024 (1220 dni) |
| `stanowisko` | `All` = wszystkie stanowiska razem; `Site_A` = stanowiska 3 i 23 (małe stanowisko obok dołączone przez autorów); `Site_B` = stanowisko 6. `Site_A` i `Site_B` są częścią `All` (nie sumować) |
| `nowe_owocniki` | liczba rekordów owocników z tego dnia (`Mnb` u autorów = `n()` rekordów z datą) |
| `wizyta` | `1` = na pewno była wizyta (są owocniki); **puste = nie wiadomo** |

### `pogoda_autorow_eobs.csv` (1220 wierszy; SHA-256 `ca7b5392a8c305ab483ea81cc515699c902bf04566dfc461910d71398031d2d0`)

| Kolumna | Opis |
|---|---|
| `data` | dzień, jak wyżej |
| `tg` | średnia dobowa temperatura powietrza, °C (E-OBS TG) |
| `rr` | suma dobowa opadu, mm (E-OBS RR) |

Obie zmienne autorzy wzięli z E-OBS 0,1° pakietem `climateExtract` (`ecad_v = NULL`, czyli wersja najnowsza w chwili ekstrakcji — numer wersji nie jest podany) i interpolowali dwuliniowo na środek obszaru (52°03'42,2"N 8°27'03,3"E). Interpolacja daje czasem wartości bliskie zeru z błędem zaokrąglenia (np. −8·10⁻¹⁶ mm). Pogoda jest identyczna dla wszystkich trzech „stanowisk”. Brak TN/TX, brak dni sprzed 1.08.

### `pogoda_eobs_v33e_komorka.csv` (12 419 wierszy; SHA-256 `9702cece59023b73b9826554be76d02b276e94079bb2587684e778ef7394b02d`)

Własna ekstrakcja: E-OBS **v33.0e** (ensemble mean, 0,1°; ta sama wersja co walidacja 2.5), komórka o środku **52,05 N, 8,45 E** — zawiera środek obszaru z pracy (52,062 N, 8,451 E). Pobranie 30.09.2026 (`scripts/pobierz_eobs.py --obszary BI`, pliki przycięte do 51,6–52,6 N, 7,9–9,0 E w `cache/eobs/*_BI.npz`), zapis: `notebooks/17_bielefeld_wczytanie.py` (`pipeline/bielefeld.py::write_eobs_cell`). Dni 1.01.1991–31.12.2024, bez braków.

| Kolumna | Opis |
|---|---|
| `data` | dzień |
| `tg`, `tn`, `tx` | temperatura średnia / minimalna / maksymalna doby, °C |
| `rr` | suma dobowa opadu, mm |

Wartości w E-OBS są zapisane w setnych, więc dwa miejsca po przecinku są dokładne.

**Porównanie z pogodą autorów** (1220 dni 1.08–30.11 2015–2024; różnica = nasze − autorzy):

| Ekstrakcja | TG: korelacja | TG: średnia różnica | TG: śr. błąd bezwzgl. (maks.) | RR: korelacja | RR: średnia różnica | RR: śr. błąd bezwzgl. (maks.) |
|---|---|---|---|---|---|---|
| najbliższa komórka (ten plik) | 0,9998 | −0,02 °C | 0,09 °C (0,48) | 0,998 | +0,02 mm | 0,14 mm (2,7) |
| interpolacja dwuliniowa (jak autorzy) | 0,9998 | +0,00 °C | 0,08 °C (0,48) | 0,999 | +0,00 mm | 0,12 mm (2,0) |

Interpolacja dwuliniowa jest bliżej danych autorów, ale nie identyczna — autorzy użyli najpewniej innej wersji E-OBS. Różnice są małe wobec zmienności dobowej; analizy aplikacji używają najbliższej komórki (tak jak 2.5).

## Znane ograniczenia (ważne przy każdej analizie)

1. **Zera nie są prawdziwymi zerami.** Autorzy wstawili 0 w każdy dzień bez rekordu (`ifelse(is.na(Mnb), 0, Mnb)`), a dni wizyt nie ma w danych. Wizyty odbywały się 2–4 razy w tygodniu od początku VIII do mrozów, więc ok. połowa „zer” to dni bez wizyty, a liczba z dnia wizyty obejmuje owocniki, które wyrosły od poprzedniej wizyty (0–4 dni wcześniej). Dni z owocnikami rozkładają się równo na dni tygodnia (18–25 na każdy), więc nie da się odtworzyć harmonogramu wizyt. Dni po zakończeniu sezonu (po mrozach) też mają 0.
2. **Brak identyfikatora owocnika** w danych publicznych. Nie da się sprawdzić, czy ten sam owocnik nie był liczony przy kolejnych wizytach; kod autorów liczy rekordy (`n()`) z datą, praca opisuje je jako nowe owocniki.
3. **Brak wag i wysiłku.** Brak liczby stanowisk odwiedzonych danego dnia; stanowiska były dokładane w kolejnych latach (15–29 stanowisk, 30 m²–1,2 ha), więc sumy roczne nie są porównywalne między latami bez efektu roku.
4. **Brak współrzędnych stanowisk** (tylko środek obszaru z pracy); jeden bukowy las w NW Niemczech.
5. Pogoda E-OBS 0,1° (ok. 7 × 11 km), bez wilgotności gleby; wersja E-OBS autorów nieznana (patrz porównanie wyżej).
6. Z tej pracy pochodzą parametry F aplikacji (optimum 13 °C, okna 26/20 dni, kara za upał 17,5 °C) — **dane nie są niezależną walidacją F**; nadają się do sprawdzenia kształtu (np. wag opadu w czasie).

## Kontrola wczytania (`notebooks/17_bielefeld_wczytanie.py`)

- 1905 owocników; 4 w 2016, 354 w 2020; dni z owocnikami 05.08–21.11 (MM-DD) — zgodnie z pracą.
- Udział dni bez owocników: **85,8% w zakresie 05.08–21.11** (1090 dni, jak w pracy i w wersji pierwszej), 87,3% w całym pliku 1.08–30.11 (1220 dni).
- Wersja pierwsza (`Data_ready.csv`): te same liczby owocników dzień po dniu, ale **inna pogoda** (różnica TG do 0,38 °C, RR do 3,0 mm/dobę — prawdopodobnie inna wersja E-OBS) i tylko okno 5-dniowe; dlatego zachowana w `cache/bielefeld/` do porównań.
- Średnie kroczące z `tg`/`rr` odtwarzają kolumny `rollT_w`/`rollP_w` autorów (różnica < 10⁻¹³; okna wyrównane do prawej, dzień oceny w oknie, liczone w obrębie roku kalendarzowego).
