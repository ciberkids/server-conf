# Homelab fix list

**Opened:** 2026-09-03. Working list for the three items raised on 2026-09-03, with the
evidence behind each so a later session does not re-derive it.

Status key: 🔴 open · 🟡 needs your decision · ✅ done

---

## 1. 🔴 Optimus Prime GPU usage "always 0"

**Complaint:** the graphics-card usage sensor reads 0 permanently, including while a Plex
hardware transcode was deliberately forced.

🔑 **CORRECTED 2026-09-03 (twice). The diagnosis is not aliasing alone — the metric is
measuring the wrong engine.** Earlier in this same session I said "`gpu_busy_percent` is NOT
blind to VAAPI, it read 18% during the encode, so the fault is purely duty-cycle vs sample
rate." That was wrong, and the 18% was never the encoder.

### 1a. 🔴 `gpu_busy_percent` under-reports the video encoder ~5x — measured

A saturated `hevc_vaapi` encode, sampling DRM fdinfo `drm-engine-enc` against the gauge at the
same instants (9 x 3 s windows):

| | value |
|---|---|
| VCN encoder duty (`drm-engine-enc`) | **96.5 %** (min 85.4, max 100.0) |
| `drm-engine-gfx` duty | **0.0 %** |
| `gpu_busy_percent` | **18.0 %** mean |
| **under-report factor** | **5.36x** |

`drm-engine-gfx` at 0.0 % is the decisive part: the 18 % is not graphics work from the
pipeline, it is the SMU's partial, indirect accounting of a VCN block it cannot properly see.
An independent research pass reproduced this five times at 5–9x (42.4 % vs 8.9 %, 48.3 % vs
7–14 %, 30–31 % vs 8–12 %, ~50 % vs 5–10 %).

**Three compounding faults, not one:**
1. **Wrong engine.** `gpu_busy_percent` is the SMU's `average_gfx_activity`; VAAPI runs on the
   VCN block. `average_mm_activity`, the field that would cover VCN, reads `0x0000` on Navi 23.
   There is no VCN block in GRBM/GRBM2 and no device-level VCN counter in sysfs.
2. **Quantisation.** It is a firmware moving average on an integer 0–100 scale. At real-time
   1080p30 — what a Plex client actually consumes — the encoder needs ~2.53 ms/frame, so the
   gauge reads **~1**. Of the genuinely non-zero samples in the retained window, most are <= 3
   and many are exactly 1. **No sampling rate fixes quantisation.**
3. **Aliasing.** Prometheus point-samples every 30 s against 1–4 s bursts.

⚠️ **The aliasing claim needs narrowing too.** Plex writes exact ground truth to
`Plex Transcoder Statistics.log` (`<State startTime= endTime= slothMode=>`, ms resolution,
`slothMode=0` = transcoding). Measured over 2 sessions / 19.1 min: duty **14.33 %** aggregate,
ON bursts median 2.61 s and **80 % <= 4 s**, OFF gaps median 19.19 s, and
**P(a burst is ever sampled) = 11.1 % at 30 s**, 46.9 % at 5 s, 80.7 % at 1 s.
🔑 A throttled transcoder at 6.6x realtime *must* settle at duty ~ 1/6.6 = **15.2 %** to keep
pace; measured 14.33 %. That single number confirms the model. It also means
**point sampling is unbiased for total TIME and broken only for event RESOLUTION** — so
"aliasing" is the right word for burst *count* and the wrong word for total *time*.
⚠️ Those logs retain only ~4 h. Calibration instrument, not a monitoring source.

### 1b. 🔴 The broken exporter — a birth defect, not drift

`scripts/optimus-prime/amdgpu-metrics.sh` (deployed at `/usr/local/bin/amdgpu-metrics.sh`,
every 15 s via `amdgpu-metrics.timer`) reads `/sys/class/drm/card0/...`. **There is no `card0`**
— the RX 6600 is **card1**. `${VRAM_USED:-0}` turns the missing file into a literal,
plausible-looking `0`.

⚠️ **It has NEVER worked.** Commit `e9ced67` (2026-05-04) introduced it already reading
`card0` — ~4 months of three fake zeros. Nothing consumes them, and it is redundant with
node_exporter's `--collector.drm`.

