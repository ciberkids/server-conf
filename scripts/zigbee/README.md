# Zigbee downlink diagnostics

Tooling built 2026-07-31 while diagnosing why three pool plugs reported telemetry
perfectly but rejected every command (`NWK_NO_ROUTE 0xcd`). Full write-up:
[`docs/zigbee-pool-plug-downlink-diagnosis.md`](../../docs/zigbee-pool-plug-downlink-diagnosis.md).

All of these are **read-only**: ZDO queries and ZCL *reads* only. None changes a
relay state, restarts a service, or power-cycles anything.

## ⚠️ The trap these scripts exist to avoid

**Zigbee uplink and downlink are separate problems with separate machinery.** A
coordinator in many-to-one concentrator mode installs a route *toward* itself in
every router, so telemetry needs no per-device route and flows even when control
is completely dead. A device happily reporting 492 W tells you **nothing** about
whether it can be commanded.

**And an error log cannot prove success.** Successes are never logged, so "zero
errors" and "never exercised" are the same observation. This produced three wrong
conclusions here, including a non-fix recorded as CONFIRMED WORKING. Critically,
**failure latency tails out to at least 40 s** (herdsman runs up to 5 data
requests plus a `ZDO_EXT_ROUTE_DISC` before surfacing one line), so a short wait
reads "not yet failed" as "worked".

**Use a positive detector.** `parse_map.py` is the only one available: a device
that *answers* `Mgmt_Lqi_req` demonstrably received a downlink unicast. Its
*failure* proves nothing — that ZDO command is optional and many Tuya devices
never implement it.

## Scripts

| Script | Purpose |
|---|---|
| `parse_map.py` | **The positive detector.** Parses a raw network map: per-device `failed[]` (did it answer?) plus the coordinator's deduped routing table. Start here. |
| `get_networkmap.sh` | Requests a raw map with routes. Runs `mosquitto_pub/sub` **inside the `mqtt5` container** — the host has no mosquitto clients and no PyYAML. Takes ~10-12 min for 60 devices. |
| `probe_downlink.sh` | Fast single downlink attempt per plug via `<device>/get` (a ZCL read). **Pass a window ≥90 s.** Matches `genOnOff.read` so its verdict can't be polluted by the device's own hourly `genTime` traffic. Absence-based — corroborate with `parse_map.py`. |
| `noroute_census.py` | Network-wide `NWK_NO_ROUTE` census with first/last seen. Establishes whether a fault is device-specific or global. |
| `watch_plugs.sh` | Detached tail capturing all lines for the three plugs plus join/announce/interview events. |
| `heater_autotest.sh` | Fully automatic power-cycle test. Triggers on a `device_announce` — a **positive** signal the device actually rejoined — then runs three maps at +0/+20/+40 min to measure decay. |
| `await_heater.sh` | Earlier polling variant. **Superseded** — kept only because its 15 s window is the documented cause of a false positive. |

## Gotchas that cost real time

- **Map JSON is nested** `data.value.{nodes,links}` — not `data.{nodes,links}`.
- **Dedupe routing tables.** z2m repeats the target's full table on every link, so
  a naive count reported 739 entries where there were 21.
- **"No route entry" only means something for a non-neighbour.** The Hue Mosquito
  plug has no coordinator route yet downlink works fine — it's a *direct*
  neighbour, so it needs none.
- **The coordinator's 43-entry association table is not a neighbour table.** Every
  entry carries filler (`relationship=2, depth=255, rxOnWhenIdle=2`) and `lqi=0`
  appears on healthy devices. No RF information whatsoever.
- **Routing tables are volatile caches** — observed 28 → 15 → 29 → 26 destinations
  over three days, with next hops changing for the same destination. Never treat
  "no entry for X" as a stable property.
- **Never `pkill -f <pattern>`** over ssh when the pattern appears in your own
  command line — it kills the ssh session (exit 255). Bit me twice, including
  `pgrep -f` falsely reporting a finished script as RUNNING.
- **A z2m restart or coordinator PoE cycle rebuilds routes** and will appear to
  fix this. Capture evidence first; log rotation is 10 MB and eats it fast.
