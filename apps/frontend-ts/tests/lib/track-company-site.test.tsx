/**
 * Tracking an application made on the company site (company-site-apply, S3).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTrackCompanySiteApplication } from "@/lib/hooks/use-jobs";
import type { JobListing } from "@/lib/types/api";

const mockTrackExternal = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/applications", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api/applications")>();
  return {
    ...actual,
    applicationsApi: {
      ...actual.applicationsApi,
      trackExternal: (...args: unknown[]) => mockTrackExternal(...args),
    },
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const job: JobListing = {
  job_id: "job-1",
  title: "Graduate Machine Learning Engineer",
  company: "Lumen Analytics Pte. Ltd.",
  description: "  Train models in PyTorch for the analytics team.  ",
  source: "mycareersfuture",
  source_url: "https://www.mycareersfuture.gov.sg/job/it/graduate-ml-lumen-1",
  is_remote: false,
  skills: [],
};

/**
 * Wrap a hook in a fresh query client.
 *
 * @returns A wrapper component for renderHook.
 */
function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

describe("useTrackCompanySiteApplication", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("records the application with method Company site and the company URL", async () => {
    mockTrackExternal.mockResolvedValue({
      success: true,
      application_id: "job-1",
      status: "applied_elsewhere",
      message: "Tracked",
    });
    const { result } = renderHook(() => useTrackCompanySiteApplication(), {
      wrapper: wrapper(),
    });
    result.current.mutate({
      job,
      companyUrl: "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
      level: "exact",
    });
    await waitFor(() => expect(mockTrackExternal).toHaveBeenCalled());
    expect(mockTrackExternal).toHaveBeenCalledWith({
      job_id: "job-1",
      job_title: "Graduate Machine Learning Engineer",
      company: "Lumen Analytics Pte. Ltd.",
      application_method: "Company site",
      metadata: {
        company_site_url:
          "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
        company_site_level: "exact",
        source_url:
          "https://www.mycareersfuture.gov.sg/job/it/graduate-ml-lumen-1",
        description: "Train models in PyTorch for the analytics team.",
      },
    });
  });
});