⛔ **My "1c: the hardcoded card index is latent fragility" claim is weakly supported.** Over
15 d, the `card` label held **only `card1`** across **5 reboots and 4 kernel versions**. The
index is empirically stable here. The real lesson is different and worse:
- the script was **never verified once** after being written
- `amdgpu-metrics.service` has **no `OnFailure=`** (only 4 of 28 OP services do)
- there is **no textfile-staleness alert** — `alerts.yml` has 6 rules, none referencing
  `textfile`, `mtime`, `drm`, `gpu` or `amdgpu`
- **the git copy still says `card0`** — a host-only fix leaves the landmine

### 1c. ✅ Recommended fix — a monotonic counter, not faster sampling

🔑 **A monotonic nanosecond counter is immune to aliasing by construction — but only on the
READ side.** ⚠️ **Narrowed 2026-09-04:** `rate()` is **interval-independent for reading** (any
scrape interval recovers the exact time integral) and **interval-dependent for writing** (the
counter only advances for clients the *writer* observes alive). Measured extremes: a **3.40 s**
encode and a **12.3 s** encode that each fell entirely between two writes moved the counter by
**exactly 0.000000000 s — 100 % loss**. So the motivation for high-rate sampling shrinks
dramatically but does not vanish; it moves from the scrape to the write.

⇒ **Do NOT raise the timer to match the 30 s scrape.** A counter loses nothing by being written
more often than it is read, so 15 s *halves* tail loss versus 30 s. ⚠️ And the real cadence is
**~15.5 s, not 15 s** (`OnUnitActiveSec=15s` + `AccuracySec=5s` + runtime), so every tail-loss
bound quoted at "15 s" is ~3 % optimistic.

`scripts/optimus-prime/amdgpu-engine-metrics.py` is **written, reviewed and dry-run — NOT
deployed.** It walks `/proc/*/fdinfo/*`, filters on `drm-driver: amdgpu` + the discovered PCI
address, deduplicates by `drm-client-id` (12 fds -> 3 clients here; naive per-fd summation
over-counts 3–6x), and accumulates per-engine ns into a host-level total that survives client
exit. Dry-run output on OP:

```
amdgpu_engine_busy_seconds_total{card="card1",engine="enc"} 0.000000000
amdgpu_engine_busy_seconds_total{card="card1",engine="gfx"} 0.001478106
amdgpu_drm_clients{card="card1"} 3
```

🔑 It **derives card and PCI address from the driver** rather than hardcoding either, and
**exits non-zero rather than writing a zero** if no amdgpu card is found — because a fake zero
is indistinguishable from an idle GPU, which is the entire bug it replaces.

**Three hardening changes applied 2026-09-04, each measured:**
1. ⚡ **~8× faster.** It used to open and regex-scan **every** fdinfo in `/proc` (5,624 files on
   this host) to find the **17** fds that point at `/dev/dri`. Resolving the fd symlink first
   measured **0.642–0.707 s → 0.074–0.097 s** wall over 4 alternating runs, with
   **byte-identical** output on a frozen target 3/3. At the real ~15.5 s cadence that is
   **~4.3 % of a core → ~0.5 %**.
2. 🔴 **Explicit root guard.** ⛔ **`amdgpu_drm_clients` CANNOT serve as the canary** —
   measured with a root-owned encode live: root → `enc 1.021276318`, `clients 4`; non-root →
   `enc 0.000000000`, `clients 3`. **Three is a perfectly plausible number** (three desktop DRM
   clients genuinely exist), so the gauge cannot tell "root, GPU idle" from "non-root, blind to
   every rootful-podman transcode". Verified: the old version silently published
   `enc 0.000000000` as non-root; the new one exits 1 with a message.
3. **`atomic_write` refuses non-regular files.** ⚠️ **My own error, on the live host:** I pointed
   `AMDGPU_OUT` at `/dev/null` during testing, and `os.replace()` **destroyed the device node**,
   turning it into a 77-byte regular file and breaking every redirect on OP until
   `mknod -m 666 /dev/null c 1 3` restored it. The guard now refuses to replace anything that is
   not a regular file. Use `AMDGPU_OUT=-` to test. ✅ Device node restored and functionally
   verified (`crw-rw-rw- 1 3`, mode 666).

