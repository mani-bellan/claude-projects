"""Venue-website source: tier-1 evidence from a venue's own stated pet policy.

Design: HTTP fetches are free, Claude calls are not. Every page goes through a
keyword pre-filter first — only pages that actually mention pets are sent to
Claude for extraction. Silence is recorded as no_pet_mention, never inferred
as pet-friendly.
"""

import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from . import config, db
from .extract import PetEvidence

# (connect, read) — keep connect tight: a dead domain with several A records
# pays the connect timeout once per address, so 15s here means minutes lost.
FETCH_TIMEOUT = (5, 10)
MAX_TEXT_CHARS = 20_000
USER_AGENT = "PetFriendlyIndiaBot/0.1 (pet policy aggregator; contact via site)"

# Social platforms block scraping — skip rather than record a false negative.
SOCIAL_DOMAINS = ("instagram.com", "facebook.com", "wa.me", "whatsapp.com",
                  "twitter.com", "x.com", "linktr.ee")

PET_KEYWORD_RE = re.compile(
    r"\b(pets?|dogs?|cats?|puppy|puppies|paw|canine|pet[- ]friendly)\b", re.I)

# Subpages worth following from the homepage if linked.
CANDIDATE_LINK_RE = re.compile(r"(pet|policy|policies|faq|rules|guidelines)", re.I)
MAX_SUBPAGES = 2

# Re-check a website after this many days (re-verification cadence).
RECHECK_DAYS = 90


class _TextAndLinks(HTMLParser):
    """Extract visible text and anchor hrefs without external dependencies."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []  # (href, anchor_text)
        self._skip_depth = 0
        self._current_href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "a":
            self._current_href = dict(attrs).get("href")
            self._anchor_text = []

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "a" and self._current_href:
            self.links.append((self._current_href, " ".join(self._anchor_text)))
            self._current_href = None

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text)
            if self._current_href is not None:
                self._anchor_text.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


def _fetch_text(url: str) -> tuple[str, list[tuple[str, str]]] | None:
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", "html"):
            return None
        parser = _TextAndLinks()
        parser.feed(resp.text)
        return parser.text[:MAX_TEXT_CHARS], parser.links
    except (requests.RequestException, Exception):
        return None


def _extract_policy(page_text: str, venue_name: str) -> PetEvidence:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=config.DEFAULT_EXTRACTION_MODEL,
        max_tokens=1024,
        system=(
            "You extract a venue's own stated pet policy from its website text, "
            "for a pet-friendly places directory in India. Only report an explicit "
            "policy statement by the venue (e.g. 'pet friendly', 'pets welcome', "
            "'no pets allowed', pet fees, pet rules). Marketing mentions of animals, "
            "menu items, or decor are NOT a policy. If the site does not state a "
            "policy about visitors' pets, set mentions_pets=false and "
            "polarity=neutral. polarity is positive if visitors' pets are welcomed, "
            "negative if pets are not allowed."
        ),
        messages=[{"role": "user", "content":
                   f"Venue: {venue_name}\n\nWebsite text:\n{page_text}"}],
        output_format=PetEvidence,
    )
    return response.parsed_output


def check_place_website(conn, place: dict) -> str:
    """Fetch a place's website (+ promising subpages) and record tier-1
    evidence if the venue states a pet policy. Returns the outcome."""
    url = place["website"]
    domain = urlparse(url).netloc.lower()
    if any(s in domain for s in SOCIAL_DOMAINS):
        return _record(conn, place["id"], url, "skipped_social")

    fetched = _fetch_text(url)
    if fetched is None:
        return _record(conn, place["id"], url, "fetch_failed")
    text, links = fetched

    # Follow up to MAX_SUBPAGES same-site links that look policy/FAQ-shaped.
    seen, followed = {url}, 0
    pages = [(url, text)]
    for href, anchor in links:
        if followed >= MAX_SUBPAGES:
            break
        target = urljoin(url, href)
        if target in seen or urlparse(target).netloc.lower() != domain:
            continue
        if CANDIDATE_LINK_RE.search(href) or CANDIDATE_LINK_RE.search(anchor):
            seen.add(target)
            sub = _fetch_text(target)
            followed += 1
            if sub:
                pages.append((target, sub[0]))

    # Keyword pre-filter: no pet mention anywhere -> no Claude call at all.
    pet_pages = [(u, t) for u, t in pages if PET_KEYWORD_RE.search(t)]
    if not pet_pages:
        return _record(conn, place["id"], url, "no_pet_mention")

    for page_url, page_text in pet_pages:
        evidence = _extract_policy(page_text, place["name"])
        if evidence.mentions_pets and evidence.polarity != "neutral":
            db.add_evidence(
                conn, place["id"], source="venue_website", tier=1,
                polarity=evidence.polarity, claim=evidence.claim,
                source_url=page_url, observed_date=date.today().isoformat(),
                extracted_fields=evidence.model_dump_json(
                    exclude={"mentions_pets", "polarity", "claim"}),
            )
            return _record(conn, place["id"], url, "policy_found")
    return _record(conn, place["id"], url, "no_pet_mention")


def _record(conn, place_id, url, outcome) -> str:
    conn.execute(
        "INSERT INTO website_checks (place_id, url, outcome) VALUES (?,?,?)",
        (place_id, url, outcome))
    return outcome


def run_website_checks(conn, limit: int | None = None) -> dict:
    """Check websites for places that have one and weren't checked recently."""
    places = db.rows(conn, f"""
        SELECT p.id, p.name, p.website FROM places p
        WHERE p.website IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM website_checks wc
            WHERE wc.place_id = p.id
              AND wc.checked_at > current_timestamp - INTERVAL {RECHECK_DAYS} DAY)
        ORDER BY p.id
        {f'LIMIT {int(limit)}' if limit else ''}
    """)
    outcomes: dict[str, int] = {}
    for place in places:
        outcome = check_place_website(conn, place)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        print(f"  {place['name'][:45]:<45} -> {outcome}")
    return outcomes
