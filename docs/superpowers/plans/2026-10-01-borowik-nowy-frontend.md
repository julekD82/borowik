# Borowik — nowy frontend: plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować od nowa czytelny interfejs (układ mapa + panel boczny, pogoda jako fakty z normą, klasy procentowe na mapie, karty rejonu i wydzielenia) oraz dopisać do eksportu pola, których ten interfejs potrzebuje — bez zmiany modelu.

**Architecture:** Backend (Python) dostaje tylko dopisane pola eksportu: `daily`/`rain26`/`warnings`/`lookback_days` w `conditions`, `site_type`/`age_years` w `details`, `mask_reason` w `scores`. Frontend: Preact + `@preact/signals`; czysta logika w `src/data/` i `src/domain/` (przeniesiona z `model.ts` i rozszerzona), jeden stan w `src/state/`, nakładka na MapLibre w `src/map/`, komponenty w `src/components/`. Stary interfejs działa do ostatniego zadania (model.ts staje się nakładką re-eksportującą), potem jest usuwany.

**Tech Stack:** Python 3 (pandas, numpy, pytest), E-OBS lokalnie (`pipeline/eobs.py`); Vite 7, TypeScript 5, Preact 10, @preact/signals, MapLibre GL 5, Vitest 3, @testing-library/preact, jsdom.

**Spec:** `docs/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md` (czytaj razem z tym planem).

## Global Constraints

