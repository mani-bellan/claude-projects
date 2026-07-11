"""
01_connection.py — Establish and test a Snowflake connection using credentials from .env
"""

import os
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_VERSION()")
    row = cur.fetchone()
    print(f"Account : {row[0]}")
    print(f"User    : {row[1]}")
    print(f"Version : {row[2]}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
