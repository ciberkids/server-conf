# Incident report — bumblebee unresponsive 2026-08-21 09:19 → 2026-08-22 11:54

**Duration:** 26 h 35 min · **Impact:** all 15 bumblebee HTTP routes down · **Data loss:** none
· **Reboot required:** no · **Root cause:** root filesystem reached 100 %

---

## 1. Summary

A GitLab CI job pulled multi-gigabyte container images onto bumblebee's **70 GB root
filesystem**, consuming the remaining 16 GB in about 19 minutes. At 100 % full, every process
that needed to write anything failed — including `sshd` session setup — while the **kernel
remained completely healthy**. The host therefore answered ICMP and completed TCP handshakes
while being unable to serve a single request, which is why it looked like a hardware fault.

It released itself when the CI build container was killed and its image layers were reclaimed,
freeing enough space for userspace to function again.

**Nothing was wrong with the hardware.** The NVMe, the arrays, and the network were fine
throughout.

## 2. Impact

| | |
|---|---|
| Services down | frigate, paperless, n8n (incl. public), ollama, open-webui, opencode, comfyui, searxng, heimdall, filebrowser, stirling-pdf, cloud-drive-sync, traefik, cockpit, gitlab-runner |
| Real-world consequence | **no camera recording for ~26 h** (Frigate) |
| Hermes | offline (Telegram assistant runs on bumblebee) |
| House automation | **unaffected** — HA, Zigbee2MQTT and the SLZB-06 all run on Optimus Prime |
| Alerting | fired correctly at 09:19 (`ServiceDown`, `for: 2m`), 0 notification failures |

## 3. Timeline (all times CEST)

| when | what |
|---|---|
| **08-21 05:00:22** | Optimus Prime begins its scheduled kernel-update reboot |
| 08-21 05:02:24 | bumblebee: `frigate.recordi` and `ffmpeg` blocked >122 s — hard NFS mounts stalled. **122 s before 05:02:24 is 05:00:22, to the second** |
| 08-21 05:03:06 → 05:03:24 | `nfs: server 192.168.1.10 not responding` → `OK`. **Self-healed in 18 s.** Not the cause of this incident |
| 08-21 09:10:21 | gitlab-runner starts job `16025087357` (`mobile-flohmihelper`), pulls `ghcr.io/cirruslabs/flutter:3.41.0` |
| 08-21 09:00 | root filesystem: **16.15 GB free** |
| 08-21 09:15 | root filesystem: **5.78 GB free** — 10.4 GB consumed in 15 min |
| 08-21 09:16:25 | last successful Frigate event (clip delivered to Telegram) — still working |
| 08-21 09:18:27 | `node-exporter: write tcp …->192.168.1.10: broken pipe` |
| **08-21 09:19** | root hits 0 %. All 15 routes DOWN. Alertmanager fires |
| 08-22 00:57 | ICMP stops; host drops off even at layer 2 (ARP `FAILED`) |
| 08-22 01:21 → 11:31 | `nfs: server not responding` every ~10 min — a **symptom** of the lost network, not a cause |
| **08-22 11:54:23** | `nfs: server 192.168.1.10 OK`; CI build container `Exited (137)`; space reclaimed; sshd answers |
| 08-22 ~12:10 | ~20 GB reclaimed by hand; root 100 % → **71 %** |

## 4. Root cause

`/` is a **70 GB LVM volume** holding `/var/lib/containers` (61 GB at peak). Container image
storage has no quota and no headroom monitoring. A single CI job pulling a Flutter/Android
toolchain image was enough to exhaust it.

**At 100 % full, a Linux host fails in a very specific and misleading way:**

- the **kernel** needs no disk to answer ICMP or complete a TCP handshake → the host looks alive
- **`sshd`** cannot write session state or run PAM → connections die *during banner exchange*
- **Traefik, podman, journald** cannot write → every service fails
- nothing gets logged, **because logging requires writing**

That combination — pingable, TCP-accepting, totally unresponsive — is what made this look like a
storage-controller or hardware failure for a full day.

