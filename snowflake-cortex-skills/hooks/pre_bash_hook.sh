#!/usr/bin/env bash
# PreToolUse/Bash hook — logs commands and blocks destructive Snowflake DDL in CI

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="/tmp/snowflake_cortex_bash.log"
echo "[$TIMESTAMP] $COMMAND" >> "$LOG_FILE"

# Block accidental DROP TABLE / DROP DATABASE in non-interactive shells
if echo "$COMMAND" | grep -qiE '^\s*(DROP\s+(TABLE|DATABASE|SCHEMA|WAREHOUSE))'; then
  echo '{"decision":"block","reason":"Destructive Snowflake DDL blocked by pre_bash_hook. Run manually if intentional."}'
  exit 0
fi

exit 0
