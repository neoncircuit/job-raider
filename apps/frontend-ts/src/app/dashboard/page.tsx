"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Activity,
  Send,
  DollarSign,
  TrendingUp,
  Percent,
  Rocket,
} from "lucide-react";
import { healthApi } from "@/lib/api/health";
import { metricsApi } from "@/lib/api/metrics";
import { pipelineApi } from "@/lib/api/pipeline";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { formatCurrency, formatDatetime } from "@/lib/utils/format";
import { STATUS_COLORS } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { BrandMark } from "@/components/layout/BrandMark";
import { useIsClient } from "@/lib/hooks/use-is-client";
import { Separator } from "@/components/ui/separator";

/**
 * Icon for a health check status string.
 *
 * @param status - Backend health status value.
 */
function HealthIcon({ status }: { status: string }) {
  if (status === "healthy")
    return <CheckCircle2 className="h-4 w-4 text-success" />;
  if (status === "degraded")
    return <AlertTriangle className="h-4 w-4 text-warning" />;
  if (status === "unhealthy")
    return <XCircle className="h-4 w-4 text-destructive" />;
  return <Activity className="h-4 w-4 text-muted-foreground" />;
}

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
}

/**
 * Compact metric tile for secondary dashboard stats.
 *
 * @param title - Metric label.
 * @param value - Primary display value.
 * @param sub - Optional supporting line.
 * @param icon - Leading icon.
 */
function StatCard({ title, value, sub, icon }: StatCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded border border-border bg-card p-4 font-mono text-foreground transition-colors duration-150",
        "hover:border-primary/30",
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </p>
          <p className="mt-1.5 text-xl font-bold tracking-tight text-foreground">
            {value}
          </p>
          {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
        </div>
        <div className="flex h-7 w-7 items-center justify-center rounded border border-border bg-muted/40 text-muted-foreground">
          {icon}
        </div>
      </div>
    </div>
  );
}

/**
 * Ops overview: primary pipeline CTA, compact health, then secondary metrics.
 */
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

  const overallStatus =
    ready && h?.status
      ? h.status
      : ready && health.isError
        ? "unreachable"
        : "…";

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        icon={<BrandMark size={36} />}
        title="Dashboard"
        subtitle="Automated job application pipeline — scrape, score, and apply."
        actions={
          <Link
            href="/pipeline"
            className={cn(
              buttonVariants({ size: "lg" }),
              "font-heading gap-1.5",
            )}
          >
            <Rocket className="h-4 w-4" />
            Run pipeline
          </Link>
        }
      />

      {ready && metrics.isError && (
        <QueryErrorBanner
          title="Metrics unavailable"
          message={metrics.error.message}
        />
      )}

      {/* Compact health strip */}
      <section className="rounded border border-border bg-card/80 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-heading text-sm font-semibold text-foreground">
              System health
            </h2>
            <Badge
              variant="outline"
              className={cn(
                "capitalize text-xs",
                overallStatus === "healthy" && "border-success/40 text-success",
                overallStatus === "degraded" &&
                  "border-warning/40 text-warning",
                (overallStatus === "unhealthy" ||
                  overallStatus === "unreachable") &&
                  "border-destructive/40 text-destructive",
              )}
            >
              {overallStatus}
            </Badge>
          </div>
          {ready && health.isError && (
            <p className="text-xs text-destructive">Backend unreachable</p>
          )}
        </div>
        {ready && (health.isLoading || health.isPending) && (
          <p className="mt-2 text-sm text-muted-foreground">Checking…</p>
        )}
        {ready && h?.checks && h.checks.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
            {h.checks.map((c) => (
              <div key={c.name} className="flex max-w-xs items-center gap-2">
                <HealthIcon status={c.status} />
                <span className="text-xs font-medium capitalize text-foreground">
                  {c.name.replace(/_/g, " ")}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {c.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Secondary stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 stagger-in">
        <StatCard
          title="Applications"
          value={ready && m ? m.outcomes.total_applications : "—"}
          sub={`${
            ready && m ? (m.outcomes.screening_rate * 100).toFixed(1) : "—"
          }% screening rate`}
          icon={<Send className="h-4 w-4" />}
        />
        <StatCard
          title="API Cost"
          value={ready && m ? formatCurrency(m.cost.total_usd) : "—"}
          sub={
            ready && m
              ? `${formatCurrency(m.cost.per_application)} / app`
              : undefined
          }
          icon={<DollarSign className="h-4 w-4" />}
        />
        <StatCard
          title="Local Usage"
          value={ready && m ? `${m.cost.local_usage_percent.toFixed(0)}%` : "—"}
          sub="Ollama vs API calls"
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <StatCard
          title="Offer Rate"
          value={
            ready && m ? `${(m.outcomes.offer_rate * 100).toFixed(1)}%` : "—"
          }
          sub={
            ready && m
              ? `${(m.outcomes.acceptance_rate * 100).toFixed(1)}% acceptance`
              : "Received so far"
          }
          icon={<Percent className="h-4 w-4" />}
        />
      </div>

      <Separator />

      {/* Recent runs — open section, not a card chrome */}
      <section className="space-y-3">
        <h2 className="font-heading text-sm font-semibold text-foreground">
          Recent pipeline runs
        </h2>
        {ready && (history.isLoading || history.isPending) && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {ready && history.isError && (
          <QueryErrorBanner message="Could not load history" />
        )}
        {ready && history.data?.runs.length === 0 && (
          <EmptyState
            className="py-8"
            title="No runs yet"
            description="Start a pipeline to begin scraping and scoring jobs."
            action={{ label: "Go to Pipeline", href: "/pipeline" }}
          />
        )}
        {ready &&
          history.data?.runs.map((r) => (
            <div
              key={r.run_id}
              className="flex items-center justify-between border-b border-border/50 py-2 last:border-0"
            >
              <div>
                <p className="text-sm font-medium text-foreground">
                  {r.jobs_scraped ?? 0} scraped · {r.jobs_applied ?? 0} applied
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDatetime(r.created_at)}
                </p>
              </div>
              <Badge
                className={cn(
                  "text-xs font-medium",
                  STATUS_COLORS[r.status] ?? "bg-muted text-muted-foreground",
                )}
              >
                {r.status}
              </Badge>
            </div>
          ))}
      </section>
    </PageContainer>
  );
}
