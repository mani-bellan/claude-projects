"""Evidence extraction: turn raw review text into structured pet-policy evidence.

Uses Claude (structured outputs via messages.parse) when ANTHROPIC_API_KEY is set;
falls back to a simple keyword heuristic so the pipeline runs offline.
"""

import json
from typing import Literal, Optional

from pydantic import BaseModel

from . import config, db


class PetEvidence(BaseModel):
    mentions_pets: bool
    polarity: Literal["positive", "negative", "neutral"]
    claim: str                      # one-line summary of what the review says about pets
    pet_types: list[str] = []       # e.g. ["dog", "cat"]
    pet_sizes: Optional[str] = None # e.g. "large dogs welcome", "small only"
    seating: Optional[Literal["indoor", "outdoor_only", "both", "unknown"]] = None
    fee: Optional[str] = None       # e.g. "Rs 1000 per night"
    amenities: list[str] = []       # e.g. ["water bowl", "fenced lawn", "pet menu"]


EXTRACTION_SYSTEM = (
    "You extract pet-policy evidence from venue reviews for a pet-friendly "
    "places directory in India. Only report what the review actually says — "
    "never infer pet-friendliness from silence. If the review does not "
    "mention pets at all, set mentions_pets=false and polarity=neutral. "
    "polarity is positive if visitors' pets were welcomed, negative if pets "
    "were refused or restricted in a way that matters to pet parents. "
    "A venue having its own resident pet (a cafe dog or cat) is NOT evidence "
    "that visitors may bring pets — treat that as neutral unless the review "
    "also shows guests' pets being allowed."
)


def extract_with_claude(review_text: str, model: str = config.DEFAULT_EXTRACTION_MODEL) -> PetEvidence:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": f"Review:\n{review_text}"}],
        output_format=PetEvidence,
    )
    return response.parsed_output


POSITIVE_KEYWORDS = ["pet friendly", "pet-friendly", "dogs allowed", "welcomed our",
                     "water bowl", "brought my dog", "took my", "allowed our"]
NEGATIVE_KEYWORDS = ["turned away", "not allowed", "no pets", "refused", "pets not allowed"]
PET_WORDS = ["dog", "pup", "cat", "pet", "retriever", "labrador", "beagle",
             "pomeranian", "indie"]


def extract_with_keywords(review_text: str) -> PetEvidence:
    lower = review_text.lower()
    mentions = any(w in lower for w in PET_WORDS)
    if not mentions:
        return PetEvidence(mentions_pets=False, polarity="neutral", claim="No pet mention")
    if any(k in lower for k in NEGATIVE_KEYWORDS):
        return PetEvidence(mentions_pets=True, polarity="negative",
                           claim="Review reports pets refused or restricted")
    if any(k in lower for k in POSITIVE_KEYWORDS):
        return PetEvidence(mentions_pets=True, polarity="positive",
                           claim="Review reports a positive visit with a pet")
    return PetEvidence(mentions_pets=True, polarity="neutral",
                       claim="Pet mentioned without clear policy signal")


def _store_evidence(conn, row: dict, evidence: PetEvidence, source: str):
    """Store a non-neutral finding and mark the review done."""
    if evidence.mentions_pets and evidence.polarity != "neutral":
        db.add_evidence(
            conn, row["place_id"],
            source=source,
            tier=3,
            polarity=evidence.polarity,
            claim=evidence.claim,
            source_url=row["source_url"],
            observed_date=row["review_date"],
            extracted_fields=evidence.model_dump_json(exclude={"mentions_pets", "polarity", "claim"}),
            raw_text=row["review_text"],
        )
    conn.execute("UPDATE pending_reviews SET processed=1 WHERE id=?", (row["id"],))


def run_extraction(conn, limit: int | None = None,
                   model: str = config.DEFAULT_EXTRACTION_MODEL) -> int:
    """Synchronous extraction — fine for small runs; use batches for whole cities."""
    use_claude = bool(config.ANTHROPIC_API_KEY)
    rows = db.rows(
        conn,
        "SELECT * FROM pending_reviews WHERE processed=0 ORDER BY id"
        + (f" LIMIT {int(limit)}" if limit else "")
    )

    processed = 0
    for row in rows:
        evidence = (extract_with_claude(row["review_text"], model) if use_claude
                    else extract_with_keywords(row["review_text"]))
        _store_evidence(conn, row, evidence,
                        source="google_review" if use_claude else "review_keyword")
        processed += 1
    mode = f"Claude ({model})" if use_claude else "keyword fallback (set ANTHROPIC_API_KEY for Claude extraction)"
    print(f"Processed {processed} reviews using {mode}")
    return processed


