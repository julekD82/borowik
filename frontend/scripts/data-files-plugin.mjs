// Dane analizy (public/data) w trybie deweloperskim: serwowane prosto z dysku, poza obserwatorem plikow Vite.
// Obserwator nie ma tu nic do przeladowania (aplikacja pobiera dane fetch-em), a na Windows wywracal
// serwer bledem EBUSY, gdy launcher zapisywal migawke do trips/ (plik zablokowany w trakcie kopiowania).
// Vite serwuje pliki z public/ tylko z listy uzupelnianej przez obserwator, wiec po wylaczeniu obserwacji
// katalogu danych nowe pliki (np. swieza migawka) trzeba serwowac samemu -- inaczej bylyby dostepne
// dopiero po restarcie serwera.
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream";

const TYPES = {
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
};

function notFound(res) {
  res.statusCode = 404;
  res.end();
}

/** Middleware (connect): pliki spod `prefix` z katalogu `dataDir`; brak pliku = 404, reszta zapytan dalej. */
export function serveDataFiles(dataDir, prefix = "/data/", { openStream = createReadStream } = {}) {
  const root = path.resolve(dataDir);
  return async (req, res, next) => {
    const url = (req.url ?? "").split("?")[0];
    if (!url.startsWith(prefix)) return next();
    let relative;
    try {
      relative = decodeURIComponent(url.slice(prefix.length));
    } catch {
      return notFound(res);
    }
    const file = path.resolve(root, relative);
    // dev:lan jest widoczny w sieci -- nic spoza katalogu danych.
    if (!file.startsWith(root + path.sep)) return notFound(res);
    const info = await stat(file).catch(() => null);
    if (!info?.isFile()) return notFound(res);
    res.statusCode = 200;
    res.setHeader("Content-Type", TYPES[path.extname(file).toLowerCase()] ?? "application/octet-stream");
    res.setHeader("Content-Length", info.size);
    res.setHeader("Cache-Control", "no-cache");
    if (req.method === "HEAD") return res.end();
    // pipeline, nie pipe: przy przerwanym pobieraniu (przeladowanie strony, telefon w trybie LAN traci
    // zasieg) pipe zostawial plik otwarty na zawsze, a na Windows otwarty plik blokuje jego podmiane
    // przez sync-data (EPERM). pipeline zamyka plik przy bledzie lub zamknieciu polaczenia.
    pipeline(openStream(file), res, () => {});
  };
}

export function dataFilesPlugin() {
  return {
    name: "borowik-data-files",
    config: () => ({ server: { watch: { ignored: ["**/public/data/**"] } } }),
    configureServer(server) {
      server.middlewares.use(serveDataFiles(path.join(server.config.publicDir, "data"), `${server.config.base}data/`));
    },
  };
}
