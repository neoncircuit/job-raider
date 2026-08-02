import { Suspense } from "react";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { ErrorBoundary } from "./ErrorBoundary";
import { PageSkeleton } from "./PageSkeleton";
import { CinematicDocumentSync } from "@/lib/hooks/use-cinematic";
import { ColorSchemeDocumentSync } from "@/lib/hooks/use-color-scheme";

/**
 * Application chrome: sidebar (desktop), mobile nav, and main content.
 *
 * Applies a quiet raid atmosphere wash behind content. Optional cinematic
 * deepening and color schemes (neon / retrowave) are gated by Settings.
 *
 * @param children - Page content rendered inside the scrollable main region.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background relative">
      <CinematicDocumentSync />
      <ColorSchemeDocumentSync />
      <div className="raid-atmosphere" aria-hidden />

      <div className="hidden md:flex relative z-10">
        <Sidebar />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden relative z-10">
        <div className="md:hidden">
          <MobileNav />
        </div>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <ErrorBoundary>
            <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
