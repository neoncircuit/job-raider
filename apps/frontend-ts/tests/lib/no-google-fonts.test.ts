/**
 * Self-hosted fonts guard.
 *
 * `next/font/google` downloads the fonts at build time, and that download
 * sometimes failed in CI. The fonts come from the Fontsource packages through
 * `next/font/local` instead, so no source file may import `next/font/google`.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..", "..", "src");

/**
 * List the TypeScript files under a folder.
 *
 * @param dir - Folder to read.
 * @returns Paths of the .ts and .tsx files.
 */
function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("self-hosted fonts", () => {
  it("imports no font from Google at build time", () => {
    const offenders = sourceFiles(SRC).filter((path) =>
      readFileSync(path, "utf8").includes("next/font/google"),
    );
    expect(offenders).toEqual([]);
  });

  it("loads IBM Plex from the Fontsource packages", () => {
    const layout = readFileSync(join(SRC, "app", "layout.tsx"), "utf8");
    expect(layout).toContain('from "next/font/local"');
    expect(layout).toContain("@fontsource/ibm-plex-sans/files/");
    expect(layout).toContain("@fontsource/ibm-plex-mono/files/");
  });

  it("lets next/font set the font variables", () => {
    // A :root value such as "IBM Plex Sans" names a family that only the
    // Google loader made, so the text fell back to a system font.
    const css = readFileSync(join(SRC, "app", "globals.css"), "utf8");
    expect(css).not.toMatch(/--font-ibm-plex-(sans|mono)\s*:/);
  });
});
