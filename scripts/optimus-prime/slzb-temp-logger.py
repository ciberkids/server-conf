#!/usr/bin/env python3
"""
slzb-temp-logger — sample the SLZB-06 coordinator's temperatures into a CSV every 5 min.

WHY THIS EXISTS
The coordinator wedges periodically (see memory project-z2m-radio-stuck-bootloader) and
thermal is the leading hypothesis — it runs at ~92-95 C. But *nothing* was recording its
temperature, so no cooling change (fan, relocation, USB power) could be evaluated.

Judging a cooling fix by "no more wedges" does not work: the observed gaps between wedges
have been 4 days and then 18 days, so a quiet month is not evidence of anything. Temperature
is the proximate measurement — direct and immediate. Wedge frequency is the distal one.

WHY /ha_sensors AND NOT /metrics
/metrics is Prometheus-formatted and would be the tidier source, but it exposes only
`smlight_device_temp` (the ESP32). /ha_sensors carries BOTH `esp32_temp` and the radio's
`zb_temp` — and zb_temp is the one that tracks the wedges. Do not "improve" this to scrape
/metrics; it would silently drop the value we actually care about.

FAILURE SEMANTICS
A failed read still appends a row, with the fields empty and status=ERR:<type>. That keeps
two different faults distinguishable:
  - a GAP in the timestamps  => the logger itself was not running
  - an ERR row               => the logger ran, the device did not answer
Silently skipping on error would conflate them, and a conflated record is how you end up
concluding "it was fine" about a window with no data. A read failure is deliberately NOT a
unit failure (a transient blip must not Telegram-spam every 5 min); it is recorded instead.
A failure to WRITE the CSV does propagate, so OnFailure= fires on the fault that matters.
"""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime

URL = "http://192.168.1.69/ha_sensors"
CSV_PATH = "/mnt/data/matteo/zigbee-forensics/slzb-temps.csv"
TIMEOUT = 10
HEADER = [
    "ts_local",
    "esp32_temp",
    "zb_temp",
    "device_uptime_s",
    "socket_uptime_s",
    "ram_usage",
    "ram_largest_free_block",
    "status",
]


def read_sensors():
    with urllib.request.urlopen(URL, timeout=TIMEOUT) as r:
        return json.load(r)["Sensors"]


def main():
    row = {k: "" for k in HEADER}
    row["ts_local"] = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        s = read_sensors()
        row.update(
            {
                "esp32_temp": s.get("esp32_temp", ""),
                "zb_temp": s.get("zb_temp", ""),
                "device_uptime_s": s.get("uptime", ""),
                "socket_uptime_s": s.get("socket_uptime", ""),
                "ram_usage": s.get("ram_usage", ""),
                "ram_largest_free_block": s.get("ram_largest_free_block", ""),
                "status": "ok",
            }
        )
    except Exception as e:
        row["status"] = f"ERR:{type(e).__name__}"
        print(f"[slzb-temp-logger] read failed: {e}", file=sys.stderr)

    # Header only when the file is genuinely new/empty, so restarts don't inject a second one.
    fresh = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if fresh:
            w.writeheader()
        w.writerow(row)

    print(
        f"[slzb-temp-logger] {row['ts_local']} "
        f"esp32={row['esp32_temp']} zb={row['zb_temp']} status={row['status']}"
    )


if __name__ == "__main__":
    main()
