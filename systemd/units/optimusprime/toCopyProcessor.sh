#!/bin/bash
# Copies .mkv files from toCopy → ToFix, notifies Telegram per file, deletes source on success.
set -euo pipefail

TOFIX_DIR="/mnt/MovieAndTvShows/ToFix"
TOCOPY_DIR="/mnt/downloads/toCopy"

shopt -s nullglob
files=("${TOCOPY_DIR}"/*.mkv)

if [[ ${#files[@]} -eq 0 ]]; then
    exit 0
fi

for f in "${files[@]}"; do
    name=$(basename "$f")
    size=$(du -sh "$f" | cut -f1)
    if rsync -av --remove-source-files "$f" "${TOFIX_DIR}/"; then
        telegram-send --format html "📥 Copied to ToFix: <code>${name}</code> (${size})"
    else
        telegram-send "❌ toCopy copy failed: ${name}"
    fi
done
