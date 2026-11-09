/**
 * Tests for the hardware fit helpers (Step 6, MH-4).
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  FIT_LABEL_TEXT,
  fitBadgeClass,
  fitTitle,
  overBudgetDetails,
} from "@/lib/hardware-fit";

const DETAILS = {
  code: "over_budget",
  tag: "examplereason:8b",
  quantization: "Q4_K_M",
  label: "over_budget",
  need_gb: 6.2,
  budget_gb: 6,
  total_vram_gb: 8,
  headroom_percent: 75,
};

describe("hardware fit helpers", () => {
  it("names and colours each label", () => {
    expect(FIT_LABEL_TEXT.fits).toBe("Fits");
    expect(FIT_LABEL_TEXT.over_budget).toBe("Over budget");
    expect(FIT_LABEL_TEXT.too_large).toBe("Too large");
    expect(fitBadgeClass("fits")).toContain("text-success");
    expect(fitBadgeClass("over_budget")).toContain("text-warning");
    expect(fitBadgeClass("too_large")).toContain("text-destructive");
  });

  it("says where the memory need comes from", () => {
    expect(
      fitTitle({
        name: "a",
        need_gb: 5.35,
        label: "fits",
        source: "llmfit_plan",
      }),
    ).toBe("Needs about 5.3 GB (llmfit plan)");
    expect(
      fitTitle({
        name: "b",
        need_gb: 7.59,
        label: "over_budget",
        source: "rough_estimate",
      }),
    ).toBe("Needs about 7.6 GB (rough estimate from size)");
    expect(
      fitTitle({ name: "c", need_gb: null, label: "unknown", source: "none" }),
    ).toBe("No estimate for this model");
  });

  it("reads the details of an over-budget 409", () => {
    const error = new ApiError(409, "needs about 6.2 GB", DETAILS);
    expect(overBudgetDetails(error)).toEqual(DETAILS);
  });

  it("ignores every other error", () => {
    expect(overBudgetDetails(new ApiError(409, "busy"))).toBeNull();
    expect(
      overBudgetDetails(new ApiError(400, "blocked", { ...DETAILS })),
    ).toBeNull();
    expect(
      overBudgetDetails(
        new ApiError(409, "other", { ...DETAILS, code: "pull_running" }),
      ),
    ).toBeNull();
    expect(overBudgetDetails(new Error("network"))).toBeNull();
  });
});
