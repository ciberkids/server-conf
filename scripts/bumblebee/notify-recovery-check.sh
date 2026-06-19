#!/bin/bash
STATE_DIR="/run/notify-failure"
[[ -d "$STATE_DIR" ]] || exit 0

shopt -s nullglob
for flag in "$STATE_DIR"/*.failed; do
    service=$(basename "$flag" .failed)
    state=$(systemctl is-active "$service" 2>/dev/null)
    if [[ "$state" == "active" ]]; then
        count=0
        count_file="$STATE_DIR/${service}.count"
        [[ -f "$count_file" ]] && count=$(cat "$count_file")
        rm -f "$flag" "$count_file"
        telegram-send --config /etc/telegram-send.conf "✅ [bumblebee] Service ${service} RECOVERED (was down ${count} attempt(s))"
    fi
done
