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

**The gap:** `podman system prune -f` without `-a` only removes *dangling* (untagged) images. It
handles the auto-update churn perfectly, but **tagged-yet-unused** images accumulate forever. On
2026-07-27 that was 8 stale GitLab CI images totalling ~5 G, the oldest untouched for 13 months
(`cirruslabs/flutter:3.41.0` alone was 4.5 G).

Check for them periodically:

```bash
sudo podman system df                                   # look at RECLAIMABLE
sudo podman ps -a --no-trunc --format '{{.ImageID}}' | sed 's|^sha256:||' | sort -u > /tmp/used
sudo podman images --no-trunc --format $'{{.ID}}\t{{.Repository}}:{{.Tag}}\t{{.Size}}' |
  while IFS=$'\t' read -r id repo size; do
    grep -q "^${id#sha256:}" /tmp/used || printf 'UNUSED  %-12s %s\n' "$size" "$repo"
  done
sudo podman image prune -a -f                            # removes ALL unused, incl. tagged
```

`prune -a` is safe but not free: it evicts GitLab CI base images, so the next pipeline re-pulls
them (a Flutter job means a 4.5 G download). It was **not** added to the weekly timer for that
reason — run it by hand when root gets tight.

> `systemd/units/bumblebee/podman-prune.{service,timer}` is a **stale duplicate** (Apr 2026) that
> specifies `podman image prune -a -f`. The deployed and authoritative copy is
> `systemd/system/bumblebee/` (May 2026, verified byte-identical to the host). Don't deploy the
> `units/` copy — it would silently start evicting CI caches weekly.

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

**2. journald is volatile on this host — rsyslog holds the only persistent history.**
There is no `/var/log/journal`, so journald runs RAM-backed out of `/run/log/journal` and loses
everything on reboot (`journalctl` only ever shows the current boot). That makes
`/var/log/messages` the sole long-term log. **Never just truncate it** — archive first.

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
Post-fix volume is ~3 MB/day.

`podman.service` is socket-activated (`podman.socket` enabled, service disabled), so apply with
`systemctl stop podman.service` — the socket re-activates it on the next request. Traefik logs one
`unexpected EOF` provider error and retries cleanly.

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
