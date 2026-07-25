"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { metricsApi } from "@/lib/api/metrics";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { EmptyState } from "@/components/layout/EmptyState";
import {
  formatCurrency,
  formatPercentage,
  formatDatetime,
} from "@/lib/utils/format";

const PIE_COLORS = [
  "var(--chart-3)",
  "var(--chart-1)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold text-foreground">{value}</p>
    </div>
  );
}

export default function MetricsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: metricsApi.getSummary,
    staleTime: 60_000,
  });

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Metrics"
        subtitle="Cost tracking, outcome funnel, and system health."
      />

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading metrics…</p>
      )}

      {isError && (
        <QueryErrorBanner
          title="Failed to load metrics"
          message={error instanceof Error ? error.message : "Unknown error"}
        />
      )}

      {data && (
        <>
          {(() => {
            const { cost, outcomes, health } = data;
            const recent_calls = data.recent_calls ?? [];
            const applications = outcomes.total_applications ?? 0;
            const screeningRate = Number.isFinite(outcomes.screening_rate)
              ? formatPercentage(outcomes.screening_rate * 100)
              : "—";
            const offerRate = Number.isFinite(outcomes.offer_rate)
              ? formatPercentage(outcomes.offer_rate * 100)
              : "—";
            const acceptanceRate = Number.isFinite(outcomes.acceptance_rate)
              ? formatPercentage(outcomes.acceptance_rate * 100)
              : "—";

            const funnelData = [
              { name: "Applied", count: applications },
              {
                name: "Screening",
                count: Math.round(
                  applications * (outcomes.screening_rate || 0),
                ),
              },
              {
                name: "Offered",
                count: Math.round(applications * (outcomes.offer_rate || 0)),
              },
              {
                name: "Accepted",
                count: Math.round(
                  applications * (outcomes.acceptance_rate || 0),
                ),
              },
            ];

            const localCount = Math.round(
              (cost.local_usage_percent / 100) * cost.total_calls,
            );
            const apiCount = cost.total_calls - localCount;
            const costPieData = [
              { name: "Local (Ollama)", value: localCount },
              { name: "API (Claude)", value: apiCount },
            ];

            return (
              <>
                <section>
                  <h2 className="mb-3 font-heading text-sm font-semibold uppercase tracking-wide text-foreground">
                    Cost
                  </h2>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Tile
                      label="Total Spent"
                      value={formatCurrency(cost.total_usd)}
                    />
                    <Tile
                      label="Per Application"
                      value={formatCurrency(cost.per_application)}
                    />
                    <Tile
                      label="Total LLM Calls"
                      value={cost.total_calls.toLocaleString()}
                    />
                    <Tile
                      label="Local Usage"
                      value={formatPercentage(cost.local_usage_percent)}
                    />
                  </div>
                </section>

                <section>
                  <h2 className="mb-3 font-heading text-sm font-semibold uppercase tracking-wide text-foreground">
                    Outcomes
                  </h2>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Tile label="Applications" value={applications} />
                    <Tile label="Screening Rate" value={screeningRate} />
                    <Tile label="Offer Rate" value={offerRate} />
                    <Tile label="Acceptance Rate" value={acceptanceRate} />
                  </div>
                </section>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <section className="space-y-3">
                    <h3 className="font-heading text-base font-semibold text-foreground">
                      Application Funnel
                    </h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={funnelData} layout="vertical">
                        <XAxis type="number" tick={{ fontSize: 12 }} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={80}
                          tick={{ fontSize: 12 }}
                        />
                        <Tooltip formatter={(v) => [v, "Count"]} />
                        <Bar
                          dataKey="count"
                          fill="var(--chart-1)"
                          radius={[0, 4, 4, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </section>

                  <section className="space-y-3">
                    <h3 className="font-heading text-base font-semibold text-foreground">
                      LLM Call Distribution
                    </h3>
                    {cost.total_calls > 0 ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                          <Pie
                            data={costPieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={55}
                            outerRadius={80}
                            paddingAngle={3}
                            dataKey="value"
                          >
                            {costPieData.map((_, i) => (
                              <Cell
                                key={i}
                                fill={PIE_COLORS[i % PIE_COLORS.length]}
                              />
                            ))}
                          </Pie>
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <EmptyState
                        className="h-[280px] border-0 bg-transparent"
                        title="No calls recorded yet"
                      />
                    )}
                  </section>
                </div>

                <section className="space-y-3">
                  <h3 className="font-heading text-base font-semibold text-foreground">
                    Recent LLM Calls
                  </h3>
                  <div className="overflow-x-auto">
                    {recent_calls.length === 0 ? (
                      <EmptyState title="No calls recorded yet" />
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs text-muted-foreground">
                            <th className="pb-2 pr-4">Task</th>
                            <th className="pb-2 pr-4">Provider</th>
                            <th className="pb-2 pr-4">Model</th>
                            <th className="pb-2 pr-4">Cost</th>
                            <th className="pb-2">Time</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {recent_calls.map((c, i) => (
                            <tr key={i} className="hover:bg-muted">
                              <td className="py-2 pr-4 text-foreground">
                                {c.task_type}
                              </td>
                              <td className="py-2 pr-4 capitalize text-muted-foreground">
                                {c.provider}
                              </td>
                              <td className="py-2 pr-4 text-muted-foreground">
                                {c.model}
                              </td>
                              <td className="py-2 pr-4 text-foreground">
                                {formatCurrency(c.cost_usd)}
                              </td>
                              <td className="py-2 text-xs text-muted-foreground">
                                {formatDatetime(c.timestamp)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </section>

                <section className="space-y-3">
                  <h3 className="font-heading text-base font-semibold text-foreground">
                    System Health Summary
                  </h3>
                  <div className="flex gap-6">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-success">
                        {health.healthy}
                      </p>
                      <p className="text-xs text-muted-foreground">Healthy</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-warning">
                        {health.degraded}
                      </p>
                      <p className="text-xs text-muted-foreground">Degraded</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-destructive">
                        {health.unhealthy}
                      </p>
                      <p className="text-xs text-muted-foreground">Unhealthy</p>
                    </div>
                  </div>
                </section>
              </>
            );
          })()}
        </>
      )}
    </PageContainer>
  );
}
