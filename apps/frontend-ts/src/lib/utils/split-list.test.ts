/**
 * Tests for comma-only list splitting.
 *
 * Before 2026-10-19 the Pipeline form and Jobs search split on spaces too,
 * so "New York" became ["New", "York"] and the backend searched "New".
 */

import { describe, expect, it } from "vitest";

import { splitList } from "@/lib/utils/split-list";

describe("splitList", () => {
  it("keeps multi-word terms whole", () => {
    expect(splitList("New York, Remote")).toEqual(["New York", "Remote"]);
    expect(splitList("python engineer, machine learning")).toEqual([
      "python engineer",
      "machine learning",
    ]);
  });

  it("trims spaces and drops empty terms", () => {
    expect(splitList("  Singapore ,, , Remote  ")).toEqual([
      "Singapore",
      "Remote",
    ]);
  });

  it("returns an empty list for blank input", () => {
    expect(splitList("   ")).toEqual([]);
  });
});
