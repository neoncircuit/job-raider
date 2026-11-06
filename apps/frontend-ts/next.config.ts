import type { NextConfig } from "next";

/**
 * The demo build is a static site with no Next.js server. Only `.tsx` files
 * are routes in it, so the server-only proxy
 * (`src/app/api/proxy/[...path]/route.ts`) is left out. Pages and layouts are
 * all `.tsx`, so they stay. A static export has no `redirects`, so
 * `src/app/page.tsx` does that work in the demo.
 *
 * The server build writes an empty flag into the bundle. With no value,
 * Next.js leaves `process.env.NEXT_PUBLIC_DEMO_MODE` as a runtime read, and
 * the bundler then keeps the demo code.
 */
const isDemo = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

const nextConfig: NextConfig = isDemo
  ? {
      output: "export",
      basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
      pageExtensions: ["tsx"],
    }
  : {
      output: "standalone",
      env: { NEXT_PUBLIC_DEMO_MODE: "" },
      async redirects() {
        return [
          {
            source: "/",
            destination: "/dashboard",
            permanent: false,
          },
        ];
      },
    };

export default nextConfig;
