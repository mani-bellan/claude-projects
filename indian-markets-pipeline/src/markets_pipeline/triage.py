"""Decide what to do about a failed task with TypeSafe AI's Jev model.

Adapted from https://github.com/mani-bellan/jev-apps (triage.py). One Jev call answers two questions
about the failure, its cause and its impact, and the policy in `triage()` turns the answers into
retry, ticket, page, or review.
"""

from __future__ import annotations

from dataclasses import dataclass

from typesafe_sdk import Choice, Score, TypeSafeClient

CAUSES = {
    "network": "Timeouts, connection resets, rate limits, or 5xx errors from an external service",
    "upstream_delay": "Expected input data, file, or partition is missing or has not arrived yet",
    "resources": "Out of memory, disk full, a worker or executor was killed, or a file or database lock is held by another process",
    "schema_change": (
        "A source added, removed, renamed, or changed the type of a column. Typical sign: a column read from a"
        " source table or file is not found, often with a similarly named column suggested instead"
    ),
    "data_quality": "A data test or constraint failed: nulls, duplicates, or out-of-range values",
    "credentials": "Authentication or permission errors, or expired tokens, passwords, or keys",
    "code_bug": "A mistake in our own pipeline code that needs a code fix, such as a SQL syntax error or a bug in a transform",
    "unknown": "The log does not contain enough information to tell what went wrong",
}
TRANSIENT = {"network", "upstream_delay", "resources"}
"""Causes that can clear up by themselves, so they are retried while attempts remain."""
OWNERS = {
    "network": "platform team",
    "upstream_delay": "upstream data owners",
    "resources": "platform team",
    "schema_change": "upstream data owners",
    "data_quality": "upstream data owners",
    "credentials": "platform team",
    "code_bug": "pipeline owners",
}

QUESTIONS = {
    "cause": Choice(instructions="The root cause of this pipeline task failure", criteria=CAUSES),
    "impact": Score(
        instructions="How badly this failure affects the consumers of the pipeline's data",
        criteria=[
            "Little impact: internal, exploratory, or rarely used data",
            "Moderate impact: a routine report, dashboard, or marketing list will be late",
            "Severe impact: invoices, billing, finance, regulatory reporting, or a customer-facing product is wrong or blocked",
        ],
    ),
}

CONFIDENCE_FLOOR = 0.6
"""Below this confidence in the cause, a human decides instead of the automation."""
PAGE_THRESHOLD = 1.5
"""Page on-call when the expected impact score (0 to 2) is at least this."""


@dataclass
class Decision:
    action: str
    """One of "retry", "page", "ticket", or "review"."""
    detail: str
    cause: str
    cause_confidence: float
    impact: float


def triage(client: TypeSafeClient, failure: dict) -> Decision:
    """`failure` needs `attempt` and `max_attempts`; every other field is context that Jev reads."""
    response = client.system_one(failure, QUESTIONS)
    cause = response.choices["cause"]
    impact = response.scores["impact"].score

    if cause.choice == "unknown" or cause.confidence < CONFIDENCE_FLOOR:
        action, detail = "review", "the cause is unclear, so a human should look at the logs"
    elif cause.choice in TRANSIENT and failure["attempt"] < failure["max_attempts"]:
        action, detail = "retry", "attempts remain and the cause can clear up by itself"
    elif impact >= PAGE_THRESHOLD:
        action, detail = "page", f"on-call for the {OWNERS[cause.choice]}"
    else:
        action, detail = "ticket", f"for the {OWNERS[cause.choice]}"
    return Decision(action, detail, cause.choice, cause.confidence, impact)
