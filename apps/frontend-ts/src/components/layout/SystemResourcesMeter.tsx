"use client";

import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/lib/api/health";
import { cn } from "@/lib/utils/cn";

/**
 * Format a utilization percentage for compact sidebar display.
 *
 * @param value - Percent in ``[0, 100]``, or null when unavailable.
 * @returns Short label such as ``42%`` or an em dash.
 */
function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value)}%`;
}

/**
 * Compact horizontal meter bar for a single resource.
 *
 * @param label - Short label (CPU / RAM / GPU).
 * @param percent - Fill percent, or null when the resource is unavailable.
 * @param detail - Optional secondary text (e.g. VRAM).
 */
function ResourceBar({
  label,
  percent,
  detail,
}: {
  label: string;
  percent: number | null | undefined;
  detail?: string;
}) {
  const clamped =
    percent == null || Number.isNaN(percent)
      ? null
      : Math.max(0, Math.min(100, percent));

  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <span className="font-mono text-[10px] tabular-nums text-sidebar-foreground">
          {formatPercent(clamped)}
          {detail ? (
            <span className="ml-1 text-muted-foreground">{detail}</span>
          ) : null}
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-sm bg-sidebar-border">
        <div
          className={cn(
            "h-full rounded-sm transition-[width] duration-500 ease-out",
            clamped == null && "w-0 bg-transparent",
            clamped != null && clamped < 70 && "bg-emerald-500/80",
            clamped != null &&
              clamped >= 70 &&
              clamped < 90 &&
              "bg-amber-500/80",
            clamped != null && clamped >= 90 && "bg-red-500/80",
          )}
          style={clamped != null ? { width: `${clamped}%` } : undefined}
        />
      </div>
    </div>
  );
}

/**
 * Sidebar strip that polls backend CPU / RAM / GPU usage every 5 seconds.
 *
 * Readings reflect what the API process (or container) observes.
 *
 * @returns Compact resource meter element.
 */
export function SystemResourcesMeter() {
  const { data, isError } = useQuery({
    queryKey: ["health-resources"],
    queryFn: healthApi.getResources,
    staleTime: 4_000,
    refetchInterval: 5_000,
  });

  const cpu = data?.cpu.percent ?? null;
  const ram = data?.ram.percent ?? null;
  const gpuUtil = data?.gpu?.utilization_percent ?? null;
  const gpuMem =
    data?.gpu != null
      ? `${Math.round(data.gpu.memory_used_mb)}/${Math.round(data.gpu.memory_total_mb)} MB`
      : undefined;

  return (
    <div className="space-y-2 px-4 py-2.5">
      <p className="font-heading text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Resources
      </p>
      {isError ? (
        <p className="text-[10px] text-muted-foreground">Unavailable</p>
      ) : (
        <div className="space-y-2">
          <ResourceBar label="CPU" percent={cpu} />
          <ResourceBar label="RAM" percent={ram} />
          <ResourceBar label="GPU" percent={gpuUtil} detail={gpuMem} />
        </div>
      )}
    </div>
  );
}
