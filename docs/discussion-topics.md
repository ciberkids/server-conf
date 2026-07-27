# Discussion Topics

Running queue of things to work through together. Newest additions go at the bottom unless
they're urgent. Move items to `## Done` (with the date and outcome) rather than deleting them,
so the reasoning stays findable.

---

## 1. Frigate NVR — false positives + video retention

**Added:** 2026-07-27

**The problem:** the AI object-recognition feature produces a lot of false positives. Two costs:
noise in the alerts, and wasted storage from recording events that aren't real. Separately, video
retention isn't configured, so footage accumulates without bound.

**Two goals, related but distinct:**

1. **Cut the false positives.** Improve detection accuracy so Frigate stops recording
   non-events.
2. **Set up retention.** Bound how long recordings and event clips are kept, so storage is
   predictable regardless of detection accuracy.

**Where to start when we pick this up:**
- Which cameras are worst, and what's being mis-detected as what (person vs. car vs. animal;
  shadows, headlights, rain, moving foliage, spiders on the lens at night are the usual
  suspects).
- Current `detect` / `objects` / `record` config per camera, and whether `zones` and
  `filters` (min/max `area`, `threshold`, `min_score`, `ratio`) are set at all — untuned
  defaults are the most common cause of exactly this.
- `snapshots`/`record` retain settings, plus whether `record.alerts` /
  `record.detections` retention differs from continuous recording.
- Actual disk consumption today and the growth rate, so retention can be chosen from real
  numbers rather than guessed.

**Context already known:** Frigate runs on bumblebee, GPU object detection via the
TensorRT build, reachable at `frigate.bumblebee.favarohome.com`. MQTT is enabled and it's
integrated into Home Assistant. Config is bind-mounted from
`/etc/containers/frigate/config`; recordings go to `/mnt/data/frigate` — verified, and
`/mnt/data` is the NFS mount from Optimus Prime (11 T, ~4.1 T free). So retention decisions
consume OP's array, not bumblebee's 70 G root — this is unrelated to the root-disk work done
2026-07-27.

---

## 2. Immich — why aren't all features enabled/available to every user?

**Added:** 2026-07-27

**The question:** not all Immich features appear to be enabled, or available to all users —
the example given is **folder creation**. Want to understand why, and enable what should be on.

**What to work out when we pick this up:**
- Which specific features are missing, and missing *for whom* — only for non-admin users, or
  for the admin account too? That distinction points at very different causes.
- Immich has per-user and server-wide controls that are easy to conflate:
  - **Admin → Settings → Features** (server-wide toggles: map, reverse geocoding, machine
    learning, smart search, facial recognition, trash, OAuth…)
  - **Admin → Users** per-account settings, including storage quota and whether the account
    has admin rights.
  - **Storage Template** — which governs how files are laid out on disk, and is the setting
    people usually mean by "folder creation". It's **off by default** and only an admin can
    enable it.
- Whether "folders" here means the **Folders view** (browsing the original directory
  structure, a comparatively recent feature that must be enabled and depends on how the
  library was imported) rather than the storage template. Worth pinning down which one is
  meant before changing anything.
- Version currently running vs. latest — some of these features simply don't exist in older
  releases, which would explain "not available" with no misconfiguration at all.

**Careful with:** enabling the Storage Template causes Immich to **move existing files** on
disk to match the new pattern. That's a bulk operation on the photo library, so it wants a
backup check and a deliberate decision, not a casual toggle.

---
