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
| `/` | almalinux_bumblebee-root | xfs | — | Root |
| `/boot` | UUID partition | xfs | — | Boot |
| `/boot/efi` | UUID partition | vfat | — | EFI |
| `/home` | almalinux_bumblebee-home | xfs | — | Home |
| swap | almalinux_bumblebee-swap | swap | — | Swap |

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
