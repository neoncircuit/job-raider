/**
 * Tests for the two builds in `next.config.ts` (Step 4, MH-1).
 *
 * The server build must stay as it was. The demo build is a static site, so
 * it must leave out the proxy route, which needs a server.
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";

import type { NextConfig } from "next";
import { afterEach, describe, expect, it, vi } from "vitest";

const PROXY_ROUTE = resolve(
  __dirname,
  "../../src/app/api/proxy/[...path]/route.ts",
);

/**
 * Load `next.config.ts` again, so it reads the current environment.
 *
 * @returns The config.
 */
async function loadConfig(): Promise<NextConfig> {
  vi.resetModules();
  const loaded = await import("../../next.config");
  return loaded.default;
}

/**
 * Check that a config is the server build.
 *
 * @param config - The config.
 */
async function expectServerBuild(config: NextConfig): Promise<void> {
  expect(config.output).toBe("standalone");
  expect(config.basePath).toBeUndefined();
  expect(config.pageExtensions).toBeUndefined();
  expect(await config.redirects?.()).toEqual([
    { source: "/", destination: "/dashboard", permanent: false },
  ]);
}

describe("next.config", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("builds the server app by default", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
    await expectServerBuild(await loadConfig());
  });

  it("builds the server app when the demo flag is not 1", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "0");
    await expectServerBuild(await loadConfig());
  });

  it("exports a static site in demo mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    const config = await loadConfig();
    expect(config.output).toBe("export");
    expect(config.basePath).toBe("");
    expect(config.redirects).toBeUndefined();
  });

  it("uses the base path of the host in demo mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/job-raider");
    expect((await loadConfig()).basePath).toBe("/job-raider");
  });

  it("leaves the proxy route out of the demo routes", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    const config = await loadConfig();
    expect(existsSync(PROXY_ROUTE)).toBe(true);
    expect(config.pageExtensions).toEqual(["tsx"]);
  });
});
