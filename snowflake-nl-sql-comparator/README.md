# Snowflake NL→SQL Comparator

Ask a question in plain English. Three modes, selectable in the sidebar:

- **Compare: Claude vs. Cortex Analyst** — both systems answer the same question from the same semantic-model YAML. **Claude (Sonnet 4.6)** gets the YAML as a cached system prompt and generates SQL via tool use; **Cortex Analyst** gets the stage path and the REST API returns SQL. The same code executes both, row sets get diffed, you vote, and everything is logged to a Snowflake table — a labeled eval dataset over time.
- **Claude only: semantic model** — skip Cortex Analyst entirely. The YAML can come from a local file (`SEMANTIC_MODEL_LOCAL_PATH`) instead of a stage.
- **Claude only: introspect schema** — zero YAML setup. The app reads `INFORMATION_SCHEMA` for your configured database/schema (tables, columns, types, comments, plus a few sample values per column) and feeds that to Claude as the schema context. Great for exploring any schema instantly; a curated semantic model still wins on accuracy because column names alone don't carry business definitions.

## What you need

1. A Snowflake account with a warehouse, database, and schema you can write to.
2. An [Anthropic API key](https://console.anthropic.com/).
3. **For Compare mode only:** a semantic-model YAML uploaded to a Snowflake stage. The app downloads it at startup and uses it as the single source of truth — Claude reads it for the system prompt, Cortex Analyst reads it from the stage path. Format must follow the [Snowflake semantic-model spec](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec).

   Verify yours exists: `LIST @MY_DB.MY_SCHEMA.MY_STAGE;`

   Introspect mode needs none of this — just the Snowflake credentials.

## Setup

```bash
# 1. Install (uv recommended, pip works)
uv sync   # or: pip install -e .

# 2. Configure credentials
cp .env.example .env
# Edit .env. The two critical entries:
#   SNOWFLAKE_ACCOUNT=...                          (account locator, no URL)
#   SEMANTIC_MODEL_STAGE_PATH=@DB.SCHEMA.STAGE/file.yaml   (your existing YAML)

# 3. Run
uv run streamlit run app.py
```

Open <http://localhost:8501> and ask away.

### Updating the semantic model

The app downloads the YAML once at startup (cached via `@st.cache_resource`). When you change the YAML on the stage, **restart Streamlit** (`Ctrl+C` and re-run) to pick up the new version.

## How it works

```
Startup (per sidebar mode)
   │
   ├─ Compare ──────────▶ GET semantic model YAML from @DB.SCHEMA.STAGE/file.yaml
   │                        ├──▶ local copy: feeds Claude's prompt-cached system prompt
   │                        └──▶ stage path: passed to Cortex Analyst REST call
   │
   ├─ Claude/semantic ──▶ local YAML (SEMANTIC_MODEL_LOCAL_PATH) or stage download
   │                        └──▶ Claude's system prompt; Cortex skipped
   │
   └─ Claude/introspect ▶ INFORMATION_SCHEMA.TABLES + .COLUMNS + sample rows
                            └──▶ rendered as YAML → Claude's system prompt; Cortex skipped
   ▼
Per question:
   │
   ├──▶ Claude (anthropic SDK)
   │     ├─ system: semantic-model YAML (prompt-cached)
   │     ├─ tool:   execute_snowflake_sql
   │     ├─ tool:   describe_table
   │     └─ loop until end_turn or 6 turns → final SQL + result
   │
   └──▶ Cortex Analyst (REST API)
         ├─ POST /api/v2/cortex/analyst/message
         ├─ parse JSON: message.content[type=sql].statement
         └─ execute the returned SQL via snowflake_client → result

           ▼
      Compare row sets (column- and order-independent)
           ▼
      Log to {database}.{schema}.NL_SQL_COMPARATOR_RUNS
```

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit UI entry point |
| `src/config.py` | `.env` → typed `Config` dataclass |
| `src/snowflake_client.py` | Connection, query execution, JWT minting, stage download |
| `src/semantic_loader.py` | Loads YAML; renders Claude system prompt |
| `src/introspector.py` | Builds schema context from `INFORMATION_SCHEMA` (introspect mode) |
| `src/claude_runner.py` | Agentic loop: Claude → tool calls → SQL execution → answer |
| `src/cortex_runner.py` | Calls `/api/v2/cortex/analyst/message`; returned SQL is executed by `snowflake_client` |
| `src/comparator.py` | Row-set equality, column-diff, count diffs |
| `src/logger.py` | Persists every run to a Snowflake table for evals |
| `semantic_models/sales.yaml` | Reference template (not loaded at runtime — the app downloads from your stage) |

## Swapping in a different semantic model

Update the YAML on your Snowflake stage (`PUT file://newmodel.yaml @MY_DB.MY_SCHEMA.MY_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE`) — or change `SEMANTIC_MODEL_STAGE_PATH` to point at a different file. Restart Streamlit to pick up the change.

The richer your YAML (sample values, synonyms, verified queries), the better both runners perform. The `verified_queries` block doubles as few-shot examples for Claude. See the [Snowflake semantic-model spec](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec) for the full schema.

## What the comparison tells you

Both runners produce **SQL only** — the same code executes both queries against the same warehouse, so the comparison cleanly isolates SQL-generation quality (not execution overhead).

- **Rows match ✓** + similar latency → either system is fine; the YAML is doing the work.
- **Rows match ✓** but very different SQL → semantic model is the source of truth; SQL differences are cosmetic.
- **Rows match ✗** → one generator got it wrong (or the question was ambiguous). Diff the two SQL statements.
- **Claude faster + cheaper** → Claude is a viable substitute for this workload. Cortex Analyst is billed per Snowflake credit; Claude's is per-token and predictable.

## Run history table

Every run with a feedback vote gets logged. Query your eval dataset directly:

```sql
SELECT
    DATE_TRUNC('day', asked_at) AS day,
    COUNT(*)                    AS runs,
    SUM(IFF(rows_match, 1, 0))  AS matching,
    AVG(claude_elapsed_ms)      AS avg_claude_ms,
    AVG(cortex_elapsed_ms)      AS avg_cortex_ms,
    AVG(claude_input_tokens + claude_output_tokens) AS avg_claude_tokens
FROM nl_sql_comparator_runs
GROUP BY 1
ORDER BY 1 DESC;
```

## Cost notes

- **Claude** — prompt caching covers the YAML system prompt (~90% discount on cache hits). Sonnet 4.6: $3/M input, $15/M output. A 5K-token YAML + 200-token question is ~2¢ cold, ~0.3¢ cached.
- **Cortex Analyst** — billed per Snowflake credits for the NL→SQL call, plus warehouse compute for executing the returned query.

## Security

- Use a **read-only Snowflake role**. The app generates SELECT-only queries, but defense in depth: a role that can only `SELECT` keeps a misbehaving model from doing damage.
- All queries have a 60-second timeout (`STATEMENT_TIMEOUT_IN_SECONDS`) and the app caps results at 1000 rows.
- `.env` is in `.gitignore`. Never commit credentials.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing required env var X` | Check `.env` against `.env.example` |
| `HTTP 403` from Cortex Analyst | Token scope wrong — verify `GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <your_role>` is in place |
| `Snowflake GET returned no files for @...` | The path in `SEMANTIC_MODEL_STAGE_PATH` doesn't exist. Run `LIST @MY_DB.MY_SCHEMA.MY_STAGE;` to see what's there, or your role is missing `USAGE`/`READ` on the stage |
| Claude generates SQL referencing tables not in your warehouse | The YAML on the stage has placeholder `MY_DATABASE.MY_SCHEMA` — edit and re-upload |
| Both runners 0 rows | Tables in the semantic model are empty — point at real data |
| YAML downloaded but Cortex says "model not found" | Cortex Analyst couldn't read the stage file. Ensure the YAML is uncompressed (`PUT ... AUTO_COMPRESS=FALSE`) |
