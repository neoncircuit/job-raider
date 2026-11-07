/**
 * Tests for the workflow that publishes the demo (Step 4, MH-6).
 *
 * A publish is outward-facing, so these tests keep its two gates: a person
 * starts it, and the E2E tests must pass first.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const WORKFLOW = readFileSync(
  resolve(__dirname, "../../../../.github/workflows/pages.yml"),
  "utf-8",
);

/**
 * Read a top-level block of the workflow.
 *
 * @param name - The key of the block.
 * @returns The text from the key to the next top-level key.
 */
function block(name: string): string {
  const start = WORKFLOW.search(new RegExp(`^${name}:`, "m"));
  expect(start).toBeGreaterThanOrEqual(0);
  const rest = WORKFLOW.slice(start + name.length + 1);
  const end = rest.search(/^\S/m);
  return end === -1 ? rest : rest.slice(0, end);
}

describe("the Publish Demo workflow", () => {
  it("runs only when a person starts it", () => {
    expect(block("on").trim()).toBe("workflow_dispatch:");
  });

  it("uploads the site only after the E2E tests", () => {
    const tests = WORKFLOW.indexOf("npm run test:e2e:demo");
    const upload = WORKFLOW.indexOf("actions/upload-pages-artifact");

    expect(tests).toBeGreaterThan(0);
    expect(upload).toBeGreaterThan(tests);
  });

  it("deploys only after the build job", () => {
    expect(block("jobs")).toMatch(/^ {2}deploy:\n(.*\n)* {4}needs: build$/m);
  });

  it("builds for the base path of the site", () => {
    expect(WORKFLOW).toContain("NEXT_PUBLIC_BASE_PATH: /job-raider");
    expect(WORKFLOW).toContain("path: apps/frontend-ts/out");
  });

  it("gives write access to the deploy job only", () => {
    expect(block("permissions").trim()).toBe("contents: read");
    expect(WORKFLOW.split("pages: write")).toHaveLength(2);
    expect(WORKFLOW.indexOf("pages: write")).toBeGreaterThan(
      WORKFLOW.indexOf("  deploy:"),
    );
  });
});