⚠️ **The units are in git too** — `systemd/units/optimusprime/amdgpu-metrics.{service,timer}` and
`scripts/optimus-prime/amdgpu-metrics.sh`, byte-identical to the deployed copies. So "change one
`ExecStart=` line" understates it: the change set is unit + script + panel **in git, then
deployed to the host** ([[feedback_deploy_quadlets_to_server]]).

🔑 **Reading `/proc/*/fdinfo` never touches the GPU** — so there are no power-management or
clock-gating side effects, unlike `amdgpu_top`'s GRBM performance-counter read. Worth knowing
before anyone worries about polling cost keeping the card awake.

Panel query once deployed:
```promql
rate(amdgpu_engine_busy_seconds_total{card="card1", engine="enc"}[$__rate_interval]) * 100
```

**Design constraints that shaped it (each one bites the obvious alternative):**
- `outputs.file`-style **appending breaks the textfile collector.** Duplicate `# HELP`/`# TYPE`
  families set `node_textfile_scrape_error=1` **and drop that file's metrics entirely**, silently
  — tested live. Hence one HELP/TYPE per family and `os.replace` for atomicity.
- node_exporter **rejects client-side timestamps for the whole file**
  (`collector/textfile.go:303`). A windowed-max design can never carry its own window's
  timestamp; counters are immune. Another reason to use a counter.
- **`/tmp` is tmpfs.** State lives in `/var/lib/amdgpu-engine-metrics/`, not `/tmp`. Losing it
  zeroes the counter, which Prometheus reads as a counter reset, so `rate()` stays correct —
  do not "fix" that later.

**Known limits, honestly:**
- **Tail loss on client exit:** work done between the last poll and a client's exit is lost.
  Measured on a 2.3 s encode polled at 3 s: **~82 % lost**. Bounded by (poll interval x duty)
  per client exit — negligible on a 45-min Plex session, severe for short jobs.
- **Requires root.** fdinfo of a root-owned process is unreadable as a normal user and yields a
  **silent zero** — the same failure class as the bug being fixed. `amdgpu-metrics.service`
  already runs as root.
- ⚠️ **Gating check, still open:** every `drm-engine-enc` measurement so far is our own
  `ffmpeg`, never Plex Transcoder. Plex's VAAPI path is ffmpeg-derived so it is very likely
  identical, but it has not been observed. Next time something transcodes:
  `sudo grep -l "Plex Transcoder" /proc/*/comm`, then check that pid's fdinfo for
  `drm-engine-enc`. (`Preferences.xml` does confirm the config:
  `HardwareAcceleratedCodecs="1"`, `HardwareDevicePath="1002:73ff...@0000:0b:00.0"`.)

### 1d. 🔴 The dashboard fix — and I fixed the wrong dashboard first

⚠️ **There are TWO GPU dashboards.** I found one and missed the other:

| dashboard | GPU panels | state |
|---|---|---|
| `Optimus Prime` | 1 (`AMD GPU`) | plotted VRAM as **% of the 8.5 GB pool** -> 2.8 % peak, flat |
| **`AMD GPU - Optimus Prime (RX 6600)`** (uid `1951df70-…`) | **7** | already plots VRAM **in bytes**; its 3 utilisation panels use the raw gauge |

The second is almost certainly the one being watched. Its `GPU Utilization`,
`GPU Utilization Over Time` and `GPU & Memory Busy %` panels all read the 5.36x-under-reporting
gauge — **re-windowing cannot fix them**, only the counter from 1c can.

`config/grafana/panels/optimusprime-amd-gpu-panel.json` fixes the *first* dashboard: VRAM/GTT in
**bytes on their own right-hand axis**, plus a burst-envelope series next to the raw sample so
the aliasing is visible rather than mysterious.

⛔ **Bug in my own first version, now fixed:** it hardcoded `[5m]`. Grafana requests
`step = range/maxDataPoints`, so at a 7 d view step = 605 s and a 300 s window covers half of
each step — **understating the 7-day peak by 1.7x**. `[$__interval]` is also wrong (at 6 h,
step = 22 s < the 30 s scrape, so windows come up empty). The correct form is
**`$__rate_interval`** = `max(step + scrape, 4 x scrape)`. Measured: 6 h -> 129 non-zero
(raw 42), 24 h -> 47 (raw 11), 7 d -> 30 / peak 15 (raw 2 / peak 2).

