#!/usr/bin/env python3
"""Positive downlink check from a z2m raw network map.

A device that ANSWERS Mgmt_Lqi_req had a downlink unicast delivered at a known
timestamp -- the only success-detecting instrument available here. Its *failure*
proves nothing (the command is optional), so only 'lqi answered' is evidence.

Usage: parse_map.py <map.json>
"""
import json
import sys

POOL = {
    "0xa4c13839620fc0b3": "PUMP",
    "0xa4c13859562db40c": "HEATER",
    "0xa4c138ca1c6b474b": "SALINATOR",
    "0x00178801094b0c0f": "MOSQUITO (Hue control)",
    "0x70d07efffe432949": "POOL SENSOR (EndDevice control)",
}

m = json.load(open(sys.argv[1]))
# z2m wraps the payload as {"data":{"routes":true,"type":"raw","value":{nodes,links}},"status":"ok"}
d = m.get("data", m)
d = d.get("value", d)
nodes = d.get("nodes", [])
links = d.get("links", [])

print(f"nodes={len(nodes)} links={len(links)}")
print()
print(f"{'DEVICE':34} {'nwk':>6} {'failed[]':28} LQI ANSWERED?")
print("-" * 88)
by_ieee = {}
for n in nodes:
    ie = n.get("ieeeAddr")
    if ie in POOL:
        by_ieee[ie] = n
for ie, label in POOL.items():
    n = by_ieee.get(ie)
    if not n:
        print(f"{label:34} {'--':>6} {'ABSENT FROM MAP':28} n/a")
        continue
    failed = n.get("failed", [])
    answered = "lqi" not in failed
    verdict = "YES -- downlink DELIVERED" if answered else "no (proves nothing)"
    print(f"{label:34} {str(n.get('networkAddress')):>6} {str(failed):28} {verdict}")

# coordinator routing table, deduped (z2m repeats it across every link)
coord = None
for n in nodes:
    if n.get("type") == "Coordinator":
        coord = n.get("ieeeAddr")
        break
routes = {}
for l in links:
    if l.get("target", {}).get("ieeeAddr") == coord or l.get("targetIeeeAddr") == coord:
        for r in l.get("routes", []) or []:
            routes[r.get("destinationAddress")] = r
print()
print(f"coordinator routing table: {len(routes)} distinct destinations (deduped)")
for ie, label in POOL.items():
    n = by_ieee.get(ie)
    if not n:
        continue
    nwk = n.get("networkAddress")
    r = routes.get(nwk)
    print(f"  {label:34} nwk={nwk:>6}  {'ROUTE: ' + json.dumps(r) if r else 'NO ROUTE ENTRY'}")
