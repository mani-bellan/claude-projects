Generate Snowflake SQL and Python code for vector embeddings and similarity search using Snowflake Cortex EMBED_TEXT functions, based on the use-case described in $ARGUMENTS.

Produce three parts:

### Part 1 — Embed a corpus

SQL to embed every row of a text column and store vectors in a VECTOR column:

```sql
-- Choose 768 or 1024 dimensions based on use-case
ALTER TABLE my_table ADD COLUMN embedding VECTOR(FLOAT, 768);

UPDATE my_table
SET embedding = SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', text_column);
```

Recommend the right model:
- `snowflake-arctic-embed-m` — general-purpose, fast
- `snowflake-arctic-embed-l` — higher accuracy, larger
- `e5-base-v2`, `nv-embed-qa-4` — domain-specific

### Part 2 — Similarity search SQL

SQL to find the top-K most similar rows to a query string using `VECTOR_COSINE_SIMILARITY`:

```sql
SELECT id, text_column,
       VECTOR_COSINE_SIMILARITY(embedding,
           SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', :query)
       ) AS score
FROM my_table
ORDER BY score DESC
LIMIT 10;
```

### Part 3 — Python (Snowpark) end-to-end

A Python function that:
1. Accepts a query string
2. Calls the embed + similarity search SQL via Snowpark
3. Returns a pandas DataFrame of results with scores

End with a note on indexing: Snowflake does not yet have an ANN index — for >10M rows, pre-filter with metadata before the vector scan.
