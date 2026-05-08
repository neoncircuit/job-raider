// Discriminated union of all WebSocket message types broadcast by the backend.
// Source of truth: backend-py/src/api/websocket/progress.py

export type WSMessage =
  | { type: "connected"; run_id: string; timestamp: string }
  | { type: "pipeline_started"; run_id: string; timestamp: string }
  | { type: "stage_started"; stage: string; metadata: Record<string, unknown>; timestamp: string }
  | { type: "stage_progress"; stage: string; progress: number; metadata: Record<string, unknown>; timestamp: string }
  | { type: "stage_completed"; stage: string; result: Record<string, unknown>; timestamp: string }
  | { type: "jobs_found"; count: number; source?: string | null; timestamp: string }
  | { type: "jobs_scored"; count: number; jobs: unknown[]; timestamp: string }
  | { type: "resume_generated"; job_id: string; resume_path: string; timestamp: string }
  | { type: "application_submitted"; job_id: string; application_id: string; method: string; timestamp: string }
  | { type: "pipeline_failed"; error: string; stage?: string | null; timestamp: string }
  | { type: "pipeline_complete"; summary: Record<string, unknown>; timestamp: string }
  | { type: "ping"; data: unknown; timestamp: string };

export type WSConnectionStatus = "idle" | "connecting" | "connected" | "error" | "closed";
