"""Snowflake Cortex Analyst runner: POST /api/v2/cortex/analyst/message → JSON with SQL.

Cortex Analyst returns SQL only (not results). We execute the returned SQL via our
own snowflake_client for parity with the Claude runner — both runners produce SQL,
the same code executes both, so the comparison isolates SQL-generation quality.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Config
from .snowflake_client import QueryResult, SnowflakeClient


@dataclass
class CortexAnalystResult:
    question: str
    final_sql: str | None
    final_result: QueryResult | None
    explanation: str
    elapsed_ms: int
    request_id: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class CortexAnalystRunner:
    """Drives Snowflake's Cortex Analyst REST API.

    Endpoint: /api/v2/cortex/analyst/message
    Auth:     scoped service token (CORTEX_ANALYST scope)
    Returns:  JSON with content blocks of type 'text' | 'sql' | 'suggestions'
    """

    def __init__(self, cfg: Config, sf: SnowflakeClient, semantic_model_stage_path: str):
        self.cfg = cfg
        self.sf = sf
        self.stage_path = semantic_model_stage_path

    def ask(self, question: str) -> CortexAnalystResult:
        start = time.perf_counter()

        try:
            auth_header = self.sf.cortex_rest_auth_header()
        except Exception as e:
            return CortexAnalystResult(
                question=question,
                final_sql=None,
                final_result=None,
                explanation="",
                elapsed_ms=int((time.perf_counter() - start) * 1000),
                error=f"Failed to obtain Snowflake auth token: {e}",
            )

        url = (
            f"https://{self.cfg.sf_account}.snowflakecomputing.com"
            f"/api/v2/cortex/analyst/message"
        )
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ],
            "semantic_model_file": self.stage_path,
        }

        raw: dict[str, Any] = {}
        sql: str | None = None
        explanation_parts: list[str] = []
        suggestions: list[str] = []
        request_id: str | None = None
        error: str | None = None

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, headers=headers, json=payload)
                request_id = resp.headers.get("x-snowflake-request-id")
                if resp.status_code != 200:
                    return CortexAnalystResult(
                        question=question,
                        final_sql=None,
                        final_result=None,
                        explanation="",
                        elapsed_ms=int((time.perf_counter() - start) * 1000),
                        request_id=request_id,
                        error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                    )
                raw = resp.json()
        except httpx.HTTPError as e:
            return CortexAnalystResult(
                question=question,
                final_sql=None,
                final_result=None,
                explanation="",
                elapsed_ms=int((time.perf_counter() - start) * 1000),
                error=f"HTTP error calling Cortex Analyst: {e}",
            )

        # Response: { message: { content: [ { type: 'text' | 'sql' | 'suggestions', ... } ] } }
        for block in raw.get("message", {}).get("content", []):
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                if text:
                    explanation_parts.append(text)
            elif btype == "sql":
                sql = block.get("statement")
            elif btype == "suggestions":
                # Analyst is asking for clarification rather than producing SQL
                for s in block.get("suggestions", []):
                    suggestions.append(s)

        if suggestions:
            explanation_parts.append(
                "Cortex Analyst suggested clarifying questions:\n"
                + "\n".join(f"- {s}" for s in suggestions)
            )

        # Execute the returned SQL via our snowflake_client for parity with Claude.
        final_result: QueryResult | None = None
        if sql:
            final_result = self.sf.execute(sql)
            if final_result.error:
                error = f"SQL executed but failed: {final_result.error}"
        elif not error:
            error = "Cortex Analyst did not return a SQL statement."

        elapsed = int((time.perf_counter() - start) * 1000)
        return CortexAnalystResult(
            question=question,
            final_sql=sql,
            final_result=final_result,
            explanation="\n\n".join(p for p in explanation_parts if p).strip(),
            elapsed_ms=elapsed,
            request_id=request_id,
            raw_response=raw,
            error=error,
        )
