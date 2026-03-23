# Favaro Home Infrastructure

Configuration, documentation, and automation for the Favaro home lab infrastructure.

## Servers

| Server | Hostname | IP | OS | Role |
|--------|----------|----|----|------|
| **Optimus Prime** | `optimusprime` | 192.168.1.10 | Arch Linux (rolling) | Main server — storage, containers, home automation |
| **Bumblebee** | `bumblebee` | 192.168.1.14 | AlmaLinux 9.4 | Workstation — GPU compute, secondary services |

## Domain & DNS

- **Domain**: `favarohome.com` (managed by Cloudflare)
- **Router DNS domain**: `localdomain` (DHCP from 192.168.1.1)
- **mDNS domain**: `.local` (Avahi on optimus prime)

### Naming Convention

Services are accessed via: `<service>.<host>.favarohome.com`

```
grafana.optimusprime.favarohome.com
homeassistant.optimusprime.favarohome.com
cockpit.bumblebee.favarohome.com
```

All DNS records point to the respective server's internal IP. HTTPS is terminated by Traefik using Let's Encrypt certificates via Cloudflare DNS-01 challenge.

## Directory Structure

```
ansible/              # Ansible playbooks for automated provisioning
  inventory.ini       # Host inventory
  setup-workstation.yml  # Bumblebee provisioning playbook
docs/                 # Detailed documentation
  optimus-prime.md    # Optimus Prime server documentation
  bumblebee.md        # Bumblebee server documentation
  networking.md       # Network, DNS, and HTTPS setup
scripts/              # Utility scripts for service management
  jellyfin/           # Jellyfin metadata & NFO file tools
  influxdb/           # InfluxDB data migration from HA PostgreSQL
  grafana/            # Grafana dashboard creation/update scripts
```

## Quick Start

Provision a fresh bumblebee install:
```bash
ansible-playbook -i ansible/inventory.ini ansible/setup-workstation.yml --ask-become-pass
```
