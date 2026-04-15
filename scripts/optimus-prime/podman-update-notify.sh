#!/bin/bash
# Podman auto-update with clean Telegram notification.
# Sends only the names of updated containers, no raw image pull output.

output=$(podman auto-update 2>&1)
rc=$?

# Extract friendly names from updated rows (format: "hash (name)" in UPDATED=true rows)
updated_names=$(echo "$output" | awk '$NF=="true" { match($0, /\(([^)]+)\)/, a); if (a[1]) print a[1] }')
count=$(printf '%s\n' "$updated_names" | grep -c . || true)

if [ "$count" -gt 0 ]; then
    list=$(printf '%s\n' "$updated_names" | paste -sd ', ')
    telegram-send --disable-web-page-preview "[optimus-prime] $count container(s) updated: $list"
else
    telegram-send --disable-web-page-preview "[optimus-prime] All containers up to date."
fi

exit $rc
