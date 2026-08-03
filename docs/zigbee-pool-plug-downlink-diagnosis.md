Verified. The coordinator runs **many-to-one concentrator mode** — that closes the mechanism. Writing the deliverable.

# Why a plug can report perfectly and still refuse every command

## The short version

Zigbee is not symmetric. Sending and receiving use two completely different pieces of machinery, and only one of them is broken.

Your coordinator runs **many-to-one (MTO) concentrator mode**. I confirmed this in all three network maps: every `manyToOne: 1` route entry in the mesh — 30, 30 and 31 of them across the three snapshots — has exactly one destination, `Coordinator`. That means the coordinator periodically floods a single "everybody, here is the way back to me" broadcast, and all 30+ routers install one route entry pointing home.

- **Uplink is therefore nearly free.** When the pump wants to say "492 W", it hands the frame to whichever neighbour it can hear and rides that pre-installed MTO route home. It needs no per-destination route, no discovery, no bookkeeping. It works as long as the plug can talk to *one* neighbour.
- **Downlink is expensive.** To send `turn off` to the pump, the coordinator needs a route *to that specific short address*. It has three ways to get one: a direct radio link (it has none to the box), a routing-table entry, or a stored source route. It has none of the three, so it launches route discovery — and route discovery only succeeds **if the destination itself answers**.

That is the crux, and it is where this fault lives. In Zigbee, a Route Reply is generated **only by the destination device**, or by the *parent* of the destination if the destination is a sleeping end device. Intermediate routers never answer from cache. So the fact that 18 other routers currently hold ACTIVE routes to the pump is completely useless to the coordinator — none of them will ever reply on the pump's behalf.

The plugs talk fine. They just don't answer the question "how do I reach you?"

**The single most telling pair of measurements in the whole dataset — both new this session:**

| Device | What it is | Distance from house | Coordinator route, 2026-07-31 16:52 |
|---|---|---|---|
| `Pool sensor` nwk 38291 | **EndDevice**, sleepy (`rxOnWhenIdle=0`), floats **in the water** | farthest | `dest 38291 → nextHop 11552` **ACTIVE**, maintained |
| `Pool Pump/Heater/Salinator Plug` | **Routers**, in the equipment box | closer | **no entry, ever** |

The sensor in the water is reachable. The plugs 3 m closer are not. The difference is not distance and not radio: the sensor's parent is `Mosquito smart plug` (`rel=1`, lqi 118) and *Mosquito* answers route discovery on the sensor's behalf. The plugs have to answer for themselves, and they don't.

---

# 1. Root cause, ranked

**The evidence does not identify a single root cause, and I want to be plain about that.** It identifies the failing *step* with high confidence, and leaves three candidate reasons for that step failing which are observationally identical in the data available. Anyone who tells you it's "the plug hardware" or "the transmit power" is over-reading the evidence.

---

## H1 — The plugs do not participate in route establishment. **The failing step. Confidence: high.**

**Mechanism.** Coordinator wants to reach nwk 6400. No direct link, no routing entry, no source route → it issues `ZDO_EXT_ROUTE_DISC` (a real NWK Route Request broadcast). The RREQ propagates. The plug must receive it and unicast a Route Reply back. No RREP arrives, so no route is installed, so the data request terminates `NWK_NO_ROUTE (0xcd)`. Next hour, same thing. Forever.

**Evidence FOR:**
- **Route discovery is genuinely being launched, and the coordinator accepts it.** `zStackAdapter.js:462-465` fires `discoverRoute()` from the second failure of every logical attempt; `:243-248` issues `znp.request(ZDO,"extRouteDisc",…)`. Across ~160 logical attempts in 4 days, the SRSP failed exactly **once** (`NWK_TABLE_FULL`, below). So discovery is being requested successfully ~159/160 times and still produces no route.
- **The Pool-sensor contrast above.** The one device in the pool area whose RREQ is answered by a healthy proxy has a live route; the three that must answer for themselves do not.
- **The empirical rule holds in your own network.** Across the three maps, coordinator routing-table entries whose destination is a Router: **23/24, 13/13, 22/23** of those destinations also *answered* `Mgmt_Lqi_req` in the same scan. The two exceptions (`Matteo Office Remote`, `Devin Room Remote`) are battery remotes, almost certainly mis-typed as Routers in the DB. Conversely, of the 9 / 7 / 7 Routers that failed `Mgmt_Lqi_req`, only that one remote had a coordinator route. Route-presence and answers-downlink track each other at 58/60.
- **The routes-everywhere-but-here paradox dissolves.** 18 routers hold ACTIVE routes to the pump, 8 to the heater, 17 to the salinator, several with the plug as *direct* next hop — and it changes nothing, exactly as the spec predicts.

**Evidence AGAINST / hard limits:**
- I cannot read anything inside the plugs. All three fail `Mgmt_Lqi_req` **and** `Mgmt_Rtg_req`, so their neighbour and routing tables — precisely the thing that would settle this — are unreadable.
- "Receives the RREQ and won't answer" vs "never receives the RREQ" are **indistinguishable** in this dataset. That is the H1/H2 boundary.
- The one `NWK_TABLE_FULL` proves the coordinator can occasionally fail locally, so "the coordinator always launched a good RREQ" is a near-certainty, not a certainty.

**Sub-mechanisms (not separable with current data):**

