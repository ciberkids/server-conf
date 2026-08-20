# MCP servers for the homelab — what exists, and what is worth connecting to Hermes

**Surveyed 2026-08-20.** Goal: give Hermes situational overview across the homelab.
Every repo below was verified to exist via the GitHub API on that date — stars, last push and
archived-state are real readings, not recollections.

---

## 1. The constraint that decides this — measured, not guessed

`hermes prompt-size --platform telegram` on the live instance:

```
System prompt total :   22,157 B  (21.6 KB)
  skills index      :    7,907 B
  memory            :    2,373 B
  user profile      :    1,065 B
Tool schemas        :   52,859 B  (51.6 KB, 32 tools)
```

**Tool schemas are ~70% of the fixed prompt cost, at ≈1.65 KB per tool, paid on every message.**
A typical MCP exposes 15–30 tools ⇒ **≈25–50 KB of permanent prompt each**.

Consequences:
- The fixed prompt is already **~18,750 tokens** (75 KB total). That is the floor for every request,
  before history. It also corrects an earlier estimate that assumed ~8,000 input tokens per request —
  the realistic DeepSeek bill is **$3–7/month**, not $1.63.
- `prompt_caching` is configured (`cache_ttl: 5m`), which offsets this for back-to-back messages but
  **not** for sparse household use.
- Beyond cost, a large tool surface degrades *tool selection* — more near-duplicate options to choose
  between.

🔑 **Method: run `hermes prompt-size` before and after adding each MCP.** It runs offline, no API call.
This is the only decision in the homelab with a directly measurable recurring price, so measure it.

🔑 **Hermes supports per-server filtering** — `mcp_servers.<name>.tools.include` (whitelist) and
`tools.exclude` (blacklist), verified in `tools/mcp_tool.py:4071-4077`. **Use `include` aggressively**:
connecting an MCP does not oblige you to import all of its tools. Note ha-mcp's metadata lists **86**
tools while only **32** reach the telegram platform, so platform toolsets already filter — check what
actually lands rather than assuming.

⚠️ **Blast radius.** Toolsets are **per-platform, not per-chat**. Every tool added is available in
*every* Telegram chat — including Manu's DM (§7.5 of the filing design). A UniFi or Nextcloud MCP is
reachable by anyone in any allowed chat. `tools.exclude` is the lever.

🔒 **Supply chain.** These are third-party servers that would hold API tokens to your services. Several
below have single-digit stars. This homelab has already had an API key compromised and abused
(April 2026). **Read the code before connecting one, prefer official/high-star, and mint least-privilege
tokens** — Hermes reuses the HA *admin* token today, which is exactly the pattern not to repeat.

---

## 2. Already connected

| Service | Server | Notes |
|---|---|---|
| Home Assistant | `homeassistant-ai/ha-mcp` (★4,441, pushed 2026-08-20) | 86 tools available, **32** exposed on telegram. Uses an admin token — full write incl. delete. |
| Zigbee2MQTT | patched `ichbinder/MCP2ZigBee2MQTT` on OP :3235 | Build-from-source + a `handlePostMessage` fix; SSE transport |

---

## 3. 🔑 Do not double up — several services are already covered *through* Home Assistant

This is the cheapest capability in the survey: it costs zero extra prompt.

| Service | Already in HA | So an MCP would be redundant |
|---|---|---|
| **Frigate** | ~78 entities *(counted 2026-07-24, not re-verified today)* — cameras, detect switches, occupancy/motion, zones | ✅ and no Frigate MCP exists anyway |
| SLZB-06 coordinator | `smlight` integration, 13 entities incl. both temperatures | ✅ |
| Fronius solar / energy meters | MQTT + Modbus sensors, LTS in InfluxDB | mostly ✅ |
| Zigbee devices | via HA *and* the z2m MCP | already double-covered |

**Check HA first for anything you want Hermes to see.** Server CPU/RAM/disk is the notable gap — HA
holds none for either host (that lives in Prometheus/Grafana).

---

## 4. Tier 1 — worth connecting

Ranked by overview-per-kilobyte for a household assistant.

| Service | Repo | ★ | Last push | Why |
|---|---|---|---|---|
| **Grafana** | `grafana/mcp-grafana` | 3,375 | 2026-08-20 | **Official.** Closes the "HA has no server metrics" gap — dashboards, Prometheus queries, alerts in one place. Best single choice for *overview*. |
| **Prometheus** | `pab1it0/prometheus-mcp-server` | 512 | 2026-08-05 | Direct PromQL. Overlaps Grafana's MCP — pick one, probably Grafana. |
| **Paperless-ngx** | `baruchiro/paperless-mcp` | 138 | 2026-07-23 | Directly serves the filing pipeline: search the archive, read tags/correspondents. |
| **UniFi** | `sirkirby/unifi-mcp` | 717 | 2026-08-17 | Dream Machine: clients, networks, port state. Would have helped every network incident in the logbook. ⚠️ Also the widest blast radius here. |
| **Grocy** | `saya6k/mcp-grocy-api` | 29 | 2026-05-27 | The one the household-assistant want needs ("put things in grocy"). ⚠️ Low stars — read it first. |
| **Nextcloud** | `cbcoutinho/nextcloud-mcp-server` | 331 | 2026-08-20 | Files, and it is the paperless backup target. |

