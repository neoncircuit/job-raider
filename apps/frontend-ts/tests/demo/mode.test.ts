/**
 * Tests for the demo mode rules (Step 4, MH-3).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { DEMO_HIDDEN_ROUTES, isDemoMode, visibleNavItems } from "@/demo/mode";

const ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/career-coach", label: "Career Coach" },
  { href: "/assessment", label: "Assessment" },
  { href: "/resume-analysis", label: "Resume Analysis" },
  { href: "/linkedin-analysis", label: "LinkedIn Analysis" },
  { href: "/logs", label: "Logs" },
];

describe("demo mode", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("is off unless the flag is 1", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
    expect(isDemoMode()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "0");
    expect(isDemoMode()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    expect(isDemoMode()).toBe(true);
  });

  it("keeps every sidebar item in the server build", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
    expect(visibleNavItems(ITEMS)).toEqual(ITEMS);
  });

  it("hides the pages that need a backend in the demo", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    expect(visibleNavItems(ITEMS).map((item) => item.href)).toEqual([
      "/dashboard",
      "/jobs",
    ]);
  });

  it("keeps the core pages in the demo", () => {
    for (const href of [
      "/dashboard",
      "/pipeline",
      "/jobs",
      "/applications",
      "/cover-letter",
      "/metrics",
      "/settings",
    ]) {
      expect(DEMO_HIDDEN_ROUTES.has(href)).toBe(false);
    }
  });
});
