#!/bin/bash
# ExecCondition for kernel-reboot.service. Decides, AT 05:00, whether to reboot.
#
# Exit 0    -> proceed, kernel-reboot.service reboots the host
# Exit 1    -> skip. systemd marks the unit "skipped", NOT "failed", so the unit's
#              OnFailure=notify-failure@ stays quiet on the ~364 days a year with no
#              kernel update. That three-way semantic is why this is an ExecCondition
#              and not an ExecStartPre (which would mark the unit failed and alert).
#
# The check is deliberately STATELESS -- it re-derives everything from uname and
# /proc/mdstat rather than reading a flag written by auto-update.sh at 04:08. That is
# the whole point of the 2026-08-21 refactor: the old design decided at 04:08 and acted
# at 05:00, and mdraid-reboot-guard.timer existed only to police that 51-minute gap.

RUNNING_KERNEL=$(uname -r)
# Only consider linux-lts module dirs; mainline linux (7.x) is installed but not booted.
INSTALLED_MODULES=$(ls /usr/lib/modules/ | grep -E '\-lts$' | sort -V | tail -1)

if [ -z "$INSTALLED_MODULES" ]; then
    echo "No linux-lts module directory found; refusing to reboot."
    exit 1
fi

if [ "$RUNNING_KERNEL" = "$INSTALLED_MODULES" ]; then
    echo "Running kernel $RUNNING_KERNEL is already current; nothing to do."
    exit 1
fi

# Never reboot into a rebuild. '[.*_' catches a degraded array (a missing member shows
# as _ in the [UUUU] map), the words catch an active resync/recovery/reshape/check.
# auto-update.timer fires at 04:08 and paru builds AUR packages; if a build runs long we
# must not reboot mid-transaction. (The old `shutdown -r 05:00` had the same exposure.)
if [ -e /var/lib/pacman/db.lck ]; then
    echo "pacman transaction still in progress; deferring reboot."
    exit 1
fi

if grep -qE 'resync|recovery|reshape|check|\[.*_' /proc/mdstat; then
    echo "MD array degraded or rebuilding; deferring reboot."
    telegram-send "[optimus-prime] Kernel $RUNNING_KERNEL -> $INSTALLED_MODULES is pending, but an MD array is degraded/rebuilding — reboot DEFERRED. Will retry at 05:00 tomorrow."
    exit 1
fi

echo "Kernel $RUNNING_KERNEL -> $INSTALLED_MODULES and all arrays healthy; rebooting."
exit 0
