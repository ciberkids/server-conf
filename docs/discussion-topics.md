# Discussion Topics

**A queue, not an archive.** Somewhere to park a topic that comes up while we're working on
something else, so neither thread gets dropped. Once a topic has been discussed, it comes **out**
of this file — the findings go to memory or `docs/`, and the entry is deleted.

Empty means nothing is queued.

## How to add one

```markdown
## <short title>

**Added:** YYYY-MM-DD

What was actually asked, in the asker's own words where possible.

**What to look at when we pick this up:** the specific config, host, file or metric to go
check — this is what makes the entry actionable later instead of just a reminder.
```

Verify factual context before writing it down. Entries get read as established fact in later
sessions, so an unverified guess becomes a wrong premise.

---

## Heating's per-day colour bands are scaled for a metric 4x bigger than heating

**Added:** 2026-08-06

Came up while fixing the all-white graphs on the Averages view of Home Info. The per-day
`color_threshold` bands for heating are 5 / 10 / 20 / 30 / 40 kWh — inherited verbatim from the
Consumption Graphs view, which copied them from the *grid import* card. But heating never exceeds
~10 kWh/day (Jun–Aug 2026 range: 0.6–9.9), so only the bottom two of five bands are ever used and
the chart reads as a single flat teal. Grid import genuinely spans 27–43 kWh/day, so the bands are
correct *there*.

**What to look at when we pick this up:** `dashboard-solar` view index 8 (`averages`) and view
index 5 (`consumption-graphs`), the `color_threshold` arrays on the two
`sensor.heating_energy_meter_total_import_power_daily` series. Something like 1 / 2 / 4 / 7 / 10
would actually use the full palette. Same question applies to the heating card on Consumption
Graphs, which has the same flat-teal look for the same reason.

## sensor.house_total_consumption_daily "Avg / month" renders N/A

**Added:** 2026-08-06

Noticed while fixing the Averages view graphs, not caused by that change. On the "House total
consumption - 3-month averages" card the *Avg / month* header state shows `N/A`, while the *Avg /
day* on the same card (41.1 kWh) and the monthly-trend card next to it (82 kWh) both resolve fine.

Best guess is that `group_by: {func: avg, duration: 90d}` wrapped around a
`statistics: {type: change, period: month}` series returns nothing when only one *partial* month
exists — the sensor was created 2026-08-05, so August is all there is. If that's right it
self-resolves once a full month closes (Sept 1), and the honest fix until then is to hide the state
rather than show N/A. The car-charging card computes the same statistic fine and it has three
months of data, which is consistent with that theory but doesn't prove it.

**What to look at when we pick this up:** `dashboard-solar` view index 8, section 2, first
apexcharts card, `series[1]`. Cheapest test is whether it starts resolving on its own after
1 Sept 2026 — if it does, nothing to fix.

## Area/floor registry oddities found while scoping the 3D floorplan

**Added:** 2026-08-10

Surfaced while inventorying entities for the interactive floorplan project. None of these are
broken today — they're cosmetic or latent — and renames break consumers (dashboards, automations,
voice aliases), so nothing was touched. Flagging for a decision:

1. **`area_id: mia_s_room` is named "Aria's Room".** The slug is stale from a previous name. Renaming
   the *area* is safe-ish, but the `area_id` itself is what automations and templates reference —
   worth grepping before changing.
2. **Floor `"Ground  Floor"` has a double space** in its display name (`ground_floor` id is fine).
   Purely cosmetic, one-field fix.
3. **A `no_floor` pseudo-floor holds 3 areas**: `Home`, `Stairs Down`, `Stairs up`. `Home` is
   probably deliberate (whole-house entities), but the two stairwells arguably belong to real
   floors — and the floorplan will want them somewhere concrete.
4. **`light.main_bedroom_night_light` is assigned to area "Corridor upstairs"**, not Main Bedroom.
   Could be genuinely mounted in the corridor — needs a physical check, not a config guess.
5. **Two UniFi AP status LEDs (`light.ap_first_floor_nano_hd_led`, `light.ap_ground_floor_u6_lr_led`)
   are assigned to "Living Room".** They're `platform: unifi`, not lamps. Harmless until something
   does "turn off all lights in the Living Room" — then the AP LED goes dark too.
