Generate an optimized Snowflake SQL query from the plain-English description in $ARGUMENTS.

Follow these rules when writing the SQL:

1. **Syntax** — use Snowflake-specific syntax: `QUALIFY`, `FLATTEN`, `LATERAL FLATTEN`, `TRY_CAST`, `IFF`, `ZEROIFNULL`, `OBJECT_CONSTRUCT`, `ARRAY_AGG`, `LISTAGG` where appropriate.
2. **Fully-qualified names** — write every table reference as `DATABASE.SCHEMA.TABLE`.
3. **Clustering / partitioning hints** — if the query filters on a high-cardinality column, add a comment `-- consider clustering on <col>`.
4. **Date handling** — prefer `DATEADD`, `DATEDIFF`, `DATE_TRUNC`, `TO_DATE` over ANSI alternatives.
5. **Performance** — avoid `SELECT *`; use CTEs for readability; push filters early; use `LIMIT` during development.
6. **Snowflake Time Travel** — mention `AT (TIMESTAMP => ...)` if the request involves historical data.
7. **Semi-structured data** — use `:` path notation and `$1:field::type` casting for VARIANT columns.

Output format:
- A fenced ```sql block containing the final query
- Bullet-point explanation of key choices
- Any recommended virtual warehouse size (X-Small → 4X-Large) for the query volume described
