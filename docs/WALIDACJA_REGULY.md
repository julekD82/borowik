# Reguły decyzyjne walidacji (Faza 2.0) — ZATWIERDZONE 28.09.2026

**Status: zatwierdzone przez właściciela z poprawkami (wersja 2).** Commit tego pliku powstaje **przed** jakąkolwiek analizą 2.4/2.5 (znacznik czasu w git jest dowodem, że reguł nie dopasowano do wyników). Reguł nie zmienia się po zobaczeniu wyników; jeśli reguła okaże się źle sformułowana, zapisuje się to w raporcie, a poprawiona reguła dotyczy dopiero nowej próby danych.

Żaden wynik nie zmienia modelu automatycznie. Jedyne domyślne działanie to **„przegląd składowej w osobnej sesji z właścicielem”**. Wagi H, progi klas F i α nie są zmieniane na podstawie tych testów.

## Ogólne

- **Trzy wyniki ustalone z góry** (dla każdej metryki głównej i każdego tła):
  - **„czerwona flaga”** — cały 95% przedział ufności (CI) < 0,5;
  - **„zgodne z modelem”** — cały 95% CI > 0,5 w obu tłach;
  - **„brak rozróżnienia”** — wszystkie pozostałe przypadki (w tym CI obejmujący 0,5 oraz CI > 0,5 tylko w jednym tle).
  Poniżej minimalnej liczebności: **„brak wniosku”**, bez względu na liczby.
- **Jeden przebieg analizy głównej.** Każda analiza dodatkowa (warianty, cechy, podziały) wykonana po zobaczeniu wyników jest oznaczona w raporcie jako **eksploracyjna** i nie wpływa na wynik z tego pliku.
- GBIF zawiera tylko znaleziska (brak informacji, gdzie szukano bez skutku); testy pokazują różnice między miejscami/dniami znalezisk a tłem, nie skuteczność wskazywania miejsc.
- Zbiór rekordów (klucze GBIF po filtrach i deduplikacji) zamraża się w pliku **przed** obliczeniem jakiejkolwiek metryki. Losowania z ustalonym ziarnem; bootstrap 2000 powtórzeń.

## 2.4 Kontrola przestrzenna H

- **Pytanie:** czy H jest wyższe w miejscach znalezisk borowika niż w tle?
- **Hipoteza:** AUC(H) > 0,5.
- **Dane (analiza główna):** rekordy *B. edulis* z niepewnością ≤ 100 m, **od 2021 roku**, w lasach D-STAN z danymi BDL. Wszystkie lata = wariant dodatkowy.
- **Źródło H:** w analizie głównej **skład z WFS dla wszystkich rekordów** (jedno źródło, profil na dzień analizy, bez zmiany parametrów). Wariant z paczkami BDL tylko dla RDLP Katowice, opisowo.
- **Bufor:** wartość H ważona powierzchnią w buforze równym niepewności współrzędnych (nie tylko wydzielenie z punktem).
- **Maska strukturalna:** rekordy w wydzieleniach niespełniających maski dostają **H = 0** (jak R w rankingu); ich liczba jest raportowana osobno.
- **Nieznany kod:** jeśli > 20% rekordów trafia w nieznany kod siedliska lub gatunku, analiza główna je pomija; odsetek jest raportowany.
- **Deduplikacja:** ten sam obserwator + to samo wydzielenie + ten sam rok = jeden rekord.
- **Dwa tła, zawsze razem:** (a) rekordy innych grzybów w lesie D-STAN (ta sama filtracja niepewności i lat); (b) rekordy niegrzybowe (rośliny, zwierzęta) w lesie D-STAN, **tylko z miesięcy VII–XI**, próbka losowa do 5 × liczby borowików.
- **Metryka:** AUC dla H względem każdego tła; 95% CI bootstrap **po obserwatorach**.
- **Minimalna liczebność:** ≥ 100 rekordów borowika (po deduplikacji i filtrach analizy głównej) w lesie D-STAN i ≥ 30 różnych obserwatorów. Poniżej: „brak wniosku”.
- **Reguła decyzji:** wynik wg trzech kategorii z sekcji „Ogólne” (uwzględniając oba tła); „czerwona flaga” → przegląd składowej H.
- **Cechy dodatkowe** (bonitacja, stan siedliska, pokrywa gleby, granica oddziału, `lower_storeys_weight`): tylko opisowo, eksploracyjnie, z uwagą o wielokrotnym testowaniu; wynik to lista cech do Fazy 5, nie wagi.

## 2.5 Kontrola czasowa F

- **Pytanie:** czy F jest wyższe w dniach znalezisk niż w dniach kontrolnych z tego samego miejsca?
- **Hipoteza:** średnia ranga F dnia znaleziska względem dni kontrolnych > 0,5.
- **Kolejność:** 2.6 (E-OBS) musi być ukończone przed 2.5.
- **Źródło pogody:** E-OBS dla wszystkich wariantów.
- **Dane:** rekordy *B. edulis* z pełną datą, niepewność ≤ 1000 m, ≥ 5 różnych lat; dni kontrolne ±15 dni (po obsłudze dat z 1.8a).
- **Deduplikacja:** ten sam obserwator + ten sam dzień + do 1 km = jeden rekord.
- **Wariant główny:** F **bez G_season**. Pozostałe warianty (sam kalendarz, samo M, sama T, model stały, F z G_season) są porównawcze.
- **Dwa tła jako granice wyniku, zawsze razem:** (a) wszystkie dni w oknie — wynik **zawyżony**; (b) dni, w których w promieniu 20 km zgłoszono inne grzyby — wynik **zaniżony**. Rekord bez ≥ 3 dni kontrolnych z innymi grzybami w promieniu 20 km jest w tle (b) pomijany; liczba pominiętych jest raportowana.
- **Metryka główna:** średnia ranga z 95% CI (bootstrap po latach i lokalizacjach); hipoteza: średnia ranga > 0,5.
- **Minimalna liczebność:** ≥ 150 rekordów z pełną datą (po deduplikacji) z ≥ 5 różnych lat. Poniżej: „brak wniosku”.
- **Reguła decyzji:** trzy kategorie z sekcji „Ogólne”. **Dodatkowa czerwona flaga:** cały 95% CI różnicy (F bez G_season − sam kalendarz) < 0 w obu tłach.
- **Bez dostrajania parametrów F na tych danych.**

## Znane ograniczenia (do sekcji „Czego te testy nie pokazują”)
- Zbiór GBIF zdominowany przez iNaturalist (92% rekordów) i kilka najaktywniejszych osób (top-5 = 41% w Polsce).
- Rekordy skupione w latach 2024–2025 (ok. 59% rekordów ≤ 100 m).
- Miejsca znalezisk zależą od tego, gdzie ludzie chodzą (drogi, parkingi), co jest skorelowane z H i P.
- Tło (a) i tło (b) skrzywiają wynik w przeciwnych kierunkach; nie wolno raportować tylko jednego.
