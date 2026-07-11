.PHONY: install test lint fmt airflow-up airflow-down dashboard backfill clean

VENV := .venv/bin

install:
	$(VENV)/pip install -e ".[dashboard,dev]"

test:
	$(VENV)/pytest tests/

lint:
	$(VENV)/ruff check src/ tests/

fmt:
	$(VENV)/ruff format src/ tests/

airflow-up:
	docker compose up -d
	@echo "Airflow UI: http://localhost:8080  (admin/admin)"

airflow-down:
	docker compose down

dashboard:
	$(VENV)/streamlit run dashboard/app.py

backfill:
	$(VENV)/python -m markets_pipeline.cli backfill

clean:
	rm -rf data/*.duckdb data/*.duckdb.wal
	rm -rf .pytest_cache .ruff_cache **/__pycache__
