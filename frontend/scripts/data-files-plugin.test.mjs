import { afterEach, expect, it } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { dataFilesPlugin, serveDataFiles } from "./data-files-plugin.mjs";

const cleanup = [];
afterEach(async () => {
  for (const step of cleanup.splice(0)) await step();
});

async function server() {
  const root = await mkdtemp(path.join(os.tmpdir(), "borowik-data-"));
  const dataDir = path.join(root, "public", "data");
  await mkdir(path.join(dataDir, "trips"), { recursive: true });
  await writeFile(path.join(root, "public", "tajne.txt"), "poza danymi");
  const handler = serveDataFiles(dataDir, "/data/");
  const srv = http.createServer((req, res) =>
    handler(req, res, () => {
      res.statusCode = 299; // „dalej” -- reszta serwera Vite
      res.end();
    }),
  );
  await new Promise((resolve) => srv.listen(0, "127.0.0.1", resolve));
  cleanup.push(() => new Promise((resolve) => srv.close(resolve)), () => rm(root, { recursive: true, force: true }));
  const base = `http://127.0.0.1:${srv.address().port}`;
  return { dataDir, get: (p) => fetch(base + p) };
}

it("serwuje dane z dysku jako JSON, także plik dodany po starcie serwera (nowa migawka)", async () => {
  const { dataDir, get } = await server();
  await mkdir(path.join(dataDir, "trips", "zawadzkie-01-10"));
  await writeFile(path.join(dataDir, "trips", "zawadzkie-01-10", "scores.json"), '[{"stand_id":"A"}]');
  const res = await get("/data/trips/zawadzkie-01-10/scores.json");
  expect(res.status).toBe(200);
  expect(res.headers.get("content-type")).toContain("json");
  expect(await res.json()).toEqual([{ stand_id: "A" }]);
  await writeFile(path.join(dataDir, "stands.geojson"), "{}");
  expect((await get("/data/stands.geojson")).headers.get("content-type")).toContain("json");
});

it("brak pliku albo katalog to 404 (aplikacja traktuje to jak brak pliku); poza /data/ idzie dalej", async () => {
  const { get } = await server();
  expect((await get("/data/nie-ma.json")).status).toBe(404);
  expect((await get("/data/trips/")).status).toBe(404);
  expect((await get("/src/index.tsx")).status).toBe(299);
});

it("nie wychodzi poza katalog danych (dev:lan jest widoczny w sieci)", async () => {
  const { get } = await server();
  for (const p of ["/data/..%2ftajne.txt", "/data/..%5ctajne.txt", "/data/trips/..%2f..%2ftajne.txt"]) {
    const res = await get(p);
    expect(res.status).not.toBe(200);
    expect(await res.text()).not.toContain("poza danymi");
  }
});

it("obserwator plików Vite pomija katalog danych", () => {
  expect(dataFilesPlugin().config().server.watch.ignored).toContain("**/public/data/**");
});
