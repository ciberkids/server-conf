#!/bin/bash
# Rebuild localhost/plex-amd:latest in lockstep with upstream plexinc/pms-docker:latest.
#
# Plex on Optimus Prime runs a LOCAL image (mesa-va-drivers layered on the official
# base for AMD /dev/dri transcoding), so `podman auto-update` can never update it.
# This script closes that gap: it re-pulls the upstream base and only rebuilds +
# restarts Plex when the base image DIGEST actually changes — so active streams are
# never interrupted on no-op days.
#
# Source of truth: git repo. Deployed to /usr/local/bin/plex-rebuild.sh
# Build context (Dockerfile) deployed to /etc/containers/build/plex/
# Driven by plex-rebuild.timer (daily 04:45).
set -uo pipefail

BASE_IMAGE="docker.io/plexinc/pms-docker:latest"
TARGET_IMAGE="localhost/plex-amd:latest"
BUILD_CONTEXT="/etc/containers/build/plex"
STATE_DIR="/var/lib/plex-autobuild"
DIGEST_FILE="$STATE_DIR/base.digest"
HOST="optimus-prime"
PMS='/usr/lib/plexmediaserver/Plex Media Server'

notify() { telegram-send --disable-web-page-preview "[$HOST] $1" || true; }
fail()   { notify "❌ Plex rebuild failed: $1"; exit 1; }

mkdir -p "$STATE_DIR"

# Pull the latest upstream base and read its digest.
podman pull -q "$BASE_IMAGE" >/dev/null 2>&1 || fail "could not pull $BASE_IMAGE"
new_digest=$(podman image inspect "$BASE_IMAGE" --format '{{.Digest}}' 2>/dev/null)
[ -n "$new_digest" ] || fail "could not read base digest"

old_digest=""
[ -f "$DIGEST_FILE" ] && old_digest=$(cat "$DIGEST_FILE")

# Nothing to do if the base is unchanged AND we already have the custom image.
if podman image exists "$TARGET_IMAGE" && [ "$new_digest" = "$old_digest" ]; then
    exit 0   # up to date — stay silent to avoid daily notification noise
fi

old_ver=$(podman exec plex "$PMS" --version 2>/dev/null | tr -d '\n')

# --pull=always guarantees the FROM matches the digest we just measured.
podman build --pull=always -t "$TARGET_IMAGE" "$BUILD_CONTEXT" >/dev/null 2>&1 \
    || fail "podman build error"

systemctl restart plex.service || fail "systemctl restart plex failed"

# Wait for the container to report healthy (HealthStartPeriod is 120s).
status=""
for _ in $(seq 1 30); do
    status=$(podman inspect --format '{{.State.Health.Status}}' plex 2>/dev/null)
    [ "$status" = "healthy" ] && break
    sleep 10
done
[ "$status" = "healthy" ] || fail "plex unhealthy after rebuild (status: ${status:-unknown})"

new_ver=$(podman exec plex "$PMS" --version 2>/dev/null | tr -d '\n')
echo "$new_digest" > "$DIGEST_FILE"

notify "✅ Plex rebuilt from upstream: ${old_ver:-unknown} → ${new_ver:-unknown}"
