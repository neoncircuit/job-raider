import type { AppSettings, ModelRouting } from "@/lib/types/api";

/** Documented recommended Ollama defaults. */
export const RECOMMENDED_OLLAMA_SMALL = "qwen2.5:3b";
export const RECOMMENDED_OLLAMA_LARGE = "qwen2.5:7b";

/**
 * Cloud providers selectable as Ollama fallbacks.
 *
 * ``none`` means local-only: never send prompts to a cloud API.
 */
export type CloudFallbackProvider = "none" | "anthropic" | "gemini";

const OLLAMA_SMALL_TASKS = [
  "selection",
  "scoring",
  "validation",
  "general",
  "question_answering",
  "trust_analysis",
  "cover_letter_review",
] as const;

const OLLAMA_LARGE_TASKS = [
  "jd_extraction",
  "resume_writing",
  "resume_parsing",
  "resume_analysis",
  "linkedin_analysis",
  "classification",
  "cover_letter_writing",
  "assessment_generation",
  "assessment_evaluation",
] as const;

const CLOUD_FALLBACK_SMALL: Record<"anthropic" | "gemini", string> = {
  anthropic: "claude-haiku-4-5-20251001",
  gemini: "gemini-2.5-flash",
};

const CLOUD_FALLBACK_LARGE: Record<"anthropic" | "gemini", string> = {
  anthropic: "claude-sonnet-4-6",
  gemini: "gemini-2.5-pro",
};

const CLOUD_PROVIDERS = new Set<string>(["anthropic", "gemini"]);

/**
 * Default cloud fallback model for a task tier.
 *
 * @param cloud - Selected cloud fallback provider (not ``none``).
 * @param taskType - Routing task key.
 * @returns Provider-specific model id.
 */
function defaultCloudFallbackModel(
  cloud: "anthropic" | "gemini",
  taskType: string,
): string {
  if ((OLLAMA_SMALL_TASKS as readonly string[]).includes(taskType)) {
    return CLOUD_FALLBACK_SMALL[cloud];
  }
  return CLOUD_FALLBACK_LARGE[cloud];
}

/**
 * Normalize a settings value to a cloud fallback choice.
 *
 * @param value - Raw settings value.
 * @returns A known cloud fallback provider.
 */
export function normalizeCloudFallbackProvider(
  value: string | null | undefined,
): CloudFallbackProvider {
  if (value === "anthropic" || value === "gemini" || value === "none") {
    return value;
  }
  return "none";
}

/**
 * Retarget Anthropic/Gemini fallbacks to the selected cloud provider.
 *
 * When ``cloud`` is ``none``, existing Anthropic/Gemini fallbacks are cleared.
 * Local Ollama-to-Ollama fallbacks are left unchanged.
 *
 * @param routing - Per-task routing map.
 * @param cloud - Cloud provider for Ollama failure fallback.
 * @returns Updated routing map.
 */
export function applyCloudFallbackProvider(
  routing: Record<string, ModelRouting>,
  cloud: CloudFallbackProvider,
): Record<string, ModelRouting> {
  const next: Record<string, ModelRouting> = {};
  for (const [task, entry] of Object.entries(routing)) {
    if (entry.fallback_provider === "ollama") {
      next[task] = entry;
      continue;
    }
    if (cloud === "none") {
      if (
        !entry.fallback_provider ||
        CLOUD_PROVIDERS.has(entry.fallback_provider)
      ) {
        next[task] = {
          ...entry,
          fallback_provider: null,
          fallback_model: null,
        };
      } else {
        next[task] = entry;
      }
      continue;
    }
    if (
      !entry.fallback_provider ||
      !CLOUD_PROVIDERS.has(entry.fallback_provider)
    ) {
      next[task] = entry;
      continue;
    }
    next[task] = {
      ...entry,
      fallback_provider: cloud,
      fallback_model: defaultCloudFallbackModel(cloud, task),
    };
  }
  return next;
}

/**
 * Derive the configured small/large Ollama models from routing.
 *
 * @param routing - Per-task routing map from settings.
 * @returns Tuple of small and large model names.
 */
export function deriveOllamaTierModels(routing: Record<string, ModelRouting>): {
  small: string;
  large: string;
} {
  const selection = routing.selection;
  const resume = routing.resume_writing;
  return {
    small:
      selection?.primary_provider === "ollama" && selection.primary_model
        ? selection.primary_model
        : RECOMMENDED_OLLAMA_SMALL,
    large:
      resume?.primary_provider === "ollama" && resume.primary_model
        ? resume.primary_model
        : RECOMMENDED_OLLAMA_LARGE,
  };
}

/**
 * Apply small/large Ollama models onto an AppSettings routing map.
 *
 * @param settings - Current settings object.
 * @param smallModel - Model for fast/small tasks.
 * @param largeModel - Model for quality/large tasks.
 * @returns New settings with updated routing.
 */
export function applyOllamaTierModelsLocally(
  settings: AppSettings,
  smallModel: string,
  largeModel: string,
): AppSettings {
  const cloud = normalizeCloudFallbackProvider(
    settings.api_config.cloud_fallback_provider,
  );
  const routing: Record<string, ModelRouting> = { ...settings.routing };

  const apply = (tasks: readonly string[], model: string) => {
    for (const task of tasks) {
      const existing = routing[task];
      if (existing && existing.primary_provider !== "ollama") {
        continue;
      }
      routing[task] = {
        task_type: task,
        primary_provider: "ollama",
        primary_model: model,
        fallback_provider: cloud === "none" ? null : cloud,
        fallback_model:
          cloud === "none" ? null : defaultCloudFallbackModel(cloud, task),
      };
    }
  };

  apply(OLLAMA_SMALL_TASKS, smallModel);
  apply(OLLAMA_LARGE_TASKS, largeModel);

  return {
    ...settings,
    routing: applyCloudFallbackProvider(routing, cloud),
  };
}