- **H1a — the plug's route-discovery / routing table is exhausted.** To answer an RREQ a router must create a discovery-table entry and then a reverse route; if those tables are full the RREQ is dropped silently. Its own uplink keeps working because the MTO entry already exists and needs no new slot. This fits *every* observation including the temporal ones (see H3), and it explains why three co-located routers that each hear the other two plus 4-5 Hue routers are the ones affected, while an isolated identical plug in the office is fine. **Best-fitting sub-mechanism — but zero direct measurement. I am not promoting it to "the cause" on elegance.**
- **H1b — firmware/state wedge in the plug's NWK layer.** Same signature, no way to distinguish.
- **H1c — the plug does not receive the broadcast RREQ** (this is H2 in another costume).

---

## H2 — Marginal, degrading last-hop RF into the equipment box. **Confidence: medium; live contributor, not excluded.**

**Mechanism.** A broadcast RREQ gets no MAC acknowledgement and no MAC retries. A unicast data report does. So a link that is good enough for a 5-minute report with retries can be too poor for reliable broadcast reception — producing exactly this asymmetry without any plug defect.

**Evidence FOR:**
- **`Outdoor Backyard Table` (nwk 8211, Router, `failed=[]`) hears the coordinator directly at lqi 159 and 15 other devices at 69-240 — and cannot hear a single pool plug.** There is already a healthy outdoor router in the backyard that is stone deaf to the box.
- **The relays' LQI on the plugs has fallen sharply.** Best LQI any relay reports, per plug:

| | 2026-07-28 08:40 | 2026-07-28 20:26 | 2026-07-31 16:52 |
|---|---|---|---|
| Pump | 53 (Wardrobe only) | **160** (via Salinator), 76, 34 | 49, 38, 23 |
| Heater | 93, 41, 35, 26 | **197** (via Salinator), 62, 49 | 94, 73, 36, 32 |
| Salinator | 36 (+ one unreliable 252) | 60, 60, 60, 32 | 36, 29 |

- **`Mosquito smart plug`** — the Hue router next to the box, 28 healthy neighbours — hears the heater at 94, the pool sensor at 118 and the garden hose at 163 on Jul 31, but **no longer hears the pump or the salinator at all**.
- The salinator's remission (H3) coincided with the box being far better connected: three relays hearing it at 60, and the salinator itself acting as the in-box relay hearing the pump at 160 and the heater at 197.

**Evidence AGAINST:**
- **Uplink is essentially lossless.** ~4,500 reports, modal period 305/305/270 s, zero gaps ≥ 1.5× modal for pump and heater, exactly one for the salinator. That bounds plug→relay delivery *and* the plug's reception of MAC ACKs very tightly.
- Mosquito's transmitter demonstrably covers the pool area — it is the pool sensor's parent and downlink to that sensor works.
- ⚠️ The dossier's strongest-looking argument against H2 is **invalid** and must not be reused: "zero `MAC_NO_ACK` network-wide, therefore this is route resolution not delivery." `zStackAdapter.js` throws only the **last** of up to 5 attempts; per-attempt statuses go to `logger.debug`, and the logs contain info 76,272 / error 2,411 / **debug 0**. `MAC_NO_ACK` is in the same `recoverableErrors` list and takes the same `discoverRoute` path, so `MAC_NO_ACK → rediscovery fails → terminal NWK_NO_ROUTE` is an expected, invisible path. The absence of MAC errors is guaranteed by configuration, not measured.

---

## H3 — Whatever it is, it resets on a **plug** power-cycle and decays over hours-to-days. **Confidence: high for the pattern; the pattern is the actionable finding.**

This is H1a/H1b's temporal signature, and it is the strongest lever you have.

**Evidence FOR — two dated remissions, both following a plug-side physical event, never a coordinator-side one:**

1. **2026-07-23 09:30-09:37.** User: *"i trigger the permit join, i will go outside now and power civle the plugs (again)"* (09:27:56 CEST). Salinator re-interviewed at `[2026-07-23 09:37:50] … device has successfully been paired`. Result: **six consecutive scheduled commands landed sub-second** — off 07-23T19:00:00.18, on 07-24T08:00:00.44, off 07-24T19:00:00.20, on 07-25T08:00:00.28, off 07-25T19:00:00.40, on 07-26T08:00:00.46. Note this remission began **79-86 minutes before** `transmit_power: 13` took effect at 10:56:39.
2. **2026-07-28 18:54 → 2026-07-29 02:28 — the cleanest natural experiment in the dataset, and it is new.** The **salinator alone** recovered downlink for **7 h 34 min** while its two box-mates failed every single hour:
   - Salinator last failure `18:54:16`, next failure `02:28:30`. Full log coverage throughout, with an hourly probe.
   - Pump failed at 20:18:51, 21:20:53, 22:21:14, 23:22:26, 00:24:13, 01:26:08, 02:28:26. Heater likewise.
   - Inside that window, the **2026-07-28 20:26:57 network map** shows the coordinator holding `dest 47762 → nextHop 11552 (Kitchen Table top light) ACTIVE` — and the salinator `failed=['routingTable']` only, i.e. **its `Mgmt_Lqi_req` was delivered and answered.** A confirmed downlink success with a timestamp.
   - Boundary events: targeted `permit_join` at 19:09:58 (via `Outdoor Entry hedge lights`), **19:14:21 and 19:15:44 via `Mosquito smart plug`**, network-wide at 20:08:31; device `0x00158d008b80f308` joined 19:11:02; the pump physically switched off at 19:13:18 and HA logged a flap burst 19:16:10-19:16:25.

