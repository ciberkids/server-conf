#!/bin/bash
# Weekly podman housekeeping. Runs on BOTH optimusprime and bumblebee.
#
# WHY: bumblebee's 70 GB root filesystem hit 100 % on 2026-08-21 and took every service
# down for 26 h. Dangling image layers accumulate steadily because every quadlet uses
# AutoUpdate=registry -- 14 of them (~20 GB) had built up unnoticed.
# See reports/incident-20260821-bumblebee-disk-full.md
#
# NEVER ADD -a / --all TO THE IMAGE PRUNE.
# Plain `podman image prune` removes only DANGLING (untagged) images.
# `--all` also removes unused TAGGED images -- which includes locally-built ones that
# have no registry to be re-pulled from:
#     optimusprime : localhost/plex-amd, localhost/zigbee2mqtt-mcp
#     bumblebee    : localhost/hermes-agent
# `podman image prune -a` at boot already destroyed hermes-agent once and took Hermes
# offline for four days. This script verifies those images survive and shouts if not.

set -o pipefail
LOG=/var/log/podman-prune.log
HOST=$(hostname -s)
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
# The two hosts diverge and hardcoding either one fails silently on the other:
#   optimusprime : /usr/bin/telegram-send        (uses root's ~/.config/telegram-send.conf)
#   bumblebee    : /usr/local/bin/telegram-send  (needs --config /etc/telegram-send.conf)
TG=$(command -v telegram-send 2>/dev/null || true)
TG_CONF=""; [ -r /etc/telegram-send.conf ] && TG_CONF="--config /etc/telegram-send.conf"
notify(){
    if [ -z "$TG" ]; then log "telegram-send NOT FOUND -- no notification sent"; return; fi
    # shellcheck disable=SC2086
    "$TG" $TG_CONF "$1" >/dev/null 2>&1 || log "telegram-send FAILED (rc=$?)"
}

avail(){ df --output=avail -B1 / | tail -1 | tr -d ' '; }
pct(){ df --output=pcent / | tail -1 | tr -d ' %'; }

BEFORE=$(avail); PCT_BEFORE=$(pct)
mapfile -t LOCAL_BEFORE < <(podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep '^localhost/' | sort)

log "start: / at ${PCT_BEFORE}% used, $((BEFORE/1024/1024/1024))GB free, ${#LOCAL_BEFORE[@]} local images"

# Stopped containers first: ephemeral CI job containers hold whole image layers open,
# so pruning images before containers frees much less.
podman container prune -f >>"$LOG" 2>&1
podman image prune -f     >>"$LOG" 2>&1   # <-- NO -a. See the warning above.

AFTER=$(avail); PCT_AFTER=$(pct)
FREED=$(( (AFTER - BEFORE) / 1024 / 1024 ))

mapfile -t LOCAL_AFTER < <(podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep '^localhost/' | sort)
MISSING=""
for img in "${LOCAL_BEFORE[@]}"; do
    printf '%s\n' "${LOCAL_AFTER[@]}" | grep -qxF "$img" || MISSING="$MISSING $img"
done
if [ -n "$MISSING" ]; then
    log "FATAL: locally-built image(s) disappeared:$MISSING"
    notify "[$HOST] podman-prune DESTROYED locally-built image(s):$MISSING -- these cannot be re-pulled. Rebuild required."
    exit 1
fi

log "done: freed ${FREED}MiB, / now ${PCT_AFTER}% used, all ${#LOCAL_AFTER[@]} local images intact"

# Notify only when it actually mattered, or when the disk is still uncomfortable.
# A weekly "freed 0 MB" message is noise, and noise is how real alerts get ignored.
if [ "$FREED" -ge 1024 ] || [ "$PCT_AFTER" -ge 85 ]; then
    notify "[$HOST] podman-prune freed $((FREED/1024))GB -- / now ${PCT_AFTER}% used ($((AFTER/1024/1024/1024))GB free). Local images intact."
fi
