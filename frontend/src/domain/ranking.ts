import type { Region, RegionView, Score, StandView, Stands } from "../data/types";
import { finite } from "./format";
import { standCentroid } from "./geometry";

// Plan 2.1 step A4 (docs/archiwum/projekt-borowik.md §5.2/§13.1): a stand this small
// isn't worth a dedicated trip as a standalone destination -- presentation
// filter only, never a mask (pipeline.habitat.passes_mask is unaffected):
// small stands still count toward their region's area (pipeline/regions.py,
// A2) and stay in scores/stands exports (pipeline/export.py). Kept here,
// not in profiles/*.yaml: this number never feeds Python scoring/H/F/R --
// putting it in the profile would misleadingly imply it does, and would
// need a new export field wired through just to carry a value the backend
// itself never uses. This is the one place it's defined; isStandaloneTarget
// is the one place it's applied (state/store.ts's visibleStands).
export const MIN_STANDALONE_AREA_HA = 0.5;

export function isStandaloneTarget(score: Score): boolean {
  // area_ha absent (older export, before this field existed) or null
  // (should not happen post-A4, but geometry could theoretically be empty)
  // means "unknown area" -- don't hide it, rather than treating unknown as
  // "too small".
  return !finite(score.area_ha) || score.area_ha >= MIN_STANDALONE_AREA_HA;
}

// Wynik rankingowy wydzielenia w wybranym trybie presji (Faza UI.1).
export function effectiveR(score: Score, pressure: boolean): number | null {
  const value = pressure ? score.R : score.R_bez_presji;
  return finite(value) ? value : null;
}

// Plan 2.1 "Zmiana 4": R rounded to 2 decimal places is the primary key (same
// precision pipeline.regions._summarize_cluster uses for region member
// ordering, chosen against a real Będziemyśl export -- see that function's own
// docstring), tie_break the secondary key among stands tied at that
// precision, stand_id the final deterministic tiebreaker.
function compareViews(a: StandView, b: StandView): number {
  const ra = Math.round(a.r * 100);
  const rb = Math.round(b.r * 100);
  if (rb !== ra) return rb - ra;
  const ta = a.score.tie_break ?? -1;
  const tb = b.score.tie_break ?? -1;
  if (tb !== ta) return tb - ta;
  return a.score.stand_id.localeCompare(b.score.stand_id);
}

// Ponowne uszeregowanie wydzielen wg wybranego trybu presji; przy `pressure = true`
// wynik jest identyczny z joinData (test). Geometria i punkt sa wspoldzielone.
export function rankEntries(entries: StandView[], pressure: boolean): StandView[] {
  const ranked: StandView[] = [];
  for (const e of entries) {
    const r = effectiveR(e.score, pressure);
    if (e.score.mask && r !== null) ranked.push({ ...e, r });
  }
  return ranked.sort(compareViews);
}

export function joinData(scores: Score[], stands: Stands, pressure = true): StandView[] {
  const byGeometry = new Map(
    stands.features.map((f) => [f.properties.stand_id, f]),
  );
  const ids = new Set(scores.map((s) => s.stand_id));
  if (
    ids.size !== byGeometry.size ||
    [...ids].some((id) => !byGeometry.has(id))
  )
    throw new Error("Wyniki i geometrie dotyczą różnych zestawów wydzieleń.");
  const views: StandView[] = [];
  for (const score of scores) {
    const r = effectiveR(score, pressure);
    if (!score.mask || r === null) continue;
    const feature = byGeometry.get(score.stand_id)!;
    views.push({ score, feature, point: standCentroid(feature), r });
  }
  return views.sort(compareViews);
}

export function joinRegions(
  regions: Region[],
  entries: StandView[],
): RegionView[] {
  const byId = new Map(entries.map((e) => [e.score.stand_id, e]));
  const views: RegionView[] = [];
  for (const region of regions) {
    const members = region.stand_ids
      .map((id) => byId.get(id))
      .filter((e): e is StandView => e !== undefined);
    if (!members.length) continue;
    const top = members.reduce((best, e) => (e.r > best.r ? e : best));
    views.push({ region, top, members });
  }
  return views.sort((a, b) => b.region.rank_score - a.region.rank_score);
}

/** Przelacznik presji dziala tylko, gdy migawka ma R_bez_presji i drugi zestaw rejonow. */
export function pressureSwitchAvailable(
  scores: Score[],
  regionsNoPressure: Region[] | null,
): boolean {
  return (
    regionsNoPressure !== null &&
    scores.some((s) => s.mask && finite(s.R_bez_presji))
  );
}

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
