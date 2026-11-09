/**
 * Typed demo data (Step 4).
 *
 * The files in `seed/` come from `scripts/build_demo_data.py`, which runs the
 * real code on synthetic input. The values below have no backend behind them,
 * so they say so: the demo shows no invented GPU or host readings.
 */

import type {
  ApplicationDashboardResponse,
  AppSettings,
  AvailableModelsResponse,
  CoverLetterResponse,
  DiscoverShortlistResponse,
  HardwareFitReport,
  HealthResponse,
  MetricsSummaryResponse,
  OllamaModelList,
  PipelineHistoryResponse,
  SystemResourcesResponse,
  UserProfile,
} from "@/lib/types/api";

import applications from "./seed/applications.json";
import history from "./seed/history.json";
import letter from "./seed/letter.json";
import metrics from "./seed/metrics.json";
import profile from "./seed/profile.json";
import shortlist from "./seed/shortlist.json";

const LOCAL_MODELS = ["qwen2.5:3b", "qwen2.5:7b"];

export const demoApplications = applications as ApplicationDashboardResponse;
export const demoHistory = history as PipelineHistoryResponse;
export const demoLetter = letter as unknown as CoverLetterResponse;
export const demoMetrics = metrics as MetricsSummaryResponse;
export const demoProfile = profile as unknown as UserProfile;
export const demoShortlist = shortlist as unknown as DiscoverShortlistResponse;

/** Health of the demo: there is no backend to check. */
export const demoHealth: HealthResponse = {
  status: "healthy",
  timestamp: "2026-11-04T12:00:00",
  checks: [
    {
      name: "demo",
      status: "healthy",
      message: "Sample data in your browser; no backend",
    },
  ],
  summary: { healthy: 1 },
};

/** The demo has no host, so it reports no reading. */
export const demoResources: SystemResourcesResponse = {
  cpu: { percent: null },
  ram: { used_mb: null, total_mb: null, percent: null },
  gpu: null,
};

/** The default local setup, with no cloud fallback. */
export const demoSettings: AppSettings = {
  routing: {
    selection: {
      primary_provider: "ollama",
      primary_model: "qwen2.5:3b",
      fallback_provider: null,
      fallback_model: null,
    },
    cover_letter_writing: {
      primary_provider: "ollama",
      primary_model: "qwen2.5:7b",
      fallback_provider: null,
      fallback_model: null,
    },
  },
  api_config: {
    has_anthropic_key: false,
    has_gemini_key: false,
    cloud_fallback_provider: "none",
    ollama_host: "http://localhost:11434",
  },
  model_params: { temperature: 0.7, max_tokens: 4096, top_p: 0.9 },
  cost_limits: {
    max_api_cost_per_run: 0,
    enable_cache: true,
    cache_ttl: 3600,
  },
};

/** Two installed sample models, as the Local models card lists them. */
export const demoOllamaModels: OllamaModelList = {
  host: "localhost:11434",
  reachable: true,
  in_use: LOCAL_MODELS,
  models: [
    {
      name: "qwen2.5:3b",
      size: 1_929_912_432,
      parameter_size: "3.1B",
      quantization: "Q4_K_M",
      in_use: true,
    },
    {
      name: "qwen2.5:7b",
      size: 4_683_087_332,
      parameter_size: "7.6B",
      quantization: "Q4_K_M",
      in_use: true,
    },
  ],
};

/**
 * The demo reads no hardware, so it shows no invented GPU. It says how a local
 * install gets hardware fit instead.
 */
export const demoHardwareFit: HardwareFitReport = {
  available: false,
  reason:
    "The demo runs in your browser and reads no hardware. A local install with llmfit shows which models fit your GPU.",
  install_hint:
    "llmfit is optional and recommended. Run ./setup.sh, or install it into the backend environment: apps/backend-py/.venv/bin/pip install llmfit==1.1.20",
  headroom_percent: 75,
  budget_gb: 0,
  ollama_reachable: true,
  installed: [],
  suggestions: [],
};

/** The recommended local models. */
export const demoModels: AvailableModelsResponse = {
  ollama: LOCAL_MODELS,
  ollama_installed: LOCAL_MODELS,
};
