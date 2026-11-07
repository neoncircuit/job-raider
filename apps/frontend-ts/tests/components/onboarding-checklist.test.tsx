/**
 * Tests for the onboarding checklist on the dashboard (Step 4, MH-5).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { readOnboardingDismissed } from "@/lib/onboarding";

import { server } from "../setup/globals";

const COMPLETE = {
  health: { status: "healthy", checks: [] },
  models: { host: "x", reachable: true, models: [{ name: "m" }], in_use: [] },
  profile: { contact_info: { name: "A" } },
  history: { runs: [{ run_id: "r" }] },
  applications: {
    applications: [
      { is_bookmarked: false, is_hidden: false, current_status: "applied" },
    ],
  },
};
type Answers = typeof COMPLETE;

/**
 * Answer the five reads of the checklist.
 *
 * @param changes - The answers to change. Null makes that read fail.
 * @returns Nothing.
 */
function answer(changes: {
  [Key in keyof Answers]?: unknown;
}): void {
  const reply = (key: keyof Answers) => () => {
    const body = key in changes ? changes[key] : COMPLETE[key];
    return body === null
      ? HttpResponse.json({ detail: "none" }, { status: 404 })
      : HttpResponse.json(body as object);
  };
  server.use(
    http.get("*/api/proxy/health", reply("health")),
    http.get("*/api/proxy/settings/ollama/models", reply("models")),
    http.get("*/api/proxy/profile", reply("profile")),
    http.get("*/api/proxy/pipeline/history", reply("history")),
    http.get("*/api/proxy/applications/dashboard", reply("applications")),
  );
}

/**
 * Render the checklist with a new query client.
 *
 * @returns The render result.
 */
function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <OnboardingChecklist />
    </QueryClientProvider>,
  );
}

describe("OnboardingChecklist", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("links each open step to its page", async () => {
    answer({
      models: { host: "x", reachable: true, models: [], in_use: [] },
      profile: null,
      history: { runs: [] },
      applications: { applications: [] },
    });

    show();

    expect(await screen.findByText("1 of 6 done")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Pull a local model" }),
    ).toHaveAttribute("href", "/settings");
    expect(
      screen.getByRole("link", { name: "Upload your resume" }),
    ).toHaveAttribute("href", "/profile");
    expect(
      screen.queryByRole("link", { name: "Start the local backend" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Start the local backend")).toBeInTheDocument();
  });

  it("hides when each step is done", async () => {
    let reads = 0;
    answer({});
    server.events.on("response:mocked", () => {
      reads += 1;
    });

    const { container } = show();

    await waitFor(() => expect(reads).toBeGreaterThanOrEqual(5));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    server.events.removeAllListeners();
  });

  it("shows the card with no backend, and reads nothing else", async () => {
    const paths: string[] = [];
    server.use(
      http.all("*/api/proxy/*", ({ request }) => {
        paths.push(new URL(request.url).pathname);
        return HttpResponse.json({ detail: "down" }, { status: 404 });
      }),
    );

    show();

    expect(await screen.findByText("0 of 6 done")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start the local backend" }),
    ).toBeInTheDocument();
    expect(paths).toEqual(["/api/proxy/health"]);
  });

  it("keeps the model step open when Ollama does not answer", async () => {
    answer({
      models: {
        host: "x",
        reachable: false,
        models: [{ name: "m" }],
        in_use: [],
      },
    });

    show();

    expect(await screen.findByText("5 of 6 done")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Pull a local model" }),
    ).toBeInTheDocument();
  });

  it("keeps a step open when its read fails", async () => {
    answer({ history: null });

    show();

    expect(await screen.findByText("5 of 6 done")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Run a first discover" }),
    ).toBeInTheDocument();
  });

  it("shows nothing until each read has finished", async () => {
    answer({ profile: null });
    server.use(
      http.get("*/api/proxy/pipeline/history", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );

    const { container } = show();

    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(container).toBeEmptyDOMElement();
  });

  it("counts a hidden job as a review", async () => {
    answer({ profile: null });
    server.use(
      http.get("*/api/proxy/applications/dashboard", ({ request }) => {
        const hidden = new URL(request.url).searchParams.has("include_hidden");
        return HttpResponse.json({
          applications: hidden
            ? [{ is_hidden: true, current_status: "not_interested" }]
            : [],
        });
      }),
    );

    show();

    expect(await screen.findByText("4 of 6 done")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Review the shortlist/ }),
    ).not.toBeInTheDocument();
  });

  it("stays away after a dismiss", async () => {
    answer({ profile: null });
    const first = show();

    await userEvent.click(
      await screen.findByRole("button", { name: "Dismiss" }),
    );

    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
    expect(readOnboardingDismissed()).toBe(true);
    first.unmount();

    show();

    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
  });
});
