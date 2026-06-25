#!/bin/bash
# Cancel any pending scheduled reboot if any MD RAID array is rebuilding or degraded.
# Runs every 30 min via mdraid-reboot-guard.timer as belt-and-suspenders alongside
# the RAID check in auto-update.sh.

if grep -qE 'resync|recovery|reshape|check|\[.*_' /proc/mdstat; then
    if systemctl show shutdown.target --property=ActiveState 2>/dev/null | grep -q 'active\|activating'; then
        shutdown -c 2>/dev/null || true
        telegram-send "[optimus-prime] ⚠️ Scheduled reboot CANCELLED: RAID array degraded or rebuild in progress."
    fi
fi
