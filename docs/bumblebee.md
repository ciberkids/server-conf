# Bumblebee

Secondary workstation with GPU compute capability.

## Hardware

| Component | Details |
|-----------|---------|
| CPU | Intel Core i7-8700K (6C/12T @ 3.70GHz) |
| RAM | 16 GB |
| GPU | NVIDIA GeForce GTX 1080 Ti (11 GB VRAM) |
| OS Disk | Samsung SSD 960 EVO 500GB (NVMe) |

## Network

- **IP**: 192.168.1.14 (DHCP, static lease from router)
- **Interface**: eno1

## OS

- AlmaLinux 9.4 (Seafoam Ocelot)
- Kernel: 5.14.0-611.x (RHEL 9 series)

## Storage Layout

| Mount | Device | Filesystem | Size | Purpose |
|-------|--------|-----------|------|---------|
| `/` | almalinux_bumblebee-root | xfs | 70 G | Root — **the tight one**; holds `/var/lib/containers` (~37 G of images) |
| `/boot` | UUID partition | xfs | 960 M | Boot |
| `/boot/efi` | UUID partition | vfat | 599 M | EFI |
| `/home` | almalinux_bumblebee-home | xfs | 386 G | Home — lots of headroom (~335 G free) |
| swap | almalinux_bumblebee-swap | swap | 7.84 G | LV exists but **not active** (commented out in `/etc/fstab`) |

Root is the only constrained filesystem. If it tightens again there is an escape hatch —
the VG has the inactive 7.84 G swap LV, and `/home` is oversized relative to use. XFS grows
online, so root can be extended without downtime:

```bash
sudo lvextend -L +10G /dev/almalinux_bumblebee/root
sudo xfs_growfs /                     # xfs can only grow, never shrink
```

Reclaiming space from `/home` first requires shrinking it — and **XFS cannot shrink**, so that
path means backup + recreate. Prefer taking the free VG extents or the swap LV.

### Container image growth (and what the weekly prune does *not* catch)

`/var/lib/containers` is the largest consumer on root (~37 G for 21 active images). Two jobs run
nightly and interact:

| Timer | When | What |
|-------|------|------|
| `podman-auto-update-notify.timer` | 00:07 | pulls new images (`AutoUpdate=registry`), orphaning the old ones |
| `podman-prune.timer` | 00:11 (weekly) | `podman system prune -f` — reclaims those orphans (~8 G/week) |

**The gap that existed until 2026-07-27:** `podman system prune -f` without `-a` only removes
*dangling* (untagged) images. It handles the auto-update churn perfectly, but
**tagged-yet-unused** images accumulated forever — 8 stale GitLab CI images totalling ~5 G, the
oldest untouched for 13 months (`cirruslabs/flutter:3.41.0` alone was 4.5 G).

Closed by adding a **second, monthly** timer rather than making the weekly one aggressive:

| Timer | When | Command | Removes |
|-------|------|---------|---------|
| `podman-prune.timer` | weekly | `podman system prune -f` | dangling images, stopped containers, unused networks |
| `podman-image-prune.timer` | monthly, `*-*-01 02:30` | `podman image prune -a -f` | **tagged-but-unused** images |

Monthly, not weekly, because `-a` evicts GitLab CI base images and the next pipeline re-pulls
them — a Flutter job means a 4.5 G download. Monthly bounds accumulation to ~1 month while
making that an occasional cost. Nothing is at risk either way: images are re-pullable, no data
is involved. The 02:30 slot is deliberate — clear of the 00:07 auto-update and 00:11 weekly
prune, so a deep prune never races a pull.

> #### Do NOT "soften" the deep prune with `--filter until=<age>`
>
> It looks like a safety net that would spare recently-used caches. It is not. `until` matches
> the image's **upstream build timestamp from its metadata**, not when you pulled it or last
> used it. **Verified 2026-07-27:** a freshly pulled `alpine:latest` — pulled seconds earlier,
> but built 5 weeks prior — was immediately deleted by `--filter until=720h`. Meanwhile
> `python:3-alpine` reports `Created=2026-06-16`, i.e. Docker Hub's build date.
>
> Podman tracks **no last-used time for images at all**, so cadence is the only honest lever.

