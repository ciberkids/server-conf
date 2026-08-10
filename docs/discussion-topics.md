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

---

*(previously cleared 2026-07-27, after Frigate, Immich, the pool pump and the coordinator
migration were all worked through)*
