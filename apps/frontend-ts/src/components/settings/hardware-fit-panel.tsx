"use client";

import { Cpu, Download, RefreshCw } from "lucide-react";
import { FIT_LABEL_TEXT, fitBadgeClass, fitTitle } from "@/lib/hardware-fit";
import type { HardwareFitReport, InstalledFit } from "@/lib/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Fit badge for one installed model.
 *
 * @param props.fit - Fit of the model, or undefined when there is none.
 * @returns The badge, or a dash.
 */
export function FitBadge({ fit }: { fit: InstalledFit | undefined }) {
  if (!fit) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge
      className={`${fitBadgeClass(fit.label)} text-xs`}
      title={fitTitle(fit)}
    >
      {FIT_LABEL_TEXT[fit.label]}
    </Badge>
  );
}

/**
 * Hardware fit summary for the Local models card (Step 6, MH-4).
 *
 * With llmfit, it shows the safety budget and models that fit it. Without
 * llmfit, it says why and how to install it; the rest of the card works.
 *
 * @param props.fit - Report from ``GET /api/hardware/fit``, if loaded.
 * @param props.isLoading - True while the report loads.
 * @param props.isError - True when the report request failed.
 * @param props.isRefreshing - True while a refresh runs.
 * @param props.pullDisabled - True when a pull cannot start now.
 * @param props.onRefresh - Run llmfit again.
 * @param props.onPull - Start a pull of a suggested model.
 * @returns The panel.
 */
export function HardwareFitPanel({
  fit,
  isLoading,
  isError,
  isRefreshing,
  pullDisabled,
  onRefresh,
  onPull,
}: {
  fit: HardwareFitReport | undefined;
  isLoading: boolean;
  isError: boolean;
  isRefreshing: boolean;
  pullDisabled: boolean;
  onRefresh: () => void;
  onPull: (model: string) => void;
}) {
  if (isLoading) {
    return (
      <p className="text-xs text-muted-foreground">Checking hardware fit…</p>
    );
  }
  if (isError || !fit) {
    return (
      <p className="text-xs text-muted-foreground">
        Hardware fit could not load.
      </p>
    );
  }
  if (!fit.available) {
    return (
      <div
        className="rounded-md border border-dashed p-3 text-xs space-y-1"
        aria-label="Hardware fit"
      >
        <p className="font-medium text-foreground">
          Hardware fit is off (llmfit is optional and recommended)
        </p>
        <p className="text-muted-foreground">{fit.reason}</p>
        {fit.install_hint && (
          <p className="text-muted-foreground">{fit.install_hint}</p>
        )}
      </div>
    );
  }

  const total = fit.hardware?.gpu_vram_gb;
  return (
    <div className="rounded-md border p-3 space-y-3" aria-label="Hardware fit">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <Cpu className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {total ? (
              <>
                Safety budget{" "}
                <span className="font-medium text-foreground">
                  {fit.budget_gb.toFixed(1)} GB
                </span>{" "}
                of {total.toFixed(1)} GB GPU memory ({fit.headroom_percent}%)
              </>
            ) : (
              "No GPU found, so models run on the CPU"
            )}
            {fit.hardware?.gpu_name ? ` on ${fit.hardware.gpu_name}` : ""}.
            Checked by llmfit {fit.llmfit_version}.
          </span>
        </p>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Refresh hardware fit"
          disabled={isRefreshing}
          onClick={onRefresh}
        >
          <RefreshCw
            className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
          />
        </Button>
      </div>

      {fit.suggestions.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-foreground">
            Suggested for your hardware
          </p>
          <ul className="space-y-1">
            {fit.suggestions.map((s) => (
              <li
                key={s.ollama_name}
                className="flex flex-wrap items-center justify-between gap-2 text-xs"
              >
                <span>
                  <span className="font-mono text-foreground">
                    {s.ollama_name}
                  </span>
                  <span className="text-muted-foreground">
                    {" "}
                    {[
                      s.category,
                      s.params_b != null ? `${s.params_b} B` : null,
                      `needs about ${s.memory_required_gb.toFixed(1)} GB`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  aria-label={`Pull ${s.ollama_name}`}
                  disabled={pullDisabled}
                  onClick={() => onPull(s.ollama_name)}
                >
                  <Download className="mr-1 h-3.5 w-3.5" />
                  Pull
                </Button>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-muted-foreground">
            Estimates from llmfit, not benchmarks. You choose what to pull.
          </p>
        </div>
      )}
    </div>
  );
}
