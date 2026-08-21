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

### Adaptec HBA 1100-8i — physical drive map

`0c:00.0 Serial Attached SCSI controller: Adaptec Smart Storage PQI SAS` — subsystem
**Adaptec HBA 1100-8i**, driver `smartpqi`, Slot 8, mode **HBA** (all drives
`Raw (Pass Through)`, so the RAID is entirely md software RAID).

⚠️ **`arcconf` needs the `sg` kernel module and fails SILENTLY without it.** With `sg`
unloaded, `arcconf LIST` prints `Controllers found: 0` **and exits "Command completed
successfully"** — it locates `/sys/bus/pci/drivers/smartpqi` fine, then dies opening
`/sys/class/scsi_generic/`. This made the controller look unsupported for months. Fixed
2026-08-21 via `/etc/modules-load.d/sg.conf` (`config/modules-load/optimusprime/sg.conf`).
Diagnose with `strace -e trace=openat arcconf LIST | grep scsi_generic`.

| Slot | Connector | Model | Serial | Dev | Array |
|---|---|---|---|---|---|
| 0 | CN0 | WDC WD40EFZX-68AWUN0 | WD-WXA2D911SD7Z | sdf | md124 |
| 1 | CN0 | WDC WD40EFRX-68WT0N0 | WD-WCC4E1605633 | sdg | md124 |
| 2 | CN0 | ST12000VN0007-2GS116 | ZJV224X2 | sdh | md125 |
| 3 | CN0 | ST12000VN0007-2GS116 | ZJV224YN | sdi | md125 |
| 4 | CN1 | WDC WD40EFRX-68WT0N0 | WD-WCC4E1943240 | sdj | md124 |
| 5 | CN1 | WDC WD40EFZX-68AWUN0 | WD-WX32DB00A4Z2 | sdk | md124 |
| 6 | CN1 | ST12000VN0008-3MH101 | WZ003K9F | sdl | md125 |
| 7 | CN1 | ST12000VN0007-2GS116 | ZJV212XF | sdm | md125 |

**Both md arrays are split 2+2 across CN0 and CN1**, so losing one SAS cable degrades
but cannot kill either array. Verified 2026-08-21.

⚠️ **`sdc` (ST3750640NS, 698 GB, serial 5QD12FW2 — the failing disk) is NOT on the HBA.**
Slots 0–7 are all 4 TB/12 TB. sdc, sdd/sde (md126) and sda/sdb (md127) hang off the
motherboard AHCI controllers, so replacing sdc never touches the Adaptec.

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

## Automatic Updates and Reboots

| Unit | When | Does |
|---|---|---|
| `auto-update.timer` | 04:08 daily | `paru -Syu` as `matteo`, `paccache` prune, Telegram digest |
| `kernel-reboot.timer` | **05:00 daily** | reboots **only** if the running kernel ≠ newest installed `-lts` **and** every md array is clean |
| `podman-auto-update-notify.timer` | 04:01 daily | container image digest |

🔑 **The 05:00 reboot is a real scheduled reboot and it is visible in
`systemctl list-timers`.** Until 2026-08-21 it was not: `auto-update.sh` decided at 04:08
and called `shutdown -r 05:00`, so nothing in `list-timers`, cron, or any unit file
mentioned a reboot — the only record was one line inside a shell script. Do not go
looking for a reboot in the wrong places again.

Why the split matters: deciding at 04:08 and acting at 05:00 left a 51-minute window in
which an array could start rebuilding, which is the *only* reason
`mdraid-reboot-guard.timer` existed (it re-checked `/proc/mdstat` every 30 min and ran
`shutdown -c`). `kernel-reboot.service` evaluates both conditions **at** 05:00, so the
window and the guard are both gone — the guard was retired 2026-08-21.

- The check is **stateless** — `uname -r` vs `/usr/lib/modules/*-lts` plus `/proc/mdstat`,
  re-derived at 05:00. Nothing is handed over from the 04:08 run, so there is no flag
  file to go stale.
