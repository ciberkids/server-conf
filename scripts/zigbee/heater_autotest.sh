#!/bin/bash
# Fully automatic heater power-cycle test. Runs detached on Optimus Prime and does
# not depend on any Claude session staying alive.
#
# TRIGGER: a device_announce for one of the three pool plugs. That is a POSITIVE
# signal that the device rejoined, i.e. that it was actually power-cycled -
# unlike inferring it from silence, which produced two false positives.
#
# TEST: a raw network map with routes. A device that ANSWERS Mgmt_Lqi_req had a
# downlink unicast delivered at a known timestamp. That is the only
# success-detecting instrument available; absence of an error is NOT proof
# (failure latency tails out to at least 40 s).
#
# Everything is read-only: ZDO queries only, no relay state is ever changed.
set -u
OUT=/mnt/data/matteo/zigbee-forensics/2026-07-31/heater_autotest.log
DIR=/mnt/data/matteo/zigbee-forensics/2026-07-31
MAXHOURS=8

PUMP=a4c13839620fc0b3
HEATER=a4c13859562db40c
SALIN=a4c138ca1c6b474b

log() { echo "[$(date '+%F %T')] $*" >> "$OUT"; }

log "=== autotest armed (waiting up to ${MAXHOURS}h for a plug device_announce) ==="
log "reference state 19:27: all three plugs failed lqi; Mosquito + Pool sensor delivered"

LOGDIR=$(ls -1dt /mnt/data/docker_persistent/zigbee2mqtt/data/log/*/ | head -1)
MARK=$(wc -l < "${LOGDIR}log.log")
DEADLINE=$(( $(date +%s) + MAXHOURS * 3600 ))

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  LOGDIR=$(ls -1dt /mnt/data/docker_persistent/zigbee2mqtt/data/log/*/ | head -1)
  CUR=$(wc -l < "${LOGDIR}log.log")
  # a rotation resets the offset; start again from the top of the new file
  [ "$CUR" -lt "$MARK" ] && MARK=0

  HIT=$(tail -n +$((MARK + 1)) "${LOGDIR}log.log" \
        | grep -E "device_announce" \
        | grep -E "$PUMP|$HEATER|$SALIN" | tail -1)

  if [ -n "$HIT" ]; then
    log "TRIGGER: plug device_announce detected"
    log "  $(echo "$HIT" | cut -c1-200)"
    case "$HIT" in
      *$HEATER*) log "  -> HEATER rejoined (this is the intended test)" ;;
      *$PUMP*)   log "  -> PUMP rejoined (NOT the intended target)" ;;
      *$SALIN*)  log "  -> SALINATOR rejoined (NOT the intended target)" ;;
    esac

    log "settling 90 s before probing, to let the rejoin complete"
    sleep 90

    for round in 1 2 3; do
      log "--- map round $round ---"
      /tmp/get_networkmap.sh >> "$OUT" 2>&1
      # the map takes ~10-12 min for 60 devices; poll generously
      for i in $(seq 1 30); do
        sz=$(sudo podman exec mqtt5 sh -c 'wc -c < /tmp/nm.json' 2>/dev/null | tr -d ' ')
        [ "${sz:-0}" -gt 100000 ] && break
        sleep 30
      done
      TS=$(date '+%H%M')
      F="$DIR/networkmap_autotest_${TS}.json"
      sudo podman exec mqtt5 cat /tmp/nm.json > "$F" 2>/dev/null
      log "map saved: $F ($(wc -c < "$F") bytes)"
      python3 /tmp/parse_map.py "$F" >> "$OUT" 2>&1
      # rounds 2 and 3 measure whether any recovery decays
      [ "$round" -lt 3 ] && { log "waiting 20 min to test for decay"; sleep 1200; }
    done

    log "=== autotest COMPLETE - read the three map blocks above ==="
    exit 0
  fi
  MARK=$CUR
  sleep 30
done

log "=== autotest EXPIRED after ${MAXHOURS}h with no plug device_announce ==="
log "No power-cycle was detected, so no conclusion can be drawn either way."
exit 2
