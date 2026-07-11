"""Recommendation scoring tests."""

from __future__ import annotations

from datetime import date

import polars as pl

from markets_pipeline.transformers import recommendations


def _features_frame(rows: list[dict]) -> pl.DataFrame:
    """Build a feature frame matching the columns score_universe expects."""
    base = {
        "ticker": [],
        "first_date": [],
        "last_date": [],
        "observations": [],
        "years_history": [],
        "latest_price": [],
        "annualized_return": [],
        "volatility": [],
        "sharpe": [],
        "max_drawdown": [],
        "cagr_1y": [],
        "cagr_3y": [],
        "cagr_5y": [],
        "cagr_10y": [],
        "computed_at": [],
    }
    for r in rows:
        for k in base:
            base[k].append(r.get(k))
    return pl.DataFrame(base)


def _row(ticker, cagr_5y, vol, dd, years):
    return {
        "ticker": ticker,
        "first_date": date(2010, 1, 1),
        "last_date": date(2024, 1, 1),
        "observations": 3500,
        "years_history": years,
        "latest_price": 100.0,
        "annualized_return": cagr_5y,
        "volatility": vol,
        "sharpe": (cagr_5y - 0.06) / vol if vol > 0 else None,
        "max_drawdown": dd,
        "cagr_1y": cagr_5y,
        "cagr_3y": cagr_5y,
        "cagr_5y": cagr_5y,
        "cagr_10y": None,
        "computed_at": None,
    }


class TestRanking:
    def test_higher_cagr_lower_vol_outranks_lower_cagr_higher_vol(self):
        df = _features_frame(
            [
                _row("GOOD", cagr_5y=0.18, vol=0.15, dd=-0.12, years=14),
                _row("BAD", cagr_5y=0.05, vol=0.40, dd=-0.55, years=14),
            ]
        )
        out = recommendations.score_universe(df, key="ticker").sort("rank")
        assert out["ticker"].to_list() == ["GOOD", "BAD"]
        assert out["score"][0] > out["score"][1]


class TestRiskTier:
    def test_lowest_volatility_is_low_risk(self):
        df = _features_frame(
            [
                _row("LOW_VOL", cagr_5y=0.10, vol=0.10, dd=-0.10, years=10),
                _row("MID_VOL", cagr_5y=0.12, vol=0.20, dd=-0.20, years=10),
                _row("HIGH_VOL", cagr_5y=0.15, vol=0.40, dd=-0.40, years=10),
            ]
        )
        out = recommendations.score_universe(df, key="ticker").sort("ticker")
        tier = dict(zip(out["ticker"].to_list(), out["risk_tier"].to_list()))
        assert tier["LOW_VOL"] == "LOW"
        assert tier["HIGH_VOL"] == "HIGH"


class TestPillarsBounded:
    def test_pillars_are_between_0_and_100(self):
        df = _features_frame(
            [
                _row("A", 0.10, 0.15, -0.20, 10),
                _row("B", 0.08, 0.18, -0.25, 8),
                _row("C", 0.12, 0.12, -0.18, 12),
                _row("D", 0.20, 0.30, -0.40, 4),
            ]
        )
        out = recommendations.score_universe(df, key="ticker")
        for col in ["pillar_returns", "pillar_stability", "pillar_drawdown", "pillar_longevity"]:
            assert out[col].min() >= 0
            assert out[col].max() <= 100
        assert out["score"].min() >= 0
        assert out["score"].max() <= 100


class TestWeightsSumToOne:
    def test_weights_total_one(self):
        assert abs(sum(recommendations.WEIGHTS.values()) - 1.0) < 1e-9


class TestRationalePresent:
    def test_rationale_string_includes_keywords(self):
        df = _features_frame([_row("ONE", 0.10, 0.15, -0.20, 10)])
        out = recommendations.score_universe(df, key="ticker")
        rationale = out["rationale"][0]
        assert "Returns" in rationale
        assert "stability" in rationale
