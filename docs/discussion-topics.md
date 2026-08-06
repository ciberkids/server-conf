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

---

*(previously cleared 2026-07-27, after Frigate, Immich, the pool pump and the coordinator
migration were all worked through)*
