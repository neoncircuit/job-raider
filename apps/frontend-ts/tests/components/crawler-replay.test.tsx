/**
 * Job Raider - Crawler replay tests
 *
 * Covers the replay controls and the reduced-motion fallback. Canvas drawing
 * is not exercised (jsdom has no 2D context); decisions must still apply.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CrawlerReplay } from "@/components/crawler-replay";
import { SAMPLE_TRACE } from "@/lib/crawler-trace";

function mockReducedMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce && query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("CrawlerReplay", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    vi.restoreAllMocks();
  });

  it("starts with no decisions applied", () => {
    mockReducedMotion(false);
    const { container } = render(<CrawlerReplay trace={SAMPLE_TRACE} />);

    expect(
      screen.getByText(`0 / ${SAMPLE_TRACE.events.length} decisions`),
    ).toBeInTheDocument();
    expect(screen.getByText("Nothing extracted yet.")).toBeInTheDocument();
    expect(
      container.querySelectorAll('[data-state]:not([data-state="unread"])'),
    ).toHaveLength(0);
    expect(screen.getByRole("button", { name: /start crawl/i })).toBeEnabled();
  });

  it("applies every trace decision on skip", async () => {
    mockReducedMotion(false);
    const user = userEvent.setup();
    const { container } = render(<CrawlerReplay trace={SAMPLE_TRACE} />);

    await user.click(screen.getByRole("button", { name: /skip/i }));

    const total = SAMPLE_TRACE.events.length;
    expect(
      screen.getByText(`${total} / ${total} decisions`),
    ).toBeInTheDocument();
    expect(screen.getByText("Scam flags")).toBeInTheDocument();
    expect(
      screen.getByText("Scam indicator: asks to contact HR on WhatsApp", {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(
      container.querySelectorAll('[data-state="flagged"]').length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /replay/i })).toBeInTheDocument();
  });

  it("restart clears applied decisions", async () => {
    mockReducedMotion(true);
    const user = userEvent.setup();
    render(<CrawlerReplay trace={SAMPLE_TRACE} />);

    await user.click(screen.getByRole("button", { name: /show result/i }));
    await user.click(screen.getByRole("button", { name: /restart/i }));

    expect(
      screen.getByText(`0 / ${SAMPLE_TRACE.events.length} decisions`),
    ).toBeInTheDocument();
    expect(screen.getByText("No decisions yet.")).toBeInTheDocument();
  });

  it("drops the canvas and offers a static result under reduced motion", async () => {
    mockReducedMotion(true);
    const user = userEvent.setup();
    const { container } = render(<CrawlerReplay trace={SAMPLE_TRACE} />);

    expect(container.querySelector("canvas")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /start crawl/i }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /show result/i }));

    expect(screen.getByText("Salary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show result/i })).toBeDisabled();
  });
});
