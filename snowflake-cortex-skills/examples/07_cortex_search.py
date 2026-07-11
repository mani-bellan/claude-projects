"""
07_cortex_search.py — Cortex Search Service: create, query, and filter

Cortex Search manages its own embedding pipeline and index refresh automatically.
It provides a managed retrieval API backed by hybrid (vector + keyword) search.

Demonstrates:
  - CREATE CORTEX SEARCH SERVICE DDL
  - Querying via the Snowflake Python SDK (snowflake.core)
  - Metadata filter patterns
"""

import os
import json
from dotenv import load_dotenv
from snowflake.snowpark import Session

load_dotenv()


def get_session() -> Session:
    return Session.builder.configs(
        {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "database": os.environ["SNOWFLAKE_DATABASE"],
            "schema": os.environ["SNOWFLAKE_SCHEMA"],
            "role": os.environ.get("SNOWFLAKE_ROLE"),
        }
    ).create()


# --- DDL: create the search service ---
CREATE_SERVICE_SQL = """
CREATE OR REPLACE CORTEX SEARCH SERVICE docs_search_service
  ON content
  ATTRIBUTES category, doc_type, created_at
  WAREHOUSE = {warehouse}
  TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-m'
AS
  SELECT
      doc_id,
      title,
      content,
      category,
      doc_type,
      created_at
  FROM knowledge_base
  WHERE is_active = TRUE
"""


def create_search_service(session: Session):
    wh = os.environ["SNOWFLAKE_WAREHOUSE"]
    session.sql(CREATE_SERVICE_SQL.format(warehouse=wh)).collect()
    print("Cortex Search Service created.")


def query_search_service(session: Session, query: str, filters: dict | None = None, limit: int = 5):
    """Query Cortex Search via the REST-style Python SDK."""
    from snowflake.core import Root

    root = Root(session)
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]

    svc = root.databases[db].schemas[schema].cortex_search_services["docs_search_service"]

    kwargs = {
        "query": query,
        "columns": ["doc_id", "title", "content", "category"],
        "limit": limit,
    }
    if filters:
        kwargs["filter"] = filters

    response = svc.search(**kwargs)
    return response.results


def main():
    session = get_session()

    # Unfiltered search
    print("=== Unfiltered search ===")
    results = query_search_service(session, "clustering keys and micro-partitions")
    for r in results:
        print(f"  [{r.get('category')}] {r['title']}")

    # Filtered search — exact match on category
    print("\n=== Filtered by category='engineering' ===")
    results = query_search_service(
        session,
        "performance tuning",
        filters={"@eq": {"category": "engineering"}},
    )
    for r in results:
        print(f"  {r['title']}")

    session.close()

    print("\nCREATE SERVICE DDL (fill in your table):")
    print(CREATE_SERVICE_SQL)


if __name__ == "__main__":
    main()
