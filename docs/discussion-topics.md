# Discussion Topics

Running queue of things to work through together. Newest additions go at the bottom unless
they're urgent. Move items to `## Done` (with the date and outcome) rather than deleting them,
so the reasoning stays findable.

---

## 1. Frigate NVR — false positives + video retention

**Added:** 2026-07-27 · **RESOLVED same day — false positives fixed, retention set.**

### Outcome (2026-07-27)

**Root cause of the false positives: a hanging hooded jacket.** In the top-left of `jooan_fixed`,
a dark hooded garment hangs in front of a window; `yolov8n-320` reads its hood-and-shoulders
silhouette as a person at 0.70–0.87, and lighting swings through the adjacent window re-trigger
detection all day. Measured: **610 of 735 total events (83%) over 2026-07-21..27 were this one
coat**, each costing a clip *and* a snapshot.

Proven, not guessed — bottom-centre coordinates of all 617 out-of-zone person events clustered:

| bottom-centre | n | share |
|---|---|---|
| (0.10, 0.20) | 439 | 71.2% |
| (0.15, 0.20) | 156 | 25.3% |
| **coat corner total** | **610** | **98.9%** |

The remaining 7 sit at the frame bottom (y=1.0) scoring up to 0.94 — real people near the camera.

**Fix applied:** an `objects.mask` on `jooan_fixed` covering `0.01,0.15,0.20,0.15,0.20,0.35,0.01,0.35`.
Verified geometrically by rendering the polygon, a real detection box, and its bottom-centre over
a live frame: the point lands inside the mask, the mask never overlaps `garage_door_main`, and its
lower edge falls on the back-wall/floor junction so people on the floor are unaffected.

**`required_zones` was considered and rejected** — it would have suppressed those 7 genuine
detections of people standing in the garage away from the door. The data changed the plan.

**Residual risk to watch:** someone standing right at the back-left wall could have feet at
y≈0.34–0.36, marginally inside the mask. Narrow strip, and they should be picked up in adjacent
frames while moving — but if a real person is ever missed there, raise the mask's lower edge.

**Not the fix, but worth doing separately:** the GPU is at **2% with 4.31 ms inference** — huge
headroom — and `yolov8n-320` is the weakest available model. A larger model/input size would
improve accuracy generally. Deliberately *not* framed as the fix here: that jacket genuinely
reads as head-and-shoulders, so a bigger model may still call it a person. The mask is
deterministic; the model is probabilistic.

**Also noticed, not acted on:** `jooan_fixed` detects on the **2304x1296 main stream** (no
substream), so motion detection runs on a full-res frame that is then squeezed to 320×320 for the
model. `jooan_ptz` correctly uses a substream for detect. Worth giving `jooan_fixed` a detect
substream too. And `review.alerts.labels` includes `car`, which is not in `objects.track` — dead
config, harmless.

> ⚠️ **The Frigate config is not in git** (it holds plaintext MQTT and camera passwords, so only
> the quadlet is tracked). All of this tuning is therefore untracked and would be lost on a
> rebuild. Frigate supports `{FRIGATE_*}` env substitution, which would make the config
> committable with secrets pulled from an env file. Worth doing as its own task.
> Backup of the pre-change config: `config.yml.bak-objectmask-1785143182`.

### Retention — the storage premise was wrong

Worth saying plainly: Frigate was using **2.6 G total** (2.2 G recordings + 356 M clips) of an
**11 T** mount with 3.9 T free, and retention was *already* bounded by Frigate's defaults — 10
days for alerts, detections and snapshots, with no 24/7 footage kept
(`record.continuous.days: 0`). Nothing was running away.

So the real waste was proportional, not absolute: 83% of events were the coat, and each carried a
clip plus a snapshot. Masking it removes that at the source. What retention work remained was
making it **deliberate rather than inherited** — nothing to reclaim.

### Retention — DECIDED AND APPLIED 2026-07-27

Chosen: longer explicit event retention, no 24/7 recording.

