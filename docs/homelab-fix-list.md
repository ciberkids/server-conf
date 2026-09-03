# Homelab fix list

**Opened:** 2026-09-03. Working list for the three items raised on 2026-09-03, with the
evidence behind each so a later session does not re-derive it.

Status key: 🔴 open · 🟡 needs your decision · ✅ done

---

## 1. 🔴 Optimus Prime GPU usage "always 0"

**Complaint:** the graphics-card usage sensor on Optimus Prime reads 0 permanently, including
while a Plex hardware transcode was deliberately forced.

This turned out to be **two unrelated problems plus a latent one**. Only the second is what you
were looking at.

### 1a. 🔴 The custom `amdgpu` textfile exporter is broken — and has been since April

`scripts/optimus-prime/amdgpu-metrics.sh` (deployed identically at
`/usr/local/bin/amdgpu-metrics.sh`, run every 15 s by `amdgpu-metrics.timer`) reads:

```
/sys/class/drm/card0/device/{gpu_busy_percent,mem_info_vram_used,mem_info_vram_total}
```

**There is no `card0` on this machine.** The RX 6600 (Navi 23, `0b:00.0`) is **`card1`** —
`/sys/class/drm/` contains only `card1*` and `renderD128`.

The script then does `${VRAM_USED:-0}`, so a missing file becomes a **literal, plausible-looking
`0`** rather than a missing metric. It has been publishing three fake zeros every 15 s:

```
amdgpu_memory_used_bytes 0
amdgpu_memory_total_bytes 0
amdgpu_utilization_percent 0
```

Verified live: `amdgpu_utilization_percent` = `0` in Prometheus, while the same instant's
`card1` sysfs read gives `gpu_busy_percent=0`, `mem_info_vram_used=78118912`,
`mem_info_vram_total=8573157376`.

**Nothing consumes these metrics.** No Grafana panel, no alert rule, no recording rule, no HA
sensor references `amdgpu_*` (grepped `config/`, `alerts.yml`, and the Grafana DB). It is dead
code that lies.

It is also **fully redundant**: node_exporter on OP already runs with `--collector.drm` and
exports the same facts correctly, with the right card label:

```
node_drm_gpu_busy_percent{card="card1"}          0
node_drm_memory_vram_used_bytes{card="card1"}    7.8118912e+07
node_drm_memory_vram_size_bytes{card="card1"}    8.573157376e+09
node_drm_memory_gtt_used_bytes{card="card1"}     2.902016e+07
```

**Two ways forward — and 1b changes which one I recommend.**

*Retire it:* stop and disable `amdgpu-metrics.timer`, remove
`/usr/local/bin/amdgpu-metrics.sh` and `/tmp/node_exporter/amdgpu.prom`, delete the two unit
files and `scripts/optimus-prime/amdgpu-metrics.sh`. `--collector.drm` already covers it.

*⭐ Or repurpose it* — which is what I now recommend, because it is the only real fix for 1b.
The 15 s timer and textfile plumbing already exist; point them at the right card and have it
**sample fast** (see 1b fix 1) instead of reading once.

⚠️ **Either way it's your call** — you asked me to check, not to remove. And if you keep it, do
*not* just change `card0`→`card1`; that repeats the bug class. Resolve the card by driver:

```bash
for d in /sys/class/drm/card*/device; do
  [ "$(basename "$(readlink -f "$d/driver")" 2>/dev/null)" = amdgpu ] && CARD=$d && break
done
```

…and drop the `:-0` defaults so a missing file emits **no sample** instead of a fake zero.

### 1b. 🔴 Why Grafana showed 0 during your transcode — sampling, not a broken sensor

The panel you are looking at is **`AMD GPU`** on the **`optimusprime-server`** dashboard. It
already queries the *correct* metrics:

```promql
node_drm_gpu_busy_percent{instance="optimusprime",card="card1"}
node_drm_memory_vram_used_bytes{...} / node_drm_memory_vram_size_bytes{...} * 100
node_drm_memory_gtt_used_bytes{...}  / node_drm_memory_gtt_size_bytes{...}  * 100
```

So the panel is not wired to the broken exporter of 1a. The zero is real, and here is why.

**Plex was genuinely transcoding on the GPU.** Tautulli during the test:

