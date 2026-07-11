# claude-projects

A collection of data engineering and AI projects built while exploring Claude, Claude Code, and the Anthropic API.

## Data pipelines

| Project | What it does |
| --- | --- |
| [orders-pipeline](orders-pipeline/) | Medallion-architecture pipeline (bronze/silver/gold) with a schema-drift generator, DuckDB warehouse, Airflow orchestration, and data-quality quarantining. |
| [weather-india-pipeline](weather-india-pipeline/) | Airflow ELT pulling Open-Meteo weather for 51 Indian cities into DuckDB using a landing-zone pattern. |
| [indian-markets-pipeline](indian-markets-pipeline/) | NIFTY-500 market data pipeline with a 20-year backfill, schema registry, Airflow DAGs, and a Streamlit dashboard. |
| [agentic-data-pipeline](agentic-data-pipeline/) | An LLM-driven agent that plans and executes data pipeline steps against DuckDB. |
| [pet-friendly-india](pet-friendly-india/) | Aggregates pet-friendly places from web data, with LLM evidence extraction from reviews. |

## Snowflake / Cortex

| Project | What it does |
| --- | --- |
| [snowflake-cortex-skills](snowflake-cortex-skills/) | Custom Claude Code commands and Python examples for Snowflake Cortex. |
| [snowflake-nl-sql-comparator](snowflake-nl-sql-comparator/) | Streamlit app comparing natural-language-to-SQL output from Claude against Snowflake Cortex Analyst. |

## Claude & agents

| Project | What it does |
| --- | --- |
| [claude-features-demo](claude-features-demo/) | Demonstrates Claude Code hooks, custom slash commands, subagents, and API usage. |
| [cli_project](cli_project/) | A CLI agent built on the Anthropic API, including an MCP client and server. |
| [interview_agent](interview_agent/) / [interview_agent_web](interview_agent_web/) | An interview-practice assistant, as a script and as a Next.js web app. |
| [law-school-guide](law-school-guide/) | Next.js guide app. |
| [weekly-data-digest](weekly-data-digest/) | Generates and emails a weekly data digest using Claude. |

## Running these locally

Most projects follow the same shape:

```bash
cd <project>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # or: pip install -e .
cp .env.example .env                 # then fill in your own credentials
```

Virtual environments, `node_modules`, build caches, and DuckDB/SQLite warehouse files are intentionally not tracked — the pipelines regenerate the data. No credentials are committed; every project that needs them ships a `.env.example` template for you to fill in.
