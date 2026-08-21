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
if [[ "$RUNNING_KERNEL" != *"$NEW_KERNEL"* ]] && [ -n "$NEW_KERNEL" ]; then
    # Only look at linux-lts module dirs, ignore mainline linux (e.g. 7.x) if installed
    INSTALLED_MODULES=$(ls /usr/lib/modules/ | grep -E '\-lts$' | sort -V | tail -1)
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
    # The reboot decision -- including the MD RAID safety check -- is made AT 05:00 by
    # kernel-reboot.service (see kernel-reboot-check.sh), not here. Deciding at 04:08 and
    # acting 51 minutes later is precisely what made mdraid-reboot-guard.timer necessary;
    # that unit was retired 2026-08-21 because the gap it policed no longer exists.
    MSG="$MSG Kernel updated ($RUNNING_KERNEL -> $INSTALLED_MODULES); kernel-reboot.timer reboots at 05:00 if the arrays are healthy."
fi
# Until 2026-08-21 the kernel-updated branch built MSG and then called shutdown WITHOUT
# ever calling telegram-send, so the one outcome that mattered most -- "your server is
# about to reboot" -- was the only one never announced.
telegram-send "$MSG"
echo "[$(date)] Auto-update finished (rc=$UPDATE_RC)" >> $LOG_FILE
