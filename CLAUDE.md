# Kontekst kontynuacji projektu

Przed dalszą pracą przeczytaj [docs/CODEX-HANDOFF.md](docs/CODEX-HANDOFF.md): zawiera wykonane przez Codex zmiany frontendu i obsługi promienia, instrukcje, wyniki testów i nadal otwarte ograniczenia. Aktualizuj tę notatkę po zmianach istotnych dla kolejnej sesji. Aktualny stan aplikacji i jej ograniczeń opisuje też `docs/Borowik_opis_techniczny_i_walidacja.md`.

Aktualna implementacja znajduje się w tym katalogu roboczym (`Grzyby`, ten sam katalog, w którym leży ten plik) — `pipeline/`, `frontend/`, `tests/` na poziomie repo. Starsza notatka mówiła o osobnym katalogu roboczym `borowik-faza2-mvp-backend` jako jedynej aktualnej implementacji; to nieaktualne, nie kieruj się tym — ten katalog już nie istnieje (albo nigdy nie był tym, do czego odnosiła się ta notatka), a kod tutaj jest aktualny (`--radius-km` działa, wiele kafli i wszystkie przecinane RDLP, grupowanie w rejony aktywne — patrz niżej).

Specyfikacja frontendu: `docs/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md` (poprzednia: `docs/superpowers/specs/2026-09-24-borowik-frontend-design.md`). Instrukcja użytkowania i odstępstwa wynikające z brakujących danych: `frontend/README.md`.

Grupowanie w rejony jest aktywne. `pipeline/prepare_trip.py` liczy i eksportuje rejony (`regions_{day}.json`), a frontend ma przełącznik „Rejony” / „Wydzielenia” (zapamiętywany w `localStorage`), domyślnie startujący w widoku rejonów, gdy są dostępne.

Plan wdrożenia ulepszeń (Faza 0/1, noc 27/28.09.2026) i jego wynik: `docs/PLAN_WDROZENIA.md`, `docs/NOC_RAPORT.md`.
