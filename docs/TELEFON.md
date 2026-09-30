# Mapa na telefon (KMZ): Locus Map i Guru Maps

Eksport zamienia wynik analizy w jeden plik **KMZ** z kolorowymi wydzieleniami, 5 najlepszymi rejonami i parkingami. Otwierasz go w aplikacji do map offline i idziesz do lasu bez internetu.

**Uwaga o stanie sprawdzenia:** plik jest poprawnym KML/KMZ (testy parsują go i sprawdzają kolory, foldery i współrzędne), ale nie był jeszcze otwierany na telefonie. Nazwy menu poniżej opisują typowe wersje aplikacji i mogą się różnić. Przed pierwszym wyjazdem otwórz plik w domu i obejrzyj mapę.

## 1. Wygenerowanie pliku

- W launcherze: wybierz **Źródło** (bieżąca analiza albo zapisana migawka) i kliknij **Eksport na telefon**. Dla bieżącej analizy nazwa pliku bierze się z pola „Nazwa miejsca”.
- Z wiersza poleceń: `python scripts/eksport_telefon.py [--nazwa "Zawadzkie"] [--migawka <id>]`.

Plik trafia do katalogu `telefon_dir` z `local_config.json` (domyślnie `dane_telefon/` obok tego pliku, poza repozytorium) i nazywa się `borowik_<obszar>_<data>.kmz`, gdzie data to dzień analizy. Skrypt wypisuje rozmiar; cel to poniżej 10 MB. Jeśli plik byłby większy, pomija klasę „4 · pozostałe” i podaje rozmiar ponownie. Dla przykładowej analizy Zawadzkie (20 km, 14 347 wydzieleń w masce) KMZ ma 2,3 MB.

### Synchronizacja z telefonem

Ustaw `telefon_dir` na folder synchronizowany z chmurą, np. w `local_config.json`:

```json
{ "telefon_dir": "C:\\Users\\<ty>\\OneDrive\\Borowik" }
```

Ścieżka może być względna (liczona od katalogu z `local_config.json`). Na telefonie oznacz plik jako dostępny offline (Dysk Google: „Udostępnij offline”, OneDrive: „Zawsze zachowuj na tym urządzeniu”). **Zaimportuj go do aplikacji jeszcze w domu**, bo w lesie nie pobierzesz go z chmury.

## 2. Co jest w pliku

Foldery działają jak legenda; włączasz i wyłączasz je w menedżerze punktów/zakładek aplikacji.

| Folder | Kolor | Co obejmuje |
|---|---|---|
| **Wynik R** → „1 · najlepsze 5%” | cyjan | wydzielenia z najwyższym R |
| „2 · 5–20%” | zielony | |
| „3 · 20–50%” | żółty | |
| „4 · pozostałe” | szary, półprzezroczysty | reszta |
| **Bez presji (domyślnie ukryte)** → te same cztery klasy z prefiksem „Bez presji · ” | jak wyżej | klasy liczone z `R_bez_presji` |
| **Rejony (5 najlepszych)** | punkty | „Rejon 1 · Łaziska” itd. (kolejność jak w aplikacji, wg rankingu rejonu) |
| **Parkingi** | punkty | tylko parkingi (bez wejść i bram) |

- **Percentyl liczony jest w tej analizie**, wśród wydzieleń, które przeszły maskę. Kolor „cyjan” oznacza „najlepsze 5% w tym obszarze i dniu”, a nie stałą wartość R. Plików z różnych analiz nie porównuj kolorami; porównuj liczby w opisie.
- Wydzielenia poza maską (m.in. za młode drzewostany, nie las) są pominięte.
- Napis na wydzieleniu to `R <liczba>`. Po dotknięciu zobaczysz opis: numer wydzielenia, R, R bez presji, H, F, P.
- Geometrie są uproszczone (tolerancja ok. 3 m) i zapisane w WGS84.
- Zestaw „Bez presji” jest oznaczony jako ukryty. Jeśli aplikacja ignoruje ten znacznik i pokazuje go od razu, wyłącz folder ręcznie. Starsze migawki nie mają `R_bez_presji`, `access_points.json` ani nazw miejscowości, więc odpowiednie foldery są pomijane albo rejony nazywają się tylko „Rejon N”.
- Jeśli telefon zwalnia (kilkanaście tysięcy wielokątów to dużo), wyłącz folder „4 · pozostałe”, który zawiera połowę wydzieleń.

## 3. Android: Locus Map