| field | value |
|---|---|
| `transcode_decision` | `transcode` |
| `transcode_hw_decode` / `transcode_hw_encode` | `vaapi` / `vaapi` |
| `transcode_hw_full_pipeline` | `1` |
| `transcode_speed` | `7.0` |
| `transcode_throttled` | `1` |

And `/sys/kernel/debug/dri/1/amdgpu_pm_info` said **`VCN: Powered up`** while reporting
**`GPU Load: 0 %`** and `SCLK 0 MHz` — that is a *throttled* encoder caught mid-pause, not a
counter blind to VAAPI. The controlled test below settles which. See 1d.

**The counter does work.** A controlled encode proved it — 1080p→HEVC via `hevc_vaapi`,
1800 frames at **397 fps (6.6× realtime)**:

```
18:01:37 busy= 18%  gfx_activity= 21%  vram_MB= 276    <-- inside the encode
18:01:39 busy=  0%  gfx_activity=  0%  vram_MB= 229    <-- encode finished (4.5 s total)
```

You confirmed this yourself: Grafana lit up during that run.

**The mechanism is aliasing.** `gpu_busy_percent` is an *instantaneous* gauge. Hardware
transcoding runs at 6–7× realtime and Plex throttles it (`transcode_throttled=1`) as soon as the
player's buffer fills — so the video engine works in **short bursts with a very low duty cycle**.
Prometheus takes **one point sample every 30 s**, which almost always lands in an idle gap.

Measured over 30 days:

| measurement | value |
|---|---|
| samples where `gpu_busy_percent` > 0 | **0.14 %** |
| peak `gpu_busy_percent` | 29 % |
| peak VRAM used | 240 MB = **2.8 %** of the 8.5 GB pool |

At 1 s sampling I saw regular 3–9 % blips; at 30 s scraping, essentially nothing. Compounding it,
all three series are plotted on one **0–100 % axis**, where VRAM at 2.8 % and GTT at 0.63 % are
flat lines on the floor even when they are moving.

**Fixes — and only one of them actually works:**

1. **⭐ The real fix — repurpose the dead script from 1a into a sampling exporter.** It already
   runs every 15 s with the textfile plumbing in place. Have it poll `gpu_busy_percent` ~20×/s
   and publish `max` and `mean` for the interval. That is the only option that *creates* the
   missing samples, so it is the only one that removes the aliasing.
   **Pick this over retiring the script in 1a** — the cadence and plumbing already exist.
2. **Plot VRAM in bytes on its own axis**, not as a percentage of 8.5 GB. A 47 MB transcode
   allocation is invisible as a percentage and obvious in bytes.
3. **For "is something transcoding" use Tautulli, not the GPU graph** — a semantic question no
   utilisation counter can answer. Now available to Hermes, see §2.

⛔ **`max_over_time(...[5m])` is NOT the fix, despite looking like it.** It widens the window over
**stored** samples; it cannot recover load that was never sampled. Measured over 30 days:

| panel query | reads non-zero |
|---|---|
| raw gauge | **0.15 %** of the time |
| `max_over_time(...[5m])` | **0.92 %** — 6× better, still zero 99 % of the time |
| `max_over_time(...[1h])` | 2.87 % |

It only helps where a burst happened to coincide with a scrape. Worth applying as a one-line
improvement alongside fix 1, but on its own the panel will still read 0 and you will think
nothing changed.

### 1c. 🔴 Latent: the card index is hardcoded in the dashboard too

The `AMD GPU` panel pins `card="card1"` in all three queries. Same fragility class as 1a's
`card0` — a kernel or hardware change renumbers it and the panel silently goes empty. Drop the
label, or drive it from a Grafana variable.

### 1d. ℹ️ `average_mm_activity` is dead on this silicon — but the graphics counters are not

`gpu_metrics` (v1.3, 120 B binary at `/sys/class/drm/card1/device/gpu_metrics`) exposes
`average_mm_activity`, the multimedia/VCN field. On Navi 23 the SMU **never populates it** — it
read `0 %` throughout the controlled encode. Don't build a panel on it.

**But that does not mean the GPU is unmeasurable during a transcode.** The same encode registered
on the graphics counters at the same instant:

| counter | during encode | source |
|---|---|---|
| `average_mm_activity` | **0 %** ⛔ never populated | `gpu_metrics` offset 20 |
| `average_gfx_activity` | **21 %** ✅ works | `gpu_metrics` offset 16 |
| `gpu_busy_percent` | **18 %** ✅ works | sysfs |
| `average_umc_activity` | works | `gpu_metrics` offset 18 |

