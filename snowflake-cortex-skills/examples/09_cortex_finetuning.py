"""
09_cortex_finetuning.py — Cortex Fine-tuning: create and use a fine-tuned model

Cortex Fine-tuning lets you adapt a base LLM (e.g. mistral-7b, llama3-8b) to your
domain using supervised examples stored in a Snowflake table.

Training data format (one row per example):
  prompt  TEXT  — the input prompt
  completion  TEXT  — the desired model output

Demonstrates:
  - Creating a fine-tuning job
  - Monitoring job status
  - Running inference with the fine-tuned model via CORTEX.COMPLETE
"""

import os
import time
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


# --- Training data table DDL ---
TRAINING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS cortex_finetune_training (
    prompt     TEXT NOT NULL,
    completion TEXT NOT NULL
)
"""

# --- Start a fine-tuning job ---
# Base models available for fine-tuning: mistral-7b, llama3-8b, llama3-70b
CREATE_JOB_SQL = """
SELECT SNOWFLAKE.CORTEX.FINETUNE(
    'CREATE',
    'my_custom_model_v1',
    'mistral-7b',
    'SELECT prompt, completion FROM cortex_finetune_training',
    NULL   -- optional validation query; NULL = auto 10% split
)
"""

# --- Check job status ---
STATUS_SQL = """
SELECT SNOWFLAKE.CORTEX.FINETUNE('DESCRIBE', %(job_id)s)
"""

# --- List all fine-tuning jobs ---
LIST_JOBS_SQL = """
SELECT SNOWFLAKE.CORTEX.FINETUNE('SHOW', NULL)
"""

# --- Inference with the fine-tuned model ---
INFERENCE_SQL = """
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'my_custom_model_v1',
    'Classify the following support ticket: ' || ticket_text
) AS predicted_category
FROM support_tickets
LIMIT 5
"""


def start_finetuning_job(conn) -> str:
    print("Starting fine-tuning job...")
    cur = conn.cursor()
    cur.execute(CREATE_JOB_SQL)
    result = cur.fetchone()[0]
    cur.close()
    import json
    job_id = json.loads(result).get("id")
    print(f"Job ID: {job_id}")
    return job_id


def wait_for_job(conn, job_id: str, poll_interval: int = 30):
    print(f"Polling job {job_id}...")
    cur = conn.cursor()
    while True:
        cur.execute(STATUS_SQL, {"job_id": job_id})
        import json
        status_raw = cur.fetchone()[0]
        status = json.loads(status_raw)
        state = status.get("status")
        progress = status.get("progress", 0)
        print(f"  Status: {state}  Progress: {progress:.0%}")
        if state in ("SUCCESS", "ERROR", "CANCELLED"):
            break
        time.sleep(poll_interval)
    cur.close()
    return status


def main():
    conn = get_connection()

    # Uncomment to run:
    # job_id = start_finetuning_job(conn)
    # final_status = wait_for_job(conn, job_id)
    # print(final_status)

    print("Training table DDL:")
    print(TRAINING_TABLE_DDL)

    print("\nCreate job SQL:")
    print(CREATE_JOB_SQL)

    print("\nInference SQL (after model is trained):")
    print(INFERENCE_SQL)

    conn.close()


if __name__ == "__main__":
    main()
