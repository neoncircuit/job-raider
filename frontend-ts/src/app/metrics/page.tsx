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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatPercentage, formatDatetime } from "@/lib/utils/format";

const PIE_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"];

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

export default function MetricsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: metricsApi.getSummary,
    staleTime: 60_000,
  });

  if (isLoading) return <p className="text-sm text-gray-400 p-4">Loading metrics…</p>;
  if (isError || !data) return <p className="text-sm text-red-500 p-4">Failed to load metrics.</p>;

  const { cost, outcomes, health } = data;
  const recent_calls = data.recent_calls ?? [];

  const funnelData = [
    { name: "Applied", count: outcomes.total_applications },
    { name: "Interviewed", count: outcomes.interviews },
    { name: "Offered", count: outcomes.offers },
  ];

  const localCount = Math.round((cost.local_usage_percent / 100) * cost.total_calls);
  const apiCount = cost.total_calls - localCount;
  const costPieData = [
    { name: "Local (Ollama)", value: localCount },
    { name: "API (Claude)", value: apiCount },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Metrics</h1>
        <p className="mt-1 text-sm text-gray-500">Cost tracking, outcome funnel, and system health.</p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-gray-700 uppercase tracking-wide">Cost</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Total Spent" value={formatCurrency(cost.total_usd)} />
          <Tile label="Per Application" value={formatCurrency(cost.per_application)} />
          <Tile label="Total LLM Calls" value={cost.total_calls.toLocaleString()} />
          <Tile label="Local Usage" value={formatPercentage(cost.local_usage_percent)} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-gray-700 uppercase tracking-wide">Outcomes</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Applications" value={outcomes.total_applications} />
          <Tile label="Interviews" value={outcomes.interviews} />
          <Tile label="Offers" value={outcomes.offers} />
          <Tile label="Interview Rate" value={formatPercentage(outcomes.interview_rate * 100)} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Application Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={funnelData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => [v, "Count"]} />
                <Bar dataKey="count" fill="#3B82F6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">LLM Call Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
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
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent LLM Calls</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {recent_calls.length === 0 ? (
            <p className="text-sm text-gray-400">No calls recorded yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500">
                  <th className="pb-2 pr-4">Task</th>
                  <th className="pb-2 pr-4">Provider</th>
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2 pr-4">Cost</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {recent_calls.map((c, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-2 pr-4 text-gray-700">{c.task_type}</td>
                    <td className="py-2 pr-4 text-gray-500 capitalize">{c.provider}</td>
                    <td className="py-2 pr-4 text-gray-500">{c.model}</td>
                    <td className="py-2 pr-4 text-gray-700">{formatCurrency(c.cost_usd)}</td>
                    <td className="py-2 text-gray-400 text-xs">{formatDatetime(c.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">System Health Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{health.healthy}</p>
              <p className="text-xs text-gray-500">Healthy</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-600">{health.degraded}</p>
              <p className="text-xs text-gray-500">Degraded</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600">{health.unhealthy}</p>
              <p className="text-xs text-gray-500">Unhealthy</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
