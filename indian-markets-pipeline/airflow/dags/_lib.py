"""Shared imports + factory for DAG tasks.

Imports are kept inside functions where it matters so the Airflow scheduler's
DAG-parsing pass stays cheap. This module itself only declares the helper.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@contextmanager
def open_loader():
    """Yield a (conn, loader) pair using the configured paths."""
    from markets_pipeline.config import CONFIG
    from markets_pipeline.duckdb_client import connect
    from markets_pipeline.loaders import DuckDBLoader
    from markets_pipeline.schema import SchemaEvolution, SchemaRegistry

    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        loader = DuckDBLoader(conn, SchemaEvolution(conn, registry))
        yield conn, loader


class NothingLoaded(RuntimeError):
    """Every fetch failed: the extractors logged warnings and returned no rows."""


class RowsQuarantined(RuntimeError):
    """The schema engine rejected the batch and moved it to a _rejects_ table."""


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.levelname} {record.name}: {record.getMessage()}")


def triaged(downstream: list[str], upstream: list[str] | None = None):
    """Send a failed task to the Jev triage app (markets_pipeline.triage) before Airflow retries it.

    The extractors catch fetch errors and only log a warning, so this also fails the task when the
    result reports nothing loaded while warnings were logged, or reports rows quarantined by the
    schema engine. A run that loads nothing without warnings, such as on a market holiday, passes.

    `upstream` names what the task runs after, and `downstream` what depends on it; Jev reads both.
    Each decision is appended to data/triage_log.jsonl. TRIAGE_MODE=shadow (the default) only records
    it, so Airflow retries as configured. TRIAGE_MODE=act stops the remaining retries when the
    decision is not "retry". Without TYPESAFE_API_KEY, failures are raised exactly as before.
    """

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            collect = _Collect()
            watched = [logging.getLogger("markets_pipeline"), logging.getLogger("yfinance")]
            for logger in watched:
                logger.addHandler(collect)
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get("rejected"):
                    raise RowsQuarantined(f"{result['rejected']} rows were quarantined by the schema engine: {result}")
                if isinstance(result, dict) and result.get("loaded") == 0 and collect.lines:
                    raise NothingLoaded(f"Nothing was loaded and the extractors logged {len(collect.lines)} warnings: {result}")
                return result
            except Exception as error:
                if os.environ.get("TYPESAFE_API_KEY"):
                    _triage_failure(error, collect.lines, downstream, upstream or [])
                raise
            finally:
                for logger in watched:
                    logger.removeHandler(collect)

        return wrapper

    return decorate


def _triage_failure(error: Exception, warnings: list[str], downstream: list[str], upstream: list[str]) -> None:
    from airflow.exceptions import AirflowFailException
    from airflow.operators.python import get_current_context
    from typesafe_sdk import TypeSafeClient

    from markets_pipeline.config import CONFIG
    from markets_pipeline.triage import triage

    ti = get_current_context()["ti"]
    trace = traceback.format_exception(error)
    error_log = "".join(trace[-12:])
    if warnings:
        error_log += "\nWarnings logged during the task:\n" + "\n".join(warnings[-10:])
    failure = {
        "pipeline": ti.dag_id,
        "task": ti.task_id,
        "attempt": ti.try_number,
        "max_attempts": ti.max_tries + 1,
        "upstream": upstream,
        "downstream": downstream,
        "error_log": error_log[-4000:],
    }
    mode = os.environ.get("TRIAGE_MODE", "shadow")
    try:
        with TypeSafeClient() as client:
            decision = triage(client, failure)
    except Exception:
        log.exception("Triage failed; leaving the failure to Airflow")
        return

    log.error(
        "TRIAGE (%s mode): %s, %s. Cause %s (%.2f confidence), impact %.1f/2",
        mode, decision.action, decision.detail, decision.cause, decision.cause_confidence, decision.impact,
    )
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "failure": failure,
        "decision": decision.__dict__,
    }
    with (CONFIG.project_root / "data" / "triage_log.jsonl").open("a") as file:
        file.write(json.dumps(record) + "\n")

    if mode == "act" and decision.action != "retry":
        raise AirflowFailException(f"Triage decided {decision.action} ({decision.detail}); not retrying") from error