⚠️ **Retention caps this regardless:** 15 d at 30 s step is a hard Prometheus error
(`exceeded maximum resolution of 11,000 points per timeseries`), so even a perfect sampler is
discarded past ~4 days at fine step.

⚠️ **Blocked on credentials.** No Grafana API key, no service account, and `grafana.ini`
is entirely defaults — the admin password exists only as a hash in the `user` table. I will not
edit Grafana's live Unified Storage sqlite (`resource` / `resource_history` /
`resource_version` move together, and Grafana caches). Either give me a service-account token,
or paste the JSON via panel -> Edit -> JSON.

### 1e. ⚠️ Correction to my own statistics

**Prometheus retention is 15 d, not 30 d** (`storage.tsdb.retention.time=15d`, verified via
`/api/v1/status/runtimeinfo`). My "30-day" figures actually covered 15.46 days. Recomputed:

| | corrected |
|---|---|
| raw gauge > 0 | **0.161 %** of samples (72 of them) |
| `max_over_time([5m])` > 0 | 0.970 % |
| `max_over_time([1h])` > 0 | 3.189 % |

⚠️ And the figure is **unstable**: 65 of those 72 samples fall in the last 2.9 days, so the
clean 12.6-day baseline is 7 events = **0.019 %**. Honest reading: GPU transcoding is **rare and
clustered, n ~ 4 real sessions**, and the statistic is noisy because n is tiny.

🔑 **The strongest evidence is not statistical at all:** two encodes of known timing and known
load (10 s each, `drm-engine-enc` 47.65 %, 176 fps) produced **zero non-zero Prometheus samples**
— all four surrounding 30 s scrapes read 0.

⚠️ **Retention is the binding constraint for any long-horizon question.** "How much has Plex
used the GPU this quarter" is unanswerable in Prometheus at *any* sample rate. The cheap move
nobody proposed: **raise retention** — 836 MB/15 d becomes ~5 GB/90 d, one flag, existing
backend, no new agent. Cost: `prometheus.container` has no `Exec=` line, so it means a quadlet
edit + `daemon-reload` + container recreate.

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
| Grafana `.10:3000` | ⚠️ **mixed** | main API 401, but a **public dashboard bypasses auth entirely** — see 3d |

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

### 3d. 🔴 CORRECTION: Grafana is not fully authenticated — a public dashboard is wide open

I reported "Grafana ✅ 401 — no anonymous access". That was **wrong**. The main API does return
401, but Grafana's *public dashboards* feature bypasses authentication completely, and one is
enabled:

| | |
|---|---|
| Dashboard | **"Grid Import / Export & Energy Balance"** |
| `dashboard_public` row | `is_enabled=1`, `share=public` |
| `GET /api/public/dashboards/<token>` | **200** — full layout |
| `GET /public-dashboards/<token>` | **200** — renders |
| `POST /api/public/dashboards/<token>/panels/1/query` | **200** — **live data, queryable** |
| control: `GET /api/dashboards/home` | 401 |

So an anonymous caller with the token reads your grid import/export, solar production, import
cost and export revenue in CHF, self-consumption and autarky rates — **and can run the panel
queries**, not just view a snapshot.

🔑 **This may well be deliberate** — that is exactly what the feature is for, and public
Nextcloud is already a confirmed intentional exposure here. ⛔ **So I have not touched it.**
Two things to decide:
- Did you enable this to share your solar dashboard? If yes, nothing to do.
- The token is a **bearer credential with no login**, so if the `.optimusprime.` hostname is
  externally reachable (the still-unproven §3 question above), anyone holding the URL has it
  from the internet. That makes the mobile-data test matter more than it did.

To revoke, if unintended: Dashboard -> Share -> Public dashboard -> revoke.

## 4. ✅ "Why don't we use Telegraf?" — answered (⛔ CORRECTED 2026-09-04)

⛔ **The user pushed back and was right twice over:** *"i proposed telegraph for the gpu not for
the modbus, for the moment modbus work perfectly with node red."*
1. **Modbus stays on Node-RED.** The `inputs.modbus` material below is parked reference, **not a
   recommendation** — do not re-propose that migration. Answering a question about the GPU by
   pivoting to a different use case was a scope drift.
