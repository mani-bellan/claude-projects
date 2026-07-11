"""
02_cortex_complete.py — Run SNOWFLAKE.CORTEX.COMPLETE() to generate text from a prompt.

Demonstrates:
  - Single prompt completion
  - Batch completion over a table column
  - Parsing JSON-structured responses with TRY_PARSE_JSON
"""

import os
import json
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


# --- Single prompt completion ---

SINGLE_PROMPT_SQL = """
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'mistral-large2',
    'You are a helpful data engineer. Explain in two sentences what a clustering key is in Snowflake.'
) AS response
"""

# --- Batch completion: classify support tickets ---

BATCH_SQL = """
SELECT
    ticket_id,
    ticket_text,
    SNOWFLAKE.CORTEX.COMPLETE(
        'snowflake-arctic',
        'Classify the following support ticket into one of: billing, technical, account, other. ' ||
        'Reply with only the category word.\n\nTicket: ' || ticket_text
    ) AS category
FROM support_tickets
LIMIT 10
"""

# --- Structured JSON output ---

JSON_SQL = """
SELECT
    product_id,
    review_text,
    TRY_PARSE_JSON(
        SNOWFLAKE.CORTEX.COMPLETE(
            'llama3.1-70b',
            'Return a JSON object with keys "pros" (array of strings) and "cons" (array of strings) ' ||
            'extracted from this product review. Review: ' || review_text
        )
    ) AS structured_review
FROM product_reviews
LIMIT 5
"""


def run_single_prompt(conn):
    print("=== Single Prompt Completion ===")
    cur = conn.cursor()
    cur.execute(SINGLE_PROMPT_SQL)
    row = cur.fetchone()
    print(row[0])
    cur.close()


def main():
    conn = get_connection()
    run_single_prompt(conn)
    conn.close()

    print("\nBatch SQL (run against your own table):")
    print(BATCH_SQL)

    print("\nStructured JSON SQL (run against your own table):")
    print(JSON_SQL)


if __name__ == "__main__":
    main()
