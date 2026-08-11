#!/usr/bin/env python3
"""Draw NUMBERED luminaire markers over the real plan, for entity binding by eye.

The extractor finds where every light outlet physically is, but it cannot know which
`light.*` entity switches it — many outlets are ganged onto one entity (a 6-lamp
kitchen grid is one or two switches; the garage row is one), and some outlets have no
HA entity at all. That mapping needs a human looking at the plan.

This produces a reference image where every extracted outlet carries an index, so the
indices can simply be listed against entity_ids.

Usage:
    ./lamp_overlay.py <plan.pdf> <extracted.json> --out overlay.svg
    inkscape overlay.svg -o overlay.png -w 2400
"""

import argparse
import json
import re
from pathlib import Path

from extract_plan import PT_PER_M, pdf_to_svg

# The electrical sheets carry matrix(1,0,0,-1,0,H): CAD is Y-up, SVG is Y-down. Plan
# geometry is drawn inside that flip; markers and their labels are drawn OUTSIDE it at
# (x, H-y) so the numbers come out upright rather than mirrored.
FLIP_RE = re.compile(r"matrix\(1,\s*0,\s*0,\s*-1,\s*0,\s*([\d.]+)\)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--clusters", type=Path,
                    help="clusters.json from make_binding_proposal.py; draws the same "
                         "cluster letters used in the binding YAML")
    ap.add_argument("--floor", help="which floor key to read from --clusters")
    args = ap.parse_args()

    svg = pdf_to_svg(args.pdf)
    data = json.loads(args.json.read_text())

    # outlet index -> cluster letter, so the image and the YAML cross-reference
    letter_of, cluster_centres = {}, []
    if args.clusters and args.clusters.exists():
        floor = args.floor or data["floor"]
        for c in json.loads(args.clusters.read_text()).get(floor, []):
            for i in c["outlets"]:
                letter_of[i] = c["letter"]
            cluster_centres.append(c)

    root = re.search(r"<svg[^>]*>", svg).group(0)
    width = float(re.search(r'width="([\d.]+)', root).group(1))
    height = float(re.search(r'height="([\d.]+)', root).group(1))
    flip = FLIP_RE.search(svg)
    flip_h = float(flip.group(1)) if flip else height

    # keep only the drawing body, drop the glyph <defs>
    d0, d1 = svg.find("<defs>"), svg.find("</defs>")
    body = svg[:d0] + svg[d1 + len("</defs>"):] if d0 != -1 else svg
    body = body[body.find(">", body.find("<svg")) + 1:].replace("</svg>", "")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<g opacity="0.35">{body}</g>',       # the plan, faded to a backdrop
    ]

    for i, lum in enumerate(data["luminaires"], start=1):
        x = lum["plan_pt"][0]
        y = flip_h - lum["plan_pt"][1]
        col = "#d94f00" if lum["class"] == "recessed" else "#0a68d0"
        out.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7.5" fill="{col}" '
            f'fill-opacity="0.9" stroke="white" stroke-width="1.2"/>'
        )
        out.append(
            f'<text x="{x:.2f}" y="{y + 3.0:.2f}" font-family="DejaVu Sans, sans-serif" '
            f'font-size="8.5" font-weight="bold" fill="white" '
            f'text-anchor="middle">{i}</text>'
        )

    # cluster letters, offset above-left of the group so they don't hide the numbers
    for c in cluster_centres:
        pts = [data["luminaires"][i - 1]["plan_pt"] for i in c["outlets"]]
        cx = min(p[0] for p in pts) - 13
        cy = flip_h - max(p[1] for p in pts) - 13
        out.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="10" fill="#111" '
            f'fill-opacity="0.82"/>'
            f'<text x="{cx:.1f}" y="{cy + 4.2:.1f}" '
            f'font-family="DejaVu Sans, sans-serif" font-size="12" font-weight="bold" '
            f'fill="#ffd400" text-anchor="middle">{c["letter"]}</text>'
        )

    # legend
    out.append(
        f'<g font-family="DejaVu Sans, sans-serif" font-size="11">'
        f'<text x="12" y="18" font-weight="bold">{data["floor"]} — '
        f'{len(data["luminaires"])} light outlets'
        + (f' in {len(cluster_centres)} clusters' if cluster_centres else '')
        + '</text>'
        f'<circle cx="18" cy="34" r="6" fill="#d94f00"/>'
        f'<text x="30" y="38">recessed / dimmed (double ring on plan)</text>'
        f'<circle cx="18" cy="52" r="6" fill="#0a68d0"/>'
        f'<text x="30" y="56">surface outlet (single ring)</text>'
        + (f'<circle cx="18" cy="70" r="7" fill="#111" fill-opacity="0.82"/>'
           f'<text x="18" y="74" font-size="9" font-weight="bold" fill="#ffd400" '
           f'text-anchor="middle">A</text>'
           f'<text x="30" y="74">cluster letter — matches '
           f'docs/floorplan-light-bindings.yaml</text>' if cluster_centres else '')
        + '</g>'
    )
    out.append("</svg>")
    args.out.write_text("".join(out))
    print(f"{args.out}  ({len(data['luminaires'])} numbered outlets)")


if __name__ == "__main__":
    main()
