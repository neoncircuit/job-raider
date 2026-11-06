/**
 * Start the service worker of the demo (Step 4).
 *
 * Only the demo build loads this file. `DemoGate` imports it behind a literal
 * check of `NEXT_PUBLIC_DEMO_MODE`, so the server build drops it.
 */

import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

/**
 * Start the worker, and wait until it answers requests.
 *
 * The worker file is at the base path of the host. The API client calls
 * `/api/proxy/*` with no base path, but a worker sees each request from the
 * pages in its scope, so it answers those calls too.
 *
 * @returns A promise that resolves when the worker is active.
 */
export async function startDemo(): Promise<void> {
  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  await setupWorker(...handlers).start({
    quiet: true,
    onUnhandledRequest: "bypass",
    serviceWorker: {
      url: `${base}/mockServiceWorker.js`,
      options: { scope: `${base}/` },
    },
  });
}
