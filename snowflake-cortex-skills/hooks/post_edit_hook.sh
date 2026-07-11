#!/usr/bin/env bash
# PostToolUse/Edit|Write hook — auto-format Python files with ruff

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path') or d.get('path',''))" 2>/dev/null)

if [[ "$FILE" == *.py ]]; then
  if command -v ruff &>/dev/null; then
    ruff format "$FILE" --quiet
    ruff check "$FILE" --fix --quiet
    echo "[post_edit_hook] Formatted $FILE with ruff" >&2
  fi
fi

exit 0
