"""
06_cortex_embed.py — Vector embeddings with SNOWFLAKE.CORTEX.EMBED_TEXT_768/1024

Demonstrates:
  - Generating embeddings for rows and storing in a VECTOR column
  - Cosine similarity search using VECTOR_COSINE_SIMILARITY
  - End-to-end semantic search function via Snowpark
"""

import os
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


# --- DDL: add embedding column ---
ADD_EMBEDDING_COLUMN_SQL = """
ALTER TABLE knowledge_base
ADD COLUMN IF NOT EXISTS embedding VECTOR(FLOAT, 768)
"""

# --- Populate embeddings ---
POPULATE_EMBEDDINGS_SQL = """
UPDATE knowledge_base
SET embedding = SNOWFLAKE.CORTEX.EMBED_TEXT_768(
    'snowflake-arctic-embed-m',
    content
)
WHERE embedding IS NULL
"""

# --- Similarity search ---
# :query_embedding is a bound parameter — replace with your query vector
SIMILARITY_SEARCH_SQL = """
SELECT
    doc_id,
    title,
    content,
    VECTOR_COSINE_SIMILARITY(
        embedding,
        SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', %(query)s)
    ) AS similarity_score
FROM knowledge_base
ORDER BY similarity_score DESC
LIMIT 5
"""

# --- Hybrid search: metadata filter + vector similarity ---
HYBRID_SEARCH_SQL = """
SELECT
    doc_id,
    title,
    category,
    VECTOR_COSINE_SIMILARITY(
        embedding,
        SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', %(query)s)
    ) AS similarity_score
FROM knowledge_base
WHERE category = %(category)s            -- metadata pre-filter reduces scan
  AND created_at >= DATEADD('day', -90, CURRENT_TIMESTAMP())
ORDER BY similarity_score DESC
LIMIT 10
"""


def semantic_search(conn, query: str, top_k: int = 5) -> list[dict]:
    cur = conn.cursor(snowflake.connector.DictCursor)
    cur.execute(SIMILARITY_SEARCH_SQL, {"query": query})
    results = cur.fetchmany(top_k)
    cur.close()
    return results


def main():
    conn = get_connection()

    query = "How do I set up a clustering key in Snowflake?"
    print(f"Query: {query}\n")
    results = semantic_search(conn, query)
    for i, row in enumerate(results, 1):
        print(f"{i}. [{row['SIMILARITY_SCORE']:.4f}] {row['TITLE']}")

    conn.close()

    print("\nDDL to add embedding column:")
    print(ADD_EMBEDDING_COLUMN_SQL)

    print("\nSQL to populate embeddings:")
    print(POPULATE_EMBEDDINGS_SQL)


if __name__ == "__main__":
    main()
