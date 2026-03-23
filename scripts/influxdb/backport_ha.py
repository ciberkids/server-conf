#!/usr/bin/env python3
"""Backport Home Assistant statistics from PostgreSQL to InfluxDB."""
import psycopg2
import requests
import sys

PG_DSN = "host=192.168.1.10 dbname=homedata user=homeassistant password=homeassistant"
INFLUX_URL = "http://192.168.1.10:8086/api/v2/write?org=favarohome&bucket=homeassistant&precision=s"
INFLUX_TOKEN = "favarohome-influxdb-token-2026"
BATCH_SIZE = 5000

def escape_tag(s):
    if not s:
        return ""
    return s.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

def main():
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor("backport_cursor")
    cur.itersize = BATCH_SIZE

    count_cur = conn.cursor()
    count_cur.execute("SELECT COUNT(*) FROM statistics")
    total = count_cur.fetchone()[0]
    count_cur.close()
    print(f"Total statistics rows to migrate: {total:,}")

    cur.execute("""
        SELECT s.start_ts, s.mean, s.min, s.max, s.state, s.sum,
               sm.statistic_id, sm.unit_of_measurement, sm.has_mean, sm.has_sum
        FROM statistics s
        JOIN statistics_meta sm ON s.metadata_id = sm.id
        ORDER BY s.start_ts ASC
    """)

    lines = []
    written = 0
    errors = 0

    for row in cur:
        ts, mean, mn, mx, state, sm, stat_id, unit, has_mean, has_sum = row
        if unit is None:
            unit = ""

        measurement = escape_tag(unit) if unit else "state"
        parts = stat_id.split(".", 1)
        domain = parts[0] if len(parts) > 1 else "unknown"
        entity_id = parts[1] if len(parts) > 1 else stat_id

        tags = f"domain={escape_tag(domain)},entity_id={escape_tag(entity_id)},source=backport"

        fields = []
        if mean is not None:
            fields.append(f"mean={mean}")
        if mn is not None:
            fields.append(f"min={mn}")
        if mx is not None:
            fields.append(f"max={mx}")
        if state is not None:
            fields.append(f"state={state}")
        if sm is not None:
            fields.append(f"sum={sm}")
        if mean is not None:
            fields.append(f"value={mean}")
        elif state is not None:
            fields.append(f"value={state}")

        if not fields:
            continue

        field_str = ",".join(fields)
        line = f"{measurement},{tags} {field_str} {ts}"
        lines.append(line)

        if len(lines) >= BATCH_SIZE:
            payload = "\n".join(lines)
            r = requests.post(INFLUX_URL, data=payload,
                            headers={"Authorization": f"Token {INFLUX_TOKEN}",
                                     "Content-Type": "text/plain"})
            if r.status_code != 204:
                errors += 1
                if errors <= 3:
                    print(f"  Error {r.status_code}: {r.text[:200]}")
            written += len(lines)
            lines = []
            pct = written / total * 100
            print(f"  Progress: {written:,}/{total:,} ({pct:.1f}%)", flush=True)

    if lines:
        payload = "\n".join(lines)
        r = requests.post(INFLUX_URL, data=payload,
                        headers={"Authorization": f"Token {INFLUX_TOKEN}",
                                 "Content-Type": "text/plain"})
        if r.status_code != 204:
            errors += 1
            print(f"  Error {r.status_code}: {r.text[:200]}")
        written += len(lines)

    cur.close()
    conn.close()
    print(f"\nDone! Wrote {written:,} points with {errors} errors.")

if __name__ == "__main__":
    main()