**This one window is decisive against every coordinator-global explanation.** Same coordinator, same second, same transmit power, same ~90 °C, same firmware: it routed to one plug in the box and not to the other two. And it is decisive against "the whole box is RF-shadowed", because the working plug was *in the box*.

**Evidence AGAINST / confound:** a plug power-cycle is not a clean intervention — it also forces a rejoin, refreshes address bookkeeping and rebuilds routes for that device. So "plug state was reset" and "route state was rebuilt" are not separated. No `Device announce` line for the salinator survives in the retained logs, so I cannot confirm it actually rejoined at 19:11-19:16 — that trigger is **inferred**, from the permit-join topics plus the pump switching off plus the flap burst, i.e. somebody was standing at the box.

---

## H4 — Coordinator-side resource / bookkeeping fault. **Confidence: low. Effectively excluded as the primary cause.**

**Evidence FOR (three genuinely new anomalies, all single-occurrence):**
- `[2026-07-29 03:37:35] … 'SREQ: ZDO - extRouteDisc - {"dstAddr":32008,…}' failed with status '(0xc7: NWK_TABLE_FULL)'` — the coordinator's own route/discovery table was full. **One occurrence in ~160 attempts.** (log dir `2026-07-29.03-17-05/log.log:632`)
- **5 ×** `'AF - dataRequest - {"dstaddr":6400,…"clusterid":10,…}' failed with status '(0x02: INVALID_PARAM)'` at `2026-07-28 16:57:39`, transid 22-26 — a *local* ZNP rejection, not an over-the-air result. (`2026-07-27.05-02-02/log.log:6277-6281`)
- **The heater changed its short address.** It is nwk **32008** in both Jul 28 maps (57488 absent) and nwk **57488** in the Jul 31 map (32008 absent). The `NWK_TABLE_FULL` above was for the *old* address.
- Coordinator thermals are worsening: `zb_temp` 91.92 → 92.90 → 94.04 → **97.20 °C**, `esp32_temp` → **98.33 °C**, measured over a few hours this session.

**Evidence AGAINST — decisive:** the H3 remission. Also, the heater got a *fresh* short address and still fails, which refutes any stale-address story for it; and the pump held nwk 6400 unchanged across all three maps and 4,372 observations, so stale addressing never applied to it. The coordinator's routing table also churns enormously on its own — **28 → 15 → 29 entries** in three days, with next hops changing for the same destinations — so it is a volatile cache, and "no entry for X" is not a stable property of anything.

Report the three anomalies upstream; do not build the diagnosis on them.

---

## H5 — `transmit_power: 20 → 13`. **Refuted as the cause. Confidence: high.**

- **Not necessary.** `transmit_power: 20` is present in `configuration_backup_v4.yaml` (2026-02-02) and `configuration.yaml.bak` (2026-04-15) — it ran 3+ months without this fault. And the fault is documented **at TX=20**: a contemporaneous capture timestamped 2026-07-23T06:51:14Z (08:51 CEST) contains `[2026-07-23 08:00:17] error: z2m: Publish 'set' 'state' to 'Outdoor Backyard Pool Pump Plug' failed: … genOnOff.on(…"direction":0…) failed (… 'NWK_NO_ROUTE' (0xcd))` — **2 h 56 min before** TX=13 took effect at 10:56:39. Corroborated independently by HA statistics: Jul 21 was a clean scheduled pair (08:00 = 492.88 W, 19:00 = 0.23 W); Jul 22 19:00 OFF failed (19:00 = 494.42 W, 20:00 = 34.56 W); Jul 23 08:00 ON failed (08:00 = 0.00 W).
- **Not sufficient.** Six scheduled commands landed sub-second at TX=13, and the salinator's 7.5 h remission happened at TX=13.
- **It was the attempted remedy**, applied ~3 h after the user reported the fault and ~80 min after the power-cycle that actually produced the remission. Correcting the brief: the change took effect at **10:56:39**, not 10:50 — the backup's `Birth/Change` is 10:56:16 (epoch 1784796976) and its 10:50:49 mtime is the pre-change file's own, preserved by `cp -a`.

**Residual unknown, stated honestly:** whether 7 dB less coordinator TX makes a marginal RREQ broadcast measurably worse is **untested**. It is excluded as the cause; it is *not* excluded as an aggravating margin factor. But reverting is not indicated (below).

---

## H6 — Plug model / silicon. **Refuted at the model level. Confidence: high.**

`Matteo Office 3D printer` `0xa4c13848a575f282`, nwk 32642, `manufacturerName: _TZ3000_ko6v90pg`, `modelID: TS011F`, `applicationVersion: 192` — **the same manufacturer, model and app version as the pump and heater** — is healthy: publishing at `2026-07-31 17:42:15`, `failed=['routingTable']` only (it **answered** `Mgmt_Lqi_req`), and the coordinator holds `dest 32642 → nextHop 11552` ACTIVE. Interestingly it was dead in both Jul 28 maps (`lastSeen` Feb 2026) and rejoined since — a fresh-from-power-up unit, consistent with H3.

Per-unit or per-location degradation of these three specific units is **not** excluded and is in fact the leading sub-mechanism. But "this model/radio module can't do downlink" is dead.

---

