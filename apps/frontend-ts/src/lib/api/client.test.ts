import { describe, expect, it } from "vitest";

import {
  ApiError,
  ConnectionError,
  getApiErrorMessage,
  normalizeApiErrorDetail,
} from "./client";

describe("normalizeApiErrorDetail", () => {
  it("keeps a string detail", () => {
    expect(normalizeApiErrorDetail("Invalid sources", "fallback")).toBe(
      "Invalid sources",
    );
  });

  it("flattens a Pydantic 422 detail array", () => {
    expect(
      normalizeApiErrorDetail(
        [
          {
            loc: ["body", "sources"],
            msg: "Value error, Invalid sources: {'mycareersfuture'}",
          },
        ],
        "fallback",
      ),
    ).toBe("sources: Value error, Invalid sources: {'mycareersfuture'}");
  });
});

describe("getApiErrorMessage", () => {
  const network = "Failed to start pipeline. Is the backend running?";

  it("uses the network fallback for ConnectionError", () => {
    expect(getApiErrorMessage(new ConnectionError(), network)).toBe(network);
  });

  it("uses ApiError.detail for backend validation failures", () => {
    expect(
      getApiErrorMessage(new ApiError(422, "Invalid sources: {'x'}"), network),
    ).toBe("Invalid sources: {'x'}");
  });
});
