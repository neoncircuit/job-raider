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

// Simple logger function (inline to avoid module resolution issues)
const LOG_PREFIX = "[JobRaider API]";

// Auth state tracking
let authValidated = false;
let authEnabled = false;

function log(level: string, message: string, ...args: unknown[]) {
  const timestamp = new Date().toISOString();
  const prefix = `${LOG_PREFIX} [${timestamp}] [${level}]`;
  switch (level) {
    case "DEBUG":
      console.debug(prefix, message, ...args);
      break;
    case "INFO":
      console.log(prefix, message, ...args);
      break;
    case "WARN":
      console.warn(prefix, message, ...args);
      break;
    case "ERROR":
      console.error(prefix, message, ...args);
      break;
  }
}

/**
 * Validate authentication configuration
 * Checks if auth is properly configured and logs status
 */
export function validateAuthConfig(): { enabled: boolean; message: string } {
  if (authValidated) {
    return { enabled: authEnabled, message: authEnabled ? "Auth enabled" : "Auth disabled (local dev mode)" };
  }

  // In browser environment, we can't directly check server env vars
  // We'll detect auth state on first API call
  log("INFO", "Authentication status will be validated on first API call");
  authValidated = true;
  return { enabled: false, message: "Auth status pending first API call" };
}

/**
 * Update auth state based on API response
 */
export function updateAuthState(isAuthenticated: boolean) {
  const wasEnabled = authEnabled;
  authEnabled = isAuthenticated;
  authValidated = true;

  if (!wasEnabled && isAuthenticated) {
    log("INFO", "✅ Authentication enabled - API key is configured");
  } else if (wasEnabled && !isAuthenticated) {
    log("WARN", "⚠️  Authentication disabled - running in local dev mode");
  }
}

function logRequest(method: string, path: string, body?: unknown) {
  log("INFO", `API Request: ${method} ${path}`, body ? JSON.stringify(body) : "");
}

function logResponse(status: number, path: string, data?: unknown) {
  const statusColor = status >= 200 && status < 300 ? "✅" : status >= 400 ? "❌" : "⚠️";
  log("INFO", `API Response: ${statusColor} ${status} ${path}`, data ? JSON.stringify(data).substring(0, 200) : "");
}

const PROXY_BASE = "/api/proxy";

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

/**
 * Sleep for specified milliseconds
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Check if a request should be retried based on the error or status code
 */
function shouldRetry(statusCode: number, error: Error): boolean {
  // Retry on retryable status codes
  if (RETRYABLE_STATUS_CODES.includes(statusCode)) {
    return true;
  }

  // Retry on connection errors
  if (error.name === "ConnectionError" || error.message.includes("fetch")) {
    return true;
  }

  return false;
}

interface RequestOptions {
  body?: unknown;
  formData?: FormData;
  params?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  retries?: number; // Number of retries attempted (internal)
}

export async function request<T>(
  method: string,
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const { body, formData, params, signal, retries = 0 } = opts;

  let url = `${PROXY_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    const str = qs.toString();
    if (str) url += `?${str}`;
  }

  // Log request
  logRequest(method, path, body);

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
  let fetchError: Error | null = null;

  try {
    res = await fetch(url, { method, headers, body: fetchBody, signal });
  } catch (err) {
    fetchError = err as Error;
    log("ERROR", `API Error: ${method} ${path}`, err);

    // Check if we should retry
    if (retries < MAX_RETRIES && shouldRetry(0, fetchError)) {
      const delay = RETRY_DELAY_MS * Math.pow(2, retries); // Exponential backoff
      log("WARN", `Retrying request (${retries + 1}/${MAX_RETRIES}) after ${delay}ms...`);
      await sleep(delay);
      return request<T>(method, path, { ...opts, retries: retries + 1 });
    }

    throw new ConnectionError(String(err));
  }

  // Detect auth state from response
  // If backend returns 401 with "Invalid or missing API key", auth is enabled
  // If request succeeds, auth is working (either enabled or disabled)
  if (!authValidated) {
    if (res.status === 401) {
      updateAuthState(true); // Auth is enabled
      log("INFO", "🔒 Authentication is enabled on the backend");
    } else if (res.ok) {
      // Request succeeded - auth might be enabled or disabled
      // We'll assume disabled for now unless we get a 401
      updateAuthState(false);
      log("INFO", "🔓 Authentication appears to be disabled (local dev mode)");
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json?.detail ?? json?.message ?? detail;
    } catch {
      // ignore parse errors
    }
    logResponse(res.status, path, { detail });

    // Special handling for 401 errors
    if (res.status === 401) {
      log("ERROR", "🔒 Authentication failed - Check API_KEY configuration");
    }

    // Check if we should retry on server errors
    const apiError = new ApiError(res.status, detail);
    if (retries < MAX_RETRIES && shouldRetry(res.status, apiError)) {
      const delay = RETRY_DELAY_MS * Math.pow(2, retries); // Exponential backoff
      log("WARN", `Retrying request (${retries + 1}/${MAX_RETRIES}) after ${delay}ms...`);
      await sleep(delay);
      return request<T>(method, path, { ...opts, retries: retries + 1 });
    }

    throw apiError;
  }

  logResponse(res.status, path);

  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}
