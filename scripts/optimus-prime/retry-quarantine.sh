#!/usr/bin/env bash
# Re-submit quarantined movies for processing.
#
# The movie renamer (movieProcessor.py) moves un-filable files to
# ToFix/_quarantine/ with a .quarantine.json sidecar and does NOT auto-retry.
# After you fix the cause (e.g. create the missing saga folder in "1 Sagas"),
# run this to move the files back to the top level of ToFix — the level-triggered
# movie-processor.path watcher then reprocesses them automatically. Same
# filesystem, so the move is an instant rename (no data copy).
#
# Usage:
#   retry-quarantine.sh              # retry ALL quarantined files
#   retry-quarantine.sh <substring>  # retry only files whose name matches <substring>
set -euo pipefail

TOFIX="/mnt/MovieAndTvShows/ToFix"
QD="$TOFIX/_quarantine"
FILTER="${1:-}"

shopt -s nullglob
mkv=("$QD"/*.mkv)

if [ ${#mkv[@]} -eq 0 ]; then
  echo "Quarantine is empty — nothing to retry."
  exit 0
fi

n=0
for f in "${mkv[@]}"; do
  base="$(basename "$f")"
  if [ -n "$FILTER" ] && [[ "$base" != *"$FILTER"* ]]; then
    continue
  fi
  if mv -n "$f" "$TOFIX/$base"; then
    rm -f "$QD/$base.quarantine.json"
    echo "↩️  re-submitted: $base"
    n=$((n + 1))
  else
    echo "⚠️  skipped (target already exists?): $base"
  fi
done

if [ "$n" -eq 0 ]; then
  echo "No quarantined files matched '${FILTER}'."
else
  echo "Re-submitted $n file(s) to ToFix — the watcher will reprocess them shortly."
fi
