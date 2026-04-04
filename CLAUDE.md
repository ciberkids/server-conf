# Homelab Project Instructions

## Memory
At the start of every conversation, **always load all project memory files** from the memory directory. Read `MEMORY.md` first, then read every referenced memory file before doing any work. This context is critical for understanding the user's infrastructure, preferences, and workflow rules.

## Workflow Rules
- **Service installs**: Always follow the full workflow: quadlet → Traefik → git commit → Heimdall (see `feedback_service_install_workflow.md`)
- **Service discovery**: Always check awesome-selfhosted repo first (see `feedback_awesome_selfhosted.md`)
- **Parallel work**: Use TeamCreate + tmux teammates, never plain Agent calls (see `feedback_use_teams.md`)
- **Network calls**: Run API calls directly from workstation, don't SSH unnecessarily (see `feedback_local_network.md`)
- **Git**: Commit to the repo after every infrastructure change. Use imperative mood, short descriptions.
- **Ansible**: Update `ansible/setup-workstation.yml` when adding services to bumblebee.

## End of Session Checklist
Before ending a session or when the user says to save/push, always:
1. **Check `git status`** — commit any uncommitted changes
2. **Update ansible** — if any bumblebee services were added/modified, ensure `ansible/setup-workstation.yml` is up to date
3. **Push to remote** — `git push origin main` to sync with GitHub
4. **Update memory** — save any new learnings about the user, infrastructure, or workflow preferences

## Git Repository
- Remote: `git@github.com-personal:ciberkids/server-conf.git`
- Branch: `main`
- Commit style: imperative mood, short description (e.g. "Add SearXNG and enable web search")
- Always push after completing work

## Server Access
- **Optimus Prime**: `ssh 192.168.1.10` (Arch Linux, no SELinux)
- **Bumblebee**: `ssh 192.168.1.14` (AlmaLinux 9, SELinux enforcing — volumes need `:Z`)
- **Workstation**: Local (Fedora, same LAN 192.168.1.0/24)

## Service Installation Workflow (Full)
When adding a new self-hosted service:
1. Look up in [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted)
2. Research Docker/container setup (image, ports, volumes, env vars, dependencies)
3. Check port availability on target server
4. Create persistent directories on target server
5. Write quadlet `.container` file (+ `.network` if multi-container)
6. Deploy quadlet to `/etc/containers/systemd/` on server
7. Start service, verify HTTP response
8. Add Traefik labels (or dynamic.yml for pods/WebSocket)
9. Add to Heimdall dashboard on the corresponding server
10. Save quadlet to git repo at `systemd/containers/system/<hostname>/`
11. Update `ansible/setup-workstation.yml` if bumblebee service
12. Git commit and push

## Key Conventions
- Bumblebee quadlets: SELinux `:Z` on all writable volumes, `AddDevice=nvidia.com/gpu=all` for GPU containers
- Optimus Prime quadlets: No `:Z` needed (Arch, no SELinux)
- Multi-container services: Use dedicated `.network` quadlet for container DNS resolution
- Naming: `<service>.<hostname>.favarohome.com` for Traefik routes
- All containers: `AutoUpdate=registry` for podman auto-update
- Bumblebee containers: `OnFailure=notify-failure@%n.service` for Telegram alerts
- Telegram notifications: Both servers have boot notify + daily auto-update digest