# ---------------------------------------------------------------------------
# Batches API path: 50% token discount and no per-request rate limiting.
# Submit now, collect when the batch ends (usually well under an hour).
# ---------------------------------------------------------------------------

def _output_schema() -> dict:
    """PetEvidence as a structured-outputs JSON schema (strict objects)."""
    schema = PetEvidence.model_json_schema()

    def clean(node):
        if isinstance(node, dict):
            node.pop("title", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for v in node.values():
                clean(v)
        elif isinstance(node, list):
            for v in node:
                clean(v)

    clean(schema)
    return schema


def submit_batch(conn, limit: int | None = None,
                 model: str = config.DEFAULT_EXTRACTION_MODEL) -> str | None:
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    rows = db.rows(
        conn,
        "SELECT id, review_text FROM pending_reviews WHERE processed=0 ORDER BY id"
        + (f" LIMIT {int(limit)}" if limit else "")
    )
    if not rows:
        print("No pending reviews to submit.")
        return None

    schema = _output_schema()
    requests = [
        Request(
            custom_id=f"review-{row['id']}",
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=1024,
                system=EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": f"Review:\n{row['review_text']}"}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            ),
        )
        for row in rows
    ]

    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)

    conn.execute(
        "INSERT INTO extraction_batches (batch_id, model, review_count) VALUES (?,?,?)",
        (batch.id, model, len(rows)),
    )
    ids = [r["id"] for r in rows]
    conn.execute(
        f"UPDATE pending_reviews SET processed=2 WHERE id IN ({','.join('?' * len(ids))})",
        ids,
    )
    print(f"Submitted batch {batch.id} with {len(rows)} reviews ({model}, 50% token discount).")
    print("Collect results with: python -m pipeline.run extract --collect")
    return batch.id


def collect_batches(conn) -> dict:
    """Fetch results for in-flight batches; returns per-batch outcome counts."""
    import anthropic

    pending = db.rows(
        conn, "SELECT batch_id FROM extraction_batches WHERE status='in_progress'")
    if not pending:
        print("No in-flight batches.")
        return {}

    client = anthropic.Anthropic()
    stats: dict = {}
    for b in pending:
        batch_id = b["batch_id"]
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status != "ended":
            counts = batch.request_counts
            print(f"{batch_id}: still {batch.processing_status} "
                  f"({counts.processing} processing, {counts.succeeded} succeeded)")
            continue

        succeeded = errored = unparseable = 0
        for result in client.messages.batches.results(batch_id):
            review_id = int(result.custom_id.removeprefix("review-"))
            row = db.one(conn, "SELECT * FROM pending_reviews WHERE id=?", (review_id,))
            if row is None:
                continue
            if result.result.type == "succeeded":
                msg = result.result.message
                text = next((blk.text for blk in msg.content if blk.type == "text"), "")
                try:
                    evidence = PetEvidence.model_validate_json(text)
                except Exception:
                    unparseable += 1
                    conn.execute("UPDATE pending_reviews SET processed=0 WHERE id=?", (review_id,))
                    continue
                _store_evidence(conn, row, evidence, source="google_review")
                succeeded += 1
            else:
                # errored / canceled / expired — return to the pending pool
                errored += 1
                conn.execute("UPDATE pending_reviews SET processed=0 WHERE id=?", (review_id,))

        conn.execute(
            "UPDATE extraction_batches SET status='collected', collected_at=current_timestamp "
            "WHERE batch_id=?", (batch_id,))
        stats[batch_id] = {"succeeded": succeeded, "errored": errored,
                           "unparseable": unparseable}
        print(f"{batch_id}: {succeeded} succeeded, {errored} errored, "
              f"{unparseable} unparseable (failures returned to pending pool)")
    return stats
