"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bookmark,
  EyeOff,
  ExternalLink,
  Plus,
  CalendarCheck,
  Sparkles,
  Loader2,
} from "lucide-react";
import { applicationsApi } from "@/lib/api/applications";
import { coverLetterApi } from "@/lib/api/coverLetter";
import type { ApplicationSummary } from "@/lib/types/api";
import type { PrepSheetResponse } from "@/lib/api/coverLetter";
import { PrepSheetDisplay } from "@/components/prep-sheet-display";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDate } from "@/lib/utils/format";
import { STATUS_COLORS } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";
import { PageContainer } from "@/components/layout/PageContainer";

// ── Application card ──────────────────────────────────────────────────────────

// Statuses that mean the company has come back and interview prep is relevant.
const INTERVIEW_STATUSES = new Set([
  "under_review",
  "screening_scheduled",
  "screening_completed",
  "technical_scheduled",
  "technical_completed",
  "onsite_scheduled",
  "onsite_completed",
  "final",
]);

function AppCard({
  app,
  onUnsave,
  onUnhide,
}: {
  app: ApplicationSummary;
  onUnsave?: () => void;
  onUnhide?: () => void;
}) {
  const qc = useQueryClient();
  const [prepOpen, setPrepOpen] = useState(false);
  const [prep, setPrep] = useState<PrepSheetResponse | null>(null);

  const status = app.current_status.toLowerCase();
  const statusColor = STATUS_COLORS[status] ?? "bg-muted text-foreground";
  const canRespond = status === "applied";
  const inInterview = INTERVIEW_STATUSES.has(status);

  const setStatus = useMutation({
    mutationFn: (s: string) =>
      applicationsApi.updateStatus(app.application_id, s),
    onSuccess: (_data, s) => {
      toast.success(
        s === "rejected" ? "Marked as rejected" : "Moved to interview stage",
      );
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: () => toast.error("Failed to update status"),
  });

  const prepMutation = useMutation({
    mutationFn: async () => {
      const detail = await applicationsApi.getDetail(app.application_id);
      const description = String(detail.metadata?.description ?? "");
      if (description.trim().length < 50) {
        throw new Error("No saved job description for this listing");
      }
      return coverLetterApi.prep({
        title: app.job_title,
        company: app.company,
        description,
      });
    },
    onSuccess: (data) => {
      setPrep(data);
      setPrepOpen(true);
    },
    onError: (err: Error) =>
      toast.error(err.message || "Failed to generate prep sheet"),
  });

  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4 pt-4 pb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-foreground truncate">
              {app.job_title}
            </p>
            {app.is_bookmarked && (
              <Bookmark className="h-3.5 w-3.5 shrink-0 text-blue-500" />
            )}
          </div>
          <p className="text-sm text-muted-foreground">{app.company}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <Badge className={cn("text-xs", statusColor)}>
              {app.current_status.replace(/_/g, " ")}
            </Badge>
            {app.applied_date && (
              <span className="text-xs text-muted-foreground">
                {formatDate(app.applied_date)}
              </span>
            )}
            {app.days_since_application != null && (
              <span className="text-xs text-muted-foreground">
                {app.days_since_application}d ago
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          {app.source_url && (
            <a
              href={app.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground hover:text-blue-600"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
          {canRespond && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setStatus.mutate("screening_scheduled")}
              disabled={setStatus.isPending}
            >
              <CalendarCheck className="mr-1.5 h-3.5 w-3.5" />
              Proceed to interview
            </Button>
          )}
          {inInterview && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => prepMutation.mutate()}
              disabled={prepMutation.isPending}
            >
              {prepMutation.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              )}
              Prep for interview
            </Button>
          )}
          {(canRespond || inInterview) && (
            <Button
              size="sm"
              variant="ghost"
              className="text-xs text-red-500"
              onClick={() => setStatus.mutate("rejected")}
              disabled={setStatus.isPending}
            >
              Rejected
            </Button>
          )}
          {onUnsave && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onUnsave}
              className="text-xs text-muted-foreground"
            >
              Unsave
            </Button>
          )}
          {onUnhide && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onUnhide}
              className="text-xs text-muted-foreground"
            >
              Unhide
            </Button>
          )}
        </div>
      </CardContent>

      <Dialog open={prepOpen} onOpenChange={setPrepOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Interview prep</h3>
              <p className="text-sm text-muted-foreground">
                {app.job_title} · {app.company}
              </p>
            </div>
            {prep && <PrepSheetDisplay prep={prep} />}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ── Track external form ────────────────────────────────────────────────────────

function TrackExternalForm({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [method, setMethod] = useState("");
  const [description, setDescription] = useState("");
  const [atInterview, setAtInterview] = useState(false);

  const reset = () => {
    setTitle("");
    setCompany("");
    setMethod("");
    setDescription("");
    setAtInterview(false);
  };

  const track = useMutation({
    mutationFn: async () => {
      const jobId = `ext-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      await applicationsApi.trackExternal({
        job_id: jobId,
        job_title: title,
        company,
        application_date: new Date().toISOString(),
        application_method: method || "External site",
        metadata: description.trim() ? { description: description.trim() } : {},
      });
      // If they already have an interview invite, jump straight to that stage
      // so "Prep for interview" is immediately available on the card.
      if (atInterview) {
        await applicationsApi.updateStatus(jobId, "screening_scheduled");
      }
    },
    onSuccess: () => {
      toast.success("External application tracked.");
      setOpen(false);
      reset();
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

  // A saved job description is required before an external listing can enter the
  // interview-prep flow, so gate the toggle on having enough text.
  const canPrep = description.trim().length >= 50;
  const blockedByPrep = atInterview && !canPrep;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Track External Application</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Job Title *</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Software Engineer"
            />
          </div>
          <div className="space-y-1">
            <Label>Company *</Label>
            <Input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Acme Corp"
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label>How did you apply?</Label>
          <Input
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            placeholder="Company website, referral…"
          />
        </div>
        <div className="space-y-1">
          <Label>Job description</Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Paste the job description to enable interview prep for this listing…"
            className="min-h-[120px] resize-y"
          />
          <p className="text-xs text-muted-foreground">
            Optional, but required (50+ characters) to run interview prep later.
          </p>
        </div>
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">
              I already have an interview invite
            </Label>
            <p className="text-xs text-muted-foreground">
              Marks this as an interview stage so you can prep right away.
            </p>
          </div>
          <Switch checked={atInterview} onCheckedChange={setAtInterview} />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => track.mutate()}
            disabled={!title || !company || blockedByPrep || track.isPending}
          >
            {track.isPending ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
        {blockedByPrep && (
          <p className="text-xs text-amber-600">
            Add a job description (50+ characters) to track this as an interview
            stage.
          </p>
        )}
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
    <PageContainer variant="full-bleed">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Applications</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Track and manage your job applications.
        </p>
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
            <div
              key={label}
              className="rounded-lg border bg-card p-4 text-center"
            >
              <p className="text-2xl font-bold text-foreground">{value}</p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      )}

      <TrackExternalForm
        onSuccess={() => qc.invalidateQueries({ queryKey: ["applications"] })}
      />

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
          {allQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {(allQuery.data?.applications ?? []).length === 0 &&
            !allQuery.isLoading && (
              <p className="text-sm text-muted-foreground">
                No applications tracked yet.
              </p>
            )}
          {(allQuery.data?.applications ?? []).map((app) => (
            <AppCard key={app.application_id} app={app} />
          ))}
        </TabsContent>

        <TabsContent value="saved" className="mt-4 space-y-2">
          {savedQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {(savedQuery.data?.applications ?? []).filter((a) => a.is_bookmarked)
            .length === 0 &&
            !savedQuery.isLoading && (
              <p className="text-sm text-muted-foreground">
                No saved jobs yet.
              </p>
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
          {hiddenQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {(hiddenQuery.data?.applications ?? []).filter((a) => a.is_hidden)
            .length === 0 &&
            !hiddenQuery.isLoading && (
              <p className="text-sm text-muted-foreground">No hidden jobs.</p>
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
    </PageContainer>
  );
}
