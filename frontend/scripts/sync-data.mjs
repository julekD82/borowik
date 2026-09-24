import {
  readdir,
  readFile,
  mkdir,
  writeFile,
  rename,
  rm,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export async function syncData(source, target) {
  const files = await readdir(source);
  const days = files
    .map((name) => /^scores_(\d{4}-\d{2}-\d{2})\.json$/.exec(name)?.[1])
    .filter(Boolean)
    .sort();
  const day = days.at(-1);
  if (!day)
    throw new Error(
      "Brak wyników analizy. Najpierw uruchom pipeline.prepare_trip.",
    );
  const names = [`scores_${day}.json`, "stands.geojson"];
  const contents = await Promise.all(
    names.map(async (name) => {
      try {
        return await readFile(path.join(source, name), "utf8");
      } catch {
        throw new Error(
          `Brak ${name}. Potrzebny jest kompletny eksport z tego samego uruchomienia.`,
        );
      }
    }),
  );
  const [scores, stands] = contents.map((s) => JSON.parse(s));
  if (
    !Array.isArray(scores) ||
    stands.type !== "FeatureCollection" ||
    !Array.isArray(stands.features)
  )
    throw new Error("Niepoprawny format eksportu.");
  if (scores.some((r) => r.day !== day))
    throw new Error("Niezgodna data wewnątrz plików.");
  const scoreIds = new Set(scores.map((s) => s.stand_id));
  const geometryIds = new Set(
    stands.features.map((f) => f.properties?.stand_id),
  );
  if (
    scoreIds.size !== scores.length ||
    geometryIds.size !== stands.features.length ||
    scoreIds.size !== geometryIds.size ||
    [...scoreIds].some((id) => !geometryIds.has(id))
  )
    throw new Error("Wyniki i geometrie dotyczą różnych zestawów wydzieleń.");

  // Region export is optional -- older exports, or exports from before
  // grouping was re-enabled, won't have a same-day regions file. But if
  // one exists for this exact day, it must be valid and reference only
  // stands that are actually in this synced bundle.
  let regionsRaw = null;
  try {
    regionsRaw = await readFile(
      path.join(source, `regions_${day}.json`),
      "utf8",
    );
  } catch {
    regionsRaw = null;
  }
  let regions = null;
  if (regionsRaw !== null) {
    try {
      regions = JSON.parse(regionsRaw);
    } catch {
      throw new Error(`Plik regions_${day}.json jest uszkodzony.`);
    }
    if (!Array.isArray(regions))
      throw new Error(`Niepoprawny format regions_${day}.json.`);
    for (const region of regions) {
      if (region.day !== day)
        throw new Error("Niezgodna data wewnątrz pliku rejonów.");
      if (
        !Array.isArray(region.stand_ids) ||
        region.stand_ids.some((id) => !geometryIds.has(id))
      )
        throw new Error(
          "Rejon odwołuje się do wydzielenia spoza zsynchronizowanego zestawu.",
        );
    }
  }

  await mkdir(target, { recursive: true });
  const targets = ["scores.json", "stands.geojson"];
  const allContents = [...contents];
  if (regions !== null) {
    targets.push("regions.json");
    allContents.push(regionsRaw);
  }
  // Validate the entire bundle before replacing any existing public file.
  for (let i = 0; i < targets.length; i++)
    await writeFile(
      path.join(target, `${targets[i]}.tmp`),
      allContents[i],
      "utf8",
    );
  for (const name of targets)
    await rename(path.join(target, `${name}.tmp`), path.join(target, name));
  if (regions === null)
    // No same-day regions file -- drop any regions.json left over from a
    // previous sync, so the toggle doesn't show a different day's regions
    // next to fresh per-stand data.
    await rm(path.join(target, "regions.json"), { force: true });
  return { day, stands: scores.length, regions: regions?.length ?? 0 };
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const frontend = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
  );
  const source = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.resolve(frontend, "../notebooks/output");
  try {
    const result = await syncData(source, path.join(frontend, "public/data"));
    console.log(`Gotowe: ${result.day}, ${result.stands} wydzieleń.`);
    if (
      JSON.parse(
        await readFile(path.join(source, `scores_${result.day}.json`), "utf8"),
      ).some((s) => s.d_park_m === undefined)
    )
      console.warn(
        "Starszy eksport nie zawiera odległości. Interfejs pokaże „Brak danych”; kolejne prepare_trip wyeksportuje d_park_m.",
      );
  } catch (error) {
    console.error(`Synchronizacja nieudana: ${error.message}`);
    process.exitCode = 1;
  }
}
