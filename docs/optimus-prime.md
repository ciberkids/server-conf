# Optimus Prime

Main home server running all containerized services.

## Hardware

| Component | Details |
|-----------|---------|
| CPU | AMD Ryzen 5 2600X (6C/12T) |
| RAM | 16 GB |
| OS Disk | 2x Samsung SSD 860 EVO 500GB (RAID1 — md127) |
| Downloads | 2x WD Red 2TB (RAID1 — md126, ~1.9TB) |
| Data | 4x WD Red 4TB (RAID5 — md124, ~11TB) |
| Media | 4x Seagate IronWolf 12TB (RAID5 — md125, ~33TB) |

## Network

- **IP**: 192.168.1.10 (DHCP, static lease from router)
- **Interface**: enp7s0
- **mDNS**: Avahi enabled, restricted to enp7s0 (`allow-interfaces=enp7s0` in `/etc/avahi/avahi-daemon.conf`)

## OS

- Arch Linux (rolling release)
- Kernel: LTS

## Storage Layout

| Mount | RAID | Filesystem | Size | Purpose |
|-------|------|-----------|------|---------|
| `/` | md127 (RAID1) | — | 465 GB | OS + root |
| `/mnt/downloads` | md126 (RAID1) | — | 1.9 TB | Downloads (transmission, amule, etc.) |
| `/mnt/data` | md124 (RAID5) | — | 11 TB | Persistent container data, photos, misc |
| `/mnt/MovieAndTvShows` | md125 (RAID5) | — | 33 TB | Plex media library |

## Services

All services run as Podman containers managed by **systemd quadlets** in `/etc/containers/systemd/`.

### Web UI Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Home Assistant | `home_assistant` | 8123 | Home automation |
| Grafana | `grafana` | 3000 | Monitoring dashboards |
| Node-RED | `node-red` | 1880 | Flow-based automation |
| Plex | `plex` | 32400 | Media server |
| Tautulli | `tautulli` | 8181 | Plex monitoring |
| Sonarr | `sonarr` | 8989 | TV show management |
| Transmission | `transmission` | 9091 | Torrent client |
| Zigbee2MQTT | `zigbee2mqtt` | 8282 | Zigbee bridge UI |
| MQTT Dashboard | `mqtt-dashboard` | 3333 | MQTT monitoring |
| MQTT Explorer | `mqtt-explorer` | 4000 | MQTT browser |
| JDownloader2 | `jdownloader2` | 5800 | Download manager |
| Handbrake | `handbrake` | 6800 | Video transcoder |
| MakeMKV | `makemkv` | 7900 | Disc ripper |
| Pingvin Share | `pingvin-share` | 5000 | File sharing |
| aMule | `amule` | 4711 | P2P client |
| Heimdall | `heimdall` | 8880 | Application dashboard |
| Nextcloud | `nextcloud` | 8443 | File sync & sharing |
| Jellyfin | `jellyfin` | 8096 | Media server |
| Immich | `immich` (pod) | 2283 | Photo management |
| File Browser | `filebrowser` | 8585 | Web file manager |
| Traefik | `traefik` | 80 (http), 443 (https), 8080 (dashboard) | Reverse proxy |
| InfluxDB | `influxdb` | 8086 | Time-series database (HA telemetry) |
| Prometheus | `prometheus` | 9092 | Metrics collection (system monitoring) |

### Backend Services (no web UI)

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Mosquitto MQTT | `mqtt5` | 1883 (MQTT), 9001 (WS) | MQTT broker |
| TimescaleDB | `timescaleDB` | 5432 | Time-series PostgreSQL (HA recorder) |
| Redis | `redis` | 6379 | Cache / message broker |
| RustDesk HBBS | `rustdesk-hbbs` | host network | Remote desktop relay |
| RustDesk HBBR | `rustdesk-hbbr` | host network | Remote desktop relay |
| Node Exporter | `node-exporter` | 9100 | System metrics for Prometheus |
| SMART Exporter | `smartctl-exporter` | 9633 | Disk SMART metrics for Prometheus |

### Non-Container Services

| Service | Port | Description |
|---------|------|-------------|
| Cockpit | 9090 | Server management UI |
| Samba | 445 | File sharing (SMB) |
| NFS | 2049 | File sharing (NFS) |
| SSH | 22 | Remote access |

## Shared Storage (NFS Exports)

Exported to `192.168.1.0/24` with `all_squash,anonuid=1000,anongid=1000`:

| Export | Mode |
|--------|------|
| `/mnt/downloads` | rw |
| `/mnt/data` | rw |
| `/mnt/MovieAndTvShows` | rw |
| `/mnt/data/docker_persistent/immich` | rw |
| `/mnt/data/docker_persistent/nextcloud` | rw |
| `/mnt/data/docker_persistent/volumetest` | rw |
| `/mnt/data/Matteo_And_Manu/Pictures` | ro |
| `/mnt/MovieAndTvShows/Movies` | ro |
| `/mnt/MovieAndTvShows/TvShows` | ro |

Config files:
- `/etc/exports` — main NFS exports
- `/etc/exports.d/cockpit-file-sharing.exports` — Cockpit-managed exports

## Samba Shares

Managed via Cockpit (registry-based config):

| Share | Path | Access |
|-------|------|--------|
| Video | `/mnt/MovieAndTvShows` | rw, user: matteo |
| Downloads | `/mnt/downloads` | rw, user: matteo |
| Data | `/mnt/data` | rw, guest ok |

## Monitoring Stack

### Architecture

```
node_exporter (OP:9100) ──┐
node_exporter (BB:9100) ──┼── Prometheus (OP:9092) ──── Grafana (OP:3000)
smartctl_exporter (OP:9633)┘

Home Assistant ──── InfluxDB (OP:8086) ──── Grafana (OP:3000)
```

### Prometheus Scrape Targets

| Job | Target | Interval | Metrics |
|-----|--------|----------|---------|
| `node-optimusprime` | 192.168.1.10:9100 | 30s | CPU, RAM, disk, network, RAID, filesystem |
| `node-bumblebee` | 192.168.1.14:9100 | 30s | CPU, RAM, disk, network, filesystem |
| `smartctl-optimusprime` | 192.168.1.10:9633 | 120s | SMART health, temperature, reallocated sectors, power-on hours |
| `prometheus` | localhost:9090 | 30s | Prometheus self-monitoring |

Config: `/mnt/data/docker_persistent/prometheus/prometheus.yml`

### InfluxDB Buckets

| Bucket | Source | Retention | Data |
|--------|--------|-----------|------|
| `homeassistant` | Home Assistant `influxdb` integration | Unlimited | All HA entity state changes (temperature, humidity, power, etc.) |
| `prometheus` | Reserved for future use | 90 days | — |

Org: `favarohome`, admin token in quadlet env vars.

### Grafana Dashboards

| Dashboard | Datasource | Description |
|-----------|-----------|-------------|
| Node Exporter Full | Prometheus | Full system metrics for both servers |
| Disk Health & RAID Status | Prometheus | SMART temps, RAID arrays, disk space, I/O |
| Home Assistant Sensors | InfluxDB | Temperature, humidity, power/energy from HA |

## Quadlet Files

All container definitions: `/etc/containers/systemd/*.container`

To manage:
```bash
systemctl daemon-reload          # After editing quadlet files
systemctl restart <name>.service # Restart a container
systemctl status <name>.service  # Check status
journalctl -u <name>.service     # View logs
```
