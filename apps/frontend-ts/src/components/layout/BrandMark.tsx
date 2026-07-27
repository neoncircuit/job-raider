import { cn } from "@/lib/utils/cn";

interface BrandMarkProps {
  /** Pixel size for the square mark. Defaults to 32. */
  size?: number;
  /** Additional classes on the outer element. */
  className?: string;
}

/**
 * Angular JR raid mark: geometric J with a sharp top-right chevron cut.
 *
 * Gains a soft pulse when cinematic atmosphere is enabled
 * (``[data-cinematic=on] .brand-mark`` in globals.css).
 *
 * @param size - Edge length in pixels for the square mark.
 * @param className - Optional extra classes.
 * @returns SVG mark on a primary background.
 */
export function BrandMark({ size = 32, className }: BrandMarkProps) {
  return (
    <div
      className={cn(
        "brand-mark flex shrink-0 items-center justify-center bg-primary text-primary-foreground",
        className,
      )}
      style={{ width: size, height: size, borderRadius: "var(--radius)" }}
      aria-hidden
    >
      <svg
        width={size * 0.68}
        height={size * 0.68}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Geometric J stem + bowl */}
        <path
          d="M7 3.5h8.2c2.9 0 5.1 2 5.1 4.85 0 2.55-1.55 4.45-4 5.05L20.2 21h-3.55l-3.7-7.15H10.2V21H7V3.5zm3.2 2.75v5.35h5.15c1.55 0 2.55-.85 2.55-2.5s-.95-2.5-2.55-2.5H10.2z"
          fill="currentColor"
        />
        {/* Raid chevron — sharp NE strike */}
        <path
          className="brand-mark-chevron"
          d="M21 3v4.1L15.4 12.7l-1.85-1.85L17.3 7.1H13.2V3H21z"
          fill="currentColor"
        />
      </svg>
    </div>
  );
}
