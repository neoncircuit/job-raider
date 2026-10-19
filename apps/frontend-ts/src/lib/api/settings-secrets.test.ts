import { describe, expect, it } from "vitest";

import { omitBlankApiKeys } from "./settings";
import type { AppSettings } from "@/lib/types/api";

/**
 * Minimal settings fixture for omitBlankApiKeys tests.
 *
 * @param api - Partial api_config overrides.
 * @returns AppSettings with routing and cost defaults.
 */
function baseSettings(api: AppSettings["api_config"]): AppSettings {
  return {
    routing: {},
    api_config: api,
    model_params: { temperature: 0.7, max_tokens: 1024, top_p: 0.9 },
    cost_limits: {
      max_api_cost_per_run: 1,
      enable_cache: true,
      cache_ttl: 60,
    },
  };
}

describe("omitBlankApiKeys", () => {
  it("removes blank key fields so PUT does not send empty secrets", () => {
    const out = omitBlankApiKeys(
      baseSettings({
        anthropic_api_key: "  ",
        gemini_api_key: "",
        has_anthropic_key: true,
        ollama_host: "localhost:11434",
      }),
    );
    expect(out.api_config).not.toHaveProperty("anthropic_api_key");
    expect(out.api_config).not.toHaveProperty("gemini_api_key");
    expect(out.api_config.has_anthropic_key).toBe(true);
  });

  it("keeps trimmed non-empty keys the user typed", () => {
    const out = omitBlankApiKeys(
      baseSettings({
        anthropic_api_key: "  sk-ant-new  ",
        gemini_api_key: "AIza-new",
        ollama_host: "localhost:11434",
      }),
    );
    expect(out.api_config.anthropic_api_key).toBe("sk-ant-new");
    expect(out.api_config.gemini_api_key).toBe("AIza-new");
  });
});
