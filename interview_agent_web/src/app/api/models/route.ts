import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const revalidate = 3600;

// Curated short list of paid models we surface in the UI. All free (`:free`)
// models OpenRouter lists are surfaced automatically — no hardcoded allowlist
// for those.
const CURATED_PAID_IDS = new Set([
  "google/gemini-2.5-flash",
  "google/gemini-2.5-pro",
  "anthropic/claude-sonnet-4.5",
  "anthropic/claude-sonnet-4.6",
  "deepseek/deepseek-chat-v3.1",
  "openai/gpt-4o-mini",
  "openai/gpt-4o",
  "qwen/qwen3-coder",
]);

interface OpenRouterModel {
  id: string;
  name?: string;
  context_length?: number;
  description?: string;
  pricing?: {
    prompt?: string;
    completion?: string;
  };
}

export interface CatalogEntry {
  id: string;
  label: string;
  tier: "free" | "paid";
  context: string;
}

function formatContext(len?: number): string {
  if (!len || len <= 0) return "—";
  if (len >= 1_000_000) return `${(len / 1_000_000).toFixed(1)}M`;
  if (len >= 1000) return `${Math.round(len / 1000)}k`;
  return String(len);
}

function cleanName(name: string | undefined, id: string): string {
  if (!name) return id;
  // OpenRouter often prefixes the org, e.g. "Meta: Llama 3.3 70B Instruct"
  // and free variants append "(free)". Keep that intact — it's already short.
  return name.length > 0 ? name : id;
}

export async function GET() {
  try {
    const response = await fetch("https://openrouter.ai/api/v1/models", {
      next: { revalidate: 3600 },
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `OpenRouter responded ${response.status}` },
        { status: 502 }
      );
    }

    const json = (await response.json()) as { data?: OpenRouterModel[] };
    const raw = Array.isArray(json.data) ? json.data : [];

    const entries: CatalogEntry[] = [];
    for (const m of raw) {
      if (!m.id || typeof m.id !== "string") continue;
      const isFree = m.id.endsWith(":free");
      const isCurated = CURATED_PAID_IDS.has(m.id);
      if (!isFree && !isCurated) continue;

      entries.push({
        id: m.id,
        label: cleanName(m.name, m.id),
        tier: isFree ? "free" : "paid",
        context: formatContext(m.context_length),
      });
    }

    entries.sort((a, b) => {
      if (a.tier !== b.tier) return a.tier === "free" ? -1 : 1;
      return a.label.localeCompare(b.label);
    });

    if (entries.length === 0) {
      return NextResponse.json(
        { error: "OpenRouter returned an empty model list" },
        { status: 502 }
      );
    }

    return NextResponse.json(
      { models: entries, fetchedAt: Date.now() },
      {
        headers: {
          "Cache-Control":
            "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400",
        },
      }
    );
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to fetch models" },
      { status: 502 }
    );
  }
}
