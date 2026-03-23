#!/usr/bin/env python3
import json, urllib.request

years = [
    {"year": "2026", "start": "2026-01-01T00:00:00Z", "stop": "2027-01-01T00:00:00Z", "color": "green"},
    {"year": "2025", "start": "2025-01-01T00:00:00Z", "stop": "2026-01-01T00:00:00Z", "color": "yellow"},
    {"year": "2024", "start": "2024-01-01T00:00:00Z", "stop": "2025-01-01T00:00:00Z", "color": "blue"},
]

panels = []
pid = 1

# Row 1: Monthly kWh production per year (3 side-by-side)
for i, y in enumerate(years):
    q = (
        'from(bucket: "homeassistant")\n'
        '  |> range(start: ' + y["start"] + ', stop: ' + y["stop"] + ')\n'
        '  |> filter(fn: (r) => r.entity_id == "solar_production_total_day_kwh" and (r._field == "value" or r._field == "max"))\n'
        '  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)\n'
        '  |> aggregateWindow(every: 1mo, fn: sum, createEmpty: true)'
    )
    panels.append({
        "id": pid, "title": "Monthly Production " + y["year"] + " (kWh)",
        "type": "barchart",
        "gridPos": {"h": 10, "w": 8, "x": i*8, "y": 0},
        "datasource": {"type": "influxdb", "uid": "dfgw1f6k9yjggc"},
        "targets": [{"refId": "A", "query": q}],
        "fieldConfig": {"defaults": {"unit": "kwatth", "decimals": 0, "color": {"mode": "fixed", "fixedColor": y["color"]}}},
        "options": {"barWidth": 0.7, "showValue": "always", "xTickLabelRotation": -45}
    })
    pid += 1

# Row 2: Monthly peak instant power per year (kW, 3 side-by-side)
for i, y in enumerate(years):
    q = (
        'from(bucket: "homeassistant")\n'
        '  |> range(start: ' + y["start"] + ', stop: ' + y["stop"] + ')\n'
        '  |> filter(fn: (r) => r.entity_id == "solar_production_instant" and (r._field == "value" or r._field == "max"))\n'
        '  |> aggregateWindow(every: 1mo, fn: max, createEmpty: true)\n'
        '  |> map(fn: (r) => ({r with _value: r._value / 1000.0}))'
    )
    panels.append({
        "id": pid, "title": "Monthly Peak Power " + y["year"] + " (kW)",
        "type": "barchart",
        "gridPos": {"h": 10, "w": 8, "x": i*8, "y": 10},
        "datasource": {"type": "influxdb", "uid": "dfgw1f6k9yjggc"},
        "targets": [{"refId": "A", "query": q}],
        "fieldConfig": {"defaults": {"unit": "kwatt", "decimals": 2, "color": {"mode": "fixed", "fixedColor": y["color"]}, "max": 7}},
        "options": {"barWidth": 0.7, "showValue": "always", "xTickLabelRotation": -45}
    })
    pid += 1

# Row 3: Daily production last 12 months
panels.append({
    "id": pid, "title": "Daily Production (last 12 months)",
    "type": "timeseries",
    "gridPos": {"h": 8, "w": 24, "x": 0, "y": 20},
    "datasource": {"type": "influxdb", "uid": "dfgw1f6k9yjggc"},
    "targets": [{"refId": "A", "query": 'from(bucket: "homeassistant")\n  |> range(start: -365d)\n  |> filter(fn: (r) => r.entity_id == "solar_production_total_day_kwh" and (r._field == "value" or r._field == "max"))\n  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)'}],
    "fieldConfig": {"defaults": {"unit": "kwatth", "color": {"mode": "continuous-YlRd"}, "custom": {"drawStyle": "bars", "fillOpacity": 80, "lineWidth": 0}}}
})
pid += 1

# Row 4: Annual totals
annual_targets = []
for ref, y in zip(["A","B","C"], years):
    q = (
        'from(bucket: "homeassistant")\n'
        '  |> range(start: ' + y["start"] + ', stop: ' + y["stop"] + ')\n'
        '  |> filter(fn: (r) => r.entity_id == "solar_production_total_day_kwh" and (r._field == "value" or r._field == "max"))\n'
        '  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)\n'
        '  |> sum()\n'
        '  |> set(key: "_field", value: "' + y["year"] + '")'
    )
    annual_targets.append({"refId": ref, "query": q})

panels.append({
    "id": pid, "title": "Annual Totals",
    "type": "stat",
    "gridPos": {"h": 5, "w": 24, "x": 0, "y": 28},
    "datasource": {"type": "influxdb", "uid": "dfgw1f6k9yjggc"},
    "targets": annual_targets,
    "fieldConfig": {"defaults": {"unit": "kwatth", "decimals": 0}, "overrides": [
        {"matcher": {"id": "byName", "options": "2024"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "blue"}}]},
        {"matcher": {"id": "byName", "options": "2025"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "yellow"}}]},
        {"matcher": {"id": "byName", "options": "2026"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}}]},
    ]}
})

d = {
    "dashboard": {
        "id": None, "uid": "004f9e5c-429b-4494-ba14-776fc3084113",
        "title": "Solar Production - Year over Year",
        "tags": ["energy", "solar", "historical"],
        "timezone": "browser", "refresh": "",
        "time": {"from": "now-3y", "to": "now"},
        "panels": panels
    },
    "overwrite": True
}

data = json.dumps(d).encode()
req = urllib.request.Request(
    "http://localhost:3000/api/dashboards/db",
    data=data,
    headers={"Content-Type": "application/json", "Authorization": "Basic YWRtaW46YWRtaW4="},
    method="POST"
)
resp = urllib.request.urlopen(req)
r = json.loads(resp.read())
print(r["status"], r.get("url",""))
