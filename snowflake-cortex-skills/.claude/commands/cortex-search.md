Scaffold a complete Cortex Search Service setup for the table or use-case described in $ARGUMENTS.

Produce all three stages:

### Stage 1 — Create the Cortex Search Service

Generate the `CREATE CORTEX SEARCH SERVICE` DDL:
- Pick appropriate `ON` column(s) for full-text + vector indexing
- Set `WAREHOUSE`, `TARGET_LAG`, and `EMBEDDING_MODEL`
- Include `ATTRIBUTES` for metadata filtering fields

```sql
-- Example shape (fill in for the user's table)
CREATE OR REPLACE CORTEX SEARCH SERVICE my_search_service
  ON text_column
  ATTRIBUTES category, created_at
  WAREHOUSE = my_wh
  TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-m'
AS
  SELECT text_column, category, created_at
  FROM my_database.my_schema.my_table;
```

### Stage 2 — Python query snippet (Snowpark)

Generate a Python function using `snowflake.core.cortex.CortexSearchService` (or `snowflake.snowpark` REST) that:
- Accepts a query string and optional filter dict
- Returns top-N results with scores

### Stage 3 — Metadata filter examples

Show three `filter` examples in JSON: exact match, range filter, and combined AND filter.

End with a note on `TARGET_LAG` trade-offs (freshness vs. cost).
