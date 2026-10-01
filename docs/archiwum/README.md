# Archiwum dokumentacji rozwoju

Dokumenty z kolejnych etapów pracy nad Borowikiem: plany, specyfikacje, raporty faz i notatki przekazania między sesjami. Opisują **historię decyzji**, nie aktualny stan aplikacji. Wiele z nich zawiera opisy funkcji, które później zmieniono lub usunięto. Aktualny stan opisują [README](../../README.md) i [opis techniczny](../Borowik_opis_techniczny_i_walidacja.md).

| Plik / katalog | Zawartość |
|---|---|
| [`projekt-borowik.md`](projekt-borowik.md) | Dokument projektowy systemu (wersja 2.x) z kolejnymi decyzjami właściciela |
| [`CODEX-HANDOFF.md`](CODEX-HANDOFF.md) | Notatki przekazania między sesjami: zmiany, testy, otwarte ograniczenia |
| [`PLAN_WDROZENIA.md`](PLAN_WDROZENIA.md), [`NOC_RAPORT.md`](NOC_RAPORT.md) | Plan ulepszeń Fazy 0/1 i raport z jego wykonania |
| `RAPORT_FAZA_1_5.md` … `RAPORT_FAZA_4.md` | Raporty kolejnych faz (opady radarowe, paczki BDL, presja grzybiarzy, pogoda) |
| [`RAPORT_UI.md`](RAPORT_UI.md), [`RAPORT_NOWY_FRONTEND.md`](RAPORT_NOWY_FRONTEND.md) | Zmiany interfejsu i przejście na nowy frontend (Preact) |
| [`frontend-IMPLEMENTATION.md`](frontend-IMPLEMENTATION.md) | Stan pierwszej wersji frontendu (bez frameworka, wrzesień 2026) |
| [`bdl-paczki-rozpoznanie.md`](bdl-paczki-rozpoznanie.md) | Rozpoznanie paczek danych taksacyjnych BDL |
| [`superpowers/`](superpowers/) | Plany implementacji i specyfikacje projektowe |
| [`ui-zrzuty/`](ui-zrzuty/) | Zrzuty ekranu interfejsu przed zmianami i po nich |
| [`porownania/`](porownania/) | Małe wyniki porównań faz 3 i 4 |

## Usunięte duże pliki

Pełne eksporty przebiegów porównawczych (`porownania/baseline`, `faza1_5`, `faza1_6`, `nowy`) oraz mapy i tabele różnic P z Fazy 3 (`roznice_P*.csv`, `mapa_roznic_P_*.html`) zajmowały ok. 500 MB. Usunięto je z repozytorium razem z historią. Skrypty `scripts/faza3_*.py` i notatnik `notebooks/15_eksploracja_wiek.py` nadal wskazują te ścieżki: można je odtworzyć przez `python -m pipeline.prepare_trip` dla tego samego obszaru i dnia, ale wyniki będą zależały od bieżących danych zewnętrznych.

Historię przepisano przy porządkowaniu repozytorium (październik 2026). Skróty commitów cytowane w dokumentach zamieniono na odpowiadające im nowe skróty.
