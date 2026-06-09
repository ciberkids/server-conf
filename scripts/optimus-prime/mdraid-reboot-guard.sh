#!/bin/bash
# Cancel any pending scheduled reboot if an MD RAID array is actively rebuilding.
# Runs every 30 min via mdraid-reboot-guard.timer as belt-and-suspenders alongside
# the RAID check in auto-update.sh.

if grep -qE 'resync|recovery|reshape|check' /proc/mdstat; then
    if systemctl show shutdown.target --property=ActiveState 2>/dev/null | grep -q 'active\|activating'; then
        shutdown -c 2>/dev/null || true
        telegram-send "[optimus-prime] ⚠️ Scheduled reboot CANCELLED: RAID rebuild still in progress."
    fi
fi
