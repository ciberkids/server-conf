# Discussion Topics

**A queue, not an archive.** Somewhere to park a topic that comes up while we're working on
something else, so neither thread gets dropped. Once a topic has been discussed, it comes **out**
of this file — the findings go to memory or `docs/`, and the entry is deleted.

Empty means nothing is queued.

## How to add one

```markdown
## <short title>

**Added:** YYYY-MM-DD

What was actually asked, in the asker's own words where possible.

**What to look at when we pick this up:** the specific config, host, file or metric to go
check — this is what makes the entry actionable later instead of just a reminder.
```

Verify factual context before writing it down. Entries get read as established fact in later
sessions, so an unverified guess becomes a wrong premise.

---

## Heating's per-day colour bands are scaled for a metric 4x bigger than heating

**Added:** 2026-08-06

Came up while fixing the all-white graphs on the Averages view of Home Info. The per-day
`color_threshold` bands for heating are 5 / 10 / 20 / 30 / 40 kWh — inherited verbatim from the
Consumption Graphs view, which copied them from the *grid import* card. But heating never exceeds
~10 kWh/day (Jun–Aug 2026 range: 0.6–9.9), so only the bottom two of five bands are ever used and
the chart reads as a single flat teal. Grid import genuinely spans 27–43 kWh/day, so the bands are
correct *there*.

**What to look at when we pick this up:** `dashboard-solar` view index 8 (`averages`) and view
index 5 (`consumption-graphs`), the `color_threshold` arrays on the two
`sensor.heating_energy_meter_total_import_power_daily` series. Something like 1 / 2 / 4 / 7 / 10
would actually use the full palette. Same question applies to the heating card on Consumption
Graphs, which has the same flat-teal look for the same reason.

## sensor.house_total_consumption_daily "Avg / month" renders N/A

**Added:** 2026-08-06

Noticed while fixing the Averages view graphs, not caused by that change. On the "House total
consumption - 3-month averages" card the *Avg / month* header state shows `N/A`, while the *Avg /
day* on the same card (41.1 kWh) and the monthly-trend card next to it (82 kWh) both resolve fine.

Best guess is that `group_by: {func: avg, duration: 90d}` wrapped around a
`statistics: {type: change, period: month}` series returns nothing when only one *partial* month
exists — the sensor was created 2026-08-05, so August is all there is. If that's right it
self-resolves once a full month closes (Sept 1), and the honest fix until then is to hide the state
rather than show N/A. The car-charging card computes the same statistic fine and it has three
months of data, which is consistent with that theory but doesn't prove it.

**What to look at when we pick this up:** `dashboard-solar` view index 8, section 2, first
apexcharts card, `series[1]`. Cheapest test is whether it starts resolving on its own after
1 Sept 2026 — if it does, nothing to fix.

## Area/floor registry oddities found while scoping the 3D floorplan

**Added:** 2026-08-10

Surfaced while inventorying entities for the interactive floorplan project. None of these are
broken today — they're cosmetic or latent — and renames break consumers (dashboards, automations,
voice aliases), so nothing was touched. Flagging for a decision:

1. **`area_id: mia_s_room` is named "Aria's Room".** The slug is stale from a previous name. Renaming
   the *area* is safe-ish, but the `area_id` itself is what automations and templates reference —
   worth grepping before changing.
2. **Floor `"Ground  Floor"` has a double space** in its display name (`ground_floor` id is fine).
   Purely cosmetic, one-field fix.
3. **A `no_floor` pseudo-floor holds 3 areas**: `Home`, `Stairs Down`, `Stairs up`. `Home` is
   probably deliberate (whole-house entities), but the two stairwells arguably belong to real
   floors — and the floorplan will want them somewhere concrete.
4. **`light.main_bedroom_night_light` is assigned to area "Corridor upstairs"**, not Main Bedroom.
   Could be genuinely mounted in the corridor — needs a physical check, not a config guess.
