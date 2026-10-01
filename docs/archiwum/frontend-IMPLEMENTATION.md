# Stan wdrożenia — 2026-09-24

> **Dokument historyczny.** Opisuje interfejs sprzed 2026-10 (Vite + TypeScript bez frameworka: `main.ts`, `map.ts`, `model.ts`), zastąpiony nowym frontendem w Preact. Aktualny projekt: `docs/archiwum/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md`; stan i lista kontrolna: `docs/archiwum/RAPORT_NOWY_FRONTEND.md`.

> **Decyzja użytkownika (2026-09-24): grupowanie wyłączone.** Ranking i mapa działają na pojedynczych wydzieleniach, bez `regions.json` i łączenia geometrii. Opisy rejonów poniżej dokumentują poprzedni etap. Szczegóły: `docs/archiwum/CODEX-HANDOFF.md` w katalogu projektu.

Podstawa: `docs/archiwum/superpowers/specs/2026-09-24-borowik-frontend-design.md`, główna dokumentacja wersji 2.0 i kontrakty rzeczywistego eksportu w gałęzi `worktree-borowik-faza2-mvp-backend`.

- [x] Vite + TypeScript, statyczny frontend bez frameworka.
- [x] GeoJSON EPSG:4326 obok GeoParquet, automatyczne wywołanie w `prepare_trip`.
- [x] `d_park_m` w eksporcie nowych wyników; jawny brak danych dla starszych plików.
- [x] Synchronizacja kompletnego zestawu danych, kontrole dat i identyfikatorów.
- [x] Mapa MapLibre/OpenFreeMap i obrysy Turf z niebuforowanych poligonów.
- [x] Karty rejonów, klasa F, H, pewność i powody, uzasadnienia, data, status dostępności.
- [x] Widok wydzieleń per rejon, wybór mapą i klawiaturą/listą, szczegóły modelu.
- [x] Zapis i odczyt `localStorage`, zakładka zapisanych rejonów, linki Google Maps.
- [x] Ekrany błędów i pustych wyników, fallback przy niedostępności podkładu/WebGL.
- [x] Testy automatyczne i sprawdzenie UI na realnych danych z Piły.

Uwagi wymagające dalszego backendu: współrzędne rzeczywistych wejść, odległość/czas dojazdu samochodem, daty pobrania warstw oraz status weryfikacji zakazów per wydzielenie. Szczegóły i odstępstwa w `README.md`. Nowy frontend nie uruchamia analiz z przeglądarki, nie dodaje hostingu, PMTiles ani PWA.

Aktualny zestaw demonstracyjny to istniejące dane z 24.09.2026, nie dane sztuczne. Zmieniono jedynie format geometrii; nie pobierano ponownie pogody/zakazów i nie uzupełniano starych odległości szacunkiem.
