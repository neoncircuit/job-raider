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
 * Provides four width presets so data-dense pages can use the full viewport
 * while forms and long prose stay within a comfortable reading measure. It
 * also applies a standard vertical rhythm (`space-y-6`) between major
 * sections.
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
