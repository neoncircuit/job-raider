import type { AvailableModelsResponse, ModelRouting } from "@/lib/types/api";

/** Sentinel Select value meaning “use Settings baseline for this task”. */
export const SETTINGS_DEFAULT_MODEL_VALUE = "__settings_default__";

export type ModelProvider = "ollama" | "anthropic" | "gemini";

export interface ModelSelectOption {
  value: string;
  label: string;
  provider: ModelProvider | "settings";
  disabled: boolean;
}

/**
 * Normalize a provider string from Settings routing.
 *
 * @param provider - Raw primary_provider value.
 * @returns Known provider key or null.
 */
export function normalizeModelProvider(
  provider: string | null | undefined,
): ModelProvider | null {
  const key = (provider || "").trim().toLowerCase();
  if (key === "ollama" || key === "anthropic" || key === "gemini") {
    return key;
  }
  return null;
}

/**
 * Build selectable + greyed model options for a TaskType.
 *
 * Allowlist: Anthropic/Gemini curated catalogs, or installed Ollama tags.
 * Grey list: foreign provider inventories (full catalogs + installed Ollama).
 *
 * @param taskType - Routing task key (e.g. cover_letter_writing).
 * @param routing - Settings routing map.
 * @param models - Available models payload from GET /settings/models.
 * @returns Options for a ModelSelect, including Settings default first.
 */
export function buildModelSelectOptions(
  taskType: string,
  routing: Record<string, ModelRouting> | undefined,
  models: AvailableModelsResponse | undefined,
): {
  provider: ModelProvider | null;
  baselineModel: string | null;
  options: ModelSelectOption[];
} {
  const route = routing?.[taskType];
  const provider = normalizeModelProvider(route?.primary_provider);
  const baselineModel = route?.primary_model?.trim() || null;

  const anthropic = [...(models?.anthropic ?? [])].sort();
  const gemini = [...(models?.gemini ?? [])].sort();
  const ollamaInstalled = [
    ...(models?.ollama_installed ?? models?.ollama ?? []),
  ].sort();

  const allowlist: string[] =
    provider === "anthropic"
      ? anthropic
      : provider === "gemini"
        ? gemini
        : provider === "ollama"
          ? ollamaInstalled
          : [];

  const options: ModelSelectOption[] = [];
  if (baselineModel) {
    options.push({
      value: SETTINGS_DEFAULT_MODEL_VALUE,
      label: `Settings default (${baselineModel})`,
      provider: "settings",
      disabled: false,
    });
  }

  const seen = new Set<string>([SETTINGS_DEFAULT_MODEL_VALUE]);
  for (const name of allowlist) {
    if (!name || seen.has(name)) continue;
    seen.add(name);
    options.push({
      value: name,
      label: name,
      provider: provider ?? "ollama",
      disabled: false,
    });
  }

  const greyGroups: Array<{ provider: ModelProvider; names: string[] }> = [
    { provider: "anthropic", names: anthropic },
    { provider: "gemini", names: gemini },
    { provider: "ollama", names: ollamaInstalled },
  ];
  for (const group of greyGroups) {
    if (group.provider === provider) continue;
    for (const name of group.names) {
      if (!name || seen.has(name)) continue;
      seen.add(name);
      options.push({
        value: name,
        label: `${name} (${group.provider})`,
        provider: group.provider,
        disabled: true,
      });
    }
  }

  return { provider, baselineModel, options };
}

/**
 * Resolve the model id to send on generate, or undefined for Settings default.
 *
 * @param selectedValue - Current Select value (may be sentinel).
 * @param baselineModel - Settings baseline for the task.
 * @returns Override model string, or undefined when using Settings default.
 */
export function resolveWriterModelOverride(
  selectedValue: string | null | undefined,
  baselineModel: string | null | undefined,
): string | undefined {
  if (
    !selectedValue ||
    selectedValue === SETTINGS_DEFAULT_MODEL_VALUE ||
    (baselineModel && selectedValue === baselineModel)
  ) {
    return undefined;
  }
  return selectedValue;
}
