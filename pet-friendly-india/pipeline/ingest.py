"""Candidate discovery: Google Places API (New) text search, or bundled sample data."""

import json
import re
import time

import requests

from . import config, db

SAMPLE_PATH = config.PROJECT_ROOT / "data" / "sample_places.json"

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
# allowsDogs sits in the Enterprise+Atmosphere SKU — listed last so trimming
# the mask to cut cost is a one-line change.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.types",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.reviews",
    "places.allowsDogs",
])

CATEGORY_MAP = {
    "cafe": "cafe", "coffee_shop": "cafe", "restaurant": "restaurant",
    "resort_hotel": "resort", "lodging": "hotel", "hotel": "hotel",
}


def _category_from_types(types: list[str]) -> str:
    for t in types or []:
        if t in CATEGORY_MAP:
            return CATEGORY_MAP[t]
    return "other"


# Localities used to fan out city-level ingestion. One text-search query
# returns at most 20 places, so covering a city means many narrower queries;
# google_place_id dedupe merges the overlaps.
CITY_LOCALITIES = {
    "bangalore": [
        "Indiranagar", "Koramangala", "HSR Layout", "Whitefield", "Jayanagar",
        "JP Nagar", "MG Road", "Malleshwaram", "Sarjapur Road", "Hebbal",
        "Kalyan Nagar", "Sahakara Nagar",
    ],
}
CITY_LOCALITIES["bengaluru"] = CITY_LOCALITIES["bangalore"]

LOCALITY_CATEGORIES = ["cafes", "restaurants"]


def city_queries(city: str) -> list[str]:
    localities = CITY_LOCALITIES.get(city.lower())
    if not localities:
        # Unknown city: fall back to broad category queries.
        return [f"pet friendly {cat} in {city}"
                for cat in ("cafes", "restaurants", "resorts", "hotels")]
    queries = [
        f"pet friendly {cat} in {loc}, {city}"
        for loc in localities for cat in LOCALITY_CATEGORIES
    ]
    queries.append(f"pet friendly resorts near {city}")
    queries.append(f"pet friendly hotels in {city}")
    return queries


def ingest_city(conn, city: str) -> tuple[int, int]:
    """Fan out locality x category queries for a city. Returns (places, api_calls)."""
    queries = city_queries(city)
    print(f"Running {len(queries)} text-search queries for {city} "
          f"(each is one Enterprise-tier Places API call)...")
    total = 0
    for q in queries:
        n = ingest_google(conn, q, city=city)
        print(f"  {q!r}: {n} places")
        total += n
        time.sleep(0.2)  # be polite to the API
    return total, len(queries)


def ingest_google(conn, query: str, city: str | None = None) -> int:
    resp = requests.post(
        PLACES_SEARCH_URL,
        headers={
            "X-Goog-Api-Key": config.GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
            "Content-Type": "application/json",
        },
        json={"textQuery": query, "pageSize": 20},
        timeout=30,
    )
    resp.raise_for_status()
    places = resp.json().get("places", [])

    count = 0
    for p in places:
        loc = p.get("location", {})
        place_id = db.upsert_place(conn, {
            "google_place_id": p.get("id"),
            "name": p.get("displayName", {}).get("text", "Unknown"),
            "category": _category_from_types(p.get("types")),
            "address": p.get("formattedAddress"),
            "city": city or _city_from_address(p.get("formattedAddress")),
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "phone": p.get("nationalPhoneNumber"),
            "website": p.get("websiteUri"),
            "rating": p.get("rating"),
            "rating_count": p.get("userRatingCount"),
        })
        _record_allows_dogs(conn, place_id, p.get("allowsDogs"), source="google_allows_dogs")
        for r in p.get("reviews", []):
            text = (r.get("text") or {}).get("text")
            if text:
                db.add_pending_review(
                    conn, place_id, text,
                    review_date=r.get("publishTime", "")[:10] or None,
                    source_url=r.get("googleMapsUri"),
                )
        count += 1
    return count


def _city_from_address(address: str | None) -> str | None:
    """Best-effort city from a Google formattedAddress like
    '743, 10th A Main Rd, Indiranagar, Bengaluru, Karnataka 560038, India'.
    The component holding the 6-digit PIN is 'State PIN'; city precedes it."""
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    for i in range(len(parts) - 1, 0, -1):
        if re.search(r"\b\d{6}\b", parts[i]):
            return parts[i - 1] or None
    return None


def ingest_sample(conn) -> int:
    places = json.loads(SAMPLE_PATH.read_text())
    for p in places:
        place_id = db.upsert_place(conn, p)
        _record_allows_dogs(conn, place_id, p.get("allows_dogs"), source="sample_allows_dogs")
        for r in p.get("reviews", []):
            db.add_pending_review(conn, place_id, r["text"], review_date=r.get("date"))
    return len(places)


def _record_allows_dogs(conn, place_id, allows_dogs, source):
    if allows_dogs is None:
        return
    # Avoid duplicate flag evidence on re-ingest.
    row = conn.execute(
        "SELECT 1 FROM evidence WHERE place_id=? AND source=?", (place_id, source)
    ).fetchone()
    if row:
        return
    db.add_evidence(
        conn, place_id, source=source, tier=1,
        polarity="positive" if allows_dogs else "negative",
        claim="Venue flag: dogs allowed" if allows_dogs else "Venue flag: dogs NOT allowed",
    )
