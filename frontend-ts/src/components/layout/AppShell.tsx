import { Suspense } from "react";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { ErrorBoundary } from "./ErrorBoundary";
import { PageSkeleton } from "./PageSkeleton";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile top nav */}
        <div className="md:hidden">
          <MobileNav />
        </div>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <ErrorBoundary>
            <Suspense fallback={<PageSkeleton />}>
              {children}
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
