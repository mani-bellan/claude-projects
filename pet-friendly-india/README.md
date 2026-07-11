# Pet-Friendly India

A trusted aggregator of pet-friendly places (cafes, restaurants, resorts, stays) across India,
starting with Bangalore. Trust comes from **multi-source corroboration**: every listing's
pet policy is backed by dated, attributed evidence from independent sources, combined into
a confidence score that decays over time. The web app shows users *why* a place is labelled
pet-friendly — sources, dates, and claims — not just a badge.

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │                INGESTION                    │
                │  Google Places API (New): locality x        │
                │  category text searches per city            │
                └──────────────────┬──────────────────────────┘
                                   ▼
        ┌──────────────────────────┴──────────────────────────┐
        │                                                     │
┌───────▼─────────────────────┐   ┌─────────────────────────▼─────┐
│  VENUE WEBSITES (tier 1)    │   │  REVIEW TEXT (tier 3)         │
│  fetch site + policy pages, │   │  Batches API + structured     │
│  keyword pre-filter, then   │   │  outputs: review text →       │
│  Claude extracts the stated │   │  PetEvidence (polarity, pet   │
│  pet policy                 │   │  sizes, seating, fees, ...)   │
└───────────┬─────────────────┘   └───────────┬───────────────────┘
            └──────────────┬──────────────────┘
                           ▼
            ┌─────────────────────────────────┐
            │       CONFIDENCE SCORING        │
            │  tier weights x recency decay   │
            │  x corroboration bonus          │
            │  − negative-evidence penalty    │
            │  → verified / likely/unverified │
            └──────────────┬──────────────────┘
                           ▼
            ┌─────────────────────────────────┐
            │   PUBLISH read-only snapshot    │
            │   web/public/data/places.json  │
            └──────────────┬──────────────────┘
                           ▼
            ┌─────────────────────────────────┐
            │   Next.js app (web/)            │
            │   search, filters, near-me,     │
            │   badges + evidence provenance  │
            └─────────────────────────────────┘
```

The web app is a thin read layer — all intelligence lives in the pipeline, which owns
every write. The app renders the published snapshot; nothing queries the DB live.

## Data model (DuckDB + spatial extension)

| Table                | Purpose |
|----------------------|---------|
| `places`             | One row per venue, anchored to a Google Place ID |
| `evidence`           | One row per pet-policy claim: source, tier, polarity, date, URL, extracted fields, raw text |
| `pending_reviews`    | Raw review text queue (0 = pending, 1 = done, 2 = in-flight batch) |
| `website_checks`     | Website fetch log; drives the 90-day re-verification window |
| `extraction_batches` | Anthropic Message Batches submitted for extraction |
| `scores`             | Derived confidence + label per place |

Evidence tiers (lower = more trusted): **0** verified user visit reports (future) ·
**1** venue's own statement (website, Google `allowsDogs`) · **2** booking-site pet
filters (future) · **3** review-text mentions.

Labels: **verified** ≥ 0.75 · **likely** ≥ 0.40 · **unverified** below. A single source
caps out around 0.65 by design — only independent corroboration earns "verified", and a
recent "we were turned away" outweighs older positive signals.

DuckDB notes: single-writer (don't run two pipeline commands at once; use
`duckdb -readonly` for ad-hoc queries) and `ST_Distance_Sphere` expects
`ST_Point(lat, lng)` axis order.

## Setup

```bash
cd pet-friendly-india
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your API keys

