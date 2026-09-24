import { finite, navigationUrl } from "./model";
export type SavedRegion = {
  key: string;
  title: string;
  day: string;
  point: [number, number];
  reasons: string[];
  conditions: string;
  savedAt: string;
};
type Reader = Pick<Storage, "getItem">;
type Writer = Pick<Storage, "getItem" | "setItem">;
const KEY = "borowik.saved-regions.v1";
export function readSaved(storage: Reader): SavedRegion[] {
  try {
    const parsed = JSON.parse(storage.getItem(KEY) ?? "null");
    if (parsed?.version !== 1 || !Array.isArray(parsed.regions)) return [];
    return parsed.regions.filter(
      (r: SavedRegion) =>
        r &&
        typeof r.key === "string" &&
        typeof r.title === "string" &&
        typeof r.day === "string" &&
        typeof r.conditions === "string" &&
        typeof r.savedAt === "string" &&
        Array.isArray(r.reasons) &&
        r.reasons.every((x) => typeof x === "string") &&
        Array.isArray(r.point) &&
        r.point.length === 2 &&
        r.point.every(finite) &&
        Math.abs(r.point[0]) <= 180 &&
        Math.abs(r.point[1]) <= 90,
    );
  } catch {
    return [];
  }
}
export function saveRegion(storage: Writer, region: SavedRegion): void {
  navigationUrl(region.point);
  const regions = readSaved(storage).filter((r) => r.key !== region.key);
  storage.setItem(
    KEY,
    JSON.stringify({ version: 1, regions: [region, ...regions].slice(0, 50) }),
  );
}
export function removeSaved(storage: Writer, key: string): void {
  storage.setItem(
    KEY,
    JSON.stringify({
      version: 1,
      regions: readSaved(storage).filter((r) => r.key !== key),
    }),
  );
}
// region_1 is reused for other trips: geographic identity must be included.
export const savedKey = (id: string, point: [number, number]) =>
  `${id}:${point.map((v) => v.toFixed(5)).join(",")}`;
