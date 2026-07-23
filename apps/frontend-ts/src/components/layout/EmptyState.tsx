import Link from "next/link";
import { cn } from "@/lib/utils/cn";
import { Button, buttonVariants } from "@/components/ui/button";

interface EmptyStateProps {
  /** Short heading describing the empty condition. */
  title: string;
  /** Optional supporting copy. */
  description?: string;
  /** Optional primary call-to-action. */
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  /** Optional illustration or icon above the title. */
  icon?: React.ReactNode;
  /** Additional classes for the outer wrapper. */
  className?: string;
}

/**
 * Consistent empty-content panel for lists, search results, and dashboards.
 *
 * Prefer this over one-line muted strings so every page offers the same
 * visual weight and an optional next-step CTA.
 */
export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: EmptyStateProps) {
  const actionNode =
    action == null ? null : action.href != null ? (
      <Link
        href={action.href}
        className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
      >
        {action.label}
      </Link>
    ) : (
      <Button size="sm" variant="outline" onClick={action.onClick}>
        {action.label}
      </Button>
    );

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/20 px-6 py-12 text-center",
        className,
      )}
    >
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actionNode}
    </div>
  );
}
