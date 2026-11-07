/**
 * Tests for the check that the server build has no demo code (Step 4, MH-4).
 */

import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DEMO_MARKERS, findDemoCode } from "../../scripts/find-demo-code.mjs";

describe("findDemoCode", () => {
  let folder = "";

  beforeEach(() => {
    folder = mkdtempSync(join(tmpdir(), "demo-code-"));
    mkdirSync(join(folder, "chunks"));
    writeFileSync(join(folder, "chunks", "clean.js"), "const page = 1;");
  });

  afterEach(() => {
    rmSync(folder, { recursive: true });
  });

  it("passes a clean build, and counts its files", () => {
    expect(findDemoCode([folder])).toEqual({ files: 1, found: [] });
  });

  it.each(DEMO_MARKERS)("finds %s in a subfolder", (marker) => {
    const file = join(folder, "chunks", "demo.js");
    writeFileSync(file, `const text = "${marker}";`);

    expect(findDemoCode([folder]).found).toEqual([`${file}: ${marker}`]);
  });

  it("reads no files in a folder that does not exist", () => {
    expect(findDemoCode([join(folder, "none")])).toEqual({
      files: 0,
      found: [],
    });
  });

  it("searches each folder", () => {
    const other = join(folder, "other");
    mkdirSync(other);
    writeFileSync(join(other, "demo.js"), "setupWorker();");

    const result = findDemoCode([join(folder, "chunks"), other]);

    expect(result.files).toBe(2);
    expect(result.found).toHaveLength(1);
  });
});
