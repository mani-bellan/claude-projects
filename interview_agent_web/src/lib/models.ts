import type { AgentType } from "@/types";

export interface ModelOption {
  id: string;
  label: string;
  tier: "free" | "paid";
  context: string;
  notes?: string;
}

// Curated subset of OpenRouter models. Users can also type a custom model id.
// IDs verified against https://openrouter.ai/api/v1/models — keep them in sync
// when bumping. Free-tier ids end with ":free" per OpenRouter convention.
export const MODEL_CATALOG: ModelOption[] = [
  // ── Free tier ────────────────────────────────────────────────────────────
  {
    id: "meta-llama/llama-3.2-3b-instruct:free",
    label: "Llama 3.2 3B (free)",
    tier: "free",
    context: "131k",
    notes: "Tiny + fast. Great default for Reader/Validator.",
  },
  {
    id: "google/gemma-4-31b-it:free",
    label: "Gemma 4 31B (free)",
    tier: "free",
    context: "131k",
    notes: "Strong mid-size from Google. Good alternative for Reader/Validator.",
  },
  {
    id: "meta-llama/llama-3.3-70b-instruct:free",
    label: "Llama 3.3 70B (free)",
    tier: "free",
    context: "131k",
    notes: "Strong default for Solver/Optimizer.",
  },
  {
    id: "nousresearch/hermes-3-llama-3.1-405b:free",
    label: "Hermes 3 Llama 3.1 405B (free)",
    tier: "free",
    context: "131k",
    notes: "Huge model. Use when you want maximum capability for free.",
  },

  // ── Paid ─────────────────────────────────────────────────────────────────
  {
    id: "google/gemini-2.5-flash",
    label: "Gemini 2.5 Flash",
    tier: "paid",
    context: "1M",
    notes: "Cheap, fast, huge context.",
  },
  {
    id: "google/gemini-2.5-pro",
    label: "Gemini 2.5 Pro",
    tier: "paid",
    context: "1M",
  },
  {
    id: "deepseek/deepseek-chat-v3.1",
    label: "DeepSeek Chat v3.1",
    tier: "paid",
    context: "163k",
    notes: "Excellent reasoning + code.",
  },
  {
    id: "qwen/qwen3-coder",
    label: "Qwen3 Coder",
    tier: "paid",
    context: "262k",
    notes: "Code-specialized. Great for coding/SQL questions.",
  },
  {
    id: "anthropic/claude-sonnet-4.5",
    label: "Claude Sonnet 4.5",
    tier: "paid",
    context: "200k",
  },
  {
    id: "anthropic/claude-sonnet-4.6",
    label: "Claude Sonnet 4.6",
    tier: "paid",
    context: "200k",
    notes: "Latest Anthropic Sonnet.",
  },
  {
    id: "openai/gpt-4o-mini",
    label: "GPT-4o mini",
    tier: "paid",
    context: "128k",
  },
  {
    id: "openai/gpt-4o",
    label: "GPT-4o",
    tier: "paid",
    context: "128k",
  },
];

export function findModel(id: string): ModelOption | undefined {
  return MODEL_CATALOG.find((m) => m.id === id);
}

// Default per-agent assignments. All free by default so a fresh user pays nothing.
export const DEFAULT_AGENT_MODELS: Record<AgentType, string> = {
  reader: "meta-llama/llama-3.2-3b-instruct:free",
  solver: "meta-llama/llama-3.3-70b-instruct:free",
  validator: "google/gemma-4-31b-it:free",
  optimizer: "meta-llama/llama-3.3-70b-instruct:free",
};

// Fallback chain per agent. If the primary returns 429/5xx/overload, OpenRouter
// tries the next id in the same request (route: "fallback"). Kept all-free so
// users on free credits aren't surprised by a paid fallback charge.
export const DEFAULT_AGENT_FALLBACKS: Record<AgentType, string[]> = {
  reader: [
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
  ],
  solver: [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-4-31b-it:free",
  ],
  validator: [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-4-31b-it:free",
  ],
  optimizer: [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-4-31b-it:free",
  ],
};
