"""
08_cortex_analyst.py — Cortex Analyst: natural language to SQL via a semantic model

Cortex Analyst reads a YAML semantic model from a Snowflake stage and translates
plain-English questions into verified SQL that runs against your data.

Demonstrates:
  - Uploading a semantic model YAML to a stage
  - Calling the /api/v2/cortex/analyst/message REST endpoint
  - Parsing the SQL response and running it
"""

import os
import json
import requests
from pathlib import Path
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


def get_jwt_token(conn) -> str:
    """Get a Snowflake JWT token for REST API auth."""
    cur = conn.cursor()
    cur.execute("SELECT SYSTEM$GENERATE_SCOPED_SERVICE_TOKEN('CORTEX_ANALYST', 3600)")
    token = cur.fetchone()[0]
    cur.close()
    return token


def upload_semantic_model(conn, yaml_path: str, stage: str = "@my_stage"):
    """Upload the semantic model YAML to a Snowflake stage."""
    cur = conn.cursor()
    cur.execute(f"PUT file://{yaml_path} {stage} OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
    print(f"Uploaded {yaml_path} to {stage}")
    cur.close()


def ask_cortex_analyst(account: str, token: str, question: str, stage_path: str) -> dict:
    """Send a natural-language question to the Cortex Analyst REST API."""
    url = f"https://{account}.snowflakecomputing.com/api/v2/cortex/analyst/message"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_model_file": stage_path,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def extract_sql(response: dict) -> str | None:
    """Pull the generated SQL out of the Cortex Analyst response."""
    for msg in response.get("message", {}).get("content", []):
        if msg.get("type") == "sql":
            return msg.get("statement")
    return None


def main():
    conn = get_connection()
    account = os.environ["SNOWFLAKE_ACCOUNT"]

    # Upload semantic model (see semantic_models/sales.yaml in this project)
    model_path = str(Path(__file__).parent.parent / "semantic_models" / "sales.yaml")
    stage_path = "@my_stage/sales.yaml"
    upload_semantic_model(conn, model_path)

    token = get_jwt_token(conn)

    question = "What were the top 5 products by revenue last quarter?"
    print(f"Question: {question}\n")

    response = ask_cortex_analyst(account, token, question, stage_path)
    sql = extract_sql(response)

    if sql:
        print("Generated SQL:")
        print(sql)
        print("\nRunning query...")
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(sql)
        for row in cur.fetchmany(10):
            print(row)
        cur.close()
    else:
        print("No SQL returned. Full response:")
        print(json.dumps(response, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
