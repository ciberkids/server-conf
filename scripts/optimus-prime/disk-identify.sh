#!/usr/bin/env bash
# disk-identify.sh — Identify physical drives by keeping the activity LED lit
#
# Usage:
#   disk-identify.sh                  # cycle ALL HDDs, 5 seconds each
#   disk-identify.sh sdj              # light up sdj for 5 seconds
#   disk-identify.sh sdj 15           # light up sdj for 15 seconds
#
# How it works: runs dd (sequential reads) in the background to keep the
# activity LED continuously on, then kills it after the timer expires.
# conv=noerror,sync ensures bad sectors (e.g. sdj) don't abort the read.

set -euo pipefail

DEFAULT_TIME=5
ALL_DRIVES=(sdf sdg sdh sdi sdj sdk sdl sdm)  # Adaptec HBA drives (slots 1-8)

# ── helpers ──────────────────────────────────────────────────────────────────

get_info() {
    local dev="$1"
    local model size_gb serial crc_errors raid

    model=$(cat /sys/block/"$dev"/device/model 2>/dev/null | xargs)
    size_gb=$(awk '{printf "%.1f TB", $1 * 512 / 1e12}' /sys/block/"$dev"/size 2>/dev/null)
    serial=$(sudo smartctl -i /dev/"$dev" 2>/dev/null | awk '/Serial Number:/ {print $NF}')
    crc_errors=$(sudo smartctl -A /dev/"$dev" 2>/dev/null \
        | awk '/UDMA_CRC_Error_Count/ {print $10}')
    raid=$(grep -E "md[0-9]+" /proc/mdstat 2>/dev/null \
        | grep "${dev}[0-9 ]" | awk '{print $1}' | paste -sd ',' -)

    echo "Model:    ${model:-unknown}"
    echo "Size:     ${size_gb:-unknown}"
    echo "Serial:   ${serial:-unknown}"
    echo "CRC Err:  ${crc_errors:-0}${crc_errors:+ ← check cable!}"
    echo "RAID:     ${raid:-none}"
}

light_up() {
    local dev="$1"
    local secs="$2"

    echo ""
    echo "┌─────────────────────────────────────────────────────┐"
    printf  "│  \033[1;33m/dev/%-5s\033[0m — LED active for %s seconds            │\n" "$dev" "$secs"
    echo "├─────────────────────────────────────────────────────┤"
    get_info "$dev" | while IFS= read -r line; do
        printf "│  %-51s│\n" "$line"
    done
    echo "└─────────────────────────────────────────────────────┘"

    # Start sustained sequential read in background
    dd if=/dev/"$dev" of=/dev/null bs=4M conv=noerror,sync status=none 2>/dev/null &
    DD_PID=$!

    # Countdown
    for ((i=secs; i>0; i--)); do
        printf "  \r  Reading... %2ds remaining  " "$i"
        sleep 1
    done
    printf "\r  Done.                        \n"

    kill "$DD_PID" 2>/dev/null || true
    wait "$DD_PID" 2>/dev/null || true
}

# ── main ─────────────────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
    # Cycle all drives
    echo "Cycling all HBA drives (${DEFAULT_TIME}s each). Watch the LEDs!"
    echo "Press Ctrl+C to stop early."
    echo ""
    for dev in "${ALL_DRIVES[@]}"; do
        if [[ -b /dev/$dev ]]; then
            light_up "$dev" "$DEFAULT_TIME"
            sleep 1
        else
            echo "  /dev/$dev not found, skipping."
        fi
    done
    echo ""
    echo "All done."

elif [[ $# -ge 1 ]]; then
    dev="${1#/dev/}"  # strip /dev/ prefix if provided
    secs="${2:-$DEFAULT_TIME}"

    if [[ ! -b /dev/$dev ]]; then
        echo "Error: /dev/$dev is not a block device." >&2
        exit 1
    fi

    light_up "$dev" "$secs"
fi