To audit unused images by hand (note `{{.Size}}` emits two whitespace-separated fields, so this
needs tab delimiters — a naive `read id repo size` silently reports everything as unused):

```bash
sudo podman system df                                   # look at RECLAIMABLE
sudo podman ps -a --no-trunc --format '{{.ImageID}}' | sed 's|^sha256:||' | sort -u > /tmp/used
sudo podman images --no-trunc --format $'{{.ID}}\t{{.Repository}}:{{.Tag}}\t{{.Size}}' |
  while IFS=$'\t' read -r id repo size; do
    grep -q "^${id#sha256:}" /tmp/used || printf 'UNUSED  %-12s %s\n' "$size" "$repo"
  done
```

## NFS Mounts (from Optimus Prime)

All mounts use `defaults,_netdev` and are in `/etc/fstab`.

| Remote | Local | Options |
|--------|-------|---------|
| `192.168.1.10:/mnt/downloads` | `/mnt/downloads` | rw |
| `192.168.1.10:/mnt/data` | `/mnt/data` | rw |
| `192.168.1.10:/mnt/MovieAndTvShows` | `/mnt/MovieAndTvShows` | rw |
| `192.168.1.10:/mnt/MovieAndTvShows/Movies` | `/mnt/MovieAndTvShows/Movies` | ro |
| `192.168.1.10:/mnt/MovieAndTvShows/TvShows` | `/mnt/MovieAndTvShows/TvShows` | ro |
| `192.168.1.10:/mnt/data/docker_persistent/immich` | `/mnt/data/docker_persistent/immich` | rw |
| `192.168.1.10:/mnt/data/docker_persistent/nextcloud` | `/mnt/data/docker_persistent/nextcloud` | rw |
| `192.168.1.10:/mnt/data/docker_persistent/volumetest` | `/mnt/data/docker_persistent/volumetest` | rw |
| `192.168.1.10:/mnt/data/Matteo_And_Manu/Pictures` | `/mnt/data/Matteo_And_Manu/Pictures` | ro |

## NVIDIA Driver

- Driver: **580.126.20** (legacy branch for GTX 1080 Ti)
- CUDA: 13.0
- Installed via: `dnf module install nvidia-driver:580-dkms`
- DKMS auto-rebuilds on kernel updates

## Installed Software

