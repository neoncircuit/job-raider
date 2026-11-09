/**
 * Job Raider - Hardware fit E2E test (Step 6, MH-4).
 *
 * With the API mock: the Local models card labels each model against the
 * GPU memory budget, and a pull of an over-budget suggestion asks the user to
 * confirm before it starts. The hardware is made up (an 8 GB GPU).
 */

import { test, expect } from "./support/test";

test.describe("Hardware fit", () => {
  test("labels models and confirms an over-budget pull", async ({ page }) => {
    const pulls: unknown[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/settings/ollama/pull")
      ) {
        pulls.push(request.postDataJSON());
      }
    });

    await page.goto("/settings");
    const card = page.getByRole("region", { name: "Local models" });

    const reasonRow = card.getByRole("row", { name: /examplereason:8b/ });
    await expect(reasonRow.getByText("Over budget")).toBeVisible();
    const chatRow = card.getByRole("row", { name: /examplechat:7b/ });
    await expect(chatRow.getByText("Fits")).toBeVisible();
    await expect(
      card.getByLabel("Hardware fit", { exact: true }),
    ).toContainText("Safety budget 6.0 GB of 8.0 GB");

    await card.getByRole("button", { name: "Pull examplebig:8b" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("Pull examplebig:8b anyway?");
    await expect(dialog).toContainText("safety budget of 6.0 GB");

    await dialog.getByRole("button", { name: "Pull anyway" }).click();
    await expect(dialog).toBeHidden();
    await expect.poll(() => pulls.length).toBe(2);
    expect(pulls).toEqual([
      { model: "examplebig:8b" },
      { model: "examplebig:8b", confirm_over_budget: true },
    ]);
  });
});