## H7 — Home Assistant / MQTT / automation path. **Excluded for every command that reached z2m. Confidence: high, with one caveat.**

Each of the 29 failed `set` attempts produces a `Publish 'set' 'state' to '<device>' failed` line, emitted only at `publish.js:280-281` inside `onMQTTMessage`. That line **is** the receipt: MQTT delivered, z2m resolved the entity, built the ZCL frame and handed it to the radio. **Caveat:** the 2026-07-28 19:00 scheduled `turn_off` has no z2m record of any kind inside continuously-covered logs while HA shows the automation ran. Whether it was dropped or delayed ~4 min into the 19:03:54 error is **unknown**. So "provably intact" overstates it; "intact for every command with a receipt" is correct.

## H8 — EMI from the 500 W pump motor. **Effectively dead. Confidence: medium-high.**

No dose-response, and the sign is wrong: the pump's own plug failed *more* with its motor idle than running (410 vs 351 line-events), aggregate 36.4/h with the motor on vs 40.7/h off. The heater reads 0 W in 2,879 of 2,880 samples and fails the most of the three. Relocating or shielding the box is not the answer.

---

# 2. The discriminating test

### The free one — and you have already run it three times without realising it was a test

**`bridge/request/networkmap` with routes, then read the `failed` array per node.** A device that answers `Mgmt_Lqi_req` had a **successful downlink unicast delivered at a known timestamp.** This is the only positive, success-detecting instrument in the entire investigation — everything else has been inference from an error log. It is read-only, touches no device state, and leaves a durable record in the log.

Run it hourly. Alert when (a) a plug's `failed` array shrinks, or (b) the coordinator's routing table gains 6400 / 57488 / 47762. Cost: ~10 min of ZDO scan per run, zero risk. It also gives you the coordinator's route table for free.

### The decisive one — power-cycle the HEATER only

`Outdoor Backyard Pool Heater Plug` reads `current: 0` and 0 W in 2,879/2,880 samples. Kill its power at the box for 30 s, restore it, then request a network map immediately and hourly after.

- **Heater downlink returns, pump and salinator stay dead** → H1a/H1b/H3 confirmed; plug-side state is the cause, and the time to relapse measures the decay constant (predicted: hours to days, from the 7.5 h and 3-day precedents).
- **Heater stays dead** → a plug-side reset is not sufficient; escalate to H2 (a router with line of sight to the box) and then to replacement.

Why this beats every alternative: **it does not restart z2m, does not touch the SLZB-06 or its PoE port, does not re-pair anything, and does not interrupt the pump** — which is still filtering at ~497 W. The coordinator-side evidence survives intact, and you get a per-device answer instead of a network-wide one.

### ⚠️ Before anyone restarts z2m, cycles the coordinator's PoE, or re-pairs a plug

**All three of those will rebuild routes and destroy the only reproducible instance of this fault.** Specifically: a z2m restart re-runs `zStackAdapter.start()` (and on the `restoreBackup` path issues a SOFT reset *after* `stackTune`, so the TX setting may silently revert); a coordinator reset drops the routing **and source-route** tables and forces the whole MTO concentrator flood to re-establish; a re-pair rebuilds the plug's parent and address state. Any of them converts "reproducible fault" into "seems fine for a while", which is exactly how the July 23 non-fix got recorded as confirmed.

Also note z2m log rotation is 10 MB and **has already eaten 2026-07-22 through 07-26**.

**Capture list — all of this, off the server, first:**

1. The **three embedded network maps** (already saved locally at `/tmp/claude-1000/-home-matteo-Claude-HomelabProject/b0b4494b-b230-4c86-ac37-5ac2336b58c3/scratchpad/maps/map_0728_0840.raw`, `map_0728_2026.raw`, `map_0731_1652.raw`). Sources on OP:
   - `/mnt/data/docker_persistent/zigbee2mqtt/data/log/2026-07-27.05-02-02/log1.log:8479` (2026-07-28 08:40:26)
   - `/mnt/data/docker_persistent/zigbee2mqtt/data/log/2026-07-28.17-00-56/log1.log:4987` (2026-07-28 20:26:57)
   - `/mnt/data/docker_persistent/zigbee2mqtt/data/log/2026-07-29.05-01-36/log.log:1249` (2026-07-31 16:52:37)
2. A **fresh map right now**, with routes.
3. The full failure-event extract: `/tmp/claude-1000/-home-matteo-Claude-HomelabProject/b0b4494b-b230-4c86-ac37-5ac2336b58c3/scratchpad/nnr.csv` — 2,292 rows of `timestamp|ieee|transactionSequenceNumber`.
4. **`tar` the entire `.../zigbee2mqtt/data/log/` directory off-box.** It is rotating under you.
5. The two one-off statuses verbatim: `NWK_TABLE_FULL` at `2026-07-29.03-17-05/log.log:632`; the five `INVALID_PARAM` at `2026-07-27.05-02-02/log.log:6277-6281`.
6. `configuration.yaml` plus all three backups (`configuration_backup_v4.yaml`, `configuration.yaml.bak`, `configuration.yaml.bak-txpower-1784796976`).
7. **HA recorder + long-term statistics** for the three switch entities and `sensor.outdoor_backyard_pool_pump_plug_power`. This is the *only* record covering the July 22-26 episode; z2m logs for it are gone.
8. Coordinator `http://192.168.1.69/ha_info` and `/ha_sensors`.
9. **Write down the retention floor** so nobody re-derives a false onset date: oldest surviving z2m log content is `2026-07-27 15:36:50`; the first `NWK_NO_ROUTE` is `2026-07-27 16:13:12`, **36 minutes later**. That date is a rotation artifact, not an onset.

