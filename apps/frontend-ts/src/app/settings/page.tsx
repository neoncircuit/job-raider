"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod/v4";
import { toast } from "sonner";
import { settingsApi } from "@/lib/api/settings";
import type { AppSettings } from "@/lib/types/api";
import {
  RECOMMENDED_OLLAMA_LARGE,
  RECOMMENDED_OLLAMA_SMALL,
  applyCloudFallbackProvider,
  applyOllamaTierModelsLocally,
  deriveOllamaTierModels,
  type CloudFallbackProvider,
} from "@/lib/ollama-tiers";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";

/**
 * Build a human-readable label for an Ollama model option.
 *
 * @param name - Model tag (e.g. ``qwen2.5:3b``).
 * @param recommended - Recommended tag for this tier.
 * @param installed - Tags currently reported by Ollama.
 * @returns Display label with optional recommended / not-installed suffixes.
 */
function ollamaOptionLabel(
  name: string,
  recommended: string,
  installed: string[],
): string {
  const notes: string[] = [];
  if (name === recommended) notes.push("recommended");
  if (!installed.includes(name)) notes.push("not installed");
  return notes.length > 0 ? `${name} (${notes.join(", ")})` : name;
}

// ── Schema ────────────────────────────────────────────────────────────────────

const schema = z.object({
  api_config: z.object({
    anthropic_api_key: z.string().optional(),
    gemini_api_key: z.string().optional(),
    cloud_fallback_provider: z.enum(["anthropic", "gemini"]),
    ollama_host: z.string().min(1, "Required"),
  }),
  model_params: z.object({
    temperature: z.number().min(0).max(2),
    max_tokens: z.number().int().min(1).max(32000),
    top_p: z.number().min(0).max(1),
  }),
  cost_limits: z.object({
    max_api_cost_per_run: z.number().min(0),
    enable_cache: z.boolean(),
    cache_ttl: z.number().int().min(0),
  }),
});

type FormValues = z.infer<typeof schema>;

// ── Form ──────────────────────────────────────────────────────────────────────

/**
 * Settings form with API, Ollama model tiers, parameters, and cost limits.
 *
 * Remount via ``key`` when server settings change so local draft state resets
 * without syncing through an effect.
 *
 * @param initial - Settings loaded from the API.
 * @returns Configured settings form element.
 */
