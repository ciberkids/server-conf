#!/usr/bin/env bash
# disk-identify.sh — Identify physical drives by keeping the activity LED lit
#
# Usage:
#   disk-identify.sh list             # show all drives grouped by cable/connector
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

RED='\033[1;31m'
YEL='\033[1;33m'
GRN='\033[1;32m'
CYN='\033[1;36m'
DIM='\033[2m'
RST='\033[0m'

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

# ── list command ─────────────────────────────────────────────────────────────

list_drives() {
    # Collect SMART CRC errors for all drives up front (one smartctl call each)
    declare -A CRC_MAP
    for dev in sda sdb sdc sdd sde sdf sdg sdh sdi sdj sdk sdl sdm; do
        [[ -b /dev/$dev ]] || continue
        crc=$(sudo smartctl -A /dev/"$dev" 2>/dev/null \
            | awk '/UDMA_CRC_Error_Count/ {print $10; found=1} END{if(!found) print "0"}')
        CRC_MAP[$dev]="${crc:-0}"
    done

    # Helper: print one drive row
    print_row() {
        local slot="$1" dev="$2"
        local model size serial crc raid crc_str crc_color

        model=$(cat /sys/block/"$dev"/device/model 2>/dev/null | xargs | cut -c1-22)
        size=$(awk '{printf "%.1fT", $1 * 512 / 1e12}' /sys/block/"$dev"/size 2>/dev/null)
        serial=$(sudo smartctl -i /dev/"$dev" 2>/dev/null | awk '/Serial Number:/ {print $NF}')
        crc="${CRC_MAP[$dev]:-0}"
        raid=$(grep -E "md[0-9]+" /proc/mdstat 2>/dev/null \
            | grep "${dev}[0-9 ]" | awk '{print $1}' | paste -sd ',' - || true)

        if   [[ "$crc" -ge 10000 ]]; then crc_color="$RED"
        elif [[ "$crc" -ge 1    ]]; then crc_color="$YEL"
        else                              crc_color="$GRN"
        fi
        crc_str=$(printf "${crc_color}%6s${RST}" "$crc")

        printf "  ${DIM}%-4s${RST}  ${YEL}/dev/%-4s${RST}  %-22s  %5s  %-22s  %s  %s\n" \
            "$slot" "$dev" "$model" "$size" "${serial:-unknown}" "$crc_str" "${raid:-—}"
    }

    local header_fmt="  %-4s  %-9s  %-22s  %5s  %-22s  %6s  %s\n"

    # ── Adaptec 1100-8i HBA ───────────────────────────────────────────────────
    echo ""
    printf "${CYN}Adaptec 1100-8i HBA (PCI 0c:00.0 — smartpqi driver)${RST}\n"
    printf "${DIM}%s${RST}\n" "────────────────────────────────────────────────────────────────────────────────"

    # Determine which connector each HBA drive is on from its sysfs port number
    # port-9:1..4 → CN0, port-9:5..8 → CN1
    declare -A PORT_MAP
    for dev in sdf sdg sdh sdi sdj sdk sdl sdm; do
        [[ -b /dev/$dev ]] || continue
        port=$(readlink -f /sys/block/"$dev"/device 2>/dev/null \
            | grep -oP 'port-9:\K[0-9]+')
        PORT_MAP[$dev]="${port:-?}"
    done

    for cn in 0 1; do
        local lo=$(( cn * 4 + 1 ))
        local hi=$(( cn * 4 + 4 ))
        # Check if any drive on this connector has CRC errors
        local cn_warn=""
        for dev in "${!PORT_MAP[@]}"; do
            port="${PORT_MAP[$dev]}"
            if [[ "$port" -ge "$lo" && "$port" -le "$hi" ]] 2>/dev/null; then
                crc="${CRC_MAP[$dev]:-0}"
                if [[ "$crc" -gt 0 ]]; then cn_warn=" ${YEL}← errors detected${RST}"; fi
            fi
        done

        printf "\n  ${CYN}Cable CN%s${RST} (SFF-8643 connector %s, ports %s–%s)%b\n" \
            "$cn" "$(( cn + 1 ))" "$lo" "$hi" "$cn_warn"
        printf "  $header_fmt" "Slot" "Device" "Model" "Size" "Serial" "CRC" "RAID"
        printf "  ${DIM}%s${RST}\n" "──────────────────────────────────────────────────────────────────────────"

        for dev in sdf sdg sdh sdi sdj sdk sdl sdm; do
            [[ -b /dev/$dev ]] || continue
            port="${PORT_MAP[$dev]:-?}"
            if [[ "$port" -ge "$lo" && "$port" -le "$hi" ]] 2>/dev/null; then
                print_row "[$port]" "$dev"
            fi
        done
    done

    # ── AMD SATA controller ───────────────────────────────────────────────────
    echo ""
    printf "\n${CYN}AMD SATA controller (PCI 01:00.1 — direct SATA)${RST}\n"
    printf "${DIM}%s${RST}\n" "────────────────────────────────────────────────────────────────────────────────"
    printf "  $header_fmt" "ATA" "Device" "Model" "Size" "Serial" "CRC" "RAID"
    printf "  ${DIM}%s${RST}\n" "──────────────────────────────────────────────────────────────────────────"
    for dev in sda sdb sdc sdd sde; do
        [[ -b /dev/$dev ]] || continue
        ata=$(readlink -f /sys/block/"$dev"/device 2>/dev/null | grep -oP 'ata\K[0-9]+')
        print_row "ata$ata" "$dev"
    done

    echo ""
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

elif [[ "$1" == "list" ]]; then
    list_drives

elif [[ $# -ge 1 ]]; then
    dev="${1#/dev/}"  # strip /dev/ prefix if provided
    secs="${2:-$DEFAULT_TIME}"

    if [[ ! -b /dev/$dev ]]; then
        echo "Error: /dev/$dev is not a block device." >&2
        exit 1
    fi

    light_up "$dev" "$secs"
fi
