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
