/**
 * Serve the static demo as GitHub Pages does (Step 4, MH-4).
 *
 * Under the base path, `/x` serves `x`, `x.html`, or `x/index.html`. Any other
 * path gets `404.html`. Run `npm run build:demo` first, with
 * `NEXT_PUBLIC_BASE_PATH=/job-raider`.
 *
 * Usage: node scripts/serve-demo.mjs
 */

import { existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join } from "node:path";

const ROOT = "out";
const BASE_PATH = "/job-raider";
const PORT = Number(process.env.DEMO_PORT ?? 4599);
const TYPES = {
  ".css": "text/css",
  ".html": "text/html",
  ".ico": "image/x-icon",
  ".js": "text/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain",
  ".woff2": "font/woff2",
};

/**
 * Find the file for a URL path.
 *
 * @param {string} pathname - The URL path.
 * @returns {string | null} The file, or null when there is no file.
 */
function findFile(pathname) {
  if (!pathname.startsWith(BASE_PATH)) {
    return null;
  }
  const inside = pathname.slice(BASE_PATH.length);
  const options = [inside, `${inside}.html`, join(inside, "index.html")];
  for (const option of options) {
    const file = join(ROOT, option);
    if (existsSync(file) && statSync(file).isFile()) {
      return file;
    }
  }
  return null;
}

createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://localhost");
  const file = findFile(decodeURIComponent(url.pathname));
  response.writeHead(file ? 200 : 404, {
    "content-type": TYPES[extname(file ?? ".html")] ?? "text/html",
  });
  response.end(readFileSync(file ?? join(ROOT, "404.html")));
}).listen(PORT);