- Model i ranking bez zmian: H, F, F_loc, P, R, `R_bez_presji`, maska, rejony, progi i profil — tylko dopisane pola eksportu.
- Teksty interfejsu po polsku, z polskimi znakami. Nagłówek pogody bez słów oceniających (same fakty).
- Klasy mapy: 1 = najlepsze 5%, 2 = 5–20%, 3 = 20–50%, 4 = reszta — definicja identyczna z `pipeline/phone_kmz.py::classify_by_percentile` (`CLASS_THRESHOLDS = {1: 0.05, 2: 0.20, 3: 0.50}`, remisy w tej samej klasie).
- Frontend: jedyne nowe zależności runtime to `preact` i `@preact/signals`; deweloperskie: `@preact/preset-vite`, `@testing-library/preact`, `jsdom`. MapLibre bez zmiany wersji.
- Kliknięcie na mapie (wydzielenie, znacznik rejonu), zmiana zakładki i trybu mapy nie zmieniają przybliżenia; wybór z listy przybliża.
- Układ komputerowy od 800 px szerokości; poniżej zakładki „Lista | Mapa”.
- Klucze `localStorage` bez zmian: `borowik.pressure.v1` („on”/„off”), `borowik.map-color.v1` („moisture” = Wilgotność, inne = Wynik), `borowik.access-layers.v1` (JSON), `borowik.view-mode.v1` („regions”/„stands”). Każdy odczyt i zapis w `try/catch`.
- Nie ruszać i nie commitować niezacommitowanych plików właściciela: `launcher/launcher.pyw`, `frontend/package.json` (linia `dev:lan` — patrz Task 0), `frontend/README.md`, `docs/Borowik_opis_techniczny_i_walidacja.md`, `docs/analiza-aplikacji/`, `output/`, `frontend/public/`.
- Polecenia: Python z katalogu repo: `.venv/Scripts/python.exe -m pytest …`; frontend z `frontend/`: `npx vitest run …`, `npx tsc --noEmit`, `npm run build`.
- Gałąź `nowy-frontend`; commit po każdym zadaniu, tylko pliki tego zadania (`git add <ścieżki>`, nigdy `git add -A`); wiadomość kończy się linią `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Kolizja identyfikatorów rejonów:** `regions.json` i `regions_bez_presji.json` oba mają `region_1…region_5`, ale to inne rejony. Po przełączeniu presji otwarta karta rejonu musi zniknąć ze stosu (nie może pokazać innego rejonu pod tym samym id) — test w Task 9.
2. **Stare migawki** (`data/trips/…`) bez `daily`/`rain26`/`mask_reason`/`site_type`/`M`/`R_bez_presji`/`confidence` muszą się otwierać bez błędu: panel w trybie zgodności, presja i Wilgotność nieaktywne — testy w Task 6, 8, 12, 14.
3. **Serwer Vite zwraca `index.html` (200, text/html) dla brakującego pliku** — plik opcjonalny ma być traktowany jak brak, wymagany ma dać czytelny błąd — test w Task 6.
4. **Wyścig przy zmianie analizy:** szczegóły (`details.json`, ok. 43 MB) wczytywane w tle dla poprzedniej analizy nie mogą nadpisać nowej — test w Task 9.
5. **Wydzielenie w masce bez wyniku** (R albo `R_bez_presji` = null) i wydzielenie poza maską: karta nie może się wysypać ani pokazać „powód nieznany” dla wydzielenia w masce — testy w Task 14.

## Struktura plików

Backend (modyfikacje): `pipeline/habitat.py` (`mask_reasons`), `pipeline/orchestrate.py` (kolumny `mask_reasons`, `age_years`), `pipeline/bdl_dictionaries.py` (opcjonalny słownik `site_type`), `pipeline/export.py` (`mask_reason`, `site_type`, `age_years`), `pipeline/conditions_timeline.py` (`daily`, `warnings`, `lookback_days`, `rain26`), nowy `pipeline/rain_normal.py` (norma E-OBS), `pipeline/prepare_trip.py` (podpięcie normy), `frontend/scripts/sync-data.mjs` (walidacja `daily`), `tests/fixtures/klasy_procentowe.json` (wspólny przykład klas).

Frontend (nowe):

| Plik | Odpowiedzialność |
|---|---|
| `vite.config.ts`, `src/test-setup.ts`, `nowy.html` | narzędzia (Preact, jsdom), tymczasowe wejście deweloperskie |
| `src/data/types.ts` | typy danych eksportu i `Analysis` |
| `src/data/parse.ts` | walidacja i normalizacja plików JSON |
| `src/data/load.ts` | pobieranie (`fetchJson`), `buildAnalysis`, `loadCore`, `loadBackground`, `loadTrips` |
| `src/domain/format.ts` | liczby, odległości, daty, `joinMeta` |
| `src/domain/geometry.ts` | `vertices`, `standCentroid` |
| `src/domain/ranking.ts` | ranking, rejony, klasy procentowe |
| `src/domain/labels.ts` | nazwy, etykiety, powody spoza maski, lata |
| `src/domain/access.ts` | warstwy dostępu, dojazd, presja |
| `src/domain/bars.ts` | paski wyniku, mediana rejonu, opisy pod paskami |
| `src/domain/moisture.ts` | skala wilgotności |
| `src/domain/weather.ts` | model panelu pogody |
| `src/state/prefs.ts`, `src/state/store.ts`, `src/state/loader.ts` | ustawienia, stan i akcje, wczytywanie analiz |
| `src/map/layers.ts`, `src/map/forestMap.ts` | wyrażenia MapLibre (czyste) i nakładka na mapę |
| `src/components/*.tsx` | komponenty interfejsu |
| `src/styles/tokens.css`, `layout.css`, `components.css` | wygląd |
| `src/test-fixtures.ts` | budowanie danych testowych |
| `src/index.tsx` | punkt wejścia |

Stare pliki (`src/main.ts`, `src/map.ts`, `src/model.ts`, `src/storage.ts`, `src/style.css`, `src/model.test.ts`, `src/ui.test.ts`) działają do Task 17.

---

### Task 0: Przygotowanie gałęzi

**Files:** brak zmian w kodzie.

- [ ] **Step 1: Sprawdź gałąź i stan katalogu**

Run: `git branch --show-current` i `git status --short`
Expected: `nowy-frontend`; zmodyfikowane pliki właściciela: `docs/Borowik_opis_techniczny_i_walidacja.md`, `frontend/README.md`, `frontend/package.json`, `launcher/launcher.pyw`; nieśledzone `docs/analiza-aplikacji/`, `frontend/public/`, `output/`.

- [ ] **Step 2: Zapytaj właściciela o `frontend/package.json` i `launcher/launcher.pyw`**

Task 4 dopisuje zależności do `frontend/package.json`, w którym jest niezacommitowana linia `"dev:lan": "vite --host 0.0.0.0",` (tryb LAN, razem ze zmianami w `launcher/launcher.pyw`). Zapytaj: „Czy zacommitujesz sam zmiany trybu LAN (`frontend/package.json` + `launcher/launcher.pyw`) przed Task 4? Mogę też zrobić to za Ciebie osobnym commitem na tej gałęzi.” Nie przechodź do Task 4, dopóki `git diff frontend/package.json` nie jest pusty albo właściciel nie wyrazi zgody na wspólny commit.

---

### Task 1: Eksport — powody spoza maski, typ siedliska, wiek

**Files:**
- Modify: `pipeline/habitat.py:128-136` (`passes_mask`)
- Modify: `pipeline/orchestrate.py` (pętla od `for _, row in stands.iterrows():` ok. linia 224; przypisania kolumn ok. linia 410)
- Modify: `pipeline/bdl_dictionaries.py` (`_DICTIONARY_SPECS`, `_load_dictionaries_from`)
- Modify: `pipeline/export.py` (`build_score_record`, `build_details_record`, `write_details_json`)
- Test: `tests/test_habitat.py`, `tests/test_bdl_dictionaries.py`, `tests/test_export.py`

**Interfaces:**
- Produces: `pipeline.habitat.mask_reasons(row, profile) -> list[str]` (kody `not_dstan`, `no_age`, `too_young`, `excluded_species`); kolumny ramki `mask_reasons` (lista) i `age_years` (wiek użyty w modelu); `pipeline.export.mask_reason_list(row) -> list[str]` (dodaje `gdos`, `zakaz`); `site_type_entry(code, dictionaries) -> dict | None`; `age_years_int(value) -> int | None`; w `scores`: `mask_reason: string[]`; w `details`: `site_type: {code, label} | null`, `age_years: int | null`.

- [ ] **Step 1: Napisz testy `mask_reasons`**

Dopisz na końcu `tests/test_habitat.py`:

```python
import pytest

from pipeline.habitat import load_profile as _load_profile_mask, mask_reasons, passes_mask

_PROFILE_MASK = _load_profile_mask("profiles/boletus_edulis.yaml")


def _mask_row(**over):
    base = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "SO", "part_cd": 10, "site_type": "BMSW"}
    return {**base, **over}


@pytest.mark.parametrize("over, expected", [
    ({}, []),
    ({"area_type": "ZRAB"}, ["not_dstan"]),
    ({"spec_age": None}, ["no_age"]),
    ({"spec_age": 5}, ["too_young"]),
    ({"species_cd": "OL", "part_cd": 8}, ["excluded_species"]),
    ({"species_cd": "OL", "part_cd": 7}, []),
    ({"area_type": "ZRAB", "spec_age": 5}, ["not_dstan", "too_young"]),
])
def test_mask_reasons_lists_every_failed_condition(over, expected):
    row = _mask_row(**over)
    assert mask_reasons(row, _PROFILE_MASK) == expected
    assert passes_mask(row, _PROFILE_MASK) is (expected == [])
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `.venv/Scripts/python.exe -m pytest tests/test_habitat.py -q -k mask_reasons`
Expected: FAIL (`ImportError: cannot import name 'mask_reasons'`).

- [ ] **Step 3: Zaimplementuj `mask_reasons` i wyprowadź z niej `passes_mask`**

W `pipeline/habitat.py` zastąp całą funkcję `passes_mask` tym kodem:

```python
def mask_reasons(row: dict, profile: dict) -> list[str]:
    """Powody odrzucenia przez maske strukturalna (pusta lista = maska spelniona).
    Te same warunki co dawne passes_mask; passes_mask jest z nich wyprowadzone, wiec
    obie nie moga sie rozjechac. Tylko prezentacja (karta wydzielenia poza filtrami)."""
    reasons = []
    if row.get("area_type") != "D-STAN":
        reasons.append("not_dstan")
    age = row.get("spec_age")
    if age is None:
        reasons.append("no_age")
    elif age < profile["age_breakpoints"]["mask_below"]:
        reasons.append("too_young")
    species = row.get("species_cd")
    if species in profile["zero_affinity_mask_species"] and (row.get("part_cd") or 0) >= 8:
        reasons.append("excluded_species")
    return reasons


def passes_mask(row: dict, profile: dict) -> bool:
    return not mask_reasons(row, profile)
```

- [ ] **Step 4: Uruchom testy habitat**

Run: `.venv/Scripts/python.exe -m pytest tests/test_habitat.py -q`
Expected: PASS (wszystkie, łącznie z dotychczasowymi testami `passes_mask`).

- [ ] **Step 5: Zapisz kolumny `mask_reasons` i `age_years` w `run_poc`**

W `pipeline/orchestrate.py`:
1. Import: dopisz `mask_reasons` do istniejącego importu z `pipeline.habitat` (obok `passes_mask`).
2. Obok `age_update_status_values = []` dopisz:

```python
    mask_reason_values = []
    age_used_values = []
```

3. Bezpośrednio po linii `mask = passes_mask(row, profile)` dopisz:

```python
        mask_reason_values.append(mask_reasons(row, profile))
        age_used_values.append(corrected_age)
```

4. Bezpośrednio po `stands["age_update_status"] = age_update_status_values` dopisz:

```python
    # Nowy frontend: powody odrzucenia przez maske strukturalna (karta wydzielenia poza
    # filtrami) i wiek uzyty w modelu (po korekcie do roku analizy) -- tylko prezentacja.
    stands["mask_reasons"] = pd.Series(mask_reason_values, index=stands.index, dtype=object)
    stands["age_years"] = age_used_values
```

(`pd.Series(..., dtype=object)` jest konieczne: lista samych pustych list przypisana wprost zostałaby odczytana jako tablica 2D.)

- [ ] **Step 6: Test słownika typów siedliskowych**

Dopisz na końcu `tests/test_bdl_dictionaries.py`:

```python
def test_load_dictionaries_adds_site_types_when_the_package_has_them(tmp_path):
    files = {**_FILES, "f_site_type_dic.txt":
             "date_from\tdate_to\tsite_type_cd\tsite_type_name\tsite_type_nr\n"
             "01-01-1970\t\tBMŚW   \tBór mieszany świeży           \t22\n"}
    _write_dictionary_package(tmp_path / "PKG_ONE", files)
    dictionaries = load_dictionaries(tmp_path)
    assert dictionaries["site_type"]["BMSW"] == "Bór mieszany świeży"


def test_load_dictionaries_without_site_type_file_still_loads_the_rest(tmp_path):
    _write_dictionary_package(tmp_path / "PKG_ONE")
    dictionaries = load_dictionaries(tmp_path)
    assert "site_type" not in dictionaries
    assert dictionaries["storey"]["PODSZ"] == "podszyt"
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_bdl_dictionaries.py -q`
Expected: FAIL w pierwszym nowym teście (`KeyError: 'site_type'`).

- [ ] **Step 7: Opcjonalny słownik `site_type`**

W `pipeline/bdl_dictionaries.py` pod `_DICTIONARY_SPECS` dopisz:

```python
# Nowy frontend: nazwa typu siedliskowego na karcie wydzielenia. Opcjonalny -- paczka bez
# tego pliku (albo testowa) dalej laduje pozostale slowniki.
_OPTIONAL_DICTIONARY_SPECS = {
    "site_type": ("f_site_type_dic.txt", "site_type_cd", "site_type_name"),
}
```

i zastąp `_load_dictionaries_from`:

```python
def _read_dictionary(path: Path, code_col: str, name_col: str) -> dict[str, str]:
    df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8")
    # Dictionary codes carry the same raw Polish diacritics as
    # f_storey_species's species_cd (e.g. "ŚW") -- normalize so lookups
    # against already-normalized codes (pipeline.bdl_packages,
    # pipeline.bdl.normalize_code) work without a second code form.
    codes = df[code_col].str.strip().map(normalize_code)
    names = df[name_col].str.strip()
    return dict(zip(codes, names))


def _load_dictionaries_from(package_dir: Path) -> dict[str, dict[str, str]]:
    dictionaries = {}
    for table_name, (filename, code_col, name_col) in _DICTIONARY_SPECS.items():
        dictionaries[table_name] = _read_dictionary(package_dir / filename, code_col, name_col)
    for table_name, (filename, code_col, name_col) in _OPTIONAL_DICTIONARY_SPECS.items():
        if (package_dir / filename).exists():
            dictionaries[table_name] = _read_dictionary(package_dir / filename, code_col, name_col)
    return dictionaries
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_bdl_dictionaries.py -q`
Expected: PASS.

- [ ] **Step 8: Testy eksportu**

Dopisz na końcu `tests/test_export.py`:

```python
from pipeline.export import age_years_int, mask_reason_list, site_type_entry


def test_score_record_mask_reason_is_empty_for_a_masked_stand():
    stands = _enriched_stands()
    stands["mask_reasons"] = pd.Series([[], ["too_young"]], index=stands.index, dtype=object)
    assert build_score_record(stands.iloc[0], day="2026-09-23")["mask_reason"] == []


def test_score_record_mask_reason_combines_structural_gdos_and_zakaz():
    stands = _enriched_stands()
    stands["mask_reasons"] = pd.Series([[], ["too_young"]], index=stands.index, dtype=object)
    stands.loc[1, "gdos_status"] = "blokada"
    stands.loc[1, "zakaz_status"] = "zakaz"
    assert build_score_record(stands.iloc[1], day="2026-09-23")["mask_reason"] == ["too_young", "gdos", "zakaz"]


def test_mask_reason_list_without_the_column_uses_only_gdos_and_zakaz():
    row = _enriched_stands().iloc[1]
    assert mask_reason_list(row) == []


def test_site_type_entry_and_age_years_int():
    assert site_type_entry("BMSW", {"site_type": {"BMSW": "Bór mieszany świeży"}}) == {
        "code": "BMSW", "label": "Bór mieszany świeży"}
    assert site_type_entry("XYZ", {}) == {"code": "XYZ", "label": "XYZ"}
    assert site_type_entry(float("nan"), {}) is None
    assert site_type_entry(None, {}) is None
    assert age_years_int(64.0) == 64
    assert age_years_int(float("nan")) is None
    assert age_years_int(None) is None


def test_details_record_carries_site_type_and_age():
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", None, "2026-09-25", {}, {}, _DICTIONARIES, {},
        site_type="BMSW", age_years=64.4,
    )
    assert record["site_type"] == {"code": "BMSW", "label": "BMSW"}
    assert record["age_years"] == 64
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -q`
Expected: FAIL (`ImportError: cannot import name 'age_years_int'`).

- [ ] **Step 9: Implementacja w `pipeline/export.py`**

1. W `build_score_record` przed `return record` dopisz:

```python
    # Nowy frontend: dlaczego wydzielenie jest poza filtrami modelu (pusta lista w masce).
    record["mask_reason"] = mask_reason_list(row)
```

2. Dopisz funkcje (pod `build_score_record`):

```python
def mask_reason_list(row) -> list[str]:
    """Powody odrzucenia: maska strukturalna (kolumna mask_reasons z run_poc, kody z
    pipeline.habitat.mask_reasons) plus GDOS i zakaz okresowy z pelnej maski. Pusta lista
    dla wydzielenia w masce albo gdy ramka nie ma tych kolumn. Tylko prezentacja."""
    if bool(row["mask_full"]):
        return []
    structural = row["mask_reasons"] if "mask_reasons" in row.index else None
    reasons = list(structural) if isinstance(structural, (list, tuple)) else []
    if row.get("gdos_status") == "blokada":
        reasons.append("gdos")
    if row.get("zakaz_status") == "zakaz":
        reasons.append("zakaz")
    return reasons


def site_type_entry(code, dictionaries: dict) -> dict | None:
    """Typ siedliskowy do karty: kod i nazwa ze slownika BDL (sam kod, gdy brak nazwy)."""
    if not isinstance(code, str) or not code.strip():
        return None
    code = code.strip()
    return {"code": code, "label": dictionaries.get("site_type", {}).get(code, code)}


def age_years_int(value) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(round(float(value)))
```

3. W sygnaturze `build_details_record` po `forest_district: str | None = None` dopisz `site_type=None, age_years=None`, a w zwracanym słowniku po `"forest_district": forest_district,` dopisz:

```python
        # Nowy frontend: typ siedliskowy (kod + nazwa) i wiek uzyty w modelu -- prezentacja.
        "site_type": site_type_entry(site_type, dictionaries),
        "age_years": age_years_int(age_years),
```

4. W `write_details_json`, w wywołaniu `build_details_record(...)` po `forest_district=forest_district_name(row.get("nazwa")),` dopisz:

```python
            site_type=row.get("site_type"),
            age_years=row.get("age_years"),
```

- [ ] **Step 10: Uruchom testy**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py tests/test_habitat.py tests/test_bdl_dictionaries.py tests/test_orchestrate.py tests/test_prepare_trip.py -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add pipeline/habitat.py pipeline/orchestrate.py pipeline/bdl_dictionaries.py pipeline/export.py tests/test_habitat.py tests/test_bdl_dictionaries.py tests/test_export.py
git commit -m "Eksport: powody spoza maski, typ siedliska i wiek na karte (model bez zmian)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Eksport warunków — dzienny opad, ostrzeżenia, okno wstecz

**Files:**
- Modify: `pipeline/conditions_timeline.py` (nowe funkcje + `build_conditions_timeline`)
- Modify: `frontend/scripts/sync-data.mjs` (walidacja `daily`)
- Test: `tests/test_conditions_timeline.py`, `frontend/scripts/sync-data.test.mjs`

**Interfaces:**
- Produces: `area_daily_table(daily, points) -> DataFrame` (index = lokalna data, kolumny `precipitation_mm`, `tmean_c`, `tmin_c`, `tmax_c` jeśli są, `radar_share`); `daily_series(area, today, back_days=35) -> list[dict]`; `weather_warnings(area, today, horizon_days, profile) -> list[dict]`; w JSON: `lookback_days: int`, `daily: [{date, precip_mm, radar_share, tmin_c, tmax_c, forecast}]`, `warnings: [{type: "frost"|"heat_drought", dates: [...]}]`.

- [ ] **Step 1: Testy**

Dopisz na końcu `tests/test_conditions_timeline.py`:

```python
from pipeline.conditions_timeline import area_daily_table, daily_series, weather_warnings


def test_area_daily_table_takes_medians_and_mean_radar_share():
    points = [(50.0, 21.0), (50.1, 21.1), (50.2, 21.2)]
    daily = _daily_multi_point(points, "2026-09-20", 2, precip=1.0, tmin=5.0)
    daily["tmax_c"] = [20.0, 20.0, 22.0, 22.0, 24.0, 24.0]
    daily["precipitation_mm"] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    daily["radar_frac"] = [1.0, 1.0, 0.5, 0.0, 0.0, 1.0]
    table = area_daily_table(daily, points)
    first = table.loc[date(2026, 9, 20)]
    assert first["precipitation_mm"] == 3.0          # mediana 1, 3, 5
    assert first["tmax_c"] == 22.0
    assert first["radar_share"] == pytest.approx(0.5)  # srednia 1, 0.5, 0


def test_daily_series_starts_35_days_back_and_marks_forecast():
    points = [(50.0, 21.0)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    table = area_daily_table(_daily_multi_point(points, start, 47), points)
    rows = daily_series(table, today)
    assert rows[0]["date"] == (today - timedelta(days=35)).isoformat()
    assert len(rows) == 35 + 1 + 6
    assert [r["forecast"] for r in rows[-7:]] == [False] + [True] * 6
    assert rows[0]["radar_share"] == 0.0 and rows[0]["tmax_c"] is None  # brak kolumn w fixture


def test_weather_warnings_frost_window_and_heat_with_drought():
    today = date(2026, 9, 27)
    idx = [today + timedelta(days=k) for k in range(-4, 6)]
    area = pd.DataFrame({"tmean_c": [20.0] * 10, "tmin_c": [5.0] * 10,
                         "precipitation_mm": [0.0] * 10}, index=idx)
    area.loc[today - timedelta(days=4), "tmin_c"] = -3.0   # przed oknem przymrozku (dzis-2)
    area.loc[today + timedelta(days=2), "tmin_c"] = -1.0
    out = {w["type"]: w["dates"] for w in weather_warnings(area, today, 7, PROFILE)}
    assert out["frost"] == [(today + timedelta(days=2)).isoformat()]
    assert out["heat_drought"] == [(today + timedelta(days=k)).isoformat() for k in range(0, 6)]


def test_build_conditions_timeline_exports_daily_warnings_and_lookback():
    points = [(50.0, 21.0)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    out = build_conditions_timeline(_daily_multi_point(points, start, 47), points, _clim(points),
                                    points, today, PROFILE)
    assert out["lookback_days"] == PROFILE["conditions"]["lookback_days"]
    assert len(out["daily"]) == 42
    assert {w["type"] for w in out["warnings"]} == {"frost", "heat_drought"}
    json.dumps(out, allow_nan=False)
```

Na górze pliku dopisz `import json`, jeśli go nie ma.

Run: `.venv/Scripts/python.exe -m pytest tests/test_conditions_timeline.py -q`
Expected: FAIL (`ImportError: cannot import name 'area_daily_table'`).

- [ ] **Step 2: Implementacja**

W `pipeline/conditions_timeline.py` upewnij się, że `to_local_date` jest importowane z `pipeline.weather` (dopisz do istniejącego importu, jeśli go brak), i dopisz nad `build_conditions_timeline`:

```python
DAILY_BACK_DAYS = 35


def area_daily_table(daily: pd.DataFrame, points) -> pd.DataFrame:
    """Nowy frontend (panel pogody): mediana obszaru na lokalna dobe -- opad i temperatury
    (srednia, min., maks.) -- oraz sredni udzial godzin z radaru (0 bez radaru). W odroznieniu
    od pipeline.flush.area_daily_weather (zamrozony eksperyment) ma tmax_c i radar_share.
    Kolumn nieobecnych w `daily` (np. tmax_c w starszych testach) po prostu nie ma."""
    wanted = set(points)
    sel = daily[[(la, lo) in wanted for la, lo in zip(daily["lat"], daily["lon"])]]
    sel = sel.assign(local_date=to_local_date(sel["date"]))
    cols = [c for c in ("precipitation_mm", "tmean_c", "tmin_c", "tmax_c") if c in sel.columns]
    out = sel.groupby("local_date")[cols].median()
    if "radar_frac" in sel.columns:
        out["radar_share"] = sel.groupby("local_date")["radar_frac"].mean().fillna(0.0)
    else:
        out["radar_share"] = 0.0
    return out.sort_index().rename_axis("date")


def _round_or_none(value, digits: int):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def daily_series(area: pd.DataFrame, today: date, back_days: int = DAILY_BACK_DAYS) -> list[dict]:
    """Wiersze do wykresu opadu w panelu: od dzis - back_days do konca danych (prognoza)."""
    start = today - timedelta(days=back_days)
    rows = []
    for day, r in area[area.index >= start].iterrows():
        rows.append({
            "date": day.isoformat(),
            "precip_mm": _round_or_none(r.get("precipitation_mm"), 1),
            "radar_share": round(float(r.get("radar_share", 0.0)), 2),
            "tmin_c": _round_or_none(r.get("tmin_c"), 1),
            "tmax_c": _round_or_none(r.get("tmax_c"), 1),
            "forecast": day > today,
        })
    return rows


def weather_warnings(area: pd.DataFrame, today: date, horizon_days: int, profile: dict) -> list[dict]:
    """Ostrzezenia panelu z progow profilu (bez nowych parametrow): przymrozek -- dni od
    dzis-2 do konca horyzontu z mediana tmin < frost_tmin3_soft_c; upal z susza -- dni od
    dzis do konca horyzontu ze srednia temperatura 5 dni > heat_penalty_tmean5_c i opadem
    5 dni < heat_penalty_p5_mm (ta sama regula co kara za upal w F)."""
    cfg = profile["fruiting"]
    end = today + timedelta(days=horizon_days - 1)
    frost = []
    if "tmin_c" in area.columns:
        for day, t in area["tmin_c"].items():
            if today - timedelta(days=2) <= day <= end and pd.notna(t) and t < cfg["frost_tmin3_soft_c"]:
                frost.append(day.isoformat())
    heat = []
    if {"tmean_c", "precipitation_mm"} <= set(area.columns):
        tmean5 = area["tmean_c"].rolling(5, min_periods=5).mean()
        p5 = area["precipitation_mm"].rolling(5, min_periods=5).sum()
        for day in area.index:
            if (today <= day <= end and pd.notna(tmean5[day])
                    and tmean5[day] > cfg["heat_penalty_tmean5_c"] and p5[day] < cfg["heat_penalty_p5_mm"]):
                heat.append(day.isoformat())
    return [{"type": "frost", "dates": frost}, {"type": "heat_drought", "dates": heat}]
```

W `build_conditions_timeline` zaraz po `area = area_daily_weather(daily, points)` dopisz `table = area_daily_table(daily, points)`, a w słowniku przekazywanym do `_nan_to_none({...})` po `"aggregation": aggregation,` dopisz:

```python
        "lookback_days": cfg["lookback_days"],
        "daily": daily_series(table, today),
        "warnings": weather_warnings(table, today, cfg["horizon_days"], profile),
```

- [ ] **Step 3: Uruchom testy**

Run: `.venv/Scripts/python.exe -m pytest tests/test_conditions_timeline.py tests/test_prepare_trip.py tests/test_panel_spojnosc_z_mapa.py -q`
Expected: PASS.

- [ ] **Step 4: Test synchronizacji**

Dopisz w `frontend/scripts/sync-data.test.mjs` po teście „rejects a same-day conditions file from another day or malformed”:

```js
it("accepts conditions with a daily array and rejects a malformed daily field", async () => {
  const { source, target } = await fixture();
  const withDaily = (daily) =>
    JSON.stringify({ day: "2026-09-24", summary: "x", days: [], daily });
  await writeFile(path.join(source, "conditions_2026-09-24.json"), withDaily([{ date: "2026-09-24" }]));
  expect((await syncData(source, target)).conditions).toBe(1);
  await writeFile(path.join(source, "conditions_2026-09-24.json"), withDaily("zle"));
  await expect(syncData(source, target)).rejects.toThrow("conditions");
});
```

Run (w `frontend/`): `npx vitest run scripts/sync-data.test.mjs`
Expected: FAIL (drugi `syncData` nie rzuca).

- [ ] **Step 5: Walidacja w `sync-data.mjs`**

W `frontend/scripts/sync-data.mjs` zaraz po warunku `if (!conditions || typeof conditions !== "object" || conditions.day !== day || !Array.isArray(conditions.days)) throw …` dopisz:

```js
    // Nowy frontend: dzienny opad do panelu pogody (opcjonalny; stare eksporty go nie maja).
    if (conditions.daily !== undefined && !Array.isArray(conditions.daily))
      throw new Error(`Niepoprawny format conditions_${day}.json (pole daily).`);
```

Run: `npx vitest run scripts/sync-data.test.mjs`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/conditions_timeline.py tests/test_conditions_timeline.py frontend/scripts/sync-data.mjs frontend/scripts/sync-data.test.mjs
git commit -m "Eksport warunkow: dzienny opad i temperatury, ostrzezenia, okno wstecz (panel pogody)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Suma opadu z 26 dni i norma z E-OBS

**Files:**
- Create: `pipeline/rain_normal.py`
- Modify: `pipeline/conditions_timeline.py` (`rain26_current`, `rain26_block`, parametry `build_conditions_timeline`)
- Modify: `pipeline/prepare_trip.py` (blok warunków, ok. linie 715–754)
- Test: `tests/test_rain_normal.py`, `tests/test_conditions_timeline.py`

**Interfaces:**
- Consumes: `pipeline.eobs.EobsStore.daily(lat, lon, start, end, variables)`; `pipeline.weather.percentile_rank`.
- Produces: `eobs_cells_in_radius(lat, lon, radius_km) -> list[tuple[float, float]]`; `rain26_pool(store, cells, doy, years=(1991, 2020), half_width=15) -> np.ndarray`; `EOBS_NORMAL_LABEL = "E-OBS v33.0e, 1991–2020"`; `build_conditions_timeline(..., rain_normal_pool=None, rain_normal_cells=0)`; w JSON `rain26: {sum_mm, window_start, window_end, normal_mm, pct, normal_source, normal_cells} | null`.

- [ ] **Step 1: Testy normy**

Utwórz `tests/test_rain_normal.py`:

```python
import math
from datetime import date

import numpy as np
import pandas as pd

from pipeline.rain_normal import eobs_cells_in_radius, rain26_pool


class _FakeStore:
    """Staly opad 1 mm/dobe albo brak danych (NaN) -- bez plikow E-OBS."""

    def __init__(self, rr: float):
        self.rr = rr

    def daily(self, lat, lon, start, end, variables=("rr",)):
        index = pd.date_range(start, end, freq="D")
        return pd.DataFrame({"rr": self.rr}, index=index)


def _km(lat1, lon1, lat2, lon2):
    rad = math.radians
    h = (math.sin(rad(lat2 - lat1) / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def test_cells_in_radius_include_the_centre_cell_and_stay_inside():
    cells = eobs_cells_in_radius(50.6191, 18.4611, 20)
    assert (50.65, 18.45) in cells
    assert len(cells) > 10
    assert all(_km(50.6191, 18.4611, la, lo) <= 20 for la, lo in cells)


def test_small_radius_still_returns_one_cell():
    assert len(eobs_cells_in_radius(50.6191, 18.4611, 1)) >= 1


def test_pool_holds_26_day_sums_from_1991_2020_near_the_day_of_year():
    pool = rain26_pool(_FakeStore(1.0), [(50.65, 18.45)], date(2026, 9, 30).timetuple().tm_yday)
    assert len(pool) == 30 * 31           # 30 lat x (dzien +-15)
    assert np.all(pool == 26.0)


def test_pool_is_empty_without_eobs_data():
    assert len(rain26_pool(_FakeStore(float("nan")), [(50.65, 18.45)], 273)) == 0
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_rain_normal.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'pipeline.rain_normal'`).

Uwaga do liczby 30 × 31: dni roku w odległości ≤ 15 (z zawinięciem, rok 365 dni) to 31 dni; w latach przestępnych `dayofyear` przesuwa się o 1 po lutym, więc liczba może różnić się o kilka. Jeśli asercja `== 30 * 31` nie przejdzie wyłącznie z tego powodu, zamień ją na `assert 30 * 30 <= len(pool) <= 30 * 32` i opisz to w commicie.

- [ ] **Step 2: Implementacja `pipeline/rain_normal.py`**

```python
"""Nowy frontend (panel pogody): norma sumy opadu z 26 dni dla tej pory roku z lokalnego E-OBS.

Pula = wszystkie 26-dniowe sumy opadu (rr) z lat 1991-2020 konczace sie w dniach roku
odleglych o <= 15 dni od biezacego (z zawinieciem roku), dla komorek E-OBS 0,1 st. w kole
analizy. Tylko prezentacja -- nic stad nie wraca do modelu. Brak plikow E-OBS = pusta pula
(panel bez normy). Zastrzezenie: biezaca suma pochodzi z radaru IMGW scalonego z modelem,
norma z E-OBS (siec stacji) -- dwa rozne produkty, porownanie przyblizone."""
import math
from datetime import date

import numpy as np

CLIM_YEARS = (1991, 2020)
WINDOW_DAYS = 26
DOY_HALF_WIDTH = 15
EOBS_NORMAL_LABEL = "E-OBS v33.0e, 1991–2020"


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rad = math.radians
    h = (math.sin(rad(lat2 - lat1) / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def eobs_cells_in_radius(lat: float, lon: float, radius_km: float) -> list[tuple[float, float]]:
    """Srodki komorek siatki 0,1 st. (x.x5) w kole; zawsze co najmniej komorka srodka."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    cells = []
    for i in range(math.floor((lat - dlat) * 10), math.floor((lat + dlat) * 10) + 1):
        for j in range(math.floor((lon - dlon) * 10), math.floor((lon + dlon) * 10) + 1):
            la, lo = round(i / 10 + 0.05, 2), round(j / 10 + 0.05, 2)
            if _km(lat, lon, la, lo) <= radius_km:
                cells.append((la, lo))
    if not cells:
        cells.append((round(round(lat * 10 - 0.5) / 10 + 0.05, 2), round(round(lon * 10 - 0.5) / 10 + 0.05, 2)))
    return cells


def rain26_pool(store, cells, doy: int, years=CLIM_YEARS, half_width: int = DOY_HALF_WIDTH) -> np.ndarray:
    """26-dniowe sumy opadu z lat `years` konczace sie w dniu roku odleglym o <= half_width
    od `doy`, z wszystkich `cells`. `store` jak pipeline.eobs.EobsStore (metoda daily)."""
    values = []
    for clat, clon in cells:
        rr = store.daily(clat, clon, date(years[0] - 1, 12, 1), date(years[1], 12, 31), variables=["rr"])["rr"]
        sums = rr.rolling(WINDOW_DAYS, min_periods=WINDOW_DAYS).sum()
        idx = sums.index
        in_years = (idx.year >= years[0]) & (idx.year <= years[1])
        diff = np.abs(idx.dayofyear.to_numpy() - doy)
        near = np.minimum(diff, 365 - diff) <= half_width
        values.append(sums[in_years & near].dropna().to_numpy())
    return np.concatenate(values) if values else np.array([])
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_rain_normal.py -q`
Expected: PASS.

- [ ] **Step 3: Testy `rain26` w warunkach**

Dopisz na końcu `tests/test_conditions_timeline.py`:

```python
def test_rain26_with_a_normal_pool():
    points = [(50.0, 21.0), (50.1, 21.1)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    out = build_conditions_timeline(_daily_multi_point(points, start, 47, precip=2.0), points, _clim(points),
                                    points, today, PROFILE,
                                    rain_normal_pool=np.array([40.0, 50.0, 60.0]), rain_normal_cells=4)
    r = out["rain26"]
    assert r["sum_mm"] == 52.0                                   # 26 dni x 2 mm
    assert r["window_start"] == (today - timedelta(days=25)).isoformat()
    assert r["window_end"] == today.isoformat()
    assert r["normal_mm"] == 50.0
    assert r["pct"] == pytest.approx(0.667, abs=0.001)
    assert r["normal_source"] == "E-OBS v33.0e, 1991–2020" and r["normal_cells"] == 4


def test_rain26_without_eobs_has_no_normal():
    points = [(50.0, 21.0)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    out = build_conditions_timeline(_daily_multi_point(points, start, 47), points, _clim(points),
                                    points, today, PROFILE)
    assert out["rain26"]["normal_mm"] is None and out["rain26"]["pct"] is None
    assert out["rain26"]["normal_cells"] == 0
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_conditions_timeline.py -q -k rain26`
Expected: FAIL (`TypeError: … unexpected keyword argument 'rain_normal_pool'`).

- [ ] **Step 4: Implementacja w `conditions_timeline.py`**

Dopisz import `from pipeline.rain_normal import EOBS_NORMAL_LABEL` i funkcje nad `build_conditions_timeline`:

```python
def rain26_current(daily: pd.DataFrame, points, today: date):
    """Mediana po punktach pogody zwyklej sumy opadu z 26 dni konczacych sie dzis
    (dzis-25 .. dzis). Zwraca (suma albo None, poczatek, koniec okna)."""
    start = today - timedelta(days=25)
    wanted = set(points)
    sel = with_local_date(daily[[(la, lo) in wanted for la, lo in zip(daily["lat"], daily["lon"])]])
    win = sel[(sel["local_date"] >= start) & (sel["local_date"] <= today)]
    if win.empty:
        return None, start, today
    sums = win.groupby(["lat", "lon"])["precipitation_mm"].sum()
    return float(sums.median()), start, today


def rain26_block(daily: pd.DataFrame, points, today: date, pool, cells: int) -> dict | None:
    current, start, end = rain26_current(daily, points, today)
    if current is None:
        return None
    has_normal = pool is not None and len(pool) > 0
    return {
        "sum_mm": round(current, 1),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "normal_mm": round(float(np.median(pool)), 1) if has_normal else None,
        "pct": round(percentile_rank(current, pool), 3) if has_normal else None,
        "normal_source": EOBS_NORMAL_LABEL if has_normal else None,
        "normal_cells": int(cells) if has_normal else 0,
    }
```

W sygnaturze `build_conditions_timeline` po `point_clim_cells: dict | None = None` dopisz `rain_normal_pool=None, rain_normal_cells: int = 0`, a w słowniku wyniku obok `"daily": …` dopisz:

```python
        "rain26": rain26_block(daily, points, today, rain_normal_pool, rain_normal_cells),
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_conditions_timeline.py -q`
Expected: PASS.

- [ ] **Step 5: Podpięcie w `prepare_trip.py`**

Dopisz importy:

```python
from pipeline.eobs import EobsStore
from pipeline.rain_normal import eobs_cells_in_radius, rain26_pool
```

W bloku `try:` warunków, bezpośrednio przed `timeline = build_conditions_timeline(`, dopisz:

```python
        # Nowy frontend: norma sumy opadu z 26 dni z lokalnego E-OBS (cache/eobs). Brak albo
        # uszkodzone pliki = panel bez normy, analiza idzie dalej.
        eobs_cells = eobs_cells_in_radius(lat, lon, radius_km)
        try:
            rain_pool = rain26_pool(EobsStore(cache_dir), eobs_cells, date.today().timetuple().tm_yday)
        except (OSError, ValueError, KeyError) as exc:
            print(f"UWAGA: norma opadu z E-OBS pominieta ({exc}).", flush=True)
            rain_pool = None
        if rain_pool is None or not len(rain_pool):
            print("UWAGA: brak lokalnych danych E-OBS -- panel pogody bez normy opadu.", flush=True)
```

i w samym wywołaniu `build_conditions_timeline(...)` dopisz argumenty `rain_normal_pool=rain_pool, rain_normal_cells=len(eobs_cells),`.

- [ ] **Step 6: Pełne testy backendu**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (wszystkie; liczba testów wyższa niż 877).

- [ ] **Step 7: Commit**

```bash
git add pipeline/rain_normal.py pipeline/conditions_timeline.py pipeline/prepare_trip.py tests/test_rain_normal.py tests/test_conditions_timeline.py
git commit -m "Eksport warunkow: suma opadu z 26 dni i norma z lokalnego E-OBS 1991-2020

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Narzędzia frontendu (Preact, jsdom) i ikony

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (przez `npm install`), `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`, `frontend/src/test-setup.ts`, `frontend/src/components/icons.tsx`
- Test: `frontend/src/components/icons.test.tsx`

**Interfaces:**
- Produces: `Icon({ name })` z `IconName = "mushroom" | "map" | "list" | "arrowLeft" | "info" | "target" | "layers" | "close" | "copy" | "navigate"`; testy komponentów zaczynają się komentarzem `// @vitest-environment jsdom`.

Wymaganie wstępne: Task 0, Step 2 zakończony (brak niezacommitowanych zmian właściciela w `frontend/package.json` albo jego zgoda).

- [ ] **Step 1: Zależności**

Run (w `frontend/`):
```bash
npm install preact @preact/signals
npm install -D @preact/preset-vite @testing-library/preact jsdom
```
Expected: bez błędów. Zanotuj zainstalowane wersje (`npm ls preact @preact/signals`). Plan zakłada Preact 10 i @preact/signals 2; jeśli npm zainstaluje nowsze główne wersje, sprawdź w ich dokumentacji, czy `signal`, `computed`, `effect`, `batch` i `render` działają tak samo.

- [ ] **Step 2: Konfiguracja**

Utwórz `frontend/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  test: {
    environment: "node",
    setupFiles: ["./src/test-setup.ts"],
  },
});
```

Utwórz `frontend/src/test-setup.ts`:

```ts
import { afterEach } from "vitest";

// Testy komponentow (// @vitest-environment jsdom) sprzataja DOM po kazdym tescie;
// testy w srodowisku node nie importuja biblioteki DOM.
afterEach(async () => {
  if (typeof document === "undefined") return;
  const { cleanup } = await import("@testing-library/preact");
  cleanup();
});
```

W `frontend/tsconfig.json` w `compilerOptions` dopisz:

```json
    "jsx": "react-jsx",
    "jsxImportSource": "preact",
    "resolveJsonModule": true,
```

- [ ] **Step 3: Test ikony**

Utwórz `frontend/src/components/icons.test.tsx`:

```tsx
// @vitest-environment jsdom
import { render } from "@testing-library/preact";
import { describe, expect, it } from "vitest";
import { Icon } from "./icons";

describe("Icon", () => {
  it("renders a decorative svg with the requested shape", () => {
    const { container } = render(<Icon name="map" />);
    const svg = container.querySelector("svg.icon");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.querySelector("path")).not.toBeNull();
  });
});
```

Run: `npx vitest run src/components/icons.test.tsx`
Expected: FAIL (brak modułu `./icons`).

- [ ] **Step 4: Ikony**

Utwórz `frontend/src/components/icons.tsx` (styl kreski w CSS klasy `.icon`, Task 11):

```tsx
import type { JSX } from "preact";

export type IconName =
  | "mushroom" | "map" | "list" | "arrowLeft" | "info" | "target" | "layers" | "close" | "copy" | "navigate";

const SHAPES: Record<IconName, () => JSX.Element> = {
  mushroom: () => (<><path d="M3 12a9 9 0 0 1 18 0Z" /><path d="M9 12v7a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-7" /></>),
  map: () => <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Zm6-3v15m6-12v15" />,
  list: () => <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  arrowLeft: () => <path d="M19 12H5m6-6-6 6 6 6" />,
  info: () => (<><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.01" /></>),
  target: () => (<><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3" /></>),
  layers: () => (<><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 13 9 5 9-5" /></>),
  close: () => <path d="m6 6 12 12M6 18 18 6" />,
  copy: () => (<><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M4 16V6a2 2 0 0 1 2-2h10" /></>),
  navigate: () => <path d="m21 3-7 18-3-8-8-3Z" />,
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      {SHAPES[name]()}
    </svg>
  );
}
```

- [ ] **Step 5: Weryfikacja**

Run: `npx vitest run` → PASS (stare testy + nowy); `npx tsc --noEmit` → bez błędów; `npm run build` → bez błędów (stary interfejs dalej się buduje).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/src/test-setup.ts frontend/src/components/icons.tsx frontend/src/components/icons.test.tsx
git commit -m "Nowy frontend: Preact, sygnaly, testy komponentow (jsdom), ikony

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Przeniesienie czystej logiki z `model.ts` do `src/data/` i `src/domain/`

Czyste przeniesienie **bez zmiany zachowania**. `model.ts` zostaje nakładką (`export * from …`) plus funkcjami, których nowy interfejs nie używa — dzięki temu stary `main.ts`, `map.ts` i stare testy działają bez zmian.

**Files:**
- Create: `frontend/src/data/types.ts`, `frontend/src/data/parse.ts`, `frontend/src/data/load.ts`, `frontend/src/domain/format.ts`, `frontend/src/domain/geometry.ts`, `frontend/src/domain/ranking.ts`, `frontend/src/domain/labels.ts`, `frontend/src/domain/access.ts`, `frontend/src/domain/bars.ts`, `frontend/src/domain/moisture.ts`, `frontend/src/domain/weather.ts`
- Modify: `frontend/src/model.ts`

**Interfaces:**
- Produces: te same nazwy i sygnatury co dziś w `model.ts`, w modułach według tabeli poniżej. Dotychczas prywatne pomocnicze funkcje oznaczone „(eksport)” stają się eksportowane.

- [ ] **Step 1: Przenieś kod według tabeli**

Wytnij z `frontend/src/model.ts` i wklej **bez zmian treści** (dodając tylko `export` tam, gdzie tabela mówi „(eksport)”, i potrzebne importy na górze plików):

| Moduł | Symbole z `model.ts` |
|---|---|
| `data/types.ts` | import typów `geojson`; `Explanation`, `Score`, `StandFeature`, `Stands`, `StandView`, `SpeciesShare`, `AccessCard`, `AccessCollection`, `AccessLayerId`, `StandDetail`, `HabitatCard`, `WeatherCard`, `Region`, `RegionView`, `ConditionsComponents`, `ForecastUncertainty`, `ConditionsDay`, `ConditionsRain`, `ConditionsTimeline`, `TripMeta` |
| `domain/format.ts` | `finite`, `finiteNumber` (eksport), `pl` (eksport), `pln` (eksport), `formatValue`, `distanceLabel`, `navigationUrl`, `roundedDistance` (eksport), `haversineKm`, `startDistanceLabel`, `areaLabel`, `dayMonth` (eksport) |
| `domain/geometry.ts` | `vertices`, `standCentroid` |
| `domain/ranking.ts` | `MIN_STANDALONE_AREA_HA`, `isStandaloneTarget`, `effectiveR`, `compareViews`, `rankEntries`, `joinData`, `joinRegions`, `pressureSwitchAvailable` |
| `domain/labels.ts` | `fruitingClass`, `habitatClass`, `STAND_STRUCTURE`, `standStructureLabel`, `densityLabel`, `neighborsSummary`, `distanceMethod`, `zakazNote`, `FOREST_DISTRICTS`, `ParsedStandId`, `parseStandId`, `standName`, `regionName`, `formatTripLabel` |
| `domain/access.ts` | `ACCESS_LAYERS`, `SURFACE_COLORS`, `SURFACE_LABELS`, `surfaceLabel`, `POINT_TYPE_LABELS`, `pointTypeLabel`, `SOURCE_LABELS`, `sourceLabel`, `attractivenessClass`, `roadKindLabel`, `distanceRange`, `regionAccessSummary`, `topPointSummary`, `ComponentRow`, `PRESSURE_TYPE_LABELS`, `pressureTop`, `keyFacts` |
| `domain/bars.ts` | `BarKey`, `Bar`, `threeWords`, `scoreBars` |
| `domain/moisture.ts` | `moistureAvailable`, `MOISTURE_STOPS`, `MOISTURE_NO_DATA_COLOR`, `hexToRgb`, `moistureColor`, `MOISTURE_LEGEND_TICKS`, `moistureTickLabel` |
| `domain/weather.ts` | `uncertaintyLabel`, `WEEKDAYS`, `dayLabel` |
| `data/parse.ts` | `object` (eksport), `strings` (eksport), `numeric` (eksport), `date` (eksport jako `isoDate`; w przeniesionym kodzie zmień wywołania `date(` na `isoDate(`), `nullableString` (eksport), `speciesShare`, `parseAccessCollection`, `parseData`, `isConditionsDay`, `parseConditions`, `parseTrips` |
| `data/load.ts` | `loadTrips` |

Zostają w `model.ts` (nowy interfejs ich nie używa; usuwane w Task 17): `confidenceLabel`, `entranceLabel`, `topExplanations`, `RANK_COLORS`, `RANK_QUANTILES`, `RANK_ZERO_COLOR`, `rankColorStops`, `accessCardSummary`, `loadData`, `WEATHER_DISCLAIMER`, `uncertaintyNote`, `weatherComponentLines`, `weatherCardLines`, `localPhenomenaNote`, `WFS_ONLY_BANNER_THRESHOLD`, `wfsOnlyBanner`, `habitatComponents`, `weatherComponents`, `ConditionBar`, `conditionBars`, `MapColorMode`, `MapControls`, `MAP_COLOR_KEY`, `colorModeForPressure`, `chooseColorMode`, `togglePressureControls`, `resolveColorMode`, `MOISTURE_NOTE`.

Importy w nowych modułach: typy zawsze `import type { … } from "../data/types"`; funkcje z innych modułów wprost (np. `domain/labels.ts` importuje `finite` z `./format`, `domain/bars.ts` importuje `finite` z `./format` i `fruitingClass` z `./labels`, `data/parse.ts` importuje `finite` z `../domain/format` i `vertices` z `../domain/geometry`, `joinData` z `../domain/ranking`).

- [ ] **Step 2: Nakładka w `model.ts`**

Na górze `frontend/src/model.ts` (w miejscu usuniętych typów) wstaw:

```ts
// Nakladka przejsciowa (nowy frontend, plan 2026-10-01): kod przeniesiony do src/data i
// src/domain; ponizej zostaja tylko funkcje starego interfejsu (usuwane w Task 17).
export * from "./data/types";
export * from "./data/parse";
export * from "./data/load";
export * from "./domain/format";
export * from "./domain/geometry";
export * from "./domain/ranking";
export * from "./domain/labels";
export * from "./domain/access";
export * from "./domain/bars";
export * from "./domain/moisture";
export * from "./domain/weather";
import type { AccessCard, ConditionsDay, ConditionsTimeline, Explanation, HabitatCard, Region, Score, StandDetail, Stands, WeatherCard, ForecastUncertainty } from "./data/types";
import { finite, finiteNumber, pl, pln, formatValue, dayMonth } from "./domain/format";
import { parseAccessCollection, parseConditions, parseData } from "./data/parse";
import { uncertaintyLabel, dayLabel } from "./domain/weather";
import { fruitingClass } from "./domain/labels";
import { pointTypeLabel, sourceLabel, type ComponentRow } from "./domain/access";
```

Po uruchomieniu `npx tsc --noEmit` usuń z tych dwóch linii importów nazwy, których pozostały kod `model.ts` nie używa (TypeScript zgłosi `is declared but never read` tylko przy `noUnusedLocals`; jeśli nie zgłasza, sprawdź ręcznie `grep` każdą nazwę w pozostałej części pliku) i dopisz te, których brakuje (błędy `Cannot find name`).

- [ ] **Step 3: Weryfikacja bez zmiany zachowania**

Run (w `frontend/`): `npx tsc --noEmit` → bez błędów; `npx vitest run` → PASS, **ta sama liczba testów co przed zadaniem**; `npm run build` → bez błędów.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/model.ts frontend/src/data frontend/src/domain
git commit -m "Nowy frontend: czysta logika przeniesiona z model.ts do src/data i src/domain (bez zmian zachowania)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Dane — nowe pola, wczytywanie w dwóch etapach, dane testowe

**Files:**
- Modify: `frontend/src/data/types.ts`, `frontend/src/data/parse.ts`, `frontend/src/data/load.ts`
- Create: `frontend/src/test-fixtures.ts`
- Test: `frontend/src/data/data.test.ts`

**Interfaces:**
- Consumes: przeniesione `parseData`, `parseConditions`, `parseAccessCollection`, `loadTrips` (Task 5).
- Produces:
  - typy: `Score.mask_reason?: string[]`, `Score.s_host_source?: string | null`, `Score.s_host_package_date?: string | null`, `SiteType`, `StandDetail.site_type?: SiteType | null`, `StandDetail.age_years?: number | null`, `DailyWeather`, `Rain26`, `WeatherWarning`, `ConditionsTimeline.lookback_days?/daily?/rain26?/warnings?`, `Manifest`, `Analysis`;
  - `parseDetails(raw: unknown, day: string | undefined, knownIds: Set<string>): StandDetail[]`, `parseManifest(raw: unknown): Manifest`;
  - `fetchJson(basePath: string, file: string, required: boolean): Promise<unknown>`;
  - `buildAnalysis(input: AnalysisInput): Analysis`, `loadCore(basePath: string): Promise<Analysis>`, `loadBackground(analysis: Analysis): Promise<Background>` z `Background = { details: Map<string, StandDetail>; accessPoints: AccessCollection | null; forestRoads: AccessCollection | null }`;
  - `test-fixtures.ts`: `DAY`, `addDays`, `makeScore`, `squareFeature`, `makeStands`, `makeRegion`, `makeDetail`, `makeConditions`, `legacyConditions`, `makeAnalysis`.

- [ ] **Step 1: Typy**

W `frontend/src/data/types.ts`:
- w `Score` dopisz pola:

```ts
  // Nowy frontend: powody odrzucenia przez filtry modelu (pusta lista w masce); brak w starszych eksportach.
  mask_reason?: string[];
  s_host_source?: string | null;
  s_host_package_date?: string | null;
```

- w `StandDetail` dopisz:

```ts
  // Nowy frontend: typ siedliskowy i wiek uzyty w modelu; brak w starszych eksportach.
  site_type?: SiteType | null;
  age_years?: number | null;
```

- w `ConditionsTimeline` dopisz:

```ts
  // Nowy frontend (panel pogody); brak w starszych eksportach.
  lookback_days?: number;
  daily?: DailyWeather[];
  rain26?: Rain26 | null;
  warnings?: WeatherWarning[];
```

- na końcu pliku dopisz:

```ts
export type SiteType = { code: string; label: string };
export type DailyWeather = {
  date: string;
  precip_mm: number | null;
  radar_share: number;
  tmin_c: number | null;
  tmax_c: number | null;
  forecast: boolean;
};
export type Rain26 = {
  sum_mm: number;
  window_start: string;
  window_end: string;
  normal_mm: number | null;
  pct: number | null;
  normal_source: string | null;
  normal_cells: number;
};
export type WeatherWarning = { type: string; dates: string[] };
export type Manifest = {
  lat: number | null;
  lon: number | null;
  radius_km: number | null;
  day: string | null;
  pressure_alpha: number | null;
};
export type Analysis = {
  basePath: string;
  day: string;
  scores: Score[];
  scoreById: Map<string, Score>;
  features: Map<string, StandFeature>;
  // Wydzielenia w masce z wynikiem, uszeregowane jak dotad (presja wlaczona).
  entries: StandView[];
  regions: Region[];
  regionsNoPressure: Region[] | null;
  conditions: ConditionsTimeline | null;
  manifest: Manifest;
};
```

- [ ] **Step 2: Dane testowe**

Utwórz `frontend/src/test-fixtures.ts`:

```ts
// Budowanie danych do testow (nie jest plikiem testowym). Wartosci jak w prawdziwym eksporcie
// z Zawadzkiego 30.09.2026, uproszczone.
import type { Analysis, ConditionsTimeline, DailyWeather, Region, Score, StandDetail, StandFeature, Stands } from "./data/types";
import { buildAnalysis } from "./data/load";

export const DAY = "2026-09-30";

export function addDays(day: string, k: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + k);
  return d.toISOString().slice(0, 10);
}

export function makeScore(id: string, over: Partial<Score> = {}): Score {
  return {
    stand_id: id, H: 0.9, F: 0.7, F_loc: 0.7, P: 0.2, R: 60, R_bez_presji: 63, M: 0.8, mask: true, day: DAY,
    confidence: "SREDNIA", confidence_reasons: [], explanation: [], distance_method: "access_points",
    entrance_status: "not_evaluated", area_ha: 2, tie_break: 0.5, mask_reason: [], ...over,
  };
}

export function squareFeature(id: string, i: number): StandFeature {
  const x = 18.4 + (i % 50) * 0.01;
  const y = 50.6 + Math.floor(i / 50) * 0.01;
  return {
    type: "Feature",
    properties: { stand_id: id },
    geometry: { type: "Polygon", coordinates: [[[x, y], [x + 0.005, y], [x + 0.005, y + 0.005], [x, y + 0.005], [x, y]]] },
  };
}

export function makeStands(ids: string[]): Stands {
  return { type: "FeatureCollection", features: ids.map((id, i) => squareFeature(id, i)) };
}

export function makeRegion(id: string, rank: number, standIds: string[], over: Partial<Region> = {}): Region {
  return {
    region_id: id, rank_score: rank, stand_count: standIds.length, stand_ids: standIds, day: DAY,
    centroid_lat: 50.61, centroid_lon: 18.41, near_place: { name: "Łaziska", distance_m: 1800 }, ...over,
  };
}

export function makeDetail(id: string, over: Partial<StandDetail> = {}): StandDetail {
  return {
    stand_id: id, day: DAY,
    drzew_species: [{ species_cd: "SO", name: "sosna zwyczajna", share: "udział 100 %" }],
    density: "0.9", podszyt_species: [], soil_type: "Gleby bielicowe", package_date: "2026-06-23",
    neighbors: [], stand_stru: "DRZEW", prot_categ: null, veg_cover: "zadarniona", standdensity_index: 0.9,
    searchability_hint: null,
    access: {
      d_parking_m: 2395, d_entrance_m: 2401, d_hard_forest_road_m: 1245, top_point_id: "p1",
      top_point_type: "parking", top_point_source: "bdl", top_point_name: null,
      pressure_contrib: { parking: 92, forest_road: 13 },
    },
    weather: null, habitat: null, forest_district: "Zawadzkie",
    site_type: { code: "BMSW", label: "Bór mieszany świeży" }, age_years: 64, ...over,
  };
}

export function makeConditions(over: Partial<ConditionsTimeline> = {}): ConditionsTimeline {
  const daily: DailyWeather[] = [];
  for (let k = -35; k <= 6; k++)
    daily.push({
      date: addDays(DAY, k), precip_mm: k === -8 ? 11.8 : k === -7 ? 7.1 : 0, radar_share: k <= 0 ? 1 : 0,
      tmin_c: 8, tmax_c: 22, forecast: k > 0,
    });
  return {
    day: DAY, generated_for: DAY, horizon_days: 7, pulse_min_mm: 12.7, lookback_days: 45,
    rains: [{ start: "2026-09-20", end: "2026-09-24", rain_mm: 30.7, days_ago: 6 }],
    summary: "Ostatni większy deszcz: 20–24.09 (30.7 mm), 6 dni temu",
    days: [{
      date: DAY, F: 0.64, level: 2, forecast: false, uncertainty: "ok",
      components: { cwb26_mm: -2, cwb26_typical_mm: -3.8, pct_cwb26: 0.54, tmean20_c: 13.7, temp_optimum_c: 13, tmin3_c: 8.7 },
    }],
    daily,
    rain26: {
      sum_mm: 59.6, window_start: addDays(DAY, -25), window_end: DAY, normal_mm: 48, pct: 0.71,
      normal_source: "E-OBS v33.0e, 1991–2020", normal_cells: 12,
    },
    warnings: [{ type: "frost", dates: [] }, { type: "heat_drought", dates: [] }],
    ...over,
  };
}

// Eksport sprzed nowego frontendu: bez daily, rain26, warnings, lookback_days.
export function legacyConditions(): ConditionsTimeline {
  const { daily: _d, rain26: _r, warnings: _w, lookback_days: _l, ...rest } = makeConditions();
  return rest;
}

export function makeAnalysis(opts: {
  scores: Score[];
  regions?: Region[];
  regionsNoPressure?: Region[];
  conditions?: ConditionsTimeline;
  manifest?: unknown;
}): Analysis {
  return buildAnalysis({
    basePath: "data/",
    scoresRaw: opts.scores,
    standsRaw: makeStands(opts.scores.map((s) => s.stand_id)),
    regionsRaw: opts.regions,
    regionsNoPressureRaw: opts.regionsNoPressure,
    conditionsRaw: opts.conditions,
    manifestRaw: opts.manifest ?? { lat: 50.6191, lon: 18.4611, radius_km: 20, day: DAY },
  });
}
```

(Zmienne `_d`, `_r`, `_w`, `_l` służą tylko do pominięcia pól; jeśli `tsc` zgłasza je jako nieużywane, zastąp destrukturyzację kopią obiektu i `delete` czterech pól.)

- [ ] **Step 3: Testy danych**

Utwórz `frontend/src/data/data.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildAnalysis, fetchJson, loadBackground } from "./load";
import { parseConditions, parseData, parseDetails, parseManifest } from "./parse";
import { DAY, legacyConditions, makeAnalysis, makeConditions, makeDetail, makeScore, makeStands } from "../test-fixtures";

const json = (body: unknown) =>
  ({ ok: true, headers: new Headers({ "content-type": "application/json" }), json: async () => body }) as unknown as Response;
const html = () =>
  ({ ok: true, headers: new Headers({ "content-type": "text/html" }), json: async () => { throw new SyntaxError("<"); } }) as unknown as Response;
const missing = () => ({ ok: false, headers: new Headers(), json: async () => null }) as unknown as Response;

afterEach(() => vi.unstubAllGlobals());

describe("parseData — nowe i opcjonalne pola wyników", () => {
  it("przyjmuje wyniki bez confidence/explanation i uzupełnia wartości domyślne", () => {
    const bare = { ...makeScore("A") } as Record<string, unknown>;
    delete bare.confidence;
    delete bare.confidence_reasons;
    delete bare.explanation;
    const { scores } = parseData([bare], makeStands(["A"]));
    expect(scores[0].confidence).toBe("");
    expect(scores[0].explanation).toEqual([]);
  });
  it("sprawdza mask_reason: lista tekstów albo brak", () => {
    expect(parseData([makeScore("A", { mask: false, mask_reason: ["too_young"] })], makeStands(["A"])).scores[0].mask_reason)
      .toEqual(["too_young"]);
    expect(() => parseData([{ ...makeScore("A"), mask_reason: "x" }], makeStands(["A"]))).toThrow();
  });
});

describe("parseDetails", () => {
  const ids = new Set(["A"]);
  it("pusty wynik bez pliku, typ siedliska i wiek z pliku", () => {
    expect(parseDetails(undefined, DAY, ids)).toEqual([]);
    const [d] = parseDetails([makeDetail("A")], DAY, ids);
    expect(d.site_type?.label).toBe("Bór mieszany świeży");
    expect(d.age_years).toBe(64);
  });
  it("przyjmuje szczegóły ze starszego eksportu bez site_type i age_years", () => {
    const old = { ...makeDetail("A") } as Record<string, unknown>;
    delete old.site_type;
    delete old.age_years;
    expect(parseDetails([old], DAY, ids)).toHaveLength(1);
  });
  it("odrzuca zły typ siedliska, obce wydzielenie i inną datę", () => {
    expect(() => parseDetails([makeDetail("A", { site_type: { code: 1 } as never })], DAY, ids)).toThrow();
    expect(() => parseDetails([makeDetail("B")], DAY, ids)).toThrow();
    expect(() => parseDetails([makeDetail("A", { day: "2026-09-29" })], DAY, ids)).toThrow();
  });
});

describe("parseConditions — pola panelu pogody", () => {
  it("przyjmuje nowy i stary format", () => {
    expect(parseConditions(makeConditions(), DAY)?.rain26?.normal_mm).toBe(48);
    expect(parseConditions(legacyConditions(), DAY)?.daily).toBeUndefined();
  });
  it("odrzuca zły wiersz daily, rain26 bez sumy i złe ostrzeżenie", () => {
    const bad = makeConditions();
    expect(() => parseConditions({ ...bad, daily: [{ date: DAY }] }, DAY)).toThrow();
    expect(() => parseConditions({ ...bad, rain26: { ...bad.rain26!, sum_mm: null } }, DAY)).toThrow();
    expect(() => parseConditions({ ...bad, warnings: [{ type: "frost", dates: ["wczoraj"] }] }, DAY)).toThrow();
  });
  it("przyjmuje rain26 bez normy", () => {
    const c = makeConditions();
    const noNormal = { ...c, rain26: { ...c.rain26!, normal_mm: null, pct: null, normal_source: null, normal_cells: 0 } };
    expect(parseConditions(noNormal, DAY)?.rain26?.normal_mm).toBeNull();
  });
});

describe("parseManifest", () => {
  it("toleruje brak pliku i złe wartości", () => {
    expect(parseManifest(undefined)).toEqual({ lat: null, lon: null, radius_km: null, day: null, pressure_alpha: null });
    expect(parseManifest({ lat: 50.6, lon: "x", radius_km: 20, day: DAY }).lon).toBeNull();
  });
});

describe("fetchJson", () => {
  it("plik opcjonalny: strona HTML lub 404 to brak pliku", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    expect(await fetchJson("data/", "regions.json", false)).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn(async () => missing()));
    expect(await fetchJson("data/", "regions.json", false)).toBeUndefined();
  });
  it("plik wymagany: brak albo niepoprawna treść to czytelny błąd", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => missing()));
    await expect(fetchJson("data/", "scores.json", true)).rejects.toThrow("Nie udało się wczytać scores.json");
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    await expect(fetchJson("data/", "scores.json", true)).rejects.toThrow("niepoprawny");
  });
});

describe("buildAnalysis i loadBackground", () => {
  it("buduje mapy wyników i geometrii oraz ranking wydzieleń w masce", () => {
    const a = makeAnalysis({ scores: [makeScore("A", { R: 50 }), makeScore("B", { R: 70 }), makeScore("C", { mask: false, R: 0 })] });
    expect(a.day).toBe(DAY);
    expect(a.scoreById.size).toBe(3);
    expect(a.features.has("C")).toBe(true);
    expect(a.entries.map((e) => e.score.stand_id)).toEqual(["B", "A"]);
    expect(a.manifest.radius_km).toBe(20);
  });
  it("wczytuje szczegóły i warstwy w tle; brak pliku szczegółów to pusta mapa", async () => {
    const a = buildAnalysis({ basePath: "data/", scoresRaw: [makeScore("A")], standsRaw: makeStands(["A"]) });
    vi.stubGlobal("fetch", vi.fn(async (url: unknown) => (String(url).includes("details.json") ? json([makeDetail("A")]) : html())));
    const bg = await loadBackground(a);
    expect(bg.details.get("A")?.age_years).toBe(64);
    expect(bg.accessPoints).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    expect((await loadBackground(a)).details.size).toBe(0);
  });
});
```

Run: `npx vitest run src/data/data.test.ts`
Expected: FAIL (brak `buildAnalysis`, `fetchJson`, `loadBackground`, `parseDetails`, `parseManifest`).

- [ ] **Step 4: Parsowanie**

W `frontend/src/data/parse.ts`:

1. W walidacji wyników w `parseData` zastąp warunki `typeof s.confidence === "string" && strings(s.confidence_reasons) &&` oraz blok `Array.isArray(s.explanation) && s.explanation.every(…)` tym:

```ts
        (s.confidence === undefined || typeof s.confidence === "string") &&
        (s.confidence_reasons === undefined || strings(s.confidence_reasons)) &&
        (s.mask_reason === undefined || strings(s.mask_reason)) &&
        (s.s_host_source === undefined || nullableString(s.s_host_source)) &&
        (s.explanation === undefined ||
          (Array.isArray(s.explanation) &&
            s.explanation.every(
              (e) => object(e) && typeof e.text === "string" && typeof e.factor === "string" && finite(e.contribution),
            ))),
```

2. Zastąp `const scores = rawScores as Score[],` normalizacją (reszta kodu bez zmian):

```ts
  // Nowy frontend: pola starego interfejsu sa opcjonalne w pliku, ale typ Score ich wymaga.
  const scores = (rawScores as Score[]).map((s) => ({
    ...s,
    confidence: s.confidence ?? "",
    confidence_reasons: s.confidence_reasons ?? [],
    explanation: s.explanation ?? [],
  }));
  const stands = rawStands as unknown as Stands;
```

3. Wydziel walidację szczegółów do funkcji eksportowanej i dopisz nowe pola; w `parseData` zastąp cały blok `let details: StandDetail[] = []; if (rawDetails !== undefined) { … }` linią `const details = parseDetails(rawDetails, scores[0]?.day, new Set(standIds));`, a pod `parseData` dodaj:

```ts
const siteType = (x: unknown) =>
  x === undefined || x === null || (object(x) && typeof x.code === "string" && typeof x.label === "string");

export function parseDetails(rawDetails: unknown, day: string | undefined, knownIds: Set<string>): StandDetail[] {
  // Szczegoly sa opcjonalne: brak pliku to brak sekcji na karcie, nie blad.
  if (rawDetails === undefined) return [];
  if (
    !Array.isArray(rawDetails) ||
    !rawDetails.every(
      (d) =>
        object(d) &&
        typeof d.stand_id === "string" &&
        isoDate(d.day) &&
        Array.isArray(d.drzew_species) &&
        d.drzew_species.every(speciesShare) &&
        nullableString(d.density) &&
        Array.isArray(d.podszyt_species) &&
        d.podszyt_species.every(speciesShare) &&
        nullableString(d.soil_type) &&
        nullableString(d.package_date) &&
        strings(d.neighbors) &&
        nullableString(d.stand_stru) &&
        nullableString(d.prot_categ) &&
        (d.veg_cover === undefined || nullableString(d.veg_cover)) &&
        (d.standdensity_index === undefined || d.standdensity_index === null || finite(d.standdensity_index)) &&
        (d.searchability_hint === undefined || nullableString(d.searchability_hint)) &&
        (d.access === undefined || d.access === null || object(d.access)) &&
        (d.habitat === undefined || d.habitat === null || object(d.habitat)) &&
        (d.forest_district === undefined || nullableString(d.forest_district)) &&
        siteType(d.site_type) &&
        (d.age_years === undefined || numeric(d.age_years)),
    )
  )
    throw new Error("Niepoprawny plik szczegółów wydzieleń.");
  const details = rawDetails as StandDetail[];
  if (details.some((d) => d.day !== day))
    throw new Error("Plik szczegółów pochodzi z innej daty. Zsynchronizuj dane ponownie.");
  if (details.some((d) => !knownIds.has(d.stand_id)))
    throw new Error("Szczegóły odwołują się do wydzielenia spoza zsynchronizowanego zestawu.");
  return details;
}

export function parseManifest(raw: unknown): Manifest {
  const m: Record<string, unknown> = object(raw) ? raw : {};
  const num = (v: unknown) => (finite(v) ? v : null);
  return {
    lat: num(m.lat),
    lon: num(m.lon),
    radius_km: num(m.radius_km),
    day: typeof m.day === "string" ? m.day : null,
    pressure_alpha: num(m.pressure_alpha),
  };
}
```

4. W `parseConditions` dopisz walidację nowych pól (nad funkcją pomocnicze, w warunku funkcji cztery nowe linie):

```ts
const dailyEntry = (d: unknown) =>
  object(d) && isoDate(d.date) && numeric(d.precip_mm) && finite(d.radar_share) &&
  numeric(d.tmin_c) && numeric(d.tmax_c) && typeof d.forecast === "boolean";
const rain26Entry = (r: unknown) =>
  r === null ||
  (object(r) && finite(r.sum_mm) && isoDate(r.window_start) && isoDate(r.window_end) && numeric(r.normal_mm) &&
    numeric(r.pct) && nullableString(r.normal_source) && finite(r.normal_cells));
const warningEntry = (w: unknown) =>
  object(w) && typeof w.type === "string" && strings(w.dates) && w.dates.every(isoDate);
```

```ts
    (c.daily === undefined || (Array.isArray(c.daily) && c.daily.every(dailyEntry))) &&
    (c.rain26 === undefined || rain26Entry(c.rain26)) &&
    (c.warnings === undefined || (Array.isArray(c.warnings) && c.warnings.every(warningEntry))) &&
    (c.lookback_days === undefined || finite(c.lookback_days)) &&
```

(Dopisz te cztery linie do istniejącego warunku `if (!c || …)` w miejscu, gdzie sprawdzane jest `c.days.every(isConditionsDay)`, zachowując negację całego warunku.) Dopisz brakujące importy typów (`Manifest`, `StandDetail`, `Stands`, `Score`).

- [ ] **Step 5: Wczytywanie**

Dopisz w `frontend/src/data/load.ts` (obok przeniesionego `loadTrips`):

```ts
import type { AccessCollection, Analysis, StandDetail } from "./types";
import { parseAccessCollection, parseConditions, parseData, parseDetails, parseManifest } from "./parse";

const isJsonResponse = (response: Response) => response.headers.get("content-type")?.includes("json") ?? false;

// Serwer Vite odpowiada na brakujacy plik strona index.html (200, text/html) zamiast 404, wiec
// plik opcjonalny bez naglowka JSON traktujemy jak brak. Plik wymagany sprawdza sam JSON.parse.
export async function fetchJson(basePath: string, file: string, required: boolean): Promise<unknown> {
  const response = await fetch(`${import.meta.env.BASE_URL}${basePath}${file}`, {
    cache: "no-cache",
    signal: AbortSignal.timeout(60000),
  }).catch(() => undefined);
  if (!response?.ok || (!required && !isJsonResponse(response))) {
    if (required)
      throw new Error(`Nie udało się wczytać ${file}. Przygotuj i zsynchronizuj dane przed otwarciem mapy.`);
    return undefined;
  }
  try {
    return await response.json();
  } catch {
    throw new Error(`Plik ${file} jest niedostępny lub niepoprawny. Uruchom synchronizację danych.`);
  }
}

export type AnalysisInput = {
  basePath: string;
  scoresRaw: unknown;
  standsRaw: unknown;
  regionsRaw?: unknown;
  regionsNoPressureRaw?: unknown;
  conditionsRaw?: unknown;
  manifestRaw?: unknown;
};

export function buildAnalysis(input: AnalysisInput): Analysis {
  const parsed = parseData(input.scoresRaw, input.standsRaw, input.regionsRaw, undefined, input.regionsNoPressureRaw);
  const day = parsed.scores[0]?.day ?? "";
  return {
    basePath: input.basePath,
    day,
    scores: parsed.scores,
    scoreById: new Map(parsed.scores.map((s) => [s.stand_id, s])),
    features: new Map(parsed.stands.features.map((f) => [f.properties.stand_id, f])),
    entries: parsed.entries,
    regions: parsed.regions,
    regionsNoPressure: parsed.regionsNoPressure,
    conditions: parseConditions(input.conditionsRaw, day),
    manifest: parseManifest(input.manifestRaw),
  };
}

// Pierwszy widok: wyniki, geometrie, rejony, warunki, manifest.
export async function loadCore(basePath: string): Promise<Analysis> {
  const [scoresRaw, standsRaw] = await Promise.all([
    fetchJson(basePath, "scores.json", true),
    fetchJson(basePath, "stands.geojson", true),
  ]);
  const [regionsRaw, regionsNoPressureRaw, conditionsRaw, manifestRaw] = await Promise.all(
    ["regions.json", "regions_bez_presji.json", "conditions.json", "manifest.json"].map((file) =>
      fetchJson(basePath, file, false),
    ),
  );
  return buildAnalysis({ basePath, scoresRaw, standsRaw, regionsRaw, regionsNoPressureRaw, conditionsRaw, manifestRaw });
}

export type Background = {
  details: Map<string, StandDetail>;
  accessPoints: AccessCollection | null;
  forestRoads: AccessCollection | null;
};

// W tle, po pierwszym widoku: szczegoly (ok. 43 MB) i warstwy dostepu.
export async function loadBackground(analysis: Analysis): Promise<Background> {
  const [detailsRaw, pointsRaw, roadsRaw] = await Promise.all(
    ["details.json", "access_points.json", "forest_roads.json"].map((file) => fetchJson(analysis.basePath, file, false)),
  );
  const list = parseDetails(detailsRaw, analysis.day, new Set(analysis.features.keys()));
  return {
    details: new Map(list.map((d) => [d.stand_id, d])),
    accessPoints: parseAccessCollection(pointsRaw, "access_points.json"),
    forestRoads: parseAccessCollection(roadsRaw, "forest_roads.json"),
  };
}
```

- [ ] **Step 6: Weryfikacja**

Run: `npx vitest run` → PASS (stare i nowe testy; stary `loadData` dalej działa, bo używa `parseData`); `npx tsc --noEmit` → bez błędów.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/data frontend/src/test-fixtures.ts
git commit -m "Nowy frontend: nowe pola danych, wczytywanie w dwoch etapach, dane testowe

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Logika domenowa — klasy procentowe, pasek rejonu, opisy, etykiety

**Files:**
- Create: `tests/fixtures/klasy_procentowe.json`, `tests/test_klasy_procentowe.py`
- Modify: `frontend/src/domain/ranking.ts`, `frontend/src/domain/labels.ts`, `frontend/src/domain/bars.ts`, `frontend/src/domain/format.ts`
- Test: `frontend/src/domain/extras.test.ts`

**Interfaces:**
- Produces:
  - `ranking.ts`: `type ScoreClass = 1 | 2 | 3 | 4`, `CLASS_THRESHOLDS`, `CLASS_LABELS: Record<ScoreClass, string>`, `classifyByPercentile(values: number[]): ScoreClass[]`, `regionAreaHa(view: RegionView): number | null`;
  - `labels.ts`: `maskReasonTexts(reasons?: string[]): string[]`, `yearsLabel(n: number): string`, `speciesShort(species: SpeciesShare[], max?: number): string | null`, `formatDateLong(day?: string | null): string`, `analysisLabel(o: { tripName: string | null; radiusKm: number | null; day: string | null }): string`, `tooltipText(name: string, r: number | null, cls: ScoreClass | 0): string`;
  - `bars.ts`: `median(values: number[]): number | null`, `regionBars(members: StandView[], pressure: boolean): Bar[]`, `type BarNotes = Partial<Record<BarKey, string>>`, `barNotes(score: Score, detail: StandDetail | null | undefined, pressure: boolean): BarNotes`;
  - `format.ts`: `joinMeta(parts: (string | null | undefined | false)[]): string`.

- [ ] **Step 1: Wspólny przykład klas (Python i TypeScript)**

Utwórz `tests/fixtures/klasy_procentowe.json` (wartości `klasy` wygenerowane z `pipeline.phone_kmz.classify_by_percentile`):

```json
{
  "opis": "Wspolny przyklad klas procentowych: te same oczekiwane klasy sprawdza test Pythona (phone_kmz) i test frontendu (mapa).",
  "przypadki": [
    {"wartosci": [1, 10, 0.5, 8, 7, 1, 9, 0.1, 6, 8, 5, 0.2, 4, 3, 1, 2, 0.5, 0.05, 0.1, 0.0],
     "klasy": [4, 1, 4, 2, 3, 4, 2, 4, 3, 2, 3, 4, 3, 3, 4, 3, 4, 4, 4, 4]},
    {"wartosci": [5.0], "klasy": [1]},
    {"wartosci": [3.0, 3.0, 3.0], "klasy": [1, 1, 1]},
    {"wartosci": [], "klasy": []}
  ]
}
```

Utwórz `tests/test_klasy_procentowe.py`:

```python
import json
from pathlib import Path

from pipeline.phone_kmz import classify_by_percentile

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "klasy_procentowe.json").read_text(encoding="utf-8"))


def test_classify_by_percentile_matches_the_shared_fixture():
    for case in FIXTURE["przypadki"]:
        assert classify_by_percentile(case["wartosci"]) == case["klasy"]
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_klasy_procentowe.py -q`
Expected: PASS (przykład opisuje istniejące zachowanie).

- [ ] **Step 2: Testy frontendu**

Utwórz `frontend/src/domain/extras.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import fixture from "../../../tests/fixtures/klasy_procentowe.json";
import { CLASS_LABELS, classifyByPercentile, regionAreaHa } from "./ranking";
import { analysisLabel, formatDateLong, maskReasonTexts, speciesShort, tooltipText, yearsLabel } from "./labels";
import { barNotes, median, regionBars } from "./bars";
import { joinMeta } from "./format";
import { joinRegions } from "./ranking";
import { makeAnalysis, makeDetail, makeRegion, makeScore } from "../test-fixtures";

describe("classifyByPercentile", () => {
  it("daje te same klasy co eksport KMZ (wspólny przykład z Pythonem)", () => {
    for (const c of fixture.przypadki) expect(classifyByPercentile(c.wartosci)).toEqual(c.klasy);
  });
  it("opisuje klasy słowami", () => {
    expect(CLASS_LABELS[1]).toBe("najlepsze 5%");
    expect(CLASS_LABELS[4]).toBe("pozostałe");
  });
});

describe("pasek rejonu i opisy pod paskami", () => {
  it("rejon: mediana 5 najlepszych wydzieleń", () => {
    const hs = [1, 0.9, 0.8, 0.7, 0.6, 0.1];
    const scores = hs.map((h, i) => makeScore(`S${i}`, { H: h, R: 90 - i * 10 }));
    const a = makeAnalysis({ scores, regions: [makeRegion("region_1", 70, scores.map((s) => s.stand_id))] });
    const [view] = joinRegions(a.regions, a.entries);
    expect(regionBars(view.members, true)[0].value).toBeCloseTo(0.8);
    expect(regionAreaHa(view)).toBe(12);
  });
  it("median", () => {
    expect(median([])).toBeNull();
    expect(median([3, 1, 2])).toBe(2);
    expect(median([1, 2, 3, 4])).toBe(2.5);
  });
  it("opisy: skład, siedlisko, wiek; opad i wilgotność; źródło presji tylko z presją", () => {
    const detail = makeDetail("A", {
      weather: {
        p26_mm: 79.4, cwb26_mm: 9.4, cwb26_typical_mm: -5.6, pct_cwb26: 0.74, tmean20_c: 13.5, temp_optimum_c: 13,
        tmin3_c: 10.4, frost: "brak", frost_date: null, F: 0.82, forecast_days: 1, forecast_window_share: 0,
      },
    });
    const notes = barNotes(makeScore("A", { M: 0.915 }), detail, true);
    expect(notes.habitat).toBe("sosna 100% · Bór mieszany świeży · 64 lata");
    expect(notes.weather).toBe("opad 79 mm / 26 dni · wilgotność 0,92 · 13,5 °C średnio 20 dni");
    expect(notes.calm).toBe("najwięcej presji: parking (2,4 km)");
    expect(barNotes(makeScore("A"), detail, false).calm).toBeUndefined();
    expect(barNotes(makeScore("A", { M: null }), null, true)).toEqual({});
  });
});

describe("etykiety", () => {
  it("powody spoza filtrów", () => {
    expect(maskReasonTexts(["too_young", "gdos"])).toEqual([
      "za młody drzewostan (młodnik)",
      "rezerwat przyrody lub park narodowy (GDOŚ)",
    ]);
    expect(maskReasonTexts([])).toEqual(["powód nieznany w tej analizie"]);
    expect(maskReasonTexts(undefined)).toEqual(["powód nieznany w tej analizie"]);
    expect(maskReasonTexts(["nowy_kod"])).toEqual(["nowy_kod"]);
  });
  it("lata po polsku", () => {
    expect([1, 2, 4, 5, 12, 22, 64, 100, 112].map(yearsLabel)).toEqual([
      "1 rok", "2 lata", "4 lata", "5 lat", "12 lat", "22 lata", "64 lata", "100 lat", "112 lat",
    ]);
  });
  it("skład w skrócie: łączy powtórzone gatunki, pomija udziały śladowe", () => {
    expect(speciesShort([
      { species_cd: "JS", name: "jesion wyniosły", share: "udział 60 %" },
      { species_cd: "LP", name: "lipa drobnolistna", share: "udział 10 %" },
      { species_cd: "LP", name: "lipa drobnolistna", share: "udział 20 %" },
      { species_cd: "JS", name: "jesion wyniosły", share: "udział 10 %" },
      { species_cd: "BK", name: "buk zwyczajny", share: "poniżej 5 % - miejscami" },
    ])).toBe("jesion 70%, lipa 30%");
    expect(speciesShort([])).toBeNull();
  });
  it("daty, opis analizy, dymek, metryka", () => {
    expect(formatDateLong("2026-09-30")).toBe("30 września 2026");
    expect(formatDateLong(null)).toBe("—");
    expect(analysisLabel({ tripName: null, radiusKm: 20, day: "2026-09-30" })).toBe("Aktualna analiza · 20 km · 30 września 2026");
    expect(analysisLabel({ tripName: "Kieleczka", radiusKm: null, day: null })).toBe("Kieleczka");
    expect(tooltipText("Oddz. 96a", 81.1, 1)).toBe("Oddz. 96a · wynik 81 · najlepsze 5%");
    expect(tooltipText("Oddz. 96a", null, 0)).toBe("Oddz. 96a · poza filtrami modelu");
    expect(tooltipText("Oddz. 96a", null, 3)).toBe("Oddz. 96a · brak wyniku");
    expect(joinMeta(["3,9 ha", null, "", false, "8 km"])).toBe("3,9 ha · 8 km");
  });
});
```

Run (w `frontend/`): `npx vitest run src/domain/extras.test.ts`
Expected: FAIL (brak nowych funkcji).

- [ ] **Step 3: Implementacja — `format.ts` i `ranking.ts`**

Dopisz w `frontend/src/domain/format.ts`:

```ts
export const joinMeta = (parts: (string | null | undefined | false)[]): string =>
  parts.filter((p): p is string => typeof p === "string" && p.length > 0).join(" · ");
```

Dopisz w `frontend/src/domain/ranking.ts`:

```ts
export type ScoreClass = 1 | 2 | 3 | 4;
// Jak pipeline/phone_kmz.py::CLASS_THRESHOLDS -- ten sam podzial co eksport KMZ na telefon.
export const CLASS_THRESHOLDS = { 1: 0.05, 2: 0.2, 3: 0.5 } as const;
export const CLASS_LABELS: Record<ScoreClass, string> = {
  1: "najlepsze 5%",
  2: "5–20%",
  3: "20–50%",
  4: "pozostałe",
};

/** Klasa 1..4: udzial wartosci scisle wiekszych < 5% / 20% / 50%; remisy w tej samej klasie. */
export function classifyByPercentile(values: number[]): ScoreClass[] {
  const n = values.length;
  if (!n) return [];
  const ascending = [...values].sort((a, b) => a - b);
  const countAtMost = (x: number) => {
    let lo = 0;
    let hi = n;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (ascending[mid] <= x) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  };
  return values.map((v) => {
    const share = (n - countAtMost(v)) / n;
    return share < CLASS_THRESHOLDS[1] ? 1 : share < CLASS_THRESHOLDS[2] ? 2 : share < CLASS_THRESHOLDS[3] ? 3 : 4;
  });
}