2. 🔴 **The claim "no fdinfo input plugin ⇒ it contributes nothing" was WRONG in its second
   half.** First clause true, second false. **`inputs.exec` + `data_format = "prometheus"` carries
   the metric fine** — verified end-to-end on OP with telegraf 1.39.3 under a live `hevc_vaapi`
   encode: metric name, `counter` TYPE, both labels and the full 9-decimal value all survive, so
   `rate()` works normally. The absence of a *specific* plugin never settles capability when a
   generic escape hatch exists.

**So: Telegraf CAN do it. It just shouldn't, because the transport it would replace is already
deployed — and after Modbus was ruled out, Telegraf has ZERO live triggers on this host.**

### On a straight sampler-vs-sampler comparison, Telegraf wins

Bench-tested on Optimus Prime (Telegraf 1.39.3):
- `interval = "50ms"` is honoured — measured **20.09 Hz** (236 samples in 11.75 s, first two
  timestamps exactly 50,000,000 ns apart, no "took longer to collect" warning)
- `aggregators.basicstats` genuinely turns that stream into max+mean per window
  (`count = 40` for a 2 s period at 50 ms)
- **There is no minimum polling interval** — no floor in `agent/agent.go`, `config/config.go` or
  `models/running_input.go`; the value goes straight to `clock.NewTicker`
- It also fixes two defects I was charging *against* it: real timestamps, and no
  stale-textfile failure class

So "why hand-roll a sampler when Telegraf exists?" has **no good answer**. My plan was worse.

⛔ Also worth retiring: the "adding Telegraf = backend sprawl like TimescaleDB" objection is a
**category error**. Telegraf with `outputs.prometheus_client` is a *collection agent*, not a
storage backend — it lands in the same TSDB as node_exporter. Not a valid reason to reject it.

### But it is the wrong tool for *this* job

- ⛔ **RETRACTED.** Telegraf has no *dedicated* fdinfo input plugin (true), but
  **`inputs.exec` runs the collector and parses its Prometheus output** — verified on OP under a
  live encode. Two conditions, both measured and non-negotiable: `metric_version = 2` on
  `outputs.prometheus_client` (at the v1 default the name is mangled to
  `prometheus_amdgpu_engine_busy_seconds_total`), and **`--pid=host` AND `SYS_PTRACE` — both,
  neither alone** (`--pid=host` alone → `Permission denied`; `SYS_PTRACE` alone → wrong PID
  namespace; without `--pid=host` the container sees **3 PIDs instead of ~900**, finds no amdgpu
  clients and publishes a plausible zero with `scrape_error` still 0). Plus
  `Entrypoint=telegraf`, since the default entrypoint dies under rootful podman and
  `--cap-add=NET_RAW` only fixes the crash while leaving Telegraf as **uid 999**, which cannot
  read fdinfo and would publish 0.
- **`inputs.amd_rocm_smi` is dead on arrival, three ways.** `rocm-smi` is not installed;
  **gfx1032 is absent from AMD's official ROCm support matrix** (gfx900/906/908/90a/942/950/
  1030/1100/1101/1200/1201 — no RX 6000-series consumer card anywhere on it); and mechanically
  it forks `exec.Command` **per collection** with 38 hardware-query flags and a 5 s timeout, so
  it cannot run at 20 Hz. Its field list has **no encode/decode field at all** — a working
  rocm-smi would still measure the wrong thing.
- **"Telegraf slots in for free" is false.** `outputs.file` opens with
  `O_RDWR|O_CREATE|O_APPEND` (`internal/rotate/file_writer.go:63`) — no `O_TRUNC`, no atomic
  replace — and the `prometheus` serializer re-emits `# HELP`/`# TYPE` on **every flush**. Fed
  that exact shape, node_exporter set `node_textfile_scrape_error` 0 -> 1 **and dropped that
  file's metrics entirely** while other `.prom` files kept working. Silently. The real route is
  `outputs.prometheus_client` (:9273, confirmed free), which needs a **new scrape target**.
- **A new scrape target is not cheap here.** `POST /-/reload` is 403 and
  `--config.auto-reload` was never set (tested live: the reload timestamp never moved over 48 s
  after an inert edit — `config.auto-reload-interval=30s` is a **decoy**). `prometheus.yml` is a
  **single-file bind mount**, so an edit must preserve the inode *and* be followed by a
  container restart. No `file_sd_configs` escape hatch exists.
