#!/usr/bin/env bash
# Notification hook — fires when Claude needs the user's attention.
# On macOS, shows a system notification. On other platforms, prints to stderr.

MESSAGE=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message','Claude needs your attention'))" 2>/dev/null)
MESSAGE="${MESSAGE:-Claude needs your attention}"

if [[ "$(uname)" == "Darwin" ]]; then
  osascript -e "display notification \"$MESSAGE\" with title \"Claude Code\"" 2>/dev/null
else
  echo "NOTIFICATION: $MESSAGE" >&2
fi

exit 0
