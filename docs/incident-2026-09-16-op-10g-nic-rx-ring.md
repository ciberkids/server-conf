# Incident 2026-09-16 — OP 10G NIC RX ring starvation broke half the homelab

**Status:** RESOLVED (Zigbee network restored 09:01, NIC fix persisted 09:06)
**Blast radius:** zigbee2mqtt (141 crash-restarts), all Zigbee entities in HA, node-red data,
and *false* "bumblebee service down" alerts.
**Duration:** 05:02 → 09:01 local (~4 h), intermittent.

## One-line cause

Optimus Prime's 10G NIC (`enp7s0`, Aquantia AQC100, `atlantic` driver) came up with the
**driver-default RX ring of 2048** instead of 8184. At 10G the kernel cannot drain a 2048-entry
ring fast enough, so the NIC silently dropped **20–43 % of received packets to every LAN host**.

## The detector that finds this in one command

```bash
ethtool -S enp7s0 | grep InErrors      # 327,629 across 8 queues
ip -s link show enp7s0                 # RX errors 0  <-- LIES
```

`ip -s link`, `ifconfig` and node-exporter's standard counters all reported **zero errors**.
The loss is only visible in the per-queue driver stats. This is why it hid for hours.

Second cheap discriminator — per-interface ping, which isolates it immediately:

```bash
ping -c 40 -i 0.2 -I 192.168.1.10 192.168.1.1   # via enp7s0 (10G): 20-43% loss
ping -c 40 -i 0.2 -I 192.168.1.13 192.168.1.1   # via enp6s0  (1G):  0% loss
```

## Why it looked like a Zigbee problem

z2m reaches the SLZB-06 coordinator over **TCP** (`192.168.1.69:6638`), so it rode the lossy NIC.
Symptoms were pure packet loss surfacing as application errors at random points:

| Error | Count |
|---|---|
| `TypeError: Cannot read properties of undefined (reading 'payload')` | 28 |
| `SRSP - SYS - ping / stackTune / getExtAddr / version after 6000ms` | several |
| `SRSP - APP_CNF - bdbSetChannel after 6000ms` | several |
| `SRSP - APP_CNF - bdbStartCommissioning after 40000ms` | 1 |
| `ECONNRESET` | 2 |
| `EHOSTUNREACH` (05:02, enp7s0 carrier still flapping) | 1 |

**A wedged radio fails the same way every time. This failed at random different ZNP commands** —
and succeeded outright at 06:05, 06:11 and 06:35 (64 devices joined, MQTT connected). That
scatter is the signature of an unreliable transport, not dead hardware. The `payload` TypeError
is the same fault surfacing as a crash: a ZNP response that never arrived → `undefined`.

## Hypotheses that were WRONG (and the evidence that killed them)

1. **Thermal wedge of the SLZB-06** (the documented recurring failure). Refuted: radio 83.4 °C /
   ESP32 85.0 °C — hot but *below* the 89 °C alarm and below the ~90 °C of real wedges. A PoE
   power-cycle at 08:41 did *not* fix it (it only changed the error signature).
2. **Coordinator firmware auto-OTA 20260310 → 20260311.** Refuted: `revision":20260310` appears
   **15 times unchanged since Sept 10**. The SLZB's `zb_version: 20260311` vs ZNP's `20260310` is
   a permanent difference between two reporting sources, not a change. `auto_zigbee: true` is a
   red herring here.
3. **ARP flux from two NICs on one /24.** Refuted: per-queue `InErrors` is a driver RX counter;
   ARP confusion does not produce it.

The owner's own hypothesis — *"something is going on with the ethernet"* — was correct from the start.

## Why the auto-recovery watchdog never fired

`zigbee-watchdog.timer` ran every 5 min for 3.5 h and fired **zero** recoveries. Every invocation:

```
[zigbee-watchdog] z2m active only 43.8s (< 15min) — insufficient history, skipping
[zigbee-watchdog] z2m not active — skipping (not a wedge; z2m is down/updating)
```

