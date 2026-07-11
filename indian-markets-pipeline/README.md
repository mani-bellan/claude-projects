# Indian Markets Pipeline

Schema-aware pipeline that pulls 20 years of Indian stock + mutual fund data into a local DuckDB,
orchestrated by Airflow, with a Streamlit dashboard recommending long-term picks for first-time investors.

> Educational tool. Not financial advice. Backtests are not predictions.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow (Docker, LocalExecutor) |
| Warehouse | DuckDB (local file) |
| Extraction | yfinance (NSE), mfapi.in (AMFI NAVs) |
| Transform | Polars |
| Schema mgmt | Custom registry + evolution engine |
| Dashboard | Streamlit + Plotly |

## Layout

```
indian-markets-pipeline/
├── src/markets_pipeline/   # library code (extractors, schema, loaders)
├── airflow/dags/           # Airflow DAGs
├── dashboard/              # Streamlit UI
├── tests/                  # pytest
└── data/                   # DuckDB file + schema registry (gitignored)
```

## Quick start

```bash
make install                # install Python deps
make test                   # run schema-engine tests
make airflow-up             # start Airflow on :8080 (admin/admin)
make backfill               # one-time 20-year load
make dashboard              # launch Streamlit on :8501
```

## Schema awareness

Every load passes through `SchemaEvolution.reconcile(table, df, primary_key)`:

| Change | Action |
|---|---|
| New table | `CREATE TABLE`, register |
| New column | `ALTER TABLE ADD COLUMN`, register |
| Widening type (e.g. `INTEGER → BIGINT`) | `ALTER TABLE ALTER COLUMN`, register |
| Narrowing or incompatible type | Reject, write to `_rejects_<table>`, alert |

Every change — applied or rejected — is logged to `_schema_evolution_log`.

## Disclaimer

Built for learning. Past performance ≠ future returns. Consult a SEBI-registered advisor for actual investment decisions.
