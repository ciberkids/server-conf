#!/bin/bash
# Downlink probe for the three pool plugs.
#
# READ-ONLY: publishes to zigbee2mqtt/<device>/get, which issues a ZCL Read
# Attributes on genOnOff. It does NOT change any relay state. Safe to run while
# the pump is filtering.
#
# v2 FIXES two defects found in v1 (v1 produced a FALSE RECOVERY at 18:17):
#   1. WAIT was shorter than the failure latency. herdsman runs up to 5 data
#      requests plus a ZDO_EXT_ROUTE_DISC before surfacing one error line, which
#      took ~16 s in practice. A 15 s wait therefore read "no failure yet" as
#      success. Default is now 40 s, and the measured latency is printed so the
#      margin stays visible.
#   2. The grep matched ANY NWK_NO_ROUTE for the device, including the plug's own
#      hourly genTime.readRsp. Now it matches 'genOnOff.read', which is uniquely
#      the signature of THIS probe - so a verdict can never be polluted by, or
#      rescued by, unrelated device-initiated traffic.
#
# Verdict logic: one probe = one downlink attempt at a known timestamp, so for
# THIS attempt an absent failure line is meaningful (unlike counting errors over
# a window - see feedback_error_log_is_not_a_success_log). Guards against log
# rotation, which would otherwise fake a clean result.
set -u
CFG=/mnt/data/docker_persistent/zigbee2mqtt/data/configuration.yaml
LOGDIR=$(ls -1dt /mnt/data/docker_persistent/zigbee2mqtt/data/log/*/ | head -1)
LOG="${LOGDIR}log.log"
WAIT="${1:-40}"

MU=$(sed -n '/^mqtt:/,/^[a-z]/{s/^  user:[[:space:]]*//p}' "$CFG" | head -1 | tr -d "'\"")
MW=$(sed -n '/^mqtt:/,/^[a-z]/{s/^  password:[[:space:]]*//p}' "$CFG" | head -1 | tr -d "'\"")

declare -A DEV=(
  [PUMP]='Outdoor Backyard Pool Pump Plug|a4c13839620fc0b3'
  [HEATER]='Outdoor Backyard Pool Heater Plug|a4c13859562db40c'
  [SALINATOR]='Outdoor Backyard Pool Salinator Plug|a4c138ca1c6b474b'
)

MARK=$(wc -l < "$LOG")
T0=$(date +%s)
echo "=== downlink probe v2 at $(date '+%F %T')  (mark $MARK, wait ${WAIT}s) ==="

for k in PUMP HEATER SALINATOR; do
  name="${DEV[$k]%%|*}"
  sudo podman exec mqtt5 mosquitto_pub -h localhost -u "$MU" -P "$MW" \
    -t "zigbee2mqtt/${name}/get" -m '{"state":""}' 2>/dev/null \
    && echo "  probe sent -> $k" || echo "  PUBLISH FAILED -> $k"
done

sleep "$WAIT"

# rotation guard: if the file shrank or was replaced, the tail offset is invalid
NOW=$(wc -l < "$LOG")
LOGDIR2=$(ls -1dt /mnt/data/docker_persistent/zigbee2mqtt/data/log/*/ | head -1)
if [ "$NOW" -lt "$MARK" ] || [ "$LOGDIR2" != "$LOGDIR" ]; then
  echo "ROTATION DETECTED (mark $MARK -> $NOW, dir changed: $([ "$LOGDIR2" != "$LOGDIR" ] && echo yes || echo no))"
  echo "VERDICT UNRELIABLE - rerun"
  exit 3
fi

echo
printf '%-11s %-9s %s\n' DEVICE VERDICT DETAIL
for k in PUMP HEATER SALINATOR; do
  ie="${DEV[$k]##*|}"
  hit=$(tail -n +$((MARK + 1)) "$LOG" | grep -E "$ie" | grep -E 'genOnOff\.read' | grep -m1 'NWK_NO_ROUTE')
  if [ -n "$hit" ]; then
    ts=$(echo "$hit" | cut -c2-20)
    lat=$(( $(date -d "$ts" +%s) - T0 ))
    printf '%-11s %-9s %s\n' "$k" "FAIL" "NWK_NO_ROUTE at $ts (+${lat}s after probe)"
  else
    printf '%-11s %-9s %s\n' "$k" "OK" "no genOnOff.read failure in ${WAIT}s window"
  fi
done

echo
echo "--- join / announce / interview activity since mark ---"
tail -n +$((MARK + 1)) "$LOG" | grep -iE "announce|interview|successfully been paired|joined" | tail -6 || echo "  (none)"
