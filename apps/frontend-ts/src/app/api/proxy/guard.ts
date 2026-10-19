/**
 * Local-first request guards for the Next.js API proxy (Step 2.6).
 *
 * Reject cross-site fetches, mismatched Origin, and non-loopback Host
 * so DNS rebinding and cross-site POSTs cannot use the key-injecting proxy.
 */

import { type NextRequest, NextResponse } from "next/server";

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
  const secFetchSite = req.headers.get("sec-fetch-site");
  if (secFetchSite === "cross-site") {
    return NextResponse.json(
      { error: "Forbidden", message: "Cross-site requests are not allowed" },
      { status: 403 },
    );
  }

  const origin = req.headers.get("origin");
  if (origin) {
    const appOrigin = req.nextUrl.origin;
    if (origin !== appOrigin) {
      return NextResponse.json(
        { error: "Forbidden", message: "Origin does not match the app" },
        { status: 403 },
      );
    }
  }

  const hostHeader = req.headers.get("host") ?? "";
  const hostname = hostHeader.split(":")[0]?.toLowerCase() ?? "";
  if (hostname !== "localhost" && hostname !== "127.0.0.1") {
    return NextResponse.json(
      {
        error: "Forbidden",
        message: "Host must be localhost or 127.0.0.1",
      },
      { status: 403 },
    );
  }

  return null;
}
