/**
 * Tests for the MSW handlers of the demo (Step 4, MH-3).
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  demoApplications,
  demoHardwareFit,
  demoHealth,
  demoHistory,
  demoLetter,
  demoMetrics,
  demoModels,
  demoOllamaModels,
  demoProfile,
  demoResources,
  demoSettings,
  demoShortlist,
} from "@/demo/data";
import { handlers, NOT_IN_DEMO, ONE_SAMPLE_LETTER } from "@/demo/handlers";
import { canRetry } from "@/lib/api/client";

import { server } from "../setup/globals";

const BASE = "http://localhost:3000/job-raider/api/proxy";
const NO_BASE = "http://localhost:3000/api/proxy";

/**
 * Call the demo API.
 *
 * @param method - The HTTP method.
 * @param path - The backend path.
 * @returns The status and the parsed body.
 */
async function call(
  method: string,
  path: string,
): Promise<{ status: number; body: unknown }> {
  const response = await fetch(`${NO_BASE}${path}`, { method });
  return { status: response.status, body: await response.json() };
}

describe("demo handlers", () => {
  beforeEach(() => {
    server.use(...handlers);
  });

  it.each([
    ["/health", demoHealth],
    ["/health/resources", demoResources],
    ["/metrics/summary", demoMetrics],
    ["/pipeline/history", demoHistory],
    ["/pipeline/shortlist/latest", demoShortlist],
    ["/profile", demoProfile],
    ["/settings/", demoSettings],
    ["/settings/models", demoModels],
    ["/settings/ollama/models", demoOllamaModels],
    ["/hardware/fit", demoHardwareFit],
    ["/applications/dashboard", demoApplications],
    ["/jobs/sources", { sources: ["sample"] }],
  ])("serves %s", async (path, expected) => {
    expect(await call("GET", path)).toEqual({ status: 200, body: expected });
  });

  it("serves a request with a base path in front", async () => {
    const response = await fetch(`${BASE}/health`);
    expect(response.status).toBe(200);
  });

  it("reports no invented host readings", () => {
    expect(demoResources.gpu).toBeNull();
    expect(demoResources.cpu.percent).toBeNull();
    expect(demoSettings.api_config.cloud_fallback_provider).toBe("none");
  });

  it("serves one job of the shortlist", async () => {
    const job = demoShortlist.jobs[3];
    expect(await call("GET", `/jobs/${job.job_id}`)).toEqual({
      status: 200,
      body: job,
    });
  });

  it("serves the shortlist as the job search", async () => {
    expect(await call("POST", "/jobs/search")).toEqual({
      status: 200,
      body: { total: demoShortlist.jobs.length, jobs: demoShortlist.jobs },
    });
  });

  it("serves one application with empty history", async () => {
    const row = demoApplications.applications[1];
    const { status, body } = await call(
      "GET",
      `/applications/${row.application_id}`,
    );
    expect(status).toBe(200);
    expect(body).toEqual({
      ...row,
      interviews: [],
      timeline_notes: [],
      metadata: {},
    });
  });

  it("serves the sample letter for its own job only", async () => {
    const own = await call("POST", `/jobs/${demoLetter.job_id}/cover-letter`);
    const other = await call(
      "POST",
      `/jobs/${demoShortlist.jobs[1].job_id}/cover-letter`,
    );

    expect(own).toEqual({ status: 200, body: demoLetter });
    expect(other).toEqual({
      status: 501,
      body: { detail: ONE_SAMPLE_LETTER },
    });
  });

  it("points a pasted job at the sample letter", async () => {
    expect(await call("POST", "/cover-letter/manual")).toEqual({
      status: 501,
      body: { detail: ONE_SAMPLE_LETTER },
    });
  });

  it.each([
    ["GET", "/jobs/rk-999"],
    ["GET", "/applications/none"],
    ["GET", "/logs"],
    ["POST", "/pipeline/start"],
    ["PUT", "/settings/"],
    ["POST", "/applications/status"],
    ["DELETE", "/pipeline/demo-run"],
  ])("refuses %s %s with a message", async (method, path) => {
    expect(await call(method, path)).toEqual({
      status: 501,
      body: { detail: NOT_IN_DEMO },
    });
  });

  it("uses a status that the API client does not retry", () => {
    expect(canRetry("GET", 0, 501)).toBe(false);
  });
});