export function regionAreaHa(view: RegionView): number | null {
  const total = view.members.reduce((sum, m) => sum + (finite(m.score.area_ha) ? m.score.area_ha : 0), 0);
  return total > 0 ? total : null;
}
```

- [ ] **Step 4: Implementacja — `labels.ts`**

Dopisz w `frontend/src/domain/labels.ts` (importy: `pl`, `joinMeta` z `./format`; `CLASS_LABELS`, `type ScoreClass` z `./ranking`; `type SpeciesShare` z `../data/types`):

```ts
const MASK_REASON_TEXT: Record<string, string> = {
  not_dstan: "to nie drzewostan (np. zrąb, łąka, droga)",
  no_age: "brak wieku drzewostanu w danych",
  too_young: "za młody drzewostan (młodnik)",
  excluded_species: "gatunek wykluczający (np. olsza, jesion) stanowi co najmniej 80%",
  gdos: "rezerwat przyrody lub park narodowy (GDOŚ)",
  zakaz: "okresowy zakaz wstępu do lasu",
};

export function maskReasonTexts(reasons?: string[]): string[] {
  if (!reasons || !reasons.length) return ["powód nieznany w tej analizie"];
  return reasons.map((r) => MASK_REASON_TEXT[r] ?? r);
}

export function yearsLabel(n: number): string {
  const k = Math.round(n);
  if (k === 1) return "1 rok";
  const last = k % 10;
  const lastTwo = k % 100;
  const few = last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14);
  return `${k} ${few ? "lata" : "lat"}`;
}

