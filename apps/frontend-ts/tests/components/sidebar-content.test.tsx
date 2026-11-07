/**
 * Tests for the sidebar groups (Step 5, MH-3).
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SidebarContent } from "@/components/layout/SidebarContent";

const pathname = vi.hoisted(() => ({ value: "/dashboard" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));
vi.mock("@/components/layout/ConnectionStatus", () => ({
  ConnectionStatus: () => null,
}));
vi.mock("@/components/layout/SystemResourcesMeter", () => ({
  SystemResourcesMeter: () => null,
}));
vi.mock("@/components/theme-toggle", () => ({ ThemeToggle: () => null }));

const CORE = [
  "Profile",
  "Dashboard",
  "Pipeline",
  "Jobs",
  "Cover Letter",
  "Applications",
  "Metrics",
  "Settings",
];
const EXTRAS = [
  "Career Coach",
  "Assessment",
  "Resume Analysis",
  "LinkedIn Analysis",
  "Logs",
];

/**
 * Read the names of the navigation links, in order.
 *
 * @returns The link names.
 */
function linkNames(): string[] {
  return within(screen.getByRole("navigation"))
    .getAllByRole("link")
    .map((link) => link.textContent ?? "");
}

describe("SidebarContent", () => {
  afterEach(() => {
    pathname.value = "/dashboard";
    vi.unstubAllEnvs();
  });

  it("shows the core loop in order, with the extras collapsed", () => {
    render(<SidebarContent />);

    expect(linkNames()).toEqual(CORE);
    expect(screen.getByRole("button", { name: "Extras" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("opens the extras on a click", async () => {
    render(<SidebarContent />);

    await userEvent.click(screen.getByRole("button", { name: "Extras" }));

    expect(linkNames()).toEqual([...CORE, ...EXTRAS]);
    expect(screen.getByRole("button", { name: "Extras" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("closes the extras on a second click", async () => {
    render(<SidebarContent />);
    const toggle = screen.getByRole("button", { name: "Extras" });

    await userEvent.click(toggle);
    await userEvent.click(toggle);

    expect(linkNames()).toEqual(CORE);
  });

  it("keeps the extras open on one of their pages", () => {
    pathname.value = "/assessment/session";

    render(<SidebarContent />);

    expect(linkNames()).toEqual([...CORE, ...EXTRAS]);
    expect(screen.getByRole("button", { name: "Extras" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("closes the mobile sheet from an extra link", async () => {
    const onNavItemClick = vi.fn();
    render(<SidebarContent onNavItemClick={onNavItemClick} />);

    await userEvent.click(screen.getByRole("button", { name: "Extras" }));
    await userEvent.click(screen.getByRole("link", { name: "Logs" }));

    expect(onNavItemClick).toHaveBeenCalledOnce();
  });

  it("has no extras group in the demo", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");

    render(<SidebarContent />);

    expect(linkNames()).toEqual(CORE);
    expect(
      screen.queryByRole("button", { name: "Extras" }),
    ).not.toBeInTheDocument();
  });
});
