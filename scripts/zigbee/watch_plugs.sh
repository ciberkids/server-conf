#!/bin/bash
# Continuously capture every log line touching the three pool plugs, plus any
# join/announce/interview activity, so a power-cycle transition is recorded with
# precise timestamps. Append-only; safe to leave running.
OUT=/mnt/data/matteo/zigbee-forensics/2026-07-31/plug_watch.log
LOGDIR=$(ls -1dt /mnt/data/docker_persistent/zigbee2mqtt/data/log/*/ | head -1)
echo "=== watcher started $(date '+%F %T') on ${LOGDIR}log.log ===" >> "$OUT"
exec tail -F "${LOGDIR}log.log" \
  | grep --line-buffered -iE 'a4c13839620fc0b3|a4c13859562db40c|a4c138ca1c6b474b|announce|interview|been paired|joined' \
  >> "$OUT"