6. ~~**26 of 47 lights have no area at all.**~~ ✅ **RESOLVED 2026-08-10** — all 31 assignments
   applied, plus three new areas created (`main_bathroom` → first_floor, `reduit` → ground_floor,
   `reduit_upstairs` → first_floor), with the floors confirmed from the CAD plans rather than
   guessed. Only the two test lights remain unassigned, deliberately.

Items 1–5 are still open. Item 5 (the AP LEDs) has gone from latent to **live**: six more real
lights were just assigned to `living_room`, and the floorplan being built is precisely the kind of
thing that generates area-scoped "turn off the Living Room" actions — which would also switch off
the access-point LEDs. Either move them out of `living_room` or exclude them by entity_id in the
dashboard config.

**What to look at when we pick this up:** `ha_list_floors_areas` output vs the physical house.
See `[[reference-ha-light-entity-map]]` and `docs/ha-3d-floorplan.md`.

## Bind the Living Room remote to a *scene* instead of toggling the group

**Added:** 2026-08-12

> "is it possible to bind a remote to a specific scene in a group? for instance the living room
> remote is binded to a group called living room but the group is composed by 4 lights and during
> the night one of these light could be used as night light, now since the remote is toggling the
> state of the group on and off, clearly if the device are out of sync you have the christmas light
> effect"

Proposed plan was: (1) bind the remote to an "all bright" scene, (2) have an automation watch for
the scene activation and, during night hours, **poll** until the lights go off manually, then bring
the night light back up.

**Why this is worth doing properly:** the remote is a **Ubisys C4** — one of the very few Zigbee
controllers where the ZCL command each input emits is fully user-authorable (manufacturer cluster
`0xFC00`, `InputActions`). So scene recall genuinely *is* reachable here, unlike on an IKEA/Tuya
remote where the firmware only ever emits On/Off/Level. Binding itself is **cluster**-granular, not
scene-granular — the scene ID travels in the `Scenes.RecallScene` *payload*, so what matters is
whether the device can be made to emit that command at all.

**Root cause of the Christmas-light effect:** the inputs currently send `Toggle` (`0x02`). Toggle is
evaluated per-bulb against each bulb's *own* state, so any pre-existing divergence is preserved and
flipped forever. Group commands are APS **multicast and unacknowledged**, so a bulb that simply
misses a frame falls behind permanently. `On`/`Off` and `RecallScene` are absolute — a missed frame
self-heals on the next press. That asymmetry is the whole problem.

### Live `input_actions` as of 2026-08-12 — THIS IS THE ROLLBACK

C4 fw `2.4.0`, dateCode `20240122-DE-FB1`, hw 3, IEEE `0x001fee0000008342`.
`input_configurations: [0, 0, 0, 0]`

Record layout (z2m presents each record as a flat array of bytes):

| byte(s) | meaning |
|---|---|
| 0 | InputAndOptions — which physical input, 0-based |
| 1 | Transition — internal state-machine edge (press / hold / release) |
| 2 | Source endpoint on the C4 |
| 3–4 | Cluster ID, uint16 **little-endian** |
| 5+ | ZCL command ID, then command payload |

| raw record | input | ep | cluster | command | payload | z2m action |
|---|---|---|---|---|---|---|
| `[0,7,1,6,0,2]` | 0 | 1 | `0x0006` genOnOff | `0x02` Toggle | — | `toggle_s1` |
| `[0,134,1,8,0,5,0,50]` | 0 | 1 | `0x0008` genLevelCtrl | `0x05` Move w/ OnOff | up, rate 50 | `brightness_move_up_s1` |
| `[0,198,1,8,0,1,1,50]` | 0 | 1 | `0x0008` | `0x01` Move | down, rate 50 | `brightness_move_down_s1` |
| `[0,11,1,8,0,3]` | 0 | 1 | `0x0008` | `0x03` Stop w/ OnOff | — | `brightness_stop_s1` |
| `[1,7,2,6,0,2]` | 1 | 2 | `0x0006` | `0x02` Toggle | — | `toggle_s2` |
| `[1,134,2,8,0,5,0,50]` | 1 | 2 | `0x0008` | `0x05` Move w/ OnOff | up, rate 50 | `brightness_move_up_s2` |
| `[1,198,2,8,0,1,1,50]` | 1 | 2 | `0x0008` | `0x01` Move | down, rate 50 | `brightness_move_down_s2` |
| `[1,11,2,8,0,3]` | 1 | 2 | `0x0008` | `0x03` Stop w/ OnOff | — | `brightness_stop_s2` |

