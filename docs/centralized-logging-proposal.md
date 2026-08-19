# Centralized logging — Grafana + Loki proposal

**Written:** 2026-08-19, in answer to "maybe in grafana and loki?" raised during a service sanity check.
**Status:** proposal. Nothing deployed. Numbers below are measured on this infrastructure, not estimates.

---

## Verdict

**Yes — Loki behind the existing Grafana is the right shape.** But do it in this order, because
**94% of what we would ship today is a single line of noise that shouldn't be logged at all:**

1. **Fix the two noise sources** (§2). Free, and independently worth doing.
2. **Then** deploy Loki (§4).

Shipping first would mean paying to store, index and query 5.7 million junk lines a day, and it
would hide the very signal the exercise is meant to surface.

---

## 1. What actually drove this: three near-misses caused by log gaps

This is not a nice-to-have. Each of these is already recorded in project memory:

| Incident | What the log gap cost |
|---|---|
| **Aug 13 coordinator wedge** | z2m's pre-wedge log dir had already rotated away, so the **error signature of the wedge is permanently unknown**. We cannot say whether it was the AF-dataRequest variant. |
| **Jul 22–26 pool-plug forensics** | z2m log rotation **ate four days** of the only evidence that could separate the competing sub-mechanisms. |
| **4-month Alertmanager outage** | Not a retention gap, but the same root problem: no single place where "did an alert actually get delivered?" is answerable after the fact. |

`project_z2m_radio_stuck_bootloader` already names the fix in its own words: *"Highest-value
follow-up: make watchdog outcomes durable — the fault is intermittent and the evidence currently
evaporates in 2 days."*

### One stale premise, corrected

Memory claims **OP journald retains only ~43 h**. **That is wrong.** Measured 2026-08-19:

```
oldest journal entry on OP:         2026-07-27T08:40  (23 days)
oldest journal entry on bumblebee:  2026-07-26T18:42  (24 days)
```

The 43 h figure was almost certainly derived from `zigbee-watchdog`'s *own* journal start (Aug 12,
when the unit was created), not from the journal's start. **journald is not the weak link.**

**The weak link is z2m's own file logger**, which is capped at 10 rotated directories:

```
z2m log dirs: 10  (at the cap)
oldest: 2026-08-13.05-01-36
newest: 2026-08-18.03-34-55     => only 6 days retained
```

That reframes the proposal: Loki's value here is **less about journald retention** and more about
(a) capturing z2m's file logs before rotation eats them, (b) making watchdog verdicts durable and
queryable, and (c) cross-host correlation in one place.

---

## 2. Prerequisite: kill the noise first

### 2a. `podman.service` access log on Optimus Prime — 5.7 M lines/day

**This is the single biggest finding of the whole exercise.** Measured on OP:

```
journal entries, 1 h sample:  253,734   => 6.1 M/day
   of which podman.service:   239,158   => 5.7 M/day  = 94%
```

Every line is Traefik's container-discovery provider polling the podman compat API:

```
podman[3349]: @ - - [19/Aug/2026:11:19:23 +0200] "GET /v1.44/containers/<id>/json HTTP/1.1" 200 7364
```

**This is the exact fault that filled bumblebee's root disk in July 2026** (17 G unrotated
`/var/log/messages`, 92% of it this same access log). It was fixed there on 2026-07-27 with a
drop-in — and **the fix was never applied to Optimus Prime.**

```
bumblebee: /etc/systemd/system/podman.service.d/log-level.conf   ✅ present
OP:        /etc/systemd/system/podman.service.d/                 ❌ does not exist
```

OP is *worse* than bumblebee was, because discovery polls every container and OP runs **54** to
bumblebee's 21.

The packaged unit is byte-identical on both hosts, so **the bumblebee drop-in works verbatim on OP**:

```ini
[Service]
Environment=LOGGING="--log-level=warn"
```

