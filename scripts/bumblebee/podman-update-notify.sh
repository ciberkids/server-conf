#!/bin/bash
# Podman auto-update with clean Telegram notification.
# Sends only the names of updated containers, no raw image pull output.

output=$(/usr/bin/podman auto-update 2>&1)
rc=$?

# Extract friendly names from updated rows (format: "hash (name)" in UPDATED=true rows)
updated_names=$(echo "$output" | awk '$NF=="true" { match($0, /\(([^)]+)\)/, a); if (a[1]) print a[1] }')
count=$(printf '%s\n' "$updated_names" | grep -c . || true)

if [ "$count" -gt 0 ]; then
    list=$(printf '%s\n' "$updated_names" | paste -sd ', ')
    /usr/local/bin/telegram-send --config /etc/telegram-send.conf --disable-web-page-preview "[bumblebee] $count container(s) updated: $list"
else
    /usr/local/bin/telegram-send --config /etc/telegram-send.conf --disable-web-page-preview "[bumblebee] All containers up to date."
fi

exit $rc
