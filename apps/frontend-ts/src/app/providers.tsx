"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { createContext, useContext, useMemo, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Toaster } from "@/components/ui/sonner";
import { createLogger } from "@/lib/logger";

const logger = createLogger("Providers");

/**
 * Client-only UI state shared across the application.
 *
 * Server/cache state belongs in TanStack Query, not here.
 */
interface AppState {
  /** Currently selected job ID in the jobs list. */
  selectedJobId: string | null;
  /** Set the currently selected job ID. */
  setSelectedJobId: Dispatch<SetStateAction<string | null>>;
  /** Zero-based page index for the jobs list pagination. */
  jobsPage: number;
  /** Set the jobs list page index. */
  setJobsPage: Dispatch<SetStateAction<number>>;
  /** Active automation run ID, if any. */
  activeRunId: string | null;
  /** Set the active automation run ID. */
  setActiveRunId: Dispatch<SetStateAction<string | null>>;
}

const AppStateContext = createContext<AppState | null>(null);

/**
 * Hook to access the client-only application UI state.
 *
 * @throws {Error} If used outside of {@link Providers}.
 * @returns The current application state and its setters.
 */
export function useAppState(): AppState {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within Providers");
  }
  return ctx;
}

interface ProvidersProps {
  /** Child components to wrap. */
  children: ReactNode;
}

/**
 * Root client providers for the application.
 *
 * Bundles TanStack Query, theme switching, toast notifications, and a minimal
 * client-only state context. Each render reuses the same `QueryClient` thanks
 * to `useMemo` with a stable initializer.
 */
export function Providers({ children }: ProvidersProps) {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
    [],
  );

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobsPage, setJobsPage] = useState(0);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  logger.info("Providers mounted");

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <AppStateContext.Provider
          value={{
            selectedJobId,
            setSelectedJobId,
            jobsPage,
            setJobsPage,
            activeRunId,
            setActiveRunId,
          }}
        >
          {children}
          <Toaster richColors position="top-right" />
        </AppStateContext.Provider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
