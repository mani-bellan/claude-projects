#!/usr/bin/env bash
# Stop hook — runs when Claude finishes a task.
# Appends a timestamped session summary to a local log.

LOGFILE="/tmp/claude_sessions.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Claude Code session ended in $(pwd)" >> "$LOGFILE"

exit 0