🔑 **This refutes the intuition that `gpu_busy_percent` is blind to VAAPI.** It is not — a
hardware transcode does load the graphics pipe measurably. The problem in 1b is purely
**duty cycle vs sample rate**, not a blind counter. So the honest transcode signals are:

- `gpu_busy_percent` / `average_gfx_activity` — **if sampled fast enough** (see 1b fix 1)
- the **VRAM delta** (+47 MB during the encode)
- `VCN: Powered up` in `/sys/kernel/debug/dri/1/amdgpu_pm_info` (boolean, needs root) — note it
  appears *alongside* `GPU Load: 0 %`, which is a throttled encoder, not a contradiction
- Tautulli, for the semantic answer (§2)

Struct header is `<HBB` = structure_size / format_revision / content_revision.

---

## 2. ✅ Hermes can now query Tautulli

**Done and verified end-to-end from inside the Hermes container.**

| | |
|---|---|
| Skill | `skills/media/tautulli/SKILL.md` (in the Hermes data volume) |
| Registered as | `tautulli / media / local / enabled` |
| Credentials | `TAUTULLI_URL`, `TAUTULLI_API_KEY` in `/etc/containers/secrets/hermes.env` |
| Verified | `get_libraries` → 1253 movies, 256 shows; `get_activity` → live stream count |
| Prompt cost | **+77 B** (27,406 → 27,483 B; skills index 9,226 → 9,303 B). Tool schemas unchanged at 41,305 B / 20 tools. |

### Why a skill and not an MCP server

`docs/hermes-mcp-candidates.md` measured tool schemas at ~1.65 KB/tool — an MCP costs
**25–50 KB of permanent prompt on every message**. The only Tautulli MCP
(`lodordev/mcp-tautulli`) has 6 stars. A skill costs **77 bytes** because only its
description sits in the always-loaded index; the body loads on demand. Same capability,
~99.8 % cheaper.

### ⚠️ Two things you should know

**I reused the existing key rather than generating a new one.** Tautulli already had
`api_enabled = 1` with a 32-char key. Rotating it would have been safe as far as this repo is
concerned — nothing but the blackbox probe and `scripts/alarm` touch Tautulli, and neither uses
the API — but a phone app (Tautulli Remote) or anything else holding the old key would have
broken silently, and I can't see those. Say the word and I'll rotate it in
Settings → Web Interface and update the env var.

**This key is full admin.** Tautulli has no read-only scope — one global key that also reaches
`restart`, `terminate_session`, `delete_library`, `delete_all_library_history`. Mitigations:

- `api_sql = 0` is already set server-side, which removes the worst of it (no arbitrary SQL).
- The skill carries an explicit **read-only allowlist** and a named do-not-call list.
- That allowlist is **convention, not enforcement** — it constrains the model's instructions,
  not the credential.

This is the second instance of the pattern `docs/hermes-mcp-candidates.md` flags as "the one not
to repeat" (Hermes also holds an HA **admin** token). Unavoidable here given Tautulli's API
design, but worth knowing rather than discovering.

---

## 3. 🟡 The monitoring stack has no authentication — your decision

**You asked: is that wanted?** Here is exactly what is open, so you can answer it.

### What I probed (not read off a config — actually requested)

| Endpoint | Auth | Notes |
|---|---|---|
| Prometheus `192.168.1.10:9092` | ❌ none | Full query API + config + targets readable |
| Alertmanager `192.168.1.10:9093` | ❌ none | `/api/v2/status`, `/api/v2/silences` → 200 |
| node_exporter `.10:9100`, `.14:9100` | ❌ none | Full host metrics, both servers |
| smartctl-exporter `.10:9633` | ❌ none | Disk serials + SMART |
| podman-exporter `.10:9882` | ❌ none | Container inventory |
| blackbox-exporter `.10:9115` | ❌ none | |
| InfluxDB `.10:8086` | ✅ 401 | Token required |
| Grafana `.10:3000` | ✅ 401 | No anonymous access |

### Prometheus itself is read-only — that part is fine

Confirmed by probing, not by trusting flags:

- `POST /api/v1/admin/tsdb/delete_series` → **500** (`web.enable-admin-api=false`)
- `POST /-/reload` → **403** (`web.enable-lifecycle=false`)

