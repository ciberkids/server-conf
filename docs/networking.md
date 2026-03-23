# Networking & DNS

## Network Topology

```
Internet
    │
    ▼
┌──────────────┐
│   Router     │  192.168.1.1
│  DNS + DHCP  │  Domain: localdomain
└──────┬───────┘
       │  192.168.1.0/24
       ├──────────────────── Optimus Prime  192.168.1.10
       ├──────────────────── Bumblebee      192.168.1.14
       └──────────────────── Other devices
```

## DNS Resolution

There are three layers of name resolution:

### 1. Router DNS (localdomain)
- The router (192.168.1.1) provides DNS for all DHCP clients
- Search domain: `localdomain`
- `optimusprime` resolves via `optimusprime.localdomain`
- `bumblebee` resolves via `bumblebee.localdomain`
- Short names work because `search localdomain` is set in resolv.conf

### 2. mDNS / Avahi (.local)
- Optimus prime runs Avahi, announcing `optimusprime.local`
- Avahi is restricted to `enp7s0` only (`allow-interfaces=enp7s0` in `/etc/avahi/avahi-daemon.conf`) to avoid interference from container veth interfaces
- Used by Dolphin/KDE for automatic network browsing and SMB discovery
- Fedora workstations need `MulticastDNS=yes` in systemd-resolved (`/etc/systemd/resolved.conf.d/mdns.conf`)

### 3. Cloudflare DNS (favarohome.com)
- Domain: `favarohome.com` managed by Cloudflare
- Used for HTTPS certificates via Let's Encrypt DNS-01 challenge
- Internal DNS records point to LAN IPs (not publicly routable)

## Domain Naming Convention

```
<service>.<host>.favarohome.com        — internal (LAN only)
<service>.public.favarohome.com        — external (internet-facing, via Traefik on port 443)
```

### Optimus Prime Services (`*.optimusprime.favarohome.com`)

| FQDN | Target | Port |
|------|--------|------|
| `homeassistant.optimusprime.favarohome.com` | 192.168.1.10 | 8123 |
| `grafana.optimusprime.favarohome.com` | 192.168.1.10 | 3000 |
| `nodered.optimusprime.favarohome.com` | 192.168.1.10 | 1880 |
| `plex.optimusprime.favarohome.com` | 192.168.1.10 | 32400 |
| `tautulli.optimusprime.favarohome.com` | 192.168.1.10 | 8181 |
| `sonarr.optimusprime.favarohome.com` | 192.168.1.10 | 8989 |
| `transmission.optimusprime.favarohome.com` | 192.168.1.10 | 9091 |
| `zigbee2mqtt.optimusprime.favarohome.com` | 192.168.1.10 | 8282 |
| `mqtt-dashboard.optimusprime.favarohome.com` | 192.168.1.10 | 3333 |
| `mqtt-explorer.optimusprime.favarohome.com` | 192.168.1.10 | 4000 |
| `jdownloader.optimusprime.favarohome.com` | 192.168.1.10 | 5800 |
| `handbrake.optimusprime.favarohome.com` | 192.168.1.10 | 6800 |
| `makemkv.optimusprime.favarohome.com` | 192.168.1.10 | 7900 |
| `pingvin.optimusprime.favarohome.com` | 192.168.1.10 | 5000 |
| `amule.optimusprime.favarohome.com` | 192.168.1.10 | 4711 |
| `heimdall.optimusprime.favarohome.com` | 192.168.1.10 | 8880 |
| `nextcloud.optimusprime.favarohome.com` | 192.168.1.10 | 8443 |
| `jellyfin.optimusprime.favarohome.com` | 192.168.1.10 | 8096 |
| `immich.optimusprime.favarohome.com` | 192.168.1.10 | 2283 |
| `filebrowser.optimusprime.favarohome.com` | 192.168.1.10 | 8585 |
| `traefik.optimusprime.favarohome.com` | 192.168.1.10 | 8080 |
| `cockpit.optimusprime.favarohome.com` | 192.168.1.10 | 9090 |
| `influxdb.optimusprime.favarohome.com` | 192.168.1.10 | 8086 |
| `prometheus.optimusprime.favarohome.com` | 192.168.1.10 | 9092 |

### Bumblebee Services (`*.bumblebee.favarohome.com`)

