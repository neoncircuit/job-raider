"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { TrustTier, TrustAnalysis } from "@/lib/types/api";
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  FileText,
  Building2,
  DollarSign,
  MessageSquare,
  User,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useState } from "react";

interface TrustAnalysisDisplayProps {
  analysis: TrustAnalysis;
}

const TIER_CONFIG: Record<
  TrustTier,
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    icon: typeof Shield;
  }
> = {
  legitimate: {
    label: "Legitimate",
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    icon: ShieldCheck,
  },
  low_risk: {
    label: "Low Risk",
    color: "text-info",
    bg: "bg-info/10",
    border: "border-info/30",
    icon: Shield,
  },
  moderate_risk: {
    label: "Moderate Risk",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
  },
  suspicious: {
    label: "Suspicious",
    color: "text-orange-700",
    bg: "bg-orange-50",
    border: "border-orange-200",
    icon: ShieldAlert,
  },
  likely_scam: {
    label: "Likely Scam",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    icon: ShieldX,
  },
};

const CATEGORY_CONFIG = [
  { key: "title", label: "Title", icon: FileText },
  { key: "description", label: "Description", icon: FileText },
  { key: "company", label: "Company", icon: Building2 },
  { key: "salary", label: "Salary", icon: DollarSign },
  { key: "contact", label: "Contact", icon: User },
];

function scoreColor(score: number): string {
  if (score === 0) return "text-green-600";
  if (score <= 15) return "text-info";
  if (score <= 30) return "text-amber-600";
  if (score <= 50) return "text-orange-600";
  return "text-red-600";
}

function scoreBarColor(score: number): string {
  if (score === 0) return "bg-green-500";
  if (score <= 15) return "bg-info/100";
  if (score <= 30) return "bg-amber-500";
  if (score <= 50) return "bg-orange-500";
  return "bg-red-500";
}

export function TrustAnalysisDisplay({ analysis }: TrustAnalysisDisplayProps) {
  const [showLlmSummary, setShowLlmSummary] = useState(false);
  const config = TIER_CONFIG[analysis.tier];
  const TierIcon = config.icon;
  const maxCategoryScore = Math.max(
    ...Object.values(analysis.category_scores),
    1,
  );

  return (
    <div className="space-y-3">
      {/* Trust Tier Header */}
      <Card className={cn("border", config.border)}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm">
              <TierIcon className={cn("h-5 w-5", config.color)} />
              Trust Rating
            </span>
            <Badge
              className={cn(
                config.bg,
                config.color,
                "border-0 text-sm font-semibold",
              )}
            >
              {config.label}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {/* Confidence bar */}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Risk Confidence</span>
              <span
                className={cn("font-medium", scoreColor(analysis.risk_score))}
              >
                {Math.round(analysis.confidence * 100)}%
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted">
              <div
                className={cn(
                  "h-2 rounded-full transition-all",
                  scoreBarColor(analysis.risk_score),
                )}
                style={{
                  width: `${Math.min(analysis.confidence * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Category Breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            Category Scores
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {CATEGORY_CONFIG.map(({ key, label, icon: CatIcon }) => {
              const score = analysis.category_scores[key] ?? 0;
              return (
                <div key={key} className="flex items-center gap-3">
                  <CatIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="w-24 text-xs text-muted-foreground">
                    {label}
                  </span>
                  <div className="flex-1">
                    <div className="h-1.5 w-full rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-1.5 rounded-full",
                          scoreBarColor(score),
                        )}
                        style={{
                          width: `${maxCategoryScore > 0 ? (score / maxCategoryScore) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                  <span
                    className={cn(
                      "w-8 text-right text-xs font-medium",
                      scoreColor(score),
                    )}
                  >
                    {score}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Reasons */}
      {analysis.reasons.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Reasons for Rating
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {analysis.reasons.map((reason, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-xs text-foreground"
                >
                  <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                  {reason}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* LLM Summary (collapsible) */}
      {analysis.llm_summary && (
        <Card>
          <CardHeader className="pb-2">
            <button
              className="flex w-full items-center justify-between text-sm"
              onClick={() => setShowLlmSummary(!showLlmSummary)}
            >
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                AI Analysis
              </CardTitle>
              {showLlmSummary ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          </CardHeader>
          {showLlmSummary && (
            <CardContent>
              <p className="text-xs leading-relaxed text-foreground">
                {analysis.llm_summary}
              </p>
              {analysis.llm_indicators &&
                analysis.llm_indicators.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {analysis.llm_indicators.map((ind, i) => (
                      <Badge
                        key={i}
                        variant="outline"
                        className="text-xs text-orange-600"
                      >
                        {ind}
                      </Badge>
                    ))}
                  </div>
                )}
            </CardContent>
          )}
        </Card>
      )}

      {/* No concerns message */}
      {analysis.reasons.length === 0 && !analysis.llm_summary && (
        <p className="text-xs text-muted-foreground">
          No trust concerns detected for this listing.
        </p>
      )}
    </div>
  );
}

/**
 * Compact trust tier badge for inline use in job cards and lists.
 */
export function TrustTierBadge({ tier }: { tier: TrustTier }) {
  const config = TIER_CONFIG[tier];
  const TierIcon = config.icon;
  return (
    <Badge
      className={cn(
        "gap-1 border-0 text-xs font-medium",
        config.bg,
        config.color,
      )}
    >
      <TierIcon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}
