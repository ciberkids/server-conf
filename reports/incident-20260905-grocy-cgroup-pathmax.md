# Incident: grocy dead 17.5 h — an upstream rename that ate PATH_MAX

**Date:** 2026-09-05 · **Host:** Optimus Prime · **Duration:** 05:01 → 22:45 CEST (~17.7 h)
**Status:** ✅ RESOLVED — service active, healthy, 0 restarts, `systemctl is-system-running` = `running`

---

## What the user saw

"Some services failed to start." One unit was failed: `grocy.service`
(`Result: start-limit-hit`). Monitoring had been telling them all day — see *Alerting* below.

## Root cause — a two-stage failure

### Stage 1: an upstream rename broke the app (the trigger)

`AutoUpdate=registry` pulled `lscr.io/linuxserver/grocy:latest` → **v4.7.1-ls339**
(build-date 2026-09-04T18:23:20). That release **moved the auth middleware into an `Auth\`
sub-namespace**, and the on-disk config still pointed at the old path:

```
HTTP/1.1 500 Internal Server Error
Invalid setting in config.php: Configured AUTH_CLASS
"Grocy\Middleware\DefaultAuthMiddleware" does not exist
```

| | |
|---|---|
| `/config/data/config.php` line 86 | `Grocy\Middleware\DefaultAuthMiddleware` |
| v4.7.1 `config-dist.php` line 93 | `Grocy\Middleware\`**`Auth\`**`DefaultAuthMiddleware` |

Every request returned **500**. The healthcheck is `curl -sf …`, and `-f` fails on 5xx ⇒
the healthcheck failed forever ⇒ `HealthOnFailure=restart` restarted the container **in place**,
every ~2.1 min (60 s start period + 3 × 30 s retries), **498 times**.

### Stage 2: 🔑 the restarts ate PATH_MAX (why it went from degraded to *dead*)

This is the novel part and it is **not grocy-specific**.

Quadlet generates `podman run … --cgroups=split`, which splits the unit cgroup into
`runtime/` + `libpod-payload-<id>/`. On an **in-place podman restart** the split is applied
again **relative to the cgroup podman is already in** — which is already `…/grocy.service/runtime`.
So **every in-place health restart appends one more `runtime/` level.**

Measured at failure time:

| | |
|---|---|
| nested `runtime/` levels | **498** |
| cgroup path depth | **504** components |
| longest cgroup path | **4,025 bytes** |
| **Linux `PATH_MAX`** | **4,096 bytes** |

At 4,025 bytes the path plus a leaf filename no longer fits. First conmon lost its watch:

```
conmon: Failed to add inotify watch for
/sys/fs/cgroup/system.slice/grocy.service/runtime/runtime/… (×498) …/memory.events
```

Then **systemd itself could not fork its executor into that cgroup**:

```
grocy.service: Failed to spawn executor: Device or resource busy
grocy.service: Failed to spawn 'start' task: Device or resource busy
grocy.service: Failed with result 'resources'
… restart counter 2,3,4,5,6 within one second …
grocy.service: Start request repeated too quickly.
grocy.service: Failed with result 'start-limit-hit'.
```

⇒ `Device or resource busy` on `spawn executor` is **not** a busy device. It is
**a cgroup path that has outgrown PATH_MAX.**

**The arithmetic, so it can be predicted:** base path ≈ 113 bytes, each level adds
`runtime/` = 8 bytes ⇒ `(4096 − 113) / 8 ≈ 498` restarts. Which is exactly what happened.

### Who else is on this trajectory

24 containers on OP set `HealthOnFailure=restart`. Nesting is **1** for all of them **except**:

| service | nested levels | longest path |
|---|---|---|
| `grocy` (before fix) | **498** | 4,025 B |
| **`jellyfin`** | **18** | 260 B |
| everything else | 1 | ~120–132 B |

⚠️ **`jellyfin` has the same accumulation, 18 restarts in.** Far from the wall, but the counter
**only resets on a full `systemctl restart`**, never on its own.

---

## The fix

1. **Backed up** `config.php` → `config.php.bak-authclass-20260905`.
2. **Verified the fix in isolation first** — rsynced the 17 MB config to a throwaway copy, ran a
   second container on port 9284, patched only the copy, confirmed **HTTP 302** (grocy's login
   redirect) and that the *exact* healthcheck command exits **0**.
3. **Patched the real config** — one line, `AUTH_CLASS` only, diff verified as a single-line change.
4. **Removed the 499 stale cgroup dirs** (verified 0 processes inside first) with `rmdir`,
   deepest-first. ⛔ Never `rm -rf` on cgroupfs.
5. `systemctl reset-failed` + `start`.

### Verification

| check | result |
|---|---|
| unit | `active` |
| container health | **healthy** |
| HTTP `:9283` | **302** (login redirect) |
| Traefik route | **302** |
| restarts over a 3-minute watch | **0** (was ~1 per 2.1 min) |
| cgroup path | **121 bytes**, 1 nested level (was 4,025 / 498) |
| `systemctl is-system-running` | **running** (was `degraded`) |

⚠️ The first `systemctl start` still reported *"failed because of unavailable resources"* — a
leftover EBUSY — then succeeded on the `Restart=always` retry. That fired one more
`notify-failure@` Telegram at 22:43, which was caused by this repair, not by a new fault.

---

## Alerting worked — this was not a monitoring failure

| | |
|---|---|
| `ServiceDown` (`probe_success == 0`) | **fired ~17.9 h** |
| `probe_success` mean over 18 h | **0.004** (down 99.6 % of the day) |
| `alertmanager_notifications_total{integration="telegram"}` | **7** |
| `alertmanager_notifications_failed_total` (all integrations) | **0** |
| `notify-failure@grocy` systemd → Telegram | delivered (`Finished`) |

With `repeat_interval: 4h` over ~18 h that is ~7 messages. The pipeline did its job end to end.

## 🔑 The monitoring gap that *does* exist

`podman_container_health` is exported (`0=healthy 1=unhealthy 2=starting`) and would have caught
this at **05:03 instead of 22:33** — but only with the right comparison:

| state over the 18 h | share of day |
|---|---|
| `starting` (2) | **100 %** |
| `unhealthy` (1) | **3.2 %** |
| `healthy` (0) | **0 %** |

⛔ **A container restarting every ~2 min spends essentially its whole life in `starting`, never
settling into `unhealthy` — so an alert on `== 1` would basically never fire.** The correct rule
is "not healthy for a while":

```yaml
- alert: ContainerNotHealthy
  expr: podman_container_health != 0 and podman_container_health != -1
  for: 15m
  labels: { severity: warning }
  annotations:
    summary: "{{ $labels.name }} on {{ $labels.instance }} has not been healthy for 15m"
