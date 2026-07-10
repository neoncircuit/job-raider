/**
 * Job Raider - UI Button Component Tests
 *
 * The Button is built on base-ui (no Radix `asChild`); variant/size are
 * resolved into a single className string by cva, so these tests assert
 * behaviour rather than literal class names.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";

describe("Button Component", () => {
  it("renders with text content", () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole("button", { name: "Click me" }),
    ).toBeInTheDocument();
  });

  it("handles click events", async () => {
    let clicked = false;
    render(
      <Button
        onClick={() => {
          clicked = true;
        }}
      >
        Click me
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Click me" }));
    expect(clicked).toBe(true);
  });

  it("is disabled when the disabled prop is set", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button", { name: "Disabled" })).toBeDisabled();
  });

  it("accepts variant and size props without error", () => {
    render(
      <Button variant="destructive" size="sm">
        Delete
      </Button>,
    );
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("is not clickable when disabled", async () => {
    let clicked = false;
    render(
      <Button
        onClick={() => {
          clicked = true;
        }}
        disabled
      >
        Loading
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Loading" }));
    expect(clicked).toBe(false);
  });
});
