"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy } from "lucide-react";
import { logsApi } from "@/lib/api/logs";
import type { LogLevel, LogRecord } from "@/lib/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { cn } from "@/lib/utils/cn";

const LEVELS: LogLevel[] = ["INFO", "WARNING", "ERROR", "CRITICAL"];
const REFRESH_MS = 3_000;
const SEARCH_DEBOUNCE_MS = 300;

const LEVEL_CLASSES: Record<string, string> = {
  WARNING: "text-warning",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive font-semibold",
};

/**
 * Format one record as a single plain-text line.
 *
 * @param r - Log record.
 * @returns ``time LEVEL logger - message``.
 */
function formatLine(r: LogRecord): string {
  return `${r.timestamp} ${r.level} ${r.logger} - ${r.message}`;
}

/**
 * Read-only viewer for recent API logs held in memory by the backend.
 *
 * Secrets are redacted by the backend before they are stored.
 *
 * @returns The Logs page.
 */
export default function LogsPage() {
  const [level, setLevel] = useState<LogLevel>("INFO");
  const [component, setComponent] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  const logs = useQuery({
    queryKey: ["logs", level, component, search],
    queryFn: ({ signal }) =>
      logsApi.get({ level, component, q: search }, signal),
    refetchInterval: autoRefresh ? REFRESH_MS : false,
  });

  const records = logs.data?.records ?? [];
  const latestSeq = records.at(-1)?.seq;

  useEffect(() => {
    if (autoRefresh && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [latestSeq, autoRefresh]);

  /** Copy the visible records to the clipboard as plain text. */
  const copyVisible = async () => {
    try {
      await navigator.clipboard.writeText(records.map(formatLine).join("\n"));
      toast.success(`Copied ${records.length} lines`);
    } catch {
      toast.error("Clipboard is not available in this browser.");
    }
  };

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Logs"
        subtitle="Recent API logs held in memory. Secrets are redacted. Restarting the backend clears them."
        actions={
          <Button
            size="sm"
            variant="outline"
            onClick={copyVisible}
            disabled={records.length === 0}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            Copy
          </Button>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="log-level">Lowest level</Label>
          <select
            id="log-level"
            value={level}
            onChange={(e) => setLevel(e.target.value as LogLevel)}
            className="rounded-md border border-border bg-card px-3 py-2 text-sm"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="log-component">Component</Label>
          <select
            id="log-component"
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            className="max-w-xs rounded-md border border-border bg-card px-3 py-2 text-sm"
          >
            <option value="">All components</option>
            {(logs.data?.loggers ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[220px] flex-1 space-y-1">
          <Label htmlFor="log-search">Search</Label>
          <Input
            id="log-search"
            placeholder="Text in message or logger"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 pb-2">
          <Switch
            id="log-auto-refresh"
            checked={autoRefresh}
            onCheckedChange={setAutoRefresh}
          />
          <Label htmlFor="log-auto-refresh">Auto-refresh</Label>
        </div>
      </div>

      {logs.isError && (
        <QueryErrorBanner
          title="Could not load logs"
          message={
            logs.error instanceof Error ? logs.error.message : "Unknown error"
          }
        />
      )}

      {logs.data && records.length === 0 ? (
        <EmptyState
          title="No matching log records"
          description="Change the filters, or wait for the API to log something."
        />
      ) : (
        <div
          ref={listRef}
          role="log"
          aria-label="Log records"
          className="h-[60vh] overflow-y-auto rounded-lg border bg-card p-3 font-mono text-xs"
        >
          {records.map((r) => (
            <div key={r.seq} className="flex gap-2 whitespace-pre-wrap">
              <span className="shrink-0 text-muted-foreground">
                {new Date(r.timestamp).toLocaleTimeString()}
              </span>
              <span
                className={cn(
                  "w-16 shrink-0",
                  LEVEL_CLASSES[r.level] ?? "text-muted-foreground",
                )}
              >
                {r.level}
              </span>
              <span className="shrink-0 text-info">{r.logger}</span>
              <span className="text-foreground">{r.message}</span>
            </div>
          ))}
        </div>
      )}

      {logs.data && (
        <p className="text-xs text-muted-foreground">
          Showing {records.length} records. The backend keeps the last{" "}
          {logs.data.capacity}.
        </p>
      )}
    </PageContainer>
  );
}
