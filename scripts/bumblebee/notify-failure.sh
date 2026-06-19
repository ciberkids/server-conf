#!/bin/bash
set -euo pipefail

SERVICE="$1"
MAX_ALERTS=3
STATE_DIR="/run/notify-failure"
mkdir -p "$STATE_DIR"

COUNT_FILE="$STATE_DIR/${SERVICE}.count"
FLAG_FILE="$STATE_DIR/${SERVICE}.failed"

# Check if systemd gave up restarting (start-limit-hit → SubState=failed)
# vs a transient failure that will be retried (SubState=auto-restart)
substate=$(systemctl show "${SERVICE}" -p SubState --value 2>/dev/null || echo "unknown")
if [[ "$substate" == "failed" ]]; then
    touch "$FLAG_FILE"
    telegram-send --config /etc/telegram-send.conf "🔴 [bumblebee] Service ${SERVICE} hit restart limit — needs manual reset"
    exit 0
fi

# Transient failure — service will be retried by systemd
count=0
[[ -f "$COUNT_FILE" ]] && count=$(cat "$COUNT_FILE")
count=$((count + 1))
echo "$count" > "$COUNT_FILE"
touch "$FLAG_FILE"

if (( count <= MAX_ALERTS )); then
    telegram-send --config /etc/telegram-send.conf "❌ [bumblebee] Service ${SERVICE} FAILED (attempt ${count})"
elif (( count == MAX_ALERTS + 1 )); then
    telegram-send --config /etc/telegram-send.conf "⚠️ [bumblebee] Service ${SERVICE} keeps failing — suppressing further alerts until recovery"
fi
