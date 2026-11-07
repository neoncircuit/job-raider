/**
 * Tests for the onboarding rules (Step 4, MH-5).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  hasReviewedShortlist,
  onboardingSteps,
  readOnboardingDismissed,
  saveOnboardingDismissed,
} from "@/lib/onboarding";
import type { OnboardingState } from "@/lib/onboarding";
import type { ApplicationSummary } from "@/lib/types/api";

const NOTHING: OnboardingState = {
  backend: false,
  model: false,
  profile: false,
  search: false,
  reviewed: false,
  tracked: false,
};

/**
 * Build an applications row.
 *
 * @param fields - The fields to change.
 * @returns The row.
 */
function row(fields: Partial<ApplicationSummary>): ApplicationSummary {
  return {
    current_status: "saved_bookmarked",
    is_bookmarked: false,
    is_hidden: false,
    ...fields,
  } as ApplicationSummary;
}

describe("onboardingSteps", () => {
  it("lists the six steps in order, each with its page", () => {
    expect(onboardingSteps(NOTHING).map((step) => step.href)).toEqual([
      "/settings",
      "/settings",
      "/profile",
      "/pipeline",
      "/jobs",
      "/applications",
    ]);
  });

  it.each(Object.keys(NOTHING) as (keyof OnboardingState)[])(
    "marks only %s as done",
    (field) => {
      const steps = onboardingSteps({ ...NOTHING, [field]: true });

      expect(steps.filter((step) => step.done).map((step) => step.id)).toEqual([
        field,
      ]);
    },
  );
});

describe("hasReviewedShortlist", () => {
  it("is false with no rows", () => {
    expect(hasReviewedShortlist([])).toBe(false);
  });

  it("is true for a saved, a hidden, or a tracked job", () => {
    expect(hasReviewedShortlist([row({ is_bookmarked: true })])).toBe(true);
    expect(hasReviewedShortlist([row({ is_hidden: true })])).toBe(true);
    expect(hasReviewedShortlist([row({ current_status: "applied" })])).toBe(
      true,
    );
  });

  it("is false for a row with no action", () => {
    expect(hasReviewedShortlist([row({})])).toBe(false);
  });
});

describe("dismissed state", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("starts as not dismissed, and remembers a dismiss", () => {
    expect(readOnboardingDismissed()).toBe(false);

    saveOnboardingDismissed();

    expect(readOnboardingDismissed()).toBe(true);
  });

  it("works when the browser blocks storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => saveOnboardingDismissed()).not.toThrow();
    expect(readOnboardingDismissed()).toBe(false);
  });
});
