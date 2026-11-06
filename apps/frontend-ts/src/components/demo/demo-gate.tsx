"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

interface DemoGateProps {
  /** The app. */
  children: ReactNode;
}

/**
 * Hold the app until the demo's service worker answers requests.
 *
 * In the server build this renders its children and nothing else. The checks
 * of `NEXT_PUBLIC_DEMO_MODE` are written out in full, so that build drops the
 * import of the demo code.
 *
 * @param children - The app.
 * @returns The app, or a message while the demo starts or when it cannot.
 */
export function DemoGate({ children }: DemoGateProps) {
  const [state, setState] = useState<"starting" | "ready" | "failed">(
    process.env.NEXT_PUBLIC_DEMO_MODE === "1" ? "starting" : "ready",
  );

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "1") {
      import("@/demo/start")
        .then(({ startDemo }) => startDemo())
        .then(
          () => setState("ready"),
          () => setState("failed"),
        );
    }
  }, []);

  if (state === "ready") {
    return children;
  }
  return (
    <div
      role="status"
      className="flex h-screen items-center justify-center p-6 text-center text-sm text-muted-foreground"
    >
      {state === "starting"
        ? "Starting the demo..."
        : "The demo needs service workers, and this browser blocks them. Try a normal window in another browser."}
    </div>
  );
}