> ⚠️ **Applying it cycles `podman.service`, which silently kills Traefik's event stream.** Traefik
> keeps serving its existing routing table, so everything looks fine while it stops learning about
> container changes — then a later container restart 502s. **`systemctl restart traefik.service` must
> be the last step,** and it must be verified against backend IPs, *not* router count. This exact
> trap fired on 2026-07-27 when this same drop-in was applied to bumblebee.
> See `feedback_restart_traefik_after_podman_cycle`.

**Why it matters even though OP's disk is fine** (root 40% used, 262 G free — this is *not* a disk
emergency):

- The same 4 GB journal budget would hold roughly **a year** of real logs instead of 23 days.
  That directly closes the forensic blind spot above.
- `journalctl --since "24 hours ago"` **times out after 2 minutes** on OP today. Log analysis is
  effectively impractical at 70 entries/second.
- Loki would otherwise index 5.7 M useless streams/day forever.

### 2b. Two container error-log floods — 99.9% one signature each

| Container | ERROR lines / 24 h | Distinct real causes |
|---|---|---|
| `home_assistant` | 15,454 | **1** (accounts for 15,432) |
| `firefly-iii` | 5,672 | **1** (accounts for 5,671) |

**Home Assistant — 4 pool-sensor setpoints outside their declared range.** Four MQTT `number`
entities are rejected on **every single publish**, 3,858 times each per day (~every 22 s):

```
Invalid value for number.pool_sensor_orp_min:            -1.0  (range 0.0 - N)
Invalid value for number.pool_sensor_orp_max:            -1.0  (range 0.0 - N)
Invalid value for number.pool_sensor_free_chlorine_max:  -1.0  (range 0.0 - N)
Invalid value for number.pool_sensor_ph_max:             1400  (range 0.0 - 14.0)
```

Confirmed against z2m's own state for `0x70d07efffe432949`:
`orp_min=-1  orp_max=-1  free_chlorine_max=-1  ph_max=1400`

These are the device's **alarm setpoints, not its measurements** — `-1` is the sensor's
"threshold disabled" sentinel, and `ph_max=1400` is a ×100 scaling mismatch (14.00 unscaled).
The actual pool readings are all fine (`orp=1, salinity=6290, tds=5876, free_chlorine=0`).
**Zero functional impact — pure noise, and it would bury a real HA error.**

**Firefly III — entirely self-inflicted by our own monitoring.** All 5,671 lines are Firefly
logging an unauthenticated page view at `ERROR` level, from exactly two healthy sources:

```
10.89.2.1 "GET / HTTP/1.1" 302  "Blackbox-Exporter/0.28.0"   <- our uptime probe, every 30s
::1       "GET / HTTP/1.1" 302  "curl/8.14.1"                <- its own HealthCmd, every 30s
```

Nothing is wrong. Firefly's log level for anonymous requests is simply miscategorised. Best fix is
to point the blackbox probe at `/login` (already returns 200) so it stops generating ERRORs.

> This is the mirror image of the lesson in `feedback_error_log_is_not_a_success_log`: there, a
> quiet error log was wrongly read as success. Here, **21,000 loud error lines/day represent zero
> faults.** Neither direction is trustworthy without deduping into logical events first.

---

## 3. What is genuinely worth shipping

After §2, OP's real signal drops to roughly **350 k entries/day** — a completely tractable volume.

| Source | Why | Currently lost after |
|---|---|---|
| **z2m file logs** (`/mnt/data/docker_persistent/zigbee2mqtt/data/log/*/log.log`) | The only record of coordinator wedges and Zigbee routing failures. **The actual data-loss problem.** | **6 days** (10-dir cap) |
| **journald, both hosts** | Unit failures, OOM, SELinux denials, boot races | 23–24 days |
| **Container stdout, both hosts** | App-level errors (HA, Frigate, paperless, n8n) | podman's own rotation |
| **Watchdog verdicts** (`zigbee-watchdog`, `monitoring-watchdog`) | Both already log a *positive* line every run. Makes "did it fire, and did recovery work?" answerable months later. | journald only |

---

## 4. Proposed architecture

