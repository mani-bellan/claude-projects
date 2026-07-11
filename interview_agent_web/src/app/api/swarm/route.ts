import { NextResponse, type NextRequest } from "next/server";
import { getMode, type Mode } from "@/lib/constants";
import { DEFAULT_AGENT_FALLBACKS, DEFAULT_AGENT_MODELS } from "@/lib/models";
import type { AgentType, Category } from "@/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";
const MAX_QUESTION_CHARS = 2000;

const VALID_CATEGORIES = new Set<Category>([
  "coding",
  "architecture",
  "design",
  "sql",
  "streaming",
  "general",
]);

// Adaptive token budget — concept answers don't need essays, and Reader/Validator
// outputs are structured/short. This cuts per-question token spend roughly in half
// vs. the original blanket 2048.
function maxTokensFor(agent: AgentType, mode: Mode): number {
  if (agent === "reader") return 600;
  if (agent === "validator") return 1000;
  if (mode === "concept") return 1400;
  return 2048;
}

const READER_PROMPT = `You are a data engineering interview question analyst.
Given a question, extract:
1. CATEGORY: (coding/architecture/design/sql/streaming/general)
2. DIFFICULTY: (easy/medium/hard)
3. KEY CONCEPTS: list the main DE concepts being tested
4. CONSTRAINTS: any explicit constraints mentioned
5. EXPECTED OUTPUT: what a complete answer should include

Be concise and structured.`;

const CODE_PROMPTS = {
  solver: `You are an expert data engineer solving an interview question that requires code.

Produce a thorough solution:
- For CODING (Python): complete, working code with brief explanation
- For SQL: the full query with explanation of the logic, joins, and window functions used

Always include:
1. APPROACH: high-level strategy
2. SOLUTION: complete code or query
3. INITIAL COMPLEXITY: state your initial time and space complexity estimate
4. EDGE CASES: list edge cases you considered`,

  validator: `You are a senior data engineer and code reviewer.
Critically validate the proposed solution. Check for:
1. CORRECTNESS: Does it solve the problem? Any logical errors?
2. TIME COMPLEXITY: Is the stated complexity correct? Can it be improved?
3. SPACE COMPLEXITY: Is memory usage optimal? Any hidden space costs?
4. EDGE CASES: What edge cases are NOT handled?
5. SCALABILITY: Will it work at scale (millions of rows, distributed systems)?
6. CODE QUALITY: Anti-patterns, inefficiencies, missing error handling?
7. ISSUES FOUND: List specific problems with severity (critical/major/minor)

Be specific and precise. This is for an interview context.`,

  optimizer: `You are a principal data engineer and algorithm optimization expert.
Based on the validation report, produce a FINAL OPTIMIZED SOLUTION.

Your response MUST include these exact sections:

## FINAL SOLUTION
[Complete, production-ready code or query — fix ALL issues from validation]

## TIME COMPLEXITY
[Big-O analysis of the optimized solution with explanation of best/average/worst case]

## SPACE COMPLEXITY
[Big-O analysis of memory usage with explanation]

## OPTIMIZATIONS MADE
[Bullet list of each specific improvement over the original]

## INTERVIEW TIPS
[2-3 key points to mention in an interview to impress the interviewer]

Do not skip any section. Code must be clean, readable, and production-grade.`,
} as const;

const CONCEPT_PROMPTS = {
  solver: `You are an expert data engineer answering an interview question about architecture, system design, streaming systems, or general DE concepts.

Produce a thorough answer that includes:
1. APPROACH: high-level framing of the problem
2. ANSWER: detailed explanation covering relevant components, data flow, technologies, and reasoning
3. KEY DECISIONS: the major choices you'd make and why
4. TRADE-OFFS: the main trade-offs of your chosen approach

Be concrete: name real technologies, patterns, and components (Kafka, Spark, Airflow, Iceberg, etc.).
Do NOT include code unless the question explicitly asks for an implementation snippet.
Do NOT discuss Big-O time/space complexity — that is not relevant for design or conceptual questions.`,

  validator: `You are a senior data engineer reviewing a proposed design or conceptual answer.

Critically evaluate the solution. Check for:
1. CORRECTNESS: Does it actually address the question? Any conceptual errors or missing pieces?
2. SCALABILITY: Will the design hold up under realistic load (millions of events/second, large datasets)?
3. FAULT TOLERANCE: How does it handle node failures, late data, schema drift, replays?
4. OPERATIONAL CONCERNS: Cost, monitoring, deployment, on-call burden, vendor lock-in
5. ALTERNATIVES: Other valid approaches the solver didn't consider
6. ISSUES FOUND: List specific gaps with severity (critical/major/minor)

Do NOT discuss Big-O time/space complexity — it does not apply to system design answers.
Be specific and precise. This is for an interview context.`,

  optimizer: `You are a principal data engineer producing a FINAL ANSWER based on the validation feedback.

Your response MUST include these exact sections:

## FINAL ANSWER
[Refined, complete answer — address ALL issues from validation. Do NOT include code. Do NOT include Big-O complexity.]

## KEY TRADE-OFFS
[The main trade-offs of the chosen approach with brief explanation of each]

## ALTERNATIVES CONSIDERED
[Other valid approaches and why you didn't pick them]

## INTERVIEW TIPS
[2-3 key points to mention in an interview to impress the interviewer]

Do not skip any section. Do not include code or Big-O complexity.`,
} as const;

