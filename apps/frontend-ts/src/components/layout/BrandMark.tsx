import { cn } from "@/lib/utils/cn";

interface BrandMarkProps {
  /** Pixel size for the square mark. Defaults to 32. */
  size?: number;
  /** Additional classes on the outer element. */
  className?: string;
}

/**
 * Angular JR lockup used as the Job Raider brand mark.
 *
 * @param size - Edge length in pixels for the square mark.
 * @param className - Optional extra classes.
 * @returns SVG mark on a primary background.
 */
export function BrandMark({ size = 32, className }: BrandMarkProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center bg-primary text-primary-foreground",
        className,
      )}
      style={{ width: size, height: size, borderRadius: "var(--radius)" }}
      aria-hidden
    >
      <svg
        width={size * 0.62}
        height={size * 0.62}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M4 3h9.5c3.2 0 5.5 2.1 5.5 5.1 0 2.4-1.4 4.2-3.6 4.9L19.5 21h-3.4l-3.8-7.2H7.2V21H4V3zm3.2 2.8v5.2h5.6c1.7 0 2.7-.9 2.7-2.6s-1-2.6-2.7-2.6H7.2z"
          fill="currentColor"
        />
        <path
          d="M20 3v3.2L16.8 9.4 15.2 7.8 18.4 4.6H14V3h6z"
          fill="currentColor"
        />
      </svg>
    </div>
  );
}
