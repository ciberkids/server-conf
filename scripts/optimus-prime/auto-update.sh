#!/bin/bash
# Arch Linux auto-update script
# Runs paru as matteo (required for AUR), sends Telegram digest

set -o pipefail

LOG_FILE="/var/log/auto-update.log"
RUNNING_KERNEL=$(uname -r)

echo "[$(date)] Starting auto-update" | tee $LOG_FILE

# Run paru as matteo for AUR support
# --noconfirm: auto-accept
# --sudoloop: keep sudo alive during long builds
UPDATE_OUTPUT=$(sudo -u matteo paru -Syu --noconfirm --sudoloop 2>&1)
UPDATE_RC=$?

echo "$UPDATE_OUTPUT" >> $LOG_FILE

# Count upgraded packages
UPGRADED=$(echo "$UPDATE_OUTPUT" | grep -c "upgrading ")
INSTALLED=$(echo "$UPDATE_OUTPUT" | grep -c "installing ")

# Check if kernel was updated
NEW_KERNEL=$(pacman -Q linux-lts 2>/dev/null | awk '{print $2}')
KERNEL_UPDATED=false
if [ "$RUNNING_KERNEL" != *"$NEW_KERNEL"* ] && [ -n "$NEW_KERNEL" ]; then
    # Compare installed kernel package with running kernel
    INSTALLED_MODULES=$(ls /usr/lib/modules/ | sort -V | tail -1)
    if [ "$RUNNING_KERNEL" != "$INSTALLED_MODULES" ]; then
        KERNEL_UPDATED=true
    fi
fi

# Clean old package cache (keep 2 versions)
paccache -rk2 -q 2>/dev/null
paccache -ruk0 -q 2>/dev/null

# Send Telegram notification
MSG="[optimus-prime] Auto-update complete: $UPGRADED upgraded, $INSTALLED installed."
if [ "$KERNEL_UPDATED" = true ]; then
    MSG="$MSG Kernel updated ($RUNNING_KERNEL -> $INSTALLED_MODULES). Reboot scheduled for 05:00."
    # Schedule reboot at 5 AM
    sudo shutdown -r 05:00 "Scheduled reboot after kernel update"
fi

telegram-send "$MSG"
echo "[$(date)] $MSG" >> $LOG_FILE
echo "[$(date)] Auto-update finished (rc=$UPDATE_RC)" >> $LOG_FILE
