import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { forbiddenProxyResponse } from "./guard";

/**
 * Build a NextRequest for proxy guard tests.
 *
 * @param headers - Extra request headers.
 * @param url - Request URL (default local app origin).
 * @returns A NextRequest aimed at the proxy.
 */
function proxyRequest(
  headers: Record<string, string>,
  url = "http://localhost:3000/api/proxy/health",
): NextRequest {
  return new NextRequest(url, { headers });
}

describe("forbiddenProxyResponse", () => {
  it("allows a same-origin request with localhost Host", () => {
    const req = proxyRequest({
      host: "localhost:3000",
      origin: "http://localhost:3000",
      "sec-fetch-site": "same-origin",
    });
    expect(forbiddenProxyResponse(req)).toBeNull();
  });

  it("allows a request with no Origin", () => {
    const req = proxyRequest({ host: "127.0.0.1:3000" });
    expect(forbiddenProxyResponse(req)).toBeNull();
  });

  it("rejects Sec-Fetch-Site cross-site", async () => {
    const req = proxyRequest({
      host: "localhost:3000",
      "sec-fetch-site": "cross-site",
    });
    const res = forbiddenProxyResponse(req);
    expect(res?.status).toBe(403);
  });

  it("rejects a mismatched Origin", async () => {
    const req = proxyRequest({
      host: "localhost:3000",
      origin: "https://evil.example",
    });
    const res = forbiddenProxyResponse(req);
    expect(res?.status).toBe(403);
  });

  it("rejects a non-loopback Host", async () => {
    const req = proxyRequest(
      { host: "evil.example:3000" },
      "http://evil.example:3000/api/proxy/health",
    );
    const res = forbiddenProxyResponse(req);
    expect(res?.status).toBe(403);
  });

  // A real Next.js server builds the request URL from its bind settings, not
  // from the address the browser used. The guard must compare Origin with Host.
  it("allows same-origin in Docker (server URL 0.0.0.0, port 3005)", () => {
    const req = proxyRequest(
      {
        host: "127.0.0.1:3005",
        origin: "http://127.0.0.1:3005",
        "sec-fetch-site": "same-origin",
      },
      "http://0.0.0.0:3000/api/proxy/settings/validate",
    );
    expect(forbiddenProxyResponse(req)).toBeNull();
  });

  it("allows same-origin on 127.0.0.1 when the server URL says localhost", () => {
    const req = proxyRequest(
      {
        host: "127.0.0.1:3000",
        origin: "http://127.0.0.1:3000",
        "sec-fetch-site": "same-origin",
      },
      "http://localhost:3000/api/proxy/settings/validate",
    );
    expect(forbiddenProxyResponse(req)).toBeNull();
  });

  it("rejects an Origin on another local port", () => {
    const req = proxyRequest({
      host: "localhost:3000",
      origin: "http://localhost:5000",
      "sec-fetch-site": "same-site",
    });
    expect(forbiddenProxyResponse(req)?.status).toBe(403);
  });

  it("rejects an opaque Origin", () => {
    const req = proxyRequest({ host: "localhost:3000", origin: "null" });
    expect(forbiddenProxyResponse(req)?.status).toBe(403);
  });
});