- ⚠️ It uses **`ExecCondition=`, not `ExecStartPre=`**. Exit 1 marks the unit *skipped*,
  so `OnFailure=notify-failure@` stays quiet on the ~364 days a year with no kernel
  update. With `ExecStartPre` the unit would be marked *failed* and alert every night.
- **Cancelling**: during the 60 s `wall` window, `systemctl stop kernel-reboot.service`
  kills the `sleep` and the remaining `ExecStart=` lines never run. Longer term:
  `systemctl disable --now kernel-reboot.timer`.
- ⚠️ `Persistent=false` is deliberate — a missed 05:00 must never fire a surprise reboot
  at an arbitrary later time.
- 🐛 Fixed at the same time: the kernel-updated branch of `auto-update.sh` built its
  Telegram message and then called `shutdown` **without ever calling `telegram-send`**,
  so "your server is about to reboot" was the one outcome never announced.

⚠️ **`auto-update.service` exits 1 every night** and has done for some time: the AUR
`arcconf` package cannot build because Microchip now returns **403** on the source zip
(EULA gate). The system upgrade itself succeeds — only the AUR build fails. Installed
`arcconf 5.05.00.28200-2` works fine, so the fix is to stop trying to update it
(`IgnorePkg = arcconf`), not to remove it. **Not yet applied.**

## Logging

### Container error-log noise removed 2026-08-20

Two containers accounted for **~21,000 ERROR lines/day between them, representing ZERO faults**.
Both are fixed at source. (The inverse of the usual trap: here a very loud error log meant nothing.
Always dedupe by message signature before believing a count.)

**Home Assistant — ~15,400/day, all four signatures from one device.** The Tuya pool sensor
(`0x70d07efffe432949`, TS0601) reports four **alarm setpoints** outside the ranges z2m declares to
HA, so `homeassistant.components.mqtt.number` rejected and logged *every* publish, ~every 24 s each:

| entity | reported | declared range |
|---|---|---|
| `number.pool_sensor_orp_min` | `-1.0` | 0.0 – 1200.0 |
| `number.pool_sensor_orp_max` | `-1.0` | 0.0 – 1200.0 |
| `number.pool_sensor_free_chlorine_max` | `-1.0` | 0.0 – 40.0 |
| `number.pool_sensor_ph_max` | `1400` | 0.0 – **140.0** |

`-1` is the vendor's "threshold disabled" sentinel; `ph_max` is 10× over a range that is itself
already pH×10. Fixed with z2m per-device **`filtered_attributes`** (confirmed present in z2m 2.13's
`settings.schema.json`; applied in `controller.js` via `utils.filterProperties` at publish time, so
the keys never reach HA at all):

```yaml
devices:
  '0x70d07efffe432949':
    friendly_name: Pool sensor
    filtered_attributes:
      - ^orp_min$
      - ^orp_max$
      - ^free_chlorine_max$
      - ^ph_max$
```

- **Regexes must be anchored.** Unanchored `orp_max` is harmless but `ph`/`orp`/`free_chlorine`
  substrings are not — anchoring is what keeps the real *measurements* and the in-range setpoints
  (`ph_min`, `free_chlorine_min`, `ec_min`, `ec_max`) publishing normally.
- **No functional loss:** HA discarded every one of these values already, so the entities had no
  usable state before or after.
- Requires a `zigbee2mqtt.service` restart (~5 s, rejoins all 60 devices).
- ⚠️ **`configuration.yaml` is NOT in git** — it holds the MQTT broker password in plaintext, so
  committing it would repeat the April 2026 key leak. Back up on the host instead; a timestamped
  `configuration.yaml.bak-filterattrs-*` was left beside it.
