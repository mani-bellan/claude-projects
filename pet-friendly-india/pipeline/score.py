"""Confidence scoring: tier weights × recency decay, corroboration bonus,
heavy penalty for negative evidence."""

import math
from datetime import date, datetime

from . import config, db


def _recency_factor(observed_date: str | None) -> float:
    if not observed_date:
        return 0.6  # undated evidence is worth less but not nothing
    try:
        observed = datetime.strptime(observed_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0.6
    age_days = max((date.today() - observed).days, 0)
    return 0.5 ** (age_days / config.DECAY_HALF_LIFE_DAYS)


def compute_scores(conn) -> int:
    places = db.rows(conn, "SELECT id FROM places")
    for place in places:
        rows = db.rows(
            conn,
            "SELECT source, tier, polarity, observed_date FROM evidence WHERE place_id=?",
            (place["id"],),
        )

        positive, negative = 0.0, 0.0
        sources = set()
        for r in rows:
            weight = config.TIER_WEIGHTS.get(r["tier"], 0.3) * _recency_factor(r["observed_date"])
            if r["polarity"] == "positive":
                positive += weight
                sources.add(r["source"])
            elif r["polarity"] == "negative":
                negative += weight

        # Corroboration: independent sources agreeing matters more than volume
        # from one source. Saturating curve keeps the score in [0, 1).
        corroboration = 1 + 0.25 * (len(sources) - 1) if sources else 1
        raw = positive * corroboration
        confidence = 1 - math.exp(-raw)

        # A recent "we were turned away" outweighs older positive signals.
        confidence = max(confidence - 1.5 * negative, 0.0)

        if not rows:
            label = "unverified"
        elif confidence >= config.VERIFIED_THRESHOLD:
            label = "verified"
        elif confidence >= config.LIKELY_THRESHOLD:
            label = "likely"
        else:
            label = "unverified"

        conn.execute(
            """INSERT INTO scores (place_id, confidence, label, evidence_count, source_count, computed_at)
               VALUES (?,?,?,?,?,current_timestamp)
               ON CONFLICT(place_id) DO UPDATE SET confidence=excluded.confidence,
                 label=excluded.label, evidence_count=excluded.evidence_count,
                 source_count=excluded.source_count, computed_at=excluded.computed_at""",
            (place["id"], round(confidence, 3), label, len(rows), len(sources)),
        )
    return len(places)
