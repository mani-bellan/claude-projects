Review and optimize the Snowflake SQL query provided in $ARGUMENTS (or the selected code in the editor if no argument is given).

Produce a structured optimization report covering:

1. **Query structure** — unnecessary sub-queries, missing CTEs, Cartesian joins, missing aliases
2. **Predicate pushdown** — filters that should move earlier, redundant WHERE clauses
3. **Clustering & micro-partition pruning** — which columns to cluster on; does the query benefit from existing cluster keys?
4. **Warehouse sizing** — recommended warehouse size (X-Small → 4X-Large) and multi-cluster settings for this query's concurrency
5. **Caching opportunities** — result cache eligibility; materialized view candidates; dynamic tables for incremental refresh
6. **Snowflake-specific rewrites** — replace ANSI constructs with Snowflake native equivalents (`QUALIFY` instead of a sub-query window filter, `FLATTEN` for array unnesting, etc.)
7. **Cost estimate** — rough credits consumed at the recommended warehouse size

Format each finding as:
- **Severity** (high / medium / low)
- **Issue** and **Rewritten SQL or fix**

End with the fully rewritten query in a fenced ```sql block.