function SettingsForm({ initial }: { initial: AppSettings }) {
  const qc = useQueryClient();
  const initialTiers = deriveOllamaTierModels(initial.routing);
  const [routing, setRouting] = useState(initial.routing);
  const [smallModel, setSmallModel] = useState(initialTiers.small);
  const [largeModel, setLargeModel] = useState(initialTiers.large);
  const [modelsDirty, setModelsDirty] = useState(false);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      api_config: {
        anthropic_api_key: initial.api_config.anthropic_api_key ?? "",
        gemini_api_key: initial.api_config.gemini_api_key ?? "",
        cloud_fallback_provider:
          initial.api_config.cloud_fallback_provider === "gemini"
            ? "gemini"
            : "anthropic",
        ollama_host: initial.api_config.ollama_host,
      },
      model_params: initial.model_params,
      cost_limits: initial.cost_limits,
    },
  });

  const { data: models } = useQuery({
    queryKey: ["settings-models"],
    queryFn: settingsApi.getModels,
    staleTime: 30_000,
  });

  const installed = models?.ollama_installed ?? [];
  const recommendedSmall =
    models?.recommended?.small ?? RECOMMENDED_OLLAMA_SMALL;
  const recommendedLarge =
    models?.recommended?.large ?? RECOMMENDED_OLLAMA_LARGE;
  const recommendedInstalled =
    installed.includes(recommendedSmall) &&
    installed.includes(recommendedLarge);

  const ensureOption = (value: string, options: string[]) =>
    value && !options.includes(value) ? [value, ...options] : options;

  // Dropdown lists installed tags only (catalog phantoms like gemma stay out).
  const smallOptions = ensureOption(smallModel, installed);
  const largeOptions = ensureOption(largeModel, installed);

  const applyTier = (small: string, large: string) => {
    const next = applyOllamaTierModelsLocally(
      { ...initial, routing },
      small,
      large,
    );
    setRouting(next.routing);
    setSmallModel(small);
    setLargeModel(large);
    setModelsDirty(true);
  };

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const withTiers = applyOllamaTierModelsLocally(
        { ...initial, routing, ...values },
        smallModel,
        largeModel,
      );
      return settingsApi.update(withTiers);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["settings-models"] });
      setModelsDirty(false);
      toast.success("Settings saved.");
    },
    onError: () => toast.error("Failed to save settings."),
  });

  const reset = useMutation({
    mutationFn: settingsApi.reset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Settings reset to defaults.");
    },
    onError: () => toast.error("Failed to reset settings."),
  });

  const validate = useMutation({
    mutationFn: (values: FormValues) => {
      const withTiers = applyOllamaTierModelsLocally(
        { ...initial, routing, ...values },
        smallModel,
        largeModel,
      );
      return settingsApi.validate(withTiers);
    },
    onSuccess: (result) => {
      if (result.valid) {
        toast.success("Settings are valid.");
      } else {
        toast.error(result.errors.join(" | ") || "Validation failed.");
      }
    },
  });

  const temperature = useWatch({ control, name: "model_params.temperature" });
  const topP = useWatch({ control, name: "model_params.top_p" });
  const cacheEnabled = useWatch({ control, name: "cost_limits.enable_cache" });
  const cloudProvider = useWatch({
    control,
    name: "api_config.cloud_fallback_provider",
  }) as CloudFallbackProvider;

  /**
   * Switch cloud fallback provider and retarget routing fallbacks.
   *
   * @param next - Anthropic or Gemini.
   */
  const setCloudProvider = (next: CloudFallbackProvider) => {
    setValue("api_config.cloud_fallback_provider", next, { shouldDirty: true });
    setRouting(applyCloudFallbackProvider(routing, next));
    setModelsDirty(true);
  };

  return (
    <form onSubmit={handleSubmit((v) => save.mutate(v))} className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left col — API Config + Cost Limits */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">API Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="ollama_host">Ollama Host</Label>
                <Input
                  id="ollama_host"
                  placeholder="ollama:11434"
                  {...register("api_config.ollama_host")}
                />
                {errors.api_config?.ollama_host && (
                  <p className="text-xs text-red-500">
                    {errors.api_config.ollama_host.message}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  Docker Compose: use{" "}
                  <span className="font-mono">ollama:11434</span>. Ollama on the
                  host machine:{" "}
                  <span className="font-mono">host.docker.internal:11434</span>.
                  Native (no Docker):{" "}
                  <span className="font-mono">localhost:11434</span>.
                </p>
              </div>
              <div className="space-y-1">
                <Label htmlFor="cloud_provider">Cloud fallback provider</Label>
                <Select
                  value={cloudProvider}
                  onValueChange={(value) => {
                    if (value === "anthropic" || value === "gemini") {
                      setCloudProvider(value);
                    }
                  }}
                >
                  <SelectTrigger
                    id="cloud_provider"
                    className="w-full bg-background dark:bg-input/30"
                  >
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent alignItemWithTrigger={false}>
                    <SelectItem value="anthropic">Anthropic</SelectItem>
                    <SelectItem value="gemini">Google Gemini</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Used when local Ollama cannot complete a request. Pick the
                  provider you subscribe to — only one is needed.
                </p>
              </div>
              {cloudProvider === "anthropic" ? (
                <div className="space-y-1">
                  <Label htmlFor="anthropic_key">Anthropic API Key</Label>
                  <Input
                    id="anthropic_key"
                    type="password"
                    placeholder="sk-ant-…"
                    autoComplete="off"
                    {...register("api_config.anthropic_api_key")}
                  />
                  <p className="text-xs text-muted-foreground">
                    Optional. Leave blank to rely on{" "}
                    <span className="font-mono">ANTHROPIC_API_KEY</span> in the
                    environment, or run Ollama-only.
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <Label htmlFor="gemini_key">Gemini API Key</Label>
                  <Input
                    id="gemini_key"
                    type="password"
                    placeholder="AIza…"
                    autoComplete="off"
                    {...register("api_config.gemini_api_key")}
                  />
                  <p className="text-xs text-muted-foreground">
                    Optional. Leave blank to rely on{" "}
                    <span className="font-mono">GEMINI_API_KEY</span> in the
                    environment, or run Ollama-only.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Ollama Models</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Choose any installed Ollama model for small (fast) and large
                (quality) tasks. Documented recommended defaults are{" "}
                <span className="font-mono">{recommendedSmall}</span> and{" "}
                <span className="font-mono">{recommendedLarge}</span>.
              </p>
              {installed.length === 0 && (
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  No models detected at the configured Ollama host. Dropdowns
                  may still show your last-saved choices (marked not installed)
                  until the host is reachable. In Docker use{" "}
                  <span className="font-mono">ollama:11434</span>, pull a model
                  if needed, save the host, then refresh.
                </p>
              )}
              {installed.length === 0 && (smallModel || largeModel) && (
                <p className="text-xs text-muted-foreground">
                  Last saved:{" "}
                  <span className="font-mono">{smallModel || "—"}</span> /{" "}
                  <span className="font-mono">{largeModel || "—"}</span>
                </p>
              )}
              <div className="space-y-1">
                <Label htmlFor="ollama_small">Small model (fast)</Label>
                <Select
                  value={smallModel}
                  onValueChange={(value) => {
                    if (typeof value === "string" && value) {
                      applyTier(value, largeModel);
                    }
                  }}
                >
                  <SelectTrigger
                    id="ollama_small"
                    className="w-full bg-background dark:bg-input/30"
                  >
                    <SelectValue placeholder="Select a model">
                      {smallModel
                        ? ollamaOptionLabel(
                            smallModel,
                            recommendedSmall,
                            installed,
                          )
                        : null}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent alignItemWithTrigger={false}>
                    {smallOptions.length === 0 && smallModel && (
                      <SelectItem value={smallModel}>
                        {ollamaOptionLabel(
                          smallModel,
                          recommendedSmall,
                          installed,
                        )}
                      </SelectItem>
                    )}
                    {smallOptions.map((name) => (
                      <SelectItem key={name} value={name}>
                        {ollamaOptionLabel(name, recommendedSmall, installed)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="ollama_large">Large model (quality)</Label>
                <Select
                  value={largeModel}
                  onValueChange={(value) => {
                    if (typeof value === "string" && value) {
                      applyTier(smallModel, value);
                    }
                  }}
                >
                  <SelectTrigger
                    id="ollama_large"
                    className="w-full bg-background dark:bg-input/30"
                  >
                    <SelectValue placeholder="Select a model">
                      {largeModel
                        ? ollamaOptionLabel(
                            largeModel,
                            recommendedLarge,
                            installed,
                          )
                        : null}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent alignItemWithTrigger={false}>
                    {largeOptions.length === 0 && largeModel && (
                      <SelectItem value={largeModel}>
                        {ollamaOptionLabel(
                          largeModel,
                          recommendedLarge,
                          installed,
                        )}
                      </SelectItem>
                    )}
                    {largeOptions.map((name) => (
                      <SelectItem key={name} value={name}>
                        {ollamaOptionLabel(name, recommendedLarge, installed)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!recommendedInstalled}
                  onClick={() => applyTier(recommendedSmall, recommendedLarge)}
                >
                  Use recommended (3b / 7b)
                </Button>
                {installed.length > 0 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const first = installed[0];
                      const second = installed[1] ?? installed[0];
                      applyTier(first, second);
                    }}
                  >
                    Use first installed models
                  </Button>
                )}
              </div>
              {!recommendedInstalled && (
                <p className="text-xs text-muted-foreground">
                  Recommended tags{" "}
                  <span className="font-mono">{recommendedSmall}</span> /{" "}
                  <span className="font-mono">{recommendedLarge}</span> are not
                  both installed yet. Pull them with Ollama, or pick from the
                  list above.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Cost Limits</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="max_cost">Max API Cost per Run (USD)</Label>
                <Input
                  id="max_cost"
                  type="number"
                  step="0.01"
                  min={0}
                  {...register("cost_limits.max_api_cost_per_run", {
                    valueAsNumber: true,
                  })}
                />
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  id="enable_cache"
                  checked={cacheEnabled}
                  onCheckedChange={(v) =>
                    setValue("cost_limits.enable_cache", v, {
                      shouldDirty: true,
                    })
                  }
                />
                <Label htmlFor="enable_cache">Enable Response Cache</Label>
              </div>
              {cacheEnabled && (
                <div className="space-y-1">
                  <Label htmlFor="cache_ttl">Cache TTL (seconds)</Label>
                  <Input
                    id="cache_ttl"
                    type="number"
                    min={0}
                    {...register("cost_limits.cache_ttl", {
                      valueAsNumber: true,
                    })}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right col — Model Parameters */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Model Parameters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Temperature</Label>
                <span className="text-sm font-mono text-foreground">
                  {temperature.toFixed(2)}
                </span>
              </div>
              <Slider
                min={0}
                max={2}
                step={0.01}
                value={[temperature]}
                onValueChange={(v) => {
                  const val = Array.isArray(v) ? v[0] : (v as number);
                  setValue("model_params.temperature", val, {
                    shouldDirty: true,
                  });
                }}
              />
              <p className="text-xs text-muted-foreground">
                Lower = more focused. Higher = more creative.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Top P</Label>
                <span className="text-sm font-mono text-foreground">
                  {topP.toFixed(2)}
                </span>
              </div>
              <Slider
                min={0}
                max={1}
                step={0.01}
                value={[topP]}
                onValueChange={(v) => {
                  const val = Array.isArray(v) ? v[0] : (v as number);
                  setValue("model_params.top_p", val, { shouldDirty: true });
                }}
              />
              <p className="text-xs text-muted-foreground">
                Nucleus sampling cutoff. 0.9 is a good default.
              </p>
            </div>

            <div className="space-y-1">
              <Label htmlFor="max_tokens">Max Tokens</Label>
              <Input
                id="max_tokens"
                type="number"
                min={1}
                max={32000}
                {...register("model_params.max_tokens", {
                  valueAsNumber: true,
                })}
              />
              <p className="text-xs text-muted-foreground">
                Maximum response length. 4096 covers most tasks.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex gap-3 border-t pt-4">
        <Button
          type="submit"
          disabled={save.isPending || (!isDirty && !modelsDirty)}
        >
          {save.isPending ? "Saving…" : "Save Settings"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => handleSubmit((v) => validate.mutate(v))()}
          disabled={validate.isPending}
        >
          Validate
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => reset.mutate()}
          disabled={reset.isPending}
          className="ml-auto text-red-600 hover:text-red-700"
        >
          Reset to Defaults
        </Button>
      </div>
    </form>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * Settings page: always renders chrome, with loading/error inside the container.
 *
 * @returns Settings page with API, model, and cost configuration.
 */
export default function SettingsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
    staleTime: 60_000,
  });

  return (
    <PageContainer variant="wide">
      <PageHeader
        title="Settings"
        subtitle="Configure model routing, API keys, and cost limits."
      />
      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading settings…</p>
      )}
      {isError && <QueryErrorBanner message="Failed to load settings." />}
      {data && (
        <SettingsForm
          key={data.updated_at ?? data.version ?? "settings"}
          initial={data}
        />
      )}
    </PageContainer>
  );
}
