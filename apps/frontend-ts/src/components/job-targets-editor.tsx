"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Target } from "lucide-react";
import { profileApi } from "@/lib/api/profile";
import type { ExperienceLevel, TargetJob } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils/cn";

const EXPERIENCE_OPTIONS: ExperienceLevel[] = [
  "Entry Level",
  "Mid Level",
  "Senior",
  "Lead",
  "Principal",
  "Executive",
  "Internship",
  "Not Specified",
];

interface JobTargetsEditorProps {
  /** Current target_job from the active profile (may be partial). */
  targetJob?: TargetJob | null;
}

/**
 * Experimental editor for job-hunt preferences stored on the profile.
 *
 * Pipeline/Jobs only apply these when the user opts in via
 * "Use profile targets". Safe to remove as a self-contained component.
 *
 * @param targetJob - Existing targets to edit.
 * @returns Preference form card.
 */
export function JobTargetsEditor({ targetJob }: JobTargetsEditorProps) {
  const queryClient = useQueryClient();
  const [keywords, setKeywords] = useState(
    (targetJob?.keywords ?? []).join(", "),
  );
  const [locations, setLocations] = useState(
    (targetJob?.locations ?? []).join(", "),
  );
  const [levels, setLevels] = useState<ExperienceLevel[]>(
    targetJob?.experience_levels ?? [],
  );
  const [remote, setRemote] = useState(targetJob?.remote_preference ?? false);
  const [excludeInternships, setExcludeInternships] = useState(
    targetJob?.exclude_internships ?? false,
  );
  const [constraintMode, setConstraintMode] = useState<"boost" | "filter">(
    targetJob?.constraint_mode === "filter" ? "filter" : "boost",
  );

  const save = useMutation({
    mutationFn: () =>
      profileApi.update({
        target_keywords: splitList(keywords),
        target_locations: splitList(locations),
        target_experience: levels,
        remote_preference: remote,
        constraint_mode: constraintMode,
        exclude_internships: excludeInternships,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.success("Job targets saved");
    },
    onError: () => toast.error("Failed to save job targets"),
  });

  const toggleLevel = (level: ExperienceLevel) => {
    setLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level],
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Target className="h-4 w-4 text-muted-foreground" />
          Job Targets
        </CardTitle>
        <p className="text-xs text-muted-foreground font-normal">
          Optional hunt helper. Pipeline and Jobs apply these only when you
          enable &quot;Use profile targets&quot; on those pages.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1.5">
          <Label htmlFor="target-keywords">Keywords</Label>
          <Input
            id="target-keywords"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="AI Engineer, Machine Learning, LLM"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="target-locations">Locations</Label>
          <Input
            id="target-locations"
            value={locations}
            onChange={(e) => setLocations(e.target.value)}
            placeholder="Singapore, Remote"
          />
        </div>

        <div className="space-y-2">
          <Label>Experience levels</Label>
          <div className="flex flex-wrap gap-2">
            {EXPERIENCE_OPTIONS.map((level) => {
              const selected = levels.includes(level);
              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => toggleLevel(level)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs transition-colors",
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground hover:bg-muted",
                  )}
                >
                  {level}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="exclude-internships"
              checked={excludeInternships}
              onCheckedChange={setExcludeInternships}
            />
            <Label htmlFor="exclude-internships">Exclude internships</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="remote-preference"
              checked={remote}
              onCheckedChange={setRemote}
            />
            <Label htmlFor="remote-preference">Prefer remote</Label>
          </div>
        </div>

        <div className="space-y-2">
          <Label>Constraint mode</Label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setConstraintMode("boost")}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs",
                constraintMode === "boost"
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              Boost (soft)
            </button>
            <button
              type="button"
              onClick={() => setConstraintMode("filter")}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs",
                constraintMode === "filter"
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              Filter (hard)
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            Filter drops non-matching experience levels. Boost keeps soft
            scoring; exclude-internships still applies when enabled.
          </p>
        </div>

        <Button
          type="button"
          size="sm"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save job targets"}
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Split a comma/whitespace-separated string into trimmed non-empty tokens.
 *
 * @param value - Raw input string.
 * @returns Token list.
 */
function splitList(value: string): string[] {
  return value
    .split(/[,]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}
