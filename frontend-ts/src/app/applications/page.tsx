"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bookmark, EyeOff, ExternalLink, Plus } from "lucide-react";
import { applicationsApi } from "@/lib/api/applications";
import type { ApplicationSummary } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils/format";
import { STATUS_COLORS } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";

// ── Application card ──────────────────────────────────────────────────────────

function AppCard({
  app,
  onUnsave,
  onUnhide,
}: {
  app: ApplicationSummary;
  onUnsave?: () => void;
  onUnhide?: () => void;
}) {
  const statusColor = STATUS_COLORS[app.current_status.toLowerCase()] ?? "bg-gray-100 text-gray-700";

  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4 pt-4 pb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-gray-900 truncate">{app.job_title}</p>
            {app.is_bookmarked && <Bookmark className="h-3.5 w-3.5 shrink-0 text-blue-500" />}
          </div>
          <p className="text-sm text-gray-500">{app.company}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <Badge className={cn("text-xs", statusColor)}>
              {app.current_status.replace(/_/g, " ")}
            </Badge>
            {app.applied_date && (
              <span className="text-xs text-gray-400">{formatDate(app.applied_date)}</span>
            )}
            {app.days_since_application != null && (
              <span className="text-xs text-gray-400">{app.days_since_application}d ago</span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {app.source_url && (
            <a href={app.source_url} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-blue-600">
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
          {onUnsave && (
            <Button size="sm" variant="ghost" onClick={onUnsave} className="text-xs text-gray-500">
              Unsave
            </Button>
          )}
          {onUnhide && (
            <Button size="sm" variant="ghost" onClick={onUnhide} className="text-xs text-gray-500">
              Unhide
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Track external form ────────────────────────────────────────────────────────

function TrackExternalForm({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen] = useState(false);
  const [jobId, setJobId] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [method, setMethod] = useState("");

  const track = useMutation({
    mutationFn: () =>
      applicationsApi.trackExternal({
        job_id: jobId || `ext-${Date.now()}`,
        job_title: title,
        company,
        application_method: method || undefined,
      }),
    onSuccess: () => {
      toast.success("External application tracked.");
      setOpen(false);
      onSuccess();
    },
    onError: () => toast.error("Failed to track application."),
  });

  if (!open) {
    return (
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Plus className="mr-1.5 h-4 w-4" />
        Track External Application
      </Button>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Track External Application</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Job Title *</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Software Engineer" />
          </div>
          <div className="space-y-1">
            <Label>Company *</Label>
            <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Corp" />
          </div>
        </div>
        <div className="space-y-1">
          <Label>How did you apply?</Label>
          <Input value={method} onChange={(e) => setMethod(e.target.value)} placeholder="Company website, referral…" />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => track.mutate()}
            disabled={!title || !company || track.isPending}
          >
            {track.isPending ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ApplicationsPage() {
  const qc = useQueryClient();

  const allQuery = useQuery({
    queryKey: ["applications", "all"],
    queryFn: () => applicationsApi.getDashboard({ include_hidden: false }),
    staleTime: 30_000,
  });

  const savedQuery = useQuery({
    queryKey: ["applications", "saved"],
    queryFn: () => applicationsApi.getDashboard({ include_bookmarked: true }),
    staleTime: 30_000,
  });

  const hiddenQuery = useQuery({
    queryKey: ["applications", "hidden"],
    queryFn: () => applicationsApi.getDashboard({ include_hidden: true }),
    staleTime: 30_000,
  });

  const unsave = useMutation({
    mutationFn: (id: string) => applicationsApi.action(id, "unsave"),
    onSuccess: () => {
      toast.success("Removed from saved");
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });

  const unhide = useMutation({
    mutationFn: (id: string) => applicationsApi.action(id, "unhide"),
    onSuccess: () => {
      toast.success("Job unhidden");
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });

  const summary = allQuery.data?.summary;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
        <p className="mt-1 text-sm text-gray-500">Track and manage your job applications.</p>
      </div>

      {/* Summary tiles */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Total", value: summary.total_applications },
            { label: "Bookmarked", value: summary.bookmarked },
            { label: "Hidden", value: summary.hidden },
            { label: "External", value: summary.external },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg border bg-white p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{value}</p>
              <p className="text-xs text-gray-500">{label}</p>
            </div>
          ))}
        </div>
      )}

      <TrackExternalForm onSuccess={() => qc.invalidateQueries({ queryKey: ["applications"] })} />

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All Applications</TabsTrigger>
          <TabsTrigger value="saved">
            <Bookmark className="mr-1.5 h-3.5 w-3.5" />
            Saved
          </TabsTrigger>
          <TabsTrigger value="hidden">
            <EyeOff className="mr-1.5 h-3.5 w-3.5" />
            Hidden
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4 space-y-2">
          {allQuery.isLoading && <p className="text-sm text-gray-400">Loading…</p>}
          {(allQuery.data?.applications ?? []).length === 0 && !allQuery.isLoading && (
            <p className="text-sm text-gray-400">No applications tracked yet.</p>
          )}
          {(allQuery.data?.applications ?? []).map((app) => (
            <AppCard key={app.application_id} app={app} />
          ))}
        </TabsContent>

        <TabsContent value="saved" className="mt-4 space-y-2">
          {savedQuery.isLoading && <p className="text-sm text-gray-400">Loading…</p>}
          {(savedQuery.data?.applications ?? []).filter((a) => a.is_bookmarked).length === 0 && !savedQuery.isLoading && (
            <p className="text-sm text-gray-400">No saved jobs yet.</p>
          )}
          {(savedQuery.data?.applications ?? [])
            .filter((a) => a.is_bookmarked)
            .map((app) => (
              <AppCard
                key={app.application_id}
                app={app}
                onUnsave={() => unsave.mutate(app.application_id)}
              />
            ))}
        </TabsContent>

        <TabsContent value="hidden" className="mt-4 space-y-2">
          {hiddenQuery.isLoading && <p className="text-sm text-gray-400">Loading…</p>}
          {(hiddenQuery.data?.applications ?? []).filter((a) => a.is_hidden).length === 0 && !hiddenQuery.isLoading && (
            <p className="text-sm text-gray-400">No hidden jobs.</p>
          )}
          {(hiddenQuery.data?.applications ?? [])
            .filter((a) => a.is_hidden)
            .map((app) => (
              <AppCard
                key={app.application_id}
                app={app}
                onUnhide={() => unhide.mutate(app.application_id)}
              />
            ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
