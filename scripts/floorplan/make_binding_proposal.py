#!/usr/bin/env python3
"""Generate the editable outlet -> entity binding proposal.

Produces a YAML file covering all floors: one flow-style mapping per outlet on a single
line, grouped into lettered CLUSTERS, with candidate entities listed as comments.

Why clusters and not rooms
--------------------------
Two attempts at naming the room each outlet sits in both failed, and the reason is worth
recording:

 1. Nearest room label. The plans carry only ~7 labels per floor and they sit wherever the
    draughtsman had space, not at room centroids. This put 23 of 39 ground-floor outlets
    in the `reduit` broom cupboard.
 2. Flood-filling the extracted walls (even re-extracted with a 150 cm join to seal
    doorways). The wall set is deliberately incomplete — window openings run to 3 m and
    some garage walls were never matched — so the exterior region floods the interior.
    38 of 39 ground-floor outlets came back as "outside the walls".

Outlet *positions* are surveyed data and exact. Room *membership* needs a complete wall
set, which we don't have and don't need for the model to look right. So group by proximity
instead: it needs no walls and it recovers the real electrical groupings anyway — ceiling
grids, the garage row, switch banks. The same letters are drawn on the overlay PNG by
lamp_overlay.py, so a cluster can be found on the plan at a glance.

Usage:
    ./make_binding_proposal.py --out ../../docs/floorplan-light-bindings.yaml
"""

import argparse
import json
import string
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent

# Single-linkage distance, chosen from the measured nearest-neighbour spectrum rather
# than guessed. On the ground floor those distances are:
#   0.15 m x13  (multi-gang bank positions - a very sharp break here)
#   0.41 - 0.86 m  (fixtures within one ceiling grid)
#   1.13 - 1.48 m, then 2.14, 6.21
# There is NO clean gap above 1 m - all pairwise distances form a continuum - so any
# threshold much over 1 m chains the whole floor into one cluster (1.6 m gave 36 of 39
# outlets in a single group). 0.95 m sits in the gap between the 0.86 and 1.13 clusters
# and yields sizes [8, 6, 6, 4, 4, 3, ...] with no group over ~21% of a floor.
CLUSTER_LINK_M = 0.95


def cluster(points, link=CLUSTER_LINK_M):
    """Single-linkage clustering. points = [(idx, x, y)] -> [[idx,...], ...]."""
    parent = {i: i for i, _, _ in points}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for n, (i, xi, yi) in enumerate(points):
        for j, xj, yj in points[n + 1:]:
            if abs(xi - xj) <= link and abs(yi - yj) <= link and \
                    ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5 <= link:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb

    out = defaultdict(list)
    for i, _, _ in points:
        out[find(i)].append(i)
    return list(out.values())


def describe(pts):
    """Short human hint about a cluster's shape, e.g. '2x3 grid' or 'row of 4'."""
    n = len(pts)
    if n == 1:
        return "single fixture"
    xs = sorted({round(x, 1) for _, x, _ in pts})
    ys = sorted({round(y, 1) for _, _, y in pts})
    span_x = max(x for _, x, _ in pts) - min(x for _, x, _ in pts)
    span_y = max(y for _, _, y in pts) - min(y for _, _, y in pts)
    # Only call it a grid if the distinct x and y counts actually multiply out to n —
    # otherwise "4x4 grid" gets printed for a 6-outlet blob, which is confidently wrong.
    if len(xs) > 1 and len(ys) > 1 and len(xs) * len(ys) == n:
        return f"{len(xs)}x{len(ys)} grid ({span_x:.1f} x {span_y:.1f} m)"
    # Pick the DOMINANT axis. Testing span_y first and then printing span_x named the
    # wrong direction for north-south runs.
    if span_x >= span_y and span_y < 0.4:
        return f"row of {n}, east-west ({span_x:.2f} m)"
    if span_y > span_x and span_x < 0.4:
        return f"row of {n}, north-south ({span_y:.2f} m)"
    return f"{n} outlets over {span_x:.1f} x {span_y:.1f} m"


def tight_note(pts):
    """Flag symbol groups spaced ~15 cm — draughting shorthand, not real positions.

    15 cm is far too tight for separate ceiling fixtures. On these plans a run of lamp
    symbols at that pitch means "N lamps on this circuit", drawn as a group rather than
    at surveyed positions. Those clusters almost always take ONE entity.
    """
    if len(pts) < 2:
        return None
    import math
    gaps = sorted(
        math.dist((a[1], a[2]), (b[1], b[2]))
        for n, a in enumerate(pts) for b in pts[n + 1:]
    )
    if gaps and gaps[0] < 0.20:
        return ("symbols ~15 cm apart = draughting shorthand for several lamps on ONE "
                "circuit, not separate ceiling points. Expect a single entity here.")
    return None