**Only inputs 0 and 1 carry actions. Inputs 2 and 3 are empty** — unknown whether they are unwired,
wired-but-unconfigured, or factory default. The `Transition` byte encodings (`0x07`, `0x86`, `0x0C6`,
`0x0B`) were **not** verified against the Ubisys technical reference — do not write new records from
guessed transition values.

### The idea worth building: mutate what the scene *contains*, not which scene is recalled

Zigbee scene tables live **in the bulbs**, and their contents are rewritable at any time. So instead
of conditionally recalling a different scene at night, keep one "off" scene and have HA rewrite its
*contents* at sunset/sunrise (night = 3 bulbs off + night light at ~2% warm; day = all 4 off). At
press time it is pure Zigbee: instant, no HA involvement, no visible off-then-on flash, and it keeps
working if HA or z2m is down. **This removes the need for the polling loop entirely** — not because
MQTT pushes state, but because HA never needs to know the state at press time at all.

**What to look at when we pick this up:**

1. **How many physical inputs serve the living room, and which endpoint (s1 or s2)?** This gates
   everything. Two inputs → the cheapest fix is a one-byte change, Toggle `0x02` → `On` `0x01` on one
   and `Off` `0x00` on the other; scenes then become an optional upgrade. One input → both the Toggle
   fix *and* scene recall are unavailable (one button recalls exactly one scene) and it needs either a
   multi-press transition or HA-side logic. Reprogramming the wrong endpoint hits a different room.
2. **Which of the 4 couch lights is the night light**, and confirm the group's actual membership.
3. **Whether ep1/ep2 is bound to group 2 or to the 4 devices individually.** Bindings are *not* in
   `configuration.yaml` — that only holds groups. They live in the coordinator / `database.db`, and
   z2m surfaces them in the `zigbee2mqtt/bridge/devices` MQTT payload and the frontend's Bind tab.
   Three SSH attempts on 2026-08-12 went at the wrong artifact; don't repeat that.
4. **Whether z2m's `scene_add` can target an individual device while specifying the group_id the
   scene belongs to.** The trick needs *per-member* values under one shared `(group_id, scene_id)`; a
   group-level `scene_add` writes identical values to every member. If it can't, the fallback is
   `scene_store`, which snapshots each bulb's own live state (per-member values for free) but needs
   the room to briefly *be* in the night configuration to capture it — visible to anyone in the room.
5. **`Living Room Couch Rear Right Corner Light`** (Nue/3A `3A12S-15`, zclVersion 3, dateCode
   `20190604`) is the risk device — the other three are Philips Hue with solid Scenes support. Verify
   it honours Scenes cluster recall *including* the colour/level extension fields before relying on
   it. Its `power_on_behavior` is currently `on`, which is a separate landmine.
6. `recall_*_s1` appearing in the z2m action enum only proves z2m can **parse an incoming** scene
   recall from the C4 — it is *not* evidence the `configure_device_setup` **write** path handles scene
   records. Different code path, and the enum contains typos (`recal_*_s2`, `recal_*_s4`) suggesting
   that converter is lightly exercised. Treat as a caution signal.

Related: `[[reference-ha-light-entity-map]]` (group 2 = `light.living_room`).

## Health findings surfaced while building the Home Health dashboard

**Added:** 2026-08-16

None of these were the task; they fell out of inventorying entities for the new `home-health`
dashboard. The "Problems" view that would have displayed them was deliberately not built, so they
are parked here instead of being lost.

1. **Two automations are in state `unavailable`** — `automation.garage_door_has_changed_status` and
   `automation.telegram_bot_to_notify_nobody_home_and_electronics_on`. An `unavailable` automation is
   **not** a disabled one: it usually means the config failed schema validation (classically an
   `enabled: false` top-level key, which is not valid). Both are almost certainly broken and silently
   not running.
2. **`sensor.matteo_office_lamp_remote_battery` is at 2.5%.** Also low: `stairs_down_motion_sensor`
   26%, `outdoor_garden_hose` 30%, `guest_room_remote_right_side` 43%.
   `sensor.postbox_pack_door_battery` reads `unknown`.
3. **129 entities are `unavailable`** (plus ~125 `unknown`, mostly never-pressed buttons — benign).
   Large clusters: UniFi per-port `power_cycle` buttons, and several `device_tracker` entities.
   Worth a triage pass; many are probably stale registry entries for devices long gone.
