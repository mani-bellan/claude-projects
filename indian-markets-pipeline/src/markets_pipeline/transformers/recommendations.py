"""Long-term first-time-investor scoring.

Score = weighted percentile-rank across four pillars:

    40%  returns      (best-available CAGR — prefers 5y, falls back to 3y/1y)
    30%  stability    (inverse annualized volatility)
    20%  drawdown     (less-negative max drawdown)
    10%  longevity    (years of price history)

Each pillar is a 0..100 percentile within the universe being scored, so the
weights compose to a 0..100 final score. Risk tier is derived from the
stability pillar only (so a flashy high-CAGR stock can still be tagged HIGH).
"""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

WEIGHTS = {
    "returns": 0.40,
    "stability": 0.30,
    "drawdown": 0.20,
    "longevity": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def score_universe(features: pl.DataFrame, key: str) -> pl.DataFrame:
    """Return `features` augmented with pillars, score, rank, risk tier, rationale."""
    if features.is_empty():
        return features

    f = features.with_columns(
        pl.coalesce(
            [pl.col("cagr_5y"), pl.col("cagr_3y"), pl.col("cagr_1y"), pl.col("annualized_return")]
        ).alias("primary_cagr")
    )

    n = f.height
    f = f.with_columns(
        [
            _percentile("primary_cagr", n, ascending=True).alias("pillar_returns"),
            _percentile("volatility", n, ascending=False).alias("pillar_stability"),
            # max_drawdown is negative; less-negative is better => ascending rank.
            _percentile("max_drawdown", n, ascending=True).alias("pillar_drawdown"),
            _percentile("years_history", n, ascending=True).alias("pillar_longevity"),
        ]
    )

    f = f.with_columns(
        (
            pl.col("pillar_returns").fill_null(50) * WEIGHTS["returns"]
            + pl.col("pillar_stability").fill_null(50) * WEIGHTS["stability"]
            + pl.col("pillar_drawdown").fill_null(50) * WEIGHTS["drawdown"]
            + pl.col("pillar_longevity").fill_null(50) * WEIGHTS["longevity"]
        ).alias("score")
    )

    f = f.with_columns(
        pl.when(pl.col("pillar_stability") >= 67)
        .then(pl.lit("LOW"))
        .when(pl.col("pillar_stability") >= 34)
        .then(pl.lit("MEDIUM"))
        .otherwise(pl.lit("HIGH"))
        .alias("risk_tier")
    )

    f = f.with_columns(
        pl.col("score").rank(method="ordinal", descending=True).cast(pl.Int32).alias("rank")
    )

    f = f.with_columns(_rationale_expr().alias("rationale"))

    return f.with_columns(pl.lit(_now_ts()).alias("computed_at"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _percentile(col: str, n: int, *, ascending: bool) -> pl.Expr:
    """Convert a numeric column into a 0..100 percentile rank.

    `ascending=True` -> larger values get higher percentile (good for CAGR).
    `ascending=False` -> smaller values get higher percentile (good for volatility).
    NULLs propagate (no rank assigned).
    """
    if n == 0:
        return pl.lit(None, dtype=pl.Float64)
    expr = pl.col(col)
    if not ascending:
        expr = -expr
    return (expr.rank(method="average") * 100.0 / n).alias(col)


def _rationale_expr() -> pl.Expr:
    """Cheap template-based rationale string. Phase 5 can swap in LLM output."""
    return (
        pl.format(
            "Returns {}, stability {}, drawdown {}, track record {}",
            _label("pillar_returns"),
            _label("pillar_stability"),
            _label("pillar_drawdown"),
            _label("pillar_longevity"),
        )
    )


def _label(col: str) -> pl.Expr:
    p = pl.col(col)
    return (
        pl.when(p >= 80)
        .then(pl.lit("excellent"))
        .when(p >= 60)
        .then(pl.lit("strong"))
        .when(p >= 40)
        .then(pl.lit("average"))
        .when(p >= 20)
        .then(pl.lit("weak"))
        .otherwise(pl.lit("poor"))
    )


def _now_ts():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Convenience wrappers used by the CLI / DAG.
# ---------------------------------------------------------------------------


def stock_recommendations(features: pl.DataFrame) -> pl.DataFrame:
    return score_universe(features, key="ticker").select(
        [
            "ticker",
            "rank",
            "score",
            "pillar_returns",
            "pillar_stability",
            "pillar_drawdown",
            "pillar_longevity",
            "risk_tier",
            "rationale",
            "primary_cagr",
            "volatility",
            "max_drawdown",
            "years_history",
            "computed_at",
        ]
    )


def mf_recommendations(features: pl.DataFrame) -> pl.DataFrame:
    f = score_universe(features, key="scheme_code")
    f = f.with_columns(
        pl.col("scheme_category").str.contains("(?i)elss|tax").fill_null(False).alias("is_elss")
    )
    return f.select(
        [
            "scheme_code",
            "scheme_name",
            "scheme_category",
            "fund_house",
            "is_elss",
            "rank",
            "score",
            "pillar_returns",
            "pillar_stability",
            "pillar_drawdown",
            "pillar_longevity",
            "risk_tier",
            "rationale",
            "primary_cagr",
            "volatility",
            "max_drawdown",
            "years_history",
            "computed_at",
        ]
    )