/** "sosna 70%, świerk 30%": sumuje powtorzone gatunki, pomija udzialy sladowe ("poniżej 5 %"). */
export function speciesShort(species: SpeciesShare[], max = 3): string | null {
  const totals = new Map<string, { name: string; share: number }>();
  for (const s of species) {
    const match = /udział\s+(\d+)\s*%/.exec(s.share);
    if (!match) continue;
    const previous = totals.get(s.species_cd);
    totals.set(s.species_cd, { name: s.name.split(" ")[0], share: (previous?.share ?? 0) + Number(match[1]) });
  }
  const list = [...totals.values()].sort((a, b) => b.share - a.share).slice(0, max);
  return list.length ? list.map((x) => `${x.name} ${x.share}%`).join(", ") : null;
}

export function formatDateLong(day?: string | null): string {
  if (!day || !/^\d{4}-\d{2}-\d{2}$/.test(day)) return "—";
  return new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
}

export function analysisLabel(o: { tripName: string | null; radiusKm: number | null; day: string | null }): string {
  return joinMeta([o.tripName ?? "Aktualna analiza", o.radiusKm !== null ? `${pl(o.radiusKm)} km` : null, o.day ? formatDateLong(o.day) : null]);
}

export function tooltipText(name: string, r: number | null, cls: ScoreClass | 0): string {
  if (cls === 0) return `${name} · poza filtrami modelu`;
  if (r === null) return `${name} · brak wyniku`;
  return `${name} · wynik ${Math.round(r)} · ${CLASS_LABELS[cls]}`;
}
```

- [ ] **Step 5: Implementacja — `bars.ts`**

Dopisz w `frontend/src/domain/bars.ts` (importy: `finite`, `formatValue`, `pl` z `./format`; `speciesShort`, `yearsLabel` z `./labels`; `pressureTop` z `./access`; typy `Score`, `StandDetail`, `StandView` z `../data/types`):

```ts
export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Paski rejonu: mediana 5 najlepszych wydzielen (ta sama podstawa co rank_score rejonu). */
export function regionBars(members: StandView[], pressure: boolean): Bar[] {
  const top = [...members].sort((a, b) => b.r - a.r).slice(0, 5);
  const pick = (value: (s: Score) => number | null) => median(top.map((m) => value(m.score)).filter(finite));
  return scoreBars({ H: pick((s) => s.H), F_loc: pick((s) => s.F_loc), P: pick((s) => s.P) }, pressure);
}

export type BarNotes = Partial<Record<BarKey, string>>;

/** Krotkie opisy pod paskami karty wydzielenia (tylko to, co jest w eksporcie). */
export function barNotes(score: Score, detail: StandDetail | null | undefined, pressure: boolean): BarNotes {
  const notes: BarNotes = {};
  const age = detail?.age_years;
  const habitat = [
    speciesShort(detail?.drzew_species ?? []),
    detail?.site_type?.label ?? null,
    finite(age) ? yearsLabel(age) : null,
  ].filter((x): x is string => !!x);
  if (habitat.length) notes.habitat = habitat.join(" · ");
  const p26 = detail?.weather?.p26_mm;
  const t20 = detail?.weather?.tmean20_c;
  const moisture = score.M;
  const weather = [
    finite(p26) ? `opad ${pl(p26)} mm / 26 dni` : null,
    finite(moisture) ? `wilgotność ${formatValue(moisture)}` : null,
    finite(t20) ? `${pl(t20, 1)} °C średnio 20 dni` : null,
  ].filter((x): x is string => !!x);
  if (weather.length) notes.weather = weather.join(" · ");
  if (pressure) {
    const top = pressureTop(detail?.access, 1)[0];
    if (top) notes.calm = `najwięcej presji: ${top.label}${top.value ? ` (${top.value})` : ""}`;
  }
  return notes;
}
```

- [ ] **Step 6: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/klasy_procentowe.json tests/test_klasy_procentowe.py frontend/src/domain
git commit -m "Nowy frontend: klasy procentowe (wspolny przyklad z KMZ), paski rejonu, opisy i etykiety

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Model panelu pogody

**Files:**
- Modify: `frontend/src/domain/weather.ts`
- Test: `frontend/src/domain/weather.test.ts`

**Interfaces:**
- Consumes: `ConditionsTimeline` (Task 6), `dayMonth`, `finite`, `pl` (format), `dayLabel` (weather, przeniesione).
- Produces: typy `RainBarKind`, `RainBar`, `TempPoint`, `ForecastRow`, `WeatherFact`, `WeatherCheck`, `WeatherPanelModel`; `WEATHER_NOTE`; `dayRangeLabel(start, end)`, `daysAgoLabel(n)`, `buildWeatherPanel(c: ConditionsTimeline | null): WeatherPanelModel | null`.

- [ ] **Step 1: Testy**

Utwórz `frontend/src/domain/weather.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildWeatherPanel, dayRangeLabel, daysAgoLabel } from "./weather";
import { DAY, legacyConditions, makeConditions } from "../test-fixtures";

describe("panel pogody — nowy format", () => {
  const m = buildWeatherPanel(makeConditions())!;
  it("nagłówek z samymi faktami", () => {
    expect(m.legacy).toBe(false);
    expect(m.headline).toBe("6 dni po większym deszczu · 60 mm w 26 dni (norma 48)");
  });
  it("trzy liczby", () => {
    expect(m.facts.map((f) => [f.value, f.note])).toEqual([
      ["60 mm", "norma 48 mm"],
      ["6 dni temu", "20–24.09 · 30,7 mm"],
      ["13,7 °C", "optimum ok. 13 °C"],
    ]);
  });
  it("zdanie o normie", () => {
    expect(m.normalLine).toBe("Więcej deszczu niż w 71% lat 1991–2020 o tej porze (E-OBS).");
  });
  it("słupki: 35 dni wstecz + dziś + 6 dni prognozy, okno 26 dni, jeden dzień dzisiejszy", () => {
    expect(m.bars).toHaveLength(42);
    expect(m.bars.filter((b) => b.inWindow)).toHaveLength(26);
    expect(m.bars.findIndex((b) => b.isToday)).toBe(35);
    expect(m.bars[0].kind).toBe("measured");
    expect(m.bars[41].kind).toBe("forecast");
  });
  it("tabela 7 dni i brak ostrzeżeń", () => {
    expect(m.forecast.map((r) => r.label)).toEqual(["dziś", "cz", "pt", "sb", "nd", "pn", "wt"]);
    expect(m.checks).toEqual([
      { label: "bez przymrozku", active: false },
      { label: "bez upału z suszą", active: false },
    ]);
  });
});

describe("panel pogody — warianty", () => {
  it("mniej deszczu niż zwykle", () => {
    const c = makeConditions();
    const m = buildWeatherPanel({ ...c, rain26: { ...c.rain26!, pct: 0.3 } })!;
    expect(m.normalLine).toBe("Mniej deszczu niż w 70% lat 1991–2020 o tej porze (E-OBS).");
  });
  it("bez większego deszczu i bez normy", () => {
    const c = makeConditions();
    const m = buildWeatherPanel({ ...c, rains: [], rain26: { ...c.rain26!, normal_mm: null, pct: null, normal_source: null, normal_cells: 0 } })!;
    expect(m.headline).toBe("Brak większego deszczu od 45 dni · 60 mm w 26 dni");
    expect(m.facts[0].note).toBe("bez normy");
    expect(m.normalLine).toBeNull();
  });
  it("przymrozek w prognozie i dzień bez radaru", () => {
    const c = makeConditions({ warnings: [{ type: "frost", dates: ["2026-10-04"] }, { type: "heat_drought", dates: [] }] });
    c.daily![10] = { ...c.daily![10], radar_share: 0 };
    const m = buildWeatherPanel(c)!;
    expect(m.checks[0]).toEqual({ label: "Przymrozek: 4.10", active: true });
    expect(m.bars[10].kind).toBe("model");
  });
  it("stara migawka: zdanie o deszczu i temperatura, bez wykresu", () => {
    const m = buildWeatherPanel(legacyConditions())!;
    expect(m.legacy).toBe(true);
    expect(m.headline).toContain("Ostatni większy deszcz");
    expect(m.bars).toEqual([]);
    expect(m.facts.map((f) => f.value)).toEqual(["13,7 °C"]);
  });
  it("brak pliku warunków", () => {
    expect(buildWeatherPanel(null)).toBeNull();
  });
});

describe("pomocnicze", () => {
  it("zakres dni i dni temu", () => {
    expect(dayRangeLabel("2026-09-20", "2026-09-24")).toBe("20–24.09");
    expect(dayRangeLabel("2026-09-20", "2026-09-20")).toBe("20.09");
    expect(dayRangeLabel("2026-09-30", "2026-10-02")).toBe("30.09–2.10");
    expect([0, 1, 6].map(daysAgoLabel)).toEqual(["dziś", "wczoraj", "6 dni temu"]);
    expect(DAY).toBe("2026-09-30");
  });
});
```

Run: `npx vitest run src/domain/weather.test.ts`
Expected: FAIL (brak `buildWeatherPanel`).

- [ ] **Step 2: Implementacja**

Dopisz w `frontend/src/domain/weather.ts` (importy: typy `ConditionsTimeline`, `DailyWeather`, `ForecastUncertainty` z `../data/types`; `dayMonth`, `finite`, `pl` z `./format`):

```ts
export type RainBarKind = "measured" | "model" | "forecast";
export type RainBar = { date: string; mm: number | null; kind: RainBarKind; inWindow: boolean; isToday: boolean };
export type TempPoint = { date: string; tmin: number | null; tmax: number | null };
export type ForecastRow = {
  date: string;
  label: string;
  mm: number | null;
  tmax: number | null;
  tmin: number | null;
  uncertainty: ForecastUncertainty;
};
export type WeatherFact = { label: string; value: string; note: string };
export type WeatherCheck = { label: string; active: boolean };
export type WeatherPanelModel = {
  legacy: boolean;
  headline: string;
  facts: WeatherFact[];
  normalLine: string | null;
  bars: RainBar[];
  temps: TempPoint[];
  optimum: number | null;
  forecast: ForecastRow[];
  checks: WeatherCheck[];
  chartLabel: string;
};

export const WEATHER_NOTE =
  "Słupki: opad dzienny (mediana obszaru). Ciemne — pomiar z radaru IMGW, pośrednie — model bez radaru, jasne — prognoza. " +
  "Wg danych z Bielefeld liczy się deszcz z ok. 3 tygodni wstecz, mniej więcej po równo. " +
  "Pomiar opadu i norma (E-OBS, sieć stacji) to różne źródła — porównanie jest przybliżone.";

export function dayRangeLabel(start: string, end: string): string {
  const [, sm, sd] = start.split("-").map(Number);
  const [, em, ed] = end.split("-").map(Number);
  const two = (n: number) => String(n).padStart(2, "0");
  if (start === end) return `${sd}.${two(sm)}`;
  if (sm === em) return `${sd}–${ed}.${two(em)}`;
  return `${sd}.${two(sm)}–${ed}.${two(em)}`;
}

export function daysAgoLabel(n: number): string {
  return n <= 0 ? "dziś" : n === 1 ? "wczoraj" : `${n} dni temu`;
}

const afterRain = (daysAgo: number) =>
  daysAgo <= 0 ? "Dziś większy deszcz" : daysAgo === 1 ? "1 dzień po większym deszczu" : `${daysAgo} dni po większym deszczu`;

const barKind = (d: DailyWeather): RainBarKind => (d.forecast ? "forecast" : d.radar_share >= 0.5 ? "measured" : "model");

const CHECKS: Record<string, { active: string; quiet: string }> = {
  frost: { active: "Przymrozek", quiet: "bez przymrozku" },
  heat_drought: { active: "Upał bez deszczu", quiet: "bez upału z suszą" },
};

/** Tresc panelu pogody z conditions.json: same fakty; stara migawka = zdanie o deszczu + temperatura. */
export function buildWeatherPanel(c: ConditionsTimeline | null): WeatherPanelModel | null {
  if (!c) return null;
  const today = c.generated_for;
  const t20 = c.days[0]?.components?.tmean20_c;
  const optimum = c.days[0]?.components?.temp_optimum_c;
  const tempFact: WeatherFact | null = finite(t20)
    ? { label: "Temperatura, średnio 20 dni", value: `${pl(t20, 1)} °C`, note: finite(optimum) ? `optimum ok. ${pl(optimum)} °C` : "" }
    : null;
  const r26 = c.rain26;
  if (!c.daily?.length || !r26)
    return {
      legacy: true, headline: c.summary, facts: tempFact ? [tempFact] : [], normalLine: null,
      bars: [], temps: [], optimum: null, forecast: [], checks: [], chartLabel: "",
    };
  const last = c.rains[0] ?? null;
  const lookback = c.lookback_days;
  const rainPart = last
    ? afterRain(last.days_ago)
    : finite(lookback) ? `Brak większego deszczu od ${lookback} dni` : "Brak większego deszczu w ostatnich tygodniach";
  const normal = r26.normal_mm;
  const facts: WeatherFact[] = [
    { label: "Opad, 26 dni", value: `${pl(r26.sum_mm)} mm`, note: finite(normal) ? `norma ${pl(normal)} mm` : "bez normy" },
    last
      ? { label: "Ostatni większy deszcz", value: daysAgoLabel(last.days_ago), note: `${dayRangeLabel(last.start, last.end)} · ${pl(last.rain_mm, 1)} mm` }
      : { label: "Ostatni większy deszcz", value: "brak", note: finite(lookback) ? `od ${lookback} dni` : "" },
  ];
  if (tempFact) facts.push(tempFact);
  const pct = r26.pct;
  const normalLine = finite(pct)
    ? pct >= 0.5
      ? `Więcej deszczu niż w ${Math.round(pct * 100)}% lat 1991–2020 o tej porze (E-OBS).`
      : `Mniej deszczu niż w ${Math.round((1 - pct) * 100)}% lat 1991–2020 o tej porze (E-OBS).`
    : null;
  const uncertaintyOf = (date: string): ForecastUncertainty => c.days.find((d) => d.date === date)?.uncertainty ?? "ok";
  const checks: WeatherCheck[] = (c.warnings ?? []).flatMap((w) => {
    const text = CHECKS[w.type];
    if (!text) return [];
    return [w.dates.length
      ? { label: `${text.active}: ${w.dates.map(dayMonth).join(", ")}`, active: true }
      : { label: text.quiet, active: false }];
  });
  return {
    legacy: false,
    headline: `${rainPart} · ${pl(r26.sum_mm)} mm w 26 dni${finite(normal) ? ` (norma ${pl(normal)})` : ""}`,
    facts,
    normalLine,
    bars: c.daily.map((d) => ({
      date: d.date, mm: d.precip_mm, kind: barKind(d),
      inWindow: d.date >= r26.window_start && d.date <= r26.window_end, isToday: d.date === today,
    })),
    temps: c.daily.map((d) => ({ date: d.date, tmin: d.tmin_c, tmax: d.tmax_c })),
    optimum: finite(optimum) ? optimum : null,
    forecast: c.daily
      .filter((d) => d.date >= today)
      .slice(0, c.horizon_days)
      .map((d, i) => ({ date: d.date, label: dayLabel(d.date, i), mm: d.precip_mm, tmax: d.tmax_c, tmin: d.tmin_c, uncertainty: uncertaintyOf(d.date) })),
    checks,
    chartLabel: `Opad dzienny od ${dayMonth(c.daily[0].date)} do ${dayMonth(c.daily[c.daily.length - 1].date)}; suma z 26 dni ${pl(r26.sum_mm)} mm.`,
  };
}
```

- [ ] **Step 3: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/domain/weather.ts frontend/src/domain/weather.test.ts
git commit -m "Nowy frontend: model panelu pogody (fakty, norma, wykres, prognoza, ostrzezenia)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Stan aplikacji i wczytywanie analiz

**Files:**
- Create: `frontend/src/state/prefs.ts`, `frontend/src/state/store.ts`, `frontend/src/state/loader.ts`
- Test: `frontend/src/state/store.test.ts`, `frontend/src/state/loader.test.ts`

**Interfaces:**
- Consumes: `Analysis`, `StandDetail`, `AccessCollection`, `TripMeta`, `StandFeature` (types); `rankEntries`, `joinRegions`, `pressureSwitchAvailable`, `classifyByPercentile`, `isStandaloneTarget`, `effectiveR`, `ScoreClass` (ranking); `moistureAvailable` (moisture); `ACCESS_LAYERS` (access); `standName`, `tooltipText` (labels); `buildWeatherPanel` (weather); `finite` (format); `loadCore`, `loadBackground`, `loadTrips` (load).
- Produces (`store.ts`): sygnały `analysis`, `details`, `access`, `load`, `trips`, `tripId`, `pressurePref`, `mapModePref`, `layers`, `tab`, `stack`, `mobilePane`, `showSmall`, `standPage`, `fitRequest`, `toast`, `aboutOpen`, `mapStatus`; wyliczane `pressureAvailable`, `pressure`, `moistureOk`, `mapMode`, `ranked`, `rankIndex`, `classById`, `regionViews`, `top`, `selectedStandId`, `activeRegionId`, `start`, `weatherModel`, `regionMarkers`, `standProps`, `selection`, `visibleStands`; akcje `setTab`, `openRegion(id, source)`, `openStand(id, source)`, `back`, `setPressure`, `setMapMode`, `setLayer`, `requestFitAll`, `notify`, `resetView`, `resetStore`; `featuresFor(req)`, `standTooltip(id)`; typy `Tab`, `PanelView`, `MapMode`, `LoadStatus`, `FitRequest`, `StandMapProps`, `RegionMarker`.
- Produces (`loader.ts`): `basePathFor(id)`, `openAnalysis(basePath, id)`, `retry()`, `startApp()`.

- [ ] **Step 1: Testy stanu**

Utwórz `frontend/src/state/store.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "./store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";

beforeEach(() => S.resetStore());

describe("stos nawigacji", () => {
  it("z listy przybliża; z mapy nie przybliża, zastępuje kartę wydzielenia i przełącza telefon na listę", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")] });
    S.mobilePane.value = "map";
    S.openStand("A", "list");
    expect(S.stack.value.map((v) => v.kind)).toEqual(["list", "stand"]);
    expect(S.fitRequest.value?.req).toEqual({ target: "stand", id: "A" });
    const seq = S.fitRequest.value!.seq;
    S.openStand("B", "map");
    expect(S.stack.value).toEqual([{ kind: "list" }, { kind: "stand", standId: "B" }]);
    expect(S.fitRequest.value!.seq).toBe(seq);
    expect(S.mobilePane.value).toBe("list");
  });
  it("wstecz wraca o poziom i nigdy nie usuwa listy", () => {
    S.openRegion("region_1", "list");
    S.openStand("A", "list");
    S.back();
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
    S.back();
    S.back();
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
  it("zmiana zakładki czyści stos", () => {
    S.openStand("A", "list");
    S.setTab("stands");
    expect(S.tab.value).toBe("stands");
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
  it("znacznik rejonu na mapie: zakładka Rejony z kartą rejonu, bez przybliżania", () => {
    S.setTab("stands");
    S.openRegion("region_2", "map");
    expect(S.tab.value).toBe("regions");
    expect(S.stack.value).toEqual([{ kind: "list" }, { kind: "region", regionId: "region_2" }]);
    expect(S.fitRequest.value).toBeNull();
  });
});

describe("presja", () => {
  it("przełączenie zamyka karty rejonów, bo rejony obu wariantów mają te same id", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A", { R: 80, R_bez_presji: 50 }), makeScore("B", { R: 50, R_bez_presji: 80 })],
      regions: [makeRegion("region_1", 70, ["A"])],
      regionsNoPressure: [makeRegion("region_1", 75, ["B"])],
    });
    S.openRegion("region_1", "list");
    S.openStand("A", "list");
    S.setPressure(false);
    expect(S.stack.value.map((v) => v.kind)).toEqual(["list", "stand"]);
    expect(S.regionViews.value[0].members[0].score.stand_id).toBe("B");
  });
  it("ranking i klasy idą za wariantem presji", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A", { R: 80, R_bez_presji: 50 }), makeScore("B", { R: 50, R_bez_presji: 80 })],
      regionsNoPressure: [],
    });
    expect(S.classById.value.get("A")).toBe(1);
    expect(S.classById.value.get("B")).toBe(4);
    S.setPressure(false);
    expect(S.ranked.value[0].score.stand_id).toBe("B");
    expect(S.classById.value.get("A")).toBe(4);
  });
  it("migawka bez wyników bez presji: przełącznik niedostępny, presja zawsze włączona", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.setPressure(false);
    expect(S.pressureAvailable.value).toBe(false);
    expect(S.pressure.value).toBe(true);
  });
});

describe("mapa", () => {
  it("Wilgotność bez M w migawce wraca do Wyniku", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { M: undefined })] });
    S.setMapMode("moisture");
    expect(S.moistureOk.value).toBe(false);
    expect(S.mapMode.value).toBe("score");
  });
  it("właściwości wydzieleń: klasa 0 poza maską, numer rejonu, wilgotność", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A"), makeScore("C", { mask: false, R: 0, M: 0.3, mask_reason: ["too_young"] })],
      regions: [makeRegion("region_1", 70, ["A"])],
    });
    expect(S.standProps.value.get("A")).toEqual({ cls: 1, moisture: 0.8, pressure: 0.2, region: 1 });
    expect(S.standProps.value.get("C")).toEqual({ cls: 0, moisture: 0.3, pressure: 0.2, region: 0 });
    expect(S.regionMarkers.value).toEqual([{ id: "region_1", number: 1, point: [18.41, 50.61] }]);
  });
  it("featuresFor: wydzielenie, rejon, cały obszar", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regions: [makeRegion("region_1", 70, ["B"])] });
    expect(S.featuresFor({ target: "stand", id: "A" })).toHaveLength(1);
    expect(S.featuresFor({ target: "region", id: "region_1" }).map((f) => f.properties.stand_id)).toEqual(["B"]);
    expect(S.featuresFor({ target: "all" })).toHaveLength(2);
  });
  it("dymek: wynik i klasa albo poza filtrami", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { R: 81.2 }), makeScore("C", { mask: false, R: 0 })] });
    expect(S.standTooltip("A")).toMatch(/wynik 81 · najlepsze 5%$/);
    expect(S.standTooltip("C")).toMatch(/poza filtrami modelu$/);
    expect(S.standTooltip("nie-ma")).toBeNull();
  });
});
```

Run: `npx vitest run src/state/store.test.ts`
Expected: FAIL (brak `./store`).

- [ ] **Step 2: `prefs.ts`**

```ts
// Te same klucze co stary interfejs -- zapamietane ustawienia przechodza do nowego.
export const KEYS = {
  pressure: "borowik.pressure.v1",
  mapMode: "borowik.map-color.v1",
  layers: "borowik.access-layers.v1",
  tab: "borowik.view-mode.v1",
} as const;

export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Bez zapisu: ustawienie dziala tylko w tej sesji.
  }
}
```

- [ ] **Step 3: `store.ts`**

```ts
import { batch, computed, signal } from "@preact/signals";
import type { AccessCollection, AccessLayerId, Analysis, StandDetail, StandFeature, TripMeta } from "../data/types";
import { ACCESS_LAYERS } from "../domain/access";
import { finite } from "../domain/format";
import { standName, tooltipText } from "../domain/labels";
import { moistureAvailable } from "../domain/moisture";
import {
  classifyByPercentile, effectiveR, isStandaloneTarget, joinRegions, pressureSwitchAvailable, rankEntries,
  type ScoreClass,
} from "../domain/ranking";
import { buildWeatherPanel } from "../domain/weather";
import { KEYS, readPref, writePref } from "./prefs";

export type Tab = "regions" | "stands";
export type PanelView = { kind: "list" } | { kind: "region"; regionId: string } | { kind: "stand"; standId: string };
export type MapMode = "score" | "moisture";
export type LoadStatus = { status: "loading" } | { status: "ready" } | { status: "error"; message: string };
export type FitRequest = { target: "stand"; id: string } | { target: "region"; id: string } | { target: "all" };
export type StandMapProps = { cls: ScoreClass | 0; moisture: number | null; pressure: number | null; region: number };
export type RegionMarker = { id: string; number: number; point: [number, number] };
type AccessState = { loaded: boolean; points: AccessCollection | null; roads: AccessCollection | null };

function initialLayers(): Record<AccessLayerId, boolean> {
  const state = Object.fromEntries(ACCESS_LAYERS.map((l) => [l.id, l.defaultOn])) as Record<AccessLayerId, boolean>;
  try {
    const saved = JSON.parse(readPref(KEYS.layers) ?? "null");
    if (saved && typeof saved === "object")
      for (const l of ACCESS_LAYERS) if (typeof saved[l.id] === "boolean") state[l.id] = saved[l.id];
  } catch {
    // Uszkodzony zapis: warstwy domyslne.
  }
  return state;
}