4. **`update.energy_tariff_energytarif` is permanently `unavailable`** — omitted from the Updates
   view for that reason. Probably a dead integration entity.
5. **`zigbee2mqtt-networkmap` card is installed but has no backing sensor**, so it cannot render.
   Needs an MQTT sensor fed from z2m's networkmap topic if you want the map.
6. **Server metrics are not in HA at all** (no CPU/RAM/disk for either host). The dashboard links to
   Grafana instead, which was the chosen option. The alternative — REST sensors querying Prometheus
   at `192.168.1.10:9092/api/v1/query` to make server health alertable inside HA — remains available.

**What to look at when we pick this up:** start with item 1 (`ha_config_get_automation` on both ids,
expect a schema error), then item 2 (physical battery swap). For item 3, `ha_search` with
`state_filter="unavailable"` paginated, grouped by domain.

## Service sanity-check findings 2026-08-19

**Added:** 2026-08-19

> ✅ **Items 1, 2 and 3 were FIXED on 2026-08-19**, together with the separate podman-access-log
> finding written up in `docs/centralized-logging-proposal.md` §2a. Commits `9523de7` (recovery
> notifications), `ea50b5e` (podman log level), `4447bcd` (15 blackbox probes), plus a volume-only
> Nextcloud `trusted_domains` change that has no file in git.
>
> ⏳ **Items 4, 5 and 6 remain OPEN** — all three were assessed as Low/informational and were
> deliberately not touched. They are the only reason this entry is still here.
> Durable write-ups: `docs/centralized-logging-proposal.md`, `docs/optimus-prime.md#logging`, and
> `[[project_notify_failure_never_worked]]` / `[[project-centralized-logging]]` in memory.

Fell out of a requested health sweep (container health + Traefik reachability + log errors) across
both hosts. **Nothing is down** — 75 containers all healthy, all 39 blackbox probes green, 0 alerts,
0 silences, and all 53 Traefik-routed hostnames answer externally. These are the things that are
quietly wrong underneath that.

1. ✅ **FIXED.** **`notify-recovery-check.service` on bumblebee had NEVER run — 6,706 failures.**
   `203/EXEC — Failed to locate executable /home/matteo/notify-recovery-check.sh: Permission denied`.
   Verified cause: the script is labelled `container_file_t` (as is `/home/matteo`), which systemd's
   `init_t` cannot exec. **This is the exact bug fixed on 2026-08-05 for `notify-failure.sh` — its
   sibling script was missed.** `notify-failure@.service` correctly points at `/usr/local/bin`
   (`bin_t`); this unit still points at `/home/matteo`. It retries every 5 min and has failed every
   time for at least the whole retained journal (since 2026-07-26). **So "service X has recovered"
   notifications have never been delivered on bumblebee.**
   **Verified to be a ONE-change fix** (checked the script before recommending): it already calls
   `telegram-send --config /etc/telegram-send.conf`, which is the correct form for bumblebee, and its
   companion `notify-failure.sh` does `mkdir -p /run/notify-failure` as root — so the state dir the
   recovery script reads will exist. Nothing else is wrong with it. So: `rsync --inplace` the script
   to `/usr/local/bin/`, update `ExecStart`, add it to ansible (which has no task for it), then test
   with a real trigger — not by assuming.
   (`/run/notify-failure` is absent right now simply because **no service has failed on bumblebee
   since the 03:49 boot today** — that is a good sign, not a second bug.)

   🔑 The generalisable check, which would have caught this in August:
   `grep -H ExecStart /etc/systemd/system/*.service | grep /home/`

2. ✅ **FIXED.** **15 Traefik-routed hostnames had no external probe — including every public service.**
   53 routed vs 39 probed. Unmonitored: `cockpit.{bumblebee,optimusprime}`, `firefox`, `frigate`,
   `immich.optimusprime`, `nextcloud.optimusprime`, `opensign-api`, `paperless`, `prowlarr`, and
   **all six internet-facing** `immich.public`, `jellyfin.public`, `n8n.public`, `nextcloud.public`,
   `pingvin.public`, `plex.public`. The `*.public` gap is the important half: those are the only
   services an outsider can reach, and nothing watches them. Note Immich *is* probed, but as
   `http://192.168.1.10:2283` — a direct host:port probe cannot detect a Traefik routing failure,
   which is precisely the fault class that hid for 4 months until 2026-08-14.

