import { afterEach, expect, it } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { syncData } from "./sync-data.mjs";
const roots = [];
afterEach(async () => {
  for (const dir of roots.splice(0))
    await rm(dir, { recursive: true, force: true });
});
async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), "borowik-sync-"));
  roots.push(root);
  const source = path.join(root, "source"),
    target = path.join(root, "target");
  await mkdir(source);
  await writeFile(
    path.join(source, "scores_2026-09-24.json"),
    JSON.stringify([{ day: "2026-09-24", stand_id: "A" }]),
  );
  await writeFile(
    path.join(source, "stands.geojson"),
    JSON.stringify({
      type: "FeatureCollection",
      features: [{ properties: { stand_id: "A" } }],
    }),
  );
  return { source, target };
}
it("copies one complete same-day bundle", async () => {
  const { source, target } = await fixture();
  expect(await syncData(source, target)).toEqual({
    day: "2026-09-24",
    stands: 1,
    regions: 0,
    regionsNoPressure: 0,
    details: 0,
    conditions: 0,
    manifest: 0,
    accessPoints: 0,
    forestRoads: 0,
  });
  expect(
    JSON.parse(await readFile(path.join(target, "scores.json"), "utf8"))[0]
      .stand_id,
  ).toBe("A");
});
it("ignores historical region exports, even newer malformed ones", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "regions_2026-09-25.json"), "invalid");
  expect((await syncData(source, target)).day).toBe("2026-09-24");
});
it("does not replace a good bundle with mismatched geometries", async () => {
  const { source, target } = await fixture();
  await syncData(source, target);
  await writeFile(
    path.join(source, "stands.geojson"),
    JSON.stringify({ type: "FeatureCollection", features: [] }),
  );
  await expect(syncData(source, target)).rejects.toThrow("różnych");
  expect(
    JSON.parse(await readFile(path.join(target, "stands.geojson"), "utf8"))
      .features,
  ).toHaveLength(1);
});
it("syncs a same-day regions file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "regions_2026-09-24.json"),
    JSON.stringify([
      { region_id: "region_1", day: "2026-09-24", stand_ids: ["A"] },
    ]),
  );
  const result = await syncData(source, target);
  expect(result.regions).toBe(1);
  expect(
    JSON.parse(await readFile(path.join(target, "regions.json"), "utf8"))[0]
      .region_id,
  ).toBe("region_1");
});
it("rejects a same-day regions file that references an unknown stand_id", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "regions_2026-09-24.json"),
    JSON.stringify([
      { region_id: "region_1", day: "2026-09-24", stand_ids: ["A", "GHOST"] },
    ]),
  );
  await expect(syncData(source, target)).rejects.toThrow();
  await expect(
    readFile(path.join(target, "regions.json"), "utf8"),
  ).rejects.toThrow();
});
it("rejects a same-day regions file that is not valid JSON, without touching scores/geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "regions_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
  await expect(
    readFile(path.join(target, "scores.json"), "utf8"),
  ).rejects.toThrow();
});
it("removes a stale regions.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "regions_2026-09-24.json"),
    JSON.stringify([
      { region_id: "region_1", day: "2026-09-24", stand_ids: ["A"] },
    ]),
  );
  await syncData(source, target);
  await rm(path.join(source, "regions_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.regions).toBe(0);
  await expect(
    readFile(path.join(target, "regions.json"), "utf8"),
  ).rejects.toThrow();
});

// Faza UI.1: regions_bez_presji_{day}.json -> regions_bez_presji.json, optional, walidowany jak regions.
it("syncs a same-day regions_bez_presji file and removes a stale one later", async () => {
  const { source, target } = await fixture();
  const file = path.join(source, "regions_bez_presji_2026-09-24.json");
  await writeFile(
    file,
    JSON.stringify([{ region_id: "region_1", day: "2026-09-24", stand_ids: ["A"] }]),
  );
  const result = await syncData(source, target);
  expect(result.regionsNoPressure).toBe(1);
  expect(
    JSON.parse(await readFile(path.join(target, "regions_bez_presji.json"), "utf8"))[0].region_id,
  ).toBe("region_1");
  await rm(file);
  expect((await syncData(source, target)).regionsNoPressure).toBe(0);
  await expect(readFile(path.join(target, "regions_bez_presji.json"), "utf8")).rejects.toThrow();
});
it("rejects a regions_bez_presji file that references an unknown stand_id", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "regions_bez_presji_2026-09-24.json"),
    JSON.stringify([{ region_id: "region_1", day: "2026-09-24", stand_ids: ["A", "GHOST"] }]),
  );
  await expect(syncData(source, target)).rejects.toThrow("bez presji");
  await expect(readFile(path.join(target, "scores.json"), "utf8")).rejects.toThrow();
});

