"use client";

import { useEffect, useState } from "react";

/**
 * Subscribe to a CSS media query and return whether it currently matches.
 *
 * On the client, the initial state is read synchronously from ``matchMedia``
 * so the first paint already matches the viewport (important for layout that
 * switches between a sheet and a side panel). During SSR the value is
 * ``false``.
 *
 * @param query - Media query string (e.g. ``"(max-width: 1023px)"``).
 * @returns Whether the query matches.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
