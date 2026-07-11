"""One-command ETL: extract from sources, transform to evidence, load + publish.

Chains the existing pipeline stages end-to-end so a city refresh is a single run:

  Extract    ingest      Google Places API (New) text searches -> places + raw reviews
  Transform  websites    venue-site fetch + Claude pet-policy extraction (tier 1)
             extract     review text -> structured PetEvidence via Claude (tier 3)
             score       tier weights x recency decay x corroboration -> labels
  Load       publish     read-only snapshot for the web app (places.json)

Usage:
  python -m pipeline.etl --city Mysore           # full run, polls until batch ends
  python -m pipeline.etl --city Mysore --no-wait # submit batch and exit; resume later
  python -m pipeline.etl --resume                # collect in-flight batches, score, publish
  python -m pipeline.etl --sample                # offline demo run (no API keys needed)
  python -m pipeline.etl --city Mysore --sync    # synchronous extraction, no Batches API

Without ANTHROPIC_API_KEY the websites stage is skipped and extraction falls back
to keywords; without GOOGLE_MAPS_API_KEY ingest falls back to sample data.
"""

import argparse
import sys
import time

from . import config, db, extract, ingest, publish, score, websites


def _banner(stage: str):
    print(f"\n=== {stage} " + "=" * max(0, 60 - len(stage)))


def stage_ingest(conn, args) -> None:
    _banner("EXTRACT: ingest places from Google Places API")
    if args.sample or not config.GOOGLE_MAPS_API_KEY:
        if not args.sample:
            print("No GOOGLE_MAPS_API_KEY set — using bundled sample data.")
        n = ingest.ingest_sample(conn)
        print(f"Ingested {n} sample places.")
    elif args.city:
        n, calls = ingest.ingest_city(conn, args.city)
        print(f"Ingested {n} place results ({calls} API calls) for {args.city}.")
    else:
        n = ingest.ingest_google(conn, args.query)
        print(f"Ingested {n} places for query: {args.query!r}")


def stage_websites(conn, args) -> None:
    _banner("TRANSFORM: tier-1 venue-website policy checks")
    if not config.ANTHROPIC_API_KEY:
        print("Skipped (ANTHROPIC_API_KEY not set).")
        return
    outcomes = websites.run_website_checks(conn, limit=args.website_limit)
    print(f"Checked {sum(outcomes.values())} websites: {outcomes}")


def stage_extract(conn, args) -> bool:
    """Run review extraction. Returns False if a batch is still in flight
    (i.e. score/publish should be deferred to a --resume run)."""
    _banner("TRANSFORM: review-text evidence extraction")
    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY not set — using keyword fallback extraction.")
        extract.run_extraction(conn, limit=args.limit)
        return True
    if args.sync:
        extract.run_extraction(conn, limit=args.limit, model=args.model)
        return True

    batch_id = extract.submit_batch(conn, limit=args.limit, model=args.model)
    if batch_id is None:  # nothing pending — maybe an earlier batch is in flight
        return wait_for_batches(conn, args) if not args.no_wait else not _in_flight(conn)
    if args.no_wait:
        print("\nBatch submitted. Finish later with: python -m pipeline.etl --resume")
        return False
    return wait_for_batches(conn, args)


def _in_flight(conn) -> bool:
    return db.one(
        conn, "SELECT 1 FROM extraction_batches WHERE status='in_progress' LIMIT 1"
    ) is not None


def wait_for_batches(conn, args) -> bool:
    """Poll the Batches API until all in-flight batches are collected."""
    if not _in_flight(conn):
        print("No in-flight batches.")
        return True
    deadline = time.time() + args.max_wait_minutes * 60
    print(f"Waiting for batch results (polling every {args.poll_minutes} min, "
          f"up to {args.max_wait_minutes} min — usually well under an hour)...")
    while True:
        extract.collect_batches(conn)
        if not _in_flight(conn):
            return True
        if time.time() >= deadline:
            print(f"\nStill in flight after {args.max_wait_minutes} min. "
                  "Finish later with: python -m pipeline.etl --resume")
            return False
        time.sleep(args.poll_minutes * 60)


def stage_score_publish(conn) -> None:
    _banner("TRANSFORM: confidence scoring")
    n = score.compute_scores(conn)
    print(f"Scored {n} places.")
    _banner("LOAD: publish snapshot for the web app")
    publish.publish(conn)


def main():
    parser = argparse.ArgumentParser(
        prog="pipeline.etl",
        description="End-to-end ETL: ingest -> websites -> extract -> score -> publish")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--city", help="Fan out locality x category queries for a whole city")
    src.add_argument("--query", help="Single ad-hoc text search instead of a city")
    src.add_argument("--sample", action="store_true", help="Use bundled sample data (offline)")
    src.add_argument("--resume", action="store_true",
                     help="Skip ingest/websites; collect in-flight batches, then score + publish")
    parser.add_argument("--sync", action="store_true",
                        help="Extract synchronously instead of via the Batches API")
    parser.add_argument("--no-wait", action="store_true",
                        help="Submit the extraction batch and exit (resume with --resume)")
    parser.add_argument("--model", default=config.DEFAULT_EXTRACTION_MODEL,
                        help="Claude model for extraction")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max reviews to extract this run")
    parser.add_argument("--website-limit", type=int, default=None,
                        help="Max venue websites to check this run")
    parser.add_argument("--poll-minutes", type=float, default=5,
                        help="Minutes between batch status checks (default 5)")
    parser.add_argument("--max-wait-minutes", type=float, default=90,
                        help="Give up polling after this long (default 90)")
    parser.add_argument("--skip-websites", action="store_true",
                        help="Skip the venue-website stage")
    parser.add_argument("--no-llm", action="store_true",
                        help="Guarantee zero Anthropic API usage: skip website checks, "
                             "use keyword extraction even if ANTHROPIC_API_KEY is set")
    args = parser.parse_args()

    if args.no_llm:
        # All stages read this at call time, so blanking it forces the
        # keyword-extraction fallback and skips the website stage.
        config.ANTHROPIC_API_KEY = ""

    if not (args.city or args.query or args.sample or args.resume):
        parser.error("pick a source: --city CITY, --query Q, --sample, or --resume")

    conn = db.connect()  # single connection: DuckDB is single-writer

    if args.resume:
        if not wait_for_batches(conn, args):
            sys.exit(1)
    else:
        stage_ingest(conn, args)
        if not args.skip_websites:
            stage_websites(conn, args)
        if not stage_extract(conn, args):
            sys.exit(0)  # batch in flight; score/publish happen on --resume

    stage_score_publish(conn)
    _banner("DONE")
    print("Review results:  python -m pipeline.run report")
    print("View in app:     cd web && npm run dev")


if __name__ == "__main__":
    main()