---

# 3. Fix plan — cheapest and most reversible first

### F0. Hourly network-map probe with alerting — free, zero risk, do this first
- **Change:** cron/n8n job publishing to `zigbee2mqtt/bridge/request/networkmap` (`{"type":"raw","routes":true}`) hourly; parse the response; alert via `telegram-send` when a plug's `failed` array changes or a plug appears in the coordinator's routing table.
- **Effect:** you gain the only positive downlink probe you have, per device, with history. It is also the discriminating test in item 2.
- **Verify:** a map JSON lands each hour; deliberately confirm you see `failed: ['lqi','routingTable']` for all three plugs today.
- **Roll back:** delete the job.
- **Cost:** ~10 min of ZDO scan traffic per hour. Non-trivial mesh chatter — if that bothers you, run it every 3 h.

### F1. Fix the `availability:` block — cheap, but be clear it will NOT detect this fault
- **Change:** in `configuration.yaml`, delete the two invalid keys `availability.timeout: 72h` and `availability.remove_unavailable_devices` (neither exists in the z2m 2.12.1 schema — `properties.availability` accepts only `enabled`, `active`, `passive`, and `additionalProperties` is undefined so they were accepted with **no warning**). Set `availability.enabled: true`, `availability.active.timeout: 15` (minutes).
- **Honest expected effect: it would not have caught this outage and will not catch the next one.** `availability.js:99-102` makes `isAvailable()` pure uplink recency; `:265-272` re-arms the ping timer on **every received frame**; these are mains Routers so the timeout is `active.timeout`. Measured max uplink gaps are 307 / 320 / 327 s against a 600 s timeout — the ping never fires and the plugs read "online" forever. Detecting a downlink-only fault requires something that *exercises* the downlink, i.e. F0 or F4.
- **Verify:** `zigbee2mqtt/<device>/availability` retained topics start appearing for devices (today only six empty *group* topics exist).
- **Roll back:** restore the previous block. Requires a z2m restart — so **do not do this until after the capture list in item 2**.
- **Cost:** one z2m restart, which destroys the fault state.