cd web && npm install  # the web app (Node 18.18+)
```

API keys (`.env`):

- `GOOGLE_MAPS_API_KEY` — Places API (New) in Google Cloud Console. The field mask
  includes `allowsDogs`/`reviews`, so calls land in the Enterprise SKU: 1,000 free
  calls/month, then ~$20/1K. Set a budget alert.
- `ANTHROPIC_API_KEY` — Claude extraction. Default model is Haiku 4.5
  (spot-checked at 99% agreement with Opus on this task); override with `--model`.

The pipeline runs end-to-end without keys using bundled sample data
(`ingest --sample`) and a keyword-extraction fallback.

## One-command ETL

`pipeline/etl.py` chains the whole flow — ingest → websites → extract (Batches API,
polled until results land) → score → publish — so a city run is a single command:

```bash
python -m pipeline.etl --city Mysore             # full run; polls the batch (~30-60 min)
python -m pipeline.etl --city Mysore --no-wait   # submit the batch and exit...
python -m pipeline.etl --resume                  # ...then finish later: collect, score, publish
python -m pipeline.etl --sample                  # offline demo, no API keys needed
python -m pipeline.etl --city Mysore --sync      # small cities: synchronous, no batch wait
```

Useful flags: `--skip-websites`, `--limit N` (reviews), `--website-limit N`,
`--model`, `--poll-minutes` / `--max-wait-minutes`. Missing keys degrade gracefully
(no Google key → sample data; no Anthropic key → keyword extraction, websites skipped).
`--no-llm` guarantees zero Anthropic spend even when the key is set — websites skipped,
keyword-only extraction (cruder evidence: tier-3 only, so labels rarely exceed "likely").
The individual stage commands below still work for step-by-step runs.

## Adding a city — the runbook

**Step 0 (optional, once per metro):** for deep coverage, add the city's neighbourhoods
to `CITY_LOCALITIES` in `pipeline/ingest.py` (Bangalore fans out to 26 locality x
category queries). Small towns can skip this — unknown cities fall back to 4 broad
queries automatically.

```bash
# 1. Discover places (seconds; 4-26 Google Enterprise calls)
python -m pipeline.run ingest --city Mysore

# 2. Tier-1 venue-website checks (minutes; keyword pre-filter keeps Claude cost tiny)
python -m pipeline.run websites

# 3. Submit review extraction via the Batches API (50% cheaper, no rate limits)
python -m pipeline.run extract --batch

# 4. ~30-60 min later: collect results (failures auto-return to the pending pool)
python -m pipeline.run extract --collect

# 5. Rescore and regenerate the web app's data
python -m pipeline.run score
python -m pipeline.run publish
```

No web-app code changes needed: the city dropdown populates from the data, and
`npm run dev` shows it on refresh (a production deploy needs a rebuild — the page is
statically generated).

Multiple cities can be batched in one sitting: run steps 1-2 per city, then one
`--batch` submits all pending reviews across cities together.

**Approximate cost per city** (Haiku, batched): small town ~$0.30 · metro ~$1.20,
plus 4-26 of your 1,000 free monthly Google calls.

**Refreshing existing cities:** the same runbook re-run. Ingest is idempotent
(Place-ID dedupe, only new reviews queue for extraction) and `websites` automatically
rechecks sites older than 90 days.

## Other commands

```bash
python -m pipeline.run report [-v]                  # ranked listing + evidence detail
python -m pipeline.run report --label verified      # filter by label
python -m pipeline.run nearby --lat 12.97 --lng 77.64 --radius-km 10 [--label likely]
python -m pipeline.run extract --limit 20           # small synchronous run (no batch)
```

## Web app

```bash
cd web && npm run dev    # http://localhost:3000
```

Search, type/city filters, "with pet evidence only" toggle, geolocation distance sort,
trust badges, policy chips (seating / sizes / fees / amenities), and an expandable
"Why we believe this" section per place showing every evidence item with source and date.

## Status & roadmap

- [x] Pipeline: ingest → websites → extract → score → publish (+ report / nearby)
- [x] City-level ingestion with locality fan-out (Bangalore: 337 places)
- [x] Tier-1 venue-website source with keyword pre-filter
- [x] Batches API extraction (50% cost, structured outputs, auto-retry of failures)
- [x] Next.js app reading the published snapshot
- [ ] Re-verification command (surface stale evidence, re-queue checks)
- [ ] Booking-site stays ingestion for getaway corridors (Coorg, Goa, Ooty…)
- [ ] Deploy web app + automated refresh schedule
- [ ] User feedback loop: "Visited with my pet ✓ / Turned away ✗" as tier-0 evidence
