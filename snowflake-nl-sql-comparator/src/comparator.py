"""Compare two query results: row-set equality + structural diff."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .claude_runner import ClaudeRunResult
from .cortex_runner import CortexAnalystResult


@dataclass
class Comparison:
    rows_match: bool
    columns_match: bool
    row_count_claude: int
    row_count_cortex: int
    claude_only_rows: int
    cortex_only_rows: int
    detail: str


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Sort columns + rows so equality is order-independent."""
    if df.empty:
        return df
    out = df.copy()
    out.columns = [c.upper() for c in out.columns]
    out = out.reindex(sorted(out.columns), axis=1)
    # Stringify everything for comparison (avoid float/int/Decimal mismatches)
    out = out.astype(str)
    try:
        out = out.sort_values(by=list(out.columns)).reset_index(drop=True)
    except Exception:
        pass
    return out


def compare(claude: ClaudeRunResult, cortex: CortexAnalystResult) -> Comparison:
    cdf = claude.final_result.rows if claude.final_result is not None else pd.DataFrame()
    xdf = cortex.final_result.rows if cortex.final_result is not None else pd.DataFrame()

    cdn = _normalize(cdf)
    xdn = _normalize(xdf)

    columns_match = set(cdn.columns) == set(xdn.columns)

    if cdn.empty and xdn.empty:
        return Comparison(
            rows_match=False,
            columns_match=False,
            row_count_claude=0,
            row_count_cortex=0,
            claude_only_rows=0,
            cortex_only_rows=0,
            detail="Neither runner produced rows.",
        )

    if not columns_match:
        return Comparison(
            rows_match=False,
            columns_match=False,
            row_count_claude=len(cdf),
            row_count_cortex=len(xdf),
            claude_only_rows=len(cdf),
            cortex_only_rows=len(xdf),
            detail=(
                f"Column sets differ. Claude: {sorted(cdn.columns)}; "
                f"Cortex: {sorted(xdn.columns)}"
            ),
        )

    # Row-set comparison via merge indicator
    merged = cdn.merge(xdn, how="outer", indicator=True)
    claude_only = int((merged["_merge"] == "left_only").sum())
    cortex_only = int((merged["_merge"] == "right_only").sum())
    rows_match = claude_only == 0 and cortex_only == 0

    return Comparison(
        rows_match=rows_match,
        columns_match=True,
        row_count_claude=len(cdf),
        row_count_cortex=len(xdf),
        claude_only_rows=claude_only,
        cortex_only_rows=cortex_only,
        detail=(
            "Row sets match." if rows_match
            else f"{claude_only} rows only in Claude, {cortex_only} only in Cortex."
        ),
    )