- **The official image dies under rootful podman:**
  `setpriv: failed to execute telegraf: Operation not permitted`. Podman's default `CapBnd` has
  `SETFCAP` (so the entrypoint's `setcap cap_net_raw` succeeds) but lacks `NET_RAW` (so the
  following exec gets EPERM). Fix: `--cap-add=NET_RAW` or `--entrypoint=telegraf`.
- **Packaging:** not in Arch repos — AUR only (1.39.3, single maintainer) or a 333 MB container.
- Cost: ~1.75–2.27 % of a core, 29–37 MB RSS.

### Also relevant: the hand-rolled sampler was more expensive than I assumed

Polling `gpu_busy_percent` is **not** free at the proposed rate. amdgpu caches the SMU metrics
table ~1 ms, so back-to-back reads are cache *hits* (10.7 µs) while 50 ms-spaced reads are
*misses* needing a real SMU mailbox round-trip: **~926 µs each** (control: a regular file at the
same spacing is 55.6 µs). At 20 Hz that is **~1.9 % of one core — ~60x my assumption.**

### The verdict: repoint the timer you already have

| | textfile (recommended) | Telegraf as collector |
|---|---|---|
| new services | **0** | 1 |
| new containers / images | **0** | 1 container + a **locally-built ~570 MB** image |
| new packages | **0** | AUR-only (1 maintainer) or the container |
| new Prometheus scrape jobs | **0** | 1 |
| new listeners | **0** | `:9273` |
| privilege grants | **0** (the unit is already root) | `--pid=host` + `SYS_PTRACE` + entrypoint override |

Everything the textfile route needs is already running: `amdgpu-metrics.timer` → a root
`Type=oneshot`, node_exporter's textfile dir, and the `node-optimusprime` job already scraping
`:9100`. **New metric names appear inside a job that is already scraped ⇒ zero Prometheus config
changes.**

🔑 The decisive argument is not privilege or cost — it is **the image**. The official telegraf
image has no Python and `python3-minimal` is not enough (`import json` → `ModuleNotFoundError`),
so this needs a **locally-built** image. That falls outside `AutoUpdate=registry` — the property
every other exporter on OP has — and inside the `podman image prune -a` blast radius, which is
exactly what took Hermes down 1–5 Aug 2026 ([[project_hermes_image_pruned]]).

⚠️ Second argument: **an `inputs.exec` that fails forever never marks the unit failed.** Measured:
with `expiration_interval = "20s"` and the source removed, the `amdgpu` series went 5 → 5 → **0**
→ 0 while the container stayed `Up` and `go_gc_duration_seconds` kept serving. A `Type=oneshot`
exiting non-zero at least *can* fire `OnFailure=`.

### ⛔ Three of my own arguments, retracted

1. **"The 690 ms `/proc` walk is a hard interval floor."** False — it was self-inflicted. The
   collector opened and regex-scanned every fdinfo in `/proc` to find the handful that matter.
   Resolving the fd symlink first and only opening fdinfo when it points at `/dev/dri/*` measured
   (mine, 4 alternating runs): **0.642–0.707 s → 0.074–0.097 s wall**, CPU 0.51–0.70 s → 0.067–0.091 s
   — **~8× faster**, and **byte-identical** output on a frozen target 3/3 runs. On this host that
   is **5,624 fdinfo files versus 17 fds** pointing at `/dev/dri`. At the real ~15.5 s cadence the
   collector drops from **~4.3 % of a core to ~0.5 %**. Applied.
2. **"A Telegraf container with `--pid=host --cap-add=SYS_PTRACE` could read every
   `/proc/<pid>/environ`."** True but **not a marginal cost** — `amdgpu-metrics.service` already
   runs as host root with the full capability set and can already do all of that. Parity, not new
   exposure.
3. **"Prometheus config changes need a container restart."** Overstated. Prometheus reloads
   `prometheus.yml` **and** `rule_files` on **SIGHUP**, independently of
   `web.enable-lifecycle=false` — proven on a throwaway container of the same image
   (`prometheus_config_last_reload_success_timestamp_seconds` advanced,
   `prometheus_config_last_reload_successful 1`). In production that is
   `podman kill -s HUP prometheus`, ⚠️ **not yet exercised against the live container.** A genuine
   restart is still needed for **retention**, which is a process flag SIGHUP cannot pick up.

