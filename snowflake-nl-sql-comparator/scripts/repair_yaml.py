"""One-shot repair: strip trailing backslashes from the YAML on your Snowflake stage.

Runs download → strip → upload → re-download → verify. Prints every step so
silent failures (e.g. PUT errors swallowed by the connector) are caught.

Usage:
    uv run python scripts/repair_yaml.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.snowflake_client import SnowflakeClient


def main() -> int:
    cfg = Config.from_env()
    sf = SnowflakeClient(cfg)
    stage_path = cfg.semantic_model_stage_path
    stage_dir = stage_path.rsplit("/", 1)[0]
    filename = stage_path.rsplit("/", 1)[-1]

    print(f"Source stage path: {stage_path}")
    print(f"Stage dir:         {stage_dir}")
    print(f"Filename:          {filename}")
    print()

    # Step 1: Download current state
    print("STEP 1: Downloading current YAML...")
    local_orig = sf.download_from_stage(stage_path)
    original = local_orig.read_text()
    orig_lines = original.splitlines()
    orig_bad = sum(1 for line in orig_lines if line.endswith("\\"))
    print(f"  Downloaded to: {local_orig}")
    print(f"  Total lines:        {len(orig_lines)}")
    print(f"  Lines with `\\` end: {orig_bad}")
    if orig_bad == 0:
        print("  ✓ YAML is already clean. Nothing to fix.")
        return 0
    print(f"  Line 1 tail (last 20 chars repr): {orig_lines[0][-20:]!r}")
    print(f"  Line 2 tail (last 20 chars repr): {orig_lines[1][-20:]!r}")
    print()

    # Step 2: Strip trailing backslashes
    print("STEP 2: Stripping trailing backslashes...")
    fixed_lines = [line.rstrip("\\") for line in orig_lines]
    fixed_text = "\n".join(fixed_lines)
    if original.endswith("\n"):
        fixed_text += "\n"

    out_dir = Path(tempfile.mkdtemp(prefix="repair_yaml_"))
    out_path = out_dir / filename
    out_path.write_text(fixed_text)

    new_bad = sum(1 for line in fixed_lines if line.endswith("\\"))
    print(f"  Wrote {len(fixed_text)} bytes to {out_path}")
    print(f"  Lines with `\\` end after strip: {new_bad}")
    print(f"  Line 1 tail now: {fixed_lines[0][-20:]!r}")
    print(f"  Line 2 tail now: {fixed_lines[1][-20:]!r}")
    if new_bad != 0:
        print("  ✗ Strip did not remove all backslashes — bailing out.")
        return 2
    print()

    # Step 3: Upload
    print("STEP 3: Uploading via PUT...")
    conn = sf.connect()
    cur = conn.cursor()
    put_sql = (
        f"PUT 'file://{out_path.resolve()}' {stage_dir} "
        f"OVERWRITE=TRUE AUTO_COMPRESS=FALSE SOURCE_COMPRESSION=NONE"
    )
    print(f"  SQL: {put_sql}")
    try:
        cur.execute(put_sql)
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        print(f"  PUT result columns: {cols}")
        for row in rows:
            print(f"  PUT result row: {dict(zip(cols, row))}")
        # Snowflake's PUT returns a 'status' column — check for UPLOADED
        if cols and "status" in cols:
            status_idx = cols.index("status")
            statuses = [r[status_idx] for r in rows]
            print(f"  Statuses: {statuses}")
            if not all(s.upper() == "UPLOADED" for s in statuses):
                print("  ✗ PUT did not report UPLOADED for all rows.")
                return 3
    except Exception as e:
        print(f"  ✗ PUT raised: {type(e).__name__}: {e}")
        return 4
    finally:
        cur.close()
    print()

    # Step 4: Re-download from stage and verify
    print("STEP 4: Re-downloading from stage to verify fix took...")
    local_verify = sf.download_from_stage(stage_path)
    verified = local_verify.read_text()
    verified_lines = verified.splitlines()
    verified_bad = sum(1 for line in verified_lines if line.endswith("\\"))
    print(f"  Re-downloaded to: {local_verify}")
    print(f"  Total lines:        {len(verified_lines)}")
    print(f"  Lines with `\\` end: {verified_bad}")
    print(f"  Line 1 tail: {verified_lines[0][-20:]!r}")
    print(f"  Line 2 tail: {verified_lines[1][-20:]!r}")
    print()

    if verified_bad == 0:
        print("✓ SUCCESS — YAML on the stage is now clean.")
        print("  Restart Streamlit:")
        print("    Ctrl+C the running instance")
        print("    uv run streamlit run app.py")
        return 0
    else:
        print(f"✗ STILL BROKEN — re-downloaded YAML still has {verified_bad} bad lines.")
        print("  The PUT may have hit a different path than expected, or the stage")
        print("  is read-only. Check stage permissions and any directory tables:")
        print(f"    LIST {stage_dir};")
        return 5


if __name__ == "__main__":
    sys.exit(main())
