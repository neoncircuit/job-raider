import { describe, expect, it } from "vitest";
import {
  RECOMMENDED_OLLAMA_LARGE,
  RECOMMENDED_OLLAMA_SMALL,
  applyCloudFallbackProvider,
  applyOllamaTierModelsLocally,
  deriveOllamaTierModels,
} from "@/lib/ollama-tiers";
import type { AppSettings } from "@/lib/types/api";

const baseSettings = (): AppSettings => ({
  routing: {
    selection: {
      task_type: "selection",
      primary_provider: "ollama",
      primary_model: RECOMMENDED_OLLAMA_SMALL,
      fallback_provider: "anthropic",
      fallback_model: "claude-haiku-4-5-20251001",
    },
    resume_writing: {
      task_type: "resume_writing",
      primary_provider: "ollama",
      primary_model: RECOMMENDED_OLLAMA_LARGE,
      fallback_provider: "anthropic",
      fallback_model: "claude-sonnet-4-6",
    },
  },
  api_config: {
    ollama_host: "localhost:11434",
    cloud_fallback_provider: "anthropic",
  },
  model_params: { temperature: 0.7, max_tokens: 4096, top_p: 0.9 },
  cost_limits: {
    max_api_cost_per_run: 5,
    enable_cache: true,
    cache_ttl: 3600,
  },
});

describe("ollama-tiers", () => {
  it("derives recommended defaults from empty routing", () => {
    const tiers = deriveOllamaTierModels({});
    expect(tiers.small).toBe(RECOMMENDED_OLLAMA_SMALL);
    expect(tiers.large).toBe(RECOMMENDED_OLLAMA_LARGE);
  });

  it("applies small/large models onto ollama-primary tasks", () => {
    const next = applyOllamaTierModelsLocally(
      baseSettings(),
      "gemma3:4b",
      "qwen2.5:14b",
    );
    expect(next.routing.selection?.primary_model).toBe("gemma3:4b");
    expect(next.routing.resume_writing?.primary_model).toBe("qwen2.5:14b");
    expect(next.routing.scoring?.primary_model).toBe("gemma3:4b");
  });

  it("retargets cloud fallbacks to Gemini", () => {
    const next = applyCloudFallbackProvider(baseSettings().routing, "gemini");
    expect(next.selection?.fallback_provider).toBe("gemini");
    expect(next.selection?.fallback_model).toBe("gemini-2.5-flash");
    expect(next.resume_writing?.fallback_model).toBe("gemini-2.5-pro");
  });
});
