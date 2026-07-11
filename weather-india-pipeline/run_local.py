#!/usr/bin/env python3
"""Run the whole pipeline once WITHOUT Airflow, for development/testing.

    python run_local.py
    python run_local.py --date 2026-06-20

This mirrors the DAG: extract -> transform -> quality_check -> load -> archive.
Handy for verifying the logic before wiring up the scheduler.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime

from extract.extract_weather import fetch_weather, write_landing_file
from dags.weather_etl import transform, quality_check, load, archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
    )
    args = parser.parse_args()

    print("== extract ==")
    data = fetch_weather(args.date)
    source_file = write_landing_file(data, args.date)

    print("== transform ==")
    staging_file = transform(source_file)

    print("== quality_check ==")
    quality_check(staging_file)

    print("== load ==")
    load(staging_file)

    print("== archive ==")
    archive(source_file)

    print("\nDone. Query the target:")
    print("  duckdb target/weather.duckdb \"SELECT city, COUNT(*) FROM weather_hourly GROUP BY 1 ORDER BY 1\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
