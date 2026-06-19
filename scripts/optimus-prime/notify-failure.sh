#!/bin/bash
set -euo pipefail

SERVICE="$1"
MAX_ALERTS=3  # notify individually for first N failures, then send one "suppressing" message
STATE_DIR="/run/notify-failure"
mkdir -p "$STATE_DIR"

COUNT_FILE="$STATE_DIR/${SERVICE}.count"
FLAG_FILE="$STATE_DIR/${SERVICE}.failed"

count=0
[[ -f "$COUNT_FILE" ]] && count=$(cat "$COUNT_FILE")
count=$((count + 1))
echo "$count" > "$COUNT_FILE"
touch "$FLAG_FILE"

if (( count <= MAX_ALERTS )); then
    telegram-send "❌ [optimusprime] Service ${SERVICE} FAILED (attempt ${count})"
elif (( count == MAX_ALERTS + 1 )); then
    telegram-send "⚠️ [optimusprime] Service ${SERVICE} keeps failing — suppressing further alerts until recovery"
fi
