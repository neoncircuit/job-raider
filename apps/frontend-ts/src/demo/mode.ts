/**
 * Demo mode rules (Step 4).
 *
 * The public demo is a static build with no backend. Each read of the
 * environment here is written out in full, because Next.js inlines
 * `NEXT_PUBLIC_*` only in that form.
 */

/** Routes that need a backend, so the demo leaves them out of the sidebar. */
export const DEMO_HIDDEN_ROUTES: ReadonlySet<string> = new Set([
  "/career-coach",
  "/assessment",
  "/resume-analysis",
  "/linkedin-analysis",
  "/logs",
]);

/**
 * Tell whether this is the demo build.
 *
 * @returns True in the demo build.
 */
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "1";
}

/**
 * Keep the sidebar items that work in this build.
 *
 * @param items - The sidebar items.
 * @returns All items, or in the demo only the items with data.
 */
export function visibleNavItems<T extends { href: string }>(
  items: readonly T[],
): readonly T[] {
  return isDemoMode()
    ? items.filter((item) => !DEMO_HIDDEN_ROUTES.has(item.href))
    : items;
}
