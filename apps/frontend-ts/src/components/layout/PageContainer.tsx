import { cn } from "@/lib/utils/cn";

export type PageContainerVariant = "full-bleed" | "content" | "wide" | "form";

interface PageContainerProps {
  /** Width strategy for the page content. */
  variant?: PageContainerVariant;
  /** Additional classes. */
  className?: string;
  /** Page content. */
  children: React.ReactNode;
}

const variantClasses: Record<PageContainerVariant, string> = {
  "full-bleed": "w-full",
  content: "max-w-5xl mx-auto",
  wide: "max-w-7xl mx-auto",
  form: "max-w-3xl mx-auto",
};

/**
 * Consistent outer wrapper for page-level content.
 *
 * Width presets:
 * - ``full-bleed``: ops/dashboard surfaces that should use the full main pane
 * - ``wide``: multi-column forms and analysis results (``max-w-7xl``)
 * - ``content``: medium reading layouts (``max-w-5xl``)
 * - ``form``: single-column short forms only (``max-w-3xl``)
 *
 * Prefer ``wide`` / ``full-bleed`` when the page uses multi-column grids so
 * content is not squeezed inside a narrow measure. Also applies a standard
 * vertical rhythm (``space-y-6``) between major sections.
 *
 * @param variant - Width strategy for the page content.
 * @param className - Optional extra classes.
 * @param children - Page content.
 */
export function PageContainer({
  variant = "full-bleed",
  className,
  children,
}: PageContainerProps) {
  return (
    <div className={cn("space-y-6", variantClasses[variant], className)}>
      {children}
    </div>
  );
}
