# Borowik GIS — Minimal Frontend (priority 4) Design

> Design doc for `docs/projekt-borowik.md` §13 priority 4: "Minimalny frontend (mapa rejonów + panel szczegółów)". Brainstormed and approved section-by-section 2026-09-24; this document is the spec `writing-plans` argues from.

## Goal

Today the pipeline's output (regions, per-stand scores, stand geometries) exists only as JSON/GeoParquet files on disk, printed as summary lines in a terminal. Priority 4's completion criterion (§13): *"Strona otwarta lokalnie w przeglądarce pokazuje ≥1 rejon na mapie z polami z sekcji 9.2, zbudowana z realnych danych z kroku 1–3."* This design covers both the region view (§9.2, the primary screen) and the wydzielenie detail view (§9.3, secondary) in one plan, per explicit direction — priority 4's own criterion only requires the region view, but the fuller scope was chosen deliberately.

**Out of scope for this plan** (unchanged from `docs/projekt-borowik.md`'s own existing scope decisions):
- Deployment to static hosting / phone access (§13 priority 5) — this plan only needs to run locally (`npm run dev`).
- PMTiles/tippecanoe (§6, §18) — plain GeoJSON instead (see Data flow), because tippecanoe has no Windows build and isn't installed on this machine, and at today's scale (~1–2k stands, one tile) GeoJSON is simpler with no build-tool dependency. Revisit only if/when tile counts grow enough that this becomes a real bottleneck.
- `localStorage` save + navigation-link export (§7.2 point 4, §9.2) are IN scope (they're part of the §9.2 card fields), but full offline PWA/cached-tile support is not (§14, explicitly deferred there already).
- Any framework (React/Vue/etc.) — plain Vite + TypeScript. Two views, a map, and a handful of cards is not enough UI complexity to justify one.
- End-to-end test tooling (Playwright etc.) — manual + `claude-in-chrome`-driven browser verification instead.
- Fixing the backend "nan" bug noted below — flagged, not fixed here.

## Context: real data shapes (verified against actual output files, 2026-09-24)

`notebooks/output/regions_2026-09-24.json` (one record per region, from `pipeline.export.build_region_record`):
```json
{
  "region_id": "region_1",
  "rank_score": 62.28744019755905,
  "stand_count": 309,
  "stand_ids": ["08-13-1-09-521   -b   -00@2026", "..."],
  "day": "2026-09-24",
  "centroid_lat": 53.17532868683392,
  "centroid_lon": 16.776312679274273
}
```
No region polygon is exported — see "Region geometry" below for how the frontend gets one anyway, without a backend change.

`notebooks/output/scores_2026-09-24.json` (one record per stand, from `pipeline.export.build_score_record`):
```json
{
  "stand_id": "08-13-1-07-385   -j   -00@2026",
  "H": null,
  "F": 0.6075277375633609,
  "F_loc": 0.6075277375633609,
  "P": 0.0,
  "confidence": "SREDNIA",
  "confidence_reasons": ["...", "..."],
  "explanation": [
    {"factor": "moisture", "contribution": 0.0988, "text": "wilgotność ostatnich 26 dni powyżej normy dla tej pory roku (M=0.46)"},
    {"factor": "host", "contribution": -0.2567, "text": "..."}
  ],
  "distance_method": "euclidean",
  "entrance_status": "not_evaluated",
  "day": "2026-09-24",
  "R": 0.0,
  "mask": false
}
```
`H` is `null` on mask-failing stands (matches `_json_safe`'s NaN→null conversion, `pipeline/export.py`). **Missing: `d_park_m` (the actual distance in metres)** — `SCORE_FIELDS` doesn't include it, so there's no way to show "dojazd: X km" on a card today. This plan adds it to `SCORE_FIELDS` (one-line change, same shape as the existing fields, no behavior change to anything already exported).

**Observed data-quality note, not fixed by this plan:** some `explanation[].text` values contain the literal substring `"nan"` (e.g. *"gatunek panujący nan słabo pasuje do borowika"*) — looks like a `None`/`NaN` species name being string-formatted into a template somewhere in `pipeline/explain.py`, upstream of this plan and unrelated to the frontend. The frontend will display explanation text as-is; if this surfaces visibly during manual verification, it's a backend bug to file separately, not something to paper over client-side in this plan.

`notebooks/output/stands_mvp.parquet` (GeoParquet, `stand_id` + `geometry` only, EPSG:2180) — this plan adds a GeoJSON export of the same data (`export_stand_geometries_geojson`, alongside the existing parquet export, not replacing it), reprojected to WGS84 (EPSG:4326) since that's what MapLibre/GeoJSON expect.

## Data flow

1. **Backend (Python), one-time additions this plan needs:**
   - `pipeline/export.py::export_stand_geometries_geojson(stands, out_path)` — same input shape as the existing `export_stand_geometries`, writes GeoJSON reprojected to EPSG:4326 instead of GeoParquet in EPSG:2180.
   - `SCORE_FIELDS` gains `"d_park_m"`.
   - `pipeline/prepare_trip.py::run_trip_preparation` calls the new GeoJSON export alongside the existing parquet one and returns its path in the summary dict, mirroring how `stands_path` already works.
2. **Getting data into the frontend:** `frontend/scripts/sync-data.mjs` (run via `npm run sync-data`), a small Node script that copies the latest `regions_{date}.json`, `scores_{date}.json`, and `stands.geojson` from `../notebooks/output/` into `frontend/public/data/` as fixed filenames (`regions.json`, `scores.json`, `stands.geojson`) — a plain file copy, not a live proxy/dev-server integration, matching the established "run the pipeline, then look at results" workflow (§7.2) and keeping `frontend/` a self-contained static site (relevant again for priority 5's deployment later, even though deployment itself is out of scope now).
3. **Region geometry, without a backend change:** `regions.json` only has `stand_ids` + a centroid. The frontend derives each region's displayed outline client-side: filter `stands.geojson`'s features to those whose `stand_id` is in the region's `stand_ids`, and render their union (via Turf.js's `union`, or simply render all member stand polygons as one highlighted layer — see Section 2 of the plan for the concrete choice). This reuses exactly the data the wydzielenie detail view already needs, so it's not a redundant fetch — one dataset, two views.
4. **Frontend runtime:** three `fetch()` calls (`/data/regions.json`, `/data/scores.json`, `/data/stands.geojson`) on load, joined client-side by `stand_id`/`region_id`. No backend, no API — `npm run dev`'s static file serving is sufficient, and the same files would deploy as-is later (priority 5).

## Frontend architecture

- **New `frontend/` directory** at repo root, sibling to `pipeline/`. Standard Vite + TypeScript project (`vanilla-ts` template).
- **Map:** MapLibre GL JS. Basemap: OpenFreeMap's free vector style (`https://tiles.openfreemap.org/styles/liberty`, no API key — matches §18's existing recommendation).
- **Geometry union for region outlines:** `@turf/union` + `@turf/helpers` (not the full `@turf/turf` bundle — these two cover exactly what's needed) — a well-established, MIT-licensed library, not a novel dependency choice.
- **Two views, one page, client-side switching (no router — two states, not a route hierarchy):**
  - **Region view (default):** left/top panel = list of region cards; map shows all regions' outlines + a start-point marker per region, colored/highlighted by which card is selected or hovered.
    - "Top-ranked member stand" means: among a region's `stand_ids`, the one with the highest `scores.json` **`R`** value (this field holds `R_final`, `pipeline/export.py::build_score_record`'s `record["R"] = float(row["R_final"])` — not the earlier, pre-presja-refinement `R` column from `pipeline/orchestrate.py`, which isn't exported at all).
    - Card fields (§9.2, using the real field names above): region rank (`rank_score`, labeled "ranking, model nieskalibrowany" per §5.7's own established wording), F class for the region (derived: the F class of its top-ranked member stand, via the existing class-boundary table already in `profiles/boletus_edulis.yaml::fruiting_classes` — reimplemented client-side as a small pure function, table copied from the YAML since the frontend has no Python runtime), start point = the region's top-ranked member stand's centroid with its `entrance_status` (confirmed/potential/not_evaluated) shown as a status badge, dojazd = that stand's `d_park_m` with `distance_method` shown as "po drogach"/"oszacowanie" per §9.2's own required disclosure, a short "dlaczego" line built from that stand's top explanation entries (already-generated `text` strings — no new text generation needed, just picking the top 1-2 by absolute `contribution`), confidence badge, `day` shown as the freshness date, **Zapisz rejon** (writes the card's summary to `localStorage`) and **Nawiguj** (`<a href="https://www.google.com/maps?q={lat},{lon}">`) buttons, and **Zobacz wydzielenia w rejonie** (switches to the detail view scoped to this region).
  - **Wydzielenie detail (secondary, per region):** map shows that region's individual stand polygons colored by `R`/class; clicking one opens the §10-style panel (S_host/S_site/S_age not present in `scores.json` today — only `H`/`F`/`F_loc` are, so the panel shows what's actually exported: H, F breakdown, P, confidence + reasons, full explanation list, distance method/entrance status) and a back link to the region view.
- **State:** no state-management library — a handful of `let`/module-level variables and direct DOM updates is proportionate to two views and a few dozen DOM nodes; introducing one would be solving a problem this app doesn't have.

## Testing

- **Vitest** (already the natural pairing with Vite) for pure functions: the `stand_id`/`region_id` join logic, the F-class-from-value mapping, the "top explanation entries" picker, the `localStorage` save/read round-trip, the Google Maps link builder. TDD'd the same way the Python backend was (red/green, one behavior per test).
- **Manual + `claude-in-chrome`** for the map and layout: run `npm run dev`, drive the browser tool to load the page, click through both views, screenshot, and visually confirm against the §9.2 field list and the region-view/detail-view requirement — the direct analogue of the Python plans' live-service manual-verification steps.
- No Playwright/Cypress in this pass.

## Success criteria (ties back to §13 priority 4)

- `npm run dev` (after `npm run sync-data` against a real `prepare_trip` run's output) opens a page showing ≥1 region on a map with every §9.2 field populated from real data, not placeholders.
- Clicking "Zobacz wydzielenia w rejonie" shows that region's real stands with real per-stand scores.
- "Zapisz rejon" and "Nawiguj" both work against real data (verified via the browser tool, including confirming saved data survives a page reload — the closest local proxy for "works offline after being saved").