export const analysis = signal<Analysis | null>(null);
// null = szczegoly jeszcze sie wczytuja; pusta mapa = brak pliku szczegolow.
export const details = signal<Map<string, StandDetail> | null>(null);
export const access = signal<AccessState>({ loaded: false, points: null, roads: null });
export const load = signal<LoadStatus>({ status: "loading" });
export const trips = signal<TripMeta[]>([]);
export const tripId = signal<string | null>(null);
export const pressurePref = signal(readPref(KEYS.pressure) !== "off");
export const mapModePref = signal<MapMode>(readPref(KEYS.mapMode) === "moisture" ? "moisture" : "score");
export const layers = signal(initialLayers());
export const tab = signal<Tab>(readPref(KEYS.tab) === "stands" ? "stands" : "regions");
export const stack = signal<PanelView[]>([{ kind: "list" }]);
export const mobilePane = signal<"list" | "map">("list");
export const showSmall = signal(false);
export const standPage = signal(1);
export const fitRequest = signal<{ req: FitRequest; seq: number } | null>(null);
export const toast = signal<string | null>(null);
export const aboutOpen = signal(false);
export const mapStatus = signal<string | null>(null);

export const pressureAvailable = computed(() => {
  const a = analysis.value;
  return !!a && pressureSwitchAvailable(a.scores, a.regionsNoPressure);
});
// Migawka bez wynikow bez presji: ranking zawsze z presja (jedyny, jaki jest).
export const pressure = computed(() => (pressureAvailable.value ? pressurePref.value : true));
export const moistureOk = computed(() => !!analysis.value && moistureAvailable(analysis.value.scores));
export const mapMode = computed<MapMode>(() => (mapModePref.value === "moisture" && moistureOk.value ? "moisture" : "score"));
export const ranked = computed(() => (analysis.value ? rankEntries(analysis.value.entries, pressure.value) : []));
export const rankIndex = computed(() => new Map(ranked.value.map((e, i) => [e.score.stand_id, i])));
export const classById = computed(() => {
  const list = ranked.value;
  const classes = classifyByPercentile(list.map((e) => e.r));
  return new Map(list.map((e, i) => [e.score.stand_id, classes[i]]));
});
export const regionViews = computed(() => {
  const a = analysis.value;
  if (!a) return [];
  return joinRegions(pressure.value ? a.regions : (a.regionsNoPressure ?? []), ranked.value);
});
export const top = computed(() => stack.value[stack.value.length - 1]);
export const selectedStandId = computed(() => (top.value.kind === "stand" ? top.value.standId : null));
export const activeRegionId = computed(() => {
  for (let i = stack.value.length - 1; i >= 0; i--) {
    const view = stack.value[i];
    if (view.kind === "region") return view.regionId;
  }
  return null;
});
export const start = computed<[number, number] | null>(() => {
  const m = analysis.value?.manifest;
  return m && m.lat !== null && m.lon !== null ? [m.lon, m.lat] : null;
});
export const weatherModel = computed(() => buildWeatherPanel(analysis.value?.conditions ?? null));
export const regionMarkers = computed<RegionMarker[]>(() =>
  regionViews.value.map((v, i) => ({ id: v.region.region_id, number: i + 1, point: [v.region.centroid_lon, v.region.centroid_lat] })),
);
const regionNumberById = computed(() => {
  const numbers = new Map<string, number>();
  regionViews.value.forEach((v, i) => v.region.stand_ids.forEach((id) => { if (!numbers.has(id)) numbers.set(id, i + 1); }));
  return numbers;
});
export const standProps = computed(() => {
  const props = new Map<string, StandMapProps>();
  const a = analysis.value;
  if (!a) return props;
  for (const s of a.scores)
    props.set(s.stand_id, {
      cls: s.mask ? (classById.value.get(s.stand_id) ?? 4) : 0,
      moisture: finite(s.M) ? s.M : null,
      pressure: finite(s.P) ? s.P : null,
      region: regionNumberById.value.get(s.stand_id) ?? 0,
    });
  return props;
});
export const selection = computed(() => {
  const regionId = activeRegionId.value;
  const view = regionId ? regionViews.value.find((v) => v.region.region_id === regionId) : undefined;
  return { standId: selectedStandId.value, regionStandIds: view ? view.members.map((m) => m.score.stand_id) : [] };
});
export const visibleStands = computed(() => ranked.value.filter((e) => showSmall.value || isStandaloneTarget(e.score)));

let fitSeq = 0;
function requestFit(req: FitRequest): void {
  fitRequest.value = { req, seq: ++fitSeq };
}
export const requestFitAll = () => requestFit({ target: "all" });

export function setTab(next: Tab): void {
  batch(() => {
    tab.value = next;
    stack.value = [{ kind: "list" }];
    standPage.value = 1;
  });
  writePref(KEYS.tab, next);
}

export function openRegion(regionId: string, source: "list" | "map"): void {
  batch(() => {
    if (source === "map") {
      tab.value = "regions";
      stack.value = [{ kind: "list" }, { kind: "region", regionId }];
      mobilePane.value = "list";
    } else stack.value = [...stack.value, { kind: "region", regionId }];
  });
  if (source === "list") requestFit({ target: "region", id: regionId });
}

export function openStand(standId: string, source: "list" | "map"): void {
  const current = stack.value;
  const base = current[current.length - 1].kind === "stand" ? current.slice(0, -1) : current;
  batch(() => {
    stack.value = [...base, { kind: "stand", standId }];
    if (source === "map") mobilePane.value = "list";
  });
  if (source === "list") requestFit({ target: "stand", id: standId });
}

export function back(): void {
  if (stack.value.length > 1) stack.value = stack.value.slice(0, -1);
}

export function setPressure(on: boolean): void {
  batch(() => {
    pressurePref.value = on;
    // Rejony z presja i bez presji maja te same identyfikatory (region_1...), ale to inne rejony --
    // karta rejonu nie moze po przelaczeniu pokazac innego rejonu pod tym samym id.
    const kept = stack.value.filter((v) => v.kind !== "region");
    stack.value = kept.length ? kept : [{ kind: "list" }];
  });
  writePref(KEYS.pressure, on ? "on" : "off");
}

export function setMapMode(mode: MapMode): void {
  mapModePref.value = mode;
  writePref(KEYS.mapMode, mode);
}

export function setLayer(id: AccessLayerId, on: boolean): void {
  layers.value = { ...layers.value, [id]: on };
  writePref(KEYS.layers, JSON.stringify(layers.value));
}

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function notify(message: string): void {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = null;
  }, 4500);
}

export function resetView(): void {
  batch(() => {
    stack.value = [{ kind: "list" }];
    standPage.value = 1;
  });
}

export function featuresFor(req: FitRequest): StandFeature[] {
  const a = analysis.value;
  if (!a) return [];
  if (req.target === "stand") {
    const feature = a.features.get(req.id);
    return feature ? [feature] : [];
  }
  if (req.target === "region") {
    const view = regionViews.value.find((v) => v.region.region_id === req.id);
    return view ? view.members.map((m) => m.feature) : [];
  }
  return ranked.value.length ? ranked.value.map((e) => e.feature) : [...a.features.values()];
}

export function standTooltip(id: string): string | null {
  const a = analysis.value;
  const score = a?.scoreById.get(id);
  if (!a || !score) return null;
  const name = standName(id, details.value?.get(id) ?? null);
  const cls = standProps.value.get(id)?.cls ?? 0;
  return tooltipText(name, cls === 0 ? null : effectiveR(score, pressure.value), cls);
}

// Tylko dla testow: wszystkie sygnaly do stanu poczatkowego (ustawienia z localStorage).
export function resetStore(): void {
  batch(() => {
    analysis.value = null;
    details.value = null;
    access.value = { loaded: false, points: null, roads: null };
    load.value = { status: "loading" };
    trips.value = [];
    tripId.value = null;
    pressurePref.value = readPref(KEYS.pressure) !== "off";
    mapModePref.value = readPref(KEYS.mapMode) === "moisture" ? "moisture" : "score";
    layers.value = initialLayers();
    tab.value = readPref(KEYS.tab) === "stands" ? "stands" : "regions";
    stack.value = [{ kind: "list" }];
    mobilePane.value = "list";
    showSmall.value = false;
    standPage.value = 1;
    fitRequest.value = null;
    toast.value = null;
    aboutOpen.value = false;
    mapStatus.value = null;
  });
}
```

Run: `npx vitest run src/state/store.test.ts`
Expected: PASS.

- [ ] **Step 4: Testy wczytywania**

Utwórz `frontend/src/state/loader.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../data/load", () => ({ loadCore: vi.fn(), loadBackground: vi.fn(), loadTrips: vi.fn(async () => []) }));

import { loadBackground, loadCore, type Background } from "../data/load";
import { openAnalysis, retry } from "./loader";
import * as S from "./store";
import { makeAnalysis, makeDetail, makeScore } from "../test-fixtures";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const background = (id: string): Background => ({ details: new Map([[id, makeDetail(id)]]), accessPoints: null, forestRoads: null });

beforeEach(() => {
  S.resetStore();
  vi.mocked(loadCore).mockReset();
  vi.mocked(loadBackground).mockReset();
});

describe("openAnalysis", () => {
  it("szczegóły poprzedniej analizy nie nadpisują nowej", async () => {
    const first = makeAnalysis({ scores: [makeScore("A")] });
    const second = { ...makeAnalysis({ scores: [makeScore("B")] }), basePath: "data/trips/x/" };
    let releaseFirst: (value: Background) => void = () => {};
    vi.mocked(loadCore).mockResolvedValueOnce(first).mockResolvedValueOnce(second);
    vi.mocked(loadBackground)
      .mockImplementationOnce(() => new Promise((resolve) => { releaseFirst = resolve; }))
      .mockResolvedValueOnce(background("B"));
    await openAnalysis("data/", null);
    await openAnalysis("data/trips/x/", "x");
    await flush();
    releaseFirst(background("A"));
    await flush();
    expect(S.analysis.value?.basePath).toBe("data/trips/x/");
    expect([...S.details.value!.keys()]).toEqual(["B"]);
    expect(S.access.value.loaded).toBe(true);
  });
  it("błąd pokazuje komunikat; ponowna próba wczytuje tę samą analizę", async () => {
    vi.mocked(loadCore).mockRejectedValueOnce(new Error("Nie udało się wczytać scores.json."));
    await openAnalysis("data/trips/x/", "x");
    expect(S.load.value).toEqual({ status: "error", message: "Nie udało się wczytać scores.json." });
    vi.mocked(loadCore).mockResolvedValueOnce(makeAnalysis({ scores: [makeScore("A")] }));
    vi.mocked(loadBackground).mockResolvedValueOnce(background("A"));
    await retry();
    expect(vi.mocked(loadCore).mock.calls[1][0]).toBe("data/trips/x/");
    expect(S.load.value.status).toBe("ready");
  });
  it("zakładka Rejony bez rejonów przechodzi na Wydzielenia; cały obszar do przybliżenia", async () => {
    vi.mocked(loadCore).mockResolvedValueOnce(makeAnalysis({ scores: [makeScore("A")] }));
    vi.mocked(loadBackground).mockResolvedValueOnce(background("A"));
    await openAnalysis("data/", null);
    expect(S.tab.value).toBe("stands");
    expect(S.fitRequest.value?.req).toEqual({ target: "all" });
  });
});
```

Run: `npx vitest run src/state/loader.test.ts`
Expected: FAIL (brak `./loader`).

- [ ] **Step 5: `loader.ts`**

```ts
import { batch } from "@preact/signals";
import { loadBackground, loadCore, loadTrips } from "../data/load";
import type { Analysis } from "../data/types";
import {
  access, analysis, details, load, notify, regionViews, requestFitAll, resetView, tab, tripId, trips,
} from "./store";

let token = 0;

export const basePathFor = (id: string | null) => (id ? `data/trips/${id}/` : "data/");

// Kazde otwarcie dostaje wlasny numer; wynik starszego wczytywania (np. szczegoly w tle)
// jest ignorowany, jesli w miedzyczasie otwarto inna analize.
export async function openAnalysis(basePath: string, id: string | null): Promise<void> {
  const mine = ++token;
  batch(() => {
    load.value = { status: "loading" };
    tripId.value = id;
    details.value = null;
    access.value = { loaded: false, points: null, roads: null };
    resetView();
  });
  let core: Analysis;
  try {
    core = await loadCore(basePath);
  } catch (error) {
    if (mine === token) load.value = { status: "error", message: error instanceof Error ? error.message : String(error) };
    return;
  }
  if (mine !== token) return;
  batch(() => {
    analysis.value = core;
    load.value = { status: "ready" };
    if (tab.value === "regions" && regionViews.value.length === 0) tab.value = "stands";
  });
  requestFitAll();
  loadBackground(core).then(
    (bg) => {
      if (mine !== token) return;
      batch(() => {
        details.value = bg.details;
        access.value = { loaded: true, points: bg.accessPoints, roads: bg.forestRoads };
      });
    },
    (error) => {
      if (mine !== token) return;
      batch(() => {
        details.value = new Map();
        access.value = { loaded: true, points: null, roads: null };
      });
      notify(error instanceof Error ? error.message : "Nie udało się wczytać szczegółów wydzieleń.");
    },
  );
}

export function retry(): Promise<void> {
  return openAnalysis(basePathFor(tripId.value), tripId.value);
}

export async function startApp(): Promise<void> {
  trips.value = await loadTrips();
  await openAnalysis("data/", null);
}
```

- [ ] **Step 6: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/state
git commit -m "Nowy frontend: stan aplikacji (sygnaly), stos nawigacji, wczytywanie analiz z ochrona przed wyscigiem

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Mapa — wyrażenia warstw i nakładka na MapLibre

**Files:**
- Create: `frontend/src/map/layers.ts`, `frontend/src/map/forestMap.ts`
- Test: `frontend/src/map/layers.test.ts`

**Interfaces:**
- Consumes: `StandMapProps`, `RegionMarker` (store, Task 9); `MOISTURE_STOPS`, `MOISTURE_NO_DATA_COLOR` (moisture); `vertices` (geometry); funkcje etykiet dostępu (access).
- Produces (`layers.ts`, bez importu MapLibre w czasie działania): `CLASS_COLORS: Record<ScoreClass, string>`, `OUTSIDE_LINE_COLOR`, `buildStandCollection(features, props)`, `scoreFillColor()`, `scoreFillOpacity()`, `moistureFillColor()`, `moistureFillOpacity()`, `lineColor()`, `lineWidth()`.
- Produces (`forestMap.ts`): `type MapHandlers = { onStandClick(id), onRegionClick(id), onStatus(message), tooltip(id): string | null }`; klasa `ForestMap(container, handlers)` z metodami `setStands(features, props)`, `setMode(mode)`, `setRegions(markers)`, `setSelection({ standId, regionStandIds })`, `setAccessData(points, roads)`, `setLayerVisible(id, visible)`, `fitFeatures(features)`, `resize()`, `destroy()`.

- [ ] **Step 1: Testy wyrażeń**

Utwórz `frontend/src/map/layers.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { CLASS_COLORS, buildStandCollection, moistureFillColor, scoreFillColor } from "./layers";
import { squareFeature } from "../test-fixtures";

describe("warstwy mapy", () => {
  it("łączy geometrię z właściwościami; brak właściwości = poza filtrami", () => {
    const fc = buildStandCollection(
      [squareFeature("A", 0), squareFeature("B", 1)],
      new Map([["A", { cls: 2, moisture: 0.5, pressure: 0.1, region: 3 }]]),
    );
    expect(fc.features[0].properties).toEqual({ stand_id: "A", cls: 2, moisture: 0.5, pressure: 0.1, region: 3 });
    expect(fc.features[1].properties).toEqual({ stand_id: "B", cls: 0, moisture: null, pressure: null, region: 0 });
  });
  it("wynik: cztery kolory klas, poza filtrami przezroczyste", () => {
    const expr = JSON.stringify(scoreFillColor());
    for (const c of [1, 2, 3, 4] as const) expect(expr).toContain(CLASS_COLORS[c]);
    expect(expr).toContain("rgba(0,0,0,0)");
  });
  it("wilgotność: skala bezwzględna i kolor braku danych", () => {
    const expr = JSON.stringify(moistureFillColor());
    expect(expr).toContain("interpolate");
    expect(expr).toContain("#cfd2c6");
  });
});
```

Run: `npx vitest run src/map/layers.test.ts`
Expected: FAIL (brak `./layers`).

- [ ] **Step 2: `layers.ts`**

```ts
import type maplibregl from "maplibre-gl";
import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import type { StandFeature } from "../data/types";
import { MOISTURE_NO_DATA_COLOR, MOISTURE_STOPS } from "../domain/moisture";
import type { ScoreClass } from "../domain/ranking";
import type { StandMapProps } from "../state/store";

type Expr = maplibregl.ExpressionSpecification;

// Kolory klas procentowych (1 = najlepsze 5%); klasa 4 prawie niewidoczna.
export const CLASS_COLORS: Record<ScoreClass, string> = { 1: "#1f5c3a", 2: "#4f8f5c", 3: "#a9cba0", 4: "#dcdcd2" };
export const OUTSIDE_LINE_COLOR = "#aeb5a3";

export function buildStandCollection(
  features: StandFeature[],
  props: Map<string, StandMapProps>,
): FeatureCollection<Polygon | MultiPolygon> {
  return {
    type: "FeatureCollection",
    features: features.map((f) => {
      const p = props.get(f.properties.stand_id);
      return {
        type: "Feature",
        geometry: f.geometry,
        properties: {
          stand_id: f.properties.stand_id,
          cls: p?.cls ?? 0,
          moisture: p?.moisture ?? null,
          pressure: p?.pressure ?? null,
          region: p?.region ?? 0,
        },
      };
    }),
  };
}

export const scoreFillColor = (): Expr =>
  ["match", ["get", "cls"], 1, CLASS_COLORS[1], 2, CLASS_COLORS[2], 3, CLASS_COLORS[3], 4, CLASS_COLORS[4], "rgba(0,0,0,0)"] as unknown as Expr;
export const scoreFillOpacity = (): Expr => ["match", ["get", "cls"], 1, 0.85, 2, 0.8, 3, 0.7, 4, 0.45, 0] as unknown as Expr;
export const moistureFillColor = (): Expr =>
  [
    "case",
    ["==", ["typeof", ["get", "moisture"]], "number"],
    ["interpolate", ["linear"], ["get", "moisture"], ...MOISTURE_STOPS.flat()],
    MOISTURE_NO_DATA_COLOR,
  ] as unknown as Expr;
