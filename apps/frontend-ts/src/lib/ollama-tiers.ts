import type { AppSettings, ModelRouting } from "@/lib/types/api";

/** Documented recommended Ollama defaults. */
export const RECOMMENDED_OLLAMA_SMALL = "qwen2.5:3b";
export const RECOMMENDED_OLLAMA_LARGE = "qwen2.5:7b";

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
        fallback_provider: existing?.fallback_provider ?? "anthropic",
        fallback_model: existing?.fallback_model ?? "claude-haiku-4-5-20251001",
      };
    }
  };

  apply(OLLAMA_SMALL_TASKS, smallModel);
  apply(OLLAMA_LARGE_TASKS, largeModel);

  return { ...settings, routing };
}
