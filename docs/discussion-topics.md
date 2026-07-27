# Discussion Topics

Running queue of things to work through together. Newest additions go at the bottom unless
they're urgent. Move items to `## Done` (with the date and outcome) rather than deleting them,
so the reasoning stays findable.

---

## 1. Frigate NVR — false positives + video retention

**Added:** 2026-07-27 · **False positives: FIXED same day. Retention: awaiting a decision.**

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

### Retention — still to decide

**The storage premise was mostly wrong, and worth saying plainly:** Frigate is using **2.6 G
total** (2.2 G recordings + 356 M clips) of an **11 T** mount with 3.9 T free, and retention is
*already* bounded by Frigate's defaults — 10 days for alerts, detections and snapshots, with
continuous recording **not** retained (`record.retain` unset). Nothing is running away.

So the real waste was proportional, not absolute: 83% of events were the coat, and each carried a
clip plus a snapshot. Masking it removes that at the source.

What remains is making retention **deliberate rather than inherited**. Nothing to reclaim — just
a decision to record explicitly so it survives a rebuild and reflects intent.

**The problem:** the AI object-recognition feature produces a lot of false positives. Two costs:
noise in the alerts, and wasted storage from recording events that aren't real. Separately, video
retention isn't configured, so footage accumulates without bound.

**Two goals, related but distinct:**

1. **Cut the false positives.** Improve detection accuracy so Frigate stops recording
   non-events.
2. **Set up retention.** Bound how long recordings and event clips are kept, so storage is
   predictable regardless of detection accuracy.

**Where to start when we pick this up:**
- Which cameras are worst, and what's being mis-detected as what (person vs. car vs. animal;
  shadows, headlights, rain, moving foliage, spiders on the lens at night are the usual
  suspects).
- Current `detect` / `objects` / `record` config per camera, and whether `zones` and
  `filters` (min/max `area`, `threshold`, `min_score`, `ratio`) are set at all — untuned
  defaults are the most common cause of exactly this.
- `snapshots`/`record` retain settings, plus whether `record.alerts` /
  `record.detections` retention differs from continuous recording.
- Actual disk consumption today and the growth rate, so retention can be chosen from real
  numbers rather than guessed.

**Context already known:** Frigate runs on bumblebee, GPU object detection via the
TensorRT build, reachable at `frigate.bumblebee.favarohome.com`. MQTT is enabled and it's
integrated into Home Assistant. Config is bind-mounted from
`/etc/containers/frigate/config`; recordings go to `/mnt/data/frigate` — verified, and
`/mnt/data` is the NFS mount from Optimus Prime (11 T, ~4.1 T free). So retention decisions
consume OP's array, not bumblebee's 70 G root — this is unrelated to the root-disk work done
2026-07-27.

---

## 2. Immich — why aren't all features enabled/available to every user?

**Added:** 2026-07-27

**The question:** not all Immich features appear to be enabled, or available to all users —
the example given is **folder creation**. Want to understand why, and enable what should be on.

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
