# Weather India Pipeline

A batch ELT pipeline that pulls **real, live weather** for 51 major Indian
cities from the free [Open-Meteo API](https://open-meteo.com/) (no API key),
lands it as raw JSON, and loads it into **DuckDB** via Airflow.

```
extract_weather.py ──> data/source/weather_YYYYMMDD.json   (landing zone)
                                  │
                          Airflow FileSensor
                                  │
                            transform ──> data/staging/weather_YYYYMMDD.parquet
                                  │
                           quality gate (row count + temp bounds)
                                  │
                              load ──> target/weather.duckdb   (idempotent upsert)
                                  │
                            archive ──> data/archive/   (processed raw file)
```

## Why it's built this way

- **Landing-zone pattern** — `source/` (raw) → `staging/` (clean Parquet) →
  `target/` (DuckDB). Files move to `archive/` once processed, so the folder
  state *is* the pipeline backlog.
- **Idempotent load** — the load does `DELETE WHERE run_date = X` then insert.
  Re-runs and backfills never create duplicates (proven: re-running keeps the
  row count flat at 1224 = 51 cities × 24 hours).
- **Atomic landing writes** — the extractor writes `.tmp` then renames, so the
  `FileSensor` never sees a half-written file.
- **Quality gate before load** — fails the DAG if 0 rows or temps fall outside
  −50…60 °C, so bad data never reaches the target.
- **Decoupled extractor** — `extract_weather.py` has zero Airflow dependency;
  run it by hand, from cron, or as the first DAG task.

## Project layout

```
weather-india-pipeline/
├── config/cities.py            # 51 Indian cities (capitals + metros) + lat/lon
├── extract/extract_weather.py  # standalone puller -> data/source/
├── dags/
│   ├── weather_etl.py          # transform / quality_check / load / archive
│   └── weather_pipeline_dag.py # the Airflow DAG (TaskFlow API)
├── data/
│   ├── source/  staging/  archive/  error/
├── target/weather.duckdb       # created on first run
├── run_local.py                # run the whole pipeline WITHOUT Airflow
└── requirements.txt
```

## Quick start (no Airflow — verify the logic)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the whole pipeline once against today's live data:
python run_local.py
# or a specific date:  python run_local.py --date 2026-06-20
```

Then query the target:

```bash
duckdb target/weather.duckdb \
  "SELECT city, ROUND(AVG(temperature_c),1) avg_t
     FROM weather_hourly GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
```

## Running it under Airflow

1. Install Airflow (use the official constraints file for a clean resolve):

   ```bash
   AIRFLOW_VERSION=2.9.3
   PYTHON_VERSION=3.11
   pip install "apache-airflow==${AIRFLOW_VERSION}" \
     --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
   pip install duckdb pyarrow requests
   ```

2. Point Airflow at this repo and start it:

   ```bash
   export AIRFLOW_HOME=~/airflow
   export PIPELINE_HOME=$(pwd)            # so the DAG can import the pipeline modules
   airflow standalone
   ```

3. Make the DAG discoverable — symlink it into the dags folder:

   ```bash
   ln -s "$PIPELINE_HOME/dags/weather_pipeline_dag.py" "$AIRFLOW_HOME/dags/"
   ```

4. The `FileSensor` uses connection `fs_default`. Create it once (UI: Admin →
   Connections, or CLI):

   ```bash
   airflow connections add fs_default --conn-type fs
   ```

5. Unpause `weather_india_pipeline` in the UI and trigger a run.

## The target table — `weather_hourly`

| column                  | type      | notes                              |
|-------------------------|-----------|------------------------------------|
| run_date                | DATE      | partition key (idempotency)        |
| city, state             | VARCHAR   | from `config/cities.py`            |
| lat, lon                | DOUBLE    | Open-Meteo resolved grid point     |
| observed_at             | TIMESTAMP | hourly, Asia/Kolkata               |
| temperature_c           | DOUBLE    | °C                                 |
| relative_humidity_pct   | DOUBLE    | %                                  |
| wind_speed_kmh          | DOUBLE    | km/h                               |
| precipitation_mm        | DOUBLE    | mm                                 |
| weather_code            | INTEGER   | WMO weather code                   |
| loaded_at               | TIMESTAMP | load timestamp                     |

## Extending it

- **More cities** — append to `config/cities.py`. The extractor batches all of
  them into one API call.
- **History instead of forecast** — swap the Open-Meteo endpoint to the
  [archive API](https://open-meteo.com/en/docs/historical-weather-api) for
  backfills, then run the DAG with `catchup=True`.
- **Swap the source** — only `extract_weather.py` changes; the transform/load
  stay the same (e.g. earthquakes, bike-share, crypto).
- **dbt on top** — point dbt at `weather.duckdb` for daily aggregates / marts.
