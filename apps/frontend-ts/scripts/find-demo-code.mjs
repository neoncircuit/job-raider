/**
 * Check that the server build has no demo code (Step 4, MH-4).
 *
 * Next.js drops the demo code only when `NEXT_PUBLIC_DEMO_MODE` has a value at
 * build time. This check keeps that true. Run it after `npm run build`.
 *
 * Usage: node scripts/find-demo-code.mjs
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const BUILD_FOLDERS = [".next/static", ".next/server"];

/** Text that occurs only in MSW and in the demo code. */
export const DEMO_MARKERS = [
  "mockServiceWorker",
  "setupWorker",
  "demo-rk-012",
  "needs the local backend",
];

/**
 * List the files in a folder and its subfolders.
 *
 * @param {string} folder - The folder.
 * @returns {string[]} The file paths, or none when the folder does not exist.
 */
function listFiles(folder) {
  if (!existsSync(folder)) {
    return [];
  }
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? listFiles(path) : [path];
  });
}

/**
 * Search build folders for demo code.
 *
 * @param {string[]} folders - The build folders.
 * @returns {{ files: number, found: string[] }} The number of files read, and
 *   one line for each marker in each file.
 */
export function findDemoCode(folders) {
  const files = folders.flatMap(listFiles);
  const found = files.flatMap((file) => {
    const text = readFileSync(file, "utf-8");
    return DEMO_MARKERS.filter((marker) => text.includes(marker)).map(
      (marker) => `${file}: ${marker}`,
    );
  });
  return { files: files.length, found };
}

/**
 * Run the check on the server build, and set the exit code.
 *
 * @returns {void}
 */
function main() {
  const { files, found } = findDemoCode(BUILD_FOLDERS);
  if (files === 0) {
    console.error("No build found. Run npm run build first.");
    process.exitCode = 2;
    return;
  }
  if (found.length > 0) {
    console.error(`Demo code in the server build:\n${found.join("\n")}`);
    process.exitCode = 1;
    return;
  }
  console.log(`No demo code in ${files} files.`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
