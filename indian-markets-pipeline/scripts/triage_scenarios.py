"""Break the pipeline in realistic ways, run the real Airflow task, and score the Jev triage decision.

    TYPESAFE_API_KEY=... .venv/bin/python scripts/triage_scenarios.py

Each scenario copies the project to a temporary directory, sets it up, runs
`airflow tasks test <dag> <task>`, and reads the decision that @triaged recorded in
data/triage_log.jsonl. Captured failures are saved to data/triage_scenarios/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
AIRFLOW = PROJECT / ".venv" / "bin" / "airflow"
PYTHON = PROJECT / ".venv" / "bin" / "python"
OUT = PROJECT / "data" / "triage_scenarios"

SEED = """
import polars as pl
from datetime import date, timedelta
from markets_pipeline.config import CONFIG
from markets_pipeline.duckdb_client import connect
from markets_pipeline.loaders import DuckDBLoader
from markets_pipeline.schema import SchemaEvolution, SchemaRegistry

days = [date(2025, 1, 1) + timedelta(days=i) for i in range(400)]
prices = pl.DataFrame({
    "ticker": ["TCS.NS"] * 400 + ["INFY.NS"] * 400,
    "date": days * 2,
    "open": [100.0 + i * 0.1 for i in range(800)], "high": [101.0 + i * 0.1 for i in range(800)],
    "low": [99.0 + i * 0.1 for i in range(800)], "close": [100.5 + i * 0.1 for i in range(800)],
    "adj_close": [100.5 + i * 0.1 for i in range(800)], "volume": [1000] * 800,
})
navs = pl.DataFrame({
    "scheme_code": [120503] * 400, "scheme_name": ["Parag Parikh Flexi Cap"] * 400,
    "fund_house": ["PPFAS"] * 400, "scheme_category": ["Equity"] * 400, "scheme_type": ["Open Ended"] * 400,
    "date": days, "nav": [50.0 + i * 0.05 for i in range(400)],
})
with connect(CONFIG.duckdb_path) as conn:
    loader = DuckDBLoader(conn, SchemaEvolution(conn, SchemaRegistry(CONFIG.schema_registry_path)))
    loader.load("stock_prices", prices, ["ticker", "date"])
    loader.load("mf_navs", navs, ["scheme_code", "date"])
