/**
 * Job Raider - Vitest Configuration
 *
 * Vitest configuration for unit and integration testing.
 * Provides fast, native TypeScript testing with ESM support.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Use import.meta.url for ES module path resolution
const __dirname = new URL(".", import.meta.url).pathname;

export default defineConfig({
  plugins: [react()],

  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup/globals.ts"],

    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html", "lcov"],
      exclude: [
        "node_modules/",
        "tests/",
        "*.config.ts",
        "*.config.js",
        "src/lib/api/client.ts", // API client has complex dependencies
      ],
      // Coverage thresholds are intentionally not enforced yet: the current
      // test set covers only a small fraction of the app (~3% lines). Coverage
      // is still measured and reported. Re-enable thresholds (e.g. 80%) once
      // page/component coverage is built out.
    },

    // Include files matching these patterns
    include: ["**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}"],

    // Exclude files matching these patterns. E2E specs (tests/e2e/**) are run
    // by Playwright, not vitest, so they are excluded from the unit runner.
    exclude: [
      "node_modules",
      "dist",
      ".idea",
      ".git",
      ".cache",
      "tests/e2e/**",
    ],

    // Watch mode configuration
    watch: false,

    // Timeout for each test (milliseconds)
    testTimeout: 10000,

    // Timeout for each hook (milliseconds)
    hookTimeout: 10000,
  },

  resolve: {
    alias: {
      "@": `${__dirname}/src`,
      "@/components": `${__dirname}/src/components`,
      "@/lib": `${__dirname}/src/lib`,
      "@/app": `${__dirname}/src/app`,
    },
  },
});