5. **Two UniFi AP status LEDs (`light.ap_first_floor_nano_hd_led`, `light.ap_ground_floor_u6_lr_led`)
   are assigned to "Living Room".** They're `platform: unifi`, not lamps. Harmless until something
   does "turn off all lights in the Living Room" — then the AP LED goes dark too.
6. ~~**26 of 47 lights have no area at all.**~~ ✅ **RESOLVED 2026-08-10** — all 31 assignments
   applied, plus three new areas created (`main_bathroom` → first_floor, `reduit` → ground_floor,
   `reduit_upstairs` → first_floor), with the floors confirmed from the CAD plans rather than
   guessed. Only the two test lights remain unassigned, deliberately.

Items 1–5 are still open. Item 5 (the AP LEDs) has gone from latent to **live**: six more real
lights were just assigned to `living_room`, and the floorplan being built is precisely the kind of
thing that generates area-scoped "turn off the Living Room" actions — which would also switch off
the access-point LEDs. Either move them out of `living_room` or exclude them by entity_id in the
dashboard config.

**What to look at when we pick this up:** `ha_list_floors_areas` output vs the physical house.
See `[[reference-ha-light-entity-map]]` and `docs/ha-3d-floorplan.md`.

## Bind the Living Room remote to a *scene* instead of toggling the group

**Added:** 2026-08-12

> "is it possible to bind a remote to a specific scene in a group? for instance the living room
> remote is binded to a group called living room but the group is composed by 4 lights and during
> the night one of these light could be used as night light, now since the remote is toggling the
> state of the group on and off, clearly if the device are out of sync you have the christmas light
> effect"

Proposed plan was: (1) bind the remote to an "all bright" scene, (2) have an automation watch for
the scene activation and, during night hours, **poll** until the lights go off manually, then bring
the night light back up.

**Why this is worth doing properly:** the remote is a **Ubisys C4** — one of the very few Zigbee
controllers where the ZCL command each input emits is fully user-authorable (manufacturer cluster
`0xFC00`, `InputActions`). So scene recall genuinely *is* reachable here, unlike on an IKEA/Tuya
remote where the firmware only ever emits On/Off/Level. Binding itself is **cluster**-granular, not
scene-granular — the scene ID travels in the `Scenes.RecallScene` *payload*, so what matters is
whether the device can be made to emit that command at all.

**Root cause of the Christmas-light effect:** the inputs currently send `Toggle` (`0x02`). Toggle is
evaluated per-bulb against each bulb's *own* state, so any pre-existing divergence is preserved and
flipped forever. Group commands are APS **multicast and unacknowledged**, so a bulb that simply
misses a frame falls behind permanently. `On`/`Off` and `RecallScene` are absolute — a missed frame
self-heals on the next press. That asymmetry is the whole problem.

### Live `input_actions` as of 2026-08-12 — THIS IS THE ROLLBACK

C4 fw `2.4.0`, dateCode `20240122-DE-FB1`, hw 3, IEEE `0x001fee0000008342`.
`input_configurations: [0, 0, 0, 0]`

Record layout (z2m presents each record as a flat array of bytes):

| byte(s) | meaning |
|---|---|
| 0 | InputAndOptions — which physical input, 0-based |
| 1 | Transition — internal state-machine edge (press / hold / release) |
| 2 | Source endpoint on the C4 |
| 3–4 | Cluster ID, uint16 **little-endian** |
| 5+ | ZCL command ID, then command payload |

| raw record | input | ep | cluster | command | payload | z2m action |
|---|---|---|---|---|---|---|
| `[0,7,1,6,0,2]` | 0 | 1 | `0x0006` genOnOff | `0x02` Toggle | — | `toggle_s1` |
| `[0,134,1,8,0,5,0,50]` | 0 | 1 | `0x0008` genLevelCtrl | `0x05` Move w/ OnOff | up, rate 50 | `brightness_move_up_s1` |
| `[0,198,1,8,0,1,1,50]` | 0 | 1 | `0x0008` | `0x01` Move | down, rate 50 | `brightness_move_down_s1` |
| `[0,11,1,8,0,3]` | 0 | 1 | `0x0008` | `0x03` Stop w/ OnOff | — | `brightness_stop_s1` |
| `[1,7,2,6,0,2]` | 1 | 2 | `0x0006` | `0x02` Toggle | — | `toggle_s2` |
| `[1,134,2,8,0,5,0,50]` | 1 | 2 | `0x0008` | `0x05` Move w/ OnOff | up, rate 50 | `brightness_move_up_s2` |
| `[1,198,2,8,0,1,1,50]` | 1 | 2 | `0x0008` | `0x01` Move | down, rate 50 | `brightness_move_down_s2` |
| `[1,11,2,8,0,3]` | 1 | 2 | `0x0008` | `0x03` Stop w/ OnOff | — | `brightness_stop_s2` |