| Setting | Was (inherited) | Now (explicit) |
|---|---|---|
| `record.continuous.days` | 0 | **0** — no 24/7 footage, as chosen |
| `record.motion.days` | 0 | **0** |
| `record.alerts.retain` | 10 d | **30 d** |
| `record.detections.retain` | 10 d | **14 d** |
| `snapshots.retain.default` | 10 d | **30 d** |

Every value only *increases* retention, so nothing was deleted. Verified in the effective config
on both cameras.

> ⚠️ **Frigate 0.17 has no `record.retain` key.** It was split into `record.continuous` and
> `record.motion`. Setting `record.retain` puts Frigate into **SAFE MODE** — cameras stop and the
> detector falls back to CPU. This happened during this change and was rolled back within ~90 s.
> The subtle part: reading the effective config, `record.get("retain")` returns `None` whether the
> key is *absent* or *null*, so it looked configurable when it no longer exists. **Check
> `/api/config/schema.json` and validate keys against it before editing this block** —
> `RecordConfig` allows only `enabled, sync_recordings, expire_interval, continuous, motion,
> detections, alerts, export, preview`. Backups: `config.yml.bak-retention-*`.

### Original ask (for the record)

> "a bunch of false positives on the ai recognition feature and I would like to fix them in order
> to limit the waste of storage, also I would like to set up the retention of the videos for the
> same reason"

Both parts are now done. The false-positive cause turned out to be a single physical object, and
the storage motivation turned out not to apply — see above.

### Environment

Frigate runs on bumblebee, GPU object detection via the
TensorRT build, reachable at `frigate.bumblebee.favarohome.com`. MQTT is enabled and it's
integrated into Home Assistant. Config is bind-mounted from
`/etc/containers/frigate/config`; recordings go to `/mnt/data/frigate` — verified, and
`/mnt/data` is the NFS mount from Optimus Prime (11 T, ~4.1 T free). So retention decisions
consume OP's array, not bumblebee's 70 G root — this is unrelated to the root-disk work done
2026-07-27.

---

## 2. Immich — why aren't all features enabled/available to every user?

**Added:** 2026-07-27 · **ANSWERED 2026-07-27 — nothing is broken. Action pending a decision.**

### Answer: they are per-user preferences that default to OFF

Immich **v3.0.3** on Optimus Prime (`immich-server`, `immich-database`, `immich-machine-learning`,
`immich-redis`, `immich-infra`).

Folders, Star rating, Tags and Google Cast are **not** server features that someone forgot to
switch on. They are **per-user preferences**, and Immich ships them **disabled by default**. The
"Features" panel on the admin user page is a **read-only status display** — it reports what each
user has, it is not a place to change anything.

Three independent pieces of evidence:

1. **Immich stores only *deviations* from defaults**, as sparse JSON in
   `user_metadata` (key = `preferences`). Actual rows:

   | User | `preferences` row |
   |---|---|
   | Antonella | `{"cast": {"gCastEnabled": true}}` |
   | Matteo (admin) | `{"cast": {"gCastEnabled": true}}` |
   | Stefania | `{"cast": {"gCastEnabled": true}}` |
   | **Vanni** | **no row at all** |
   | **Manuela** | **no row at all** |

2. **Vanni has no `user_metadata` rows whatsoever** — so the screenshotted Features panel *is*
   Immich's default set, read straight off a user with zero overrides:
   - default **ON**: Email notifications, Memories, People, Shared links, Supporter badge
   - default **OFF**: **Folders, Star rating, Tags, Google Cast**

3. The server code confirms it — `gCastEnabled: false` is the built-in default. And the
   server-level flags (`/api/server/features`) contain **no** entry for folders/ratings/tags/cast
   at all; that list is `smartSearch, facialRecognition, duplicateDetection, map,
   reverseGeocoding, importFaces, sidecar, search, trash, oauth, ocr, passwordLogin, email,
   realtimeTranscoding`. So there is no server-side gate on these four.

Proof they are user-toggleable: three users have exactly `{"cast":{"gCastEnabled":true}}` — they
turned Cast on themselves and only that one deviation got stored.

