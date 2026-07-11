import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH = PROJECT_ROOT / os.environ.get("PFI_DB_PATH", "data/petfriendly.duckdb")

# Model for review-text evidence extraction. Haiku is ~5x cheaper than Opus
# and spot-checked at near-identical quality on this task (see README).
DEFAULT_EXTRACTION_MODEL = "claude-haiku-4-5"

# Evidence source tiers — lower number = more trusted.
# Tier 0 is reserved for verified user visit reports (future).
TIER_WEIGHTS = {
    0: 1.2,  # user visit report (future)
    1: 1.0,  # venue's own statement / Google allowsDogs flag
    2: 0.7,  # booking-site pet filter
    3: 0.4,  # review-text mention, blog listicle
}

# Recency decay: evidence loses half its weight every N days.
DECAY_HALF_LIFE_DAYS = 180

# Score thresholds for listing labels.
VERIFIED_THRESHOLD = 0.75
LIKELY_THRESHOLD = 0.40
