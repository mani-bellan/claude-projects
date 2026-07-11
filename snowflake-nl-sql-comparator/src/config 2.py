"""Centralized config loaded from .env. Fail fast on missing required vars."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var {name} (see .env.example)")
    return value


@dataclass(frozen=True)
class Config:
    sf_account: str
    sf_user: str
    sf_password: str
    sf_warehouse: str
    sf_database: str
    sf_schema: str
    sf_role: str | None
    sf_stage: str
    anthropic_api_key: str
    run_log_table: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            sf_account=_require("SNOWFLAKE_ACCOUNT"),
            sf_user=_require("SNOWFLAKE_USER"),
            sf_password=_require("SNOWFLAKE_PASSWORD"),
            sf_warehouse=_require("SNOWFLAKE_WAREHOUSE"),
            sf_database=_require("SNOWFLAKE_DATABASE"),
            sf_schema=_require("SNOWFLAKE_SCHEMA"),
            sf_role=os.environ.get("SNOWFLAKE_ROLE"),
            sf_stage=_require("SNOWFLAKE_STAGE"),
            anthropic_api_key=_require("ANTHROPIC_API_KEY"),
            run_log_table=os.environ.get("RUN_LOG_TABLE", "NL_SQL_COMPARATOR_RUNS"),
        )
