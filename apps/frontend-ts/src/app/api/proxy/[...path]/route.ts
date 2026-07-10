// Server-side proxy: adds X-API-Key and forwards all /api/proxy/* requests to the backend.
// The API key and backend URL are server-only env vars — never exposed to the browser.
import { type NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.API_KEY ?? "";

// In Next.js 16, params is a Promise — must be awaited. The context type is
// declared inline (rather than the generated `RouteContext<...>`) so that
// `tsc --noEmit` passes without a prior `next build` generating .next/types.
type ProxyRouteContext = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, ctx: ProxyRouteContext) {
  const { path } = await ctx.params;
  const backendPath = "/api/" + path.join("/");

  const backendUrl = new URL(backendPath, BACKEND_API_URL);
  // Forward query string unchanged
  req.nextUrl.searchParams.forEach((value, key) => {
    backendUrl.searchParams.set(key, value);
  });

  const headers = new Headers(req.headers);
  headers.set("X-API-Key", API_KEY);
  // Remove host header so the backend doesn't reject it
  headers.delete("host");

  let body: BodyInit | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const contentType = req.headers.get("content-type") ?? "";
    if (contentType.includes("multipart/form-data")) {
      // For multipart, pass the body directly; do NOT re-set Content-Type
      // (it contains the boundary that the backend needs)
      body = await req.blob();
    } else {
      body = (await req.text()) || null;
    }
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl.toString(), {
      method: req.method,
      headers,
      body,
      // @ts-expect-error — Node fetch duplex option
      duplex: "half",
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Backend unreachable", message: String(err) },
      { status: 503 },
    );
  }

  const responseHeaders = new Headers(backendRes.headers);
  // Strip encoding headers that Next.js will re-set correctly
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new NextResponse(backendRes.body, {
    status: backendRes.status,
    statusText: backendRes.statusText,
    headers: responseHeaders,
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const HEAD = handler;
export const OPTIONS = handler;
