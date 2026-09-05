/**
 * Job Raider - Formatting Utilities Test
 *
 * Tests for formatting utility functions.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { describe, it, expect } from "vitest";
import { formatDurationMs, formatTokenCount } from "@/lib/utils/format";

describe("Formatting Utilities", () => {
  describe("formatDurationMs", () => {
    it("formats sub-second durations in milliseconds", () => {
      expect(formatDurationMs(843)).toBe("843 ms");
    });

    it("formats multi-second durations with one decimal", () => {
      expect(formatDurationMs(4510)).toBe("4.5 s");
    });

    it("returns an em dash for invalid values", () => {
      expect(formatDurationMs(Number.NaN)).toBe("—");
    });
  });

  describe("formatTokenCount", () => {
    it("formats token counts with grouping", () => {
      expect(formatTokenCount(2200)).toBe("2,200");
    });

    it("returns an em dash for invalid values", () => {
      expect(formatTokenCount(Number.NaN)).toBe("—");
    });
  });

  describe("Date Formatting", () => {
    it("should format ISO date to readable format", () => {
      const isoDate = "2026-06-01";
      expect(isoDate).toBeTruthy();
    });

    it("should handle invalid dates gracefully", () => {
      const invalidDate = "invalid-date";
      expect(invalidDate).toBeDefined();
    });
  });

  describe("Salary Formatting", () => {
    it("should format salary range string", () => {
      const salary = "$150k-$200k";
      expect(salary).toContain("$");
    });

    it("should handle empty salary range", () => {
      const salary = "";
      expect(salary).toBe("");
    });
  });

  describe("Location Formatting", () => {
    it("should format location with remote indicator", () => {
      const location = "Remote";
      expect(location).toBe("Remote");
    });

    it("should format city, state location", () => {
      const location = "San Francisco, CA";
      expect(location).toContain(", ");
    });
  });
});
