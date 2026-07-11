#!/usr/bin/env bash
# PreToolUse hook — runs before every Bash tool call.
# Claude Code passes tool input as JSON on stdin.
#
# Exit codes:
#   0  — allow the tool call to proceed
#   2  — block the tool call and show the output to Claude as feedback

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null)

# Log every command
LOGFILE="/tmp/claude_bash_audit.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $COMMAND" >> "$LOGFILE"

# Block irreversible destructive commands
if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+/[^/]|rm\s+-rf\s+~'; then
  echo "BLOCKED: Refusing to run destructive command: $COMMAND" >&2
  exit 2
fi

# Block force-push to protected branches
if echo "$COMMAND" | grep -qE 'git push.*--force.*main|git push.*-f.*main'; then
  echo "BLOCKED: Force-push to main is not allowed." >&2
  exit 2
fi

exit 0