3. ✅ **FIXED + exposure CONFIRMED INTENDED by the user 2026-08-19** ("yes I need to be able to reach nextcloud from the internet") — **do not close it.** **`nextcloud.public.favarohome.com` → 400 "Access through untrusted domain."**
   Routed, internet-exposed, TLS valid, and Nextcloud itself answers (`server: nginx`, NC CSP
   header) — but the hostname is not in Nextcloud's `trusted_domains`, so it is unusable. The LAN
   name `nextcloud.optimusprime` works (302). Either add the domain or retire the route; right now
   it is an open door to an error page. Unnoticed because of finding 2.

4. ⏳ **STILL OPEN (Low).** **Boot-time Telegram notifications race the network.** `telegram-boot-notify.service` (OP) has
   been in `failed` state since the Aug 13 05:01 boot: `telegram.error.NetworkError:
   httpx.ConnectError: All connection attempts failed`. It **already has**
   `After=network-online.target` + `Wants=` — so that target is satisfied before DNS/egress actually
   works. The same boot took down `notify-failure@zigbee2mqtt-mcp.service.service` for the same
   reason, meaning **a service that fails at boot also loses its alert**. Needs a retry/backoff in
   the script, or a real reachability gate, not more ordering.

5. ⏳ **STILL OPEN.** **`sdj-reminder.timer` on OP can never fire again.** `OnCalendar=2026-03-31 21:00:00` with
   `Persistent=false` — a one-shot reminder whose date passed 4.5 months ago, still `enabled` and
   `active` with `NEXT="-"`. Harmless cruft, but it is the only `NEXT="-"` timer on either host, so
   it dilutes that check. (Both timers that matter — `zigbee-watchdog` and `slzb-temp-logger` — are
   correctly scheduled and firing.) Nothing deleted; say the word.

6. ⏳ **STILL OPEN (note, not a fault).** **`paperless` on bumblebee uses the routing pattern that is broken on OP, and gets away with it.**
   Traefik's backend for it is `http://10.89.0.6:8000` while bumblebee's Traefik is on `10.88.0.14`
   only. On OP that combination hangs for 20 s (`http=000`) — the documented
   `reference_traefik_routing_optimusprime` fault. On bumblebee it **works**: verified reachable from
   inside the Traefik container, and paperless answers in 63 ms. So the "10.89.x is unreachable" rule
   is **host-specific, not universal** — worth correcting in memory. It is still a fragility: the
   container is dual-homed (`paperless=10.89.0.6`, `podman=10.88.0.15`) and Traefik picked the
   10.89 address, so a firewall or podman change could silently break it. And per finding 2, nothing
   probes it.

**What to look at when we pick this up:** finding 1 first — it is a two-command fix with a written
precedent in `project_notify_failure_never_worked`. Then 3 (one `occ config:system:set
trusted_domains`), then 2 (extend the blackbox target list in Prometheus config on OP). The log-noise
findings from the same sweep are written up separately in
`docs/centralized-logging-proposal.md` §2, because they gate the Loki question.

## Document ingestion project — ✅ DESIGNED 2026-08-20, see docs/document-filing-pipeline.md

**The design and phased action plan now live in `docs/document-filing-pipeline.md`.** Read that, not
this entry. Kept here only for the open decisions listed in its §7 (whole archive vs `Manu & I`;
`PAPERLESS_FILENAME_FORMAT`; zipped vs incremental export; backfill paperless with all 3,159 docs;
second Hermes instance for Manu). Delete this entry once those five are settled.

### Original entry

**Added:** 2026-08-19

> "after you have finish remember me to discus about the document ingestion project"

Parked here deliberately so it survives context compaction. **The design already exists and should
not be re-derived** — the surviving spec is the "n8n Document Classification Pipeline" entry in
`project_pending_tasks`: a single Gemini 2.5 Flash call doing OCR + classification, dynamic folder-tree
discovery, confidence ≥ 0.8 → filed into the matched folder, < 0.8 → `_Unclassified/` plus a Telegram
alert, every document logged to a Google Sheet.

⚠️ The original plan file `/home/matteo/.claude/plans/bubbly-dancing-ullman.md` is **gone** (the whole
`plans/` directory is missing) — do not send anyone to read it.

