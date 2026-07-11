"""Generator configuration: canonical schema, drift modes, realism knobs."""

from __future__ import annotations

# Canonical (v1) order schema. The drift engine mutates a copy of this state.
BASE_SCHEMA = {
    "order_id": "string",
    "customer_id": "string",
    "customer_name": "string",
    "order_ts": "timestamp",
    "status": "string",
    "currency": "string",
    "total_amount": "float",
    "items": "array",
}

# Optional columns the additive drift mode can introduce, in order.
ADDITIVE_COLUMNS = [
    ("discount_code", "string"),
    ("shipping_tier", "string"),
    ("gift_wrap", "boolean"),
    ("loyalty_points", "integer"),
    ("delivery_notes", "string"),
]

# Columns eligible for removal drift (never core identifiers).
REMOVABLE_COLUMNS = ["customer_name", "currency"]

# Rename drift pairs: original -> drifted name.
RENAME_MAP = {
    "customer_id": "cust_id",
    "total_amount": "order_total",
}

STATUSES = ["placed", "confirmed", "shipped", "delivered", "cancelled", "refunded"]
CURRENCIES = ["INR", "USD", "EUR", "GBP", "SGD"]

SHIPPING_TIERS = ["standard", "express", "same_day"]
DISCOUNT_CODES = ["WELCOME10", "FESTIVE25", "FREESHIP", None, None]

PRODUCTS = [
    {"sku": "SKU-1001", "name": "Wireless Mouse", "unit_price": 1299.0},
    {"sku": "SKU-1002", "name": "Mechanical Keyboard", "unit_price": 4499.0},
    {"sku": "SKU-1003", "name": "USB-C Hub", "unit_price": 2199.0},
    {"sku": "SKU-1004", "name": "Laptop Stand", "unit_price": 1799.0},
    {"sku": "SKU-1005", "name": "Noise-Cancelling Headphones", "unit_price": 8999.0},
    {"sku": "SKU-1006", "name": "Webcam 1080p", "unit_price": 3499.0},
    {"sku": "SKU-1007", "name": "Desk Lamp", "unit_price": 999.0},
    {"sku": "SKU-1008", "name": "Portable SSD 1TB", "unit_price": 7499.0},
]

# Names with unicode/emoji to exercise encoding paths downstream.
CUSTOMER_NAMES = [
    "Aarav Sharma", "Priya Iyer", "José García", "François Müller",
    "Søren Kierkegaard", "Ólafur Arnalds", "李小龙", "山田太郎",
    "Anaïs Nin", "Zoë Washburne", "Ravi 🚀 Kumar", "Ñandú Pérez",
]

# Realism knobs (probabilities per record).
DUPLICATE_EVENT_RATE = 0.08     # same order re-emitted with a later status
LATE_ARRIVAL_RATE = 0.05        # order_ts from 1-3 windows ago
NULL_OPTIONAL_RATE = 0.10       # optional field emitted as null
BAD_CURRENCY_RATE = 0.02        # non-ISO currency code
FUTURE_TS_RATE = 0.01           # order_ts in the future
NEGATIVE_AMOUNT_RATE = 0.03     # refunds carry negative amounts (legit)

DEFAULT_ROWS_PER_BATCH = (40, 120)  # uniform range
