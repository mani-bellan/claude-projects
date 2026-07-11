CREATE SEQUENCE IF NOT EXISTS seq_places START 1;
CREATE SEQUENCE IF NOT EXISTS seq_evidence START 1;
CREATE SEQUENCE IF NOT EXISTS seq_pending_reviews START 1;

CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY DEFAULT nextval('seq_places'),
    google_place_id TEXT UNIQUE,
    name TEXT NOT NULL,
    category TEXT,                -- cafe | restaurant | resort | hotel | other
    address TEXT,
    city TEXT,
    lat DOUBLE,
    lng DOUBLE,
    phone TEXT,
    website TEXT,
    rating DOUBLE,
    rating_count INTEGER,
    created_at TIMESTAMP DEFAULT current_timestamp,
    updated_at TIMESTAMP DEFAULT current_timestamp
);

-- One row per pet-policy claim, always attributed and dated.
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY DEFAULT nextval('seq_evidence'),
    place_id INTEGER NOT NULL REFERENCES places(id),
    source TEXT NOT NULL,          -- e.g. google_allows_dogs, google_review, sample
    tier INTEGER NOT NULL,         -- 0..3, see config.TIER_WEIGHTS
    polarity TEXT NOT NULL,        -- positive | negative | neutral
    claim TEXT NOT NULL,           -- human-readable summary of the evidence
    source_url TEXT,
    observed_date TEXT,            -- ISO date the evidence refers to
    extracted_fields TEXT,         -- JSON: pet sizes, indoor/outdoor, fees, etc.
    raw_text TEXT,                 -- original text the claim was extracted from
    created_at TIMESTAMP DEFAULT current_timestamp
);

-- Raw review text waiting for the extraction step.
-- processed: 0 = pending, 1 = done, 2 = submitted in an in-flight batch
CREATE TABLE IF NOT EXISTS pending_reviews (
    id INTEGER PRIMARY KEY DEFAULT nextval('seq_pending_reviews'),
    place_id INTEGER NOT NULL REFERENCES places(id),
    review_text TEXT NOT NULL,
    review_date TEXT,
    source_url TEXT,
    processed INTEGER DEFAULT 0
);

-- Anthropic Message Batches submitted for extraction (50% token discount).
CREATE TABLE IF NOT EXISTS extraction_batches (
    batch_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    review_count INTEGER NOT NULL,
    status TEXT DEFAULT 'in_progress',  -- in_progress | collected
    submitted_at TIMESTAMP DEFAULT current_timestamp,
    collected_at TIMESTAMP
);

-- One row per website fetch attempt, so re-runs skip already-checked sites
-- until the re-verification window expires.
CREATE SEQUENCE IF NOT EXISTS seq_website_checks START 1;
CREATE TABLE IF NOT EXISTS website_checks (
    id INTEGER PRIMARY KEY DEFAULT nextval('seq_website_checks'),
    place_id INTEGER NOT NULL REFERENCES places(id),
    url TEXT NOT NULL,
    outcome TEXT NOT NULL,         -- policy_found | no_pet_mention | fetch_failed | skipped_social
    checked_at TIMESTAMP DEFAULT current_timestamp
);

-- Derived per-place confidence, recomputed by the score step.
CREATE TABLE IF NOT EXISTS scores (
    place_id INTEGER PRIMARY KEY REFERENCES places(id),
    confidence DOUBLE NOT NULL,
    label TEXT NOT NULL,           -- verified | likely | unverified
    evidence_count INTEGER NOT NULL,
    source_count INTEGER NOT NULL, -- distinct sources, drives corroboration bonus
    computed_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_evidence_place ON evidence(place_id);
CREATE INDEX IF NOT EXISTS idx_pending_unprocessed ON pending_reviews(processed);