**Three user prerequisites, none confirmed done:**
1. Add a PersonalDocs GDrive sync pair in cloud-drive-sync → `/data/gdrive-sync/PersonalDocs`
2. Create a "Document Classification Log" Google Sheet and note its spreadsheet ID
3. Set up a Google Sheets OAuth2 credential in n8n

**What to look at when we pick this up — and one thing that changes the design:**

- **🔑 A full `paperless-ngx` stack is already deployed on bumblebee — and it is completely EMPTY.**
  Verified 2026-08-19: all five containers up and healthy (`paperless`, `paperless-db`,
  `paperless-broker`, `paperless-gotenberg`, `paperless-tika`), reachable at
  `paperless.bumblebee.favarohome.com` — but the database holds **0 documents, 0 tags,
  0 correspondents**, and the consume directory is empty. It has been deployed and never used.

  This is the single most important input to the design discussion, because paperless-ngx *is* a
  document ingestion and classification system: OCR (via tika/gotenberg, both already running),
  tags, correspondents, document types, full-text search, and a watched **consume folder**. The
  original n8n design was written as if none of that existed.

  So the real question is **not** "how do we build the Gemini pipeline" but **"which half of this
  job is paperless's?"** Three shapes worth weighing:
  - (a) **n8n only delivers.** Drop files into paperless's consume dir; paperless does OCR,
    classification and storage. Least new code; gives up Gemini's semantic classification and the
    Google-Drive folder-tree filing that was the original goal.
  - (b) **Gemini classifies, paperless stores.** n8n calls Gemini for the classification decision,
    then posts to paperless's API with tags/correspondent pre-set. Keeps the smart classification,
    gains a real document store and search UI instead of a Google Sheet log.
  - (c) **Two corpora.** Paperless for archival documents, the GDrive tree for things that must stay
    as files in Drive. Legitimate, but doubles the surface.
  Recommendation to discuss: **(b)** — it reuses a stack that is already running and idle, and
  replaces the "log every document to a Google Sheet" step (prerequisites 2 and 3, both unstarted)
  with something queryable. That would also drop the Google Sheets OAuth2 dependency entirely.
- The sibling **receipt** pipeline (Warracker / Grocy / Firefly III, watch folder
  `/home/matteo/gdrive-sync/AI Bills/ToAnalize`) is also DESIGNED-NOT-BUILT and shares the same
  OCR-then-route shape — see `reference_n8n_api_endpoints`. Decide whether they are one pipeline or two.
- ⚠️ **Firefly III's API token was never retrieved** (`reference_n8n_api_endpoints` says so, and the
  2026-08-19 sweep found nothing authenticating against it — 5,671 `Unauthenticated` log lines/day
  are all our own uptime probe and healthcheck). If receipts are in scope, that token is a blocker.
- ⚠️ n8n on bumblebee runs `:latest` + `AutoUpdate=registry`, so it restarts near-nightly, and
  `staticData` writes are lost when a trigger fires within seconds of a restart — see
  `reference_n8n_api`. A new pipeline should **not** keep state in `staticData`.

## Enable 2FA on the Nextcloud admin account (now that the login page is public)

**Added:** 2026-08-20

Follow-on from the user confirming (2026-08-19) that internet access to Nextcloud is a requirement:
*"yes I need to be able to reach nextcloud from the internet."* That is settled and not in question —
this entry is only about the one gap it opens.

**Checked 2026-08-20, so this is not a generic hardening lecture — it is the single actual finding:**

| | state |
|---|---|
| Nextcloud version | **34.0.3** (memory had said 33.0.3 — corrected) |
| `auth.bruteforce.protection.enabled` | unset ⇒ **core default ON** ✅ |
| `bruteforcesettings` app | **enabled** ✅ |
| nginx PROPFIND ≥100 KB guard | still in place ✅ |
| `twofactor_totp`, `twofactor_backupcodes` | apps **installed and enabled** ✅ |
| **2FA on `matteofavaro@gmail.com`** | ❌ **NOT enabled** — both providers disabled *for the user* |
| `suspicious_login` | disabled |

So the admin account is **password-only and now reachable from the internet**, while the TOTP
provider is already installed and waiting. Brute-force throttling limits guessing but does nothing
against a credential that leaks elsewhere.

**Why this wasn't just done:** enrolling TOTP requires scanning a QR into an authenticator app, and
doing it without the user present risks locking them out of their own admin account. It is
inherently a user action, not an agent one.