export const moistureFillOpacity = (): Expr => ["case", [">", ["get", "cls"], 0], 0.8, 0.35] as unknown as Expr;
export const lineColor = (): Expr => ["case", [">", ["get", "cls"], 0], "#fffef5", OUTSIDE_LINE_COLOR] as unknown as Expr;
export const lineWidth = (): Expr => ["case", [">", ["get", "cls"], 0], 0.7, 0.5] as unknown as Expr;
```

Run: `npx vitest run src/map/layers.test.ts`
Expected: PASS.

- [ ] **Step 3: `forestMap.ts`**

Utwórz `frontend/src/map/forestMap.ts`. Z obecnego `frontend/src/map.ts` skopiuj **bez zmian** stałe `ACCESS_LAYER_GROUPS` i `SURFACE_MATCH` oraz metody `showAccessPopup`, `addAccessLayers`, `applyAccessVisibility`, `setAccessData`, `setLayerVisible`, `loadBasemap` (w `loadBasemap` zamień `this.status(` na `this.handlers.onStatus(`). Reszta pliku:

```ts
import maplibregl from "maplibre-gl";
import type { AccessCollection, AccessLayerId, StandFeature } from "../data/types";
import {
  SURFACE_COLORS, attractivenessClass, pointTypeLabel, roadKindLabel, sourceLabel, surfaceLabel,
} from "../domain/access";
import { vertices } from "../domain/geometry";
import type { RegionMarker, StandMapProps } from "../state/store";
import {
  buildStandCollection, lineColor, lineWidth, moistureFillColor, moistureFillOpacity, scoreFillColor, scoreFillOpacity,
} from "./layers";

export type MapHandlers = {
  onStandClick: (id: string) => void;
  onRegionClick: (id: string) => void;
  onStatus: (message: string) => void;
  tooltip: (id: string) => string | null;
};

// ACCESS_LAYER_GROUPS i SURFACE_MATCH: skopiowane z src/map.ts (patrz Step 3).

const ACCESS_CLICK_LAYERS = [
  "ap-parking-bdl", "ap-parking-osm", "ap-entrance", "ap-gate", "ap-settlement", "road-public", "road-closed", "road-fire",
];

export class ForestMap {
  private map: maplibregl.Map;
  private collection = buildStandCollection([], new Map());
  private mode: "score" | "moisture" = "score";
  private selection: { standId: string | null; regionStandIds: string[] } = { standId: null, regionStandIds: [] };
  private markers: maplibregl.Marker[] = [];
  private hover: maplibregl.Popup;
  private accessPoints: AccessCollection | null = null;
  private forestRoads: AccessCollection | null = null;
  private layerVisible: Record<AccessLayerId, boolean> = {
    parkings: true, entrances: true, roads: true, fire: false, settlements: false, pressure: false,
  };

  constructor(container: HTMLElement, private handlers: MapHandlers) {
    this.map = new maplibregl.Map({
      container,
      style: { version: 8, sources: {}, layers: [{ id: "paper", type: "background", paint: { "background-color": "#e7ecdf" } }] },
      center: [17.5, 52.2],
      zoom: 6,
      attributionControl: { compact: true },
    });
    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    this.map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    this.hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "stand-tooltip" });
    // Podklad (setStyle) usuwa nasze zrodla i warstwy -- odtworz je po kazdym zaladowaniu stylu.
    this.map.on("style.load", () => {
      this.addLayers();
      this.applyMode();
      this.applySelection();
    });
    this.map.on("error", () => this.handlers.onStatus("Nie udało się wczytać części mapy. Lista pozostaje dostępna."));
    this.map.on("click", "stand-fill", (event) => {
      const id = event.features?.[0]?.properties?.stand_id;
      if (typeof id === "string") this.handlers.onStandClick(id);
    });
    this.map.on("mousemove", "stand-fill", (event) => {
      this.map.getCanvas().style.cursor = "pointer";
      const id = event.features?.[0]?.properties?.stand_id;
      const text = typeof id === "string" ? this.handlers.tooltip(id) : null;
      if (text) this.hover.setLngLat(event.lngLat).setText(text).addTo(this.map);
    });
    this.map.on("mouseleave", "stand-fill", () => {
      this.map.getCanvas().style.cursor = "";
      this.hover.remove();
    });
    for (const layer of ACCESS_CLICK_LAYERS) this.map.on("click", layer, (event) => this.showAccessPopup(event));
    void this.loadBasemap();
  }

  private addLayers() {
    if (this.map.getSource("stands")) return;
    this.map.addSource("stands", { type: "geojson", data: this.collection, attribution: "Bank Danych o Lasach" });
    this.map.addLayer({ id: "stand-fill", type: "fill", source: "stands", paint: { "fill-color": scoreFillColor(), "fill-opacity": scoreFillOpacity() } });
    this.map.addLayer({ id: "stand-line", type: "line", source: "stands", paint: { "line-color": lineColor(), "line-width": lineWidth() } });
    this.map.addLayer({
      id: "region-outline", type: "line", source: "stands", filter: [">", ["get", "region"], 0],
      paint: { "line-color": "#234b3d", "line-width": 1.6, "line-opacity": 0.85 },
    });
    this.map.addLayer({
      id: "region-selected", type: "line", source: "stands", filter: ["in", ["get", "stand_id"], ["literal", []]],
      paint: { "line-color": "#234b3d", "line-width": 3 },
    });
    this.map.addLayer({
      id: "stand-selected", type: "line", source: "stands", filter: ["==", ["get", "stand_id"], ""],
      paint: { "line-color": "#d35400", "line-width": 3 },
    });
    this.addAccessLayers();
  }

  private applyMode() {
    if (!this.map.getLayer("stand-fill")) return;
    const moisture = this.mode === "moisture";
    this.map.setPaintProperty("stand-fill", "fill-color", moisture ? moistureFillColor() : scoreFillColor());
    this.map.setPaintProperty("stand-fill", "fill-opacity", moisture ? moistureFillOpacity() : scoreFillOpacity());
  }

  private applySelection() {
    if (!this.map.getLayer("stand-selected")) return;
    this.map.setFilter("stand-selected", ["==", ["get", "stand_id"], this.selection.standId ?? ""]);
    this.map.setFilter("region-selected", ["in", ["get", "stand_id"], ["literal", this.selection.regionStandIds]]);
  }

  setStands(features: StandFeature[], props: Map<string, StandMapProps>) {
    this.collection = buildStandCollection(features, props);
    (this.map.getSource("stands") as maplibregl.GeoJSONSource | undefined)?.setData(this.collection);
  }

  setMode(mode: "score" | "moisture") {
    this.mode = mode;
    this.applyMode();
  }

  setSelection(selection: { standId: string | null; regionStandIds: string[] }) {
    this.selection = selection;
    this.applySelection();
  }

  setRegions(regions: RegionMarker[]) {
    for (const marker of this.markers) marker.remove();
    this.markers = regions.map((region) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "region-marker";
      element.textContent = String(region.number);
      element.setAttribute("aria-label", `Rejon ${region.number}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        this.handlers.onRegionClick(region.id);
      });
      return new maplibregl.Marker({ element }).setLngLat(region.point).addTo(this.map);
    });
  }

  fitFeatures(features: StandFeature[], duration = 650) {
    const bounds = new maplibregl.LngLatBounds();
    for (const feature of features) for (const p of vertices(feature)) bounds.extend([p[0], p[1]]);
    if (bounds.isEmpty()) return;
    this.map.fitBounds(bounds, {
      padding: 55,
      maxZoom: 15,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : duration,
    });
  }

  resize() {
    this.map.resize();
  }

  destroy() {
    this.hover.remove();
    for (const marker of this.markers) marker.remove();
    this.map.remove();
  }

  // showAccessPopup, addAccessLayers, applyAccessVisibility, setAccessData, setLayerVisible,
  // loadBasemap: skopiowane z src/map.ts (patrz Step 3).
}
```

(Uwaga: skopiowana `addAccessLayers` dodaje warstwę `stand-pressure` przed `stand-line`, a drogi i punkty przed `stand-selected` — obie warstwy istnieją, więc kolejność się zgadza. Jeśli `tsc` zgłosi nieużyty import `SURFACE_COLORS` lub funkcji etykiet, oznacza to, że któraś ze skopiowanych metod nie została wklejona.)

- [ ] **Step 4: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów. (Klasy z MapLibre nie da się uruchomić w jsdom — działanie mapy sprawdzane w przeglądarce w Task 16.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/map
git commit -m "Nowy frontend: warstwy mapy (klasy procentowe, wilgotnosc, rejony) i nakladka na MapLibre

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Szkielet interfejsu — style, pasek górny, analizy, okno „O danych”, stany

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/layout.css`, `frontend/src/styles/components.css`
- Create: `frontend/src/components/TopBar.tsx`, `AnalysisPicker.tsx`, `AboutDialog.tsx`, `StatusViews.tsx`, `MobileTabs.tsx`
- Test: `frontend/src/components/shell.test.tsx`

**Interfaces:**
- Consumes: store (Task 9), `openAnalysis`, `retry`, `basePathFor` (loader), `analysisLabel`, `formatTripLabel` (labels), `Icon`.
- Produces: komponenty `TopBar`, `AnalysisPicker`, `AboutDialog`, `LoadingState`, `ErrorState({ message })`, `Toast`, `MobileTabs`; wszystkie klasy CSS używane w Task 12–15 (zdefiniowane w `components.css` tego zadania).

- [ ] **Step 1: Style**

Utwórz `frontend/src/styles/tokens.css`:

```css
:root {
  --green-900: #17352b;
  --green-800: #234b3d;
  --green-600: #3e6e57;
  --green-200: #cfe0d4;
  --green-100: #e7efe9;
  --green-50: #f3f7f4;
  --paper: #f6f5f0;
  --surface: #ffffff;
  --line: #dfe3da;
  --text: #1f2a24;
  --muted: #616b65;
  --blue-700: #3f73a3;
  --blue-500: #7d9fbf;
  --blue-200: #c4d6e6;
  --blue-50: #eef4f9;
  --warm-200: #f3d9c4;
  --warm-700: #9a5a22;
  --warn-bg: #fdecea;
  --warn-text: #a93226;
  --ok-bg: #eaf3ea;
  --ok-text: #2d6a3e;
  --accent: #d35400;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 3px rgb(0 0 0 / 12%), 0 6px 18px rgb(0 0 0 / 8%);
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  color-scheme: light;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body { font: 14px/1.45 var(--font); color: var(--text); background: var(--paper); }
button, input, select { font: inherit; color: inherit; }
h1, h2, h3, h4, p, dl, dd, ul, ol { margin: 0; }
ul, ol { padding: 0; list-style: none; }
.icon { width: 18px; height: 18px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

Utwórz `frontend/src/styles/layout.css`:

```css
.app { display: grid; grid-template-rows: 48px minmax(0, 1fr); height: 100vh; height: 100dvh; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 0 16px; background: var(--surface); border-bottom: 1px solid var(--line); min-width: 0; }
.brand { display: flex; align-items: center; gap: 8px; color: var(--green-800); font-weight: 700; font-size: 16px; text-decoration: none; }
.brand .icon { width: 22px; height: 22px; }
.topbar-context { flex: 1; min-width: 0; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.workspace { display: grid; grid-template-columns: 400px minmax(0, 1fr); min-height: 0; }
.sidebar { display: flex; flex-direction: column; gap: 14px; padding: 12px; overflow-y: auto; background: var(--surface); border-right: 1px solid var(--line); min-height: 0; }
.map-area { position: relative; min-height: 0; }
.mobile-tabs { display: none; }
@media (max-width: 799px) {
  .topbar { gap: 8px; padding: 0 10px; }
  .topbar-context { display: none; }
  .workspace { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); }
  .mobile-tabs { display: flex; gap: 4px; padding: 6px 10px; background: var(--surface); border-bottom: 1px solid var(--line); }
  .workspace[data-pane="list"] .map-area { display: none; }
  .workspace[data-pane="map"] .sidebar { display: none; }
  .sidebar { border-right: 0; }
}
```

Utwórz `frontend/src/styles/components.css`:

```css
/* Przyciski i drobne elementy */
.button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 7px 12px; border: 1px solid var(--green-800); border-radius: var(--radius-sm); background: var(--surface); color: var(--green-800); cursor: pointer; text-decoration: none; }
.button.primary { background: var(--green-800); color: #fff; }
.button:hover { filter: brightness(0.95); }
.link-button { display: inline-flex; align-items: center; gap: 6px; padding: 4px 6px; border: 0; background: none; color: var(--green-800); font-weight: 600; cursor: pointer; }
.icon-button { display: inline-grid; place-items: center; width: 30px; height: 30px; border: 0; border-radius: var(--radius-sm); background: none; cursor: pointer; }
.icon-button:hover { background: var(--green-50); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-block; padding: 2px 8px; border-radius: 999px; background: var(--green-50); font-size: 12px; white-space: nowrap; }
.chip.ok { background: var(--ok-bg); color: var(--ok-text); }
.chip.warn { background: var(--warn-bg); color: var(--warn-text); font-weight: 600; }
.chip-class-1 { background: #1f5c3a; color: #fff; }
.chip-class-2 { background: #4f8f5c; color: #fff; }
.chip-class-3 { background: #d6e7d1; }
.chip-class-4 { background: #eeeeea; color: var(--muted); }
.picker { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
.picker select { padding: 4px 8px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); max-width: 260px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }

/* Stany */
.status { display: grid; justify-items: center; gap: 10px; padding: 32px 12px; text-align: center; }
.status-error h2 { font-size: 16px; }
.spinner { width: 28px; height: 28px; border: 3px solid var(--green-100); border-top-color: var(--green-800); border-radius: 50%; animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty { padding: 16px 4px; color: var(--muted); }
.toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); padding: 10px 16px; border-radius: var(--radius); background: var(--green-900); color: #fff; box-shadow: var(--shadow); z-index: 30; }

/* Okno dialogowe */
.overlay { position: fixed; inset: 0; display: grid; place-items: center; padding: 16px; background: rgb(0 0 0 / 35%); z-index: 20; }
.dialog { position: relative; width: min(640px, 100%); max-height: 85vh; overflow-y: auto; padding: 22px; border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); display: grid; gap: 12px; }
.dialog-close { position: absolute; top: 10px; right: 10px; }
.dialog ul { list-style: disc; padding-left: 20px; display: grid; gap: 6px; }
.sources { font-size: 12px; color: var(--muted); }

/* Panel pogody */
.weather { display: grid; gap: 8px; padding: 12px; border-radius: var(--radius); background: var(--green-50); }
.weather-headline { font-size: 15px; font-weight: 700; }
.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.facts > div { padding: 6px 8px; border-radius: var(--radius-sm); background: var(--surface); }
.facts dt { font-size: 11px; color: var(--muted); }
.facts dd { font-weight: 700; }
.facts .fact-note { font-weight: 400; font-size: 11px; color: var(--muted); }
.rain-chart { width: 100%; height: auto; display: block; }
.rain-chart .window { fill: var(--blue-50); }
.rain-chart .bar-measured { fill: var(--blue-700); }
.rain-chart .bar-model { fill: var(--blue-500); }
.rain-chart .bar-forecast { fill: var(--blue-200); }
.rain-chart .dry { fill: #d7dde0; }
.rain-chart .today { stroke: var(--accent); stroke-width: 1.5; }
.rain-chart text { font: 9px var(--font); fill: var(--muted); }
.rain-chart .today-label { fill: var(--accent); }
.rain-chart .temp-band { fill: var(--warm-200); }
.rain-chart .optimum { stroke: var(--warm-700); stroke-dasharray: 3 3; }
.forecast { width: 100%; border-collapse: collapse; font-size: 12px; }
.forecast th, .forecast td { padding: 3px 4px; text-align: center; border-bottom: 1px solid var(--line); }
.forecast thead th { color: var(--muted); font-weight: 500; }
.forecast tr.uncertain { color: var(--muted); }

/* Przełącznik presji i zakładki */
.switch { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--radius); cursor: pointer; }
.switch input { margin-top: 3px; accent-color: var(--green-800); }
.switch-text { display: grid; }
.switch-text small { color: var(--muted); }
.switch.is-disabled { opacity: 0.6; cursor: not-allowed; }
.tabs { display: flex; padding: 3px; border-radius: var(--radius); background: var(--green-100); }
.tabs button { flex: 1; padding: 6px; border: 0; border-radius: var(--radius-sm); background: none; cursor: pointer; }
.tabs button[aria-selected="true"] { background: var(--surface); font-weight: 600; box-shadow: 0 1px 2px rgb(0 0 0 / 10%); }
.mobile-tabs button { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 6px; border: 0; border-radius: var(--radius-sm); background: var(--green-50); cursor: pointer; }
.mobile-tabs button[aria-selected="true"] { background: var(--green-800); color: #fff; }

/* Listy rejonów i wydzieleń */
.rows { display: grid; gap: 4px; }
.row { width: 100%; display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); text-align: left; cursor: pointer; }
.row:hover, .row[aria-current="true"] { border-color: var(--green-800); background: var(--green-50); }
.row-rank { flex: none; display: inline-grid; place-items: center; min-width: 24px; height: 24px; border-radius: 12px; background: var(--green-100); font-size: 12px; font-weight: 700; }
.row-rank.region { background: var(--green-800); color: #fff; }
.row-main { flex: 1; min-width: 0; display: grid; }
.row-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row-meta { font-size: 12px; color: var(--muted); }
.row-score { font-size: 18px; font-weight: 700; color: var(--green-800); }
.more { justify-self: start; }

/* Karty */
.card { display: grid; gap: 14px; }
.back { justify-self: start; }
.card-head { display: flex; align-items: flex-start; gap: 12px; }
.card-head > div:first-child { flex: 1; min-width: 0; }
.card-head h2 { font-size: 17px; }
.score-badge { display: grid; justify-items: end; }
.score-badge strong { font-size: 28px; line-height: 1; color: var(--green-800); }
.score-badge small { color: var(--muted); font-size: 11px; }
.card section { display: grid; gap: 6px; padding-top: 10px; border-top: 1px solid var(--line); }
.card h3 { font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }
.kv { display: grid; gap: 4px; }
.kv > div { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 8px; }
.kv dt { color: var(--muted); }
.mono { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 12px; word-break: break-all; }
.hint { font-size: 12px; color: var(--muted); }
.notice { padding: 10px 12px; border-radius: var(--radius-sm); background: var(--warn-bg); }
.notice ul { list-style: disc; padding-left: 18px; }
.notice-inline { font-size: 12px; color: var(--warn-text); }
.card-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.bars { display: grid; gap: 8px; }
.bar { display: grid; grid-template-columns: 78px minmax(0, 1fr) auto; align-items: center; gap: 4px 8px; }
.bar-label { font-weight: 600; }
.bar-track { height: 8px; border-radius: 4px; background: var(--green-100); overflow: hidden; }
.bar-track i { display: block; height: 100%; border-radius: 4px; background: var(--green-600); }
.bar-weather .bar-track i { background: var(--blue-700); }
.bar-calm .bar-track i { background: #8a6fb0; }
.bar-word { font-size: 12px; color: var(--muted); white-space: nowrap; }
.bar-note { grid-column: 2 / 4; font-size: 12px; color: var(--muted); }
.bar.is-muted { opacity: 0.55; }
.sidebar-note { margin-top: auto; font-size: 12px; color: var(--muted); }

/* Mapa */
.map-stage { position: absolute; inset: 0; }
.map-canvas { position: absolute; inset: 0; }
.map-controls { position: absolute; top: 10px; right: 10px; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; z-index: 5; }
.segmented { display: flex; padding: 2px; border-radius: var(--radius-sm); background: var(--surface); box-shadow: var(--shadow); }
.segmented button { padding: 5px 10px; border: 0; border-radius: 5px; background: none; cursor: pointer; }
.segmented button[aria-pressed="true"] { background: var(--green-800); color: #fff; }
.segmented button:disabled { opacity: 0.45; cursor: not-allowed; }
.map-button { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border: 0; border-radius: var(--radius-sm); background: var(--surface); box-shadow: var(--shadow); cursor: pointer; }
.popover { position: absolute; top: 42px; right: 0; width: 280px; padding: 12px; border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); display: grid; gap: 10px; }
.popover-head { display: flex; align-items: center; justify-content: space-between; }
.layer-list { display: grid; gap: 6px; }
.layer-list label { display: flex; align-items: center; gap: 8px; }
.layer-legend { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
.key { display: inline-flex; align-items: center; gap: 6px; }
.key i { display: inline-block; width: 14px; height: 10px; border-radius: 2px; }
.key i.dot { width: 10px; border-radius: 50%; }
.legend { position: absolute; left: 10px; bottom: 28px; max-width: 280px; padding: 10px 12px; border-radius: var(--radius); background: rgb(255 255 255 / 94%); box-shadow: var(--shadow); display: grid; gap: 6px; font-size: 12px; z-index: 5; }
.legend ul { display: grid; gap: 3px; }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend i { display: inline-block; width: 16px; height: 10px; border-radius: 2px; }
.legend i.outline { border: 1px solid #aeb5a3; }
.legend i.region { border: 2px solid var(--green-800); }
.legend .gradient { height: 10px; border-radius: 3px; }
.legend .ticks { display: flex; justify-content: space-between; color: var(--muted); }
.legend-note { color: var(--muted); }
.map-status { position: absolute; left: 50%; top: 10px; transform: translateX(-50%); padding: 6px 12px; border-radius: var(--radius-sm); background: var(--surface); box-shadow: var(--shadow); font-size: 12px; z-index: 6; }
.region-marker { display: grid; place-items: center; width: 26px; height: 26px; border: 2px solid #fff; border-radius: 50%; background: var(--green-800); color: #fff; font-weight: 700; font-size: 12px; box-shadow: 0 0 0 4px rgb(35 75 61 / 25%); cursor: pointer; }
.stand-tooltip .maplibregl-popup-content { padding: 6px 10px; font: 12px var(--font); }
@media (max-width: 799px) {
  .facts { grid-template-columns: minmax(0, 1fr); }
  .legend { max-width: 220px; }
}
```

- [ ] **Step 2: Testy szkieletu**

Utwórz `frontend/src/components/shell.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../state/loader", () => ({
  openAnalysis: vi.fn(async () => {}),
  retry: vi.fn(async () => {}),
  basePathFor: (id: string | null) => (id ? `data/trips/${id}/` : "data/"),
}));

import { openAnalysis, retry } from "../state/loader";
import * as S from "../state/store";
import { makeAnalysis, makeScore } from "../test-fixtures";
import { AboutDialog } from "./AboutDialog";
import { MobileTabs } from "./MobileTabs";
import { ErrorState } from "./StatusViews";
import { TopBar } from "./TopBar";

const trip = { id: "kieleczka", name: "Kieleczka", radius_km: 20, day: "2026-09-29", lat: 50.5, lon: 18.6, saved_at: "2026-09-29T20:00:00" };

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
  vi.mocked(openAnalysis).mockClear();
});

describe("pasek górny", () => {
  it("opisuje bieżącą analizę", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<TopBar />);
    expect(screen.getByText("Aktualna analiza · 20 km · 30 września 2026")).toBeTruthy();
  });
  it("lista analiz: ukryta bez migawek, wybór otwiera migawkę", () => {
    const { container, rerender } = render(<TopBar />);
    expect(container.querySelector("select")).toBeNull();
    S.trips.value = [trip];
    rerender(<TopBar />);
    fireEvent.change(container.querySelector("select")!, { target: { value: "kieleczka" } });
    expect(openAnalysis).toHaveBeenCalledWith("data/trips/kieleczka/", "kieleczka");
  });
  it("otwiera okno O danych z podziękowaniem za E-OBS", () => {
    render(<><TopBar /><AboutDialog /></>);
    fireEvent.click(screen.getByText("O danych"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(/We acknowledge the E-OBS dataset/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Zamknij"));
    expect(S.aboutOpen.value).toBe(false);
  });
});

describe("stany i zakładki telefonu", () => {
  it("błąd z ponowną próbą", () => {
    render(<ErrorState message="Nie udało się wczytać scores.json." />);
    expect(screen.getByRole("alert").textContent).toContain("scores.json");
    fireEvent.click(screen.getByText("Spróbuj ponownie"));
    expect(retry).toHaveBeenCalled();
  });
  it("przełącza listę i mapę", () => {
    render(<MobileTabs />);
    fireEvent.click(screen.getByText("Mapa"));
    expect(S.mobilePane.value).toBe("map");
  });
});
```

Run: `npx vitest run src/components/shell.test.tsx`
Expected: FAIL (brak komponentów).

- [ ] **Step 3: Komponenty**

`frontend/src/components/AnalysisPicker.tsx`:

```tsx
import { formatTripLabel } from "../domain/labels";
import { basePathFor, openAnalysis } from "../state/loader";
import { tripId, trips } from "../state/store";

export function AnalysisPicker() {
  if (!trips.value.length) return null;
  return (
    <label class="picker">
      <span>Analiza</span>
      <select
        value={tripId.value ?? ""}
        onChange={(event) => {
          const id = (event.currentTarget as HTMLSelectElement).value || null;
          void openAnalysis(basePathFor(id), id);
        }}
      >
        <option value="">Aktualna</option>
        {trips.value.map((t) => (
          <option key={t.id} value={t.id}>{formatTripLabel(t)}</option>
        ))}
      </select>
    </label>
  );
}
```

`frontend/src/components/TopBar.tsx`:

```tsx
import { analysisLabel } from "../domain/labels";
import { aboutOpen, analysis, tripId, trips } from "../state/store";
import { AnalysisPicker } from "./AnalysisPicker";
import { Icon } from "./icons";

export function TopBar() {
  const a = analysis.value;
  const trip = trips.value.find((t) => t.id === tripId.value) ?? null;
  const label = a
    ? analysisLabel({ tripName: trip?.name ?? null, radiusKm: a.manifest.radius_km ?? trip?.radius_km ?? null, day: a.day || null })
    : "Wczytywanie analizy…";
  return (
    <header class="topbar">
      <a class="brand" href="./"><Icon name="mushroom" /><span>Borowik</span></a>
      <p class="topbar-context">{label}</p>
      <AnalysisPicker />
      <button type="button" class="link-button" onClick={() => { aboutOpen.value = true; }}>
        <Icon name="info" />O danych
      </button>
    </header>
  );
}
```

`frontend/src/components/AboutDialog.tsx`:

```tsx
import { aboutOpen } from "../state/store";
import { Icon } from "./icons";

const close = () => { aboutOpen.value = false; };

export function AboutDialog() {
  if (!aboutOpen.value) return null;
  return (
    <div class="overlay" onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="about-title">
        <button type="button" class="icon-button dialog-close" aria-label="Zamknij" onClick={close}><Icon name="close" /></button>
        <h2 id="about-title">O danych i ograniczeniach</h2>
        <p>
          Borowik porównuje lasy w wybranym promieniu: siedlisko (skład drzew, typ siedliska), pogodę i to, ilu innych
          grzybiarzy można spotkać. To model ekspercki, nieskalibrowany na danych z terenu. Wynik porównuje miejsca w tej
          analizie i nie jest prawdopodobieństwem znalezienia grzybów.
        </p>
        <ul>
          <li>Klasy na mapie to procent najlepszych wydzieleń w tej analizie (najlepsze 5%, 5–20%, 20–50%) — te same co w eksporcie na telefon.</li>
          <li>Panel pogody pokazuje fakty: dzienny opad (radar IMGW scalony z modelem, prognoza Open-Meteo), sumę z 26 dni i normę z E-OBS 1991–2020. Pomiar i norma pochodzą z różnych źródeł, więc porównanie jest przybliżone.</li>
          <li>Wilgotność na mapie to składnik modelu; w obecnym modelu najmocniej liczy się ostatni deszcz, a dane z Bielefeld wskazują, że deszcz działa mniej więcej równo przez ok. 3 tygodnie.</li>
          <li>„Nawiguj” prowadzi do środka wydzielenia lub rejonu, nie do parkingu ani wejścia do lasu.</li>
          <li>Rezerwaty i parki narodowe są wykluczone; okresowe zakazy wstępu sprawdzane są tylko dla najlepszych wydzieleń, na dzień przygotowania analizy.</li>
        </ul>
        <p class="sources">
          Źródła: <a href="https://www.bdl.lasy.gov.pl/" target="_blank" rel="noopener noreferrer">Bank Danych o Lasach</a>,{" "}
          <a href="https://danepubliczne.imgw.pl/" target="_blank" rel="noopener noreferrer">IMGW-PIB (radar RainGRS)</a>,{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>,{" "}
          <a href="https://surfobs.climate.copernicus.eu/" target="_blank" rel="noopener noreferrer">E-OBS</a>, GDOŚ,{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>; podkład{" "}
          <a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a>.
        </p>
        <p class="sources" lang="en">
          {"We acknowledge the E-OBS dataset from the EU-FP6 project UERRA (https://www.uerra.eu) and the Copernicus Climate Change Service, and the data providers in the ECA&D project (https://www.ecad.eu)."}
        </p>
        <p class="sources" lang="en">
          Cornes, R., G. van der Schrier, E.J.M. van den Besselaar, P.D. Jones (2018): An Ensemble Version of the E-OBS
          Temperature and Precipitation Datasets. J. Geophys. Res. Atmos., 123. doi:10.1029/2017JD028200.
        </p>
      </div>
    </div>
  );
}
```

`frontend/src/components/StatusViews.tsx`:

```tsx
import { retry } from "../state/loader";
import { toast } from "../state/store";

export function LoadingState() {
  return (
    <div class="status" role="status">
      <span class="spinner" aria-hidden="true" />
      <p>Wczytuję analizę…</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div class="status status-error" role="alert">
      <h2>Nie udało się wczytać analizy</h2>
      <p>{message}</p>
      <button type="button" class="button primary" onClick={() => void retry()}>Spróbuj ponownie</button>
    </div>
  );
}

export function Toast() {
  return toast.value ? <div class="toast" role="status">{toast.value}</div> : null;
}
```

`frontend/src/components/MobileTabs.tsx`:

```tsx
import { mobilePane } from "../state/store";
import { Icon } from "./icons";

export function MobileTabs() {
  return (
    <div class="mobile-tabs" role="tablist" aria-label="Widok">
      <button type="button" role="tab" aria-selected={mobilePane.value === "list"} onClick={() => { mobilePane.value = "list"; }}>
        <Icon name="list" />Lista
      </button>
      <button type="button" role="tab" aria-selected={mobilePane.value === "map"} onClick={() => { mobilePane.value = "map"; }}>
        <Icon name="map" />Mapa
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles frontend/src/components
git commit -m "Nowy frontend: style, pasek gorny z lista analiz, okno O danych (z podziekowaniem E-OBS), stany

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Panel pogody i wykres opadu

**Files:**
- Create: `frontend/src/components/WeatherPanel.tsx`, `frontend/src/components/RainChart.tsx`
- Test: `frontend/src/components/weather.test.tsx`

**Interfaces:**
- Consumes: `weatherModel` (store), `WeatherPanelModel`, `WEATHER_NOTE` (weather), `dayMonth`, `pl` (format).
- Produces: `WeatherPanel()`, `RainChart({ model, expanded })`.

- [ ] **Step 1: Testy**

Utwórz `frontend/src/components/weather.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { legacyConditions, makeAnalysis, makeConditions, makeScore } from "../test-fixtures";
import { WeatherPanel } from "./WeatherPanel";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("panel pogody", () => {
  it("nowa analiza: nagłówek, liczby, norma, wykres; szczegóły po rozwinięciu", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], conditions: makeConditions() });
    const { container } = render(<WeatherPanel />);
    expect(screen.getByText("6 dni po większym deszczu · 60 mm w 26 dni (norma 48)")).toBeTruthy();
    expect(screen.getByText("Więcej deszczu niż w 71% lat 1991–2020 o tej porze (E-OBS).")).toBeTruthy();
    expect(container.querySelectorAll(".rain-chart rect[class^='bar-']")).toHaveLength(42);
    expect(container.querySelector(".forecast")).toBeNull();
    fireEvent.click(screen.getByText("Szczegóły: temperatura, prognoza"));
    expect(container.querySelectorAll(".forecast tbody tr")).toHaveLength(7);
    expect(container.querySelector(".temp-band")).not.toBeNull();
    expect(screen.getByText("bez przymrozku")).toBeTruthy();
  });
  it("ostrzeżenie widać też po zwinięciu", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A")],
      conditions: makeConditions({ warnings: [{ type: "frost", dates: ["2026-10-04"] }, { type: "heat_drought", dates: [] }] }),
    });
    render(<WeatherPanel />);
    expect(screen.getByText("Przymrozek: 4.10")).toBeTruthy();
  });
  it("stara migawka: zdanie o deszczu, bez wykresu i bez rozwijania", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], conditions: legacyConditions() });
    const { container } = render(<WeatherPanel />);
    expect(screen.getByText(/Ostatni większy deszcz: 20–24.09/)).toBeTruthy();
    expect(container.querySelector(".rain-chart")).toBeNull();
    expect(screen.queryByText("Szczegóły: temperatura, prognoza")).toBeNull();
  });
  it("bez pliku warunków nic nie pokazuje", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    const { container } = render(<WeatherPanel />);
    expect(container.innerHTML).toBe("");
  });
});
```

Run: `npx vitest run src/components/weather.test.tsx`
Expected: FAIL (brak komponentów).

- [ ] **Step 2: `RainChart.tsx`**

```tsx
import { dayMonth, pl } from "../domain/format";
import type { WeatherPanelModel } from "../domain/weather";

const WIDTH = 360;
const TOP = 12;
const BARS = 64;
const AXIS = 14;
const TEMP = 56;

export function RainChart({ model, expanded }: { model: WeatherPanelModel; expanded: boolean }) {
  const n = model.bars.length;
  if (!n) return null;
  const bw = WIDTH / n;
  const maxMm = Math.max(10, ...model.bars.map((b) => b.mm ?? 0));
  const first = model.bars.findIndex((b) => b.inWindow);
  const last = n - 1 - [...model.bars].reverse().findIndex((b) => b.inWindow);
  const todayIndex = model.bars.findIndex((b) => b.isToday);
  const temps = model.temps.filter((t) => t.tmin !== null && t.tmax !== null);
  const showTemp = expanded && temps.length > 1;
  const height = TOP + BARS + AXIS + (showTemp ? TEMP + 6 : 0);
  const labels: [number, string][] = [[0, dayMonth(model.bars[0].date)], [n - 1, dayMonth(model.bars[n - 1].date)]];
  if (first > 0) labels.push([first, dayMonth(model.bars[first].date)]);
  return (
    <svg class="rain-chart" viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={model.chartLabel}>
      {first >= 0 && <rect class="window" x={first * bw} y={0} width={(last - first + 1) * bw} height={TOP + BARS} />}
      {first >= 0 && <text x={first * bw + 3} y={9}>okno 26 dni</text>}
      {model.bars.map((b, i) => {
        const mm = b.mm ?? 0;
        const h = mm > 0 ? Math.max(1.5, (mm / maxMm) * BARS) : 1.5;
        const suffix = b.kind === "forecast" ? " (prognoza)" : b.kind === "model" ? " (model, bez radaru)" : "";
        return (
          <rect class={`bar-${b.kind}${mm > 0 ? "" : " dry"}`} x={i * bw + 0.8} y={TOP + BARS - h} width={Math.max(1, bw - 1.6)} height={h} rx={1}>
            <title>{`${dayMonth(b.date)}: ${b.mm === null ? "brak danych" : `${pl(b.mm, 1)} mm`}${suffix}`}</title>
          </rect>
        );
      })}
      {todayIndex >= 0 && (
        <>
          <line class="today" x1={(todayIndex + 1) * bw} x2={(todayIndex + 1) * bw} y1={0} y2={TOP + BARS + 4} />
          <text class="today-label" x={(todayIndex + 1) * bw + 2} y={9}>dziś</text>
        </>
      )}
      {labels.map(([i, text]) => (
        <text x={i * bw + bw / 2} y={TOP + BARS + 11} text-anchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>{text}</text>
      ))}
      {showTemp && <TempBand model={model} bw={bw} top={TOP + BARS + AXIS + 6} />}
    </svg>
  );
}

function TempBand({ model, bw, top }: { model: WeatherPanelModel; bw: number; top: number }) {
  const values = model.temps.flatMap((t) => [t.tmin, t.tmax]).filter((v): v is number => v !== null);
  const lo = Math.min(...values, model.optimum ?? Infinity) - 1;
  const hi = Math.max(...values, model.optimum ?? -Infinity) + 1;
  const y = (t: number) => top + TEMP - ((t - lo) / (hi - lo)) * TEMP;
  const upper = model.temps.flatMap((t, i) => (t.tmax === null ? [] : [`${i * bw + bw / 2},${y(t.tmax)}`]));
  const lower = model.temps.flatMap((t, i) => (t.tmin === null ? [] : [`${i * bw + bw / 2},${y(t.tmin)}`])).reverse();
  return (
    <>
      <polygon class="temp-band" points={[...upper, ...lower].join(" ")} />
      {model.optimum !== null && (
        <>
          <line class="optimum" x1={0} x2={WIDTH} y1={y(model.optimum)} y2={y(model.optimum)} />
          <text x={2} y={y(model.optimum) - 2}>{`${pl(model.optimum)} °C`}</text>
        </>
      )}
      <text x={WIDTH - 2} y={top + 8} text-anchor="end">temp. min.–maks.</text>
    </>
  );
}
```

(Jeśli typy Preact nie przyjmą atrybutu `text-anchor`, użyj `textAnchor` — Preact przekazuje nazwy atrybutów SVG bez zamiany, więc w przeglądarce sprawdź, czy etykiety są wyrównane; poprawna jest ta forma, która daje w DOM atrybut `text-anchor`.)

- [ ] **Step 3: `WeatherPanel.tsx`**

```tsx
import { useState } from "preact/hooks";
import { pl } from "../domain/format";
import { WEATHER_NOTE, type WeatherPanelModel } from "../domain/weather";
import { weatherModel } from "../state/store";
import { RainChart } from "./RainChart";

const mm = (v: number | null) => (v === null ? "—" : v === 0 ? "0" : `${pl(v, 1)} mm`);
const temp = (v: number | null) => (v === null ? "—" : `${pl(v)}°`);

