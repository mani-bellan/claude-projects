"""Composite card components built on top of styling primitives."""

from __future__ import annotations

import streamlit as st

from .styling import rank_badge, tier_badge


def stock_top_card(row: dict) -> None:
    """Glass card for a top-3 stock pick. `row` is a dict from the rec table."""
    cagr = row.get("primary_cagr")
    cagr_pct = f"{cagr * 100:+.1f}%/yr" if cagr is not None else "—"
    vol_pct = f"{(row.get('volatility') or 0) * 100:.1f}%"
    dd_pct = f"{(row.get('max_drawdown') or 0) * 100:.1f}%"

    st.markdown(
        f"""
        <div class="glass-card">
          <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.75rem;">
            {rank_badge(int(row['rank']))}
            <div style="flex:1">
              <div style="font-size:1.4rem; font-weight:700;">{row['ticker']}</div>
              <div style="color:rgba(224,230,237,0.6); font-size:0.85rem;">
                Score <span style="color:#00D9FF; font-weight:700;">{row['score']:.0f}</span>/100 · {tier_badge(row['risk_tier'])}
              </div>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">CAGR {cagr_pct}</span>
            <span class="pill">Vol {vol_pct}</span>
            <span class="pill">Max DD {dd_pct}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def mf_top_card(row: dict) -> None:
    cagr = row.get("primary_cagr")
    cagr_pct = f"{cagr * 100:+.1f}%/yr" if cagr is not None else "—"
    vol_pct = f"{(row.get('volatility') or 0) * 100:.1f}%"
    name = row.get("scheme_name") or f"#{row['scheme_code']}"
    elss = "ELSS" if row.get("is_elss") else (row.get("scheme_category") or "—")

    st.markdown(
        f"""
        <div class="glass-card">
          <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.75rem;">
            {rank_badge(int(row['rank']))}
            <div style="flex:1; min-width:0">
              <div style="font-size:1.05rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{name}</div>
              <div style="color:rgba(224,230,237,0.6); font-size:0.85rem;">
                Score <span style="color:#00D9FF; font-weight:700;">{row['score']:.0f}</span>/100 · {tier_badge(row['risk_tier'])}
              </div>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">CAGR {cagr_pct}</span>
            <span class="pill">Vol {vol_pct}</span>
            <span class="pill">{elss}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
