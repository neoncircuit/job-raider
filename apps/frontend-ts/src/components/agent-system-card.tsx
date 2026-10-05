"use client";

import { useQuery } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { formatPercentage } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

/** Badge classes per agent state; unknown states use the muted style. */
const STATE_CLASSES: Record<string, string> = {
  ready: "bg-success/10 text-success",
  busy: "bg-info/10 text-info",
  initializing: "bg-warning/10 text-warning",
  failed: "bg-destructive/10 text-destructive",
};

/**
 * One labelled boolean indicator for the system row.
 *
 * @param props.label - Indicator name.
 * @param props.ok - Whether the indicator is healthy.
 * @returns A dot with its label.
 */
function Indicator({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-sm text-foreground">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          ok ? "bg-success" : "bg-destructive",
        )}
      />
      {label}: {ok ? "OK" : "Down"}
    </span>
  );
}

/**
 * Read-only view of the multi-agent system for the Metrics page.
 *
 * Shows coordinator and message-bus health, totals, and one row per agent.
 * It has no controls; shutdown stays API-only.
 *
 * @returns The agent system section.
 */
export function AgentSystemCard() {
  const status = useQuery({
    queryKey: ["agents-status"],
    queryFn: ({ signal }) => agentsApi.getStatus(signal),
    refetchInterval: 15_000,
  });
  const performance = useQuery({
    queryKey: ["agents-performance"],
    queryFn: ({ signal }) => agentsApi.getPerformance(signal),
    refetchInterval: 15_000,
  });

  const system = status.data?.data;
  const totals = performance.data?.data;
  const agents = system ? Object.values(system.agent_status) : [];

  return (
    <section className="space-y-3" aria-label="Agent system">
      <h2 className="font-heading text-sm font-semibold uppercase tracking-wide text-foreground">
        Agent system
      </h2>

      {status.isLoading && (
        <p className="text-sm text-muted-foreground">Loading agent status…</p>
      )}

      {status.isError && (
        <QueryErrorBanner
          title="Could not load agent status"
          message={
            status.error instanceof Error
              ? status.error.message
              : "Unknown error"
          }
        />
      )}

      {system && (
        <>
          <div className="flex flex-wrap gap-6 rounded-lg border bg-card p-4">
            <Indicator label="Coordinator" ok={system.coordinator_running} />
            <Indicator label="Message bus" ok={system.communication_healthy} />
            <span className="text-sm text-muted-foreground">
              {system.registered_agents}{" "}
              {system.registered_agents === 1 ? "agent" : "agents"} registered
            </span>
            {totals && (
              <span className="text-sm text-muted-foreground">
                {totals.total_tasks_completed} tasks done ·{" "}
                {totals.total_tasks_failed} failed
              </span>
            )}
          </div>

          {agents.length === 0 ? (
            <EmptyState title="No agents registered" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-4">Agent</th>
                    <th className="pb-2 pr-4">State</th>
                    <th className="pb-2 pr-4">Tasks</th>
                    <th className="pb-2 pr-4">Success</th>
                    <th className="pb-2 pr-4">Avg time</th>
                    <th className="pb-2">Load</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {agents.map((a) => (
                    <tr key={a.agent_id}>
                      <td className="py-2 pr-4 text-foreground">
                        {a.agent_id}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge
                          className={cn(
                            "text-xs",
                            STATE_CLASSES[a.state] ??
                              "bg-muted text-muted-foreground",
                          )}
                        >
                          {a.state}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {a.performance.tasks_completed} done ·{" "}
                        {a.performance.tasks_failed} failed
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {formatPercentage(a.performance.success_rate * 100)}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {a.performance.average_execution_time.toFixed(1)} s
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {formatPercentage(a.performance.utilization * 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
