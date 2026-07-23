import { cn } from "@/lib/utils/cn";

interface QueryErrorBannerProps {
  /** Error message shown to the user. */
  message: string;
  /** Optional prefix before the message (e.g. "Search failed"). */
  title?: string;
  /** Additional classes for the banner. */
  className?: string;
}

/**
 * Bordered destructive banner for failed React Query / API loads.
 *
 * Matches the Jobs search error pattern so failed queries are visible
 * instead of looking like empty data.
 */
export function QueryErrorBanner({
  message,
  title,
  className,
}: QueryErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive",
        className,
      )}
    >
      {title ? (
        <>
          <span className="font-medium">{title}</span>
          {": "}
        </>
      ) : null}
      {message}
    </div>
  );
}