def compass(x, y, ext):
    """Rough position within the floor, so a cluster can be found by eye."""
    w = ext["x1"] - ext["x0"]
    h = ext["y1"] - ext["y0"]
    fx, fy = (x - ext["x0"]) / w, (y - ext["y0"]) / h
    ns = "north" if fy > 0.62 else "south" if fy < 0.38 else "middle"
    ew = "east" if fx > 0.62 else "west" if fx < 0.38 else "centre"
    return f"{ns}-{ew}" if ns != "middle" or ew != "centre" else "centre"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", type=Path, default=HERE / "build")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    snap = json.loads((HERE / "entities_snapshot.json").read_text())
    by_area = defaultdict(list)
    for e in snap["lights"]:
        if e["kind"] != "exclude":
            by_area[e["area"]].append(e)

    FLOOR_HINT = {
        "ground": ["kitchen", "dining_table", "living_room", "matteo_s_office", "toilet",
                   "reduit", "garage", "entry", "outside_front_door", "garden",
                   "stairs_up", "stairs_down"],
        "first": ["mia_s_room", "devin_s_bedroom", "bedroom", "main_bathroom",
                  "reduit_upstairs", "corridor_upstairs", "closet"],
        "basement": ["keller", "technic_room", "guest_room", "manu_s_office",
                     "corridor_downstairs"],
    }

    L = []
    add = L.append
    add("# " + "=" * 76)
    add("#  LIGHT OUTLET  ->  HOME ASSISTANT ENTITY  BINDING")
    add("# " + "=" * 76)
    add("#")
    add("#  Fill in `entity:` for each outlet, then hand this file back. That is the")
    add("#  only field to edit — everything else is context.")
    add("#")
    add("#  READING AN ENTRY")
    add("#    - {i: 19, xy: [7.6, 6.8], type: recessed, entity: ~}")
    add("#      i      = the NUMBER printed on the overlay PNG for this floor")
    add("#      xy     = metres from that floor's south-west corner (x east, y north)")
    add("#      type   = recessed (double ring on the plan) / surface (single ring)")
    add("#      entity = what to control.  <-- THE ONLY FIELD TO EDIT")
    add("#")
    add("#  Outlets are grouped into lettered CLUSTERS by physical proximity. The same")
    add("#  letters are drawn on the overlay PNGs, so cluster D in this file is the")
    add("#  group marked D on the image. Clusters usually correspond to one switch.")
    add("#")
    add("#  RULES")
    add("#    * Several outlets SHARING one entity is normal — a 6-lamp ceiling grid on")
    add("#      one switch is simply the same entity six times. Whole clusters often")
    add("#      take a single entity; write it on each line.")
    add("#    * Don't know / nothing connected / not in HA  ->  leave `entity: ~`")
    add("#      Those become dim passive dots on the plan, not broken buttons.")
    add("#    * `entity: skip` drops the outlet from the floorplan entirely.")
    add("#")
    add("#  WORTH KNOWING")
    add("#    (switch) = wall switch presented as a light: ON/OFF only, cannot dim.")
    add("#    (bulb)   = real Zigbee bulb, can dim and take colour.")
    add("#    (group)  = controls a whole room at once — usually the right answer when")
    add("#               several outlets sit on one physical switch.")
    add("#")
    add("#  I have NOT guessed which room each outlet is in. Two automated attempts")
    add("#  (nearest-label, and flood-filling the walls) both produced nonsense, and a")
    add("#  confident-looking wrong default is worse than a blank. You have the overlay")
    add("#  image and you know the house — see scripts/floorplan/README.md for why.")
    add("#")

    totals, cluster_map = {}, {}
    for floor in ("ground", "first", "basement"):
        data = json.loads((args.build / f"{floor}.json").read_text())
        lums, ext = data["luminaires"], data["extent_m"]
        totals[floor] = len(lums)

        pts = [(i, l["x_m"], l["y_m"]) for i, l in enumerate(lums, start=1)]
        pos = {i: (x, y) for i, x, y in pts}
        groups = cluster(pts)
        # order: north to south, then west to east, so reading order follows the plan
        groups.sort(key=lambda g: (-max(pos[i][1] for i in g),
                                   min(pos[i][0] for i in g)))

        add("")
        add("# " + "#" * 74)
        add(f"#  {floor.upper()} FLOOR  —  {len(lums)} outlets in "
            f"{len(groups)} clusters  (overlay_{floor}.png)")
        add("# " + "#" * 74)
        add("#  Entities on this floor:")
        for area in FLOOR_HINT[floor]:
            for c in by_area.get(area, []):
                add(f"#    {c['entity_id']:<52} {c['name']} ({c['kind']})")
        add(f"{floor}:")

        letters = []
        for n, g in enumerate(groups):
            letter = (string.ascii_uppercase[n] if n < 26
                      else "A" + string.ascii_uppercase[n - 26])
            letters.append((letter, g))
            cpts = [(i, *pos[i]) for i in g]
            cx = sum(pos[i][0] for i in g) / len(g)
            cy = sum(pos[i][1] for i in g) / len(g)
            nums = ", ".join(str(i) for i in sorted(g))
            add("")
            add(f"  # ---- {letter}:  {describe(cpts)} ".ljust(78, "-"))
            add(f"  #      {compass(cx, cy, ext)} of the floor   |   outlets {nums}")
            note = tight_note(cpts)
            if note:
                add(f"  #      NOTE: {note}")
            add(f"  #      entity for all of {letter}:  ______________________________")
            for i in sorted(g, key=lambda i: (-pos[i][1], pos[i][0])):
                lum = lums[i - 1]
                add(f"  - {{i: {i:>2}, xy: [{lum['x_m']-ext['x0']:>4.1f}, "
                    f"{lum['y_m']-ext['y0']:>4.1f}], "
                    f"type: {lum['class']:<8}, entity: ~}}   # {letter}")
        cluster_map[floor] = [
            {"letter": lt, "outlets": sorted(g),
             "x": round(sum(pos[i][0] for i in g) / len(g), 3),
             "y": round(sum(pos[i][1] for i in g) / len(g), 3)}
            for lt, g in letters
        ]

    add("")
    add("# " + "=" * 76)
    add(f"#  TOTAL {sum(totals.values())} outlets — "
        + ", ".join(f"{k} {v}" for k, v in totals.items()))
    add("# " + "=" * 76)

    args.out.write_text("\n".join(L) + "\n")
    (args.build / "clusters.json").write_text(json.dumps(cluster_map, indent=2))
    print(f"{args.out}  ({sum(totals.values())} outlets)")
    for f in totals:
        print(f"  {f:9s} {totals[f]:3d} outlets in {len(cluster_map[f]):2d} clusters")


if __name__ == "__main__":
    main()
