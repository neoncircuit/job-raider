// Base fetch wrapper. All calls go to /api/proxy/* which is a Next.js Route Handler
// that injects the X-API-Key and forwards to the backend.

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

export class ConnectionError extends Error {
  constructor(message = "Backend unreachable") {
    super(message);
    this.name = "ConnectionError";
  }
}

const PROXY_BASE = "/api/proxy";

interface RequestOptions {
  body?: unknown;
  formData?: FormData;
  params?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

export async function request<T>(
  method: string,
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const { body, formData, params, signal } = opts;

  let url = `${PROXY_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    const str = qs.toString();
    if (str) url += `?${str}`;
  }

  const headers: Record<string, string> = {};
  let fetchBody: BodyInit | undefined;

  if (formData) {
    fetchBody = formData;
    // Do NOT set Content-Type — browser sets it with correct multipart boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: fetchBody, signal });
  } catch (err) {
    throw new ConnectionError(String(err));
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json?.detail ?? json?.message ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}
