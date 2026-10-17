"""The @triaged guard for silent failures, and the triage policy, without Airflow or a Jev API key."""

import logging
import sys
from pathlib import Path

import httpx2
import pytest
from typesafe_sdk import TypeSafeClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "dags"))

from _lib import NothingLoaded, RowsQuarantined, triaged  # noqa: E402
from markets_pipeline.triage import triage  # noqa: E402

extractor_log = logging.getLogger("markets_pipeline.extractors.mutual_funds")


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


def test_nothing_loaded_after_fetch_warnings_fails_the_task():
    @triaged(downstream=[])
    def task():
        extractor_log.warning("mfapi fetch failed for 120503: connection refused")
        return {"loaded": 0, "rejected": 0}

    with pytest.raises(NothingLoaded, match="1 warnings"):
        task()


def test_nothing_loaded_without_warnings_passes_like_a_market_holiday():
    @triaged(downstream=[])
    def task():
        return {"loaded": 0, "rejected": 0}

    assert task() == {"loaded": 0, "rejected": 0}


def test_partial_load_with_warnings_passes():
    @triaged(downstream=[])
    def task():
        extractor_log.warning("mfapi fetch failed for 120503: connection refused")
        return {"loaded": 16, "rejected": 0}

    assert task()["loaded"] == 16


def test_quarantined_rows_fail_the_task():
    @triaged(downstream=[])
    def task():
        return {"loaded": 0, "rejected": 20}

    with pytest.raises(RowsQuarantined, match="20 rows"):
        task()


def fake_jev(cause: str, confidence: float, impact: float) -> TypeSafeClient:
    answers = {
        "cause": {"type": "choice", "choice": cause, "confidence": confidence, "probabilities": {cause: confidence}},
        "impact": {"type": "score", "score": impact, "confidence": 1.0, "legend": {}, "probabilities": {}},
    }
    body = {"model": "jev-test", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}
    return TypeSafeClient(api_key="test-key", transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=body)))


@pytest.mark.parametrize(
    ("cause", "attempt", "max_attempts", "action"),
    [
        # Retries follow each DAG's own retry count: the last attempt is never retried.
        ("network", 3, 4, "retry"),
        ("network", 4, 4, "ticket"),
        # A cause that needs a fix is not retried, even with attempts left.
        ("code_bug", 1, 4, "ticket"),
        ("unknown", 1, 4, "review"),
    ],
)
def test_policy(cause, attempt, max_attempts, action):
    failure = {"pipeline": "daily_navs", "task": "fetch_and_load", "attempt": attempt, "max_attempts": max_attempts}

    assert triage(fake_jev(cause, 1.0, 0.0), failure).action == action
