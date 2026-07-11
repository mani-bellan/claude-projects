"""Core transform + load logic for the weather pipeline.

Kept separate from the DAG definition so it can be unit-tested and run by hand
without an Airflow scheduler:

    python -c "from dags.weather_etl import transform, load; ..."

Stages:
    transform(source_file) -> staging Parquet path
    load(staging_file)     -> rows upserted into DuckDB
    archive(source_file)   -> move processed raw file aside
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"
ERROR_DIR = PROJECT_ROOT / "data" / "error"
TARGET_DB = PROJECT_ROOT / "target" / "weather.duckdb"
TARGET_TABLE = "weather_hourly"

# Basic sanity bounds for the data-quality gate.
TEMP_MIN_C, TEMP_MAX_C = -50.0, 60.0


# --------------------------------------------------------------------------- #
# Transform: raw nested JSON -> flat, validated rows -> Parquet in staging/
# --------------------------------------------------------------------------- #
def transform(source_file: str | Path) -> str:
    source_file = Path(source_file)
    with source_file.open(encoding="utf-8") as f:
        payload = json.load(f)

    run_date = payload["run_date"]
    rows: list[dict] = []

    for rec in payload["records"]:
        hourly = rec["weather"]["hourly"]
        times = hourly["time"]
        temps = hourly["temperature_2m"]
        hums = hourly["relative_humidity_2m"]
        winds = hourly["wind_speed_10m"]
        precip = hourly.get("precipitation", [None] * len(times))
        wcode = hourly.get("weather_code", [None] * len(times))

        for i, ts in enumerate(times):
            rows.append({
                "run_date": run_date,
                "city": rec["city"],
                "state": rec["state"],
                "lat": rec["weather"].get("latitude"),
                "lon": rec["weather"].get("longitude"),
                "observed_at": datetime.fromisoformat(ts),
                "temperature_c": temps[i],
                "relative_humidity_pct": hums[i],
                "wind_speed_kmh": winds[i],
                "precipitation_mm": precip[i],
                "weather_code": wcode[i],
            })

    if not rows:
        raise ValueError(f"No rows produced from {source_file.name} — empty extract.")

    table = pa.Table.from_pylist(rows)

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staging_path = STAGING_DIR / f"weather_{run_date.replace('-', '')}.parquet"
    pq.write_table(table, staging_path)
    print(f"transform: {len(rows)} rows -> {staging_path}")
    return str(staging_path)


# --------------------------------------------------------------------------- #
# Data-quality gate: fail the DAG before load if the data looks wrong.
# --------------------------------------------------------------------------- #
def quality_check(staging_file: str | Path) -> dict:
    staging_file = Path(staging_file)
    con = duckdb.connect()
    try:
        stats = con.execute(
            f"""
            SELECT
                COUNT(*)                              AS row_count,
                COUNT(DISTINCT city)                  AS city_count,
                MIN(temperature_c)                    AS min_temp,
                MAX(temperature_c)                    AS max_temp,
                SUM(CASE WHEN temperature_c IS NULL THEN 1 ELSE 0 END) AS null_temps
            FROM read_parquet('{staging_file}')
            """
        ).fetchone()
    finally:
        con.close()

    row_count, city_count, min_temp, max_temp, null_temps = stats
    report = {
        "row_count": row_count,
        "city_count": city_count,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "null_temps": null_temps,
    }

    if row_count == 0:
        raise ValueError(f"Quality check failed: 0 rows. {report}")
    if min_temp is not None and min_temp < TEMP_MIN_C:
        raise ValueError(f"Quality check failed: temp below {TEMP_MIN_C}C. {report}")
    if max_temp is not None and max_temp > TEMP_MAX_C:
        raise ValueError(f"Quality check failed: temp above {TEMP_MAX_C}C. {report}")

    print(f"quality_check passed: {report}")
    return report


# --------------------------------------------------------------------------- #
# Load: idempotent upsert into DuckDB partitioned by run_date.
# --------------------------------------------------------------------------- #
def load(staging_file: str | Path) -> int:
    staging_file = Path(staging_file)
    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(TARGET_DB))
    try:
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
                run_date              DATE,
                city                  VARCHAR,
                state                 VARCHAR,
                lat                   DOUBLE,
                lon                   DOUBLE,
                observed_at           TIMESTAMP,
                temperature_c         DOUBLE,
                relative_humidity_pct DOUBLE,
                wind_speed_kmh        DOUBLE,
                precipitation_mm      DOUBLE,
                weather_code          INTEGER,
                loaded_at             TIMESTAMP DEFAULT now()
            )
            """
        )

        # Idempotency: delete this run_date's partition, then re-insert. Re-runs
        # and backfills are safe — no duplicate rows.
        run_date = con.execute(
            f"SELECT DISTINCT run_date FROM read_parquet('{staging_file}')"
        ).fetchone()[0]

        con.execute(f"DELETE FROM {TARGET_TABLE} WHERE run_date = ?", [run_date])
        con.execute(
            f"""
            INSERT INTO {TARGET_TABLE}
            SELECT *, now() AS loaded_at
            FROM read_parquet('{staging_file}')
            """
        )
        count = con.execute(
            f"SELECT COUNT(*) FROM {TARGET_TABLE} WHERE run_date = ?", [run_date]
        ).fetchone()[0]
    finally:
        con.close()

    print(f"load: {count} rows in partition run_date={run_date}")
    return count


# --------------------------------------------------------------------------- #
# Archive: move the processed raw file so the source/ folder state == backlog.
# --------------------------------------------------------------------------- #
def archive(source_file: str | Path) -> str:
    source_file = Path(source_file)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / source_file.name
    source_file.replace(dest)
    print(f"archive: {source_file.name} -> {dest}")
    return str(dest)
