/**
 * Local-first request guards for the Next.js API proxy (Step 2.6).
 *
 * Reject cross-site fetches, non-loopback Host, and an Origin that does not
 * match the Host, so DNS rebinding and cross-site POSTs cannot use the
 * key-injecting proxy.
 */

import { type NextRequest, NextResponse } from "next/server";

const LOOPBACK_HOSTNAMES = new Set(["localhost", "127.0.0.1"]);

/**
 * Build the 403 response the proxy returns for a refused request.
 *
 * @param message - Reason shown to the caller.
 * @returns A 403 JSON ``NextResponse``.
 */
function forbidden(message: string): NextResponse {
  return NextResponse.json({ error: "Forbidden", message }, { status: 403 });
}

/**
 * Check that an Origin header names the same host and port as the request.
 *
 * Compare with the ``Host`` header, not ``req.nextUrl``. Next.js builds
 * ``nextUrl`` from the server bind settings (for example ``0.0.0.0:3000`` in
 * the Docker image), not from the address the browser used.
 *
 * @param origin - Value of the ``Origin`` header.
 * @param host - Lowercase value of the ``Host`` header.
 * @returns True when the origin is http(s) on exactly ``host``.
 */
function originMatchesHost(origin: string, host: string): boolean {
  try {
    const url = new URL(origin);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.host === host
    );
  } catch {
    return false;
  }
}

/**
 * Return a 403 response when the proxy request is not allowed.
 *
 * Allows requests with no Origin (same-origin navigations and many
 * same-origin fetches). After frontend bind to 127.0.0.1, only this
 * machine can reach the proxy.
 *
 * @param req - Incoming Next.js request to ``/api/proxy/*``.
 * @returns A 403 ``NextResponse`` when forbidden, otherwise ``null``.
 */
export function forbiddenProxyResponse(req: NextRequest): NextResponse | null {
  if (req.headers.get("sec-fetch-site") === "cross-site") {
    return forbidden("Cross-site requests are not allowed");
  }

  const host = (req.headers.get("host") ?? "").toLowerCase();
  const hostname = host.split(":")[0] ?? "";
  if (!LOOPBACK_HOSTNAMES.has(hostname)) {
    return forbidden("Host must be localhost or 127.0.0.1");
  }

  const origin = req.headers.get("origin");
  if (origin && !originMatchesHost(origin, host)) {
    return forbidden("Origin does not match the app");
  }

  return null;
}
