# Reguły decyzyjne walidacji (Faza 2.0) — PROJEKT DO ZATWIERDZENIA

**Status: projekt agenta, niezatwierdzony.** Testów 2.4 i 2.5 nie wolno uruchamiać, dopóki właściciel nie zatwierdzi tego pliku, a jego commit nie powstanie **przed** jakąkolwiek analizą (znacznik czasu w git jest dowodem, że reguł nie dopasowano do wyników). Po zatwierdzeniu reguł nie zmienia się; jeśli reguła okaże się źle sformułowana, zapisuje się to w raporcie, a poprawiona reguła dotyczy dopiero nowej próby danych.

Żaden wynik poniżej nie zmienia modelu automatycznie. Jedyne domyślne działanie to **„przegląd składowej w osobnej sesji z właścicielem”**. Wagi H, progi klas F i α nie są zmieniane na podstawie tych testów.

Dane wejściowe wszystkich testów: rekordy GBIF *Boletus edulis* (Polska), zebrane i policzone w 2.3 (`docs/RAPORT_FAZA_2.md`). GBIF zawiera tylko znaleziska, bez informacji, gdzie szukano bez skutku — testy pokazują różnice między miejscami znalezisk a tłem, nie skuteczność wskazywania miejsc.

Zbiór wspólny: rekordy z `coordinateUncertaintyInMeters ≤ 100 m` (2.4) lub ≤ 1000 m (2.5), pełna data zdarzenia, `hasGeospatialIssue = false`. Zbiór rekordów zamraża się (zapis kluczy GBIF do pliku) **przed** obliczeniem jakiejkolwiek metryki.

## 2.4 Kontrola przestrzenna H

- **Pytanie:** czy H jest wyższe w miejscach znalezisk borowika niż w tle?
- **Hipoteza:** AUC(H) > 0,5 (kierunek zgodny z modelem).
- **Dane:** rekordy B. edulis, niepewność ≤ 100 m, w lasach D-STAN z danymi BDL (WFS/paczki). Wartość H = średnia ważona powierzchnią w buforze równym niepewności (nie tylko wydzielenie z punktem). H liczone z profilu na dzień analizy bez zmian parametrów.
- **Dwa tła, zawsze razem:** (a) rekordy innych grzybów w lesie D-STAN, ta sama filtracja niepewności; (b) rekordy niegrzybowe (rośliny, zwierzęta) w lesie D-STAN, próbka losowa do 5 × liczby borowików, z ustalonym ziarnem losowania.
- **Metryka:** AUC dla H względem każdego tła; 95% przedział ufności metodą bootstrap **po obserwatorach** (losowanie obserwatorów ze zwracaniem, 2000 powtórzeń, ziarno ustalone).
- **Minimalna liczebność:** ≥ 100 rekordów borowika w lesie D-STAN i ≥ 30 różnych obserwatorów. Poniżej: **„brak wniosku”**, bez względu na liczby.
- **Reguła decyzji:** czerwona flaga (przegląd składowej H), gdy **cały** 95% przedział ufności AUC względem któregokolwiek tła leży poniżej 0,5. Wynik w pozostałych przypadkach jest raportowany bez działania.
- **Cechy dodatkowe** (bonitacja, stan siedliska, pokrywa gleby, granica oddziału, `lower_storeys_weight`): tylko opisowo, tą samą metodą; przy wielu cechach wyraźna uwaga o wielokrotnym testowaniu. Wynik to lista cech wartych sprawdzenia w Fazie 5, nie wagi.

## 2.5 Kontrola czasowa F

- **Pytanie:** czy F jest wyższe w dniach znalezisk niż w dniach kontrolnych z tego samego miejsca?
- **Hipoteza:** ranga F dnia znaleziska względem dni kontrolnych ma medianę > 0,5.
- **Dane:** rekordy B. edulis z pełną datą, niepewność ≤ 1000 m, ≥ 5 różnych lat; dni kontrolne ±15 dni od dnia znaleziska (po obsłudze dat z 1.8a). Cechy pogodowe z jednego źródła dla wszystkich wariantów (E-OBS lub archiwum Open-Meteo).
- **Dwa tła jako granice wyniku, zawsze razem:** (a) wszystkie dni w oknie — wynik **zawyżony**; (b) dni, w których w promieniu 20 km zgłoszono inne grzyby — wynik **zaniżony**. Prawdziwa wartość leży pomiędzy; raport podaje obie.
- **Warianty:** F bez G_season, sam kalendarz, samo M, sama T, model stały (referencja).
- **Metryka:** średnia ranga i AUC dnia znaleziska; 95% przedział ufności bootstrap **po latach i lokalizacjach** (2000 powtórzeń, ziarno ustalone).
- **Minimalna liczebność:** ≥ 150 rekordów z pełną datą z ≥ 5 różnych lat. Poniżej: **„brak wniosku”**.
- **Reguła decyzji:** czerwona flaga (przegląd składowej F), gdy cały 95% przedział ufności rangi leży poniżej 0,5 dla tła (a) lub (b). **Bez dostrajania parametrów F na tych danych.**

## Znane ograniczenia (do sekcji „Czego te testy nie pokazują”)
- Zbiór GBIF jest zdominowany przez iNaturalist (92% rekordów) i kilka najaktywniejszych osób (top-5 = 41% rekordów w Polsce).
- Rekordy koncentrują się w latach 2024–2025 (ok. 59% rekordów ≤ 100 m), więc „≥ 5 lat” nie oznacza równomiernego pokrycia lat.
- Miejsca znalezisk są ustalane przez to, gdzie ludzie chodzą (drogi, parkingi), więc H i P są skorelowane z obecnością obserwatora.
- Tło (a) i tło (b) skrzywiają wynik w przeciwnych kierunkach; nie wolno raportować tylko jednego.
