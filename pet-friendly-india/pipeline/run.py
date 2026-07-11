"""CLI for the pet-friendly-india pipeline.

  python -m pipeline.run ingest --query "pet friendly cafes in Indiranagar Bangalore"
  python -m pipeline.run ingest --sample
  python -m pipeline.run extract
  python -m pipeline.run score
  python -m pipeline.run report [--label verified|likely|unverified]
  python -m pipeline.run nearby --lat 12.9719 --lng 77.6412 --radius-km 10
"""

import argparse
import json

from . import config, db, extract, ingest, publish, score, websites


def cmd_ingest(args):
    conn = db.connect()
    if args.sample or not config.GOOGLE_MAPS_API_KEY:
        if not args.sample:
            print("No GOOGLE_MAPS_API_KEY set — using bundled sample data.")
        n = ingest.ingest_sample(conn)
        print(f"Ingested {n} sample places.")
    elif args.city:
        n, calls = ingest.ingest_city(conn, args.city)
        print(f"\nIngested {n} place results ({calls} API calls) for {args.city}. "
              "Duplicates across queries were merged on Place ID.")
        print("Next: python -m pipeline.run extract && python -m pipeline.run score")
    else:
        n = ingest.ingest_google(conn, args.query)
        print(f"Ingested {n} places from Google Places for query: {args.query!r}")


def cmd_extract(args):
    conn = db.connect()
    if args.collect:
        if extract.collect_batches(conn):
            print("Run `score` then `publish` to fold new evidence into the app.")
    elif args.batch:
        if not config.ANTHROPIC_API_KEY:
            print("ANTHROPIC_API_KEY required for batch submission.")
            return
        extract.submit_batch(conn, limit=args.limit, model=args.model)
    else:
        extract.run_extraction(conn, limit=args.limit, model=args.model)


def cmd_websites(args):
    conn = db.connect()
    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY required for website policy extraction.")
        return
    outcomes = websites.run_website_checks(conn, limit=args.limit)
    total = sum(outcomes.values())
    print(f"\nChecked {total} websites: {outcomes}")
    if outcomes.get("policy_found"):
        print("Run `score` to fold the new tier-1 evidence into confidence scores.")


def cmd_score(_args):
    conn = db.connect()
    n = score.compute_scores(conn)
    print(f"Scored {n} places.")


def cmd_publish(_args):
    conn = db.connect()
    publish.publish(conn)


def cmd_report(args):
    conn = db.connect()
    query = """
        SELECT p.name, p.category, p.city, s.label, s.confidence,
               s.evidence_count, s.source_count, p.id AS place_id
        FROM places p LEFT JOIN scores s ON s.place_id = p.id
    """
    params = ()
    if args.label:
        query += " WHERE s.label = ?"
        params = (args.label,)
    query += " ORDER BY s.confidence DESC NULLS LAST"
    rows = db.rows(conn, query, params)

    if not rows:
        print("No places found. Run `ingest`, `extract`, and `score` first.")
        return

    label_marks = {"verified": "✅", "likely": "🟡", "unverified": "❓"}
    print(f"\n{'':2} {'Place':<42} {'Type':<10} {'City':<10} {'Conf':>5}  Evidence")
    print("-" * 90)
    for r in rows:
        mark = label_marks.get(r["label"], "❓")
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "-"
        ev = f"{r['evidence_count'] or 0} items / {r['source_count'] or 0} sources"
        print(f"{mark:2} {r['name']:<42.42} {r['category'] or '-':<10} {r['city'] or '-':<10} {conf:>5}  {ev}")

    if args.verbose:
        print("\nEvidence detail:")
        for r in rows:
            ev_rows = db.rows(
                conn,
                "SELECT source, tier, polarity, claim, observed_date, extracted_fields "
                "FROM evidence WHERE place_id=? ORDER BY tier", (r["place_id"],),
            )
            if not ev_rows:
                continue
            print(f"\n  {r['name']}")
            for e in ev_rows:
                fields = ""
                if e["extracted_fields"]:
                    parsed = {k: v for k, v in json.loads(e["extracted_fields"]).items() if v}
                    if parsed:
                        fields = f"  {parsed}"
                sign = "+" if e["polarity"] == "positive" else "-"
                print(f"   {sign} [tier {e['tier']}] {e['claim']} "
                      f"({e['source']}, {e['observed_date'] or 'undated'}){fields}")


