# Floorplan extraction — house geometry from the CAD plans

Tooling for the interactive 3D floorplan dashboard in Home Assistant
(see `docs/ha-3d-floorplan.md`).

## Source plans

Not in this repo — they live in the Insync Google Drive mirror:

```
~/Insync/matteofavaro@gmail.com/Google Drive/Manu & I/Documents/Personal Documents/
  House/House Sirnach/Documentation house plans/
    1_Pläne BUVAG/        architectural, ARCHICAD, 840x450 mm sheets
    3_Elektropläne/       electrical,   BricsCAD,  A3 sheets   <-- geometry source
```

Both sets are **pure vector** (`pdfimages -list` returns 0 embedded rasters).

## Why the electrical plans are the source

The architectural sheets carry a `matrix(2.8336,…)` transform (= 72/25.4, so the local
unit is paper millimetres) and draw walls as hatched regions with the faces buried in
hundreds of hatch strokes.

The electrical sheets are better in three ways:

1. Only a Y-flip transform, so coordinates are already PostScript points.
2. **Colour-separated by circuit**: black = building fabric, blue = lighting,
   red = power, plus cyan/green/magenta for weak current and earthing.
3. They carry the walls **and** the surveyed luminaire positions in the *same*
   coordinate frame — so no cross-sheet affine registration is needed. That removes
   the largest error source (lights landing a room off).

## Key constants

| Fact | Value |
|---|---|
| Scale | **1:50** (stated on the arch sheets; confirmed — longest run = 19.40 m) |
| Points per metre | **56.6929** (`72/25.4 * 1000/50`) |
| Luminaire symbol ⊗ | 8.50 pt circle (5 path commands) + two 8.35×8.49 pt diagonals |
| Second fixture class | concentric 11.91 pt circle → recessed/dimmed |
| Real wall thicknesses | **13, 15.5, 20, 28 cm** (measured from the gap spectrum) |

## Usage

```bash
./extract_plan.py "<plan>.PDF" --floor ground \
    --out ground.json --verify ground.svg
```

`--verify` writes an SVG of *only what was extracted* — always render it and compare
against the real plan before trusting the output:

```bash
inkscape ground.svg -o ground.png -w 1700
```

`--join-gap-cm` (default 20) controls how far apart collinear wall-face pieces may be
and still be merged into one run. 20 cm is deliberate: the measured gap distribution
has a natural break there, so it repairs CAD fragmentation while leaving real door and
window openings as genuine holes.

## Room membership is NOT derivable — don't try again

Two automated attempts to work out which room each outlet is in both failed badly. Both
are recorded here so they aren't repeated:

1. **Nearest room label.** The plans carry only ~7 labels per floor and they sit wherever
   the draughtsman had space, not at room centroids. Result: **23 of 39** ground-floor
   outlets assigned to the `reduit` — a broom cupboard.
2. **Flood-filling the extracted walls** (`rooms.py`, since deleted), even re-extracted
   with `--join-gap-cm 150` to seal doorways. The wall set is *deliberately* incomplete —
   window openings run to 3 m, and some garage walls were never matched — so the exterior
   region floods straight into the interior. Result: **38 of 39** ground-floor outlets came
   back as "outside the walls".

The distinction that matters: outlet **positions** are surveyed data and exact; room
**membership** requires a complete, sealed wall set, which we do not have and do not need
for the model to look right.

So `make_binding_proposal.py` groups outlets by **proximity** instead. That needs no walls
and recovers the real electrical groupings anyway (ceiling grids, switch banks). Clusters
get letters that `lamp_overlay.py` draws on the plan, so the file and the image
cross-reference. Naming is left to a human who has stood in the rooms.

Clustering threshold: **0.95 m**, taken from the measured nearest-neighbour spectrum, not
guessed. Ground-floor neighbour distances are 0.15 m ×13, then 0.41–0.86, then 1.13–1.48,
then 2.14 and 6.21. There is **no clean gap above 1 m** — all pairwise distances form a
continuum — so anything much over 1 m chains the floor into one blob (1.6 m gave 36 of 39
outlets in a single cluster). 0.95 m sits in the 0.86→1.13 gap.

Also worth knowing: a run of lamp symbols exactly **15 cm** apart is too tight to be real
ceiling fixtures. It is draughting shorthand for "N lamps on this circuit", so those
clusters almost always take a single entity. `tight_note()` flags them.

## Gotchas learned the hard way

- **Do not filter to 2-point paths.** The ground-floor building outline is a single
  31-point polyline, and interior partitions are polylines too. Filtering to 2-point
  segments silently discards the best geometry in the file. Use `straight_segments()`,
  which walks M/L/Z runs and skips C (cubic) spans — curves are door swings and
  symbol rings, never walls.
- **Keep the thickness tolerance tight (±1 cm).** At ±2 cm the four thickness targets
  cover nearly the whole 10–29 cm range, so kitchen counters, terrace paving and
  furniture outlines all match. That yielded 1294 bogus walls on one floor.
- **Do not bucket by thickness when consolidating.** It splits a single wall across
  adjacent buckets, multiplying it instead of merging it. Group by axis + centre-line
  only, then take the median thickness.
- Merge collinear faces **before** pairing, not after — otherwise a wall split into
  five pieces yields five stubby fragments.