function Details({ model }: { model: WeatherPanelModel }) {
  const uncertain = model.forecast.some((r) => r.uncertainty !== "ok");
  return (
    <div class="weather-details">
      {model.forecast.length > 0 && (
        <table class="forecast">
          <thead>
            <tr><th scope="col">Dzień</th><th scope="col">Opad</th><th scope="col">Maks.</th><th scope="col">Min.</th></tr>
          </thead>
          <tbody>
            {model.forecast.map((r) => (
              <tr class={r.uncertainty !== "ok" ? "uncertain" : undefined}>
                <th scope="row">{r.label}{r.uncertainty === "uncertain" ? " ?" : r.uncertainty === "indicative" ? " ~" : ""}</th>
                <td>{mm(r.mm)}</td>
                <td>{temp(r.tmax)}</td>
                <td>{temp(r.tmin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {uncertain && <p class="muted small">? prognoza niepewna · ~ orientacyjnie</p>}
      <p class="muted small">{WEATHER_NOTE}</p>
    </div>
  );
}

export function WeatherPanel() {
  const [open, setOpen] = useState(false);
  const model = weatherModel.value;
  if (!model) return null;
  const activeChecks = model.checks.filter((c) => c.active);
  const checks = open ? model.checks : activeChecks;
  return (
    <section class="weather" aria-label="Pogoda">
      <h2 class="weather-headline">{model.headline}</h2>
      {model.facts.length > 0 && (
        <dl class="facts">
          {model.facts.map((f) => (
            <div>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
              {f.note && <dd class="fact-note">{f.note}</dd>}
            </div>
          ))}
        </dl>
      )}
      {model.normalLine && <p class="muted small">{model.normalLine}</p>}
      {checks.length > 0 && (
        <ul class="chips">
          {checks.map((c) => <li class={`chip ${c.active ? "warn" : "ok"}`}>{c.label}</li>)}
        </ul>
      )}
      <RainChart model={model} expanded={open} />
      {open && <Details model={model} />}
      {!model.legacy && (
        <button type="button" class="link-button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Zwiń" : "Szczegóły: temperatura, prognoza"}
        </button>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/WeatherPanel.tsx frontend/src/components/RainChart.tsx frontend/src/components/weather.test.tsx
git commit -m "Nowy frontend: panel pogody z wykresem opadu, norma, ostrzezeniami i prognoza

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Przełącznik presji, zakładki i listy

**Files:**
- Create: `frontend/src/components/PressureToggle.tsx`, `Tabs.tsx`, `StandRow.tsx`, `RegionList.tsx`, `StandList.tsx`
- Test: `frontend/src/components/lists.test.tsx`

**Interfaces:**
- Consumes: store (`pressure`, `pressureAvailable`, `setPressure`, `tab`, `setTab`, `regionViews`, `ranked`, `rankIndex`, `classById`, `visibleStands`, `showSmall`, `standPage`, `start`, `details`, `selectedStandId`, `openRegion`, `openStand`); `CLASS_LABELS`, `regionAreaHa` (ranking); `standName`, `regionName` (labels); `areaLabel`, `startDistanceLabel`, `joinMeta` (format).
- Produces: `PressureToggle()`, `Tabs()`, `StandRow({ entry, rank, onOpen })`, `RegionList()`, `StandList()`; stała `STAND_PAGE_SIZE = 50` (w `StandList.tsx`).

- [ ] **Step 1: Testy**

Utwórz `frontend/src/components/lists.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";
import { PressureToggle } from "./PressureToggle";
import { RegionList } from "./RegionList";
import { StandList } from "./StandList";
import { Tabs } from "./Tabs";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("przełącznik presji", () => {
  it("niedostępny w migawce bez wyników bez presji", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<PressureToggle />);
    expect((screen.getByRole("switch") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText(/starszy eksport/)).toBeTruthy();
  });
  it("wyłączenie zapisuje wybór i przelicza ranking", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regionsNoPressure: [] });
    render(<PressureToggle />);
    fireEvent.click(screen.getByRole("switch"));
    expect(S.pressure.value).toBe(false);
    expect(localStorage.getItem("borowik.pressure.v1")).toBe("off");
  });
});

describe("zakładki i listy", () => {
  it("zakładki pokazują liczebność i przełączają widok", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regions: [makeRegion("region_1", 70, ["A"])] });
    render(<Tabs />);
    expect(screen.getByText("Rejony (1)")).toBeTruthy();
    fireEvent.click(screen.getByText("Wydzielenia (2)"));
    expect(S.tab.value).toBe("stands");
  });
  it("lista rejonów: nazwa, wynik, klik otwiera kartę rejonu", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 76.4, ["A"])] });
    render(<RegionList />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    expect(screen.getByText("76")).toBeTruthy();
    fireEvent.click(screen.getByText("Rejon 1 · Łaziska"));
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
  });
  it("lista rejonów bez rejonów podpowiada zakładkę Wydzielenia", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<RegionList />);
    expect(screen.getByText(/nie ma rejonów/)).toBeTruthy();
  });
  it("lista wydzieleń: małe ukryte do zaznaczenia, klasa, stronicowanie po 50", () => {
    const scores = Array.from({ length: 60 }, (_, i) => makeScore(`S${String(i).padStart(2, "0")}`, { R: 90 - i * 0.5, area_ha: i === 0 ? 0.2 : 2 }));
    S.analysis.value = makeAnalysis({ scores });
    const { container } = render(<StandList />);
    expect(container.querySelectorAll(".rows li")).toHaveLength(50);
    expect(container.textContent).not.toContain("Oddz.") ; // identyfikatory testowe nie maja adresu lesnego
    expect(screen.getByText(/mniejsze niż 0,5 ha \(1\)/)).toBeTruthy();
    fireEvent.click(screen.getByText("Pokaż więcej (9)"));
    expect(container.querySelectorAll(".rows li")).toHaveLength(59);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(container.querySelectorAll(".rows li")).toHaveLength(50);
    fireEvent.click(container.querySelector(".rows .row")!);
    expect(S.top.value.kind).toBe("stand");
  });
});
```

Run: `npx vitest run src/components/lists.test.tsx`
Expected: FAIL (brak komponentów).

- [ ] **Step 2: Komponenty**

`frontend/src/components/PressureToggle.tsx`:

```tsx
import { pressure, pressureAvailable, setPressure } from "../state/store";

export function PressureToggle() {
  const available = pressureAvailable.value;
  const on = pressure.value;
  const hint = !available
    ? "Niedostępne w tej migawce — starszy eksport nie ma wyników bez presji."
    : on
      ? "Ranking uwzględnia, ilu innych grzybiarzy można spotkać."
      : "Ranking tylko z siedliska i pogody.";
  return (
    <label class={`switch${available ? "" : " is-disabled"}`}>
      <input
        type="checkbox"
        role="switch"
        checked={on}
        disabled={!available}
        onChange={(event) => setPressure((event.currentTarget as HTMLInputElement).checked)}
      />
      <span class="switch-text">
        <strong>Uwzględniaj presję grzybiarzy</strong>
        <small>{hint}</small>
      </span>
    </label>
  );
}
```

`frontend/src/components/Tabs.tsx`:

```tsx
import { ranked, regionViews, setTab, tab } from "../state/store";

export function Tabs() {
  return (
    <div class="tabs" role="tablist" aria-label="Lista">
      <button type="button" role="tab" aria-selected={tab.value === "regions"} onClick={() => setTab("regions")}>
        Rejony ({regionViews.value.length})
      </button>
      <button type="button" role="tab" aria-selected={tab.value === "stands"} onClick={() => setTab("stands")}>
        Wydzielenia ({ranked.value.length.toLocaleString("pl-PL")})
      </button>
    </div>
  );
}
```

(Uwaga: `toLocaleString("pl-PL")` rozdziela tysiące twardą spacją — test używa 2 wydzieleń, więc „(2)”.)

`frontend/src/components/StandRow.tsx`:

```tsx
import type { StandView } from "../data/types";
import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { standName } from "../domain/labels";
import { CLASS_LABELS } from "../domain/ranking";
import { classById, details, selectedStandId, start } from "../state/store";

export function StandRow({ entry, rank, onOpen }: { entry: StandView; rank: number; onOpen: () => void }) {
  const id = entry.score.stand_id;
  const cls = classById.value.get(id) ?? 4;
  return (
    <li>
      <button type="button" class="row" onClick={onOpen} aria-current={selectedStandId.value === id ? "true" : undefined}>
        <span class="row-rank">{rank}</span>
        <span class="row-main">
          <span class="row-name">{standName(id, details.value?.get(id) ?? null)}</span>
          <span class="row-meta">{joinMeta([areaLabel(entry.score.area_ha), startDistanceLabel(start.value, entry.point)])}</span>
        </span>
        <span class={`chip chip-class-${cls}`}>{CLASS_LABELS[cls]}</span>
        <span class="row-score">{Math.round(entry.r)}</span>
      </button>
    </li>
  );
}
```

`frontend/src/components/RegionList.tsx`:

```tsx
import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { regionName } from "../domain/labels";
import { regionAreaHa } from "../domain/ranking";
import { openRegion, regionViews, start } from "../state/store";

export function RegionList() {
  const views = regionViews.value;
  if (!views.length)
    return <p class="empty">W tej analizie nie ma rejonów. Zobacz zakładkę „Wydzielenia”.</p>;
  return (
    <ol class="rows" aria-label="Rejony">
      {views.map((v, i) => (
        <li key={v.region.region_id}>
          <button type="button" class="row" onClick={() => openRegion(v.region.region_id, "list")}>
            <span class="row-rank region">{i + 1}</span>
            <span class="row-main">
              <span class="row-name">{regionName(v.region, i + 1)}</span>
              <span class="row-meta">
                {joinMeta([
                  `${v.members.length} wydz.`,
                  areaLabel(regionAreaHa(v)),
                  startDistanceLabel(start.value, [v.region.centroid_lon, v.region.centroid_lat]),
                ])}
              </span>
            </span>
            <span class="row-score">{Math.round(v.region.rank_score)}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
```

`frontend/src/components/StandList.tsx`:

```tsx
import { openStand, rankIndex, ranked, showSmall, standPage, visibleStands } from "../state/store";
import { StandRow } from "./StandRow";

export const STAND_PAGE_SIZE = 50;

export function StandList() {
  const list = visibleStands.value;
  const shown = list.slice(0, standPage.value * STAND_PAGE_SIZE);
  const hiddenSmall = ranked.value.length - list.length;
  return (
    <section class="rows-section" aria-label="Wydzielenia">
      <label class="check">
        <input
          type="checkbox"
          checked={showSmall.value}
          onChange={(event) => {
            showSmall.value = (event.currentTarget as HTMLInputElement).checked;
            standPage.value = 1;
          }}
        />
        Pokaż też wydzielenia mniejsze niż 0,5 ha{!showSmall.value && hiddenSmall > 0 ? ` (${hiddenSmall})` : ""}
      </label>
      {list.length === 0 ? (
        <p class="empty">Brak wydzieleń spełniających filtry modelu w tej analizie.</p>
      ) : (
        <ol class="rows">
          {shown.map((e) => (
            <StandRow
              key={e.score.stand_id}
              entry={e}
              rank={(rankIndex.value.get(e.score.stand_id) ?? 0) + 1}
              onOpen={() => openStand(e.score.stand_id, "list")}
            />
          ))}
        </ol>
      )}
      {shown.length < list.length && (
        <button type="button" class="button more" onClick={() => { standPage.value += 1; }}>
          Pokaż więcej ({list.length - shown.length})
        </button>
      )}
    </section>
  );
}
```

Dopisz w `frontend/src/styles/components.css` (sekcja „Listy”): `.rows-section { display: grid; gap: 8px; }`.

- [ ] **Step 3: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

(Test „lista wydzieleń”: 60 wydzieleń, jedno 0,2 ha ukryte → 59 widocznych; pierwsza strona 50, „Pokaż więcej (9)”, po zaznaczeniu małych strona wraca do 50 z 60.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PressureToggle.tsx frontend/src/components/Tabs.tsx frontend/src/components/StandRow.tsx frontend/src/components/RegionList.tsx frontend/src/components/StandList.tsx frontend/src/components/lists.test.tsx frontend/src/styles/components.css
git commit -m "Nowy frontend: przelacznik presji, zakladki, listy rejonow i wydzielen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Karty rejonu i wydzielenia, panel boczny

**Files:**
- Create: `frontend/src/components/ScoreBars.tsx`, `CardParts.tsx`, `RegionCard.tsx`, `StandCard.tsx`, `Sidebar.tsx`
- Test: `frontend/src/components/cards.test.tsx`

**Interfaces:**
- Consumes: store; `scoreBars`, `regionBars`, `barNotes`, `Bar`, `BarNotes` (bars); `regionAccessSummary`, `keyFacts`, `topPointSummary` (access); `standName`, `regionName`, `maskReasonTexts`, `yearsLabel`, `densityLabel`, `neighborsSummary`, `zakazNote`, `parseStandId`, `formatDateLong` (labels); `effectiveR`, `regionAreaHa` (ranking); `standCentroid` (geometry); `navigationUrl`, `areaLabel`, `startDistanceLabel`, `joinMeta`, `formatValue`, `finite` (format); komponenty z Task 11–13.
- Produces: `ScoreBars({ bars, notes? })`, `BackButton()`, `ScoreBadge({ value, label })`, `CardActions({ point, label })`, `RegionCard({ regionId })`, `StandCard({ standId })`, `Sidebar()`.

- [ ] **Step 1: Testy**

Utwórz `frontend/src/components/cards.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { makeAnalysis, makeDetail, makeRegion, makeScore } from "../test-fixtures";
import { RegionCard } from "./RegionCard";
import { Sidebar } from "./Sidebar";
import { StandCard } from "./StandCard";

const ID = "02-14-3-11-96    -a   -00@2026";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("karta wydzielenia", () => {
  it("w modelu: nazwa, miejsce w rankingu, wynik, paski z opisami, drzewostan, dojazd, dane", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID, { R: 81.1 }), makeScore("B", { R: 40 })], regionsNoPressure: [] });
    S.details.value = new Map([[ID, makeDetail(ID)]]);
    S.stack.value = [{ kind: "list" }, { kind: "stand", standId: ID }];
    const { container } = render(<StandCard standId={ID} />);
    expect(screen.getByText("Oddz. 96a · Nadl. Zawadzkie")).toBeTruthy();
    expect(container.textContent).toContain("#1 z 2");
    expect(container.querySelector(".score-badge strong")?.textContent).toBe("81");
    expect(screen.getByText("sosna 100% · Bór mieszany świeży · 64 lata")).toBeTruthy();
    expect(screen.getByText("Bór mieszany świeży (BMSW)")).toBeTruthy();
    expect(screen.getByText("parking 2,4 km")).toBeTruthy();
    expect(container.textContent).toContain("leśnictwo 3 · oddział 96 · pododdział a");
    expect(screen.getByRole("link", { name: /Nawiguj/ }).getAttribute("href")).toMatch(/^https:\/\/www\.google\.com\/maps\?q=/);
  });
  it("szczegóły jeszcze się wczytują", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID)] });
    render(<StandCard standId={ID} />);
    expect(screen.getAllByText("Wczytuję szczegóły…").length).toBeGreaterThan(0);
  });
  it("poza filtrami: powody zamiast pasków", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("C", { mask: false, R: 0, mask_reason: ["too_young", "gdos"] })] });
    S.details.value = new Map();
    const { container } = render(<StandCard standId="C" />);
    expect(screen.getByText("Nie spełnia filtrów modelu")).toBeTruthy();
    expect(screen.getByText("za młody drzewostan (młodnik)")).toBeTruthy();
    expect(container.querySelector(".bars")).toBeNull();
    expect(screen.getByText("Brak szczegółów dla tego wydzielenia.")).toBeTruthy();
  });
  it("w masce, ale bez wyniku w wariancie bez presji: brak wyniku, nie „powód nieznany”", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A"), makeScore("B", { R_bez_presji: null })],
      regionsNoPressure: [],
    });
    S.setPressure(false);
    render(<StandCard standId="B" />);
    expect(screen.getByText("Brak wyniku dla tego wydzielenia w tej analizie.")).toBeTruthy();
    expect(screen.queryByText("powód nieznany w tej analizie")).toBeNull();
  });
  it("wstecz wraca do listy", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID)] });
    S.stack.value = [{ kind: "list" }, { kind: "stand", standId: ID }];
    render(<StandCard standId={ID} />);
    fireEvent.click(screen.getByText("Wróć"));
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
});

describe("karta rejonu", () => {
  it("wynik rejonu, paski z mediany 5 najlepszych, lista wydzieleń otwiera kartę", () => {
    const scores = [1, 0.9, 0.8, 0.7, 0.6, 0.1].map((h, i) => makeScore(`S${i}`, { H: h, R: 90 - i * 10 }));
    S.analysis.value = makeAnalysis({ scores, regions: [makeRegion("region_1", 76.4, scores.map((s) => s.stand_id))] });
    S.details.value = new Map();
    S.stack.value = [{ kind: "list" }, { kind: "region", regionId: "region_1" }];
    const { container } = render(<RegionCard regionId="region_1" />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    expect(container.querySelector(".score-badge strong")?.textContent).toBe("76");
    expect(container.querySelector(".bar-habitat .bar-word")?.textContent).toContain("0,80");
    expect(container.querySelectorAll(".rows li")).toHaveLength(6);
    fireEvent.click(container.querySelector(".rows .row")!);
    expect(S.top.value).toEqual({ kind: "stand", standId: "S0" });
  });
  it("nieistniejący rejon (np. po zmianie migawki) nie wysypuje karty", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<RegionCard regionId="region_9" />);
    expect(screen.getByText(/Nie ma już tego rejonu/)).toBeTruthy();
  });
});

describe("panel boczny", () => {
  it("wczytywanie, błąd, lista, karta z wierzchu stosu", () => {
    const { rerender } = render(<Sidebar />);
    expect(screen.getByText("Wczytuję analizę…")).toBeTruthy();
    S.load.value = { status: "error", message: "Brak scores.json." };
    rerender(<Sidebar />);
    expect(screen.getByRole("alert").textContent).toContain("Brak scores.json.");
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 70, ["A"])] });
    S.load.value = { status: "ready" };
    rerender(<Sidebar />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    S.openRegion("region_1", "list");
    rerender(<Sidebar />);
    expect(screen.getByText("Wydzielenia w rejonie (1)")).toBeTruthy();
  });
});
```

Run: `npx vitest run src/components/cards.test.tsx`
Expected: FAIL (brak komponentów).

- [ ] **Step 2: `ScoreBars.tsx` i `CardParts.tsx`**

`frontend/src/components/ScoreBars.tsx`:

```tsx
import type { Bar, BarNotes } from "../domain/bars";
import { formatValue } from "../domain/format";

export function ScoreBars({ bars, notes }: { bars: Bar[]; notes?: BarNotes }) {
  return (
    <ul class="bars">
      {bars.map((b) => (
        <li class={`bar bar-${b.key}${b.muted ? " is-muted" : ""}`}>
          <span class="bar-label">{b.label}</span>
          <span class="bar-track"><i style={{ width: `${Math.round((b.value ?? 0) * 100)}%` }} /></span>
          <span class="bar-word">{b.word}{b.value !== null && !b.muted ? ` · ${formatValue(b.value)}` : ""}</span>
          {notes?.[b.key] && <span class="bar-note">{notes[b.key]}</span>}
        </li>
      ))}
    </ul>
  );
}
```

`frontend/src/components/CardParts.tsx`:

```tsx
import { navigationUrl } from "../domain/format";
import { back, notify } from "../state/store";
import { Icon } from "./icons";

export function BackButton() {
  return (
    <button type="button" class="link-button back" onClick={back}>
      <Icon name="arrowLeft" />Wróć
    </button>
  );
}

export function ScoreBadge({ value, label }: { value: number; label: string }) {
  return (
    <div class="score-badge">
      <strong>{Math.round(value)}</strong>
      <small>{label}</small>
    </div>
  );
}

export function CardActions({ point, label }: { point: [number, number]; label: string }) {
  const [lon, lat] = point;
  const coords = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(coords);
      notify(`Skopiowano współrzędne: ${coords}`);
    } catch {
      notify(`Współrzędne: ${coords}`);
    }
  };
  return (
    <div class="card-actions">
      <a class="button primary" href={navigationUrl(point)} target="_blank" rel="noopener noreferrer" aria-label={`Nawiguj: ${label} (Google Maps)`}>
        <Icon name="navigate" />Nawiguj
      </a>
      <button type="button" class="button" onClick={() => void copy()}>
        <Icon name="copy" />Kopiuj współrzędne
      </button>
    </div>
  );
}
```

- [ ] **Step 3: `RegionCard.tsx`**

```tsx
import { regionAccessSummary } from "../domain/access";
import { regionBars } from "../domain/bars";
import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { regionName } from "../domain/labels";
import { regionAreaHa } from "../domain/ranking";
import type { AccessCard } from "../data/types";
import { details, openStand, pressure, rankIndex, regionViews, start } from "../state/store";
import { BackButton, CardActions, ScoreBadge } from "./CardParts";
import { ScoreBars } from "./ScoreBars";
import { StandRow } from "./StandRow";

export function RegionCard({ regionId }: { regionId: string }) {
  const index = regionViews.value.findIndex((v) => v.region.region_id === regionId);
  const view = regionViews.value[index];
  if (!view)
    return (
      <article class="card">
        <BackButton />
        <p class="empty">Nie ma już tego rejonu w bieżącym wariancie rankingu.</p>
      </article>
    );
  const name = regionName(view.region, index + 1);
  const point: [number, number] = [view.region.centroid_lon, view.region.centroid_lat];
  const loaded = details.value !== null;
  const cards = view.members
    .map((m) => details.value?.get(m.score.stand_id)?.access)
    .filter((c): c is AccessCard => !!c);
  const access = regionAccessSummary(cards);
  const members = [...view.members].sort((a, b) => b.r - a.r);
  return (
    <article class="card">
      <BackButton />
      <header class="card-head">
        <div>
          <h2>{name}</h2>
          <p class="muted">
            {joinMeta([`${view.members.length} wydz.`, areaLabel(regionAreaHa(view)), startDistanceLabel(start.value, point)])}
          </p>
        </div>
        <ScoreBadge value={view.region.rank_score} label="wynik rejonu" />
      </header>
      <section>
        <h3>Dlaczego taki wynik</h3>
        <ScoreBars bars={regionBars(view.members, pressure.value)} />
        <p class="hint">Mediana 5 najlepszych wydzieleń rejonu — ta sama podstawa co wynik rejonu.</p>
      </section>
      <section>
        <h3>Dojazd</h3>
        {!loaded ? (
          <p class="muted">Wczytuję szczegóły…</p>
        ) : access ? (
          <>
            <p>{access.distances}</p>
            <p class="muted small">{access.top}</p>
          </>
        ) : (
          <p class="muted">Brak danych o dojeździe.</p>
        )}
      </section>
      <section>
        <h3>Wydzielenia w rejonie ({view.members.length})</h3>
        <ol class="rows">
          {members.map((m) => (
            <StandRow
              key={m.score.stand_id}
              entry={m}
              rank={(rankIndex.value.get(m.score.stand_id) ?? 0) + 1}
              onOpen={() => openStand(m.score.stand_id, "list")}
            />
          ))}
        </ol>
      </section>
      <CardActions point={point} label={name} />
    </article>
  );
}
```

(Asercja testu `0,80` dotyczy mediany H 5 najlepszych: 1; 0,9; 0,8; 0,7; 0,6 → 0,8; `scoreBars` wypisuje słowo i wartość `formatValue` z dwoma miejscami.)

- [ ] **Step 4: `StandCard.tsx`**

```tsx
import { keyFacts, topPointSummary } from "../domain/access";
import { barNotes, scoreBars } from "../domain/bars";
import { areaLabel, finite, joinMeta, startDistanceLabel } from "../domain/format";
import { standCentroid } from "../domain/geometry";
import {
  densityLabel, formatDateLong, maskReasonTexts, neighborsSummary, parseStandId, standName, yearsLabel, zakazNote,
} from "../domain/labels";
import { effectiveR } from "../domain/ranking";
import type { Score, StandDetail } from "../data/types";
import { analysis, details, pressure, rankIndex, ranked, start } from "../state/store";
import { BackButton, CardActions, ScoreBadge } from "./CardParts";
import { ScoreBars } from "./ScoreBars";

// undefined = szczegoly jeszcze sie wczytuja; null = wczytane, ale brak tego wydzielenia.
type DetailState = StandDetail | null | undefined;

function TreeSection({ detail }: { detail: DetailState }) {
  if (detail === undefined)
    return <section><h3>Drzewostan</h3><p class="muted">Wczytuję szczegóły…</p></section>;
  if (detail === null)
    return <section><h3>Drzewostan</h3><p class="muted">Brak szczegółów dla tego wydzielenia.</p></section>;
  const rows: [string, string][] = [];
  if (detail.drzew_species.length) rows.push(["Skład", detail.drzew_species.map((s) => `${s.name} (${s.share})`).join(", ")]);
  if (finite(detail.age_years)) rows.push(["Wiek", yearsLabel(detail.age_years)]);
  if (detail.site_type) rows.push(["Siedlisko", `${detail.site_type.label} (${detail.site_type.code})`]);
  if (detail.soil_type) rows.push(["Gleba", detail.soil_type]);
  if (detail.density) rows.push(["Zwarcie", densityLabel(detail.density)]);
  if (detail.veg_cover) rows.push(["Runo", detail.veg_cover]);
  if (detail.podszyt_species.length) rows.push(["Podszyt", detail.podszyt_species.map((s) => s.name).join(", ")]);
  rows.push(["Sąsiedztwo", detail.neighbors.length ? detail.neighbors.join(", ") : (neighborsSummary(detail.neighbors) ?? "")]);
  return (
    <section>
      <h3>Drzewostan</h3>
      <dl class="kv">
        {rows.map(([k, v]) => <div><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
      {detail.searchability_hint && <p class="hint">{detail.searchability_hint}</p>}
    </section>
  );
}

function AccessSection({ score, detail }: { score: Score; detail: DetailState }) {
  const facts = keyFacts(detail?.access ?? null, null, score.d_park_m);
  const zakaz = zakazNote(score.zakaz_status);
  return (
    <section>
      <h3>Dojazd</h3>
      {detail === undefined && <p class="muted">Wczytuję szczegóły…</p>}
      {facts.length > 0 && <ul class="chips">{facts.map((f) => <li class="chip">{f}</li>)}</ul>}
      {detail?.access && <p class="muted small">{topPointSummary(detail.access)}</p>}
      {zakaz && <p class="notice-inline">{zakaz}</p>}
    </section>
  );
}

function DataSection({ score, day }: { score: Score; day: string }) {
  const parsed = parseStandId(score.stand_id);
  const source =
    score.s_host_source === "paczka"
      ? `paczka BDL${score.s_host_package_date ? ` z ${formatDateLong(score.s_host_package_date)}` : ""}`
      : score.s_host_source === "wfs" ? "opis WFS (tylko gatunek panujący)" : null;
  return (
    <section>
      <h3>Dane</h3>
      <dl class="kv">
        <div><dt>Kod</dt><dd class="mono">{score.stand_id}</dd></div>
        {parsed && <div><dt>Adres leśny</dt><dd>{`leśnictwo ${parsed.forestry} · oddział ${parsed.section} · pododdział ${parsed.subsection}`}</dd></div>}
        {source && <div><dt>Skład drzew</dt><dd>{source}</dd></div>}
        <div><dt>Analiza</dt><dd>{formatDateLong(day)}</dd></div>
      </dl>
    </section>
  );
}

export function StandCard({ standId }: { standId: string }) {
  const a = analysis.value;
  const score = a?.scoreById.get(standId);
  const feature = a?.features.get(standId);
  if (!a || !score || !feature)
    return (
      <article class="card">
        <BackButton />
        <p class="empty">Nie ma tego wydzielenia w bieżącej analizie.</p>
      </article>
    );
  const detail: DetailState = details.value === null ? undefined : (details.value.get(standId) ?? null);
  const point = standCentroid(feature);
  const name = standName(standId, detail ?? null);
  const r = effectiveR(score, pressure.value);
  const index = rankIndex.value.get(standId);
  const inModel = score.mask && r !== null && index !== undefined;
  return (
    <article class="card">
      <BackButton />
      <header class="card-head">
        <div>
          <h2>{name}</h2>
          <p class="muted">
            {joinMeta([areaLabel(score.area_ha), startDistanceLabel(start.value, point), inModel ? `#${index + 1} z ${ranked.value.length}` : null])}
          </p>
        </div>
        {inModel && <ScoreBadge value={r} label="wynik" />}
      </header>
      {inModel ? (
        <section>
          <h3>Dlaczego taki wynik</h3>
          <ScoreBars bars={scoreBars(score, pressure.value)} notes={barNotes(score, detail, pressure.value)} />
        </section>
      ) : score.mask ? (
        <section class="notice"><p>Brak wyniku dla tego wydzielenia w tej analizie.</p></section>
      ) : (
        <section class="notice">
          <h3>Nie spełnia filtrów modelu</h3>
          <ul>{maskReasonTexts(score.mask_reason).map((t) => <li>{t}</li>)}</ul>
        </section>
      )}
      <TreeSection detail={detail} />
      <AccessSection score={score} detail={detail} />
      <DataSection score={score} day={a.day} />
      <CardActions point={point} label={name} />
    </article>
  );
}
```

(`inModel` zawęża `r` i `index` w JSX tylko wtedy, gdy TypeScript to rozpozna; jeśli `tsc` zgłosi `r` jako `number | null` w `<ScoreBadge value={r} />`, zapisz `value={r ?? 0}` — przy `inModel` wartość nigdy nie jest null.)

- [ ] **Step 5: `Sidebar.tsx`**

```tsx
import { load, tab, top } from "../state/store";
import { PressureToggle } from "./PressureToggle";
import { RegionCard } from "./RegionCard";
import { RegionList } from "./RegionList";
import { StandCard } from "./StandCard";
import { StandList } from "./StandList";
import { ErrorState, LoadingState } from "./StatusViews";
import { Tabs } from "./Tabs";
import { WeatherPanel } from "./WeatherPanel";

function PanelBody() {
  const view = top.value;
  if (view.kind === "stand") return <StandCard standId={view.standId} />;
  if (view.kind === "region") return <RegionCard regionId={view.regionId} />;
  return tab.value === "regions" ? <RegionList /> : <StandList />;
}

export function Sidebar() {
  const state = load.value;
  return (
    <aside class="sidebar" aria-label="Panel analizy">
      {state.status === "loading" ? (
        <LoadingState />
      ) : state.status === "error" ? (
        <ErrorState message={state.message} />
      ) : (
        <>
          <WeatherPanel />
          <PressureToggle />
          <Tabs />
          <PanelBody />
          <p class="sidebar-note">
            Model ekspercki, nieskalibrowany. Wynik porównuje miejsca w tej analizie; to nie jest prawdopodobieństwo znalezienia grzybów.
          </p>
        </>
      )}
    </aside>
  );
}
```

- [ ] **Step 6: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ScoreBars.tsx frontend/src/components/CardParts.tsx frontend/src/components/RegionCard.tsx frontend/src/components/StandCard.tsx frontend/src/components/Sidebar.tsx frontend/src/components/cards.test.tsx
git commit -m "Nowy frontend: karty rejonu i wydzielenia (takze poza filtrami), panel boczny

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Mapa w interfejsie, złożenie aplikacji, wejście deweloperskie

**Files:**
- Modify: `frontend/src/domain/moisture.ts` (stała `MOISTURE_LEGEND_NOTE`)
- Create: `frontend/src/components/MapView.tsx`, `MapControls.tsx`, `LayersPopover.tsx`, `Legend.tsx`, `App.tsx`, `frontend/src/index.tsx`, `frontend/nowy.html`
- Test: `frontend/src/components/map-ui.test.tsx`

**Interfaces:**
- Consumes: `ForestMap`, `MapHandlers` (Task 10); `CLASS_COLORS` (layers); store; komponenty Task 11–14; `startApp` (loader).
- Produces: `MapView()`, `MapControls()`, `LayersPopover({ onClose })`, `Legend()`, `App()`; `MOISTURE_LEGEND_NOTE`; wejście `src/index.tsx`; strona deweloperska `nowy.html` (usuwana w Task 16).

- [ ] **Step 1: Testy**

Utwórz `frontend/src/components/map-ui.test.tsx`:

```tsx
// @vitest-environment jsdom
import { act } from "preact/test-utils";
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ maps: [] as { handlers: Record<string, (id: string) => unknown>; calls: Record<string, unknown[][]> }[] }));

vi.mock("../map/forestMap", () => ({
  ForestMap: class {
    handlers: Record<string, (id: string) => unknown>;
    calls: Record<string, unknown[][]> = {};
    constructor(_container: HTMLElement, handlers: Record<string, (id: string) => unknown>) {
      this.handlers = handlers;
      mocks.maps.push(this);
    }
    private record(name: string, args: unknown[]) {
      (this.calls[name] ??= []).push(args);
    }
    setStands(...args: unknown[]) { this.record("setStands", args); }
    setMode(...args: unknown[]) { this.record("setMode", args); }
    setRegions(...args: unknown[]) { this.record("setRegions", args); }
    setSelection(...args: unknown[]) { this.record("setSelection", args); }
    setAccessData(...args: unknown[]) { this.record("setAccessData", args); }
    setLayerVisible(...args: unknown[]) { this.record("setLayerVisible", args); }
    fitFeatures(...args: unknown[]) { this.record("fitFeatures", args); }
    resize() { this.record("resize", []); }
    destroy() { this.record("destroy", []); }
  },
}));

import * as S from "../state/store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";
import { App } from "./App";
import { Legend } from "./Legend";
import { MapControls } from "./MapControls";
import { MapView } from "./MapView";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
  mocks.maps.length = 0;
});

describe("mapa w interfejsie", () => {
  it("przekazuje wydzielenia do mapy; kliknięcie wydzielenia otwiera kartę bez przybliżania", () => {
    render(<MapView />);
    const map = mocks.maps[0];
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regionsNoPressure: [] });
    });
    const [features, props] = map.calls.setStands.at(-1)! as [unknown[], Map<string, unknown>];
    expect(features).toHaveLength(2);
    expect(props.get("A")).toMatchObject({ cls: 1 });
    act(() => { map.handlers.onStandClick("B"); });
    expect(S.top.value).toEqual({ kind: "stand", standId: "B" });
    expect(map.calls.fitFeatures ?? []).toHaveLength(0);
    expect(map.handlers.tooltip("A")).toMatch(/wynik 60/);
  });
  it("przybliża tylko na żądanie, nie po przełączeniu presji", () => {
    render(<MapView />);
    const map = mocks.maps[0];
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regionsNoPressure: [] });
      S.requestFitAll();
    });
    const fits = map.calls.fitFeatures.length;
    act(() => S.setPressure(false));
    expect(map.calls.fitFeatures).toHaveLength(fits);
  });
  it("znacznik rejonu otwiera kartę rejonu", () => {
    render(<MapView />);
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 70, ["A"])] });
    });
    act(() => { mocks.maps[0].handlers.onRegionClick("region_1"); });
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
  });
});

