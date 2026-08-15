"use client";

import type { ReactNode } from "react";
import { parseJobMarkdown } from "@/lib/utils/job-description";

interface JobDescriptionBodyProps {
  /** Markdown or plain-text job description. */
  markdown: string;
}

const headingClass =
  "text-lg font-bold capitalize border-l-4 border-primary pl-3 py-2 bg-muted rounded-r shadow-sm";

const INLINE_TOKEN =
  /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`|\[[^\]]+\]\([^)]+\))/g;

/**
 * Render a short inline Markdown fragment (bold, italic, code, links).
 *
 * Args:
 *   text: A heading, paragraph, or list item.
 *
 * Returns:
 *   React nodes with inline emphasis. HTML is not interpreted.
 */
function renderInline(text: string): ReactNode[] {
  const parts = text.split(INLINE_TOKEN);
  return parts.map((part, index) => {
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {bold[1]}
        </strong>
      );
    }
    const italic = part.match(/^\*([^*]+)\*$/);
    if (italic) {
      return (
        <em key={index} className="italic">
          {italic[1]}
        </em>
      );
    }
    const code = part.match(/^`([^`]+)`$/);
    if (code) {
      return (
        <code
          key={index}
          className="rounded bg-muted px-1 py-0.5 text-xs font-mono"
        >
          {code[1]}
        </code>
      );
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const href = link[2];
      const safe =
        href.startsWith("http://") ||
        href.startsWith("https://") ||
        href.startsWith("mailto:");
      if (!safe) {
        return <span key={index}>{link[1]}</span>;
      }
      return (
        <a
          key={index}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 text-foreground"
        >
          {link[1]}
        </a>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

/**
 * Render a job description stored as Markdown.
 *
 * Covers ATX headings, lists, bold, italic, code, and http(s) links.
 * Raw HTML is not interpreted.
 */
export function JobDescriptionBody({ markdown }: JobDescriptionBodyProps) {
  const blocks = parseJobMarkdown(markdown);

  return (
    <div className="space-y-4">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <h3 key={index} className={headingClass}>
              {renderInline(block.text)}
            </h3>
          );
        }
        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <ListTag
              key={index}
              className={
                block.ordered
                  ? "list-decimal space-y-1.5 pl-5 text-sm text-foreground"
                  : "list-disc space-y-1.5 pl-5 text-sm text-foreground"
              }
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="leading-relaxed">
                  {renderInline(item)}
                </li>
              ))}
            </ListTag>
          );
        }
        return (
          <p key={index} className="text-sm leading-relaxed text-foreground">
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}
