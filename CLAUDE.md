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