**What to look at when we pick this up:**
- Enrol via the web UI: Settings → Security → Two-Factor Authentication (TOTP), **and save the
  backup codes** — `twofactor_backupcodes` is already enabled for exactly this.
- Verify afterwards with
  `occ twofactorauth:state matteofavaro@gmail.com` (wants totp under *Enabled* providers).
- Decide whether to enforce it for the other 4 users (`occ twofactorauth:enforce --on`) — note that
  enforcing it estate-wide affects family accounts and any WebDAV/desktop clients using passwords,
  which need app passwords instead. Probably admin-only first.
- Optional: enable `suspicious_login` (ML-based login-anomaly detection) — cheap now the service is
  public.
- Unrelated but adjacent: the NC33 `PresetManager` performance regression recorded in
  `[[project_nextcloud_app_cleanup]]` was measured on 33.0.3; this host is now on 34.0.3, so
  **re-measure before treating the 22 disabled apps as permanently necessary.**

## ⏸️ Garage contact-input fault — resume Sunday eve / Monday (owner away 21-24 Aug)

**Added:** 2026-08-21

Owner narrowed it well: the PJ-ZGD01 module **works and actuates** (door motor triggered from z2m
successfully), radio is healthy (LQI 122-203), but the **contact input is dead** - a magnet held
against the reed sensor produces no change in z2m. Plan was: (1) disconnect the magnetic sensor,
(2) short the two input pins and watch z2m.

🔴 **Read `[[project_ha_garage_lametric_bug]]` before doing that - there is a confound that would
frame an innocent sensor.** `status` is still **"Run Time Alarm"** (latched since 20 Aug 13:54), and
the contact does not update while it is latched. So the magnet test *and* the short test both return
"no change" whether or not the wiring is faulty. Clear the alarm first (power cycle), then
**immediately restore `run_time: 120`** - a power cycle resets it to 10 s, which re-arms the fault
within one door cycle.

Then retest the magnet: if it responds, the latch was the whole problem and no wiring work is needed.
Only if it is still dead does the 3-way multimeter bisect (reed switch -> cable -> module terminals)
apply - that separates sensor from cable, which shorting alone cannot.

⚠️ **While stuck it reads CLOSED, so both garage-open alert automations cannot fire** - no
open-garage alerting during the absence.

---

*(previously cleared 2026-07-27, after Frigate, Immich, the pool pump and the coordinator
migration were all worked through)*

---

## Devin's under-bed light: HA nulls brightness in RGB mode (found 2026-08-27)

Discovered while building the bedtime fade. **Pre-existing bug, unrelated to the fade.**

`light.devin_room_under_bed_lights` is a Gledopto **GL-C-008P** RGB+CCT controller. Zigbee2MQTT
advertises it to HA with `supported_color_modes: [color_temp, xy]` — **no `hs`**. But as soon as an
RGB colour is set, z2m publishes `color_mode: "hs"`, and HA's MQTT JSON light schema rejects the
**entire** state payload:

```
homeassistant.components.mqtt.light.schema_json  WARNING   (count: 11)
  Invalid color mode 'hs' received for entity light.devin_room_under_bed_lights
```

Effect: `brightness`, `color_temp_kelvin`, `rgb_color` etc. all read `null` in HA while the device
itself is perfectly healthy (`linkquality: 127`) and still reports the true `brightness: 203` to z2m.
Confirmed both ways: in `color_temp` mode HA reads `brightness: 204`; in `hs` mode it reads `null`.

Consequences worth deciding on:
- Anything that reads this light's brightness silently sees nothing. The fade now **guards** on it
  and raises a persistent notification rather than mis-anchoring, but the underlying gap remains.
- The dashboard tile exposes `light-color-favorites`, so picking a colour is the *easy* path into the
  broken mode.

Possible fixes, none applied yet:
1. Check whether a newer z2m exposes `color_hs` for GL-C-008P (would make HA accept `hs`).
2. Remove the `light-color-favorites` feature from the tile so the light stays in white/CCT mode.
3. Leave as-is and rely on the guard.

**Also noted:** `light.devin_room_under_bed_lights` has **no area assigned**, which is why the
existing "Turn on/off night lamp" automation (which targets `area_id: devin_s_bedroom` at sunrise)
never turned it off. Handled with a dedicated entity-targeted automation rather than assigning the
area, since assigning it would enrol the light in every other area-targeted automation and script.
