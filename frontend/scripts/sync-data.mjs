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

  // Detail export is optional too, same reasoning as regions above (plan
  // 2.1 step B3) -- but a detail entry references only its OWN stand_id,
  // not a list of others, so the check is simpler than regions'.
  let detailsRaw = null;
  try {
    detailsRaw = await readFile(
      path.join(source, `details_${day}.json`),
      "utf8",
    );
  } catch {
    detailsRaw = null;
  }
  let details = null;
  if (detailsRaw !== null) {
    try {
      details = JSON.parse(detailsRaw);
    } catch {
      throw new Error(`Plik details_${day}.json jest uszkodzony.`);
    }
    if (!Array.isArray(details))
      throw new Error(`Niepoprawny format details_${day}.json.`);
    for (const item of details) {
      if (item.day !== day)
        throw new Error("Niezgodna data wewnątrz pliku szczegółów.");
      if (!geometryIds.has(item.stand_id))
        throw new Error(
          "Szczegóły odwołują się do wydzielenia spoza zsynchronizowanego zestawu.",
        );
    }
  }

  // Plan A2 Plan-B: conditions_{day}.json is optional too (fact-only rain + per-day F).
  let conditionsRaw = null;
  try {
    conditionsRaw = await readFile(path.join(source, `conditions_${day}.json`), "utf8");
  } catch {
    conditionsRaw = null;
  }
  let conditions = null;
  if (conditionsRaw !== null) {
    try {
      conditions = JSON.parse(conditionsRaw);
    } catch {
      throw new Error(`Plik conditions_${day}.json jest uszkodzony.`);
    }
    if (!conditions || typeof conditions !== "object" || conditions.day !== day || !Array.isArray(conditions.days))
      throw new Error(`Niepoprawny format conditions_${day}.json.`);
  }

  // Plan wdrozenia 1.1: run_manifest_{day}.json is optional too (older
  // exports predate it) -- same "validate, sync as manifest.json, drop if
  // absent" pattern as conditions above.
  let manifestRaw = null;
  try {
    manifestRaw = await readFile(path.join(source, `run_manifest_${day}.json`), "utf8");
  } catch {
    manifestRaw = null;
  }
  let manifest = null;
  if (manifestRaw !== null) {
    try {
      manifest = JSON.parse(manifestRaw);
    } catch {
      throw new Error(`Plik run_manifest_${day}.json jest uszkodzony.`);
    }
    if (!manifest || typeof manifest !== "object" || manifest.day !== day)
      throw new Error(`Niepoprawny format run_manifest_${day}.json.`);
  }

  await mkdir(target, { recursive: true });
  const targets = ["scores.json", "stands.geojson"];
  const allContents = [...contents];
  if (regions !== null) {
    targets.push("regions.json");
    allContents.push(regionsRaw);
  }
  if (details !== null) {
    targets.push("details.json");
    allContents.push(detailsRaw);
  }
  if (conditions !== null) {
    targets.push("conditions.json");
    allContents.push(conditionsRaw);
  }
  if (manifest !== null) {
    targets.push("manifest.json");
    allContents.push(manifestRaw);
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
  if (details === null)
    await rm(path.join(target, "details.json"), { force: true });
  if (conditions === null)
    await rm(path.join(target, "conditions.json"), { force: true });
  if (manifest === null)
    await rm(path.join(target, "manifest.json"), { force: true });
  return {
    day,
    stands: scores.length,
    regions: regions?.length ?? 0,
    details: details?.length ?? 0,
    conditions: conditions === null ? 0 : 1,
    manifest: manifest === null ? 0 : 1,
  };
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
