"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  hostnameFromUrl,
  type MissionSourceCitation,
} from "@/lib/mission-sources";
import { cn } from "@/lib/utils";

interface CoverLetterSourcesProps {
  sources: MissionSourceCitation[];
}

/**
 * Perplexity-inspired numbered source citations for mission grounding.
 *
 * One source renders inline; two or more use a collapsible panel. Numbers
 * label the panel only — they are not injected into the editable letter.
 *
 * @param props.sources - Citation cards from mission_context.
 */
export function CoverLetterSources({ sources }: CoverLetterSourcesProps) {
  const [open, setOpen] = useState(false);

  if (!sources.length) {
    return null;
  }

  if (sources.length === 1) {
    return (
      <div className="space-y-2" data-testid="cover-letter-sources">
        <p className="text-xs font-medium text-foreground">Sources</p>
        <SourceCard source={sources[0]} />
      </div>
    );
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="space-y-2"
      data-testid="cover-letter-sources"
    >
      <CollapsibleTrigger
        className={cn(
          "flex w-full items-center justify-between rounded-md border border-border",
          "bg-muted/30 px-3 py-2 text-left text-xs font-medium text-foreground",
          "hover:bg-muted/50 transition-colors",
        )}
      >
        <span>
          Sources ({sources.length}) — grounded with company-mission pages
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-2">
        {sources.map((source) => (
          <SourceCard key={`${source.index}-${source.url}`} source={source} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

/**
 * Single numbered citation card linking to an external mission page.
 *
 * @param props.source - One citation entry.
 */
function SourceCard({ source }: { source: MissionSourceCitation }) {
  const domain = source.domain || hostnameFromUrl(source.url);
  const label = (source.title || "").trim() || domain;

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex gap-2.5 rounded-md border border-border bg-background/60 px-3 py-2",
        "hover:border-primary/40 hover:bg-muted/20 transition-colors group",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-5 min-w-5 items-center justify-center rounded",
          "bg-muted px-1 font-mono text-[10px] font-semibold text-muted-foreground",
        )}
        aria-hidden
      >
        {source.index}
      </span>
      <span className="min-w-0 flex-1 space-y-0.5">
        <span className="flex items-start gap-1.5 text-sm font-medium text-foreground group-hover:text-primary">
          <span className="truncate">{label}</span>
          <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
        </span>
        <span className="block truncate text-[11px] text-muted-foreground">
          {domain}
        </span>
        {source.snippet ? (
          <span className="block text-[11px] leading-snug text-muted-foreground/90 line-clamp-2">
            {source.snippet}
          </span>
        ) : null}
      </span>
    </a>
  );
}
