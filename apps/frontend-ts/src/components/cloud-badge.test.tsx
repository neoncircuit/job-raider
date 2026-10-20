import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CloudBadge } from "./cloud-badge";

describe("CloudBadge", () => {
  it("renders Cloud when show is true", () => {
    render(<CloudBadge show />);
    expect(screen.getByText("Cloud")).toBeInTheDocument();
  });

  it("renders nothing when show is false", () => {
    const { container } = render(<CloudBadge show={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
