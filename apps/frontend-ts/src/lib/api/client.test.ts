import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  ConnectionError,
  PROXY_ERROR_HEADER,
  PROXY_UNREACHABLE,
  canRetry,
  getApiErrorMessage,
  normalizeApiErrorDetail,
  request,
  retryDelayMs,
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

describe("canRetry", () => {
  it("retries GET and HEAD on transient failures", () => {
    expect(canRetry("GET", 0, 503)).toBe(true);
    expect(canRetry("HEAD", 2, 0)).toBe(true);
  });

  it("never retries methods that change state", () => {
    for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
      expect(canRetry(method, 0, 503)).toBe(false);
      expect(canRetry(method, 0, 0)).toBe(false);
    }
  });

  it("does not retry client errors or after the last retry", () => {
    expect(canRetry("GET", 0, 404)).toBe(false);
    expect(canRetry("GET", 3, 503)).toBe(false);
  });
});

describe("retryDelayMs", () => {
  it("uses Retry-After seconds, capped at 30 s", () => {
    expect(retryDelayMs(0, "2")).toBe(2000);
    expect(retryDelayMs(0, "600")).toBe(30_000);
  });

  it("uses a Retry-After HTTP date", () => {
    const now = Date.parse("2026-10-19T00:00:00Z");
    expect(retryDelayMs(0, "Mon, 19 Oct 2026 00:00:05 GMT", now)).toBe(5000);
  });

  it("falls back to exponential backoff", () => {
    expect(retryDelayMs(0, null)).toBe(1000);
    expect(retryDelayMs(2, "not a date")).toBe(4000);
  });
});

/**
 * Build a JSON response.
 *
 * @param status - HTTP status.
 * @param body - JSON body.
 * @param headers - Extra headers.
 * @returns A fetch Response.
 */
function jsonResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("request retry behavior", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends a POST only once, even on a 503", async () => {
    fetchMock.mockResolvedValue(jsonResponse(503, { detail: "busy" }));

    await expect(
      request("POST", "/pipeline/start", { body: {} }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries a GET after a 503 and returns the next response", async () => {
    vi.useFakeTimers();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(503, { detail: "busy" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const pending = request<{ ok: boolean }>("GET", "/health");
    await vi.advanceTimersByTimeAsync(1000);

    await expect(pending).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("maps the proxy 503 for a down backend to ConnectionError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        503,
        { error: "Backend unreachable", message: "TypeError: fetch failed" },
        { [PROXY_ERROR_HEADER]: PROXY_UNREACHABLE },
      ),
    );

    await expect(
      request("POST", "/pipeline/start", { body: {} }),
    ).rejects.toBeInstanceOf(ConnectionError);
  });

  it("keeps a backend 503 without the proxy header as ApiError", async () => {
    fetchMock.mockResolvedValue(jsonResponse(503, { detail: "Model loading" }));

    await expect(
      request("POST", "/cover-letter/manual", { body: {} }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      detail: "Model loading",
    });
  });

  it("rethrows a caller abort unchanged and does not retry it", async () => {
    const abort = new DOMException("The operation was aborted.", "AbortError");
    fetchMock.mockRejectedValue(abort);

    await expect(request("GET", "/jobs/search")).rejects.toBe(abort);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
