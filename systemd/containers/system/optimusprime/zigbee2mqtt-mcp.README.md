# zigbee2mqtt-mcp

MCP server exposing Zigbee2MQTT (device discovery + control) over MCP, for
Claude Code and Hermes. Talks to the `mqtt5` broker (192.168.1.10:1883),
NOT to Home Assistant — so it gives Zigbee-native tools independent of HA.

- **Upstream:** https://github.com/ichbinder/MCP2ZigBee2MQTT (Node.js, build from source — no published image)
- **Runs:** HTTP/SSE on `:3235`, API-key auth, `Network=host`
- **MQTT user:** dedicated `z2m-mcp` in mosquitto pwfile (broker requires auth)

## Build (on Optimus Prime)
Clone requires TWO source patches before `podman build`:

1. **`Dockerfile`**: `npm ci` → `npm install` (repo ships no `package-lock.json`).
2. **`src/index.ts` `startHttpMode()`**: upstream bug — `POST /messages` was a
   no-op stub, so MCP `initialize` was never processed → clients got
   "Session terminated". Fix = standard SSE boilerplate: keep a
   `sessionId -> SSEServerTransport` map, create a fresh `ZigbeeMcpServer`
   per `/sse` connection, and route `POST /messages` into
   `transport.handlePostMessage(req, res, req.body)`.

```
git clone --depth 1 https://github.com/ichbinder/MCP2ZigBee2MQTT /root/z2m-mcp-build
# apply the two patches above (see /root/z2m-mcp-build/src/index.ts.bak for pre-patch)
sudo podman build -t localhost/zigbee2mqtt-mcp:latest /root/z2m-mcp-build
sudo systemctl daemon-reload && sudo systemctl restart zigbee2mqtt-mcp.service
```

## Clients (must use SSE transport — server is legacy SSE, not Streamable HTTP)
- **Claude Code** (`~/.claude.json` mcpServers): `{"type":"sse","url":"http://192.168.1.10:3235/sse","headers":{"Authorization":"Bearer <API_KEY>"}}`
- **Hermes** (`/opt/data/config.yaml` mcp_servers): `url` + **`transport: sse`** + `headers.Authorization: "Bearer ${Z2M_MCP_API_KEY}"` (secret in `/etc/containers/secrets/hermes.env`)

## Gotchas
- **~90s cold start**: subscribes to `zigbee2mqtt/+` and processes the retained
  message flood synchronously, starving the event loop until done; the HTTP
  listener only comes up afterward. One `EPIPE`/MQTT reconnect during this is
  normal. Health: `curl http://192.168.1.10:3235/health`.
- **`Network=host`** required: podman's published-port proxy wasn't reachable
  from bumblebee on this multi-NIC host.
