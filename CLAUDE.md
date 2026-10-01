# Wskazówki dla asystentów AI

Borowik: Python (`pipeline/`) liczy ranking wydzieleń leśnych do poszukiwań prawdziwków, a frontend (`frontend/`, Preact + MapLibre + Vite) wyświetla przygotowane pliki. Opis dla ludzi: `README.md`.

## Gdzie szukać kontekstu

- Aktualny stan modelu, źródeł danych i ograniczeń: `docs/Borowik_opis_techniczny_i_walidacja.md`. Przy rozbieżności pierwszeństwo mają kod i `profiles/boletus_edulis.yaml`.
- Historia decyzji i notatki przekazania między sesjami: `docs/archiwum/CODEX-HANDOFF.md` (numerowane notatki). Dopisuj tam zmiany istotne dla kolejnej sesji.
- Interfejs i synchronizacja danych: `frontend/README.md`. Specyfikacja obecnego frontendu: `docs/archiwum/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md`.
- Pozostałe plany, raporty faz i specyfikacje są w `docs/archiwum/`. Opisują historię i mogą być nieaktualne.

## Polecenia

```powershell
uv run pytest                                   # testy Pythona
uv run python -m pipeline.prepare_trip --lat 50.53 --lon 18.61 --radius-km 20
cd frontend; npm test; npm run build; npm run sync-data; npm run dev
```

## Zasady

- Grupowanie w rejony jest aktywne (`regions_{day}.json`, przełącznik „Rejony” / „Wydzielenia”).
- Nie zapisuj danych osobowych (e-maile, nazwiska obserwatorów GBIF, prywatne współrzędne) w commitowanych plikach ani w opisach commitów.
- Dane lokalne i prywatne zostają poza gitem: `cache/`, `BDL/`, `dane_terenowe/`, `dane_telefon/`, `notebooks/output/`, `frontend/public/data/`, `local_config.json`, `launcher/launcher_config.json`.
- Zmiany wag i progów modelu wprowadza się w profilu YAML z komentarzem wskazującym uzasadnienie.