**So the current reality: nobody has Folders, Tags or Star rating on. Cast is on for 3 of 5.**

### Two ways to change it

- **Per user, in the UI:** each person signs in → **Account Settings → Features** → toggle.
- **Centrally, as admin:** `PUT /api/admin/users/{id}/preferences`. **Verified this route exists**
  on 3.0.3 by probing it — it returns **401** (auth required), not 404. Needs an admin API key.
  This can enable the features for everyone without asking each person to log in.

Prefer the API over writing `user_metadata` directly: a direct DB write bypasses app validation
and any cache invalidation.

### Side finding worth knowing: email notifications can't actually send

Every user shows **Email notifications ✓** — but that is the *user preference*. The **server** has
`email: false` in `/api/server/features`, i.e. no SMTP configured. So the preference is on and no
mail can leave. Either configure SMTP or treat that ✓ as cosmetic.

### Decision needed

Which of Folders / Tags / Star rating / Google Cast to enable, and for whom — just the admin
account, or all five users. Enabling features on other people's accounts is a change to their
accounts, so that is a call to make deliberately rather than by default.

### Original framing (superseded by the answer above)

**What to work out when we pick this up:**
- Which specific features are missing, and missing *for whom* — only for non-admin users, or
  for the admin account too? That distinction points at very different causes.
- Immich has per-user and server-wide controls that are easy to conflate:
  - **Admin → Settings → Features** (server-wide toggles: map, reverse geocoding, machine
    learning, smart search, facial recognition, trash, OAuth…)
  - **Admin → Users** per-account settings, including storage quota and whether the account
    has admin rights.
  - **Storage Template** — which governs how files are laid out on disk, and is the setting
    people usually mean by "folder creation". It's **off by default** and only an admin can
    enable it.
- Whether "folders" here means the **Folders view** (browsing the original directory
  structure, a comparatively recent feature that must be enabled and depends on how the
  library was imported) rather than the storage template. Worth pinning down which one is
  meant before changing anything.
- Version currently running vs. latest — some of these features simply don't exist in older
  releases, which would explain "not available" with no misconfiguration at all.

**Careful with:** enabling the Storage Template causes Immich to **move existing files** on
disk to match the new pattern. That's a bulk operation on the photo library, so it wants a
backup check and a deliberate decision, not a casual toggle.

---

## 3. z2m "lost connection" to the pool pump — when did it happen?

**Added:** 2026-07-27. **Investigated same day — answer below.**

### It never disconnected

The pump was publishing normally throughout, including seconds before this was investigated:
`state: ON`, 496 W, 2.18 A, 236 V, energy 524.93 kWh. All four pool devices were live. So there
is no disconnection event to date.

### What actually failed: three outbound *commands*, not the link

Every `set` failure for the pump across the whole log history — exactly three:

| When | Command | Error | Cause |
|---|---|---|---|
| 2026-07-26 19:00:06 | `genOnOff.off` | `SRSP - AF - dataRequest after 6000ms` | the **coordinator wedge** (network was dark 08:28→22:15 that day) |
| 2026-07-27 08:00:26 | `genOnOff.on` | `NWK_NO_ROUTE (0xcd)` | routing failure |
| 2026-07-27 11:05:21 | `genOnOff.on` | `NWK_NO_ROUTE (0xcd)` | routing failure |

19:00 and 08:00 look like a scheduled off/on automation, so **what was noticed was almost
certainly the pump not responding to its schedule** — the *command* was lost, not the device.
The first one has a completely different cause from the other two: see
[[project-z2m-radio-stuck-bootloader]].

### The real underlying problem: the backyard link is unstable again

Link quality over the last samples — note the **minimums**:

| Device | min | max | avg | last |
|---|---|---|---|---|
| Pool Pump Plug | **3** | 181 | 115 | 63 |
| Pool Heater Plug | **3** | 200 | 81 | 63 |
| Pool Salinator Plug | 53 | 186 | 150 | 63 |
| Pool sensor | 40 | 181 | 91 | 81 |