type AgentId = AgentType;

function getAgentPrompt(id: AgentId, mode: Mode): string {
  if (id === "reader") return READER_PROMPT;
  const set = mode === "code" ? CODE_PROMPTS : CONCEPT_PROMPTS;
  return set[id];
}

interface OpenRouterMessage {
  role: "system" | "user";
  content: string;
}

interface OpenRouterUsage {
  prompt: number;
  completion: number;
  total: number;
}

interface OpenRouterStreamResult {
  content: string;
  modelUsed: string;
  usage?: OpenRouterUsage;
  finishReason?: string;
}

interface OpenRouterStreamCallbacks {
  onModel: (model: string) => void;
  onDelta: (text: string) => void;
}

// Stream a chat completion from OpenRouter. Calls onDelta for each content
// fragment as it arrives, and onModel once we know which model actually ran
// (after failover resolves). Returns the accumulated content + usage + finish
// reason once the stream is fully drained.
async function streamOpenRouter(
  apiKey: string,
  models: string[],
  messages: OpenRouterMessage[],
  maxTokens: number,
  signal: AbortSignal,
  referer: string,
  title: string,
  callbacks: OpenRouterStreamCallbacks
): Promise<OpenRouterStreamResult> {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
      "HTTP-Referer": referer,
      "X-Title": title,
    },
    body: JSON.stringify({
      models,
      messages,
      temperature: 0.3,
      max_tokens: maxTokens,
      route: "fallback",
      stream: true,
      stream_options: { include_usage: true },
    }),
    signal,
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error("OpenRouter rejected the API key. Check that it's valid.");
    }
    if (response.status === 429) {
      throw new Error("All configured models are rate limited. Try again shortly or add another fallback.");
    }
    if (response.status === 402) {
      throw new Error("OpenRouter reports insufficient credits. Top up at openrouter.ai/credits.");
    }
    if (response.status === 404) {
      const isFree = models[0].endsWith(":free");
      if (isFree) {
        throw new Error(
          `Free models require opting in. Open https://openrouter.ai/settings/privacy and enable "Free model publication", then retry. (Model: ${models[0]})`
        );
      }
      throw new Error(
        `Model not found on OpenRouter: ${models[0]}. The id may have changed — pick a different model in Settings.`
      );
    }
    throw new Error(`OpenRouter error: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("OpenRouter returned no response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let modelUsed: string | null = null;
  let usage: OpenRouterUsage | undefined;
  let finishReason: string | undefined;
  let modelEmitted = false;

  const handleEventBlock = (block: string) => {
    // Each SSE event is a chunk of lines; we only care about `data:` lines.
    for (const rawLine of block.split("\n")) {
      const line = rawLine.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;

      let json: {
        model?: string;
        choices?: Array<{
          delta?: { content?: string };
          finish_reason?: string | null;
        }>;
        usage?: {
          prompt_tokens?: number;
          completion_tokens?: number;
          total_tokens?: number;
        };
      };
      try {
        json = JSON.parse(payload);
      } catch {
        continue;
      }

      if (!modelEmitted && json.model) {
        modelUsed = json.model;
        modelEmitted = true;
        callbacks.onModel(json.model);
      }

      const delta = json.choices?.[0]?.delta?.content;
      if (typeof delta === "string" && delta.length > 0) {
        content += delta;
        callbacks.onDelta(delta);
      }

      const fr = json.choices?.[0]?.finish_reason;
      if (fr) finishReason = fr;

      if (json.usage) {
        usage = {
          prompt: json.usage.prompt_tokens ?? 0,
          completion: json.usage.completion_tokens ?? 0,
          total:
            json.usage.total_tokens ??
            (json.usage.prompt_tokens ?? 0) + (json.usage.completion_tokens ?? 0),
        };
      }
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line (\n\n).
      let sepIdx;
      while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        handleEventBlock(block);
      }
    }
    if (buffer.trim()) handleEventBlock(buffer);
  } finally {
    reader.releaseLock();
  }

  return {
    content,
    modelUsed: modelUsed ?? models[0],
    usage,
    finishReason,
  };
}

function encodeStreamEvent(
  agent: string,
  type: "start" | "chunk" | "end" | "error" | "model",
  payload?: {
    content?: string;
    error?: string;
    model?: string;
    usage?: OpenRouterUsage;
  }
): string {
  const event = {
    agent,
    type,
    ...(payload?.content !== undefined ? { content: payload.content } : {}),
    ...(payload?.error !== undefined ? { error: payload.error } : {}),
    ...(payload?.model !== undefined ? { model: payload.model } : {}),
    ...(payload?.usage !== undefined ? { usage: payload.usage } : {}),
  };
  return `data: ${JSON.stringify(event)}\n\n`;
}

function buildUserContent(
  id: AgentId,
  question: string,
  category: Category,
  prior: Partial<Record<AgentId, string>>
): string {
  switch (id) {
    case "reader":
      return `Question (category hint: ${category}):\n${question}`;
    case "solver":
      return `Question: ${question}\n\nAnalysis:\n${prior.reader ?? ""}`;
    case "validator":
      return `Original question: ${question}\n\nProposed solution:\n${prior.solver ?? ""}`;
    case "optimizer":
      return `Question: ${question}\n\nOriginal solution:\n${prior.solver ?? ""}\n\nValidation issues:\n${prior.validator ?? ""}`;
  }
}

function isValidOpenRouterKey(k: string): boolean {
  return /^sk-or-[\w-]{20,}$/.test(k);
}

function sanitizeModelId(id: unknown): string | null {
  if (typeof id !== "string") return null;
  const trimmed = id.trim();
  if (!trimmed) return null;
  if (trimmed.length > 120) return null;
  if (!/^[a-zA-Z0-9._/:-]+$/.test(trimmed)) return null;
  return trimmed;
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { question, category, apiKey, agentModels } = (body ?? {}) as {
    question?: unknown;
    category?: unknown;
    apiKey?: unknown;
    agentModels?: unknown;
  };

  if (typeof question !== "string" || !question.trim()) {
    return NextResponse.json({ error: "Missing 'question'" }, { status: 400 });
  }
  if (question.length > MAX_QUESTION_CHARS) {
    return NextResponse.json(
      { error: `Question exceeds ${MAX_QUESTION_CHARS} characters` },
      { status: 400 }
    );
  }
  if (typeof category !== "string" || !VALID_CATEGORIES.has(category as Category)) {
    return NextResponse.json({ error: "Invalid 'category'" }, { status: 400 });
  }
  const typedCategory = category as Category;
  const mode = getMode(typedCategory);

  const clientKey = typeof apiKey === "string" ? apiKey.trim() : "";
  const serverKey = process.env.OPENROUTER_API_KEY?.trim() ?? "";
  const effectiveKey = clientKey || serverKey;

  if (!effectiveKey) {
    return NextResponse.json(
      { error: "API key is required. Add an OpenRouter key in settings or set OPENROUTER_API_KEY." },
      { status: 400 }
    );
  }
  if (!isValidOpenRouterKey(effectiveKey)) {
    return NextResponse.json(
      { error: "API key format looks invalid. OpenRouter keys start with 'sk-or-'." },
      { status: 400 }
    );
  }

  // Build the per-agent model chain: user's primary, then 2 curated fallbacks
  // (deduped). Caller-supplied ids are sanitized; falls back to defaults if missing.
  const callerModels = (agentModels && typeof agentModels === "object"
    ? (agentModels as Record<string, unknown>)
    : {}) as Record<AgentType, unknown>;

  const resolvedChain = (agent: AgentType): string[] => {
    const primary = sanitizeModelId(callerModels[agent]) ?? DEFAULT_AGENT_MODELS[agent];
    const seen = new Set([primary]);
    const chain = [primary];
    for (const fb of DEFAULT_AGENT_FALLBACKS[agent]) {
      if (seen.has(fb)) continue;
      seen.add(fb);
      chain.push(fb);
    }
    return chain;
  };

  const referer = request.headers.get("origin") ?? "https://de-interview-helper.local";
  const title = "DE Interview Helper";

  const encoder = new TextEncoder();
  const abortController = new AbortController();
  request.signal.addEventListener("abort", () => abortController.abort());

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (chunk: string) => controller.enqueue(encoder.encode(chunk));
      const results: Partial<Record<AgentId, string>> = {};
      const agents: AgentId[] = ["reader", "solver", "validator", "optimizer"];

      try {
        for (const id of agents) {
          if (abortController.signal.aborted) break;

          send(encodeStreamEvent(id, "start"));

          try {
            const models = resolvedChain(id);
            const { content, usage } = await streamOpenRouter(
              effectiveKey,
              models,
              [
                { role: "system", content: getAgentPrompt(id, mode) },
                { role: "user", content: buildUserContent(id, question, typedCategory, results) },
              ],
              maxTokensFor(id, mode),
              abortController.signal,
              referer,
              title,
              {
                onModel: (model) => send(encodeStreamEvent(id, "model", { model })),
                onDelta: (text) => send(encodeStreamEvent(id, "chunk", { content: text })),
              }
            );

            results[id] = content;
            // Usage (and known finish_reason) arrives in the final stream chunk.
            // Piggyback usage on the `end` event so the client can update token
            // totals at the right moment.
            send(encodeStreamEvent(id, "end", { usage }));
          } catch (err) {
            const message = err instanceof Error ? err.message : "Unknown error";
            send(encodeStreamEvent(id, "error", { error: message }));
            break;
          }
        }
      } finally {
        controller.close();
      }
    },
    cancel() {
      abortController.abort();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
