import { redirect } from "next/navigation";

/**
 * Send the root path to the dashboard in the static demo build.
 *
 * A static export does not support `redirects` in `next.config.ts`. In the
 * server build, that config answers first, with an HTTP redirect.
 *
 * @returns Never: the redirect ends the render.
 */
export default function Home(): never {
  redirect("/dashboard");
}
