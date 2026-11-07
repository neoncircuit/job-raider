/**
 * Keep the split modules of Step 5 small (MH-4).
 *
 * The Cover Letter page was one 1,348-line file. This test fails when the page
 * or one of the modules that replaced it reaches the limit again.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "../..");
const LIMIT = 600;
const FOLDERS = ["src/app/cover-letter", "src/components/cover-letter"];
const FILES = ["src/lib/hooks/use-cover-letter-page.ts"];

/**
 * List the source files to check.
 *
 * @returns The paths, relative to the frontend folder.
 */
function checkedFiles(): string[] {
  const inFolders = FOLDERS.filter((folder) =>
    existsSync(join(ROOT, folder)),
  ).flatMap((folder) =>
    readdirSync(join(ROOT, folder))
      .filter((name) => /\.tsx?$/.test(name))
      .map((name) => `${folder}/${name}`),
  );
  return [
    ...inFolders,
    ...FILES.filter((file) => existsSync(join(ROOT, file))),
  ];
}

describe("module size", () => {
  it("checks the page, its hook, and its sections", () => {
    expect(checkedFiles()).toEqual(
      expect.arrayContaining([
        "src/app/cover-letter/page.tsx",
        "src/lib/hooks/use-cover-letter-page.ts",
      ]),
    );
  });

  it.each(checkedFiles())(`keeps %s under ${LIMIT} lines`, (file) => {
    const lines = readFileSync(join(ROOT, file), "utf-8").split("\n").length;

    expect(lines).toBeLessThan(LIMIT);
  });
});
