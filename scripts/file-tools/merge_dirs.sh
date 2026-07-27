#!/usr/bin/env bash
# merge_dirs.sh
# Merge directory A into B (name/path-based), quarantining the files from A
# that already exist in B into a DUPLICATES directory for later deletion.
#
# Strategy (rsync --ignore-existing --remove-source-files):
#   Step 1  Copy only files unique to A into B, removing them from A as they
#           transfer. Files that already exist in B are SKIPPED, so they are
#           NOT removed -> they remain in A. After this, A holds only the
#           duplicates (files that already existed in B).
#   Step 2  Move those leftover duplicates from A into DUPLICATES/.
#   Step 3  Delete the now-empty directory skeleton left behind in A.
#
# IMPORTANT: this is NAME/PATH-based, not content-based. A file is treated as
# a duplicate only if the SAME relative path already exists in B. Same content
# under a different name/path is NOT detected (use the hash script for that).
#
# Usage:
#   merge_dirs.sh [--apply] [--duplicates DIR] <A_dir> <B_dir>
#
#   --apply           Actually perform the merge. WITHOUT this flag the script
#                     runs in dry-run mode (rsync -n) and changes NOTHING.
#   --duplicates DIR  Where to move A's duplicate files (default: ./duplicates)
#
# Examples:
#   merge_dirs.sh A/ B/                       # dry run, preview only
#   merge_dirs.sh --apply A/ B/               # merge, duplicates -> ./duplicates
#   merge_dirs.sh --apply --duplicates /tmp/dupes A/ B/

set -euo pipefail

APPLY=0
DUPLICATES="./duplicates"

POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply)      APPLY=1; shift ;;
        --duplicates) DUPLICATES="${2:-}"; shift 2 ;;
        -h|--help)    grep '^#' "$0" | sed 's/^#\{1,\} \{0,1\}//'; exit 0 ;;
        --) shift; POSITIONAL+=("$@"); break ;;
        -*) echo "Unknown option: $1" >&2; exit 1 ;;
        *)  POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]}"

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 [--apply] [--duplicates DIR] <A_dir> <B_dir>" >&2
    exit 1
fi

A="$1"
B="$2"

[[ -d "$A" ]] || { echo "Error: source directory '$A' does not exist" >&2; exit 1; }
[[ -d "$B" ]] || { echo "Error: destination directory '$B' does not exist" >&2; exit 1; }

# Normalise to trailing-slash form so rsync merges CONTENTS of A into B
# (rather than creating B/A/...). Collapse any duplicate trailing slashes.
A="${A%/}/"
B="${B%/}/"

# ---------------------------------------------------------------------------
if [[ "$APPLY" -eq 0 ]]; then
    echo "=== DRY RUN (no changes will be made) ==="
    echo "Would merge unique files from:  $A"
    echo "                          into:  $B"
    echo "Duplicates would be quarantined in: ${DUPLICATES%/}/"
    echo
    echo "--- Files that WOULD be transferred (unique to A) ---"
    rsync -avhn --ignore-existing "$A" "$B"
    echo
    echo "Re-run with --apply to perform the merge."
    exit 0
fi

echo "=== APPLYING MERGE ==="
mkdir -p "$DUPLICATES"

echo
echo "[Step 1/3] Merging unique files from A into B (removing them from A)..."
rsync -avh --ignore-existing --remove-source-files "$A" "$B"

echo
echo "[Step 2/3] Moving leftover duplicates from A into '${DUPLICATES%/}/'..."
# Anything still in A is a duplicate (existed in B, so it was skipped above).
rsync -avh --remove-source-files "$A" "${DUPLICATES%/}/"

echo
echo "[Step 3/3] Removing empty directory skeleton left in A..."
# --remove-source-files removes files, not directories; clean those up.
find "$A" -type d -empty -delete 2>/dev/null || true

echo
echo "=== DONE ==="
echo "  Unique files merged into : $B"
echo "  Duplicates quarantined in: ${DUPLICATES%/}/"
echo
echo "Review the duplicates, then delete when satisfied:"
echo "  rm -rf \"${DUPLICATES%/}/\""