### F2. "Route refresh" — be aware this is largely a no-op here
- **Reality:** there is no z2m or ZNP command that makes the coordinator install a route to a device that will not answer route discovery. `bridge/request/device/configure`, `.../interview`, a `set`, a `get` — all are downlinks and all fail the same way. The `discoverRoute` call already runs 5 times per logical attempt, ~160 times over 4 days.
- The only things that *do* refresh route state are (a) a plug power-cycle (F0's test / the real lever) and (b) a z2m or coordinator restart, which rebuilds MTO and both tables — and destroys the evidence.
- **Recommendation:** do not spend effort here. Skip to F3/F5.

### F3. Add a router with a healthy radio at the pool box — the best-value hardware fix
- **Change:** a mains-powered Zigbee router (Hue/IKEA/Sonoff — **not** another Tuya TS011F) in a weatherproof enclosure **physically at or on the equipment box**, with line of sight to the plugs.
- **Effect:** shortens the last hop so the RREQ arrives with margin and the RREP has a short path home. Addresses H2 and H1c. **Does nothing for H1a/H1b** — if the plug won't answer, a closer neighbour won't make it answer.
- **Placement warning from the data:** `Outdoor Backyard Table` (nwk 8211) already sits outdoors with lqi **159** direct to the coordinator and hears **no** pool plug. "Somewhere in the backyard" is demonstrably not close enough. Same wall or same pole as the box.
- **Verify:** in the next network map the new router's neighbour table lists all three plugs at LQI well above the current 23-94, and the coordinator begins holding routing-table entries for 6400/57488/47762.
- **Roll back:** unplug it and re-pair nothing (leaving a spare router in the mesh is harmless).
- **Cost:** ~CHF 15-30 plus an outdoor mains outlet near the box. Adds one more device to the mesh.

### F4. `transmit_power` back to 20 — **now recommended AGAINST**
- **Why not:** refuted as the cause (H5), and the thermal argument has got worse — the coordinator is at **97.20 °C** `zb_temp` / **98.33 °C** ESP32 *right now*, up ~5 °C over a few hours. Raising PA output adds dissipation to a part already running very hot, on a device with a documented history of thermal wedging (2× in 4 days per `project_z2m_radio_stuck_bootloader.md`).
- **If you try it anyway:** set it **explicitly to 20** — do **not** delete the key. With the key absent, `transmitPower` is `undefined`, the `!= null` guard at `zStackAdapter.js:142-143` is false, `SYS_STACK_TUNE` is **never sent**, and the radio sits at firmware default. That is a different and less informative experiment. Put `log_level: debug` (or `log_namespaced_levels: {zh:zstack:znp: debug}`) in the *same* edit — you only get one restart's worth of information, and the `stackTune` SRSP's value byte (the firmware's actual TX power) is currently discarded unlogged, which is why nobody can tell you what the radio is really running at.
- **Verify:** the debug log's `stackTune` SRSP value; then a scheduled command landing sub-second, and the plugs' `failed` arrays shrinking in the next map. **Do not** verify with "zero NWK_NO_ROUTE since restart" — see the flagged fallacy below.
- **Roll back:** one-line edit + restart.
- **Cost:** destroys the fault state. Do it last, or never.
- **Separately and independently: cool the coordinator.** 97 °C is a real reliability problem regardless of this fault. Try USB power instead of PoE (per your existing memory note), better airflow, or a heatsink. Expose `zb_temp` as an HA sensor — there is currently **no** temperature history anywhere, which is why the thermal question has been unanswerable all week.

### F5. Replace the plugs — honestly, the evidence has moved *toward* this, but for a different reason
- **The old argument is dead** — see §5. The `_TZ3210_` salinator fails downlink too (50/50 logical attempts in the retained window), and the byte-identical `_TZ3000_ko6v90pg / TS011F / app 192` 3D printer works fine. So "wrong radio module" is refuted.
- **What survives and is consistent with everything:** these three specific units, in this specific location, stop answering route discovery, and only a power-cycle restores it. That is a per-unit/per-location degradation, and replacement is a legitimate fix for it.
- **But test before you spend.** Run the F0 heater power-cycle test first. If the heater's downlink returns and then decays in hours, you know exactly what you are buying your way out of. If it *doesn't* return, replacement may not help either and F3 becomes the priority.
- **If you do replace:** use a different model, and consider **not** putting three mains routers in one small box — three co-located routers each hearing the other two plus 4-5 Hue routers is precisely the topology that stresses small routing tables.
- **Cost:** ~CHF 20-40 per plug, plus a trip to the box and re-pairing (which itself resets the fault, confounding your evaluation — take a map *before* removing anything).

### F6. Take the plugs out of the control path — the robust engineering answer
- **Change:** put a WiFi relay (Shelly) or a DIN contactor upstream of the pump, drive the schedule from that, and demote the Zigbee plug to metering only.
- **Effect:** the schedule stops depending on the plug being addressable at all. `power_outage_memory` is already `on`, so the plug returns to ON when powered — a deterministic upstream schedule works with the plug as a pass-through.
- **Verify:** two consecutive scheduled cycles land, confirmed from `sensor.outdoor_backyard_pool_pump_plug_power`.
- **Roll back:** re-point the automation at the Zigbee entity.
- **Cost:** ~CHF 25 plus wiring in a wet outdoor location — get it done properly.

---

# 4. Making the schedule reliable — and no, a retry does not help

**Retrying is worthless here, and the numbers are unambiguous.** Over 2026-07-27 16:13 → 07-31 17:15 there were **~53 logical downlink attempts to the pump, 57 to the heater, 50 to the salinator — a 100% failure rate**, and `zigbee-herdsman` *already* performs 5 AF data requests plus a genuine `ZDO_EXT_ROUTE_DISC` plus a network-address recheck inside every single one of those. An HA-level retry loop multiplies zero by N. When the coordinator has no route and cannot obtain one, the tenth attempt fails identically to the first.

What actually helps, in order of value:

1. **Verify-after-command, and alert on mismatch.** Today `automation.turn_on_off_pool_pump` fires blind: `conditions: []`, one `choose`, `mode: single`, no read-back. HA recorded the 2026-07-31 08:00 run as `script_execution: "finished"` with **no error key, in 2.6 ms**, while z2m failed 15 s later. Add: command → `wait_for_trigger` on the switch reaching the target state with a 60 s timeout → on timeout, `telegram-send` an alert. This does not fix anything, but it converts a silent 4-day pump outage into a notification. **This is the single highest-value change in this whole document**, because the fault's real cost was invisibility.
2. **Fix the phantom schedule.** `script.pool_pump_timed_start` calls `switch.turn_on` and then starts `timer.pool_pump_timer` **unconditionally**, and `automation.pool_pump_timer_finished_turn_off` turns off with `conditions: []`. Together they produce a UI that looks perfectly healthy while the pump does whatever it likes. Gate the `timer.start` on the switch actually having reached `on`.
3. **A control path that does not require the plug to be addressable** — F6. This is the only thing that makes the schedule reliable *regardless of root cause*, which is what you asked for.
4. **The hourly map probe (F0)** as the standing health check, since availability cannot do this job.
5. **Fix the actual fault** (F3/F5, guided by the heater test).

One thing that will *not* work, so don't reach for it: the TS011F's on-board `countdown` / local schedule. Setting it is itself a downlink.

---

# 5. Corrections to the record

### `memory/project_backyard_zigbee_marginal_link.md` — the root-cause claim is wrong

**Currently asserts:** *"⭐ROOT CAUSE = PLUG HARDWARE … three plugs share ONE box; the `_TZ3210_` salinator sees 4 routers, the two `_TZ3000_` TS011F (pump/heater) see 2 and fail. Same modelId TS011F hides different radio modules."*

**Contradicted, precisely:**

1. **The premise "the `_TZ3210_` salinator works" is factually false.** The salinator fails downlink on **50 of 50** logical attempts in the retained window, including continuously from 2026-07-30 19:13 through 2026-07-31 17:15. It also fails `Mgmt_Lqi_req` and `Mgmt_Rtg_req` in the Jul 31 map exactly like the other two.
2. **Where that premise came from — and this is the important part: nobody had ever sent a command to the salinator.** Across every retained log there are **0** `set` attempts to `0xa4c138ca1c6b474b` (the 29 failed sets break down as pump 22, heater 1, `Living Room Couch Rear Right Corner Light` 6, salinator 0). Its downlink was never tested; it was *assumed* working from an absence of errors. That is the error-log-as-successes fallacy, and it is the origin of the wrong root cause.
3. **The model-level claim is refuted by a live control.** `Matteo Office 3D printer` `0xa4c13848a575f282` is `_TZ3000_ko6v90pg` / `TS011F` / `applicationVersion 192` — identical device identity to the pump and heater — and it works: publishing at `2026-07-31 17:42:15`, answered `Mgmt_Lqi_req`, coordinator holds `dest 32642 → nextHop 11552` ACTIVE.
4. **The "sees 4 routers vs sees 2" asymmetry does not survive three snapshots.** Relays hearing each plug: Jul 28 08:40 — heater 4, salinator 2, pump 1. Jul 28 20:26 — salinator 4, heater 3, pump 3. Jul 31 16:52 — heater 4, pump 3, salinator 2. The ordering reverses between snapshots, and the plug with the *most* relays is not consistently the working one.

**Corrected statement to store:**
> Root cause NOT established. The failing step is identified: the coordinator cannot obtain a route to nwk 6400 / 57488 / 47762 because these three Router devices do not answer route discovery, and in Zigbee only the destination (or an EndDevice's parent) generates a Route Reply — so the 18/8/17 ACTIVE routes other mesh routers hold for them are irrelevant. Uplink is unaffected because the coordinator runs many-to-one concentrator mode (30-31 `manyToOne:1` routes to 0x0000 across the mesh), so reports ride a pre-installed route home and need no discovery. Why the plugs stopped answering is undetermined: route/discovery-table exhaustion in the plug, a firmware/state wedge, and marginal broadcast-RREQ reception are observationally identical here. The model/silicon theory is refuted (identical `_TZ3000_ko6v90pg / TS011F / app 192` unit works fine elsewhere); per-unit or per-location degradation of these three units is the leading sub-mechanism. Both documented remissions followed a **plug** power-cycle, never a coordinator action.

### Same file — the "FIXED / RESOLVED 2026-07-23" framing is wrong

- The July 23 remission began at the physical plug power-cycle + permit-join at **09:30-09:37**, which is **79-86 minutes BEFORE** `transmit_power: 13` took effect at **10:56:39**. The remission is attributable to the power-cycle; the TX change is not distinguishable from a coincidence, and reverting to 20 is not indicated.
- The fault relapsed. Episode 2 began no later than **2026-07-26**, and the currently-failing state has run continuously since at least **2026-07-27 16:13:12**. The file must record the relapse and drop RESOLVED.
- Also correct a date in the file's own record: the change was at **10:56:16 CEST** (backup `Birth/Change`, epoch 1784796976), not 10:50 — the 10:50:49 mtime is the *pre*-change file's, preserved by `cp -a`.

### Facts to ADD

- **The coordinator is a many-to-one concentrator.** This is the structural reason uplink is immune to route problems and downlink is not. It is the answer to "how can it report but not obey."
- **The `failed` array in a network map is a positive downlink probe.** A device that answers `Mgmt_Lqi_req` had a downlink unicast delivered at a known timestamp. This refines the existing note `Failed to execute LQI ≠ unreachable`: *failure* is weak evidence, but *success* is strong evidence, and it is the only success detector available.
- **Three network maps are embedded in the z2m logs** (2026-07-28 08:40:26, 2026-07-28 20:26:57, 2026-07-31 16:52:37) and are the only route history that exists. They are inside a 10 MB rotation window. Saved to scratchpad; copy somewhere permanent.
- **Coordinator routing tables are volatile caches** — 28 → 15 → 29 entries in 3 days with next hops changing for the same destinations. Never treat "no route entry for X" as a stable property; 20+ healthy devices have no entry at any given moment.
- **`coordLQI 0 ≠ broken` — keep, and strengthen.** All 43 entries in the coordinator's association table carry filler (`relationship=2, depth=255, rxOnWhenIdle=2, permitJoining=2`) and 6 read `lqi=0`, including healthy devices. It is not a neighbour table and carries no RF information.
- **z2m availability is OFF and, even configured correctly, cannot detect this class of fault.** Worth its own note so nobody "fixes" it and believes they are now covered.
- **Two upstream issues for `zigbee2mqtt` / `zigbee-herdsman`:** (a) the `SYS_STACK_TUNE` SRSP value byte — the firmware's actual TX power — is discarded and never logged, and its status gate is skipped because that SRSP carries no status field, so firmware clamping is completely invisible; (b) `stackTune` is issued around an un-awaited `adapterManager.start()`, so on the `restoreBackup` / `startCommissioning` paths a later reset silently wipes it with no re-apply and no warning.

---

# Measured vs inferred, and where the record read an error log as if it recorded successes

### The count correction — the most consequential number in this report

**2,292 `NWK_NO_ROUTE` log lines** (2026-07-27 16:13:12 → 07-31 17:15:29) collapse to **~160 logical downlink attempts: heater 57, pump 53, salinator 50.**

Method: group by (device, `transactionSequenceNumber`), treat lines >120 s apart as separate attempts. Sound because one exhausted herdsman chain contains ~7,000 ms of code-known waits and surfaces as a single `error:` line per completed `readResponse()`, the tsn is echoed from the inbound device frame, and the observed retry trains span ~3 minutes (e.g. heater tsn=80: 15 lines 16:07:04→16:10:37 carrying only three distinct `localTime` values, decoding to a ~3 s arrival window — the *plug* re-transmitting one frame, not herdsman looping). **Direction of error: this is a floor, not an inflation** — 120 s could only merge two genuinely distinct attempts if they shared a tsn within two minutes, which the ~1/hour probe cadence makes near-impossible.

Every count in the prior record is a **line** count: 306/312/284, 810/761/699, 2278, 2324, "~900 route discoveries issued." Inflated 15-40×. The real probe rate is roughly **one logical downlink attempt per plug per hour** (the plugs' `genTime` read). So "every attempt for 21 h failed" is ~21 attempts per plug — a much smaller sample than it sounded, though the four-day 160/160 record is still conclusive.

### Error-log-as-successes fallacies in the record — flagged explicitly

1. **The most damaging one.** The 2026-07-23 `FIX APPLIED + CONFIRMED WORKING` verification counted **zero `NWK_NO_ROUTE` in ~10 minutes** after a restart and concluded the plugs were responsive. Successes are never logged at `info` level, and the probe rate is ~1/hour/plug — so zero errors in 10 minutes is the *expected* observation even if downlink is completely dead. **This is why a non-fix was recorded as confirmed and the memory file was marked RESOLVED.**
2. *"Zero `NWK_NO_ROUTE` across all 59 devices since the restart → no collateral damage detected."* Same fallacy.
3. *"50 of 53 devices are completely clean"* and *"other lqi-0 devices, all with zero errors"* used as control groups. Cannot distinguish "downlink works" from "never commanded." `availability.enabled` is false, so nothing pings them; the only devices with an observable downlink-success signal are the five ubisys remotes polled every ~60 s, making that comparison "continuously-polled vs never-polled."
4. *"Exactly 3 devices have `NWK_NO_ROUTE`"* — window-bound. Two others appear across the full retention, and **neither is a usable control**: `Matteo Office Test Lamp` `0x00124b00234cc7d5` has `lastSeen 2025-02-03` (absent ~18 months; a route to an absent device legitimately cannot be found), and `Living Room Couch Rear Right Corner Light` produced 6 lines in one 2-minute slider drag on 2026-07-27 and self-healed by 05:53 the next morning, sitting at lqi 138 with an ACTIVE direct route.
5. *"Zero `MAC_NO_ACK` network-wide → the terminal failure is route resolution, not delivery."* An artifact of logging configuration, detailed under H2. Do not reuse it.
6. *"~900 route discoveries failed."* Only ~160 were issued, and the code never waits for an RREP — `discoverRoute` awaits the local SRSP then sleeps 3,000 ms. The correct claim is "~160 route discoveries were **requested**"; that they yielded no route is a separate fact, established from the map snapshots.

### Measured this session (read-only)

Everything cited above from: `stat`/`grep`/`sed` on the z2m log tree; the three embedded map JSON payloads parsed locally; `podman exec` reads inside `zigbee2mqtt` / `mqtt5`; `curl` to `http://192.168.1.69/ha_info` and `/ha_sensors`; HA recorder and long-term statistics reads.

### Inferred — flagged, not measured

- **"Only the destination (or an EndDevice's parent) generates a Route Reply."** Zigbee spec behaviour, not measured here. Empirically consistent in your network at 58/60 (route-present ⟺ answers `Mgmt_Lqi_req`, the 2 exceptions being battery remotes mis-typed as Routers).
- **"The plugs don't answer the RREQ" vs "they never receive it."** Not distinguishable with available instruments. This is the H1/H2 boundary and the reason I decline to name a single root cause.
- **The trigger for the salinator's 19:00 Jul 28 remission.** Inferred from the permit-join topics (19:09:58, 19:14:21, 19:15:44), the pump physically switching off at 19:13:18 and the 19:16:10-19:16:25 flap burst — i.e. somebody was at the box. **No `Device announce` line for the salinator survives**, so I cannot confirm it rejoined.
- **The coordinator's source-route table.** Not readable by any available means. Its emptiness for the plugs is inferred from the persistent `NWK_NO_ROUTE`, not observed.
- **That the radio is actually running at 13 dBm.** Inferred from config plus code path only. The `SYS_STACK_TUNE` SRSP value is discarded, nothing is logged at `info`, the SLZB-06 exposes no radio-power field, and the running process's startup strategy is unobserved (both file logs and `podman logs` truncate to 2026-07-29 20:17:08) — so a `restoreBackup` path that SOFT-resets after `stackTune` is not excluded. It may never have been in force.
- **`SALINATOR heard by Main Bedroom Night light lqi=252, rel=3, depth=1`** (Jul 28 08:40). Single anomalous entry; deliberately not load-bearing anywhere above.
- **Coordinator temperature as a factor.** Explicitly *not* claimed: the salinator remission occurred at comparable temperatures. 97.20 °C is a real reliability problem on its own merits, with no measured link to this fault — and no history exists to test one.

### Constraints honoured

No `set` or control command to any device. No z2m restart. No PoE or coordinator power-cycle. No re-pair, no forced leave. No edits to `configuration.yaml` or anything under `/mnt/data` or `/etc`. The pump was left running (~497 W, 2.15 A) throughout. All writes were to the session scratchpad: `maps/*.raw`, `maps/parse.py`, `maps/parse2.py`, `maps/out.txt`, `nnr.csv`, `hours.txt`.