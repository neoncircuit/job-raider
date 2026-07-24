import { cn } from "@/lib/utils/cn";

interface PageHeaderProps {
  /** Page title shown as the primary heading. */
  title: string;
  /** Optional supporting sentence under the title. */
  subtitle?: string;
  /** Optional trailing actions (buttons, links). */
  actions?: React.ReactNode;
  /** Optional leading icon or element before the title text. */
  icon?: React.ReactNode;
  /** Additional classes for the outer wrapper. */
  className?: string;
}

/**
 * Standard page title block used across all routes.
 *
 * Uses mono tracking for titles so page chrome matches the raid type system.
 *
 * @param title - Primary heading text.
 * @param subtitle - Optional supporting sentence.
 * @param actions - Optional trailing action nodes.
 * @param icon - Optional leading icon.
 * @param className - Optional wrapper classes.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  icon,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {icon}
          <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">
            {title}
          </h1>
        </div>
        {subtitle ? (
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      ) : null}
    </div>
  );
}
