"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod/v4";
import { toast } from "sonner";
import { settingsApi } from "@/lib/api/settings";
import type { AppSettings } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { PageContainer } from "@/components/layout/PageContainer";

// ── Schema ────────────────────────────────────────────────────────────────────

const schema = z.object({
  api_config: z.object({
    anthropic_api_key: z.string().optional(),
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

function SettingsForm({ initial }: { initial: AppSettings }) {
  const qc = useQueryClient();

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
        ollama_host: initial.api_config.ollama_host,
      },
      model_params: initial.model_params,
      cost_limits: initial.cost_limits,
    },
  });

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      settingsApi.update({ ...initial, ...values }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
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
    mutationFn: (values: FormValues) =>
      settingsApi.validate({ ...initial, ...values }),
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
                  placeholder="http://localhost:11434"
                  {...register("api_config.ollama_host")}
                />
                {errors.api_config?.ollama_host && (
                  <p className="text-xs text-red-500">
                    {errors.api_config.ollama_host.message}
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <Label htmlFor="anthropic_key">Anthropic API Key</Label>
                <Input
                  id="anthropic_key"
                  type="password"
                  placeholder="sk-ant-…"
                  {...register("api_config.anthropic_api_key")}
                />
                <p className="text-xs text-gray-400">
                  Leave blank to use Ollama only.
                </p>
              </div>
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
                <span className="text-sm font-mono text-gray-700">
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
              <p className="text-xs text-gray-400">
                Lower = more focused. Higher = more creative.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Top P</Label>
                <span className="text-sm font-mono text-gray-700">
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
              <p className="text-xs text-gray-400">
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
              <p className="text-xs text-gray-400">
                Maximum response length. 4096 covers most tasks.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex gap-3 border-t pt-4">
        <Button type="submit" disabled={save.isPending || !isDirty}>
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

export default function SettingsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
    staleTime: 60_000,
  });

  if (isLoading)
    return <p className="text-sm text-gray-400 p-4">Loading settings…</p>;
  if (isError || !data)
    return <p className="text-sm text-red-500 p-4">Failed to load settings.</p>;

  return (
    <PageContainer variant="form">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure model routing, API keys, and cost limits.
        </p>
      </div>
      <SettingsForm initial={data} />
    </PageContainer>
  );
}
