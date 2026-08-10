#!/usr/bin/env bash
# Regenerate every floorplan build artifact from the CAD plans.
#
# The JSON, verify SVGs and numbered overlays are build artifacts and are NOT committed
# (see docs/ha-3d-floorplan.md). This rebuilds all of them from scratch, so nothing is
# lost by a reboot or by clearing a scratchpad.
#
# Usage:  ./regen.sh [output-dir]        (default: ./build, which is gitignored)

set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-./build}"
PLANS="$HOME/Insync/matteofavaro@gmail.com/Google Drive/Manu & I/Documents/Personal Documents/House/House Sirnach/Documentation house plans/3_Elektropläne"

if [[ ! -d "$PLANS" ]]; then
    echo "ERROR: plans not found at:" >&2
    echo "  $PLANS" >&2
    echo "Is Insync running and the Google Drive mirror synced?" >&2
    exit 1
fi

mkdir -p "$OUT"

# floor label : plan filename
FLOORS=(
    "ground:0. erdgeschoss (1)_inst NEU.PDF"
    "first:1. obergeschoss (1)_inst NEU.PDF"
    "basement:-1. untergeschoss (1)_inst NEU.PDF"
)

for spec in "${FLOORS[@]}"; do
    floor="${spec%%:*}"
    file="${spec#*:}"
    echo "=== $floor"
    ./extract_plan.py "$PLANS/$file" --floor "$floor" \
        --out "$OUT/$floor.json" --verify "$OUT/verify_$floor.svg"
    ./lamp_overlay.py "$PLANS/$file" "$OUT/$floor.json" \
        --out "$OUT/overlay_$floor.svg"

    if command -v inkscape >/dev/null; then
        inkscape "$OUT/verify_$floor.svg"  -o "$OUT/verify_$floor.png"  -w 1700 2>/dev/null
        inkscape "$OUT/overlay_$floor.svg" -o "$OUT/overlay_$floor.png" -w 2400 2>/dev/null
    fi
done

echo
echo "Expected (regression check — if these drift, something changed):"
echo "  ground    69 walls  114.0 m  39 outlets (20 recessed / 19 surface)"
echo "  first     35 walls  116.1 m  22 outlets (11 / 11)"
echo "  basement  11 walls   54.6 m   5 outlets (0 / 5)"
echo
echo "Artifacts in: $OUT"
echo "  verify_<floor>.png   extracted walls + lamp dots — compare against the real plan"
echo "  overlay_<floor>.png  numbered outlets over the plan — for entity mapping"