def cmd_nearby(args):
    conn = db.connect()
    if db.SPATIAL_ENABLED:
        # DuckDB spatial's *_Sphere functions expect ST_Point(lat, lng) axis
        # order (verified: Indiranagar->Koramangala = 4.46 km). Returns meters.
        dist_expr = "ST_Distance_Sphere(ST_Point(p.lat, p.lng), ST_Point(?, ?)) / 1000.0"
        dist_params = (args.lat, args.lng)
    else:
        dist_expr = """2 * 6371 * asin(sqrt(
            pow(sin(radians(p.lat - ?) / 2), 2) +
            cos(radians(?)) * cos(radians(p.lat)) * pow(sin(radians(p.lng - ?) / 2), 2)))"""
        dist_params = (args.lat, args.lat, args.lng)

    query = f"""
        SELECT p.name, p.category, p.city, s.label, s.confidence,
               {dist_expr} AS km
        FROM places p LEFT JOIN scores s ON s.place_id = p.id
        WHERE p.lat IS NOT NULL AND km <= ?
    """
    params = [*dist_params, args.radius_km]
    if args.label:
        query += " AND s.label = ?"
        params.append(args.label)
    query += " ORDER BY km"
    results = db.rows(conn, query, params)

    if not results:
        print(f"No places within {args.radius_km} km. Try a larger --radius-km.")
        return

    engine = "spatial extension" if db.SPATIAL_ENABLED else "haversine fallback"
    label_marks = {"verified": "✅", "likely": "🟡", "unverified": "❓"}
    print(f"\nWithin {args.radius_km} km of ({args.lat}, {args.lng})  [{engine}]")
    print(f"{'':2} {'Place':<42} {'Type':<10} {'Km':>6} {'Conf':>5}")
    print("-" * 72)
    for r in results:
        mark = label_marks.get(r["label"], "❓")
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "-"
        print(f"{mark:2} {r['name']:<42.42} {r['category'] or '-':<10} {r['km']:>6.1f} {conf:>5}")


def main():
    parser = argparse.ArgumentParser(prog="pipeline.run")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Discover candidate places")
    p_ingest.add_argument("--city", help="Fan out locality x category queries for a whole city")
    p_ingest.add_argument("--query", default="pet friendly cafes in Bangalore",
                          help="Single ad-hoc text search (ignored if --city is set)")
    p_ingest.add_argument("--sample", action="store_true", help="Use bundled sample data")
    p_ingest.set_defaults(func=cmd_ingest)

    p_extract = sub.add_parser("extract", help="Extract evidence from pending reviews")
    p_extract.add_argument("--limit", type=int, default=None)
    p_extract.add_argument("--model", default=config.DEFAULT_EXTRACTION_MODEL,
                           help="Claude model for extraction (e.g. claude-opus-4-8 for max quality)")
    p_extract.add_argument("--batch", action="store_true",
                           help="Submit via the Batches API (50%% cheaper, results within ~1h)")
    p_extract.add_argument("--collect", action="store_true",
                           help="Fetch results of in-flight batches")
    p_extract.set_defaults(func=cmd_extract)

    p_websites = sub.add_parser("websites", help="Tier-1 evidence from venue websites")
    p_websites.add_argument("--limit", type=int, default=None)
    p_websites.set_defaults(func=cmd_websites)

    p_score = sub.add_parser("score", help="Recompute confidence scores")
    p_score.set_defaults(func=cmd_score)

    p_publish = sub.add_parser("publish", help="Write web/public/data/places.json snapshot")
    p_publish.set_defaults(func=cmd_publish)

    p_report = sub.add_parser("report", help="Show scored places")
    p_report.add_argument("--label", choices=["verified", "likely", "unverified"])
    p_report.add_argument("--verbose", "-v", action="store_true", help="Show evidence per place")
    p_report.set_defaults(func=cmd_report)

    p_nearby = sub.add_parser("nearby", help="Geo search: places within a radius")
    p_nearby.add_argument("--lat", type=float, required=True)
    p_nearby.add_argument("--lng", type=float, required=True)
    p_nearby.add_argument("--radius-km", type=float, default=10.0)
    p_nearby.add_argument("--label", choices=["verified", "likely", "unverified"])
    p_nearby.set_defaults(func=cmd_nearby)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