| FQDN | Target | Port |
|------|--------|------|
| `chat.bumblebee.favarohome.com` | 192.168.1.14 | 3000 |
| `openclaw.bumblebee.favarohome.com` | 192.168.1.14 | 18789 |
| `opencode.bumblebee.favarohome.com` | 192.168.1.14 | 4096 |
| `n8n.bumblebee.favarohome.com` | 192.168.1.14 | 5678 |
| `ollama.bumblebee.favarohome.com` | 192.168.1.14 | 11434 |
| `heimdall.bumblebee.favarohome.com` | 192.168.1.14 | 8880 |
| `comfyui.bumblebee.favarohome.com` | 192.168.1.14 | 8188 |
| `traefik.bumblebee.favarohome.com` | 192.168.1.14 | 8080 |
| `cockpit.bumblebee.favarohome.com` | 192.168.1.14 | 9090 |

## HTTPS Setup

### Architecture

```
Browser ──HTTPS──▶ Traefik (443) ──HTTP──▶ Container (internal port)
                      │
                      ├── Let's Encrypt cert via Cloudflare DNS-01
                      └── Auto-renewal
```

### Traefik + Let's Encrypt + Cloudflare

Traefik acts as the TLS termination point for all services on optimus prime:

1. **Cloudflare API token** — scoped to DNS edit for `favarohome.com` zone, stored in the Traefik quadlet as `CF_DNS_API_TOKEN`
2. **DNS-01 challenge** — Traefik proves domain ownership by creating TXT records via Cloudflare API
3. **Per-service certificates** — each service gets its own cert (e.g., `grafana.optimusprime.favarohome.com`)
4. **Internal + External** — `*.optimusprime.favarohome.com` points to LAN IPs; `*.public.favarohome.com` points to the public IP (51.154.63.53) and is routed through the same Traefik instance via port 443 forwarding
5. **Auto-renewal** — Traefik handles certificate renewal automatically
6. **Upload timeouts** — `websecure` entrypoint configured with `readTimeout: 600s`, `writeTimeout: 600s`, `idleTimeout: 300s` to support large file uploads (e.g., Immich photo/video uploads from phones)

### Traefik Configuration Files

On optimus prime:

| File | Purpose |
|------|---------|
| `/etc/containers/systemd/traefik.container` | Quadlet definition (ports 80, 443, 8080) |
| `/mnt/data/docker_persistent/traefik/traefik.yml` | Static config (entrypoints, ACME, providers) |
| `/mnt/data/docker_persistent/traefik/dynamic.yml` | Dynamic config for non-container services (Cockpit) |
| `/mnt/data/docker_persistent/traefik/acme.json` | Let's Encrypt certificates (auto-managed, chmod 600) |

### Adding a New Service

For container services, add these labels to the quadlet `.container` file (before `[Service]`):

```ini
Label=traefik.enable=true
Label=traefik.http.routers.<name>.rule=Host(`<name>.optimusprime.favarohome.com`)
Label=traefik.http.routers.<name>.entrypoints=websecure
Label=traefik.http.routers.<name>.tls.certresolver=cloudflare
Label=traefik.http.services.<name>.loadbalancer.server.port=<port>
```

Then: `systemctl daemon-reload && systemctl restart <name>.service`

For non-container services (like Cockpit), add a router/service in `dynamic.yml`.

### Cloudflare DNS Records

```
*.optimusprime.favarohome.com  A  192.168.1.10   (DNS only — internal LAN)
*.bumblebee.favarohome.com     A  192.168.1.14   (DNS only — internal LAN)
*.public.favarohome.com        A  51.154.63.53   (DNS only — public IP, internet-facing)
*.k8s.favarohome.com           A  <TBD>          (DNS only)
optimusprime.favarohome.com    A  192.168.1.10   (DNS only — internal LAN)
bumblebee.favarohome.com       A  192.168.1.14   (DNS only — internal LAN)
```

**Important**: Internal records must be "DNS only" (grey cloud), not "Proxied" (orange cloud), since they point to internal IPs. The `*.public` record also uses "DNS only" as Traefik handles TLS termination directly.

### Public (Internet-Facing) Services (`*.public.favarohome.com`)

External access goes through port 443, forwarded by the UniFi router to Traefik on optimus prime. Each service has a second Traefik router with a `*.public.favarohome.com` hostname.

| FQDN | Internal Service | Port |
|------|-----------------|------|
| `plex.public.favarohome.com` | Plex | 32400 |
| `pingvin.public.favarohome.com` | Pingvin Share | 3000 |
| `nextcloud.public.favarohome.com` | Nextcloud | 443 |
| `jellyfin.public.favarohome.com` | Jellyfin | 8096 |
| `immich.public.favarohome.com` | Immich | 2283 |

To expose an additional service publicly, add a second set of Traefik labels to its quadlet:

```ini
Label=traefik.http.routers.<name>-public.rule=Host(`<name>.public.favarohome.com`)
Label=traefik.http.routers.<name>-public.entrypoints=websecure
Label=traefik.http.routers.<name>-public.tls.certresolver=cloudflare
Label=traefik.http.routers.<name>-public.service=<name>
```

