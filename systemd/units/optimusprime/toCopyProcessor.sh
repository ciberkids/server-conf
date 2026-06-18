#!/bin/bash
# Copies .mkv files from toCopy → ToFix, notifies Telegram per file, deletes source on success.
set -euo pipefail

TOFIX_DIR="/mnt/MovieAndTvShows/ToFix"
TOCOPY_DIR="/mnt/downloads/toCopy"

tg_notify() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=$1" \
        --data-urlencode "parse_mode=HTML" > /dev/null
}

shopt -s nullglob
files=("${TOCOPY_DIR}"/*.mkv)

if [[ ${#files[@]} -eq 0 ]]; then
    exit 0
fi

for f in "${files[@]}"; do
    name=$(basename "$f")
    size=$(du -sh "$f" | cut -f1)
    if rsync -av --remove-source-files "$f" "${TOFIX_DIR}/"; then
        tg_notify "📥 Copied to ToFix: <code>${name}</code> (${size})"
    else
        tg_notify "❌ toCopy copy failed: <code>${name}</code>"
    fi
done