LQI 3 is effectively no link. The whole backyard cluster oscillates between excellent (180–200)
and dead. This is a **regression of [[project-backyard-zigbee-marginal-link]]**, which was fixed
2026-07-23 by lowering coordinator `transmit_power` 20→13 to force the plugs off the weak direct
path onto upstairs relays (LQI went 0→191 then). `transmit_power: 13` is **still set** — verified
— so the setting held but the routing did not. Plausible trigger: the coordinator PoE
power-cycle on 2026-07-26 ~22:15 rebuilt the mesh from scratch and the plugs re-homed onto the
weak direct link again.

### Also found: the HEATER is far worse than the pump

`NWK_NO_ROUTE` today, by device — and note the pump is a minor contributor:

| Device | count |
|---|---|
| **Pool Heater Plug** | **300** |
| Pool Pump Plug | 24 |
| Matteo Office Test Lamp | 1 |

161 of these are `genTime.readRsp` — the Tuya TS011F plugs poll the coordinator for time and the
response can't be routed back. This is **chronic and flat at ~15/hour every hour**, not an event.
(An early read of "16 yesterday vs 160 today" was wrong — that compared a partial rotated log
against a fuller one.)

### Not the cause — ruled out

- **The zigbee-watchdog did not fire.** No cooldown stamp exists and all ~90 runs since
  deployment report "healthy — traffic flowing". It is not false-firing.
- **The 05:02 z2m restart was podman auto-update**, not the watchdog. z2m failed to start twice
  (`Error while starting zigbee-herdsman`) before succeeding at 05:02:06 — the usual
  coordinator-still-busy race after a container restart. Worth considering a `RestartSec` delay
  so auto-update restarts don't crash-loop.

### To decide when we pick this up

1. Re-home the backyard cluster onto the upstairs relays again (the 2026-07-23 remedy) — and
   work out how to make it **survive a coordinator reboot**, since that appears to undo it.
2. Whether to attack the heater's 300/day `genTime` routing failures directly.
3. Whether HA should retry failed `set` commands, so a single lost packet doesn't silently
   skip a pump schedule. That is arguably the highest-value fix: it makes the schedule robust
   regardless of mesh health.

---

## 4. Does upgrading/changing the Zigbee coordinator force re-pairing every device?

**Added:** 2026-07-27. Prompted by two pending items: the SLZB-06 firmware update
(`20260310` → `20260425`) and the possibility of swapping the coordinator hardware to escape its
~90 °C thermal problem. The worry: devices installed **behind wall switches** can't easily be
factory-reset by hand.

### Short answer: in the two most likely cases, no re-pairing

A Zigbee device doesn't bond to a *coordinator*; it joins a *network*, identified by **PAN ID,
extended PAN ID, channel, and the network key**. Preserve those four and devices keep working —
they neither know nor care that the radio hardware changed.

| Scenario | Re-pair needed? | Why |
|---|---|---|
| **Firmware update, same SLZB-06** | **No** | A normal CC2652 firmware flash preserves NVRAM (network config + device table). This is the low-risk path and the one already queued. |
| **Replace with same chip family** (another CC2652 stick) | **No**, if the coordinator backup is restored | z2m keeps `coordinator_backup.json` and writes the saved PAN ID / keys onto the new adapter, so the network is recreated identically. |
| **Cross-family** (CC2652 → Silabs EFR32, e.g. SLZB-07) | **Maybe** | zigbee-herdsman can convert backups between stacks and z2m documents adapter migration, but this is the genuinely risky path and wants its own research before committing. |

**We already have the backup:** `/mnt/data/docker_persistent/zigbee2mqtt/data/coordinator_backup.json`
(15,846 bytes, last written 2026-07-25). z2m refreshes it on start/stop. **Confirm it is fresh
immediately before any swap** — a stale backup is the one thing that would turn a no-re-pair
migration into a re-pair-everything migration.

### If re-pairing ever *is* needed, physical access is not the only option

This is the part worth knowing given the in-wall switches (the Vesternet/Sunricher VES-ZB-SWI-005
units in Keller / Tech room / Stairs):

