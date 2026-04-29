#!/bin/bash
# Schedule a reboot after an NVIDIA package upgrade.
# Called by the dnf post-transaction-actions plugin; may fire once per matched package.
if [ -f /run/systemd/shutdown/scheduled ]; then
    exit 0
fi
logger -t nvidia-reboot "NVIDIA package upgraded — scheduling reboot in 5 minutes"
shutdown -r +5 'Rebooting: NVIDIA driver upgrade detected'