### Port Forwarding (UniFi Router)

Traffic path: `Internet → ISP router (DMZ all ports → 192.168.2.4) → UniFi (192.168.1.1) → port forward → Optimus Prime (192.168.1.10)`

| Rule | Ports | Protocol | Source | Notes |
|------|-------|----------|--------|-------|
| Traefik HTTPS | 443 | TCP | Any | Routes all `*.public.favarohome.com` traffic |
| RustDesk HBBS (TCP) | 21114, 21115, 21118 | TCP | Any | Remote desktop relay |
| RustDesk HBBS (TCP/UDP) | 21116 | TCP/UDP | Any | Remote desktop relay |
| RustDesk HBBR (TCP) | 21117, 21119 | TCP | Any | Remote desktop relay |
| stefano | 22, 9090 | TCP/UDP | `185.44.213.143` | SSH + Cockpit (source-restricted) |
| Work | 22 | TCP/UDP | `62.12.152.2` | SSH (source-restricted) |
| ~~Plex~~ | ~~32400~~ | — | — | Disabled — now via Traefik 443 |
| ~~Pingvin Share~~ | ~~5000~~ | — | — | Disabled — now via Traefik 443 |

### Service URL Reference

All services are accessible via HTTPS with trusted Let's Encrypt certificates:

| Service | URL |
|---------|-----|
| Home Assistant | `https://homeassistant.optimusprime.favarohome.com` |
| Grafana | `https://grafana.optimusprime.favarohome.com` |
| Node-RED | `https://nodered.optimusprime.favarohome.com` |
| Plex | `https://plex.optimusprime.favarohome.com` |
| Tautulli | `https://tautulli.optimusprime.favarohome.com` |
| Sonarr | `https://sonarr.optimusprime.favarohome.com` |
| Transmission | `https://transmission.optimusprime.favarohome.com` |
| Zigbee2MQTT | `https://zigbee2mqtt.optimusprime.favarohome.com` |
| MQTT Dashboard | `https://mqtt-dashboard.optimusprime.favarohome.com` |
| MQTT Explorer | `https://mqtt-explorer.optimusprime.favarohome.com` |
| JDownloader | `https://jdownloader.optimusprime.favarohome.com` |
| Handbrake | `https://handbrake.optimusprime.favarohome.com` |
| MakeMKV | `https://makemkv.optimusprime.favarohome.com` |
| Pingvin Share | `https://pingvin.optimusprime.favarohome.com` |
| aMule | `https://amule.optimusprime.favarohome.com` |
| Cockpit (OP) | `https://cockpit.optimusprime.favarohome.com` |
| File Browser | `https://filebrowser.optimusprime.favarohome.com` |
| Heimdall | `https://heimdall.optimusprime.favarohome.com` |
| Nextcloud | `https://nextcloud.optimusprime.favarohome.com` |
| Jellyfin | `https://jellyfin.optimusprime.favarohome.com` |
| Immich | `https://immich.optimusprime.favarohome.com` |
| Traefik Dashboard | `https://traefik.optimusprime.favarohome.com` |
| InfluxDB | `https://influxdb.optimusprime.favarohome.com` |
| Prometheus | `https://prometheus.optimusprime.favarohome.com` |
| **Bumblebee (LAN)** | |
| Open WebUI | `https://chat.bumblebee.favarohome.com` |
| OpenClaw | `https://openclaw.bumblebee.favarohome.com` |
| OpenCode | `https://opencode.bumblebee.favarohome.com` |
| n8n | `https://n8n.bumblebee.favarohome.com` |
| Ollama | `https://ollama.bumblebee.favarohome.com` |
| Heimdall (BB) | `https://heimdall.bumblebee.favarohome.com` |
| Traefik (BB) | `https://traefik.bumblebee.favarohome.com` |
| ComfyUI | `https://comfyui.bumblebee.favarohome.com` |
| Cockpit (BB) | `https://cockpit.bumblebee.favarohome.com` |
| **Public (external)** | |
| Plex | `https://plex.public.favarohome.com` |
| Pingvin Share | `https://pingvin.public.favarohome.com` |
| Nextcloud | `https://nextcloud.public.favarohome.com` |
| Jellyfin | `https://jellyfin.public.favarohome.com` |
| Immich | `https://immich.public.favarohome.com` |

## Firewall

- **Optimus Prime**: No firewall (no firewall-cmd installed)
- **Bumblebee**: firewalld (default AlmaLinux 9 config)
- **Fedora workstation**: firewalld with mdns, samba-client, ssh, dhcpv6-client allowed
