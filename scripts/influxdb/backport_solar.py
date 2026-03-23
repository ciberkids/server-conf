#!/usr/bin/env python3
"""Backport solar and energy statistics from PostgreSQL to InfluxDB with integer timestamps."""
import psycopg2
import requests

PG_DSN = "host=192.168.1.10 dbname=homedata user=homeassistant password=homeassistant"
INFLUX_URL = "http://192.168.1.10:8086/api/v2/write?org=favarohome&bucket=homeassistant&precision=s"
INFLUX_TOKEN = "***REDACTED***"
BATCH_SIZE = 5000

ENTITIES = [
    '%solar_production%',
    '%solarnet%',
    '%symo%',
    '%main_energy_meter%',
    '%rooms_energy_meter%',
    '%devices_energy_meter%',
    '%heating_energy_meter%',
    '%charging_station_energy_meter%',
    '%ht_nt%',
]

def escape_tag(s):
    if not s:
        return ""
    return s.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

def main():
    conn = psycopg2.connect(PG_DSN)

    where_clauses = " OR ".join([f"sm.statistic_id LIKE '{e}'" for e in ENTITIES])

    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM statistics s JOIN statistics_meta sm ON s.metadata_id = sm.id WHERE {where_clauses}")
    total = cur.fetchone()[0]
    cur.close()
    print(f"Total rows to migrate: {total:,}")

    cur = conn.cursor("solar_cursor")
    cur.itersize = BATCH_SIZE
    cur.execute(f"""
        SELECT CAST(s.start_ts AS bigint), s.mean, s.min, s.max, s.state, s.sum,
               sm.statistic_id, sm.unit_of_measurement
        FROM statistics s
        JOIN statistics_meta sm ON s.metadata_id = sm.id
        WHERE {where_clauses}
        ORDER BY s.start_ts ASC
    """)

    lines = []
    written = 0
    errors = 0

    for row in cur:
        ts, mean, mn, mx, state, sm, stat_id, unit = row
        if unit is None:
            unit = ""

        measurement = escape_tag(unit) if unit else "state"
        parts = stat_id.split(".", 1)
        domain = parts[0] if len(parts) > 1 else "unknown"
        entity_id = parts[1] if len(parts) > 1 else stat_id

        tags = ",".join([
            f"domain={escape_tag(domain)}",
            f"entity_id={escape_tag(entity_id)}",
            "source=backport"
        ])

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
                if errors <= 5:
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
