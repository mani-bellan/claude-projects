"""Mutual fund NAV history via mfapi.in (free wrapper around AMFI)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

import polars as pl
import requests

log = logging.getLogger(__name__)

_NAV_URL = "https://api.mfapi.in/mf/{code}"
_HEADERS = {"User-Agent": "Mozilla/5.0 markets-pipeline/0.1"}


def fetch_navs(scheme_codes: Iterable[int], since: date | None = None) -> pl.DataFrame:
    """Fetch full NAV history for each scheme code. `since` filters by date."""
    rows: list[dict] = []
    for code in scheme_codes:
        try:
            r = requests.get(_NAV_URL.format(code=code), headers=_HEADERS, timeout=20)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            log.warning("mfapi fetch failed for %s: %s", code, e)
            continue

        meta = payload.get("meta", {})
        scheme_name = meta.get("scheme_name", "")
        fund_house = meta.get("fund_house", "")
        scheme_category = meta.get("scheme_category", "")
        scheme_type = meta.get("scheme_type", "")

        for entry in payload.get("data", []):
            try:
                d = datetime.strptime(entry["date"], "%d-%m-%Y").date()
            except (KeyError, ValueError):
                continue
            if since and d < since:
                continue
            try:
                nav = float(entry["nav"])
            except (KeyError, ValueError):
                continue

            rows.append(
                {
                    "scheme_code": int(code),
                    "scheme_name": scheme_name,
                    "fund_house": fund_house,
                    "scheme_category": scheme_category,
                    "scheme_type": scheme_type,
                    "date": d,
                    "nav": nav,
                }
            )

    if not rows:
        return pl.DataFrame(schema=_schema())

    return pl.DataFrame(rows).unique(subset=["scheme_code", "date"], keep="last").sort(
        ["scheme_code", "date"]
    )


def _schema() -> dict:
    return {
        "scheme_code": pl.Int64,
        "scheme_name": pl.Utf8,
        "fund_house": pl.Utf8,
        "scheme_category": pl.Utf8,
        "scheme_type": pl.Utf8,
        "date": pl.Date,
        "nav": pl.Float64,
    }
