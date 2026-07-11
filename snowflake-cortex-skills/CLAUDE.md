# Snowflake & Cortex Skills

A project of Claude Code custom commands (skills), hooks, and Python examples covering Snowflake SQL and Snowflake Cortex AI capabilities.

## Setup

```bash
cp .env.example .env
# Fill in your Snowflake credentials in .env
uv sync  # or: pip install -e .
```

## Project Layout

| Path | Purpose |
|---|---|
| `.claude/settings.json` | Hooks configuration |
| `.claude/commands/` | Custom slash commands for Snowflake & Cortex workflows |
| `hooks/` | Shell scripts invoked by hooks |
| `examples/` | Standalone Python scripts — one per Cortex / Snowflake feature |
| `semantic_models/` | YAML semantic model files for Cortex Analyst |

## Custom Commands

Open Claude Code in this directory and type:

| Command | What it does |
|---|---|
| `/snowflake-query` | Generate optimized Snowflake SQL from a plain-English description |
| `/snowflake-optimize` | Review and optimize an existing Snowflake query |
| `/cortex-complete` | Draft a SNOWFLAKE.CORTEX.COMPLETE() SQL call from a prompt |
| `/cortex-analyze` | Apply Cortex functions (sentiment, summarize, translate) to a column |
| `/cortex-search` | Scaffold a Cortex Search Service setup and query pattern |
| `/cortex-analyst` | Build a Cortex Analyst semantic model YAML for a table |
| `/cortex-embed` | Generate EMBED_TEXT SQL for vector similarity search |

## Running Examples

```bash
# Snowflake connection test
python examples/01_connection.py

# Cortex LLM completion
python examples/02_cortex_complete.py

# Sentiment analysis
python examples/03_cortex_sentiment.py

# Summarization
python examples/04_cortex_summarize.py

# Translation
python examples/05_cortex_translate.py

# Embeddings + vector search
python examples/06_cortex_embed.py

# Cortex Search Service
python examples/07_cortex_search.py

# Cortex Analyst — NL to SQL
python examples/08_cortex_analyst.py

# Cortex Fine-tuning
python examples/09_cortex_finetuning.py

# Snowpark ML
python examples/10_snowpark_ml.py
```

## Cortex LLM Functions Quick Reference

| SQL Function | Purpose |
|---|---|
| `SNOWFLAKE.CORTEX.COMPLETE(model, prompt)` | LLM text generation |
| `SNOWFLAKE.CORTEX.SENTIMENT(text)` | Returns score -1..1 |
| `SNOWFLAKE.CORTEX.SUMMARIZE(text)` | One-paragraph summary |
| `SNOWFLAKE.CORTEX.TRANSLATE(text, src, tgt)` | Language translation |
| `SNOWFLAKE.CORTEX.CLASSIFY_TEXT(text, labels)` | Zero-shot classification |
| `SNOWFLAKE.CORTEX.EXTRACT_ANSWER(context, question)` | QA extraction |
| `SNOWFLAKE.CORTEX.EMBED_TEXT_768(model, text)` | 768-dim embedding vector |
| `SNOWFLAKE.CORTEX.EMBED_TEXT_1024(model, text)` | 1024-dim embedding vector |

## Supported Cortex Models

`snowflake-arctic`, `mistral-large`, `mistral-large2`, `llama3-70b`, `llama3.1-70b`, `llama3.1-405b`, `mixtral-8x7b`, `gemma-7b`, `reka-flash`, `reka-core`

## Conventions

- Python 3.11+, managed with `uv`
- All examples are standalone — no shared state
- Credentials loaded from `.env` via `python-dotenv`
- SQL in examples uses fully-qualified `DATABASE.SCHEMA.TABLE` notation
