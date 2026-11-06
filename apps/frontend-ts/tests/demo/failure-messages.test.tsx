/**
 * Tests for the messages of refused actions on the Jobs page (Step 4, MH-3).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { demoShortlist } from "@/demo/data";
import { handlers, NOT_IN_DEMO, ONE_SAMPLE_LETTER } from "@/demo/handlers";
import {
  useAnalyzeTrust,
  useClassifyJob,
  useExplainJobFit,
  useGenerateCoverLetter,
  useSaveJob,
} from "@/lib/hooks/use-jobs";

import { server } from "../setup/globals";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const job = demoShortlist.jobs[1];
const target = { id: job.job_id, job };
const client = new QueryClient({
  defaultOptions: { mutations: { retry: false } },
});

/**
 * Give a hook the query client.
 *
 * @param props - The component props.
 * @param props.children - The hook test component.
 * @returns The children inside the provider.
 */
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/**
 * Run an action and read its failure message.
 *
 * @param useAction - The mutation hook.
 * @param input - The mutation input.
 * @param message - The message that the visitor must see.
 * @returns Nothing.
 */
async function expectMessage(
  useAction: () => { mutate: (input: never) => void },
  input: unknown,
  message: string,
): Promise<void> {
  const { result } = renderHook(useAction, { wrapper });

  act(() => result.current.mutate(input as never));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
}

describe("refused actions on the Jobs page", () => {
  beforeEach(() => {
    vi.mocked(toast.error).mockClear();
    server.use(...handlers);
  });

  it("explains a letter for another job", async () => {
    await expectMessage(useGenerateCoverLetter, target, ONE_SAMPLE_LETTER);
  });

  it("explains a saved job", async () => {
    await expectMessage(
      useSaveJob,
      { id: job.job_id, saved: true },
      NOT_IN_DEMO,
    );
  });

  it("explains a job analysis", async () => {
    await expectMessage(useClassifyJob, target, NOT_IN_DEMO);
  });

  it("explains a trust analysis", async () => {
    await expectMessage(useAnalyzeTrust, target, NOT_IN_DEMO);
  });

  it("explains a fit explanation", async () => {
    await expectMessage(useExplainJobFit, target, NOT_IN_DEMO);
  });
});