So nobody can delete your history or reload config through it. The exposure is **read-only
disclosure**: metrics, hostnames, container names, disk serials, the full target list.

### 🔴 Two things that are worse than the question you asked

**1. `web.cors.origin = .*`** — Prometheus sends a permissive CORS header, so **any web page
open in any browser on your LAN can read the metrics API via JavaScript** and ship the results
out. That is a drive-by path, not "someone would have to be on my network with curl". This is
the sharpest finding here and it is a one-line fix (`--web.cors.origin` to something specific,
or drop it).

**2. Alertmanager accepts writes.** It runs with no `--web.config.file`, and unlike Prometheus it
has **mutating endpoints** — `POST /api/v2/silences` would let anyone on the LAN **silence every
alert on both servers**, indefinitely, with no credential. Given the four-month alerting outage
that `project_monitoring_watchdog` exists to catch, an unauthenticated silence API is the more
serious of the two. (I did **not** test the write — that would have created a real silence.)

### Scope: LAN-only, but one thing is unproven

Public DNS for `*.optimusprime.favarohome.com` resolves to **192.168.1.10** (RFC1918), so the
names are not reachable from the internet by DNS. Port 8080 is confirmed not forwarded.

⚠️ **Still unproven** (carried over from `reference_public_services`): Traefik serves *every*
router on the one `:443` entrypoint, and 443 **is** port-forwarded. Forcing the hostname against
the WAN IP returns 200 — but every such test so far ran from **inside the LAN via NAT hairpin**,
so it does not establish that a genuine external client gets the same. I could not settle it this
session either: the workstation is currently egressing via the home WAN (`51.154.63.53`, route via
`192.168.1.1`), not the office VPN, so it has no external vantage point.

**The test that settles it** — from a phone on **mobile data**, WiFi off:

```bash
curl -k -m 10 -o /dev/null -w "%{http_code}\n" \
  --resolve prometheus.optimusprime.favarohome.com:443:51.154.63.53 \
  https://prometheus.optimusprime.favarohome.com/
```

`200` = real external exposure gated only by hostname obscurity → fix is a Traefik entrypoint
split or an IP-allowlist middleware on the `.optimusprime.` routers. `000`/timeout = the split
holds and this is LAN-only.

### ⛔ If you decide to add auth, these break in lockstep

Half-applying auth **blinds the monitoring** — the exact failure the watchdog exists to catch.
All four must move together:

1. **Grafana datasource ID 4** → `http://192.168.1.10:9092`
2. **`monitoring-watchdog.py` on bumblebee** → hits **both** `:9092` and `:9093`
   (`/usr/local/bin/monitoring-watchdog.py:46-47`)
3. **`config/prometheus/prometheus.yml`** `alerting.alertmanagers` → `192.168.1.10:9093`
4. **The blackbox probe** of `https://prometheus.optimusprime.favarohome.com` — would start
   returning 401 and firing an alert

### My recommendation

Cheapest meaningful hardening, in order:

1. **Fix `web.cors.origin`** — closes the browser drive-by path, breaks nothing.
2. **Put basic auth on Alertmanager** (`--web.config.file` with a bcrypt hash) and update
   consumers 2 and 3 — closes the unauthenticated-silence hole.
3. **Leave Prometheus read-open on the LAN** unless the phone test above comes back `200`.
   It is read-only, and authenticating it costs you four coupled changes for disclosure-only risk.

⚠️ Prometheus's `alerts.yml` is a **single-file bind mount** and `/-/reload` is 403, so any
config change needs a **container restart**, verified with `podman exec` — see
`project_bumblebee_wedge_20260821`.

---

## Decisions I need from you

1. **1a + 1b** — shall I **repurpose** the dead exporter into the 20 Hz sampling exporter? That
   is the only fix that removes the aliasing, and it reuses the timer that already exists.
   (Retiring the script instead is the alternative — but then the panel stays as it is.)
2. **1b** — split VRAM onto a byte axis, and add `max_over_time` as a partial improvement
   (⛔ not as the fix — measured 0.92 % vs 0.15 %, still zero 99 % of the time)?
3. **2** — rotate the Tautulli API key, or keep the existing one?
4. **3** — fix CORS and/or authenticate Alertmanager? And can you run the mobile-data test?
