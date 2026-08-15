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
  Clock,
  Trash2,
  Undo2,
} from "lucide-react";
import {
  APPLICATIONS_DASHBOARD_QUERY_KEY,
  applicationsApi,
} from "@/lib/api/applications";
import { coverLetterApi } from "@/lib/api/coverLetter";
import type { ApplicationSummary } from "@/lib/types/api";
import type { PrepSheetResponse } from "@/lib/api/coverLetter";
import { PrepSheetDisplay } from "@/components/prep-sheet-display";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
import {
  canAdvanceToInterview,
  canRevertStatus,
  displayApplicationCompany,
  displayApplicationTitle,
  filterExpiredApplications,
  filterTrackedApplications,
  isInterviewStage,
  MIN_JOB_DESCRIPTION_CHARS,
  safeListingUrl,
} from "@/lib/applications-filters";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { AiWaitProgress } from "@/components/ai-wait-progress";

// ── Application card ──────────────────────────────────────────────────────────

function AppCard({
  app,
  onUnsave,
  onUnhide,
  onUntrack,
  untrackPending,
}: {
  app: ApplicationSummary;
  onUnsave?: () => void;
  onUnhide?: () => void;
  onUntrack?: () => void;
  untrackPending?: boolean;
}) {
  const qc = useQueryClient();
  const [prepOpen, setPrepOpen] = useState(false);
  const [prep, setPrep] = useState<PrepSheetResponse | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rejectConfirmOpen, setRejectConfirmOpen] = useState(false);
  const [pastedDescription, setPastedDescription] = useState("");
  const [needsDescription, setNeedsDescription] = useState(false);

  const status = app.current_status.toLowerCase();
  const statusColor = STATUS_COLORS[status] ?? "bg-muted text-foreground";
  const canRespond = canAdvanceToInterview(status);
  const inInterview = isInterviewStage(status);
  const canRevert = canRevertStatus(status, app.previous_status);
  const title = displayApplicationTitle(app.job_title);
  const company = displayApplicationCompany(app.company);
  const listingHref = safeListingUrl(app.source_url);
  const showDescriptionPaste =
    (canRespond || inInterview) &&
    (app.has_job_description === false || needsDescription);

  const setStatus = useMutation({
    mutationFn: (s: string) =>
      applicationsApi.updateStatus(app.application_id, s),
    onSuccess: (_data, s) => {
      toast.success(
        s === "rejected" ? "Marked as rejected" : "Moved to interview stage",
      );
      qc.invalidateQueries({
        queryKey: ["applications"],
        refetchType: "all",
      });
    },
    onError: () => toast.error("Failed to update status"),
  });

  const revertStatus = useMutation({
    mutationFn: () => applicationsApi.revertStatus(app.application_id),
    onSuccess: (data) => {
      const restored = data.new_status?.replace(/_/g, " ") ?? "previous status";
      toast.success(`Restored to ${restored}`);
      qc.invalidateQueries({
        queryKey: ["applications"],
        refetchType: "all",
      });
    },
    onError: () => toast.error("Failed to revert status"),
  });

  const statusPending = setStatus.isPending || revertStatus.isPending;

  const prepMutation = useMutation({
    mutationFn: async () => {
      const detail = await applicationsApi.getDetail(app.application_id);
      const description = String(detail.metadata?.description ?? "");
      if (description.trim().length < MIN_JOB_DESCRIPTION_CHARS) {
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
    onError: (err: Error) => {
      if (err.message.includes("No saved job description")) {
        setNeedsDescription(true);
      }
      toast.error(err.message || "Failed to generate prep sheet");
    },
  });

  const saveDescription = useMutation({
    mutationFn: (description: string) =>
      applicationsApi.updateStatus(
        app.application_id,
        app.current_status,
        undefined,
        { description },
      ),
    onSuccess: () => {
      toast.success("Job description saved");
      setNeedsDescription(false);
      setPastedDescription("");
      qc.invalidateQueries({
        queryKey: ["applications"],
        refetchType: "all",
      });
    },
    onError: () => toast.error("Failed to save job description"),
  });

  return (
    <Card className="transition-all duration-150 hover:ring-2 hover:ring-ring/50">
      <CardContent className="space-y-3 pt-4 pb-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-medium text-foreground truncate">{title}</p>
              {app.is_bookmarked && (
                <Bookmark className="h-3.5 w-3.5 shrink-0 text-info" />
              )}
            </div>
            <p className="text-sm text-muted-foreground">{company}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <Badge className={cn("text-xs", statusColor)}>
                {app.current_status.replace(/_/g, " ")}
              </Badge>
              {app.listing_status === "expired" && (
                <Badge className="text-xs bg-destructive text-destructive-foreground">
                  Expired
                </Badge>
              )}
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
            {listingHref && (
              <a
                href={listingHref}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open listing
              </a>
            )}
            {canRespond && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setStatus.mutate("screening_scheduled")}
                disabled={statusPending}
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
                disabled={prepMutation.isPending || statusPending}
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
                className="text-xs text-destructive"
                onClick={() => setRejectConfirmOpen(true)}
                disabled={statusPending}
              >
                Rejected
              </Button>
            )}
            {canRevert && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => revertStatus.mutate()}
                disabled={statusPending}
              >
                <Undo2 className="mr-1.5 h-3.5 w-3.5" />
                Revert
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
            {onUntrack && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmOpen(true)}
                disabled={untrackPending}
                className="text-xs text-destructive"
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Remove
              </Button>
            )}
          </div>
        </div>
        {prepMutation.isPending ? (
          <AiWaitProgress
            label="Generating interview prep…"
            hint="The model is drafting questions and talking points."
            size="compact"
          />
        ) : null}
      </CardContent>
      {showDescriptionPaste && (
        <CardContent className="space-y-2 pt-0">
          <Label className="text-sm">Job description</Label>
          <Textarea
            value={pastedDescription}
            onChange={(e) => setPastedDescription(e.target.value)}
            placeholder="Paste the job description to enable interview prep…"
            className="min-h-[100px] resize-y"
          />
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              Required ({MIN_JOB_DESCRIPTION_CHARS}+ characters) to run
              interview prep.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => saveDescription.mutate(pastedDescription.trim())}
              disabled={
                pastedDescription.trim().length < MIN_JOB_DESCRIPTION_CHARS ||
                saveDescription.isPending
              }
            >
              {saveDescription.isPending ? "Saving…" : "Save description"}
            </Button>
          </div>
        </CardContent>
      )}

      <Dialog open={prepOpen} onOpenChange={setPrepOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Interview prep</h3>
              <p className="text-sm text-muted-foreground">
                {title} · {company}
              </p>
            </div>
            {prep && <PrepSheetDisplay prep={prep} />}
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this application?</AlertDialogTitle>
            <AlertDialogDescription>
              This deletes the tracking record for {title} at {company}. It does
              not withdraw an application you already sent.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={untrackPending}
              onClick={() => {
                setConfirmOpen(false);
                onUntrack?.();
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={rejectConfirmOpen} onOpenChange={setRejectConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Mark this application as rejected?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This marks {title} at {company} as rejected. You can revert the
              status later. Remove deletes the tracking record instead.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={statusPending}
              onClick={() => {
                setRejectConfirmOpen(false);
                setStatus.mutate("rejected");
              }}
            >
              Rejected
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

// ── Track external form ────────────────────────────────────────────────────────

function TrackExternalForm({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [method, setMethod] = useState("");
  const [listingUrl, setListingUrl] = useState("");
  const [description, setDescription] = useState("");
  const [atInterview, setAtInterview] = useState(false);

  const reset = () => {
    setTitle("");
    setCompany("");
    setMethod("");
    setListingUrl("");
    setDescription("");
    setAtInterview(false);
  };

  const track = useMutation({
    mutationFn: async () => {
      const jobId = `ext-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      const metadata: Record<string, unknown> = {};
      if (description.trim()) {
        metadata.description = description.trim();
      }
      const cleanedUrl = safeListingUrl(listingUrl);
      if (cleanedUrl) {
        metadata.source_url = cleanedUrl;
      }
      await applicationsApi.trackExternal({
        job_id: jobId,
        job_title: title,
        company,
        application_date: new Date().toISOString(),
        application_method: method || "External site",
        metadata,
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
  const canPrep = description.trim().length >= MIN_JOB_DESCRIPTION_CHARS;
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
          <Label>Listing link</Label>
          <Input
            value={listingUrl}
            onChange={(e) => setListingUrl(e.target.value)}
            placeholder="https://… (optional)"
            inputMode="url"
            autoComplete="url"
          />
          <p className="text-xs text-muted-foreground">
            Optional. Shown as Open listing on the application card.
          </p>
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
    queryKey: APPLICATIONS_DASHBOARD_QUERY_KEY,
    queryFn: () =>
      applicationsApi.getDashboard({
        include_hidden: false,
        include_external: true,
      }),
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
      qc.invalidateQueries({ queryKey: ["applications"], refetchType: "all" });
    },
  });

  const unhide = useMutation({
    mutationFn: (id: string) => applicationsApi.action(id, "unhide"),
    onSuccess: () => {
      toast.success("Job unhidden");
      qc.invalidateQueries({ queryKey: ["applications"], refetchType: "all" });
    },
  });

  const untrack = useMutation({
    mutationFn: (id: string) => applicationsApi.action(id, "untrack"),
    onSuccess: () => {
      toast.success("Application removed");
      qc.invalidateQueries({ queryKey: ["applications"], refetchType: "all" });
    },
    onError: () => toast.error("Failed to remove application"),
  });

  const summary = allQuery.data?.summary;
  const trackedApplications = filterTrackedApplications(
    allQuery.data?.applications ?? [],
  );
  const dashboardError =
    allQuery.error ?? savedQuery.error ?? hiddenQuery.error;

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Applications"
        subtitle="Track and manage your job applications."
      />

      {dashboardError && (
        <QueryErrorBanner
          title="Failed to load applications"
          message={dashboardError.message}
        />
      )}

      {/* Summary tiles */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            { label: "Total", value: trackedApplications.length },
            { label: "Bookmarked", value: summary.bookmarked },
            { label: "Hidden", value: summary.hidden },
            { label: "External", value: summary.external },
            { label: "Expired", value: summary.expired ?? 0 },
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
        onSuccess={() =>
          qc.invalidateQueries({
            queryKey: ["applications"],
            refetchType: "all",
          })
        }
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
          <TabsTrigger value="expired">
            <Clock className="mr-1.5 h-3.5 w-3.5" />
            Expired
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4 space-y-2">
          {allQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {trackedApplications.length === 0 &&
            !allQuery.isLoading &&
            !allQuery.isError && (
              <EmptyState
                title="No applications tracked yet"
                description="Search and apply to jobs, or track an external application above."
                action={{ label: "Browse jobs", href: "/jobs" }}
              />
            )}
          {trackedApplications.map((app) => (
            <AppCard
              key={app.application_id}
              app={app}
              onUntrack={() => untrack.mutate(app.application_id)}
              untrackPending={untrack.isPending}
            />
          ))}
        </TabsContent>

        <TabsContent value="saved" className="mt-4 space-y-2">
          {savedQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {(savedQuery.data?.applications ?? []).filter((a) => a.is_bookmarked)
            .length === 0 &&
            !savedQuery.isLoading &&
            !savedQuery.isError && (
              <EmptyState
                title="No saved jobs yet"
                description="Bookmark listings from the Jobs or Pipeline pages to revisit them here."
                action={{ label: "Browse jobs", href: "/jobs" }}
              />
            )}
          {(savedQuery.data?.applications ?? [])
            .filter((a) => a.is_bookmarked)
            .map((app) => (
              <AppCard
                key={app.application_id}
                app={app}
                onUnsave={() => unsave.mutate(app.application_id)}
                onUntrack={() => untrack.mutate(app.application_id)}
                untrackPending={untrack.isPending}
              />
            ))}
        </TabsContent>

        <TabsContent value="hidden" className="mt-4 space-y-2">
          {hiddenQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {(hiddenQuery.data?.applications ?? []).filter((a) => a.is_hidden)
            .length === 0 &&
            !hiddenQuery.isLoading &&
            !hiddenQuery.isError && (
              <EmptyState
                title="No hidden jobs"
                description="Jobs you hide from the pipeline appear here so you can restore them later."
                action={{ label: "Open pipeline", href: "/pipeline" }}
              />
            )}
          {(hiddenQuery.data?.applications ?? [])
            .filter((a) => a.is_hidden)
            .map((app) => (
              <AppCard
                key={app.application_id}
                app={app}
                onUnhide={() => unhide.mutate(app.application_id)}
                onUntrack={() => untrack.mutate(app.application_id)}
                untrackPending={untrack.isPending}
              />
            ))}
        </TabsContent>

        <TabsContent value="expired" className="mt-4 space-y-2">
          {allQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {filterExpiredApplications(allQuery.data?.applications ?? [])
            .length === 0 &&
            !allQuery.isLoading &&
            !allQuery.isError && (
              <EmptyState
                title="No expired listings"
                description="Saved or applied jobs whose catalog listing has expired appear here. They stay on All with an Expired badge."
                action={{ label: "Browse jobs", href: "/jobs" }}
              />
            )}
          {filterExpiredApplications(allQuery.data?.applications ?? []).map(
            (app) => (
              <AppCard
                key={app.application_id}
                app={app}
                onUntrack={() => untrack.mutate(app.application_id)}
                untrackPending={untrack.isPending}
              />
            ),
          )}
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
