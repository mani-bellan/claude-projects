"""
05_cortex_translate.py — Translation with SNOWFLAKE.CORTEX.TRANSLATE()

Translates text between languages using ISO 639-1 language codes.
Pass '' as the source language for auto-detection.

Demonstrates:
  - Translate a single string
  - Batch translate a multilingual table to English
  - Auto-detect source language
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


# Common ISO 639-1 codes: en, fr, de, es, it, ja, ko, pt, zh, ar, ru, nl

SINGLE_TRANSLATE_SQL = """
SELECT
    SNOWFLAKE.CORTEX.TRANSLATE('Bonjour, comment puis-je vous aider?', 'fr', 'en') AS en_text,
    SNOWFLAKE.CORTEX.TRANSLATE('Hola, ¿cómo puedo ayudarte?',          'es', 'en') AS en_text2,
    SNOWFLAKE.CORTEX.TRANSLATE('こんにちは、お手伝いできますか？',         'ja', 'en') AS en_text3
"""

# Auto-detect source language (pass '' as src)
AUTO_DETECT_SQL = """
SELECT
    original_text,
    SNOWFLAKE.CORTEX.TRANSLATE(original_text, '', 'en') AS english_translation
FROM multilingual_reviews
LIMIT 10
"""

# Batch normalize to English then score sentiment
TRANSLATE_THEN_ANALYZE_SQL = """
SELECT
    review_id,
    original_language,
    review_text,
    SNOWFLAKE.CORTEX.TRANSLATE(review_text, original_language, 'en')         AS english_text,
    SNOWFLAKE.CORTEX.SENTIMENT(
        SNOWFLAKE.CORTEX.TRANSLATE(review_text, original_language, 'en')
    )                                                                          AS sentiment_score
FROM multilingual_reviews
LIMIT 20
"""


def run_single(conn):
    print("=== Single Translation Examples ===")
    cur = conn.cursor()
    cur.execute(SINGLE_TRANSLATE_SQL)
    row = cur.fetchone()
    print(f"French → English : {row[0]}")
    print(f"Spanish → English: {row[1]}")
    print(f"Japanese → English: {row[2]}")
    cur.close()


def main():
    conn = get_connection()
    run_single(conn)
    conn.close()

    print("\nAuto-detect SQL:")
    print(AUTO_DETECT_SQL)

    print("\nTranslate → Sentiment pipeline SQL:")
    print(TRANSLATE_THEN_ANALYZE_SQL)


if __name__ == "__main__":
    main()
