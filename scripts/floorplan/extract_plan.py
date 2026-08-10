#!/usr/bin/env python3
"""Extract wall geometry and light-fixture positions from the house electrical plans.

Why the ELECTRICAL plans and not the architectural ones
-------------------------------------------------------
Both sets are true vector CAD (0 embedded rasters), but:

  * `1_Pläne BUVAG/*.pdf` (ARCHICAD) draws walls as *hatched* regions — the wall
    faces are buried in hundreds of short hatch strokes, and the sheet is in a
    custom 840x450 mm frame with a uniform matrix(2.8336,...) transform (= 72/25.4,
    i.e. the local unit is paper millimetres).
  * `3_Elektropläne/*.PDF` (BricsCAD, eboplan.ch) is on A3, carries only a Y-flip
    transform matrix(1,0,0,-1,0,841) so coordinates are already PostScript points,
    AND is colour-separated by circuit type.

Crucially the electrical sheets contain the walls *and* the surveyed light-outlet
positions in the SAME coordinate frame, so no cross-sheet affine registration is
needed. That removes the single largest source of error (lights landing a room off).

Colour separation observed on `0. erdgeschoss (1)_inst NEU.PDF`:
    black  rgb(0%,0%,0%)      building fabric: walls, doors, stairs, fixtures
    blue   rgb(0%,0%,100%)    lighting circuits + luminaire outlets
    red    rgb(100%,0%,0%)    power / socket circuits
    cyan, green, magenta      weak current, earthing, misc

Luminaire symbol (the classic ⊗ "Leuchtenanschluss"):
    a circle of 8.50 pt diameter, drawn as M + 4 cubic béziers (5 commands),
    plus two ~8.35 x 8.49 pt diagonal strokes forming the X.
    A concentric 11.91 pt circle marks a second fixture class (recessed/dimmed).

Scale: the architectural sheets state "1 : 50". Confirmed independently — the
longest continuous black run on the electrical ground floor is 1099.7 pt, which is
19.40 m at 1:50 (the site/terrace width incl. the double garage). At 1:100 it would
be 38.8 m, impossible for this building. So:

    1 m = 72/25.4 * 1000/50 = 56.6929 pt

Usage:
    ./extract_plan.py <plan.pdf> [--floor ground] [--out out.json] [--verify out.svg]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

PT_PER_M = 72 / 25.4 * 1000 / 50          # 56.6929 pt per metre at 1:50

BLACK = "rgb(0%, 0%, 0%)"
BLUE = "rgb(0%, 0%, 100%)"
RED = "rgb(100%, 0%, 0%)"

# Measured, not assumed. Histogramming the gap between every pair of parallel
# overlapping merged faces on the ground floor gives clear peaks at 13, 15/16, 20 and
# 28 cm, which line up with the architectural plan's callouts (kalksandstein
# partition, backstein, and the "nachträglich aufmauern" build-up). 15 and 16 are the
# same nominal 15 cm wall measured either side of a rounding boundary.
#
# The tolerance must stay TIGHT. At ±2 cm these four targets cover almost the whole
# 10-29 cm range, so kitchen counters, terrace paving and furniture outlines all
# qualify as "walls" — that produced 1294 bogus walls on this floor.
WALL_THICKNESS_CM = (13, 15.5, 20, 28)
THICKNESS_TOL_PT = 0.55                    # ±1 cm at 1:50

MIN_WALL_LEN_PT = 20.0                     # ignore runs under ~35 cm
AXIS_TOL_PT = 0.35                         # how straight counts as axis-aligned
COLLINEAR_TOL_PT = 0.6                     # faces within 1 cm count as the same line

# CAD splits one wall face into several collinear pieces at junctions. Measuring the
# gap distribution on the ground floor gives a natural break: 26 gaps are <=20 cm
# (segmentation artifacts) and the next cluster is 70-150 cm (real door/window
# openings), with 239 gaps over 3 m (unrelated walls). Joining at 20 cm therefore
# repairs the fragmentation while leaving every real opening as a genuine hole.
DEFAULT_JOIN_GAP_CM = 20.0

# Below this a "wall" is furniture, a door frame or a symbol box that happens to show
# two parallel faces at a wall-like spacing. 60 cm is under the narrowest real
# partition stub in the house but well above the furniture outlines.
MIN_KEEP_LEN_M = 0.60

# The decisive discriminator: in these plans WALLS ARE HATCHED and furniture is not.
# The hatch is drawn as thousands of short strokes (measured: 782 in the 5-30 cm band
# on the ground floor). So a candidate wall rectangle that contains no hatch strokes is
# a kitchen counter, a terrace paving line or a symbol box — not a wall. Requiring a
# minimum hatch density per metre rejects those on evidence rather than on another
# tolerance tweak.
MAX_HATCH_LEN_PT = 17.0                    # a stroke longer than ~30 cm isn't hatch
MIN_HATCH_PER_M = 4.0                      # strokes per metre of wall to qualify


def pdf_to_svg(pdf: Path) -> str:
    """Convert a single-page vector PDF to SVG text via pdftocairo."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        out = Path(tmp.name)
    subprocess.run(["pdftocairo", "-svg", str(pdf), str(out)], check=True)
    text = out.read_text()
    out.unlink(missing_ok=True)
    return text


