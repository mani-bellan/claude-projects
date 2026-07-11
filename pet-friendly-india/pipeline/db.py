from pathlib import Path

import duckdb

from . import config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Set by connect(): whether the DuckDB spatial extension loaded successfully.
# When False, geo queries fall back to a plain-SQL haversine (see run.py).
SPATIAL_ENABLED = False


def connect() -> duckdb.DuckDBPyConnection:
    global SPATIAL_ENABLED
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(config.DB_PATH))
    try:
        conn.execute("INSTALL spatial")
        conn.execute("LOAD spatial")
        SPATIAL_ENABLED = True
    except duckdb.Error:
        SPATIAL_ENABLED = False  # offline / install failed; haversine fallback
    conn.execute(SCHEMA_PATH.read_text())
    return conn


def rows(conn, sql: str, params=()) -> list[dict]:
    """Run a query and return rows as dicts (DuckDB returns plain tuples)."""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(conn, sql: str, params=()) -> dict | None:
    result = rows(conn, sql, params)
    return result[0] if result else None


def upsert_place(conn, place: dict) -> int:
    """Insert or update a place keyed on google_place_id; returns place id."""
    if place.get("google_place_id"):
        row = one(conn, "SELECT id FROM places WHERE google_place_id = ?",
                  (place["google_place_id"],))
        if row:
            conn.execute(
                """UPDATE places SET name=?, category=?, address=?, city=COALESCE(?, city),
                   lat=?, lng=?, phone=?, website=?, rating=?, rating_count=?,
                   updated_at=current_timestamp
                   WHERE id=?""",
                (
                    place["name"], place.get("category"), place.get("address"),
                    place.get("city"), place.get("lat"), place.get("lng"),
                    place.get("phone"), place.get("website"), place.get("rating"),
                    place.get("rating_count"), row["id"],
                ),
            )
            return row["id"]
    else:
        # Sample data has no google_place_id — dedupe on name so re-ingest is idempotent.
        row = one(conn, "SELECT id FROM places WHERE name = ? AND google_place_id IS NULL",
                  (place["name"],))
        if row:
            return row["id"]
    cur = conn.execute(
        """INSERT INTO places (google_place_id, name, category, address, city, lat, lng,
           phone, website, rating, rating_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
        (
            place.get("google_place_id"), place["name"], place.get("category"),
            place.get("address"), place.get("city"), place.get("lat"), place.get("lng"),
            place.get("phone"), place.get("website"), place.get("rating"),
            place.get("rating_count"),
        ),
    )
    return cur.fetchone()[0]


def add_evidence(conn, place_id, source, tier, polarity, claim,
                 source_url=None, observed_date=None, extracted_fields=None, raw_text=None):
    conn.execute(
        """INSERT INTO evidence (place_id, source, tier, polarity, claim, source_url,
           observed_date, extracted_fields, raw_text)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (place_id, source, tier, polarity, claim, source_url,
         observed_date, extracted_fields, raw_text),
    )


def add_pending_review(conn, place_id, review_text, review_date=None, source_url=None):
    # Skip exact duplicates so re-ingesting doesn't double-count evidence.
    row = conn.execute(
        "SELECT 1 FROM pending_reviews WHERE place_id=? AND review_text=?",
        (place_id, review_text),
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO pending_reviews (place_id, review_text, review_date, source_url) VALUES (?,?,?,?)",
            (place_id, review_text, review_date, source_url),
        )
