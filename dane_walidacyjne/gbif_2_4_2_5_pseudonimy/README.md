# Zamrożone zbiory walidacji 2.4 i 2.5 (GBIF) — kopia z pseudonimami

Zbiory rekordów GBIF zamrożone przed obliczeniem metryk walidacji 2.4 (`notebooks/13_walidacja_2_4.py`, 29.09.2026) i 2.5 (`notebooks/12_walidacja_2_5.py`, 28.09.2026); reguły: `docs/WALIDACJA_REGULY.md`, wyniki: `docs/RAPORT_FAZA_2.md`. Plik odtwarza `scripts/kopiuj_zbiory_gbif.py` (decyzja właściciela 30.09.2026).

## Oryginały (tylko lokalnie, poza gitem)

Oryginały zawierają nazwy obserwatorów GBIF (`recordedBy`), więc nie trafiają do repozytorium. Leżą w dwóch miejscach: `notebooks/output/walidacja/` (tam czytają je notatniki 12–16) oraz kopia w `dane_walidacyjne/gbif_2_4_2_5/` (w `.gitignore`), razem z tabelą przypisań pseudonimów `przypisania_obserwatorow.csv`.

| Plik | SHA-256 oryginału |
|---|---|
| `2_4_zbior_pozytywy.csv` | `08351485fdfcec713ecb00ebca93e489a10aefb7c7e71915650f74cc309b7853` |
| `2_4_zbior_tlo_a.csv` | `f7395d5a1adad5126c6a03cce1677f2b31f1d72c6a4efea894703e4fcda1bd4c` |
| `2_4_zbior_tlo_b.csv` | `1259074f73810e8f980625a7d92f72f1a996bef461c2617014a5901866f93e6e` |
| `2_5_zbior_zamrozony.csv` | `6a048d63df698bd2bed82d57b47e837fc6bb366f90519534855e625fadf6622e` |

## Kopie w tym katalogu

Te same wiersze i kolumny co oryginały; zmienione tylko kolumny `observer` i `observer_id`: każda osoba dostaje numer `obs_001`, `obs_002`, … (wspólny dla wszystkich czterech plików, kolejność pierwszego wystąpienia; 635 osób). Puste pola i identyfikatory `anon_<klucz GBIF>` (rekordy bez obserwatora) bez zmian. Grupowanie po obserwatorze (deduplikacja, bootstrap po obserwatorach w 2.4) daje więc te same wyniki.

| Plik | Wiersze | SHA-256 kopii |
|---|---|---|
| `2_4_zbior_pozytywy.csv` | 229 | `899b6f0dc224f77cd9b011e86badc48487e0f4b86c2d456f1643bf0fad1af211` |
| `2_4_zbior_tlo_a.csv` | 1104 | `a870803eaae4737aacac97a8e5f2e579511a384a357585da3e3c6490041ee2a3` |
| `2_4_zbior_tlo_b.csv` | 522 | `5b28cec38a85c9bdbfa5fe380213d737e47e8402be332483908257052a98876c` |
| `2_5_zbior_zamrozony.csv` | 482 | `739d493d28c0e9cc86d1020e786305ff3a6a67deb64b1d6ad6f99504abe23760` |

Zastrzeżenia:
- Klucz GBIF (`key`) pozwala odnaleźć rekord źródłowy w GBIF razem z obserwatorem — pseudonim chroni tylko przed trzymaniem nazwisk w repozytorium, nie jest anonimizacją.
- Nazwy w oryginałach 2.4 mają uszkodzone polskie znaki (`�`) — tak zostały zapisane 29.09; nie wpływa to na grupowanie.
- Licencje rekordów zależą od zbioru GBIF (`dataset`; iNaturalist głównie CC BY-NC). Źródło: GBIF.org, API wyszukiwania występowań, zapytania z 28–29.09.2026 (bez DOI pobrania).
- Dni tła (b) w 2.5 (inne grzyby w promieniu 20 km) nie są w tych plikach — pochodzą z cache zapytań GBIF w `.cache/gbif_inventory/` (lokalnie).