Its wedge test needs **z2m up >15 min with no device publishes**. A crash-looping z2m never
reaches 15 minutes, so the uptime gate — added deliberately to stop false-firing on normal
restarts — makes the watchdog **structurally blind to a crash loop**. It covers the *silent*
wedge and misses the *loud* one. Still open.

## Why "bumblebee services are down" was a false alarm

Bumblebee was healthy throughout: 21/21 containers up, **zero** failed units, uptime 4 days.
But Prometheus and blackbox-exporter run on **OP**, and probe bumblebee across the network —
the worst-hit path at 43 % loss. The alerts measured OP's broken NIC, not bumblebee.

## Why the fix had never persisted

Both udev rules are dead and always have been:

```
/etc/udev/rules.d/99-10g-nic.rules       ACTION=="add" KERNEL=="enp7s0"  ethtool -G rx 8184 tx 8184
/etc/udev/rules.d/99-atlantic-fix.rules  ACTION=="add" KERNEL=="enp7s0"  ethtool -G rx 512 tx 4096
```

At `ACTION=="add"` the interface is **still named `eth0`** — the kernel logs
`atlantic 0000:07:00.0 enp7s0: renamed from eth0` — so `KERNEL=="enp7s0"` never matches.
Proof the rules did not run this boot: `tso/gso/gro` are all **on** and `tx-usecs` is **510**,
though `99-atlantic-fix.rules` sets them off/50. The June 2026 ring fix only ever held because it
was applied by hand; every reboot since silently reverted to RX 2048.

Note the two rules also **contradict** each other (rx 8184 vs rx 512). `99-atlantic-fix.rules`
is stale (Apr 2026, for a TX retransmit storm later solved by BBR + ring sizing) and would
actively re-break RX if it ever did start firing. **Owner decision needed on deleting it.**

## Fix applied

`/etc/systemd/system/enp7s0-ring-buffers.service` (repo: `systemd/units/optimusprime/`):
oneshot, `After=`/`BindsTo=sys-subsystem-net-devices-enp7s0.device`, `WantedBy=multi-user.target`.
Chosen over a systemd `.link` file with `RxBufferSize=`, because a custom matching `.link`
**replaces** `99-default.link` and would drop `NamePolicy=`/`MACAddressPolicy=` — if the NIC then
failed to become `enp7s0`, `10-enp7s0.network` would not match and `.10` would be unconfigured on
a host only reachable over a WAN tunnel.

Verified behaviourally, not by exit code: ring forced back to 2048/4096, unit restarted,
read back **8184/8184**; enablement symlink confirmed in `multi-user.target.wants/`.

### Result

| Metric | Before | After |
|---|---|---|
| RX / TX ring | 2048 / 4096 | 8184 / 8184 |
| Loss OP→DM (.1) | 20 % | 0 % |
| Loss OP→bumblebee (.14) | 43 % | 0 % (300 pkts) |
| Loss OP→SLZB (.69) | 33 % | 0 % |
| `InErrors` | 327,629 | 1 (no drift) |
| zigbee2mqtt | 141 restarts | up, 64 devices, 104 publishing |

## Caveat, stated honestly

`ethtool -G` reallocates the RX datapath, so it is also a soft reset. The ring *size* is the
likely cause (it matches the June 2026 failure exactly) but the reset alone is not excluded by a
32-second test. **The durable check is OP's own Prometheus blackbox history over the next days** —
if loss returns with the ring still at 8184, the cause is physical (DAC/SFP) after all.

## Still open

1. Watchdog uptime-gate defect — crash loops are undetectable.
2. `notify-failure@zigbee2mqtt-mcp.service.service` failed; the alerting path that should have
   reported 141 restarts did not reach the owner.
3. `192.168.1.1 dev enp6s0 proto dhcp` host route is back despite `UseGateway=no`/`UseRoutes=no`
   being present and applied (systemd 261) — a second silently-regressed documented fix. Did not
   cause this incident.
4. `searxng.bumblebee.favarohome.com` → 404 (no Traefik router matched); container is up.
5. Owner decision: delete the conflicting `99-atlantic-fix.rules`?