## 5. Tier 2 — exists, with caveats

| Service | Repo | ★ | Last push | Caveat |
|---|---|---|---|---|
| n8n | `czlonkowski/n8n-mcp` | **22,735** | 2026-08-19 | Huge project, but oriented at *building* workflows rather than running the homelab. Probably large tool surface — measure. |
| Alertmanager | `ntk148v/alertmanager-mcp-server` | 24 | 2026-06-16 | Niche; the cross-host watchdog already covers the "is alerting alive" question. |
| InfluxDB | `idoru/influxdb-mcp-server` | 44 | **2026-01-14** | ⚠️ 7 months stale. |
| Immich | `barryw/ImmichMCP` / `drolosoft/immich-photo-manager` | 39 / 39 | 2026-08-05 / 08-17 | Two comparable options; neither dominant. |
| *arr suite | `aplaceforallmystuff/mcp-arr` | 196 | 2026-08-09 | Covers Sonarr/Radarr/Prowlarr in one — the efficient way to do the media stack. |
| Jellyfin | `jaredtrent/jellyfin-mcp` | 28 | 2026-08-20 | Active but small. |
| Transmission | `philogicae/transmission-mcp` | 4 | 2026-07-13 | ⚠️ Tiny. `arr-mcp` may cover it. |
| Firefly III | `etnperlong/firefly-iii-mcp` | 82 | **2025-06-12** | ⚠️ 14 months stale. `fabianonetto/mcp-server-firefly-iii` (22★, 2026-05-05) is fresher. **Moot for now — the Firefly API token was never retrieved.** |
| SearXNG | `SecretiveShell/MCP-searxng` | 128 | 2026-05-29 | Only useful if Hermes should web-search via your own instance. |
| Tautulli | `lodordev/mcp-tautulli` | 6 | 2026-07-24 | ⚠️ Tiny. |
| Redis / PostgreSQL | `modelcontextprotocol/servers-archived` | — | — | ⚠️ **Archived** by upstream. Direct DB access from an LLM is also a poor idea here. |

⚠️ **Name-collision traps found while surveying** — the catalogues will mislead you:
- `gofireflyio/firefly-mcp` is **cloud infrastructure**, *not* Firefly III the finance app.
- The "Grafana" hit in `awesome-mcp-servers` is **k6** (load testing), not Grafana.
- The "Jellyfin" hit is **Overseerr**; the "Plex" hit is **Tautulli**.
- The "Home Assistant" hit is a **KNX** server.
- "Heimdall" MCP is unrelated to the Heimdall dashboard.

## 6. Tier 3 — no MCP exists (searched, nothing real)

**Frigate** (covered via HA anyway) · Traefik · Warracker · Heimdall · OpenSign · Pingvin Share ·
FileBrowser · Stirling-PDF · JDownloader · RustDesk · Affine · Node-RED · Mosquitto ·
makemkv / handbrake / shutter-encoder · cloud-drive-sync (own project) · comfyui-launcher · opencode.

For these, the options are a REST call from a skill, an OliveTin action (already planned for the filing
pipeline — the same pattern generalises), or nothing.

---

## 7. Recommendation

**Connect three, not fifteen:**

1. **`grafana/mcp-grafana`** — official, and the single biggest overview win: it closes the server
   metrics gap that HA cannot fill.
2. **`baruchiro/paperless-mcp`** — earns its place through the filing pipeline rather than in general.
3. **`saya6k/mcp-grocy-api`** — the household-assistant behaviour that was explicitly asked for.
   Read the source first; 29 stars.

Then **stop and measure** with `hermes prompt-size` before considering UniFi or Nextcloud. Use
`tools.include` on each to import only the handful of tools actually wanted, rather than the whole
surface.

**Deliberately not recommended:** Prometheus *and* Grafana together (redundant); Redis/PostgreSQL
(archived, and raw DB access from an LLM is the wrong shape); Firefly III (no token, stale servers);
anything in Tier 3 (use OliveTin).

---

## 8. Related records

- Hermes multi-chat, toolsets, API server: `project_hermes_migration` (memory)
- The filing pipeline that motivates paperless + OliveTin: `docs/document-filing-pipeline.md`
- HA entity coverage incl. Frigate's 78 entities: `reference_frigate_nvr`, `reference_ha_health_dashboard`
- Why least-privilege tokens matter here: `project_openclaw_key_compromise` (memory)
