/**
 * Tests for the demo gate, banner, and letter note (Step 4, MH-3).
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DemoGate } from "@/components/demo/demo-gate";
import { DemoBanner, DemoLetterNote } from "@/components/demo/demo-notes";
import { demoLetter, demoProfile } from "@/demo/data";

const startDemo = vi.hoisted(() => vi.fn());
vi.mock("@/demo/start", () => ({ startDemo }));

describe("DemoGate", () => {
  beforeEach(() => {
    startDemo.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the app at once in the server build", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");

    render(<DemoGate>the app</DemoGate>);

    expect(screen.getByText("the app")).toBeInTheDocument();
    await vi.dynamicImportSettled();
    expect(startDemo).not.toHaveBeenCalled();
  });

  it("holds the app until the worker is ready", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    let ready = () => {};
    startDemo.mockReturnValue(
      new Promise<void>((resolve) => {
        ready = resolve;
      }),
    );

    render(<DemoGate>the app</DemoGate>);

    expect(screen.queryByText("the app")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Starting the demo");
    await waitFor(() => expect(startDemo).toHaveBeenCalledOnce());

    ready();

    expect(await screen.findByText("the app")).toBeInTheDocument();
  });

  it("says so when the worker cannot start", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    startDemo.mockRejectedValue(new Error("blocked"));

    render(<DemoGate>the app</DemoGate>);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("service workers"),
    );
    expect(screen.queryByText("the app")).not.toBeInTheDocument();
  });
});

describe("demo notes", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows nothing in the server build", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");

    const { container } = render(
      <>
        <DemoBanner />
        <DemoLetterNote />
      </>,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("says that the data is sample data and stays in the browser", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");

    render(<DemoBanner />);

    const note = screen.getByRole("note");
    expect(note).toHaveTextContent("sample data");
    expect(note).toHaveTextContent("fictional");
    expect(note).toHaveTextContent("nothing leaves your browser");
  });

  it("says what the rule checks missed", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");

    render(<DemoLetterNote />);

    expect(screen.getByRole("note")).toHaveTextContent("they miss real errors");
    expect(screen.getByRole("note")).toHaveTextContent("deployed");
  });

  it("stays true for the sample letter", () => {
    const letter = demoLetter.cover_letter.content.toLowerCase();
    const profile = JSON.stringify(demoProfile).toLowerCase();

    expect(letter).toContain("deployed");
    expect(profile).not.toContain("deployed");
    expect(demoLetter.validation.recommendation).toBe("approve");
  });
});