- Verified: last pool error 06:19:28, z2m restarted 06:23, **0 pool errors and 0 total HA ERROR
  lines afterwards**, while `ph=7.6 orp=-49 salinity=4130 tds=4068` kept arriving.

**Firefly III — ~5,671/day, entirely self-inflicted by our own monitoring.** Firefly logs every
*anonymous* page view as `production.ERROR: Unauthenticated.`, and two callers hit `/` every 30 s:
the blackbox uptime probe and the container's own healthcheck. `/login` returns 200 and logs at
INFO only (verified). **Both** were retargeted — fixing one would only have halved it:

- `firefly-iii.container`: `HealthCmd=... curl -sf -o /dev/null http://localhost:8080/login`
- `config/prometheus/prometheus.yml`: target is now `https://firefly.optimusprime.favarohome.com/login`

⚠️ Changing a blackbox target changes its `instance` label, so the old series lingers for
Prometheus' ~5-minute staleness window and `count(probe_success)` reads one high. Check
`/api/v1/targets?state=active` — that is authoritative — rather than trusting the series count.
The `ServiceDown` rule is generic (`probe_success == 0`) so it is unaffected.


### podman API access log silenced 2026-08-19

`podman.service` was logging **every** REST API request at the packaged `--log-level=info`, and
Traefik's container-discovery provider polls that API continuously. Measured before the fix:

```
journal entries, 1 h sample:   253,734   =>  6.1 M/day
   of which podman.service:    239,158   =>  5.7 M/day  =  94% of the entire journal
```

Fixed with `/etc/systemd/system/podman.service.d/log-level.conf`
(git: `systemd/system/optimusprime/podman-log-level.conf`) setting
`Environment=LOGGING="--log-level=warn"`. Verified: last access line 11:44:30, podman restarted
11:44:37, **0 access lines afterwards**.

This is the same fault that produced bumblebee's 17 G `/var/log/messages` in July 2026 — see
[bumblebee.md](bumblebee.md#logging-read-this-before-debugging-a-full-root-filesystem). It was fixed
there on 2026-07-27 and **not** on OP until now.

**It was never a disk risk here.** Arch runs no rsyslog, so everything went to journald, which
self-caps at the default `SystemMaxUse` of ~4 G. The actual costs were:

- **Journal retention squeezed to ~23 days.** Retention here is `4 G ÷ daily volume`, *not* a
  configured time window — `journald.conf` is all defaults. With the noise gone the same 4 G should
  hold roughly a year. That window is what nearly lost the Aug 13 coordinator-wedge evidence.
- `journalctl --since "24 hours ago"` **timed out after 2 minutes** at ~70 entries/second, which made
  log analysis on this host effectively impractical.

⚠️ **Applying or reverting this requires restarting Traefik afterwards.** Cycling `podman.service`
kills Traefik's event stream: it keeps serving its existing routing table so everything *looks* fine,
but it stops learning about container changes and a later container restart 502s. **Router count is
not a valid check** — verify by probing the routed hostnames end-to-end. (After this change all 53
were swept: 0 failures, 0 backends left on `10.89.x`.)

`podman.service` on OP is **socket-activated** (`podman.socket` enabled+active, `podman.service`
disabled), so `systemctl stop podman.service` is safe — the next API request restarts it with the new
environment. Confirm the running process actually picked it up, since the configured `Environment=`
property updates immediately while the old process keeps running:

```bash
ps -eo pid,cmd | grep "podman system service"   # want: podman --log-level=warn system service
```

⚠️ There is **no ansible coverage for Optimus Prime** — `ansible/setup-workstation.yml` targets
bumblebee only. This drop-in must be re-deployed by hand from git if the host is rebuilt.

## Quadlet Files

All container definitions: `/etc/containers/systemd/*.container`

To manage:
```bash
systemctl daemon-reload          # After editing quadlet files
systemctl restart <name>.service # Restart a container
systemctl status <name>.service  # Check status
journalctl -u <name>.service     # View logs
```