**Otwarcie pliku**
1. Skopiuj lub zsynchronizuj plik na telefon (np. Dysk Google, OneDrive, przewód USB).
2. W menedżerze plików albo w aplikacji Dysk/OneDrive dotknij pliku `.kmz` i wybierz **Otwórz w Locus Map** (albo „Udostępnij” → Locus Map). Locus zapyta o import. Alternatywnie w Locusie: menu → **Punkty** (menedżer danych) → import z pliku.
3. Zaimportowane foldery pojawią się w menedżerze punktów (folder = folder KML). Włącz widoczność folderów, które chcesz widzieć na mapie.
4. Wielokąty KML Locus zwykle importuje jako obszary/ślady. Jeśli po imporcie widać tylko kontury bez kolorowego wypełnienia, sprawdź w ustawieniach wyglądu obszarów i zgłoś to (wtedy zmienię format).

**Mapa offline**
1. Menu → **Mapy** → wybierz mapę offline i pobierz obszar (LoMaps, wektorowe mapy Locusa oparte na OpenStreetMap, są darmowe i działają bez internetu). Dokładne nazwy pozycji zależą od wersji.
2. Pobieraj na Wi-Fi, przed wyjazdem. Wybierz cały region obejmujący promień analizy (np. województwo) i sprawdź, czy mapa wyświetla się po włączeniu trybu samolotowego.
3. Dla pewności zostaw mapę jako aktywną (nie „mapa online”).

**Lokalizacja i obrót mapy**
1. Włącz GPS w telefonie i przyznaj Locusowi uprawnienie do lokalizacji (Ustawienia Androida → Aplikacje → Locus Map → Uprawnienia → Lokalizacja: „Podczas używania aplikacji”).
2. Dotknij ikony GPS/celownika na mapie, aby wycentrować mapę na sobie i włączyć śledzenie pozycji.
3. Kolejne dotknięcie ikony przełącza tryby (m.in. wycentrowanie z obracaniem mapy zgodnie z kierunkiem ruchu lub kompasem). Rotację można też ustawić w ustawieniach mapy (obrót mapy: wyłączony / kierunek ruchu / kompas).

## 4. iPhone: Guru Maps

**Otwarcie pliku**
1. Zsynchronizuj plik z Dyskiem/OneDrive albo wgraj go do aplikacji Pliki (iCloud Drive).
2. Otwórz plik `.kmz` w aplikacji Pliki (albo Dysk/OneDrive), dotknij **Udostępnij** → **Guru Maps** (albo „Otwórz w…”).
3. Guru Maps importuje dane do **Moich miejsc / Zakładek** (`My Places`). Włącz widoczność zaimportowanej kolekcji, a w niej foldery, które chcesz widzieć.
4. Guru Maps ma ograniczone wsparcie wielokątów z KML. Jeśli widać tylko punkty (rejony, parkingi), a wydzielenia nie, daj znać, bo wtedy potrzebny będzie inny format wydzieleń dla iPhone'a.

**Mapa offline**
1. **Mapy** (menu główne) → **Pobierz mapy** → wybierz kraj/region (Polska, województwo) i pobierz na Wi-Fi.
2. Sprawdź w trybie samolotowym, że mapa i zaimportowane wydzielenia są widoczne.

**Lokalizacja i obrót mapy**
1. Ustawienia iOS → Prywatność i bezpieczeństwo → Usługi lokalizacji → Guru Maps: „Podczas używania aplikacji” (dokładna lokalizacja włączona).
2. W aplikacji dotknij przycisku lokalizacji (strzałka), aby wycentrować mapę na sobie.
3. Kolejne dotknięcie włącza tryb kompasu, w którym mapa obraca się zgodnie z kierunkiem, w którym idziesz lub patrzysz (ikona zmienia wygląd). Obrót można też wykonać dwoma palcami, a powrót północy dotykiem kompasu.

## 5. Po co jest ten plik, a czego nie robi

- To zrzut wyniku analizy z konkretnego dnia; nie odświeża się sam. Przed kolejnym wyjazdem wygeneruj nowy plik i zaimportuj go, usuwając stary (kolory zależą od tej konkretnej analizy).
- Aplikacje pokazują pozycję GPS względem wydzieleń, ale nie zastępują map leśnych ani oznaczeń w terenie. Sprawdź zakazy wstępu i zamknięcia lasów przed wyjazdem (aplikacja ostrzega o nich w karcie wydzielenia, KMZ nie).
