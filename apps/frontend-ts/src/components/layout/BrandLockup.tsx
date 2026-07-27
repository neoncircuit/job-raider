import { cn } from "@/lib/utils/cn";
import { BrandMark } from "./BrandMark";

interface BrandLockupProps {
  /** Mark edge length in pixels. Defaults to 32. */
  size?: number;
  /** Show the muted tagline under the wordmark. Defaults to true. */
  showTagline?: boolean;
  /** Additional classes on the outer flex row. */
  className?: string;
}

/**
 * Job Raider brand lockup: raid mark + spaced wordmark (+ optional tagline).
 *
 * @param size - Pixel size for the square mark.
 * @param showTagline - When true, render ``Automated Pipeline`` under the name.
 * @param className - Optional classes on the lockup container.
 * @returns Horizontal brand lockup for sidebar / mobile chrome.
 */
export function BrandLockup({
  size = 32,
  showTagline = true,
  className,
}: BrandLockupProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark size={size} />
      <div className="min-w-0">
        <p className="font-heading text-sm font-bold leading-tight text-sidebar-foreground">
          <span className="tracking-tight">Job</span>
          <span className="mx-1 tracking-[0.14em]">Raider</span>
        </p>
        {showTagline ? (
          <p className="mt-0.5 text-[10px] leading-none tracking-wide text-muted-foreground">
            Automated Pipeline
          </p>
        ) : null}
      </div>
    </div>
  );
}
