"""
04_cortex_summarize.py — Summarization with SNOWFLAKE.CORTEX.SUMMARIZE()

Condenses long text (documents, call transcripts, emails) into a short paragraph.

Demonstrates:
  - Single text summarization
  - Batch summarization of a table column
  - Chaining: summarize then sentiment-score the summary
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


SAMPLE_TEXT = """
Snowflake is a cloud data platform that enables data storage, processing, and analytic solutions
that are faster, easier to use, and far more flexible than traditional offerings. Snowflake's
architecture separates storage and compute, allowing customers to scale each independently.
The platform supports structured and semi-structured data, including JSON, Avro, ORC, Parquet,
and XML. Snowflake Cortex brings AI directly to your data, enabling large language model
capabilities without moving data out of Snowflake. Features include COMPLETE for text generation,
SENTIMENT for opinion mining, SUMMARIZE for condensing content, TRANSLATE for multilingual data,
and Cortex Search for vector-powered retrieval.
"""

SINGLE_SUMMARIZE_SQL = f"""
SELECT SNOWFLAKE.CORTEX.SUMMARIZE($${SAMPLE_TEXT.strip()}$$) AS summary
"""

# Batch: summarize call transcripts
BATCH_SUMMARIZE_SQL = """
SELECT
    call_id,
    agent_id,
    SNOWFLAKE.CORTEX.SUMMARIZE(transcript) AS summary
FROM call_transcripts
WHERE LENGTH(transcript) > 500
LIMIT 10
"""

# Chain: summarize → sentiment (useful for long-form feedback)
CHAINED_SQL = """
SELECT
    ticket_id,
    SNOWFLAKE.CORTEX.SUMMARIZE(description)                                         AS summary,
    SNOWFLAKE.CORTEX.SENTIMENT(SNOWFLAKE.CORTEX.SUMMARIZE(description))             AS summary_sentiment
FROM support_tickets
WHERE LENGTH(description) > 1000
LIMIT 10
"""


def run_single(conn):
    print("=== Single Text Summarization ===")
    cur = conn.cursor()
    cur.execute(SINGLE_SUMMARIZE_SQL)
    row = cur.fetchone()
    print(row[0])
    cur.close()


def main():
    conn = get_connection()
    run_single(conn)
    conn.close()

    print("\nBatch SQL:")
    print(BATCH_SUMMARIZE_SQL)

    print("\nChained summarize → sentiment SQL:")
    print(CHAINED_SQL)


if __name__ == "__main__":
    main()
