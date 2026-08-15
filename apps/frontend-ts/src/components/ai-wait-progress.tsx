"use client";

import { useId } from "react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils/cn";

export interface AiWaitProgressProps {
  /** Current honest stage label, for example "Writing cover letter…". */
  label: string;
  /**
   * Real 0–100 progress when the backend reports a stage fraction.
   * Omit or pass null for an indeterminate bar. Do not invent a percent.
   */
  value?: number | null;
  /** Optional secondary line under the stage label. */
  hint?: string;
  /** Compact sizing for dense cards and side panels. */
  size?: "default" | "compact";
  className?: string;
}

/**
 * Shared wait indicator for long AI calls.
 *
 * Uses a determinate bar only when `value` is a real 0–100 fraction.
 * Otherwise it shows an indeterminate bar plus the current stage label.
 *
 * @param props - Component props.
 * @returns Accessible progress UI for an in-flight AI wait.
 */
export function AiWaitProgress({
  label,
  value = null,
  hint,
  size = "default",
  className,
}: AiWaitProgressProps) {
  const labelId = useId();
  const determinate = typeof value === "number" && Number.isFinite(value);
  const clamped = determinate ? Math.min(100, Math.max(0, value)) : 0;
  const compact = size === "compact";

  return (
    <div
      className={cn("w-full space-y-1.5", className)}
      aria-busy="true"
      data-slot="ai-wait-progress"
    >
      <p
        id={labelId}
        className={cn(
          "font-medium text-foreground",
          compact ? "text-xs" : "text-sm",
        )}
      >
        {label}
      </p>
      {hint ? (
        <p
          className={cn(
            "text-muted-foreground",
            compact ? "text-[11px]" : "text-xs",
          )}
        >
          {hint}
        </p>
      ) : null}
      {determinate ? (
        <Progress
          value={clamped}
          className="w-full gap-0"
          aria-labelledby={labelId}
        />
      ) : (
        <div
          role="progressbar"
          aria-labelledby={labelId}
          className={cn(
            "relative w-full overflow-hidden rounded-full bg-muted",
            compact ? "h-1" : "h-1.5",
          )}
          data-slot="ai-wait-track"
        >
          <div
            className="ai-wait-indeterminate-bar absolute inset-y-0 w-1/3 rounded-full bg-primary"
            data-slot="ai-wait-indicator"
          />
        </div>
      )}
    </div>
  );
}