### 📌 PARKED — not requested: when Telegraf *would* become the right call

**Exactly one plugin: `inputs.modbus`.** It matches your hardware precisely —
`transmission_mode = "RTUoverTCP"` and plain TCP, register/request/metric configuration,
holding and input registers, FLOAT32-IEEE, and the `CDAB` mid-little-endian word order the
**Eastron SDM230** needs. Hand-writing a Modbus exporter is real work; this is config.

**The trigger:** when you decide to move energy metering off the Node-RED -> HA -> InfluxDB path.
Today the meters flow through HA, and the HA energy dashboard plus
`sensor.house_total_consumption_daily` consume that path — Telegraf -> InfluxDB bypasses HA and
breaks both. So it is a migration project with its own cost, **not a side effect of a GPU fix**.
Second trigger: three or more odd-protocol sources at once (Modbus + MQTT + SNMP).

**Non-triggers, measured:**
- **SNMP on the Dream Machine: not enabled.** `nmap -sU -p 161,162` -> `161/udp closed
  snmp port-unreach`, `162/udp closed snmptrap`. `inputs.snmp` unlocks nothing today.
- `inputs.ping` -> already covered by blackbox-exporter (55 targets, 2 jobs)
- `inputs.docker` -> already covered by podman-exporter on both hosts (:9882)
- smartctl gap on bumblebee -> cheaper as smartctl-exporter, the established pattern on OP

### And the alternative nobody names: Grafana Alloy

The Prometheus-shop answer to "why not Telegraf". Grafana 13.2.1 is already deployed;
`prometheus.exporter.unix` embeds node_exporter (drm collector included) and
`prometheus.scrape` sets **per-target intervals** — same data model, no second one. Honestly:
same container + quadlet cost as Telegraf, and Prometheus has no
`--web.enable-remote-write-receiver`, so it is not free either. Mentioned for completeness.

⛔ Confirmed closed: **no maintained consumer-AMD fdinfo exporter exists**
(`ROCm/device-metrics-exporter` is Instinct/K8s; `amd/amd_smi_exporter` is retired). Hence a
~100-line script rather than a dependency. `amdgpu_top v0.11.5` is already at
`/usr/bin/amdgpu_top` if you want an interactive look (**must run as root** — non-root silently
reports `Encode=0`).

## 5. 🔴 NEW — the Telegram alerting this homelab relies on drops ~1 in 4

Found while comparing failure signals for §1c. **This is not about the GPU** — it undermines
every `OnFailure=` alert on Optimus Prime.

Verified independently just now:

| | |
|---|---|
| `notify-failure@` instances in **`failed`** state right now | **2** (`zigbee2mqtt-mcp`, `zigbee2mqtt`) |
| journal, last 30 d | **21 errors vs 17 completions** |
| `After=network-online.target` | ⛔ **absent** |
| `Wants=` | ⛔ **absent** |
| `Restart=` / any retry | ⛔ **absent** |

Two instances failed **today at 05:02:58** — **2 min 58 s after the 05:00 `kernel-reboot.timer`
reboot** — with `telegram-send: Error: Connection timed out`. 🔑 **The unit makes exactly one
HTTP call, with no network-ready dependency and no retry, at the least reliable moment in the
host's day, and drops the alert silently on timeout.**

⚠️ This matters beyond itself: [[project_notify_failure_never_worked]] records 25 failures / 0
deliveries before the Aug-2026 fix. The fix worked, but the mechanism is still **lossy**, and
several arguments in §1c and §4 leaned on "systemd `OnFailure=` is the reliable signal". On this
evidence it is roughly **26 % lossy**.

**Suggested fix (not applied):** add `After=network-online.target` + `Wants=network-online.target`
to `notify-failure@.service`, and either a bounded `Restart=on-failure` with
`RestartSec=30`/`StartLimitBurst=3`, or route through the Prometheus/Alertmanager path instead —
which §3 notes is itself unauthenticated, so pick deliberately.

