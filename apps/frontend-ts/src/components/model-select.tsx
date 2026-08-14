"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { settingsApi } from "@/lib/api/settings";
import {
  SETTINGS_DEFAULT_MODEL_VALUE,
  buildModelSelectOptions,
  resolveWriterModelOverride,
} from "@/lib/model-select";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface TaskModelSelectProps {
  /** Routing task key, e.g. cover_letter_writing. */
  taskType: string;
  /** Accessible label for the control. */
  label?: string;
  /** Session override value (sentinel or model id). */
  value: string;
  /** Called when the user picks a value (including Settings default). */
  onValueChange: (value: string) => void;
  /** Optional className for the outer wrapper. */
  className?: string;
}

/**
 * Per-section model picker: Settings baseline + provider allowlist,
 * with foreign-provider models shown greyed/disabled.
 *
 * Provider itself is never changed here — only the model name.
 *
 * @param props - Task type, controlled value, and change handler.
 */
export function TaskModelSelect({
  taskType,
  label = "Writer model",
  value,
  onValueChange,
  className,
}: TaskModelSelectProps) {
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
    staleTime: 60_000,
  });
  const modelsQuery = useQuery({
    queryKey: ["settings", "models"],
    queryFn: settingsApi.getModels,
    staleTime: 60_000,
  });

  const { provider, baselineModel, options } = useMemo(
    () =>
      buildModelSelectOptions(
        taskType,
        settingsQuery.data?.routing,
        modelsQuery.data,
      ),
    [taskType, settingsQuery.data?.routing, modelsQuery.data],
  );

  const selectable = options.filter((opt) => !opt.disabled);
  const greyed = options.filter((opt) => opt.disabled);
  const isLoading = settingsQuery.isLoading || modelsQuery.isLoading;
  const valueAllowed = options.some(
    (opt) => opt.value === value && !opt.disabled,
  );
  const effectiveValue = valueAllowed
    ? value
    : SETTINGS_DEFAULT_MODEL_VALUE;

  useEffect(() => {
    if (isLoading || options.length === 0) return;
    if (value && !valueAllowed && value !== SETTINGS_DEFAULT_MODEL_VALUE) {
      onValueChange(SETTINGS_DEFAULT_MODEL_VALUE);
    }
  }, [isLoading, options.length, value, valueAllowed, onValueChange]);

  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={`model-select-${taskType}`}>{label}</Label>
      <Select
        value={effectiveValue}
        onValueChange={(next) => {
          if (typeof next === "string") onValueChange(next);
        }}
        disabled={isLoading || selectable.length === 0}
      >
        <SelectTrigger
          id={`model-select-${taskType}`}
          className="w-full min-w-0"
          size="default"
        >
          <SelectValue placeholder="Loading models…" />
        </SelectTrigger>
        <SelectContent align="start" className="max-h-72">
          {selectable.length > 0 && (
            <SelectGroup>
              <SelectLabel>
                {provider ? `Available (${provider})` : "Available"}
              </SelectLabel>
              {selectable.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
          {greyed.length > 0 && (
            <SelectGroup>
              <SelectLabel>Other providers (switch in Settings)</SelectLabel>
              {greyed.map((opt) => (
                <SelectItem
                  key={`grey-${opt.value}`}
                  value={opt.value}
                  disabled
                  className="text-muted-foreground"
                >
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">
        Uses your Settings provider
        {provider ? ` (${provider})` : ""}
        {baselineModel ? `; default ${baselineModel}` : ""}. Change provider in{" "}
        <Link href="/settings" className="underline underline-offset-2">
          Settings
        </Link>
        .
      </p>
    </div>
  );
}

export { resolveWriterModelOverride, SETTINGS_DEFAULT_MODEL_VALUE };
