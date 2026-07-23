"use client";

import { CheckCircle, AlertTriangle, Lightbulb } from "lucide-react";
import type { ScoreExplanation } from "@/lib/api/coverLetter";

interface ScoreExplanationDisplayProps {
  explanation: ScoreExplanation;
}

/**
 * Render a plain-language score explanation as grouped strengths, concerns,
 * and improvement bullets. Shared by the job-fit and cover-letter panels.
 *
 * @param explanation - Strengths, concerns, improvements, and optional score.
 * @returns Explanation panel, or null when all lists are empty.
 */
export function ScoreExplanationDisplay({
  explanation,
}: ScoreExplanationDisplayProps) {
  const sections = [
    {
      label: "Strengths",
      items: explanation.strengths,
      color: "text-emerald-600",
      Icon: CheckCircle,
    },
    {
      label: "Concerns",
      items: explanation.concerns,
      color: "text-amber-600",
      Icon: AlertTriangle,
    },
    {
      label: "How to improve",
      items: explanation.improvements,
      color: "text-primary",
      Icon: Lightbulb,
    },
  ];
  const hasAny = sections.some((s) => s.items.length > 0);
  if (!hasAny) return null;
  return (
    <div className="rounded-lg border p-3 space-y-2">
      {explanation.fit_score != null && (
        <p className="text-xs text-muted-foreground">
          Explained score:{" "}
          <span className="font-semibold text-foreground">
            {explanation.fit_score}/100
          </span>
        </p>
      )}
      {sections.map(({ label, items, color, Icon }) =>
        items.length > 0 ? (
          <div key={label} className="space-y-1">
            <p
              className={`text-xs font-semibold flex items-center gap-1.5 ${color}`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </p>
            <ul className="list-disc pl-5 space-y-0.5 text-xs text-muted-foreground">
              {items.map((item, index) => (
                <li key={`${label}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </div>
  );
}
