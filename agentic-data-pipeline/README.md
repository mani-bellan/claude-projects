# Agentic Data Engineering Pipeline

A single AI agent that can ingest, explore, transform, profile, and export data — all driven by natural language. Powered by **Claude claude-opus-4-7** and **DuckDB**.

---

## How It Works

```
You describe a task in plain English
        ↓
Claude (claude-opus-4-7) reasons about the steps needed
        ↓
Claude calls DuckDB tools autonomously in a loop
        ↓
Results are written to the database and exported to files
```

The agent runs a **tool loop**: it receives your task, decides which tool to call, gets the result, then decides what to do next — repeating until the task is complete. You never write SQL or Python; the agent figures out the sequence.

---

## Project Structure

```
agentic-data-pipeline/
├── agent.py          # Entry point — runs the agent loop
├── tools.py          # 8 DuckDB tools the agent can call
├── requirements.txt  # Python dependencies
├── .env              # Your API key (not committed to git)
├── .env.example      # Template for the .env file
├── pipeline.duckdb   # DuckDB database file (created on first run)
├── data/
│   └── sample_sales.csv   # Sample dataset (30 rows of sales records)
└── output/
    └── *.csv / *.parquet  # Exported results land here
```

---

## The 8 Tools

Each tool is a Python function decorated with `@beta_tool`, which lets Claude call it automatically. Claude reads the function name, description, and parameter types to decide when and how to use each one.

| Tool | Purpose |
|---|---|
| `load_file` | Ingest a CSV, Parquet, or JSON file into a DuckDB table |
| `list_tables` | Show all tables currently in the database |
| `describe_table` | Show column names and data types for a table |
| `run_sql` | Execute any SQL query — SELECTs, CTEs, CREATE TABLE AS, etc. |
| `sample_table` | Preview the first N rows of a table |
| `profile_table` | Statistical summary: null rates, unique counts, min/max/avg |
| `check_duplicates` | Find duplicate rows across all columns or a specific subset |
| `export_table` | Write a table to CSV or Parquet |

### How tools are defined

```python
# tools.py
from anthropic import beta_tool

@beta_tool
def load_file(file_path: str, table_name: str) -> str:
    """Load a data file into DuckDB. Supports CSV, Parquet, and JSON.

    Args:
        file_path: Path to the input file (.csv, .parquet, .json, or .jsonl).
        table_name: Target table name to create in DuckDB.
    """
    # implementation calls duckdb ...
```

Claude reads the docstring to understand what the tool does and what each argument means. The `@beta_tool` decorator auto-generates the JSON schema that the API uses for structured tool calling.

---

## How the Agent Loop Works

```python
# agent.py (simplified)
runner = client.beta.messages.tool_runner(
    model="claude-opus-4-7",
    system=SYSTEM_PROMPT,
    tools=ALL_TOOLS,          # the 8 tools above
    messages=[{"role": "user", "content": task}],
)

for message in runner:        # iterates until Claude is done
    for block in message.content:
        if block.type == "text":
            print(block.text) # show the agent's narration
```

The `tool_runner` handles everything automatically:

1. Sends your task to Claude
2. Claude returns a `tool_use` block (e.g., call `load_file`)
3. The SDK executes the tool and feeds the result back to Claude
4. Claude decides the next step — another tool call, or a final answer
5. Loop ends when Claude stops calling tools

---

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your API key**

Copy `.env.example` to `.env` and add your key from [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys):

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**3. Run the default task**

```bash
python agent.py
```

The default task loads `data/sample_sales.csv`, profiles it, finds the top products and regional breakdown by revenue, and exports two CSV files to `output/`.

---

## Usage Examples

**Run the default task:**
```bash
python agent.py
```

**Pass any natural language task as an argument:**
```bash
python agent.py "Load data/sample_sales.csv and show me which customers spent more than 2000 total"

python agent.py "Load data/sample_sales.csv, remove any duplicates, and export a clean version to output/sales_clean.csv"

python agent.py "Load data/sample_sales.csv and create a monthly revenue trend from January to March"
```

---

## Sample Dataset

`data/sample_sales.csv` contains 30 rows with these columns:

| Column | Type | Description |
|---|---|---|
| `order_id` | integer | Unique order identifier |
| `date` | date | Order date |
| `customer_id` | string | Customer identifier (C001–C010) |
| `product` | string | Product name |
| `category` | string | Electronics or Furniture |
| `quantity` | integer | Units ordered |
| `unit_price` | float | Price per unit |
| `total_price` | float | quantity × unit_price |
| `region` | string | North / South / East / West |

---

## Extending the Pipeline

**Add a new tool** — define a function in `tools.py` and add it to `ALL_TOOLS` in `agent.py`:

```python
# tools.py
@beta_tool
def filter_table(table_name: str, condition: str, output_table: str) -> str:
    """Create a filtered copy of a table using a SQL WHERE condition.

    Args:
        table_name: Source table to filter.
        condition: SQL WHERE clause (e.g., 'region = ''North'' AND quantity > 2').
        output_table: Name for the resulting filtered table.
    """
    try:
        _conn.execute(
            f"CREATE OR REPLACE TABLE {output_table} AS "
            f"SELECT * FROM {table_name} WHERE {condition}"
        )
        count = _conn.execute(f"SELECT COUNT(*) FROM {output_table}").fetchone()[0]
        return f"Created '{output_table}' with {count:,} rows"
    except Exception as e:
        return f"Error: {e}"
```

Then in `agent.py`:
```python
from tools import ..., filter_table

ALL_TOOLS = [..., filter_table]
```

That's it — Claude will discover and use the new tool automatically based on its name and description.

**Swap in your own data** — just point Claude at any file:
```bash
python agent.py "Load my_data/transactions.parquet into a table called transactions and profile it"
```

**Persist results across runs** — DuckDB writes to `pipeline.duckdb`, so tables created in one run are available in the next.

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| Single agent, many tools | Simpler than multi-agent; one Claude instance holds full context across all steps |
| DuckDB | Embedded, no server needed; handles CSV/Parquet/JSON natively; fast SQL on local files |
| `@beta_tool` decorator | Auto-generates tool schemas from type hints and docstrings — no manual JSON |
| `tool_runner` loop | SDK handles the call/execute/respond cycle; no manual loop needed |
| Module-level DB connection | Single shared connection across all tools; consistent transaction state |
| Tools return strings | Simple contract — Claude reads the string result and decides what to do next |
