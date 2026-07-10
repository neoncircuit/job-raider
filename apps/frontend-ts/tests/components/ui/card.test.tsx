/**
 * Job Raider - UI Card Component Tests
 *
 * Card exports its parts as named components (CardHeader, CardContent,
 * CardFooter) rather than compound members (Card.Header).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

describe("Card Component", () => {
  it("renders header, content, and footer children", () => {
    render(
      <Card>
        <CardHeader>
          <h3>Card Title</h3>
        </CardHeader>
        <CardContent>
          <p>Card content</p>
        </CardContent>
        <CardFooter>
          <span>Footer content</span>
        </CardFooter>
      </Card>,
    );

    expect(screen.getByText("Card Title")).toBeInTheDocument();
    expect(screen.getByText("Card content")).toBeInTheDocument();
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });

  it("applies a custom className", () => {
    const { container } = render(<Card className="custom-card">Body</Card>);
    expect(container.querySelector(".custom-card")).toBeInTheDocument();
  });

  it("renders without header or footer", () => {
    render(
      <Card>
        <CardContent>Just content</CardContent>
      </Card>,
    );
    expect(screen.getByText("Just content")).toBeInTheDocument();
  });
});