⚠️ **Related trap if you ever add `Restart=` to a notifying unit:** measured on throwaway units,
`Restart=always` + `OnFailure=` **without a start limit** leaves the unit in `activating` with
`NRestarts=9` — **never `failed`, so invisible to `systemctl --failed`** — while the `OnFailure`
sink fires **7 times in 12 s** (a Telegram per `RestartSec`). With
`StartLimitIntervalSec=30s`/`StartLimitBurst=3` it reaches `failed (start-limit-hit)` and fires a
bounded 4 times. **A start limit is mandatory, not optional.**

## Decisions I need from you

⛔ **Zero of the five real defects is a transport question, and all five survive either choice.**
Transport is one `ExecStart=` line; these are the things actually broken:
(a) live false zeros in Prometheus, (b) no `OnFailure=` on `amdgpu-metrics.service`, (c) no
staleness *or sanity* alert, (d) three panels on the watched dashboard reading the
5.36×-under-reporting gauge, (e) the git copy still says `card0`.

1. ⛔ **RUN THIS FIRST — it gates everything.** No `drm-engine-enc` measurement has **ever** come
   from Plex Transcoder; every one is our own `ffmpeg` or HandBrake. Your original complaint was
   Plex-specific. Next time something transcodes:
   ```bash
   sudo grep -l 'Plex Transcoder' /proc/*/comm          # find the pid
   sudo grep -H drm-engine /proc/<pid>/fdinfo/*         # must show a rising enc counter
   ```
   **If it fails, the zero-code answer wins:** delete the three fake zeros, answer "is Plex using
   the GPU" from Tautulli's `transcode_hw_full_pipeline` (already wired into Hermes, §2), and
   every transport argument above is void.
2. **Deploy the fdinfo counter?** Hardened and dry-run, **not deployed**. Change set = unit +
   script + panel in git, then deployed to the host. Includes adding the missing `OnFailure=` and
   a `StateDirectory=`.
3. 🔑 **The panel edit is what actually fixes your complaint — and it is blocked on a credential.**
   **No Grafana panel has referenced `amdgpu_*` since 2026-04-16.** Both GPU dashboards query
   `node_drm_*`, so the 0 you are looking at is the **sysfs DRM gauge**, and fixing the collector
   alone will **not** change what you see. I need a **Grafana service-account token** (or you
   paste the JSON). This is a harder blocker than anything in the transport debate.
4. **Add the sanity + staleness alert?** ⚠️ It needs the `absent()` half or it is not a safety net:
   `/etc/tmpfiles.d/node-exporter.conf` is a **`d` line only**, so after the 05:00 reboot the
   *directory* returns but `amdgpu.prom` does not — and an absent series never satisfies a `>`
   comparison.
   ```yaml
   - alert: AmdgpuMetricsStale
     expr: absent(node_textfile_mtime_seconds{file=~".*amdgpu.*"})
        or (time() - node_textfile_mtime_seconds{file=~".*amdgpu.*"} > 120)
     for: 5m
   ```
   ⚠️ Edit `alerts.yml` **in place** (single-file bind mount — rsync swaps the inode), then
   `podman kill -s HUP prometheus` and verify `prometheus_config_last_reload_successful == 1`.
   ⛔ **Note what freshness canNOT catch:** it is green *right now* while the file serves three
   fake zeros. A writer that runs fine and emits garbage is invisible to mtime — that is the
   failure that actually cost four months, and only the collector's `sys.exit()` addresses it.
5. **Raise Prometheus retention?** 15 d → 365 d ≈ **20.7 GB** against 3.5 TB free; the 5 new GPU
   series cost **8.3 MB/year**. ⚠️ Quadlet `Exec=` **replaces** the image CMD rather than
   appending, and `prometheus.container` has no `Exec=` line today, so all three flags must be
   given together:
   `Exec=--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=365d`
   This one is a genuine restart — retention is a process flag SIGHUP cannot pick up.
6. **§5 — fix `notify-failure@`?** It is ~26 % lossy and has no network dependency or retry.
   Independent of the GPU, and it silently weakens every other alert on the host.
7. **§2 — rotate the Tautulli API key**, or keep it?
8. **§3 — fix `web.cors.origin` and authenticate Alertmanager?** And can you run the mobile-data
   test?
9. **§3d — is the public "Grid Import / Export" Grafana dashboard intentional?** Anonymously
   readable *and* queryable right now.
