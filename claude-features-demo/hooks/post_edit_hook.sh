#!/usr/bin/env bash
# PostToolUse hook — runs after every Edit or Write tool call.
# Auto-formats Python files with ruff if it is available.
#
# Claude Code passes tool result JSON on stdin.

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('filePath', d.get('file_path','')))" 2>/dev/null)

if [[ "$FILE" == *.py ]]; then
  if command -v ruff &>/dev/null; then
    ruff format --quiet "$FILE" 2>/dev/null
    ruff check --fix --quiet "$FILE" 2>/dev/null
    echo "ruff: formatted $FILE"
  fi
fi

exit 0