"""


def committed_registry(root: Path, env: dict) -> None:
    shutil.copy(PROJECT / "data" / "schema_registry.json", env["SCHEMA_REGISTRY_PATH"])


def seed(root: Path, env: dict) -> None:
    subprocess.run([PYTHON, "-c", SEED], env=env, check=True)


def nav_registered_as_text(root: Path, env: dict) -> None:
    seed(root, env)
    path = Path(env["SCHEMA_REGISTRY_PATH"])
    registry = json.loads(path.read_text())
    registry["tables"]["mf_navs"]["columns"]["nav"]["type"] = "VARCHAR"
    path.write_text(json.dumps(registry))


def hold_duckdb_lock(root: Path, env: dict) -> subprocess.Popen:
    script = f"import duckdb, time; c = duckdb.connect({env['DUCKDB_PATH']!r}); print('locked', flush=True); time.sleep(120)"
    holder = subprocess.Popen([PYTHON, "-c", script], env=env, stdout=subprocess.PIPE, text=True)
    holder.stdout.readline()
    return holder


def typo_in_features(root: Path, env: dict) -> None:
    seed(root, env)
    path = root / "src" / "markets_pipeline" / "transformers" / "features.py"
    text = path.read_text()
    old = '(pl.col("_daily_vol") * math.sqrt'
    assert old in text
    path.write_text(text.replace(old, '(pl.col("_daily_volatility") * math.sqrt', 1))


def nav_column_renamed(root: Path, env: dict) -> None:
    seed(root, env)
    script = f"import duckdb; duckdb.connect({env['DUCKDB_PATH']!r}).execute('ALTER TABLE mf_navs RENAME COLUMN nav TO nav_value')"
    subprocess.run([PYTHON, "-c", script], env=env, check=True)


SCENARIOS = {
    # A fresh clone: the committed schema registry says mf_navs exists, but the new DuckDB file is empty.
    "registry_out_of_sync": {"task": ("daily_navs", "fetch_and_load"), "setup": committed_registry, "expect": ({"code_bug"}, "ticket")},
    # The network path to mfapi.in is down; the extractor logs a warning per scheme and loads nothing.
    "api_unreachable": {
        "task": ("daily_navs", "fetch_and_load"),
        "env": {"HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": "api.typesafe.ai"},
        "expect": ({"network"}, "retry"),
    },
    # The Streamlit dashboard (or another job) holds the DuckDB file open.
    "duckdb_locked": {"task": ("daily_navs", "fetch_and_load"), "hold": hold_duckdb_lock, "expect": ({"resources", "network"}, "retry")},
    # An earlier run registered nav as text; today's numbers are quarantined by the schema engine.
    "schema_conflict": {"task": ("daily_navs", "fetch_and_load"), "setup": nav_registered_as_text, "expect": ({"schema_change"}, "ticket")},
    # feature_build runs before any prices have been loaded.
    "feature_build_too_early": {"task": ("feature_build", "build"), "expect": ({"upstream_delay"}, "retry")},
    # A typo in the feature code.
    "code_bug": {"task": ("feature_build", "build"), "setup": typo_in_features, "expect": ({"code_bug"}, "ticket")},
    # Held out: added after the wording was tuned on the scenarios above, to check it generalizes.
    # The weekly AMFI master download cannot reach mfapi.in; this extractor raises instead of logging.
    "held_out_master_unreachable": {
        "task": ("universe_refresh", "refresh_mfs"),
        "env": {"HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": "api.typesafe.ai"},
        "expect": ({"network"}, "retry"),
    },
    # Someone renamed a column in the warehouse table that feature_build reads.
    "held_out_column_renamed": {"task": ("feature_build", "build"), "setup": nav_column_renamed, "expect": ({"schema_change"}, "ticket")},
}


def run(name: str, scenario: dict) -> dict | None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "project"
        shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns(".venv", "data", "logs", "__pycache__", "*.db", "*.cfg"))
        (root / "data").mkdir()
        env = {
            **os.environ,
            "PYTHONPATH": str(root / "src"),
            "AIRFLOW__CORE__DAGS_FOLDER": str(root / "airflow" / "dags"),
            "AIRFLOW__CORE__LOAD_EXAMPLES": "false",
            "DUCKDB_PATH": str(root / "data" / "markets.duckdb"),
            "SCHEMA_REGISTRY_PATH": str(root / "data" / "schema_registry.json"),
            "TRIAGE_MODE": "shadow",
            **scenario.get("env", {}),
        }
        if "setup" in scenario:
            scenario["setup"](root, {k: v for k, v in env.items() if not k.endswith("_PROXY")})
        holder = scenario["hold"](root, env) if "hold" in scenario else None
        try:
            dag, task = scenario["task"]
            started = time.perf_counter()
            subprocess.run([AIRFLOW, "tasks", "test", dag, task, "2026-10-15"], cwd=root, env=env, capture_output=True, text=True)
            seconds = time.perf_counter() - started
        finally:
            if holder:
                holder.kill()
        log = root / "data" / "triage_log.jsonl"
        if not log.exists():
            print(f"{name}: the task did not fail, or triage did not run")
            return None
        record = json.loads(log.read_text().splitlines()[-1])
        record["seconds"] = round(seconds, 1)
        return record


def main() -> None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("Set TYPESAFE_API_KEY first.")
    OUT.mkdir(parents=True, exist_ok=True)
    correct = 0
    for name, scenario in SCENARIOS.items():
        record = run(name, scenario)
        if record is None:
            continue
        (OUT / f"{name}.json").write_text(json.dumps(record["failure"], indent=2) + "\n")
        decision = record["decision"]
        causes, action = scenario["expect"]
        ok = decision["cause"] in causes and decision["action"] == action
        correct += ok
        print(
            f"{'OK ' if ok else 'BAD'} {name:24} cause {decision['cause']} ({decision['cause_confidence']:.2f}), "
            f"impact {decision['impact']:.1f} -> {decision['action']}"
            + ("" if ok else f"  (expected {'/'.join(sorted(causes))} -> {action})")
        )
    print(f"{correct}/{len(SCENARIOS)} match the expected cause and action")


if __name__ == "__main__":
    main()
