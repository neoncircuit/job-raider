"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { createContext, useContext, useRef, useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import type { JobSearchResponse } from "@/lib/types/api";
import type { Dispatch, SetStateAction } from "react";
import { validateAuthConfig } from "@/lib/api/client";
import { useEffect } from "react";

// ── App State Context (client-only UI state) ──────────────────────────────────

interface AppState {
  selectedJobId: string | null;
  setSelectedJobId: Dispatch<SetStateAction<string | null>>;
  jobsPage: number;
  setJobsPage: Dispatch<SetStateAction<number>>;
  searchResults: JobSearchResponse | null;
  setSearchResults: Dispatch<SetStateAction<JobSearchResponse | null>>;
  activeRunId: string | null;
  setActiveRunId: Dispatch<SetStateAction<string | null>>;
  savedJobIds: Set<string>;
  addSavedJobId: (id: string) => void;
  removeSavedJobId: (id: string) => void;
}

const AppStateContext = createContext<AppState | null>(null);

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within Providers");
  return ctx;
}

// ── Providers ─────────────────────────────────────────────────────────────────

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClientRef = useRef<QueryClient | null>(null);
  if (queryClientRef.current == null) {
    queryClientRef.current = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 1,
          refetchOnWindowFocus: false,
        },
      },
    });
  }

  // eslint-disable-next-line react-hooks/refs
  const queryClient = queryClientRef.current;
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobsPage, setJobsPage] = useState(0);
  const [searchResults, setSearchResults] = useState<JobSearchResponse | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [savedJobIds, setSavedJobIds] = useState<Set<string>>(new Set());

  const addSavedJobId = (id: string) =>
    setSavedJobIds((prev) => new Set(prev).add(id));
  const removeSavedJobId = (id: string) =>
    setSavedJobIds((prev) => { const s = new Set(prev); s.delete(id); return s; });

  // Validate auth configuration on mount
  useEffect(() => {
    const authStatus = validateAuthConfig();
    console.log("[JobRaider] Auth configuration:", authStatus);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <AppStateContext.Provider
          value={{
            selectedJobId,
            setSelectedJobId,
            jobsPage,
            setJobsPage,
            searchResults,
            setSearchResults,
            activeRunId,
            setActiveRunId,
            savedJobIds,
            addSavedJobId,
            removeSavedJobId,
          }}
        >
          {children}
          <Toaster richColors position="top-right" />
        </AppStateContext.Provider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
