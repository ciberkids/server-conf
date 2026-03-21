# Server Configuration

All services run as Podman containers managed by systemd quadlets.

## Structure

```
systemd/containers/system/
├── optimusprime/    # Optimus Prime (192.168.1.10) quadlets
└── bumblebee/       # Bumblebee (192.168.1.14) quadlets
```

## Deploying a quadlet

```bash
sudo cp <name>.container /etc/containers/systemd/
sudo systemctl daemon-reload
sudo systemctl start <name>.service
```

## Managing services

```bash
systemctl status <name>.service    # Check status
systemctl restart <name>.service   # Restart
journalctl -u <name>.service       # View logs
```
