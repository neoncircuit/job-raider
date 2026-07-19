"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Activity,
  Send,
  DollarSign,
  TrendingUp,
  Briefcase,
} from "lucide-react";
import { healthApi } from "@/lib/api/health";
import { metricsApi } from "@/lib/api/metrics";
import { pipelineApi } from "@/lib/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDatetime } from "@/lib/utils/format";
import { STATUS_COLORS } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";
import { PageContainer } from "@/components/layout/PageContainer";
import { useIsClient } from "@/lib/hooks/use-is-client";

function HealthIcon({ status }: { status: string }) {
  if (status === "healthy")
    return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (status === "degraded")
    return <AlertTriangle className="h-4 w-4 text-amber-500" />;
  if (status === "unhealthy")
    return <XCircle className="h-4 w-4 text-red-500" />;
  return <Activity className="h-4 w-4 text-muted-foreground" />;
}

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  iconBg: string;
}

function StatCard({ title, value, sub, icon, iconBg }: StatCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded border p-5 text-foreground shadow-sm transition-all duration-150 font-mono",
        "bg-card hover:shadow-md hover:border-primary/30",
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {title}
          </p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">
            {value}
          </p>
          {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
        </div>
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded border bg-card shadow-sm",
            iconBg,
          )}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const isClient = useIsClient();

  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.getHealth,
    staleTime: 15_000,
    refetchInterval: 30_000,
    enabled: isClient,
  });

  const metrics = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: metricsApi.getSummary,
    staleTime: 30_000,
    enabled: isClient,
  });

  const history = useQuery({
    queryKey: ["pipeline-history"],
    queryFn: () => pipelineApi.getHistory(5),
    staleTime: 30_000,
    enabled: isClient,
  });

  const m = metrics.data;
  const h = health.data;

  // All data-dependent UI is gated behind isClient so the server render and the
  // hydration render match. Without this, cached TanStack Query data from a
  // previous client visit can render rows on the client while the server still
  // shows placeholders, triggering a React hydration mismatch.
  const ready = isClient;

  return (
    <PageContainer variant="full-bleed">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Overview of your job application pipeline.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 stagger-in">
        <StatCard
          title="Applications"
          value={ready && m ? m.outcomes.total_applications : "—"}
          sub={`${ready && m ? (m.outcomes.interview_rate * 100).toFixed(1) : "—"}% interview rate`}
          icon={<Send className="h-5 w-5 text-white" />}
          iconBg="bg-card/15"
        />
        <StatCard
          title="API Cost"
          value={ready && m ? formatCurrency(m.cost.total_usd) : "—"}
          sub={
            ready && m
              ? `${formatCurrency(m.cost.per_application)} / app`
              : undefined
          }
          icon={<DollarSign className="h-5 w-5 text-white" />}
          iconBg="bg-card/15"
        />
        <StatCard
          title="Local Usage"
          value={ready && m ? `${m.cost.local_usage_percent.toFixed(0)}%` : "—"}
          sub="Ollama vs API calls"
          icon={<TrendingUp className="h-5 w-5 text-white" />}
          iconBg="bg-card/15"
        />
        <StatCard
          title="Offers"
          value={ready && m ? m.outcomes.offers : "—"}
          sub="Received so far"
          icon={<Briefcase className="h-5 w-5 text-white" />}
          iconBg="bg-card/15"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* System health */}
        <Card className="shadow-sm border-border/60 backdrop-blur-sm bg-card/50">
          <CardHeader className="pb-3 card-corner-accent">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Activity className="h-4 w-4 text-muted-foreground" />
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {ready && (health.isLoading || health.isPending) && (
              <p className="text-sm text-muted-foreground">Checking…</p>
            )}
            {ready && health.isError && (
              <p className="text-sm text-red-500">Backend unreachable</p>
            )}
            {ready &&
              h?.checks?.map((c) => (
                <div
                  key={c.name}
                  className="flex items-center justify-between py-1 border-b border-border/50 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <HealthIcon status={c.status} />
                    <span className="text-sm font-medium text-foreground capitalize">
                      {c.name.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground truncate max-w-[180px] md:max-w-[240px] lg:max-w-xs">
                    {c.message}
                  </span>
                </div>
              ))}
          </CardContent>
        </Card>

        {/* Recent runs */}
        <Card className="shadow-sm border-border/60 backdrop-blur-sm bg-card/50">
          <CardHeader className="pb-3 card-corner-accent">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Activity className="h-4 w-4 text-muted-foreground" />
              Recent Pipeline Runs
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {ready && (history.isLoading || history.isPending) && (
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
            {ready && history.isError && (
              <p className="text-sm text-red-500">Could not load history</p>
            )}
            {ready && history.data?.runs.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No runs yet. Start a pipeline to begin.
              </p>
            )}
            {ready &&
              history.data?.runs.map((r) => (
                <div
                  key={r.run_id}
                  className="flex items-center justify-between py-1 border-b border-border/50 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {r.jobs_scraped ?? 0} scraped · {r.jobs_applied ?? 0}{" "}
                      applied
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDatetime(r.created_at)}
                    </p>
                  </div>
                  <Badge
                    className={cn(
                      "text-xs font-medium",
                      STATUS_COLORS[r.status] ??
                        "bg-muted text-muted-foreground",
                    )}
                  >
                    {r.status}
                  </Badge>
                </div>
              ))}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
