# Interactive 3D floorplan for Home Assistant

Goal: a clickable model of the house in HA — see which lights are on at a glance, tap a
lamp to toggle it. Two phases, sharing one underlying model:

* **Phase 1** — isometric render + core `picture-elements` card. No custom card, so
  nothing to break on an HA upgrade. Ships first.
* **Phase 2** — **Floor3D Pro Card**: real 3D geometry, orbit and zoom, click the actual
  lamp object, bulbs emit light into the scene, doors and blinds animate.

The expensive work (an accurate model of the house) is identical for both, which is why
Phase 1 is not throwaway.

## Card choice — checked, not assumed

| Option | Verdict |
|---|---|
| **Floor3D Pro Card** | ✅ **Use this.** Actively maintained (July 2026), in the HACS default repo, drop-in compatible with the original's YAML and GLB models. Deterministic render scheduler + per-instance asset cloning, which is what fixes the old card's mobile behaviour. |
| `adizanni/floor3d-card` | ❌ Do not use. Last release **v1.5.3, April 2024**. Pro is its maintained successor. |
| `picture-elements` | ✅ Core HA. Phase 1. |
| `ha-floorplan` | Viable 2D SVG alternative; not needed given the above. |
| Native HA floorplan | ✗ **Does not exist.** 2026.3's areas feature is *vacuum room mapping* ("clean the kitchen"), unrelated to floorplan cards. |

HA in use: **2026.8.1**.

## Where the geometry comes from

See `scripts/floorplan/README.md` for the full extraction detail. The short version:

The house plans are **true vector CAD** (0 embedded rasters) — both an ARCHICAD
architectural set and a BricsCAD electrical set. **The electrical set is the geometry
source**, because it is colour-separated by circuit *and* carries the walls together
with the surveyed luminaire positions **in one coordinate frame**. Using the
architectural plan for walls and the electrical plan for lights would have required an
affine registration between two differently-sized sheets — the single most likely way
to put every light one room off.

Confirmed facts:

| | |
|---|---|
| Scale | **1:50**, stated on the arch sheets and confirmed against a 19.40 m run |
| Points per metre | **56.6929** |
| Ground floor extent | 15.70 × 11.19 m (arch plan states 15.90 m overall — centre-line vs outer face) |
| Wall thicknesses present | 13, 15.5, 20, 28 cm |

### Storey heights

From `1_Pläne BUVAG/20 schnitt  a - a.pdf`, relative to ground-floor finished level:

| Level | Floor at | Ceiling at | Clear height |
|---|---|---|---|
| Basement (`untergeschoss`) | −2.80 | −0.30 | 2.50 m |
| Ground (`erdgeschoss`) | ±0.00 | +2.50 | 2.50 m |
| First (`obergeschoss`) | +2.85 | +5.30 | 2.45 m |

Ridge at +7.76. The 35 cm between +2.50 and +2.85 is the intermediate slab build-up.

### Extraction results

```
floor      walls   total length   light outlets
ground        69        114.0 m      45  (26 recessed / 19 surface)
first         35        116.1 m      22  (11 / 11)
basement      11         54.6 m       5  (0 / 5)
```

Total wall length is the sanity metric: a house with a ~54 m perimeter plus interior
partitions should land near 110–130 m per occupied floor. An earlier iteration reported
283 walls / 324.9 m — visually indistinguishable in a render, but it would have extruded
~2.5× the needed geometry into the GLB, and heavy models are Floor3D Pro's known
weakness on mobile. Two evidence-based filters fixed it (hatch density and composite-wall
containment) rather than another tolerance tweak.

## Prerequisite: the entity map

Everything above produces *positions*. Turning a position into a control needs an
`entity_id`, and two gaps must close first.

### 1. Unassigned areas

26 of 47 `light.*` entities had `area: null`, including nearly everything
floorplan-relevant. A reviewed mapping is required before placing icons — doing it
afterwards means redoing the placement.

Five entities have **no matching area in the registry at all**:

* `light.main_bathroom_1_light_sink`, `light.main_bathroom_2_light_bathtub`,
  `light.main_bathroom_2_light_l2` — there is **no bathroom area anywhere**. The only wet
  room in the registry is `toilet` on the Ground Floor.
* `light.reduit`, `light.reduit_upstairs` — no `Reduit` area exists.

Excluded from the floorplan entirely: `light.ap_first_floor_nano_hd_led` and
`light.ap_ground_floor_u6_lr_led` (UniFi AP status LEDs, `platform: unifi`, both
mis-assigned to Living Room), plus `light.test_lights` and
`light.matteo_office_test_lamp`.

See also `docs/discussion-topics.md` for six related area-registry oddities that were
deliberately *not* touched.

### 2. Outlet → entity binding

This is the long-lead item and the plans cannot answer it. The ground floor has **45
outlets against roughly 20 relevant entities**, because outlets are ganged:

* the 6-lamp kitchen grid is `light.kitchen_spots_l1` / `l2`
* the evenly-spaced garage row is one switch
* some outlets have no HA entity at all

`scripts/floorplan/lamp_overlay.py` renders every outlet with an index over the real
plan; the mapping is then just a list of index → entity_id.

Useful shortcut when binding: an entity's `unique_id` says what it is. A small **integer**
(`7_light_zigbee2mqtt`) is a Zigbee2MQTT **group** — the right target for a whole-room
click. A `0x…` IEEE address is **one physical bulb** — the right target for an individual
lamp object in the 3D model. So `light.aria_room` and `light.aria_room_light` are not
duplicates; they are group and bulb.

## Build order

1. ~~Extract walls + luminaire positions from the CAD plans~~ ✅
2. Close the entity map (areas, then outlet → entity binding) ← **blocking**
3. Blender: extrude walls to the heights above, stack three storeys, place lamp objects
4. Phase 1: isometric renders + per-light overlay PNGs + `picture-elements` dashboard
   on a **new** dashboard (do not overwrite the existing `ground-floor` / `first-floor` /
   `under-ground-floor` dashboards)
5. Phase 2: GLB export, Floor3D Pro via HACS, entity bindings, mobile performance check

## Files

```
scripts/floorplan/extract_plan.py    walls + luminaires -> JSON in metres
scripts/floorplan/lamp_overlay.py    numbered outlet reference image
scripts/floorplan/README.md          extraction detail + gotchas
```

Renders, `.blend` files and GLB exports are build artifacts and are **not** committed.
