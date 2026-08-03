#!/usr/bin/env python3
"""Census of NWK_NO_ROUTE errors across the whole z2m log set.

Read-only. Answers the control question: is downlink failure specific to the
pool plugs, or network-wide?
"""
import re
import collections
import glob
import os

DATA = "/mnt/data/docker_persistent/zigbee2mqtt/data"
LOGDIR = sorted(glob.glob(DATA + "/log/*/"), key=os.path.getmtime)[-1]

# friendly names come from configuration.yaml (no PyYAML on this host, so
# parse the simple two-line-per-device shape directly)
names = {}
pending = None
for line in open(DATA + "/configuration.yaml", errors="replace"):
    m = re.match(r"\s*['\"]?(0x[0-9a-f]{16})['\"]?:\s*$", line)
    if m:
        pending = m.group(1)
        continue
    m2 = re.search(r"friendly_name:\s*(.+?)\s*$", line)
    if m2 and pending:
        names[pending] = m2.group(1).strip("'\" ")
        pending = None

noroute = collections.Counter()
other_err = collections.Counter()
seen = collections.Counter()
shapes = collections.Counter()
first_last = {}

files = sorted(glob.glob(LOGDIR + "log*.log"))
for f in files:
    for line in open(f, errors="replace"):
        ies = re.findall(r"0x[0-9a-f]{16}", line)
        for ie in set(ies):
            seen[ie] += 1
        if "NWK_NO_ROUTE" in line:
            ts = line[1:20]
            if ies:
                dev = ies[0]
                noroute[dev] += 1
                if dev not in first_last:
                    first_last[dev] = [ts, ts]
                first_last[dev][1] = ts
            head = line.split("(ZCL command")[0]
            head = re.sub(r"0x[0-9a-f]{16}", "<dev>", head)
            shapes[head[:70].strip()] += 1
        elif re.search(r"\berror\b", line) and ies:
            other_err[ies[0]] += 1

print("logdir:", LOGDIR)
print("files :", ", ".join(os.path.basename(x) for x in files))
print()
print(f"devices appearing in logs      : {len(seen)}")
print(f"devices WITH NWK_NO_ROUTE      : {len(noroute)}")
print(f"devices with other error lines : {len(other_err)}")
print()
print("=== EVERY device with NWK_NO_ROUTE (count, first seen, last seen) ===")
for ie, c in noroute.most_common():
    fl = first_last.get(ie, ["?", "?"])
    print(f"{c:6}  {fl[0]}  ->  {fl[1]}  {ie}  {names.get(ie, '?')}")
print()
print("=== other-error devices NOT in the NO_ROUTE set ===")
clean = [(ie, c) for ie, c in other_err.most_common() if ie not in noroute]
for ie, c in clean[:15]:
    print(f"{c:6}  {ie}  {names.get(ie, '?')}")
if not clean:
    print("  (none)")
print()
print("=== NO_ROUTE line shapes ===")
for k, c in shapes.most_common(8):
    print(f"{c:6}  {k}")