- **The breaker is the reset button.** Most in-wall Zigbee switches reset via a power-cycle
  *pattern* (a set number of off/on cycles). That's done at the fuse box — no need to open the
  wall plate or remove the switch.
- **Ask the device to leave and rejoin** from the coordinator side (ZDO leave with `rejoin=true`),
  no physical contact at all. Only works while the device is still reachable — so if a migration
  is planned, do this *before* tearing anything down, not after.
- **Touchlink reset** works for Zigbee Light Link devices without physical access, but needs the
  coordinator physically near the device — awkward for a PoE-mounted SLZB-06, easier with a
  spare USB stick.
- Check each model's datasheet for its specific reset sequence *before* starting, not midway.

### Candidate replacement: SLZB-MR2 (added 2026-07-27)

Being considered as the replacement. Vendor description: compact multi-radio adapter with
**CC2652P + EFR32MG21 + ESP32**, running Zigbee 3.0 and Matter-over-Thread simultaneously on
separate SoCs. Ethernet, Wi-Fi or USB, with PoE. SLZB-OS with OTA firmware updates, VPN, HA
integration, 20+ languages, IPv6, Ethernet-to-Wi-Fi bridge.

**The good news, and it's the decisive point: the MR2 carries a CC2652P — the same radio family
as the SLZB-06.** So this lands in the middle row of the table above: a same-chip-family swap,
where restoring `coordinator_backup.json` recreates the identical network (PAN ID, extended PAN
ID, channel, network key). **No re-pairing, and no touching the in-wall switches.** The
cross-family risk that would have made this painful does not apply.

**The caution, and it is a real one: this may not fix the thermal problem, which is the whole
reason for replacing the SLZB-06.** The current unit sits at ~90 °C radio / ~94 °C ESP, and the
ESP being *hotter than the radio* points at the onboard **PoE-to-5V converter** as the heat
source, not the radio. The MR2 packs **three** SoCs into a compact enclosure and still offers
PoE — so powered over PoE it could plausibly run as hot or hotter. Buying it and running it on
PoE risks reproducing the exact failure we are trying to escape.

Worth resolving before ordering:

- **Plan to power it over USB, not PoE**, if the goal is thermal. That alone removes ~20–30 °C on
  the current unit and would likely do the same here. If USB is the plan, the MR2's PoE support
  is a nice-to-have rather than the reason to buy it.
- **⚠️ USB power breaks the auto-recovery watchdog.** `zigbee-watchdog` recovers a wedged
  coordinator by **PoE-cycling switch `24:5a:4c:a0:df:56` port 2** via the UniFi API. On USB power
  there is no PoE port to cycle, so recovery would need a different lever — a smart plug on the
  USB supply is the obvious substitute, and the watchdog's `poe_cycle()` would need swapping for a
  plug toggle. Decide this *with* the power decision, not after.
- If it stays on PoE, check whether the switch port changes, and update `SW_MAC` / `SW_PORT` in
  `scripts/optimus-prime/zigbee-watchdog.py` accordingly.
- Look for real-world temperature reports for the MR2 specifically (three SoCs, compact case)
  before assuming it runs cooler than the 06.
- The EFR32MG21 gives a Thread/Matter radio we have no current use for — genuine future value,
  but it isn't a reason to migrate today, and it does add heat.

**Net:** the MR2 makes the *migration* easy (same radio family → backup restore → no re-pairing).
Whether it fixes the *problem* depends entirely on how it's powered. Sorting the power/cooling
question is the higher-value work; the hardware swap is the easy part.

### Ordering suggestion when we do this

1. Firmware update first — it addresses the pending `20260425` item at essentially no risk, and
   might even help the recurring wedge. Do it while nothing else is changing.
2. Only then consider hardware. The real driver for a swap is thermal (~90 °C radio / ~94 °C ESP,
   see [[project-z2m-radio-stuck-bootloader]]) — but note that simply **moving the SLZB-06 to USB
   power instead of PoE** removes ~20–30 °C without touching the network at all. Try that before
   any migration.
3. Verify `coordinator_backup.json` is current, and copy it somewhere off-box, before either step.

---