```
  OP journald ─┐
  OP containers┤
  z2m log files┤──> Grafana Alloy (OP) ──┐
               │                          ├──> Loki (OP, /mnt/data) ──> Grafana (existing)
  bb journald ─┤                          │
  bb containers┴──> Grafana Alloy (bb) ───┘
```

**Use Grafana Alloy, not Promtail.** Promtail reached end-of-life in March 2026; Alloy is the
supported successor and reads journald, files and container logs in one agent.

### Placement: Loki on Optimus Prime, `/mnt/data`

Non-negotiable. **Not bumblebee** — its root LV is 70 G and hit 90% in July over precisely this
problem (logs). It sits at 65% / 25 G free today. OP has 262 G free on root and multi-TB arrays.

This does mean Loki shares a host with most of what it observes. That is an accepted trade-off:
the cross-host dead-man's-switch (`monitoring-watchdog` on bumblebee, HA push transport) already
covers "is OP's monitoring alive?", and it must **stay** on bumblebee for exactly that reason.

### Sizing (from measured volume, post-§2)

| | entries/day | ~bytes/day | 90 d retained (compressed ~10×) |
|---|---|---|---|
| OP, after noise fix | ~350 k | ~40 MB | ~1.1 GB |
| bumblebee, after §5 fix | ~250 k | ~30 MB | ~0.8 GB |
| z2m file logs | — | ~9 MB | ~0.3 GB |
| **Total** | | **~80 MB/day** | **~2–3 GB** |

**90 days is the recommended retention** — it comfortably spans the observed 4–18 day gap between
coordinator wedges, so a recurrence can always be compared against its predecessors. Even a year
would be ~10 GB, which is nothing on `/mnt/data`. Set `retention_enabled: true` with the compactor;
Loki keeps data forever by default and that is how these things quietly become the disk problem
they were meant to solve.

### Quadlet notes for this estate

- OP quadlet, so **no `:Z`** on volumes; `AutoUpdate=registry`; route via Traefik as
  `loki.optimusprime.favarohome.com`.
- **Do not give Loki its own `.network`** — Traefik on OP cannot reach `10.89.x` from `10.88.0.18`.
  Keep it on the default `podman` network, or use the file provider on a published port.
  See `reference_traefik_routing_optimusprime`.
- Alloy on bumblebee needs SELinux `:z`/`:Z` and, if it reads `/var/log`, an appropriate label —
  and any helper script must live in **`/usr/local/bin`** (`bin_t`), never `/home/matteo`
  (`container_file_t`, which `init_t` cannot exec). That mistake is live on bumblebee right now (§5).
- Add `loki.optimusprime.favarohome.com` to the **blackbox target list** — 15 routed services
  currently have no external probe (§5), and it would be ironic to add a 16th.

### What this does *not* replace

Loki is for **retrieval and correlation after the fact**. It is not an alerting layer —
Prometheus + Alertmanager already do that well, and `monitoring-watchdog` covers the
watch-the-watcher case. Loki-side alerting rules can come later, if ever.

---

## 5. Related findings from the same sanity check

Independent of Loki, but they came out of the same sweep and are logged in
`docs/discussion-topics.md`:

1. **`notify-recovery-check.service` on bumblebee has never once run** — `203/EXEC`,
   `container_file_t` on `/home/matteo/notify-recovery-check.sh`. **6,706 failure events** in the
   journal. Identical to the bug fixed on 2026-08-05 for `notify-failure.sh`; this sibling script
   was missed. Recovery notifications have never been delivered on that host.
2. **15 Traefik-routed hostnames have no blackbox probe**, including **every** internet-facing
   `*.public.favarohome.com` service.
3. **`nextcloud.public.favarohome.com` returns 400 "Access through untrusted domain"** — routed and
   internet-exposed, but not in Nextcloud's `trusted_domains`.
4. **Boot-time Telegram notifications race the network.** `telegram-boot-notify.service` failed at
   the Aug 13 boot with `httpx.ConnectError` *despite* having `After=network-online.target` —
   that target does not imply working DNS.
