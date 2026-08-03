#!/bin/bash
# Poll the downlink probe until the HEATER recovers, or until timeout.
# Exits 0 on recovery (with two confirmation probes), 2 on timeout.
# All probes are read-only ZCL reads; no relay state is changed.
#
# v2: uses a 40 s probe window. v1 used 15 s, which was SHORTER than the ~18 s
# failure latency and produced a false RECOVERED at 18:17 - the tell was that the
# pump, which nobody had touched, "recovered" at the same moment.
#
# Recovery is only declared when the HEATER is OK *and* at least one other plug
# still FAILs. A simultaneous all-three flip means an instrument or coordinator
# artifact, not a power-cycle effect, so it is reported rather than trusted.
OUT=/mnt/data/matteo/zigbee-forensics/2026-07-31/heater_test.log
MAX=30
GAP=75

echo "" >> "$OUT"
echo "=== v2 watch started $(date '+%F %T') (40s window; v1 result above was a FALSE POSITIVE) ===" >> "$OUT"
echo "validated baseline 18:21:17 = PUMP FAIL(+18s) / HEATER FAIL(+18s) / SALINATOR FAIL(+19s)" >> "$OUT"

for i in $(seq 1 $MAX); do
  RES=$(/tmp/probe_downlink.sh 40 2>&1)
  echo "--- attempt $i @ $(date '+%F %T') ---" >> "$OUT"
  echo "$RES" >> "$OUT"

  if echo "$RES" | grep -q 'VERDICT UNRELIABLE'; then
    echo "  (rotation - retrying)" >> "$OUT"
    sleep 10
    continue
  fi

  if echo "$RES" | grep -qE '^HEATER +OK'; then
    OTHERFAIL=$(echo "$RES" | grep -cE '^(PUMP|SALINATOR) +FAIL')
    echo ">>> HEATER OK at $(date '+%F %T') attempt $i; other plugs still failing: $OTHERFAIL/2" >> "$OUT"
    sleep 30
    echo "--- confirm 1 ---" >> "$OUT"; /tmp/probe_downlink.sh 40 >> "$OUT" 2>&1
    sleep 60
    echo "--- confirm 2 ---" >> "$OUT"; /tmp/probe_downlink.sh 40 >> "$OUT" 2>&1
    if [ "$OTHERFAIL" -ge 1 ]; then
      echo "RESULT=RECOVERED_ISOLATED" >> "$OUT"
    else
      echo "RESULT=ALL_THREE_FLIPPED_SUSPECT_ARTIFACT" >> "$OUT"
    fi
    exit 0
  fi
  sleep $GAP
done

echo "RESULT=TIMEOUT after $MAX attempts at $(date '+%F %T')" >> "$OUT"
exit 2