```

(`-1` = no healthcheck defined — excluded, or it fires on ~half the fleet.)

A companion rule would have caught stage 2 before it was fatal — but cgroup depth is not
exported by anything today, so the cheap proxy is the restart rate:

```yaml
- alert: ContainerRestartLooping
  expr: increase(podman_container_exit_code[1h]) > 10   # verify this counter behaves first
  for: 30m
```

⚠️ Edit `alerts.yml` **in place** (single-file bind mount — rsync swaps the inode and the
container keeps reading the old file), then `podman kill -s HUP prometheus` and confirm
`prometheus_config_last_reload_successful == 1`.

---

## Lessons

1. 🔑 **`Device or resource busy` from `Failed to spawn executor` means the cgroup path has
   outgrown PATH_MAX** — not a busy device, not a failing disk. Check
   `find /sys/fs/cgroup/system.slice/<unit> -type d | awk '{print length}' | sort -n | tail -1`.
2. 🔑 **`HealthOnFailure=restart` is a slow-acting landmine under quadlet's `--cgroups=split`:**
   ~498 in-place restarts and the unit becomes unstartable. It is silent until it is fatal, and
   the counter never resets by itself.
3. ⚠️ **`AutoUpdate=registry` on `:latest` will eventually pull a release that breaks your
   config.** The blast radius here was one app; the detection was good, the *recovery* was not
   automatic, and the app spent 17.5 h in a restart loop that made things worse rather than
   holding still.
4. ⚠️ **A restart loop looks alive to freshness checks.** The unit was `active` for 17.5 h.
5. ⛔ **Diagnostic trap I walked into:** I mounted `/config` **read-only** to be "safe", which
   made linuxserver.io's nginx/php-fpm fail to start at all — **HTTP 000**, a *different* symptom
   from the real fault's HTTP 500. I nearly concluded "the image is broken". These images must
   have a **writable** config; test against an rsynced throwaway copy, never `:ro`.
6. Recording it as fixed is not the same as it staying fixed: the proof is **0 restarts over a
   3-minute watch**, against a known prior cadence of one per 2.1 min.

## Open

- **`jellyfin` at 18 nested levels** — harmless today, resets only on a full restart. Worth a
  one-off `systemctl restart jellyfin` and then leaving it alone.
- **Neither alert rule above is deployed.** Both need the in-place `alerts.yml` edit + SIGHUP.
- **`config.php` lives in the volume, not git** (same as Nextcloud's) — so this fix has nothing
  to commit beyond this report. If grocy's config should be tracked, that is a separate decision.
- The stale comment on line 84 of `config.php` still names the old class path. Harmless, but it
  will mislead the next person who reads it.
