#!/usr/bin/env bash
# Stop hook — log session summary

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] Claude session ended in snowflake-cortex-skills" >> /tmp/snowflake_cortex_sessions.log
exit 0
