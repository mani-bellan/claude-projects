# DE Interview Helper

A Next.js web app that helps you prepare for data engineering interviews using a four-agent pipeline. You bring your own [OpenRouter](https://openrouter.ai) key and choose a model per agent — Reader, Solver, Validator, Optimizer.

Built with Next.js 15 (App Router), React 18, TypeScript, Tailwind CSS, and Zustand. Streams agent output via SSE. Deploys clean to Vercel.

## Features

- **Four-agent pipeline** — Reader (classifies), Solver (drafts), Validator (reviews), Optimizer (finalises). Each agent's output streams in real time.
- **Per-agent model selection** — pick a small/fast model for Reader/Validator and a strong model for Solver/Optimizer. Curated catalog of free + paid OpenRouter models, plus a custom-ID escape hatch.
- **Auto-failover** — if your primary model is rate-limited or unavailable, OpenRouter transparently tries a curated fallback in the same request (`route: "fallback"`). The UI shows a "fallback" chip when this happens.
- **Token usage visible** — each agent card shows the actual model used and tokens (prompt / completion). A compact bar below the grid totals usage across all agents.
- **Category-aware output** — `coding` / `sql` produce code + Big-O complexity; `architecture` / `design` / `streaming` / `general` produce conceptual answers with trade-offs and alternatives (no code, no complexity).
- **Public question bank** — auto-loaded examples from four public GitHub sources (andkret/Cookbook + Devinterview-io repos), merged with bundled defaults and shown in the sidebar. Cached server-side for 1 hour.
- **Export** — save the final answer + analysis as Markdown.
- **History** — last 20 runs kept locally.

## Prerequisites

- Node.js 18.18+ and npm
- An OpenRouter API key — free signup at [openrouter.ai/keys](https://openrouter.ai/keys). Free-tier models cost $0.

## Setup

```bash
cd interview_agent_web
npm install
cp .env.local.example .env.local   # optional — only needed if you want a server-side fallback key
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). On first visit, the Settings modal opens — paste your `sk-or-v1-…` key and Save.

The key is stored only in your browser's `localStorage`. It is sent to `/api/swarm` per request, never embedded in the client bundle.

## Environment variables

| Variable | Required? | What it does |
|---|---|---|
| `OPENROUTER_API_KEY` | optional | Server-side fallback key. Used only if the request body has no `apiKey`. Don't prefix with `NEXT_PUBLIC_` — that would leak the secret into the browser bundle. |

There are no required env vars for the BYOK flow.

## Usage

1. Click **Set API key** (top right). Paste your OpenRouter key and optionally pick different models per agent.
2. Pick a **Category** in the left sidebar (or accept "General"). The Examples panel auto-loads questions from public sources merged with bundled defaults — click any to populate the input.
3. Type or paste a question (≤ 2000 chars) and click **Analyze question**.
4. Watch the four agents work in order. Each card shows status, model used, and tokens as it completes.
5. When the Optimizer finishes, the Results panel appears with tabs:
   - **Final solution / Final answer** — the polished output.
   - **Complexity** (code mode only) — time + space Big-O.
   - **Trade-offs** (concept mode only) — key trade-offs + alternatives considered.
   - **Interview tips** — 2–3 talking points.
6. Click **Save markdown** to download.

## Architecture

```
src/
├── app/
│   ├── api/
│   │   ├── swarm/route.ts      # SSE-streamed multi-agent pipeline → OpenRouter
│   │   └── questions/route.ts  # Fetches + parses public question banks (1h ISR)
│   ├── layout.tsx              # Root layout, fonts (Inter + JetBrains Mono)
│   ├── page.tsx                # Main UI
│   └── globals.css
├── components/
│   ├── Header.tsx              # Brand + pipeline indicator
│   ├── QuestionInput.tsx
│   ├── CategorySelector.tsx
│   ├── ExamplesList.tsx        # Bundled + remote examples with refresh
│   ├── AgentCard.tsx           # Status, model, tokens, fallback chip
│   ├── UsageBar.tsx            # Per-agent + total token usage
│   ├── ResultsPanel.tsx        # Mode-aware tabs (code vs concept)
│   ├── ApiKeyModal.tsx         # Settings: key + per-agent model pickers
│   ├── ErrorBanner.tsx
│   └── icons.tsx               # Inline SVG icon set
├── hooks/
│   ├── useSwarmStream.ts       # SSE consumer → store updates
│   └── useApiKeyModal.ts
├── lib/
│   ├── api.ts                  # Client → /api/swarm
│   ├── constants.ts            # Categories + mode mapping
│   ├── models.ts               # Curated OpenRouter catalog + defaults + fallbacks
│   └── utils.ts                # Section extraction, markdown export
├── store/index.ts              # Zustand store with persistence
└── types/index.ts
```

### How the pipeline works

1. Client posts `{ question, category, apiKey, agentModels }` to `/api/swarm`.
2. Route validates input, derives `mode` from category (`code` vs `concept`), and resolves a `[primary, …fallbacks]` chain per agent.
3. For each agent (sequentially), it POSTs to OpenRouter's `/chat/completions` with `{ models: chain, route: "fallback", … }`. OpenRouter handles failover internally.
4. Each agent's full response is split into lines and streamed back as SSE events:
   - `{type: "start"}` when an agent begins.
   - `{type: "model", model, usage}` once the upstream call returns — includes the actual model used and token counts.
   - `{type: "chunk", content}` for each line of output.
   - `{type: "end"}` when the agent completes.
   - `{type: "error", error}` on failure (aborts remaining agents).
5. The hook updates the Zustand store; React rerenders the cards and usage bar.

### Mode mapping

| Category | Mode | Agents produce |
|---|---|---|
| `coding`, `sql` | code | Code/query + time/space Big-O |
| `architecture`, `design`, `streaming`, `general` | concept | Text answer + trade-offs + alternatives. **No code, no Big-O.** |

### Model selection

Defaults are all free-tier:

| Agent | Default | Why |
|---|---|---|
| Reader | `meta-llama/llama-3.2-3b-instruct:free` | Classification — tiny model is enough |
| Solver | `meta-llama/llama-3.3-70b-instruct:free` | Main reasoning workhorse |
| Validator | `google/gemma-4-31b-it:free` | Review pass — mid-size is fine |
| Optimizer | `meta-llama/llama-3.3-70b-instruct:free` | Final-answer quality matters |

Fallback chains are kept all-free so a free-tier user doesn't get a surprise paid charge if their primary fails over.

### Public question sources

`/api/questions` fetches and parses four public GitHub markdown files in parallel:

- [andkret/Cookbook · 08-InterviewQuestions.md](https://github.com/andkret/Cookbook/blob/master/sections/08-InterviewQuestions.md) — multi-section, mapped to categories
- [Devinterview-io/data-engineer-interview-questions](https://github.com/Devinterview-io/data-engineer-interview-questions)
- [Devinterview-io/sql-interview-questions](https://github.com/Devinterview-io/sql-interview-questions)
- [Devinterview-io/apache-spark-interview-questions](https://github.com/Devinterview-io/apache-spark-interview-questions)

Results are deduped, capped at 30 per category, cached server-side for 1 hour (`revalidate: 3600`). Streaming-flavoured questions are auto-routed to the `streaming` category regardless of source.

## Scripts

```bash
npm run dev          # dev server
npm run build        # production build
npm start            # serve the production build
npm run lint         # Next/ESLint
npm run type-check   # tsc --noEmit
```

## Deployment to Vercel

1. Push to GitHub.
2. Import the repo at [vercel.com/new](https://vercel.com/new). Framework: Next.js.
3. (Optional) Add `OPENROUTER_API_KEY` under **Settings → Environment Variables** if you want a server-side fallback key. **Do not** add a `NEXT_PUBLIC_*` variant.
4. Deploy.

Function timeouts: `/api/swarm` declares `maxDuration = 300` to accommodate 4 sequential LLM calls. Make sure your Vercel plan supports it.

## Security notes

- API keys never enter the client bundle. BYOK flow stores keys in `localStorage` and posts them per request to `/api/swarm`.
- Input is validated server-side: question length capped at 2000 chars, category whitelist, OpenRouter key format check before any upstream call.
- The route never mutates `process.env` (avoids cross-request key contamination on warm serverless instances).
- Upstream auth/rate-limit error bodies are not echoed back — only generic messages.
- Security response headers set in `next.config.js`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
- `npm audit` reports 0 vulnerabilities (prod + dev) at the time of writing.

## Troubleshooting

**"API key is required"** — open Settings, paste an OpenRouter key starting with `sk-or-v1-…`.

**"Model not found on OpenRouter: …"** — the model ID in your saved settings no longer exists on OpenRouter (catalog changes over time). Open Settings → either pick another from the dropdown for that agent or click **Reset to defaults**.

**"All configured models are rate limited"** — your primary and all fallbacks hit 429 simultaneously. Wait a minute or pick a paid model for that agent.

**"OpenRouter reports insufficient credits"** — you picked a paid model but your OpenRouter account has $0. Top up at [openrouter.ai/credits](https://openrouter.ai/credits) or switch to a `:free` model.

**Examples sidebar empty for a category** — the bundled questions are minimal for some categories; the public sources (Cookbook + Devinterview) supplement. If a category still looks sparse it's because the upstream repos don't have many questions for it (especially `general`).

**Build error about a stale `.next` page** — `rm -rf .next && npm run build`. Common after rapid rebuilds in Next 15.

## Tech stack

- **Next.js 15.5** (App Router)
- **React 18.3** + **TypeScript 5.6**
- **Tailwind CSS 3.4**
- **Zustand 4.5** for state
- Inline SVG icons (no icon library dep)
- **Inter** + **JetBrains Mono** via `next/font/google`

## License

MIT.
