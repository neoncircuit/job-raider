/**
 * Job Raider - Agent system card tests
 *
 * Tests cover the data, empty, and error states, and that the card has no
 * controls (shutdown stays API-only).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AgentSystemCard } from "@/components/agent-system-card";
import type {
  AgentPerformanceSummary,
  AgentSystemStatus,
} from "@/lib/types/api";

const mockGetStatus = vi.fn();
const mockGetPerformance = vi.fn();

vi.mock("@/lib/api/agents", () => ({
  agentsApi: {
    getStatus: (...args: unknown[]) => mockGetStatus(...args),
    getPerformance: (...args: unknown[]) => mockGetPerformance(...args),
  },
}));

const STATUS: AgentSystemStatus = {
  coordinator_running: true,
  communication_healthy: false,
  registered_agents: 1,
  active_pipelines: 0,
  completed_pipelines: 0,
  agent_status: {
    career_coach: {
      agent_id: "career_coach",
      state: "ready",
      capabilities: { task_types: ["gap_analysis"] },
      performance: {
        tasks_completed: 4,
        tasks_failed: 1,
        average_execution_time: 12.34,
        success_rate: 0.75,
        last_execution_time: null,
        utilization: 1 / 3,
      },
    },
  },
};

const PERFORMANCE: AgentPerformanceSummary = {
  total_tasks_completed: 4,
  total_tasks_failed: 1,
  average_success_rate: 0.75,
  average_execution_time: 12.34,
  agent_utilization: { career_coach: 1 / 3 },
};

/**
 * Render the card inside a fresh query client without retries.
 */
function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AgentSystemCard />
    </QueryClientProvider>,
  );
}

describe("AgentSystemCard", () => {
  beforeEach(() => {
    mockGetStatus.mockReset();
    mockGetPerformance.mockReset();
    mockGetPerformance.mockResolvedValue({ data: PERFORMANCE });
  });

  it("renders system health and one row per agent", async () => {
    mockGetStatus.mockResolvedValue({ data: STATUS });
    renderCard();

    expect(await screen.findByText("career_coach")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("Coordinator: OK")).toBeInTheDocument();
    expect(screen.getByText("Message bus: Down")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText("12.3 s")).toBeInTheDocument();
    expect(
      await screen.findByText(/4 tasks done · 1 failed/),
    ).toBeInTheDocument();
  });

  it("shows an empty state when no agents are registered", async () => {
    mockGetStatus.mockResolvedValue({
      data: { ...STATUS, registered_agents: 0, agent_status: {} },
    });
    renderCard();

    expect(await screen.findByText("No agents registered")).toBeInTheDocument();
  });

  it("shows an error banner when status fails", async () => {
    mockGetStatus.mockRejectedValue(new Error("Agent system not ready"));
    renderCard();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load agent status: Agent system not ready",
    );
  });

  it("has no buttons", async () => {
    mockGetStatus.mockResolvedValue({ data: STATUS });
    renderCard();

    await screen.findByText("career_coach");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
