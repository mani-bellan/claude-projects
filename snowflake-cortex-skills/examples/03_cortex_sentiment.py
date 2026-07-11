"""
03_cortex_sentiment.py — Sentiment analysis with SNOWFLAKE.CORTEX.SENTIMENT()

Returns a score between -1.0 (very negative) and 1.0 (very positive).

Demonstrates:
  - Scoring individual strings
  - Batch scoring a table column
  - Binning scores into labels (positive / neutral / negative)
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


SINGLE_SENTIMENT_SQL = """
SELECT
    SNOWFLAKE.CORTEX.SENTIMENT('The product exceeded all my expectations!') AS score_positive,
    SNOWFLAKE.CORTEX.SENTIMENT('It was okay, nothing special.')             AS score_neutral,
    SNOWFLAKE.CORTEX.SENTIMENT('Terrible experience, would not recommend.') AS score_negative
"""

# Batch: score + bin reviews from your own table
BATCH_SENTIMENT_SQL = """
SELECT
    review_id,
    review_text,
    SNOWFLAKE.CORTEX.SENTIMENT(review_text) AS sentiment_score,
    CASE
        WHEN SNOWFLAKE.CORTEX.SENTIMENT(review_text) >= 0.3  THEN 'positive'
        WHEN SNOWFLAKE.CORTEX.SENTIMENT(review_text) <= -0.3 THEN 'negative'
        ELSE 'neutral'
    END AS sentiment_label
FROM product_reviews
ORDER BY sentiment_score
LIMIT 20
"""

# Aggregate: average sentiment by product category
AGGREGATE_SENTIMENT_SQL = """
SELECT
    category,
    ROUND(AVG(SNOWFLAKE.CORTEX.SENTIMENT(review_text)), 3) AS avg_sentiment,
    COUNT(*) AS review_count
FROM product_reviews
GROUP BY category
ORDER BY avg_sentiment DESC
"""


def run_single(conn):
    print("=== Individual Sentiment Scores ===")
    cur = conn.cursor()
    cur.execute(SINGLE_SENTIMENT_SQL)
    row = cur.fetchone()
    print(f"Positive text score : {row[0]:.4f}")
    print(f"Neutral text score  : {row[1]:.4f}")
    print(f"Negative text score : {row[2]:.4f}")
    cur.close()


def main():
    conn = get_connection()
    run_single(conn)
    conn.close()

    print("\nBatch SQL (run against your own reviews table):")
    print(BATCH_SENTIMENT_SQL)

    print("\nAggregate SQL:")
    print(AGGREGATE_SENTIMENT_SQL)


if __name__ == "__main__":
    main()