### System Tools
- podman
- samba, samba-client
- nfs-utils
- policycoreutils-python-utils (semanage)
- rsyslog, **rsyslog-logrotate** (the second one is a separate package on EL9 and is
  mandatory — without it `/var/log/messages` never rotates; see [Logging](#logging-read-this-before-debugging-a-full-root-filesystem))
- pigz (parallel gzip — used for log archiving)
- fastfetch (enabled for all users via `/etc/profile.d/fastfetch.sh`)
- btop
- nvtop

### Cockpit (port 9090)
- cockpit
- cockpit-podman
- cockpit-storaged
- cockpit-networkmanager
- cockpit-packagekit

## Services

All services run as Podman containers managed by **systemd quadlets** in `/etc/containers/systemd/`.
Persistent data is stored in `/home/matteo/docker_persistent/`.
OpenClaw workspace is at `/home/matteo/openclaw-workspace/` (mount symlinks to project directories as needed).

### Web UI Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Open WebUI | `open-webui` | 3000 | ChatGPT-like interface for Ollama |
| OpenClaw | `openclaw` | 18789 | AI agent platform (Claude Sonnet via Anthropic API) |
| OpenCode | `opencode` | 4096 | AI coding assistant |
| n8n | `n8n` | 5678 | Workflow automation |
| Heimdall | `heimdall` | 8880 | Application dashboard |
| ComfyUI | `comfyui` | 8188 | Image generation (FLUX) |
| Traefik | `traefik` | 80 (http), 443 (https), 8080 (dashboard) | Reverse proxy |

### Backend Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Ollama | `ollama` | 11434 | Local LLM server (GPU-accelerated) |
| Node Exporter | `node-exporter` | 9100 | System metrics (scraped by Prometheus on Optimus Prime) |

### Non-Container Services

| Service | Port | Description |
|---------|------|-------------|
| Cockpit | 9090 | Server management UI |

## Logging (read this before debugging a full root filesystem)

Two traps here bit us on 2026-07-27, when `/var/log/messages` had grown to **17 G** and root
hit 90%.

**1. `rsyslog-logrotate` is a separate package on EL9 — and it was missing.**
Older RHEL shipped `/etc/logrotate.d/rsyslog` inside the `rsyslog` package. EL9 split it into
`rsyslog-logrotate`. Without it, logrotate runs daily, exits 0, and rotates **nothing** —
`/var/log/messages` grew unrotated for 97 days. `rpm -V rsyslog` comes back clean because the
missing file was never owned by that package, so nothing flags it.

```bash
rpm -q rsyslog-logrotate            # MUST be installed
cat /etc/logrotate.d/rsyslog        # must exist; covers cron/maillog/messages/secure/spooler
sudo logrotate -d /etc/logrotate.d/rsyslog   # dry run — confirms the files are considered
```

**2. journald was volatile — FIXED 2026-07-27, but read the rsyslog trap below.**
There was no `/var/log/journal`, so journald ran RAM-backed out of `/run/log/journal` and lost
everything on reboot (`journalctl` only ever showed the current boot). That made
`/var/log/messages` the sole long-term log — which is how a 17 G file went unnoticed.

Now persistent via `systemd/system/bumblebee/journald-persistent.conf` →
`/etc/systemd/journald.conf.d/persistent.conf`:

```
Storage=persistent      SystemMaxUse=2G       SystemKeepFree=2G
Compress=yes            SystemMaxFileSize=128M   MaxRetentionSec=3month
```

The caps are the point: journald defaults `SystemMaxUse` to **10% of the filesystem**, which is
~7 G on this 70 G root. Note that persistence is really triggered by the *existence* of
`/var/log/journal` (with `Storage=auto`, the default) — `Storage=persistent` is set explicitly
so it does not silently depend on a directory. Create that directory with
`systemd-tmpfiles --create --prefix /var/log/journal`, not bare `mkdir`, because journald needs
setgid + `systemd-journal` group ACLs for non-root reads.

> ### ⚠️ Restarting journald silently kills rsyslog
>
> On EL9, rsyslog does **not** read `/dev/log` for system messages — it pulls them from
> journald via the `imjournal` module, tracking its position in
> `/var/lib/rsyslog/imjournal.state`. Restart journald and that cursor goes stale: rsyslog
> logs a cheerful `imjournal: journal files changed, reloading...` and then writes **nothing
> further**, while remaining `active` with exit 0. `/var/log/messages` just flatlines.
>
> Observed live on 2026-07-27 while switching journald to persistent — `/var/log/messages`
> stopped dead at the exact second journald restarted. Fixed by `systemctl restart rsyslog`.
>
> Guarded permanently by `systemd/system/bumblebee/rsyslog-follow-journald.conf` →
> `/etc/systemd/system/rsyslog.service.d/follow-journald.conf`, which sets
> `PartOf=systemd-journald.service` so systemd restarts rsyslog whenever journald restarts.
> **Verified** by restarting journald and confirming rsyslogd got a new PID and logging
> continued. If you ever see `/var/log/messages` stop while journald is fine, check this first.

Both logs now persist, which is deliberately redundant — journald (2 G cap) and rsyslog
(~91 MB/week, compressed on rotation). Total well under 3 G. `/var/log/messages` could be
slimmed now that journald survives reboots, but it is kept because existing tooling and
runbooks grep it.

**Never just truncate `/var/log/messages`** — archive first (procedure below).

To reclaim it safely (rsyslog holds the fd, so the order matters):

```bash
sudo pigz -c /var/log/messages > /home/matteo/logarchive/messages-<range>.gz
pigz -dc /home/matteo/logarchive/messages-<range>.gz | wc -l   # verify CRC before destroying
sudo truncate -s 0 /var/log/messages
sudo systemctl kill -s HUP rsyslog.service   # REQUIRED: reopens at offset 0
```

Skipping the HUP leaves rsyslog writing at its old offset, producing a **sparse** file that
reports 17 G in `ls -l` forever. Verify with `df -h /` **and** `du -sh /var/log/messages`.

Log volume compresses ~25x (17.5 G → 655 M). Archives live in `/home/matteo/logarchive/`
(deliberately on `/home`, not root).

**3. The podman API access log was 92% of the volume.**
Traefik's container-discovery provider polls the podman REST API at ~9.5 req/s, and the packaged
`podman.service` runs `--log-level=info`, which logs every single request to syslog — ~180 MB/day.
Fixed with a drop-in (`systemd/system/bumblebee/podman-log-level.conf` →
`/etc/systemd/system/podman.service.d/log-level.conf`) setting `--log-level=warn`.

`podman.service` is socket-activated (`podman.socket` enabled, service disabled), so apply with
`systemctl stop podman.service` — the socket re-activates it on the next request.

> ### ⚠️ After cycling podman.service, RESTART TRAEFIK
>
> Traefik discovers containers through the podman compat API and watches its **event stream**.
> Cycling `podman.service` kills that stream. Traefik logs one `unexpected EOF`, reconnects, and
> **keeps serving its existing routing table** — but it has stopped learning about container
> changes. Every container restarted afterwards gets a new IP that Traefik never sees, and its
> backend goes stale. Result: **502 Bad Gateway**, while the container is perfectly healthy.
>
> Hit exactly this on 2026-07-27: podman cycled at 10:19, then frigate and filebrowser were
> restarted at ~10:47–11:21. Traefik still pointed at `frigate → 10.88.0.9` when the container had
> moved to `10.88.0.27`. Fixed by `systemctl restart traefik.service`.
>
> **Checking "traefik still knows 18 routers" is NOT sufficient** — the router *count* stays
> correct while the backend *IPs* rot. That check was made and passed while the fault was already
> present. Verify the actual backend IPs against the containers:
>
> ```bash
> sudo podman exec traefik wget -qO- http://localhost:8080/api/http/services |
>   python3 -c 'import json,sys,re
> for s in json.load(sys.stdin):
>     for sv in (s.get("loadBalancer") or {}).get("servers") or []:
>         print(s["name"], sv["url"])'
> # compare against:
> for c in $(sudo podman ps --format '{{.Names}}'); do
>   echo "$c $(sudo podman inspect $c --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}')"
> done
> ```
>
> Or just end any session that cycled podman with a Traefik restart and an end-to-end HTTP sweep
> of the routed hostnames — note the hostname is **not** always the service name
> (searxng is routed as `search.bumblebee.favarohome.com`).

### Current log volume

All measured on this host, 2026-07-27:

| | Rate | Dominant source |
|---|---|---|
| Before (Apr–Jul 2026) | ~180 MB/day | podman REST API access log (Traefik polling), 92% |
| After the podman drop-in | ~37 MB/day | podman container `health_status` events, 85% |
| After the healthcheck fix | **~13 MB/day** | ordinary system chatter |

Silencing Traefik's polling did not make the log quiet — it promoted the next-noisiest source.

**The `health_status` mechanism, because it is not obvious:** podman writes a syslog line on
**every healthcheck run**, not only when health *changes* (this differs from docker). Each line
is ~330 characters. So a 5-second interval costs 17,280 lines/day from a single container.

Four containers were polling aggressively — three of them pointlessly:

| Container | Was | Now | Where the interval came from |
|---|---|---|---|
| `paperless-db` | 5s | 30s | quadlet `HealthInterval=` (upstream compose default) |
| `filebrowser` | 5s | 30s | the **image's own `HEALTHCHECK`** — needed a quadlet override to add |
| `paperless-broker` | 10s | 30s | quadlet `HealthInterval=` |
| `paperless` | 30s | 30s | unchanged, already sane |

That is 32 → 8 health events/min. Raising them was risk-free because **nothing consumed the
fast signal**: none of the three has `Notify=` (so systemd readiness is not gated on health)
or `HealthOnFailure=` (so nothing restarts on it). The check only set an informational label.
Worst-case failure detection is now `HealthRetries × HealthInterval` = 150s.

`prometheus-podman-exporter` does scrape health status, so its view can now be up to 30s
stale — irrelevant for dashboards, worth knowing if you ever alert on it.

Retention is bounded by three directives changed in `/etc/logrotate.conf` on 2026-07-27
(also applied by the playbook, backup at `/etc/logrotate.conf.bak-20260727`):

```
compress          # ~25x on this data — measured 17.5 G -> 655 M
maxsize 500M      # rotate early if a log blows past this inside the weekly window
rotate 12         # was 4 — see the trade-off below
```

These must sit **before** the `include /etc/logrotate.d` line — global options only apply to
includes that follow them. Effective config:
`weekly / rotate 12 / create / dateext / compress / maxsize 500M`.

**The `maxsize` trade-off, stated plainly:** `maxsize` is not free upside. `rotate` bounds how
many rotations are kept, so when `maxsize` fires early under a spike you keep N *spike-length*
windows instead of N weeks — with the stock `rotate 4` that could mean only a few days of
history, in precisely the incident you'd want logs for. Since journald here is volatile, that
history loss is unrecoverable. `rotate` was raised 4 → 12 to compensate; compression makes the
depth cheap:

| Scenario | Active file | Retained history | Total |
|---|---|---|---|
| Normal (41 MB/day) | ~287 MB/week | 12 × ~11 MB | ~430 MB |
| Spike (maxsize fires) | ≤ 500 MB | 12 × ~20 MB | ~740 MB |

Both are comfortable against ~29 G free. If you ever prefer a hard size ceiling over history
depth, lower `rotate` — but know that you are trading away the only persistent log on this host.

**Verified working 2026-07-27** via `logrotate -f`: rotated 506 K → 36 K `.gz`, `gzip -t` passed
with all lines intact, and a `logger` marker landed in the freshly created file — confirming the
`sharedscripts` postrotate HUP wins the race against compression.

### Installed Models (Ollama)

| Model | Size | Purpose |
|-------|------|---------|
| qwen2.5-coder:7b | 4.7 GB | Coding tasks |
| llama3.1:8b | 4.7 GB | General purpose |

## SSH Keys

SSH keys copied from `/mnt/downloads/ssh/optimus-prime/`:
- `/home/matteo/.ssh/id_rsa` — private key (shared with optimus prime)
- `/home/matteo/.ssh/id_rsa.pub` — public key
- `/home/matteo/.ssh/authorized_keys` — allows incoming SSH with same key

## Provisioning

Bumblebee can be fully provisioned from scratch using the Ansible playbook:

```bash
ansible-playbook -i ansible/inventory.ini ansible/setup-workstation.yml --ask-become-pass
```

See `ansible/setup-workstation.yml` for the full automation.

## GitLab CI storage (2026-08-26)

CI runs via the **Docker executor pointed at the host's podman socket**
(`/run/podman/podman.sock` → `/var/run/docker.sock` in the runner quadlet). That matters: job
images and volumes are created by the **host** podman, so they land in
`/var/lib/containers/storage` on the **70 GiB root LV** alongside every production container.
A single job image pull is therefore an outage risk — this is what took the host down on
2026-08-21 (`ghcr.io/cirruslabs/flutter:3.41.0`, 4.5 GB).

**Done:**
- **Job cache moved to `/home`** — `volumes = ["/home/matteo/gitlab-runner-cache:/cache:z"]`
  in `config.toml` (was the anonymous `/cache`). `:z` because every job container mounts it and
  SELinux is enforcing; the directory carries `container_file_t`.
  ⚠️ **`config.toml` is NOT in git — it contains the runner token.** Backups are kept in place
  as `config.toml.bak-<timestamp>`.
- **Daily prune** (`podman-prune.timer`, `OnCalendar=*-*-* 06:00:00`) plus **name-matched
  removal of `runner-*-cache-*` volumes**. Deliberately not a blanket `podman volume prune`.

**Still open — the actual fix:** podman's `graphroot` is still `/var/lib/containers/storage`
on `/`. Moving it to `/home` (346 GiB free) is the only change that stops a job image pull from
being able to fill the root. ⚠️ Requires stopping every container on the host, relocating ~50 GB,
and an SELinux relabel — a real maintenance window. ⛔ `lvextend` is NOT an alternative: the VG
has **0 free extents** and XFS cannot shrink, so /home's space cannot be given to root.

⚠️ **Latent:** the runner's configured default job image `localhost/android-sdk:latest` **does
not exist on the host**, and with `pull_policy = ["if-not-present"]` a `localhost/` ref cannot be
pulled. Jobs that set their own `image:` are unaffected (recent ones use
`ghcr.io/cirruslabs/flutter`). Most likely collateral from the 2026-08-01 `podman image prune -a`
that also destroyed `hermes-agent` — that one was rebuilt, this one never was.