// Plan 2.1 step B3: details_{day}.json -> details.json, same optional
// same-day-or-absent pattern as regions above.
it("syncs a same-day details file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "details_2026-09-24.json"),
    JSON.stringify([{ stand_id: "A", day: "2026-09-24", drzew_species: [] }]),
  );
  const result = await syncData(source, target);
  expect(result.details).toBe(1);
  expect(
    JSON.parse(await readFile(path.join(target, "details.json"), "utf8"))[0]
      .stand_id,
  ).toBe("A");
});
it("rejects a same-day details file that references an unknown stand_id", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "details_2026-09-24.json"),
    JSON.stringify([{ stand_id: "GHOST", day: "2026-09-24" }]),
  );
  await expect(syncData(source, target)).rejects.toThrow();
  await expect(
    readFile(path.join(target, "details.json"), "utf8"),
  ).rejects.toThrow();
});
it("rejects a same-day details file that is not valid JSON, without touching scores/geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "details_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
  await expect(
    readFile(path.join(target, "scores.json"), "utf8"),
  ).rejects.toThrow();
});
it("removes a stale details.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(
    path.join(source, "details_2026-09-24.json"),
    JSON.stringify([{ stand_id: "A", day: "2026-09-24" }]),
  );
  await syncData(source, target);
  await rm(path.join(source, "details_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.details).toBe(0);
  await expect(
    readFile(path.join(target, "details.json"), "utf8"),
  ).rejects.toThrow();
});

// Plan A2 Plan-B: conditions_{day}.json -> conditions.json, optional like regions/details.
const conditionsFile = (day = "2026-09-24") =>
  JSON.stringify({ day, summary: "Ostatni większy deszcz: 21–22.09 (28.5 mm), 5 dni temu", days: [] });

it("syncs a same-day conditions file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile());
  const result = await syncData(source, target);
  expect(result.conditions).toBe(1);
  expect(JSON.parse(await readFile(path.join(target, "conditions.json"), "utf8")).summary).toContain("deszcz");
});

it("rejects a same-day conditions file from another day or malformed", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile("2026-09-23"));
  await expect(syncData(source, target)).rejects.toThrow();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
});

it("accepts conditions with a daily array and rejects a malformed daily field", async () => {
  const { source, target } = await fixture();
  const withDaily = (daily) =>
    JSON.stringify({ day: "2026-09-24", summary: "x", days: [], daily });
  await writeFile(path.join(source, "conditions_2026-09-24.json"), withDaily([{ date: "2026-09-24" }]));
  expect((await syncData(source, target)).conditions).toBe(1);
  await writeFile(path.join(source, "conditions_2026-09-24.json"), withDaily("zle"));
  await expect(syncData(source, target)).rejects.toThrow("conditions");
});

it("removes a stale conditions.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile());
  await syncData(source, target);
  await rm(path.join(source, "conditions_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.conditions).toBe(0);
  await expect(readFile(path.join(target, "conditions.json"), "utf8")).rejects.toThrow();
});

// Plan wdrozenia 1.1: run_manifest_{day}.json -> manifest.json, optional like conditions.
const manifestFile = (day = "2026-09-24") =>
  JSON.stringify({ day, run_id: "abc123", commit: "deadbeef", sources: {}, counts: {} });

it("syncs a same-day manifest file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "run_manifest_2026-09-24.json"), manifestFile());
  const result = await syncData(source, target);
  expect(result.manifest).toBe(1);
  expect(JSON.parse(await readFile(path.join(target, "manifest.json"), "utf8")).run_id).toBe("abc123");
});