def parse_paths(svg: str) -> list[dict]:
    """Return drawing paths, skipping the <defs> block (text glyph outlines)."""
    d0, d1 = svg.find("<defs>"), svg.find("</defs>")
    body = svg[:d0] + svg[d1:] if d0 != -1 else svg

    paths = []
    for m in re.finditer(r"<path\b([^>]*?)/?>", body):
        attrs = m.group(1)

        def attr(name):
            hit = re.search(rf'\b{name}="([^"]*)"', attrs)
            return hit.group(1) if hit else None

        d = attr("d")
        if not d:
            continue
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", d)]
        if len(nums) < 4:
            continue
        xs, ys = nums[0::2], nums[1::2]
        paths.append(
            {
                "d": d,
                "fill": attr("fill"),
                "stroke": attr("stroke"),
                "x0": min(xs), "x1": max(xs),
                "y0": min(ys), "y1": max(ys),
                "pts": list(zip(xs, ys)),
                "segments": straight_segments(d),
                "ncmd": len(re.findall(r"[MLCZ]", d)),
            }
        )
    return paths


def straight_segments(d: str):
    """Yield the STRAIGHT segments of a path as ((x1,y1),(x2,y2)).

    Necessary because the building fabric is not all 2-point paths: the ground-floor
    outline is a single 31-point polyline, and interior partitions are polylines too.
    Only M/L/Z runs produce segments — C (cubic) spans are curves (door swings,
    symbols, luminaire rings) and are deliberately skipped, though a curve still
    advances the cursor so the following L starts in the right place.
    """
    tokens = re.findall(r"([MLCZmlcz])([^MLCZmlcz]*)", d)
    segs, cur, start = [], None, None
    for cmd, body in tokens:
        vals = [float(v) for v in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", body)]
        up = cmd.upper()
        if up == "M":
            for i in range(0, len(vals) - 1, 2):
                pt = (vals[i], vals[i + 1])
                # a multi-coordinate M is an implicit lineto after the first pair
                if i and cur:
                    segs.append((cur, pt))
                cur = pt
                if i == 0:
                    start = pt
        elif up == "L":
            for i in range(0, len(vals) - 1, 2):
                pt = (vals[i], vals[i + 1])
                if cur:
                    segs.append((cur, pt))
                cur = pt
        elif up == "C":
            # skip the curve itself, but land the cursor on its endpoint
            for i in range(0, len(vals) - 5, 6):
                cur = (vals[i + 4], vals[i + 5])
        elif up == "Z":
            if cur and start and cur != start:
                segs.append((cur, start))
            cur = start
    return segs


def colour_of(p: dict) -> str | None:
    """Effective ink colour: stroke wins, else fill."""
    if p["stroke"] and p["stroke"] != "none":
        return p["stroke"]
    return p["fill"]


def extract_luminaires(paths: list[dict]) -> list[dict]:
    """Blue circle glyphs = luminaire outlets. Returns positions in metres."""
    found = defaultdict(set)
    for p in paths:
        if colour_of(p) != BLUE or p["ncmd"] != 5:
            continue
        w, h = p["x1"] - p["x0"], p["y1"] - p["y0"]
        if abs(w - h) > 0.2 or not 7.0 < w < 13.0:
            continue                      # not one of the two circle classes
        cx, cy = (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2
        found[round(w, 1)].add((round(cx, 2), round(cy, 2)))

    # Concentric pairs are ONE fixture drawn with two rings, not two fixtures.
    small = found.get(8.5, set())
    large = found.get(11.9, set())
    concentric = {s for s in small for l in large
                  if abs(s[0] - l[0]) < 1.0 and abs(s[1] - l[1]) < 1.0}

    lums = []
    for cx, cy in sorted(small | large):
        is_double = (cx, cy) in concentric or any(
            abs(cx - l[0]) < 1.0 and abs(cy - l[1]) < 1.0 for l in large
        )
        lums.append(
            {
                "x_m": round(cx / PT_PER_M, 3),
                "y_m": round(cy / PT_PER_M, 3),
                "class": "recessed" if is_double else "surface",
                "plan_pt": [cx, cy],
                "entity_id": None,          # filled in by hand / by the mapping step
            }
        )
    return lums


def merge_collinear(faces, join_gap_pt):
    """Union collinear face pieces that CAD split apart.

    `faces` is [(line_coord, span_lo, span_hi)]. Pieces sharing a line coordinate
    (within COLLINEAR_TOL_PT) and separated by no more than `join_gap_pt` become one
    run. Larger gaps are left alone: they are real door/window openings.
    """
    lanes = defaultdict(list)
    for coord, lo, hi in faces:
        lanes[round(coord / COLLINEAR_TOL_PT)].append((lo, hi))

    merged = []
    for key, spans in lanes.items():
        coord = key * COLLINEAR_TOL_PT
        spans.sort()
        cur_lo, cur_hi = spans[0]
        for lo, hi in spans[1:]:
            if lo <= cur_hi + join_gap_pt:
                cur_hi = max(cur_hi, hi)
            else:
                merged.append((coord, cur_lo, cur_hi))
                cur_lo, cur_hi = lo, hi
        merged.append((coord, cur_lo, cur_hi))
    return merged


def hatch_points(paths):
    """Midpoints of every short black stroke — i.e. the hatch fill inside walls."""
    pts = []
    for p in paths:
        if colour_of(p) != BLACK:
            continue
        for (xa, ya), (xb, yb) in p["segments"]:
            if abs(xb - xa) + abs(yb - ya) <= MAX_HATCH_LEN_PT:
                pts.append(((xa + xb) / 2, (ya + yb) / 2))
    return pts


def keep_hatched(walls, hatch, min_per_m=MIN_HATCH_PER_M):
    """Drop candidate walls whose rectangle contains too little hatch fill."""
    # bucket hatch points into 20 pt cells so each wall only tests nearby points
    cell = 20.0
    grid = defaultdict(list)
    for x, y in hatch:
        grid[(int(x // cell), int(y // cell))].append((x, y))

    kept = []
    for w in walls:
        half = w["thickness_cm"] / 100 / 2 * PT_PER_M
        c = w["centre_m"] * PT_PER_M
        lo, hi = w["start_m"] * PT_PER_M, w["end_m"] * PT_PER_M
        if w["axis"] == "h":
            x0, x1, y0, y1 = lo, hi, c - half, c + half
        else:
            x0, x1, y0, y1 = c - half, c + half, lo, hi

        n = 0
        for gx in range(int(x0 // cell), int(x1 // cell) + 1):
            for gy in range(int(y0 // cell), int(y1 // cell) + 1):
                for x, y in grid.get((gx, gy), ()):
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        n += 1
        w = dict(w, hatch_per_m=round(n / max(w["length_m"], 0.01), 1))
        if w["hatch_per_m"] >= min_per_m:
            kept.append(w)
    return kept


def drop_contained(walls, overlap_frac=0.70):
    """Remove thin walls that sit inside a thicker wall at the same place.

    Ground-floor exterior walls are COMPOSITE (concrete + insulation + facing), so they
    draw several parallel faces. Sub-pairs at 13/15/20 cm then match inside the real
    28 cm wall, are all genuinely hatched, and so survive the hatch filter — they are
    the same wall counted several times. Keep the thickest, drop what it swallows.
    """
    order = sorted(walls, key=lambda w: (-w["thickness_cm"], -w["length_m"]))
    kept = []
    for w in order:
        swallowed = False
        for k in kept:
            if k["axis"] != w["axis"]:
                continue
            # is w's centre-line inside k's footprint?
            if abs(k["centre_m"] - w["centre_m"]) > k["thickness_cm"] / 100 / 2 + 0.01:
                continue
            ov = min(k["end_m"], w["end_m"]) - max(k["start_m"], w["start_m"])
            if ov >= overlap_frac * w["length_m"]:
                swallowed = True
                break
        if not swallowed:
            kept.append(w)
    return sorted(kept, key=lambda w: (w["axis"], w["centre_m"], w["start_m"]))


def consolidate(walls, min_len_m=MIN_KEEP_LEN_M):
    """Collapse the raw pair-matches into one entry per physical wall.

    Non-consuming pair matching deliberately over-produces (a long face pairs with
    several opposite faces, and every sub-span shows up), so walls sharing an axis,
    centre-line and thickness get their spans unioned. Then anything still shorter
    than `min_len_m` is dropped: those are furniture outlines and symbol boxes that
    happened to present two parallel faces at a plausible wall thickness.
    """
    # Group by axis + centre-line ONLY. Bucketing by thickness as well used to split a
    # single wall across adjacent buckets, multiplying it instead of merging it.
    lanes = defaultdict(list)
    for w in walls:
        lanes[(w["axis"], round(w["centre_m"] / 0.03))].append(w)

    out = []
    for (axis, ckey), group in lanes.items():
        spans = sorted((w["start_m"], w["end_m"]) for w in group)
        centre = sum(w["centre_m"] for w in group) / len(group)
        thick = sorted(w["thickness_cm"] for w in group)[len(group) // 2]
        cur_lo, cur_hi = spans[0]
        merged = []
        for lo, hi in spans[1:]:
            if lo <= cur_hi + 0.02:          # touching or overlapping
                cur_hi = max(cur_hi, hi)
            else:
                merged.append((cur_lo, cur_hi))
                cur_lo, cur_hi = lo, hi
        merged.append((cur_lo, cur_hi))

        for lo, hi in merged:
            if hi - lo < min_len_m:
                continue
            out.append(
                {
                    "axis": axis,
                    "centre_m": round(centre, 3),
                    "start_m": round(lo, 3),
                    "end_m": round(hi, 3),
                    "thickness_cm": round(thick, 1),
                    "length_m": round(hi - lo, 3),
                }
            )
    return sorted(out, key=lambda w: (w["axis"], w["centre_m"], w["start_m"]))


def extract_walls(paths: list[dict], join_gap_cm=DEFAULT_JOIN_GAP_CM):
    """Detect walls as PARALLEL PAIRS of black faces at a known thickness.

    Hatching is short and diagonal; dimension lines are thin and isolated. A real
    wall always shows up as two long parallel faces separated by its thickness, so
    pair-matching rejects both without needing any layer information.

    Faces are merged (see merge_collinear) BEFORE pairing — otherwise a wall split
    into five pieces yields five stubby fragments instead of one clean run.
    """
    horiz, vert = [], []
    for p in paths:
        if colour_of(p) != BLACK:
            continue
        for (xa, ya), (xb, yb) in p["segments"]:
            dx, dy = abs(xb - xa), abs(yb - ya)
            # Keep short pieces here; merging is what makes them long. Anything under
            # ~9 cm is hatch fill and never survives to a wall.
            if dy <= AXIS_TOL_PT and dx >= 5.0:
                horiz.append((round((ya + yb) / 2, 2), min(xa, xb), max(xa, xb)))
            elif dx <= AXIS_TOL_PT and dy >= 5.0:
                vert.append((round((xa + xb) / 2, 2), min(ya, yb), max(ya, yb)))

    join_pt = join_gap_cm / 100 * PT_PER_M
    horiz = [f for f in merge_collinear(horiz, join_pt) if f[2] - f[1] >= MIN_WALL_LEN_PT]
    vert = [f for f in merge_collinear(vert, join_pt) if f[2] - f[1] >= MIN_WALL_LEN_PT]

    targets = [cm / 100 * PT_PER_M for cm in WALL_THICKNESS_CM]

    def pair_up(faces, axis):
        """Emit a wall for every valid face pair.

        Faces are NOT consumed on match: at a T-junction one long face legitimately
        forms a wall with two different opposite faces. Duplicates are removed after.
        """
        walls, matched = [], set()
        faces = sorted(set(faces))
        for i, (c1, a1, b1) in enumerate(faces):
            for j in range(i + 1, len(faces)):
                c2, a2, b2 = faces[j]
                gap = abs(c2 - c1)
                if gap > max(targets) + THICKNESS_TOL_PT:
                    break                   # sorted by coord: nothing closer ahead
                if not any(abs(gap - t) <= THICKNESS_TOL_PT for t in targets):
                    continue
                lo, hi = max(a1, a2), min(b1, b2)
                if hi - lo < MIN_WALL_LEN_PT:
                    continue                # faces don't actually overlap
                matched.update({i, j})
                walls.append(
                    {
                        "axis": axis,
                        "centre_m": round((c1 + c2) / 2 / PT_PER_M, 3),
                        "start_m": round(lo / PT_PER_M, 3),
                        "end_m": round(hi / PT_PER_M, 3),
                        "thickness_cm": round(gap / PT_PER_M * 100, 1),
                        "length_m": round((hi - lo) / PT_PER_M, 3),
                    }
                )
        return consolidate(walls), len(faces) - len(matched)

    hw, h_unmatched = pair_up(horiz, "h")
    vw, v_unmatched = pair_up(vert, "v")
    candidates = hw + vw

    hatched = keep_hatched(candidates, hatch_points(paths))
    final = drop_contained(hatched)
    stats = {
        "join_gap_cm": join_gap_cm,
        "horiz_faces": len(horiz), "vert_faces": len(vert),
        "horiz_unmatched": h_unmatched, "vert_unmatched": v_unmatched,
        "candidates_before_hatch_filter": len(candidates),
        "rejected_unhatched": len(candidates) - len(hatched),
        "rejected_contained": len(hatched) - len(final),
    }
    return final, stats


def write_verify_svg(dest: Path, walls, lums, extent):
    """Render just what we extracted, so it can be eyeballed against the real plan."""
    x0, x1, y0, y1 = extent
    pad = 1.0
    w_m, h_m = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    px = 100  # px per metre
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_m*px:.0f}" '
        f'height="{h_m*px:.0f}" viewBox="{x0-pad} {y0-pad} {w_m} {h_m}">',
        f'<rect x="{x0-pad}" y="{y0-pad}" width="{w_m}" height="{h_m}" fill="white"/>',
        '<g stroke="#222" stroke-linecap="butt">',
    ]
    for w in walls:
        t = w["thickness_cm"] / 100
        if w["axis"] == "h":
            parts.append(
                f'<line x1="{w["start_m"]}" y1="{w["centre_m"]}" '
                f'x2="{w["end_m"]}" y2="{w["centre_m"]}" stroke-width="{t}"/>'
            )
        else:
            parts.append(
                f'<line x1="{w["centre_m"]}" y1="{w["start_m"]}" '
                f'x2="{w["centre_m"]}" y2="{w["end_m"]}" stroke-width="{t}"/>'
            )
    parts.append("</g>")
    for l in lums:
        col = "#e07000" if l["class"] == "recessed" else "#0080ff"
        parts.append(
            f'<circle cx="{l["x_m"]}" cy="{l["y_m"]}" r="0.13" '
            f'fill="{col}" fill-opacity="0.85"/>'
        )
    parts.append("</svg>")
    dest.write_text("".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--floor", default="unknown")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path, help="write an SVG of what was extracted")
    ap.add_argument("--join-gap-cm", type=float, default=DEFAULT_JOIN_GAP_CM,
                    help="max collinear gap to bridge when merging wall faces "
                         f"(default {DEFAULT_JOIN_GAP_CM:g}; raise it to close door "
                         "openings, lower it to keep every gap)")
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(f"no such plan: {args.pdf}")

    paths = parse_paths(pdf_to_svg(args.pdf))
    lums = extract_luminaires(paths)
    walls, stats = extract_walls(paths, join_gap_cm=args.join_gap_cm)

    if not walls:
        sys.exit("no walls matched — check the scale assumption and WALL_THICKNESS_CM")

    xs = [w["start_m"] for w in walls if w["axis"] == "h"] + \
         [w["centre_m"] for w in walls if w["axis"] == "v"]
    ys = [w["centre_m"] for w in walls if w["axis"] == "h"] + \
         [w["start_m"] for w in walls if w["axis"] == "v"]
    xs += [w["end_m"] for w in walls if w["axis"] == "h"]
    ys += [w["end_m"] for w in walls if w["axis"] == "v"]
    extent = (min(xs), max(xs), min(ys), max(ys))

    result = {
        "source_pdf": str(args.pdf),
        "floor": args.floor,
        "scale": "1:50",
        "pt_per_m": round(PT_PER_M, 4),
        "extent_m": {"x0": round(extent[0], 3), "x1": round(extent[1], 3),
                     "y0": round(extent[2], 3), "y1": round(extent[3], 3)},
        "wall_stats": stats,
        "walls": walls,
        "luminaires": lums,
    }

    total_len = sum(w["length_m"] for w in walls)
    print(f"floor {args.floor}: {len(walls)} walls, {len(lums)} luminaires")
    print(f"  faces: {stats['horiz_faces']}h / {stats['vert_faces']}v   "
          f"unmatched: {stats['horiz_unmatched']}h / {stats['vert_unmatched']}v")
    print(f"  hatch filter: {stats['candidates_before_hatch_filter']} candidates -> "
          f"{len(walls)} kept ({stats['rejected_unhatched']} unhatched, "
          f"{stats['rejected_contained']} contained)")
    print(f"  extent: {extent[1]-extent[0]:.2f} m x {extent[3]-extent[2]:.2f} m")
    print(f"  total wall length: {total_len:.1f} m")
    by_class = defaultdict(int)
    for l in lums:
        by_class[l["class"]] += 1
    print(f"  luminaire classes: {dict(by_class)}")

    if args.out:
        args.out.write_text(json.dumps(result, indent=2))
        print(f"  -> {args.out}")
    if args.verify:
        write_verify_svg(args.verify, walls, lums, extent)
        print(f"  -> {args.verify}")


if __name__ == "__main__":
    main()
