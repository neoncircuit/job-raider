"use client";

import { useEffect, useState } from "react";

/**
 * Returns `true` only in the browser and `false` during server-side rendering.
 *
 * The initial client render during hydration must match the server render, so
 * the hook starts at `false` and flips to `true` in an effect that only runs
 * after the component has mounted on the client. This avoids React hydration
 * mismatches while still allowing components to gate client-only behaviour
 * (such as TanStack Query `enabled`) behind a post-mount transition.
 *
 * The intentional setState-in-effect is the canonical pattern for this; the
 * lint rule is disabled because the double render is required and expected.
 *
 * @returns Whether the component is running on the client.
 */
export function useIsClient(): boolean {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsClient(true);
  }, []);

  return isClient;
}
