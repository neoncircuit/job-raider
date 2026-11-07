/**
 * E2E tests on the exported demo (Step 4, MH-4).
 *
 * The service worker of the real build answers each API request here, so
 * these tests have no mock layer. They also prove the wires that unit tests
 * do not cover: the gate in `providers.tsx`, the banner in `AppShell.tsx`, and
 * the sidebar filter in `SidebarContent.tsx`.
 */

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const CORE_PAGES = [
  { name: "Dashboard", path: "dashboard", data: "70 scraped" },
  { name: "Pipeline", path: "pipeline", data: "Start Discover" },
  {
    name: "Jobs",
    path: "jobs",
    data: "Research Engineer, Machine Learning",
  },
  {
    name: "Applications",
    path: "applications",
    data: "Associate NLP Engineer",
  },
  { name: "Cover Letter", path: "cover-letter", data: "sample-resume.pdf" },
  { name: "Profile", path: "profile", data: "sample.candidate@example.com" },
  { name: "Metrics", path: "metrics", data: "demo-run" },
  { name: "Settings", path: "settings", data: "Model Parameters" },
];
const HIDDEN_LINKS = [
  "Career Coach",
  "Assessment",
  "Resume Analysis",
  "LinkedIn Analysis",
  "Logs",
];
const NOT_IN_DEMO = "This needs the local backend, so it is not in the demo.";
const ONE_SAMPLE_LETTER =
  "The demo has one sample letter. Open the first job on the Jobs page.";

/**
 * Collect each defect that a visitor can meet on a page.
 *
 * A 501 from the API is the demo's own answer, so it is not a defect. A
 * request that the browser cancels on a change of page is not a defect.
 *
 * @param page - The Playwright page.
 * @returns A list that fills while the test runs.
 */
function watchProblems(page: Page): string[] {
  const problems: string[] = [];
  const origin = new URL(test.info().project.use.baseURL ?? "").origin;
  page.on("pageerror", (error) => problems.push(`error: ${error.message}`));
  page.on("request", (request) => {
    const url = request.url();
    if (/^https?:/.test(url) && !url.startsWith(origin)) {
      problems.push(`left the browser: ${url}`);
    }
  });
  page.on("requestfailed", (request) => {
    if (request.failure()?.errorText !== "net::ERR_ABORTED") {
      problems.push(`failed: ${request.url()}`);
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    const isApi = url.includes("/api/proxy/");
    if (isApi && !response.fromServiceWorker()) {
      problems.push(`no worker: ${url}`);
    }
    if (response.status() >= 400 && !(isApi && response.status() === 501)) {
      problems.push(`${response.status()}: ${url}`);
    }
  });
  return problems;
}

/**
 * Open the panel of a job.
 *
 * @param page - The Playwright page.
 * @param title - The start of the job title.
 * @returns Nothing.
 */
async function openJob(page: Page, title: string): Promise<void> {
  await page.getByRole("button", { name: `View ${title}` }).click();
}

test.describe("demo pages", () => {
  for (const { name, path, data } of CORE_PAGES) {
    test(`${name} shows data and the banner`, async ({ page }) => {
      const problems = watchProblems(page);

      await page.goto(path);

      await expect(page.getByRole("main")).toContainText(data);
      await expect(page.getByRole("note").first()).toContainText(
        "Demo with sample data",
      );
      await expect(page.getByRole("note").first()).toContainText(
        "nothing leaves your browser",
      );
      expect(problems).toEqual([]);
    });
  }

  test("the root opens the dashboard", async ({ page }) => {
    await page.goto("./");

    await expect(page).toHaveURL(/\/job-raider\/dashboard$/);
    await expect(page.getByRole("main")).toContainText("70 scraped");
  });

  test("a reload keeps the data", async ({ page }) => {
    await page.goto("jobs");
    await expect(page.getByRole("main")).toContainText("Research Engineer");

    await page.reload();

    await expect(page.getByRole("main")).toContainText("Research Engineer");
  });

  test("the sidebar links work and keep the base path", async ({ page }) => {
    await page.goto("dashboard");

    await page.getByRole("link", { name: "Applications" }).click();

    await expect(page).toHaveURL(/\/job-raider\/applications$/);
    await expect(page.getByRole("main")).toContainText(
      "Associate NLP Engineer",
    );
  });

  test("the sidebar leaves out the pages that need a backend", async ({
    page,
  }) => {
    await page.goto("dashboard");
    await expect(page.getByRole("link", { name: "Metrics" })).toBeVisible();

    for (const name of HIDDEN_LINKS) {
      await expect(page.getByRole("link", { name })).toHaveCount(0);
    }
  });

  test("a phone width has no sideways scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    await page.goto("dashboard");
    await expect(page.getByRole("main")).toContainText("70 scraped");

    const wide = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );

    expect(wide).toBe(false);
  });
});

test.describe("demo actions", () => {
  test("the first job has the sample letter and its note", async ({ page }) => {
    const problems = watchProblems(page);
    await page.goto("jobs");

    await openJob(page, "Research Engineer");
    await page.getByRole("button", { name: "Generate Cover Letter" }).click();

    await expect(page.getByRole("main")).toContainText("they miss real errors");
    await expect(page.getByRole("main")).toContainText(
      "At Example AI Institute",
    );
    expect(problems).toEqual([]);
  });

  test("another job explains the limit", async ({ page }) => {
    await page.goto("jobs");

    await openJob(page, "Associate NLP Engineer");
    await page.getByRole("button", { name: "Generate Cover Letter" }).click();

    await expect(page.getByText(ONE_SAMPLE_LETTER)).toBeVisible();
  });

  test("a job analysis explains the limit", async ({ page }) => {
    await page.goto("jobs");

    await openJob(page, "Associate NLP Engineer");
    await page.getByRole("button", { name: "Analyze with AI" }).click();

    await expect(page.getByText(NOT_IN_DEMO)).toBeVisible();
  });

  test("a pipeline start explains the limit", async ({ page }) => {
    await page.goto("pipeline");

    await page.getByRole("textbox").first().fill("machine learning engineer");
    await page.getByRole("button", { name: "Start Discover" }).click();

    await expect(page.getByText(NOT_IN_DEMO)).toBeVisible();
  });
});
