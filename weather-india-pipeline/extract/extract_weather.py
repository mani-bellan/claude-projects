#!/usr/bin/env python3
"""Standalone weather extractor.

Pulls today's hourly forecast for every Indian city in config/cities.py from the
free Open-Meteo API (no API key required) and drops a single raw JSON file into
the landing zone (data/source/).

Airflow then picks that file up. This script is deliberately decoupled from
Airflow so you can run it by hand, from cron, or as the first DAG task:

    python extract/extract_weather.py
    python extract/extract_weather.py --date 2026-06-20

Design notes
------------
- One file per run, named by date: weather_YYYYMMDD.json. The filename *is* the
  partition key, which makes the downstream load idempotent.
- We batch all cities into a single Open-Meteo call (it accepts comma-separated
  lat/lon lists), so one run = one HTTP request, well within the free tier.
- The raw payload is written untouched (schema-on-read). Cleaning happens in the
  Airflow transform step, not here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

# Make `config` importable whether run from repo root or from extract/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.cities import CITIES  # noqa: E402

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_DIR = PROJECT_ROOT / "data" / "source"
HOURLY_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code"
TIMEZONE = "Asia/Kolkata"
REQUEST_TIMEOUT = 60


def fetch_weather(run_date: date) -> dict:
    """Fetch one day of hourly forecast for all cities in a single request."""
    latitudes = ",".join(str(c["lat"]) for c in CITIES)
    longitudes = ",".join(str(c["lon"]) for c in CITIES)

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "hourly": HOURLY_VARS,
        "timezone": TIMEZONE,
        "start_date": run_date.isoformat(),
        "end_date": run_date.isoformat(),
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    # When multiple coordinates are requested Open-Meteo returns a list; for a
    # single coordinate it returns a dict. Normalize to a list so the structure
    # is stable regardless of how many cities are configured.
    if isinstance(payload, dict):
        payload = [payload]

    if len(payload) != len(CITIES):
        raise ValueError(
            f"Expected {len(CITIES)} city results, got {len(payload)}. "
            "City/result mismatch — aborting before writing a bad file."
        )

    # Stitch our city metadata onto each result so downstream has names, not just
    # coordinates. Open-Meteo preserves request order.
    records = []
    for city, result in zip(CITIES, payload):
        records.append({
            "city": city["name"],
            "state": city["state"],
            "req_lat": city["lat"],
            "req_lon": city["lon"],
            "weather": result,
        })

    return {
        "run_date": run_date.isoformat(),
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "open-meteo",
        "city_count": len(records),
        "records": records,
    }


def write_landing_file(data: dict, run_date: date) -> Path:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SOURCE_DIR / f"weather_{run_date.strftime('%Y%m%d')}.json"

    # Write to a temp file then rename, so Airflow's FileSensor never sees a
    # half-written file (atomic on the same filesystem).
    tmp_path = out_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(out_path)
    return out_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull Indian city weather into the landing zone.")
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Run date (YYYY-MM-DD). Defaults to today.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"Fetching weather for {len(CITIES)} cities, date={args.date} ...")
    data = fetch_weather(args.date)
    out_path = write_landing_file(data, args.date)
    print(f"Wrote {data['city_count']} city records -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
