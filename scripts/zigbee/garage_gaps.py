#!/usr/bin/env python3
"""Extract the Garage Door (PJ-ZGD01) publish stream from z2m's journal and report
publish gaps + contact transitions.

The module publishes every ~30 s when healthy and then goes silent for hours. HA only
records *state changes*, so a blackout that swallows an open->close pair is invisible
there. This reads the MQTT publish stream instead, which is the only place the silence
is visible.

Run on Optimus Prime, or pipe a journal in from anywhere:
    sudo journalctl -u zigbee2mqtt --since '14 days ago' --no-pager | garage_gaps.py -
    ssh 192.168.1.10 "sudo journalctl -u zigbee2mqtt --since '14 days ago' --no-pager" | garage_gaps.py -
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime

# z2m log line: [2026-08-30 22:27:46] info: z2m:mqtt: MQTT publish: topic 'zigbee2mqtt/Garage Door', payload '{...}'
LINE = re.compile(
    r"\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\].*"
    r"topic 'zigbee2mqtt/Garage Door'.*"
    r'"garage_door_contact":(?P<contact>true|false)'
)
# The device name is a prefix of the cameras' ("Garage Door Back All"), so anchor on the
# exact MQTT topic above rather than a bare name match.


def parse(lines):
    out = []
    for line in lines:
        m = LINE.search(line)
        if m:
            ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S")
            out.append((ts, m.group("contact") == "true"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default="journal",
                    help="'-' to read a journal on stdin, otherwise run journalctl")
    ap.add_argument("--since", default="14 days ago")
    ap.add_argument("--min-gap", type=int, default=120,
                    help="report gaps longer than this many seconds (default 120)")
    args = ap.parse_args()

    if args.source == "-":
        samples = parse(sys.stdin)
    else:
        cmd = ["sudo", "journalctl", "-u", "zigbee2mqtt", "--since", args.since, "--no-pager"]
        samples = parse(subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines())

    if not samples:
        print("no Garage Door publishes found in the journal window", file=sys.stderr)
        return 1

    print(f"publishes: {len(samples)}   {samples[0][0]}  ->  {samples[-1][0]}")

    # Contact transitions: what HA would have seen.
    print("\n=== contact transitions (true=closed, false=open) ===")
    prev = None
    for ts, c in samples:
        if c != prev:
            print(f"  {ts}  contact={'closed' if c else 'OPEN'}")
            prev = c

    # Gaps: what HA could not have seen.
    gaps = []
    for (t0, c0), (t1, _) in zip(samples, samples[1:]):
        d = (t1 - t0).total_seconds()
        if d > args.min_gap:
            gaps.append((d, t0, t1, c0))

    print(f"\n=== gaps > {args.min_gap}s ===")
    for d, t0, t1, c0 in gaps:
        h = d / 3600
        print(f"  {h:6.2f} h  {t0}  ->  {t1}   (was reading {'closed' if c0 else 'OPEN'})")

    # A gap is dangerous in proportion to how long the door state is unverifiable, so the
    # distribution matters more than the max when choosing an alert threshold.
    if gaps:
        ds = sorted(d / 3600 for d, _, _, _ in gaps)
        span_h = (samples[-1][0] - samples[0][0]).total_seconds() / 3600
        days = max(span_h / 24, 1e-9)
        print(f"\n=== distribution over {span_h:.1f} h ({days:.1f} days) ===")
        print(f"  gaps: {len(gaps)}  ({len(gaps)/days:.1f}/day)")
        print(f"  median {ds[len(ds)//2]:.2f} h   p90 {ds[int(len(ds)*0.9)]:.2f} h   max {ds[-1]:.2f} h")
        print(f"  blind time: {sum(ds):.1f} h of {span_h:.1f} h = {100*sum(ds)/span_h:.1f}%")
        for thr in (1, 2, 3, 6, 12, 14, 24):
            n = sum(1 for d in ds if d > thr)
            print(f"  threshold {thr:>2} h would fire {n:>3} times = {n/days:.2f}/day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
