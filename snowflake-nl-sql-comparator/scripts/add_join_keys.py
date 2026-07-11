"""Add foreign-key dimensions to tables so Cortex Analyst relationships validate.

Cortex Analyst requires every column referenced in a `relationships:` block to
be declared as a dimension/fact on its logical table. This script:

  1. Downloads the YAML from SEMANTIC_MODEL_STAGE_PATH
  2. Audits all relationships against declared columns
  3. Adds any missing join-key columns to the appropriate tables as dimensions
  4. Uploads the fixed YAML back to the same stage path
  5. Re-downloads and verifies

Usage:
    uv run python scripts/add_join_keys.py
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.snowflake_client import SnowflakeClient

KEY_DATA_TYPE = "NUMBER(38,0)"


def _declared_columns(table: dict[str, Any]) -> set[str]:
    cols: set[str] = set()
    for section in ("dimensions", "facts", "time_dimensions"):
        for item in table.get(section) or []:
            if isinstance(item, dict) and item.get("name"):
                cols.add(str(item["name"]).upper())
    return cols


def audit(data: dict[str, Any]) -> dict[str, set[str]]:
    """Return {table_name: {missing_column, ...}} for relationships."""
    tables = {
        str(t["name"]).upper(): t for t in data.get("tables", []) if isinstance(t, dict)
    }
    declared = {name: _declared_columns(t) for name, t in tables.items()}
    missing: dict[str, set[str]] = {}

    for rel in data.get("relationships", []) or []:
        if not isinstance(rel, dict):
            continue
        lt = str(rel.get("left_table", "")).upper()
        rt = str(rel.get("right_table", "")).upper()
        for rc in rel.get("relationship_columns", []) or []:
            if not isinstance(rc, dict):
                continue
            lc = str(rc.get("left_column", "")).upper()
            rc_ = str(rc.get("right_column", "")).upper()
            if lt in declared and lc and lc not in declared[lt]:
                missing.setdefault(lt, set()).add(lc)
            if rt in declared and rc_ and rc_ not in declared[rt]:
                missing.setdefault(rt, set()).add(rc_)
    return missing


def patch(data: dict[str, Any], missing: dict[str, set[str]]) -> int:
    """Insert missing columns as dimensions on the referenced tables. Returns count added."""
    added = 0
    for table in data.get("tables", []):
        if not isinstance(table, dict):
            continue
        tname = str(table.get("name", "")).upper()
        if tname not in missing:
            continue
        dims = table.setdefault("dimensions", [])
        if not isinstance(dims, list):
            continue
        existing = {
            str(d.get("name", "")).upper()
            for d in dims
            if isinstance(d, dict)
        }
        for col in sorted(missing[tname]):
            if col in existing:
                continue
            dims.append(
                {
                    "name": col,
                    "expr": col,
                    "data_type": KEY_DATA_TYPE,
                    "description": "Foreign-key column (added for Cortex Analyst relationship validation).",
                }
            )
            added += 1
    return added


def main() -> int:
    cfg = Config.from_env()
    sf = SnowflakeClient(cfg)
    stage_path = cfg.semantic_model_stage_path
    stage_dir = stage_path.rsplit("/", 1)[0]
    filename = stage_path.rsplit("/", 1)[-1]

    print(f"Source: {stage_path}")
    print()

    # STEP 1: Download + parse
    print("STEP 1: Downloading and parsing YAML...")
    local = sf.download_from_stage(stage_path)
    text = local.read_text()

    ryaml = YAML(typ="rt", pure=True)  # round-trip preserves formatting
    ryaml.preserve_quotes = True
    data = ryaml.load(text)
    if not isinstance(data, dict):
        print("  ✗ YAML did not parse as a mapping.")
        return 1

    initial_missing = audit(data)
    if not initial_missing:
        print("  ✓ No missing relationship columns. Nothing to fix.")
        return 0
    print(f"  Found missing columns on {len(initial_missing)} tables:")
    for t, cols in initial_missing.items():
        print(f"    {t}: {sorted(cols)}")
    print()

    # STEP 2: Patch in-memory
    print("STEP 2: Adding missing dimensions...")
    added = patch(data, initial_missing)
    print(f"  Added {added} dimensions.")
    remaining = audit(data)
    if remaining:
        print(f"  ✗ Still missing after patch: {remaining}")
        return 2
    print("  ✓ All relationship columns now declared.")
    print()

    # STEP 3: Dump to file
    print("STEP 3: Writing patched YAML...")
    out_dir = Path(tempfile.mkdtemp(prefix="add_join_keys_"))
    out_path = out_dir / filename
    buf = io.StringIO()
    ryaml.dump(data, buf)
    out_path.write_text(buf.getvalue())
    print(f"  Wrote {len(buf.getvalue())} bytes to {out_path}")
    print()

    # STEP 4: Upload
    print("STEP 4: Uploading via PUT...")
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
        for row in rows:
            print(f"  PUT result: {dict(zip(cols, row))}")
        if cols and "status" in cols:
            status_idx = cols.index("status")
            statuses = [r[status_idx] for r in rows]
            if not all(s.upper() == "UPLOADED" for s in statuses):
                print("  ✗ PUT did not report UPLOADED for all rows.")
                return 3
    except Exception as e:
        print(f"  ✗ PUT raised: {type(e).__name__}: {e}")
        return 4
    finally:
        cur.close()
    print()

    # STEP 5: Re-download + verify
    print("STEP 5: Re-downloading from stage to verify fix took...")
    verify_local = sf.download_from_stage(stage_path)
    verify_text = verify_local.read_text()
    verify_data = ryaml.load(verify_text)
    verify_missing = audit(verify_data) if isinstance(verify_data, dict) else {}
    if verify_missing:
        print(f"  ✗ Still missing columns on stage: {verify_missing}")
        return 5
    print("  ✓ Stage YAML is clean — all relationship columns declared.")
    print()
    print("Restart Streamlit:")
    print("  Ctrl+C the running instance")
    print("  uv run streamlit run app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