## 5. What released it

The CI build container was killed (`Exited (137)` = SIGKILL) and its image layers were
reclaimed. That freed enough space for userspace to write again, and the host recovered on its
own with **no reboot** — `uptime -s` remained `2026-08-19 03:49:10` throughout.

The exact killer is not pinned. The job carried `job-timeout=1h0m0s` and started at 09:10, so a
runner-side abandonment is the most likely candidate, but this is **not proven**.

## 6. Why diagnosis took a day — three wrong turns worth recording

1. **"Storage controller stall / failing NVMe."** Fitted every remote symptom. Refuted by SMART
   (0 media errors, 100 % spare, 4 % used) and by dmesg (no nvme timeouts/resets, XFS clean).
2. **"The kernel died"** — inferred from ARP `FAILED` at 00:57. Refuted by `uptime -s`: the
   kernel ran continuously for the entire episode.
3. **"Hard NFS mounts + OP's reboot."** The most seductive one: the 122-second hung-task
   timestamp matches OP's reboot *to the second*, Frigate really does record to an NFS mount,
   and all nine mounts really are `hard`. **But the NFS transition log refutes it** — NFS
   recovered at 05:03:24 and stayed healthy through the 09:19 wedge, with no further event until
   01:21 the next day.

🔑 **The decisive evidence lived on another host.** bumblebee's own journal contains no ENOSPC
errors *because journald could not write them* — a full disk erases the record of its own
cause. The disk-fill curve came from **Prometheus on Optimus Prime**. On this infrastructure,
the only telemetry that survives a host's failure is telemetry stored elsewhere.

## 7. Contributing factors

- **No disk-space alerting on bumblebee.** 16 GB free was already tight and nothing said so.
- **CI shares the root filesystem with production containers.** A build job can starve Frigate,
  paperless and Traefik.
- **No quota on container storage**, and `AutoUpdate=registry` steadily accumulates dangling
  layers — 14 of them (~20 GB) had built up.
- **Alert repeat noise**: `repeat_interval: 4h` produced identical 15-line bursts for 26 h.

## 8. Actions taken

- Reclaimed ~20 GB: `podman container prune -f` + `podman image prune -f`. Root 100 % → **71 %**.
  ⚠️ **Deliberately NOT `podman image prune -a`** — `localhost/hermes-agent:latest` is built
  locally with no registry to re-pull from, and `--all` removes unused *tagged* images too. That
  exact command destroyed it once before. Verified present and `hermes.service` active after.
- Cleared a stale `dnf-makecache` failure; `systemd is-system-running` = **running**.
- Expired both Alertmanager silences; **54/54 blackbox targets green**, 0 alerts firing.
- Raw diagnostic capture preserved at `reports/bumblebee-nfs-wedge-20260822.txt`.

## 9. Recommendations

**Prevents recurrence (highest value first)**

1. **Alert on free disk space** — bumblebee had none. `node_filesystem_avail_bytes` is already
   scraped; a rule at <15 % and <5 % would have given hours of warning.
2. **Move CI off the root filesystem.** `/home` has 347 GB free and 11 % used. Pointing
   gitlab-runner's builds and container storage there removes the shared-fate problem entirely.
3. **Cap or regularly prune container storage** — a weekly `podman container prune -f` +
   `podman image prune -f` (never `-a`) timer.

**Separate latent risk, found during this investigation and still open**

4. **Frigate records to `/mnt/data/frigate`, which is a `hard` NFS mount from Optimus Prime**,
   and OP reboots itself unattended for kernel updates. On 08-21 that stalled Frigate for ~18 s
   and it self-healed — but a longer OP outage would wedge bumblebee the same way this incident
   did. An NVR should not need another host to be up to write a frame.
5. **Install smartctl-exporter on bumblebee** — it is the only host with no disk telemetry, which
   is why the NVMe stayed a suspect for a day. Also worth watching: the NVMe read **64 °C** under
   load (53 °C idle).
