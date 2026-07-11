"""Bronze ingestion: file-level edge cases and idempotency."""

import json

from pipeline import warehouse
from pipeline.landing import discover_batches
from pipeline.run import ingest, sense
from tests.conftest import valid_order, write_batch_files


def bronze_count(paths, batch_id=None):
    con = warehouse.connect(paths.db_path)
    try:
        if batch_id:
            return con.execute(
                "SELECT COUNT(*) FROM bronze.orders_raw WHERE batch_id = ?",
                [batch_id]).fetchone()[0]
        return con.execute("SELECT COUNT(*) FROM bronze.orders_raw").fetchone()[0]
    finally:
        con.close()


def batch_status(paths, batch_id):
    con = warehouse.connect(paths.db_path)
    try:
        row = con.execute(
            "SELECT status FROM meta.processed_batches WHERE batch_id = ?",
            [batch_id]).fetchone()
        return row[0] if row else None
    finally:
        con.close()


class TestHappyPath:
    def test_batch_lands_and_archives(self, paths):
        b = write_batch_files(paths.incoming, [valid_order() for _ in range(10)])
        results = ingest(paths)
        assert results[0] == {**results[0], "batch_id": b, "rows": 10, "skipped": False}
        assert bronze_count(paths, b) == 10
        assert not list(paths.incoming.glob("*.jsonl"))
        assert len(list(paths.processed.glob("*.jsonl"))) == 1

    def test_two_batches_between_runs_both_load_in_order(self, paths):
        b1 = write_batch_files(paths.incoming, [valid_order()])
        b2 = write_batch_files(paths.incoming, [valid_order(), valid_order()])
        results = ingest(paths)
        assert len(results) == 2
        assert bronze_count(paths, b1) == 1 and bronze_count(paths, b2) == 2

    def test_large_batch(self, paths):
        b = write_batch_files(paths.incoming, [valid_order() for _ in range(10_000)])
        ingest(paths)
        assert bronze_count(paths, b) == 10_000


class TestFileEdgeCases:
    def test_empty_batch_loads_zero_rows(self, paths):
        b = write_batch_files(paths.incoming, [])
        results = ingest(paths)
        assert results[0]["rows"] == 0 and not results[0].get("error")
        assert batch_status(paths, b) == "loaded"

    def test_whitespace_only_file_loads_zero_rows(self, paths):
        b = write_batch_files(paths.incoming, [], tamper="whitespace")
        results = ingest(paths)
        assert results[0]["rows"] == 0 and not results[0].get("error")
        assert batch_status(paths, b) == "loaded"

    def test_corrupt_json_goes_to_failed(self, paths):
        b = write_batch_files(paths.incoming, [valid_order()], tamper="corrupt_json")
        results = ingest(paths)
        assert "corrupt JSON" in results[0]["error"]
        assert batch_status(paths, b) == "failed"
        assert bronze_count(paths, b) == 0
        assert len(list(paths.failed.glob("*.jsonl"))) == 1

    def test_checksum_mismatch_goes_to_failed(self, paths):
        b = write_batch_files(paths.incoming, [valid_order()], tamper="checksum")
        results = ingest(paths)
        assert "checksum mismatch" in results[0]["error"]
        assert batch_status(paths, b) == "failed"

    def test_row_count_mismatch_goes_to_failed(self, paths):
        b = write_batch_files(paths.incoming, [valid_order()], tamper="row_count")
        results = ingest(paths)
        assert "row count mismatch" in results[0]["error"]
        assert batch_status(paths, b) == "failed"

    def test_data_without_manifest_is_left_waiting(self, paths):
        write_batch_files(paths.incoming, [valid_order()], tamper="no_manifest")
        assert sense(paths) == []
        assert ingest(paths) == []
        # file stays in incoming for when its manifest arrives
        assert len(list(paths.incoming.glob("*.jsonl"))) == 1

    def test_zero_files_is_clean_skip(self, paths):
        assert sense(paths) == []
        assert ingest(paths) == []

    def test_non_matching_filenames_ignored(self, paths):
        paths.incoming.mkdir(parents=True, exist_ok=True)
        (paths.incoming / "random.jsonl").write_text("{}")
        (paths.incoming / ".DS_Store").write_text("")
        assert sense(paths) == []


class TestIdempotency:
    def test_redelivered_batch_is_skipped(self, paths):
        b = write_batch_files(paths.incoming, [valid_order() for _ in range(5)])
        ingest(paths)
        # simulate redelivery: copy the processed files back to incoming
        for f in paths.processed.iterdir():
            (paths.incoming / f.name).write_bytes(f.read_bytes())
        results = ingest(paths)
        assert results[0]["skipped"] is True
        assert bronze_count(paths, b) == 5, "no double counting"

    def test_retry_after_partial_write_converges(self, paths):
        b = write_batch_files(paths.incoming, [valid_order() for _ in range(5)])
        batch = discover_batches(paths.incoming)[0]
        con = warehouse.connect(paths.db_path)
        # simulate a crashed load: orphan bronze rows, batch never registered
        con.execute(
            "INSERT INTO bronze.orders_raw VALUES (?, 'f', now(), 'h', 's', ?)",
            [b, json.dumps({"partial": True})])
        con.close()
        ingest(paths)
        assert bronze_count(paths, b) == 5, "partial rows replaced, not appended"
