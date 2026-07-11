"""Publish a read-only snapshot for the web app.

The website is a thin read layer: it renders web/public/data/places.json,
which this step regenerates from the pipeline DB. No live DB access from
the app — the pipeline owns all writes and business logic.
"""

import json
from datetime import datetime, timezone

from . import config, db

SNAPSHOT_PATH = config.PROJECT_ROOT / "web" / "public" / "data" / "places.json"

LIST_FIELDS = ("pet_types", "amenities")
SCALAR_FIELDS = ("pet_sizes", "seating", "fee")


def _aggregate_policy(evidence_rows: list[dict]) -> dict:
    """Merge extracted_fields across positive evidence into one policy card.
    Lists union; scalars take the most recent non-null value."""
    policy: dict = {f: set() for f in LIST_FIELDS}
    for ev in sorted(evidence_rows, key=lambda e: e["observed_date"] or ""):
        if ev["polarity"] != "positive" or not ev["extracted_fields"]:
            continue
        fields = json.loads(ev["extracted_fields"])
        for f in LIST_FIELDS:
            policy[f].update(fields.get(f) or [])
        for f in SCALAR_FIELDS:
            value = fields.get(f)
            if value and value != "unknown":
                policy[f] = value
    return {k: (sorted(v) if isinstance(v, set) else v)
            for k, v in policy.items() if v}


def build_snapshot(conn) -> dict:
    places = db.rows(conn, """
        SELECT p.*, s.confidence, s.label, s.source_count, s.computed_at
        FROM places p LEFT JOIN scores s ON s.place_id = p.id
        ORDER BY s.confidence DESC NULLS LAST, p.name
    """)
    out = []
    for p in places:
        evidence = db.rows(conn, """
            SELECT claim, source, tier, polarity, observed_date, source_url, extracted_fields
            FROM evidence WHERE place_id=? ORDER BY tier, observed_date DESC
        """, (p["id"],))
        out.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "city": p["city"],
            "address": p["address"],
            "lat": p["lat"], "lng": p["lng"],
            "phone": p["phone"], "website": p["website"],
            "rating": p["rating"], "rating_count": p["rating_count"],
            "label": p["label"] or "unverified",
            "confidence": p["confidence"] or 0.0,
            "policy": _aggregate_policy(evidence),
            "evidence": [
                {"claim": e["claim"], "source": e["source"], "tier": e["tier"],
                 "polarity": e["polarity"], "date": e["observed_date"],
                 "url": e["source_url"]}
                for e in evidence
            ],
            "last_checked": str(p["computed_at"]) if p["computed_at"] else None,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "place_count": len(out),
        "places": out,
    }


def publish(conn) -> int:
    snapshot = build_snapshot(conn)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    print(f"Wrote {snapshot['place_count']} places to {SNAPSHOT_PATH}")
    return snapshot["place_count"]
