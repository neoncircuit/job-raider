"use client";

import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/lib/api/health";
import { cn } from "@/lib/utils/cn";

export function ConnectionStatus() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.getHealth,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const status = isError ? "unreachable" : (data?.status ?? "unknown");

  const dotClass = cn(
    "h-1.5 w-1.5 rounded-full shrink-0",
    status === "healthy" && "bg-emerald-400 animate-pulse",
    status === "degraded" && "bg-amber-400",
    (status === "unhealthy" || status === "unreachable") && "bg-red-400",
    status === "unknown" && "bg-slate-500"
  );

  const textClass = cn(
    "text-xs font-medium",
    status === "healthy" && "text-emerald-400",
    status === "degraded" && "text-amber-400",
    (status === "unhealthy" || status === "unreachable") && "text-red-400",
    status === "unknown" && "text-slate-500"
  );

  const labels: Record<string, string> = {
    healthy: "Connected",
    degraded: "Degraded",
    unhealthy: "Unhealthy",
    unreachable: "Unreachable",
    unknown: "Connecting…",
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2.5">
      <span className={dotClass} />
      <span className={textClass}>{labels[status] ?? status}</span>
    </div>
  );
}