describe("kontrolki i legenda", () => {
  it("Wilgotność nieaktywna bez M; wybór zapamiętany", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { M: undefined })] });
    const { rerender } = render(<MapControls />);
    expect((screen.getByText("Wilgotność") as HTMLButtonElement).disabled).toBe(true);
    act(() => { S.analysis.value = makeAnalysis({ scores: [makeScore("A")] }); });
    rerender(<MapControls />);
    fireEvent.click(screen.getByText("Wilgotność"));
    expect(S.mapMode.value).toBe("moisture");
    expect(localStorage.getItem("borowik.map-color.v1")).toBe("moisture");
  });
  it("warstwy: lista dostępnych, przełączenie zapamiętane", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.access.value = { loaded: true, points: { type: "FeatureCollection", features: [] }, roads: null };
    render(<MapControls />);
    fireEvent.click(screen.getByText("Warstwy"));
    expect(screen.getByText("Parkingi")).toBeTruthy();
    expect(screen.queryByText("Drogi leśne")).toBeNull();
    fireEvent.click(screen.getByLabelText("Osiedla przy lesie"));
    expect(S.layers.value.settlements).toBe(true);
    expect(JSON.parse(localStorage.getItem("borowik.access-layers.v1")!).settlements).toBe(true);
  });
  it("legenda: klasy albo skala wilgotności", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    const { rerender } = render(<Legend />);
    expect(screen.getByText("najlepsze 5%")).toBeTruthy();
    act(() => S.setMapMode("moisture"));
    rerender(<Legend />);
    expect(screen.getByText("Wilgotność (model)")).toBeTruthy();
  });
  it("cała aplikacja montuje jedną mapę i pokazuje wczytywanie", () => {
    render(<App />);
    expect(mocks.maps).toHaveLength(1);
    expect(screen.getByText("Wczytuję analizę…")).toBeTruthy();
  });
});
```

Run: `npx vitest run src/components/map-ui.test.tsx`
Expected: FAIL (brak komponentów).

- [ ] **Step 2: Stała legendy**

Dopisz w `frontend/src/domain/moisture.ts`:

```ts
export const MOISTURE_LEGEND_NOTE =
  "Wilgotność w modelu: bilans opadu i parowania z 26 dni względem typowego dla tej pory roku. " +
  "W obecnym modelu najmocniej liczy się ostatni deszcz, więc mapa może różnić się od wymowy panelu pogody.";
```

- [ ] **Step 3: Komponenty mapy**

`frontend/src/components/MapView.tsx`:

```tsx
import { effect, untracked } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { ACCESS_LAYERS } from "../domain/access";
import { ForestMap } from "../map/forestMap";
import {
  access, analysis, featuresFor, fitRequest, layers, mapMode, mapStatus, mobilePane, openRegion, openStand,
  regionMarkers, selection, standProps, standTooltip,
} from "../state/store";
import { Legend } from "./Legend";
import { MapControls } from "./MapControls";

export function MapView() {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const map = new ForestMap(container.current, {
      onStandClick: (id) => openStand(id, "map"),
      onRegionClick: (id) => openRegion(id, "map"),
      onStatus: (message) => { mapStatus.value = message; },
      tooltip: standTooltip,
    });
    const stops = [
      effect(() => {
        const a = analysis.value;
        if (a) map.setStands([...a.features.values()], standProps.value);
      }),
      effect(() => map.setMode(mapMode.value)),
      effect(() => map.setRegions(regionMarkers.value)),
      effect(() => map.setSelection(selection.value)),
      effect(() => map.setAccessData(access.value.points, access.value.roads)),
      effect(() => {
        const on = layers.value;
        for (const l of ACCESS_LAYERS) map.setLayerVisible(l.id, on[l.id]);
      }),
      // Przyblizenie tylko po nowym zadaniu (fitRequest); zmiany rankingu nie przesuwaja mapy.
      effect(() => {
        const request = fitRequest.value;
        if (request) untracked(() => map.fitFeatures(featuresFor(request.req)));
      }),
      effect(() => {
        void mobilePane.value;
        requestAnimationFrame(() => map.resize());
      }),
    ];
    return () => {
      for (const stop of stops) stop();
      map.destroy();
    };
  }, []);
  return (
    <div class="map-stage">
      <div ref={container} class="map-canvas" aria-label="Mapa wydzieleń" />
      <MapControls />
      <Legend />
      {mapStatus.value && <p class="map-status" role="status">{mapStatus.value}</p>}
    </div>
  );
}
```

`frontend/src/components/MapControls.tsx`:

```tsx
import { useState } from "preact/hooks";
import { mapMode, moistureOk, requestFitAll, setMapMode } from "../state/store";
import { Icon } from "./icons";
import { LayersPopover } from "./LayersPopover";

export function MapControls() {
  const [open, setOpen] = useState(false);
  return (
    <div class="map-controls">
      <div class="segmented" role="group" aria-label="Kolory mapy">
        <button type="button" aria-pressed={mapMode.value === "score"} onClick={() => setMapMode("score")}>Wynik</button>
        <button
          type="button"
          aria-pressed={mapMode.value === "moisture"}
          disabled={!moistureOk.value}
          title={moistureOk.value ? undefined : "Ta analiza nie ma danych o wilgotności."}
          onClick={() => setMapMode("moisture")}
        >
          Wilgotność
        </button>
      </div>
      <button type="button" class="map-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="layers" />Warstwy
      </button>
      <button type="button" class="map-button" aria-label="Pokaż cały obszar" onClick={requestFitAll}>
        <Icon name="target" />
      </button>
      {open && <LayersPopover onClose={() => setOpen(false)} />}
    </div>
  );
}
```

`frontend/src/components/LayersPopover.tsx`:

```tsx
import { ACCESS_LAYERS, SURFACE_COLORS, SURFACE_LABELS } from "../domain/access";
import { access, layers, setLayer } from "../state/store";
import { Icon } from "./icons";

export function LayersPopover({ onClose }: { onClose: () => void }) {
  const state = access.value;
  const available = ACCESS_LAYERS.filter((l) => l.needs === "stands" || (l.needs === "points" ? state.points : state.roads));
  return (
    <div class="popover" role="dialog" aria-label="Warstwy mapy">
      <div class="popover-head">
        <strong>Warstwy</strong>
        <button type="button" class="icon-button" aria-label="Zamknij warstwy" onClick={onClose}><Icon name="close" /></button>
      </div>
      {!state.loaded ? (
        <p class="muted small">Wczytuję warstwy…</p>
      ) : (
        <ul class="layer-list">
          {available.map((l) => (
            <li>
              <label>
                <input
                  type="checkbox"
                  checked={layers.value[l.id]}
                  onChange={(event) => setLayer(l.id, (event.currentTarget as HTMLInputElement).checked)}
                />
                {l.label}
              </label>
            </li>
          ))}
        </ul>
      )}
      {state.loaded && (state.points || state.roads) && (
        <div class="layer-legend">
          <span class="key"><i class="dot" style={{ background: "#1f4e9c" }} />parking (BDL)</span>
          <span class="key"><i class="dot" style={{ background: "#5b8ec9" }} />parking (OSM)</span>
          <span class="key"><i class="dot" style={{ background: "#2a8f7a" }} />wjazd do lasu</span>
          <span class="key"><i class="dot" style={{ background: "#c0392b" }} />szlaban</span>
          {Object.keys(SURFACE_COLORS).map((k) => (
            <span class="key"><i style={{ background: SURFACE_COLORS[k] }} />droga: {SURFACE_LABELS[k]}</span>
          ))}
          <span>Linia ciągła — droga publiczna, przerywana — zamknięta droga leśna; grubość — atrakcyjność.</span>
        </div>
      )}
    </div>
  );
}
```

`frontend/src/components/Legend.tsx`:

```tsx
import { MOISTURE_LEGEND_NOTE, MOISTURE_LEGEND_TICKS, MOISTURE_STOPS, moistureTickLabel } from "../domain/moisture";
import { CLASS_LABELS } from "../domain/ranking";
import { CLASS_COLORS } from "../map/layers";
import { mapMode, pressure } from "../state/store";

export function Legend() {
  if (mapMode.value === "moisture") {
    const gradient = `linear-gradient(90deg, ${MOISTURE_STOPS.map(([v, c]) => `${c} ${v * 100}%`).join(", ")})`;
    return (
      <div class="legend">
        <strong>Wilgotność (model)</strong>
        <div class="gradient" style={{ background: gradient }} />
        <div class="ticks">{MOISTURE_LEGEND_TICKS.map((t) => <span>{moistureTickLabel(t)}</span>)}</div>
        <p class="legend-note">{MOISTURE_LEGEND_NOTE}</p>
      </div>
    );
  }
  return (
    <div class="legend">
      <strong>{pressure.value ? "Wynik" : "Wynik bez presji"}</strong>
      <ul>
        {([1, 2, 3, 4] as const).map((c) => (
          <li><i style={{ background: CLASS_COLORS[c] }} />{CLASS_LABELS[c]}</li>
        ))}
        <li><i class="outline" />poza filtrami modelu</li>
        <li><i class="region" />rejon</li>
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Aplikacja i wejście**

`frontend/src/components/App.tsx`:

```tsx
import { mobilePane } from "../state/store";
import { AboutDialog } from "./AboutDialog";
import { MapView } from "./MapView";
import { MobileTabs } from "./MobileTabs";
import { Sidebar } from "./Sidebar";
import { Toast } from "./StatusViews";
import { TopBar } from "./TopBar";

export function App() {
  return (
    <div class="app">
      <TopBar />
      <main class="workspace" data-pane={mobilePane.value}>
        <MobileTabs />
        <Sidebar />
        <section class="map-area" aria-label="Mapa">
          <MapView />
        </section>
      </main>
      <AboutDialog />
      <Toast />
    </div>
  );
}
```

`frontend/src/index.tsx`:

```tsx
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/components.css";
import { render } from "preact";
import { App } from "./components/App";
import { startApp } from "./state/loader";

render(<App />, document.getElementById("app")!);
void startApp();
```

`frontend/nowy.html` (tymczasowe wejście do porównania ze starym interfejsem; usuwane w Task 16):

```html
<!doctype html>
<html lang="pl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#234b3d" />
    <title>Borowik (nowy interfejs)</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/index.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów; `npm run build` → bez błędów (buduje stary `index.html`; nowy działa w trybie deweloperskim).

Uruchom `npm run dev` i otwórz `http://127.0.0.1:5173/nowy.html` — aplikacja ma się wczytać na aktualnych danych bez błędów w konsoli (pełna weryfikacja w Task 16).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/domain/moisture.ts frontend/src/components frontend/src/index.tsx frontend/nowy.html
git commit -m "Nowy frontend: mapa w interfejsie (kontrolki, warstwy, legenda), zlozenie aplikacji

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Przełączenie na nowy interfejs, sprawdzenie w przeglądarce, raport

**Files:**
- Modify: `frontend/index.html`
- Delete: `frontend/nowy.html`
- Create: `docs/RAPORT_NOWY_FRONTEND.md`, zrzuty `docs/ui-zrzuty/nowy-*.png`

- [ ] **Step 1: Wejście**

W `frontend/index.html` zamień `<script type="module" src="/src/main.ts"></script>` na `<script type="module" src="/src/index.tsx"></script>` i tytuł na `<title>Borowik</title>`. Usuń `frontend/nowy.html`.

Run (w `frontend/`): `npm run build` → bez błędów; `npx vitest run` → PASS.

- [ ] **Step 2: Świeże dane z nowymi polami (za zgodą właściciela)**

Zapytaj właściciela, czy przygotować nową analizę (nadpisze bieżącą w `frontend/public/data`, migawki w `trips/` zostają). Po zgodzie, z katalogu repo:

```bash
.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 50.6191 --lon 18.4611 --radius-km 20
cd frontend && npm run sync-data
```

Sprawdź nowe pola:

```bash
.venv/Scripts/python.exe -c "import json; c=json.load(open('frontend/public/data/conditions.json',encoding='utf-8')); print(len(c['daily']), c['rain26'], c['warnings'], c['lookback_days']); d=json.load(open('frontend/public/data/details.json',encoding='utf-8')); print(d[0].get('site_type'), d[0].get('age_years')); s=json.load(open('frontend/public/data/scores.json',encoding='utf-8')); print(sum(1 for x in s if x['mask_reason']))"
```

Expected: ok. 42 wiersze `daily`; `rain26` z `normal_mm` (jeśli jest `cache/eobs`); `site_type` z nazwą; niezerowa liczba wydzieleń z powodami. Jeśli sieć jest niedostępna, zapisz to w raporcie i sprawdź interfejs na istniejących danych (tryb zgodności panelu pogody).

- [ ] **Step 3: Sprawdzenie w przeglądarce**

`npm run dev`, otwórz `http://127.0.0.1:5173` (Chrome, narzędzia claude-in-chrome). Przejdź listę kontrolną i przy każdej pozycji zapisz wynik (OK / uwaga):

| # | Stare pole | Nowe miejsce | Sprawdź |
|---|---|---|---|
| 1 | Hasło „Wybierz swój kawałek lasu”, nagłówek strony | usunięte | mapa widoczna od góry ekranu |
| 2 | Data analizy | pasek górny | „Aktualna analiza · 20 km · …” |
| 3 | Pasek pogody (zdanie + 7 słupków F) | panel pogody | nagłówek z faktami, 3 liczby, norma, wykres, rozwinięcie z tabelą i pasmem temperatury |
| 4 | Baner „skład tylko z WFS” | usunięty | **zapytaj właściciela**, czy go przywrócić |
| 5 | „Zapisane mapy” | „Analiza” w pasku górnym | wybór migawki wczytuje ją; „Aktualna” wraca |
| 6 | Zakładka „Zapisane”, „Zapisz miejsce” | usunięte | są „Nawiguj” i „Kopiuj współrzędne” |
| 7 | Przełącznik presji | nad zakładkami | przelicza listy, rejony, klasy mapy i legendę |
| 8 | „Rejony / Wydzielenia” | zakładki panelu | liczebności w nawiasach |
| 9 | Karta rejonu | karta rejonu | paski z mediany 5 najlepszych, dojazd rejonu, lista wydzieleń |
| 10 | Karta wydzielenia | karta wydzielenia | paski z opisami, drzewostan z wiekiem i siedliskiem, dojazd, dane |
| 11 | Pewność „średnia”, zdania uzasadnień | usunięte | brak na kartach |
| 12 | Tryby Wynik / Wynik bez presji / Wilgotność | Wynik (klasy) i Wilgotność (skala) | 4 klasy jak w KMZ; wilgotność ciągła |
| 13 | Warstwy pod mapą + legenda nawierzchni | „Warstwy” na mapie | przełączanie działa i jest pamiętane po odświeżeniu |
| 14 | Legenda mapy | lewy dolny róg | zmienia się z trybem i presją |
| 15 | Pinezka wybranego wydzielenia | obrys wybranego wydzielenia, numery rejonów | numery klikalne |
| 16 | „Pokaż cały obszar” | przycisk przy „Warstwy” | przybliża do całości |
| 17 | „O danych i ograniczeniach” | „O danych” w pasku | treść + podziękowanie E-OBS |
| 18 | Lista/Mapa na telefonie | bez zmian | poniżej 800 px dwie zakładki; klik na mapie przełącza na kartę |
| 19 | Stopka | usunięta | nota o modelu na dole panelu |
| 20 | Klik na mapie bez zmiany przybliżenia | zachowane | także dla wydzielenia poza filtrami (karta z powodami) |

Dodatkowo: otwórz jedną starą migawkę (np. z 29.09) — panel pogody w trybie zgodności, bez błędów w konsoli (`read_console_messages`).

Zrzuty ekranu (zapisz do `docs/ui-zrzuty/`): `nowy-pulpit-rejony.png`, `nowy-pulpit-karta-wydzielenia.png`, `nowy-pulpit-pogoda-rozwinieta.png`, `nowy-pulpit-wilgotnosc.png`, `nowy-telefon-lista.png`, `nowy-telefon-mapa.png`. Widok telefonu: spróbuj `resize_window` do 390×844; jeśli zrzut nie odzwierciedla zmiany szerokości (znane ograniczenie narzędzia), utwórz tymczasowo `frontend/public/_telefon.html` z `<iframe src="/" width="390" height="844" style="border:0">`, otwórz `http://127.0.0.1:5173/_telefon.html`, zrób zrzuty i usuń plik.

- [ ] **Step 4: Raport**

Utwórz `docs/RAPORT_NOWY_FRONTEND.md`: co zmieniono (odwołanie do specu i planu), wypełniona lista kontrolna z Step 3, nowe pola eksportu, liczby testów (pytest, vitest), lista zrzutów, ograniczenia (model bez zmian, mapa wilgotności z wagami K0, widok telefonu sprawdzony w iframe/oknie, pytanie o baner WFS), decyzje doprecyzowane w trakcie (klik na mapie zastępuje kartę wydzielenia na wierzchu stosu; przełączenie presji zamyka kartę rejonu, bo oba warianty rejonów mają te same identyfikatory).

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html docs/RAPORT_NOWY_FRONTEND.md docs/ui-zrzuty/nowy-*.png
git rm frontend/nowy.html
git commit -m "Nowy frontend: przelaczenie wejscia, sprawdzenie w przegladarce, raport z lista kontrolna

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: Usunięcie starego interfejsu i dokumentacja

**Files:**
- Delete: `frontend/src/main.ts`, `frontend/src/map.ts`, `frontend/src/storage.ts`, `frontend/src/style.css`, `frontend/src/model.ts`
- Move + Modify: `frontend/src/model.test.ts` → `frontend/src/domain/domain.test.ts`, `frontend/src/ui.test.ts` → `frontend/src/domain/ui-logic.test.ts`
- Modify: `docs/CODEX-HANDOFF.md`, `CLAUDE.md`, `frontend/IMPLEMENTATION.md`; `frontend/README.md` tylko za zgodą właściciela

- [ ] **Step 1: Usuń stary kod i przenieś testy**

```bash
git rm frontend/src/main.ts frontend/src/map.ts frontend/src/storage.ts frontend/src/style.css frontend/src/model.ts
git mv frontend/src/model.test.ts frontend/src/domain/domain.test.ts
git mv frontend/src/ui.test.ts frontend/src/domain/ui-logic.test.ts
```

- [ ] **Step 2: Popraw importy w przeniesionych testach**

W obu plikach zamień każdy import `from "./model"` na importy z nowych modułów (ścieżki względem `src/domain/`): typy z `../data/types`; `parseData`, `parseConditions`, `parseTrips`, `parseAccessCollection` z `../data/parse`; `joinData`, `joinRegions`, `rankEntries`, `effectiveR`, `isStandaloneTarget`, `MIN_STANDALONE_AREA_HA`, `pressureSwitchAvailable` z `./ranking`; `fruitingClass`, `navigationUrl`… według tabeli z Task 5 (`navigationUrl`, `distanceLabel`, `areaLabel`, `haversineKm`, `startDistanceLabel` z `./format`; `zakazNote`, `standStructureLabel`, `densityLabel`, `neighborsSummary`, `formatTripLabel`, `parseStandId`, `standName`, `regionName`, `distanceMethod` z `./labels`; funkcje dostępu z `./access`; `scoreBars` z `./bars`; wilgotność z `./moisture`; `dayLabel`, `uncertaintyLabel` z `./weather`). Usuń import z `./storage`.

- [ ] **Step 3: Usuń testy usuniętych funkcji**

Usunięte symbole: `confidenceLabel`, `entranceLabel`, `topExplanations`, `RANK_COLORS`, `RANK_QUANTILES`, `RANK_ZERO_COLOR`, `rankColorStops`, `accessCardSummary`, `loadData`, `WEATHER_DISCLAIMER`, `uncertaintyNote`, `weatherComponentLines`, `weatherCardLines`, `localPhenomenaNote`, `WFS_ONLY_BANNER_THRESHOLD`, `wfsOnlyBanner`, `habitatComponents`, `weatherComponents`, `conditionBars`, `chooseColorMode`, `togglePressureControls`, `resolveColorMode`, `colorModeForPressure`, `MAP_COLOR_KEY`, `MOISTURE_NOTE`, `readSaved`, `saveRegion`.

W `domain/domain.test.ts` usuń: `it("selects strongest explanations without mutating input")`, `describe("saved regions")`, `describe("loadData against a dev-server SPA fallback for missing optional files")` (to samo sprawdza teraz `fetchJson` w `data/data.test.ts`), `describe("rankColorStops")`, `it("summarises the card as nearest parking / entrance / paved forest road")`, `describe("Faza 4: składniki pogody")`, `describe("Plan 1.3: baner składu tylko z WFS")`, w `describe("Faza 4.4: lokalne zjawiska w panelu")` tylko `it("pokazuje udział lasu z przymrozkiem i silnym opadem tylko gdy > 0")`, a w `describe("Faza 4: oznaczenia niepewności prognozy")` tylko asercje `uncertaintyNote` (asercje `uncertaintyLabel` zostają).

W `domain/ui-logic.test.ts` usuń: `it("składniki siedliska: wiek w trybie neutral „nie wpływa na wynik”")`, `it("składniki pogody: M, T, K_frost (jeśli eksport je ma)")`, `describe("Faza UI.3: słupki 7 dni")`, a w `describe("tryby kolorowania mapy")` sześć testów `chooseColorMode`/`togglePressureControls`/`resolveColorMode` (tytuły zaczynające się od: „„Wynik” i „Wynik bez presji” ustawiają”, „przełącznik presji ustawia tryb”, „przełącznik presji wyprowadza mapę”, „Wilgotność zmienia tylko kolory”, „niedostępne tryby są odrzucane”, „stan początkowy”). W teście „progi skali są rosnące…” zamień asercję o `MOISTURE_NOTE` na `expect(MOISTURE_LEGEND_NOTE).toContain("model")`.

Run (w `frontend/`): `npx tsc --noEmit` — każdy błąd `Cannot find name`/`has no exported member` wskazuje pozostały test usuniętej funkcji: usuń tę asercję (albo cały `it`, jeśli testuje tylko usuniętą funkcję). Powtarzaj do braku błędów.

- [ ] **Step 4: Pełna weryfikacja**

Run: `npx vitest run` → PASS; `npx tsc --noEmit` → bez błędów; `npm run build` → bez błędów; z katalogu repo `.venv/Scripts/python.exe -m pytest -q` → PASS. `npm run dev` → aplikacja działa jak w Task 16.

- [ ] **Step 5: Dokumentacja**

1. `docs/CODEX-HANDOFF.md`: nowa notatka na górze, z datą dnia wykonania, tytuł „aktualne (37): nowy frontend (Preact); gałąź `nowy-frontend`” — co powstało (moduły `src/data`, `src/domain`, `src/state`, `src/map`, `src/components`), nowe pola eksportu, decyzje doprecyzowane w trakcie, liczby testów, otwarte kwestie (baner WFS, K1 po sezonie, widok telefonu).
2. `CLAUDE.md`: w linii „Specyfikacja frontendu: …” zamień ścieżkę na `docs/superpowers/specs/2026-09-30-borowik-nowy-frontend-design.md` i dopisz „(poprzednia: `docs/superpowers/specs/2026-09-24-borowik-frontend-design.md`)”.
3. `frontend/IMPLEMENTATION.md`: na górze dopisz akapit, że opisuje interfejs sprzed 2026-10 (zastąpiony), z odwołaniem do nowego specu i `docs/RAPORT_NOWY_FRONTEND.md`.
4. `frontend/README.md` ma niezacommitowane zmiany właściciela — zaproponuj właścicielowi krótki akapit o nowym interfejsie i edytuj dopiero po zgodzie.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/domain/domain.test.ts frontend/src/domain/ui-logic.test.ts docs/CODEX-HANDOFF.md CLAUDE.md frontend/IMPLEMENTATION.md
git commit -m "Nowy frontend: usuniety stary interfejs, testy przeniesione do src/domain, dokumentacja

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Następnie: skill `superpowers:finishing-a-development-branch` (scalenie `nowy-frontend` z `master` — decyzja właściciela).