**Only inputs 0 and 1 carry actions. Inputs 2 and 3 are empty** — unknown whether they are unwired,
wired-but-unconfigured, or factory default. The `Transition` byte encodings (`0x07`, `0x86`, `0x0C6`,
`0x0B`) were **not** verified against the Ubisys technical reference — do not write new records from
guessed transition values.

### The idea worth building: mutate what the scene *contains*, not which scene is recalled

Zigbee scene tables live **in the bulbs**, and their contents are rewritable at any time. So instead
of conditionally recalling a different scene at night, keep one "off" scene and have HA rewrite its
*contents* at sunset/sunrise (night = 3 bulbs off + night light at ~2% warm; day = all 4 off). At
press time it is pure Zigbee: instant, no HA involvement, no visible off-then-on flash, and it keeps
working if HA or z2m is down. **This removes the need for the polling loop entirely** — not because
MQTT pushes state, but because HA never needs to know the state at press time at all.

**What to look at when we pick this up:**

1. **How many physical inputs serve the living room, and which endpoint (s1 or s2)?** This gates
   everything. Two inputs → the cheapest fix is a one-byte change, Toggle `0x02` → `On` `0x01` on one
   and `Off` `0x00` on the other; scenes then become an optional upgrade. One input → both the Toggle
   fix *and* scene recall are unavailable (one button recalls exactly one scene) and it needs either a
   multi-press transition or HA-side logic. Reprogramming the wrong endpoint hits a different room.
2. **Which of the 4 couch lights is the night light**, and confirm the group's actual membership.
3. **Whether ep1/ep2 is bound to group 2 or to the 4 devices individually.** Bindings are *not* in
   `configuration.yaml` — that only holds groups. They live in the coordinator / `database.db`, and
   z2m surfaces them in the `zigbee2mqtt/bridge/devices` MQTT payload and the frontend's Bind tab.
   Three SSH attempts on 2026-08-12 went at the wrong artifact; don't repeat that.
4. **Whether z2m's `scene_add` can target an individual device while specifying the group_id the
   scene belongs to.** The trick needs *per-member* values under one shared `(group_id, scene_id)`; a
   group-level `scene_add` writes identical values to every member. If it can't, the fallback is
   `scene_store`, which snapshots each bulb's own live state (per-member values for free) but needs
   the room to briefly *be* in the night configuration to capture it — visible to anyone in the room.
5. **`Living Room Couch Rear Right Corner Light`** (Nue/3A `3A12S-15`, zclVersion 3, dateCode
   `20190604`) is the risk device — the other three are Philips Hue with solid Scenes support. Verify
   it honours Scenes cluster recall *including* the colour/level extension fields before relying on
   it. Its `power_on_behavior` is currently `on`, which is a separate landmine.
6. `recall_*_s1` appearing in the z2m action enum only proves z2m can **parse an incoming** scene
   recall from the C4 — it is *not* evidence the `configure_device_setup` **write** path handles scene
   records. Different code path, and the enum contains typos (`recal_*_s2`, `recal_*_s4`) suggesting
   that converter is lightly exercised. Treat as a caution signal.

Related: `[[reference-ha-light-entity-map]]` (group 2 = `light.living_room`).

---

*(previously cleared 2026-07-27, after Frigate, Immich, the pool pump and the coordinator
migration were all worked through)*
