/**
 * Tests for the start of the demo's service worker (Step 4, MH-3).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { startDemo } from "@/demo/start";

const start = vi.hoisted(() => vi.fn());
vi.mock("msw/browser", () => ({ setupWorker: () => ({ start }) }));

describe("startDemo", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    start.mockReset();
  });

  it("finds the worker on the base path, with the site as its scope", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/job-raider");

    await startDemo();

    expect(start).toHaveBeenCalledWith(
      expect.objectContaining({
        serviceWorker: {
          url: "/job-raider/mockServiceWorker.js",
          options: { scope: "/job-raider/" },
        },
      }),
    );
  });

  it("sends a static file request to the network", async () => {
    await startDemo();

    expect(start).toHaveBeenCalledWith(
      expect.objectContaining({ onUnhandledRequest: "bypass" }),
    );
  });

  it("stops when the worker cannot start", async () => {
    start.mockRejectedValue(new Error("blocked"));

    await expect(startDemo()).rejects.toThrow("blocked");
  });
});