it("rejects a same-day manifest file from another day or malformed", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "run_manifest_2026-09-24.json"), manifestFile("2026-09-23"));
  await expect(syncData(source, target)).rejects.toThrow();
  await writeFile(path.join(source, "run_manifest_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
});

it("removes a stale manifest.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "run_manifest_2026-09-24.json"), manifestFile());
  await syncData(source, target);
  await rm(path.join(source, "run_manifest_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.manifest).toBe(0);
  await expect(readFile(path.join(target, "manifest.json"), "utf8")).rejects.toThrow();
});

// Faza 3.5: access_points_{day}.geojson / forest_roads_{day}.geojson -> optional map layers.
const layerFile = (features = []) => JSON.stringify({ type: "FeatureCollection", features });

it("syncs same-day access layers under day-less names", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "access_points_2026-09-24.geojson"), layerFile([{ type: "Feature" }]));
  await writeFile(path.join(source, "forest_roads_2026-09-24.geojson"), layerFile());
  const result = await syncData(source, target);
  expect([result.accessPoints, result.forestRoads]).toEqual([1, 1]);
  expect(JSON.parse(await readFile(path.join(target, "access_points.json"), "utf8")).features).toHaveLength(1);
  expect(JSON.parse(await readFile(path.join(target, "forest_roads.json"), "utf8")).type).toBe("FeatureCollection");
});

it("rejects a malformed access layer without touching the previous public files", async () => {
  const { source, target } = await fixture();
  await syncData(source, target);
  await writeFile(path.join(source, "access_points_2026-09-24.geojson"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
  await writeFile(path.join(source, "access_points_2026-09-24.geojson"), JSON.stringify({ type: "Feature" }));
  await expect(syncData(source, target)).rejects.toThrow();
});

it("removes stale access layers from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "forest_roads_2026-09-24.geojson"), layerFile());
  await syncData(source, target);
  await rm(path.join(source, "forest_roads_2026-09-24.geojson"));
  const result = await syncData(source, target);
  expect(result.forestRoads).toBe(0);
  await expect(readFile(path.join(target, "forest_roads.json"), "utf8")).rejects.toThrow();
});
it("retries a rename blocked by another process (Windows EPERM) and then succeeds", async () => {
  const { renameWithRetry } = await import("./sync-data.mjs");
  const calls = [];
  const sleeps = [];
  const renameFn = async (from, to) => {
    calls.push([from, to]);
    if (calls.length < 3) throw Object.assign(new Error("locked"), { code: "EPERM" });
  };
  await renameWithRetry("a.tmp", "a", { renameFn, delays: [1, 2, 3], sleep: async (ms) => sleeps.push(ms) });
  expect(calls).toHaveLength(3);
  expect(sleeps).toEqual([1, 2]);
});
it("does not retry other rename errors and gives up after the last delay", async () => {
  const { renameWithRetry } = await import("./sync-data.mjs");
  let n = 0;
  const missing = async () => { n++; throw Object.assign(new Error("missing"), { code: "ENOENT" }); };
  await expect(renameWithRetry("a.tmp", "a", { renameFn: missing, sleep: async () => {} })).rejects.toThrow("missing");
  expect(n).toBe(1);
  n = 0;
  const locked = async () => { n++; throw Object.assign(new Error("locked"), { code: "EBUSY" }); };
  await expect(renameWithRetry("a.tmp", "a", { renameFn: locked, delays: [1, 1], sleep: async () => {} })).rejects.toThrow("locked");
  expect(n).toBe(3);
});
it("reports a mixed public bundle when a later file stays locked", async () => {
  const { source, target } = await fixture();
  const { rename } = await import("node:fs/promises");
  const renameFn = async (from, to) => {
    if (to.endsWith("stands.geojson")) throw Object.assign(new Error("locked"), { code: "EPERM" });
    return rename(from, to);
  };
  await expect(syncData(source, target, { renameFn, delays: [1], sleep: async () => {} })).rejects.toThrow(
    /stands\.geojson \(EPERM\).*scores\.json.*NIESPÓJNE/,
  );
});
