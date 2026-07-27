# Plan — Scanner → Google Drive → filing + Paperless

**Status:** agreed 2026-07-27, not started. Implement one step at a time.

> Kept in git deliberately. The previous plan for this area lived in `~/.claude/plans/` and
> that whole directory has since vanished, taking the spec with it.

---

## Goal

Scanned paper arrives in Google Drive. Get it (a) filed into the right folder with a sensible
name, with human approval, and (b) into Paperless for OCR and search — without ever putting the
Drive originals at risk. Separately, keep a **safety copy** of the whole `ManuAndI` tree.

## Four independent pipelines

Deliberately decoupled — each can fail or be paused without stopping the others. This matters
because Nextcloud has already proven it can go down (see #48), and a Nextcloud outage must not
stop documents being filed or OCR'd.

| # | Pipeline | Purpose | Trigger |
|---|---|---|---|
| **A** | Drive ↔ local (`cloud-drive-sync`, `two_way`) | transport | continuous, 30 s poll |
| **B** | scan → propose → approve → file **+** Paperless | document processing | event (new file) |
| **C** | **`ManuAndI` → Nextcloud** | **safety copy — nothing else** | timer, async |
| **D** | Paperless → Nextcloud + Drive | protect Paperless's own data | timer, async |

**C is not part of the Paperless idea at all.** It exists purely so a second copy of the folder
tree exists somewhere other than Google Drive. It reads only, never writes back to the source, and
knows nothing about scans, proposals, approvals or OCR. If B were deleted tomorrow, C would still
be worth running.

### LIVE vs BACKLOG (applies to pipeline B only)

| | Scope |
|---|---|
| **LIVE** | new scans, from the moment the scanner uploads |
| **BACKLOG** | the documents that already exist — one-off bulk load into Paperless |

---

## Verified starting state (2026-07-27)

Everything below was checked on the hosts, not assumed.

| Thing | State |
|---|---|
| `cloud-drive-sync` (bumblebee) | running, UI :8090, **0 sync pairs**, gdrive + nextcloud creds loaded |
| `cloud-drive-sync` (OP) | running, separate instance, `/mnt/data/gdrive-sync` empty |
| `/home/matteo/gdrive-sync` (bumblebee) | **empty** — cleaned |
| Paperless (bumblebee) | running; **media empty**, consume empty — clean slate |
| Paperless volumes | `data`, `media`, `export`, `consume` all local under `/home/matteo/docker_persistent/paperless/` |
| n8n (bumblebee) | running; **no filesystem mount** — only its own config dir |
| Nextcloud (OP) | 34.0.2, **encryption disabled**, data at `…/nextcloud/data/matteofavaro@gmail.com/files/` |
| Nextcloud NFS on bumblebee | **mounted** at `/mnt/data/docker_persistent/nextcloud`, writable as `matteo` |
| Nextcloud runs as | `PUID/PGID 1000` = `matteo` — same uid on both hosts, so ownership already matches |
| Nextcloud holds | `Documents/ManuAndI` 2888 files / 3.8 G, incl. `Scanned/` 331 PDFs |
| `state.db` (cloud-drive-sync) | 4.4 G + 4.4 G WAL, **0 rows**, 99.999% free pages |
| bumblebee `/home` | 341 G free |

**The scanner** uploads a PDF to one of two Google Drive folders depending on which button is
pressed — one under `ManuAndI`, one for personal documents outside it.

---

## Architecture decisions, and why

### Bidirectional sync is correct here

Initially argued for `download_only` as the safe option. **Wrong for this goal:** step 8 below
moves and renames the file, and that move has to propagate *up* to Drive. `download_only` cannot
do that. So both pairs are `two_way`.

The risk normally attached to `two_way` — stale sync state being read as "the user deleted
everything locally", propagating mass deletions upward — **does not apply**: `state.db` has 0 rows
in every table. Verified, not assumed. There is no history to misread.

### Nextcloud is written over NFS, never over WebDAV

`cloud-drive-sync`'s Nextcloud leg is the thing that kept breaking Nextcloud, and the mechanism is
now known and still open upstream:

> **ciberkids/cloud-drive-sync#48** — failed WebDAV actions log the entire request payload.
> The errors are `413 Request Entity Too Large`: Nextcloud *rejecting* oversized bodies, which the
> tool then retries. Related: **#47** (property list grows unboundedly → 19 MB PROPFIND bodies,
> 138,575 repeated lock properties), **#49** (`state.db` never vacuumed).

So:

| Leg | Mechanism | Reason |
|---|---|---|
| Drive ↔ local | `cloud-drive-sync` | Drive backend works |
| → **Nextcloud** | **`rsync` over the NFS mount + `occ files:scan`** | no HTTP, no PHP, no DB → cannot hit #48 |

The NFS mount already exists and uid 1000 already matches, so this needs no new infrastructure.
`occ files:scan` must be **scoped with `--path=`** (never `--all`) and must run only **after**
rsync completes — scanning mid-write registers a partial file with the wrong size and etag.

### Proposal state lives outside the synced tree

Under `two_way`, every JSON written, deleted, or moved inside the tree becomes Drive API churn —
on a tool whose open bugs are all about churn. Only the **final approved move** should sync.

### Correction happens by Telegram reply, not by editing files

The original design was: reject → move to quarantine with its JSON → edit the JSON → move back to
`Scanned`. That is a four-step filesystem round-trip to carry one fact (the correct destination),
and it leaves a file in flux while both n8n and the sync engine have opinions about it.

Replying in Telegram closes the loop in one step and the file never moves. Quarantine stays as the
fallback for "can't decide right now", not the primary path.

### The classification rulebook already exists

`ManuAndI/Folder desciption - what goes where?.xlsx` (6.5 KB) and `Folder_Restructure_Proposal.md`
(3.9 KB). **Feed these to the model as the allowed set**, rather than letting it invent categories
— otherwise you get `Insurance` / `Insurances` / `Assicurazioni` drift over months. Constrained
choice beats open-ended classification.

Target structure:

```
ManuAndI/Documents/
├── AI Bills Folder     ├── Personal Documents
├── Diverse Bills       ├── Taxes
├── Insurances          ├── Warranties
├── Pension             └── Wedding Matteo-Manu 05.06.2021
```

### Paperless gets a copy, never the original

Paperless **deletes** from its consume directory after ingesting. It must therefore only ever see
a copy. Two consequences:

- The copy is made from the stable `Scanned` path **before** the approved move.
- Nothing of yours can be destroyed by Paperless's normal behaviour, so letting it delete its own
  copy is fine and needs no configuration.

### Pipeline C — `ManuAndI` → Nextcloud: a backup, not a mirror

This is the one rule that defines the whole pipeline:

> **No `--delete`. Ever.**

`★` A mirror propagates deletions, so it gives no protection against the most common way data is
lost — someone deleting it. Today is the proof: `gdrive-sync` went from **7.0 GB to empty**. A
`--delete` mirror would have faithfully emptied the Nextcloud copy too, and the 331 scanned PDFs
would be gone. They survived *only* because the old sync was `upload_only` with no deletion
propagation.

Consequences of that choice, accepted deliberately:

- The Nextcloud copy **accumulates** and will diverge from Drive over time. That is the point.
- It is **append-only**, so it protects against deletion but not against a bad *overwrite* — a file
  corrupted in place would overwrite the good copy. Out-of-band writes get **no Nextcloud version
  history and no trash**, so Nextcloud won't save you either. `rsync --backup
  --backup-dir=…/_versions/<date>/` closes that gap cheaply and is recommended.
- Pruning is a **manual, deliberate** act, never automatic. If it ever prunes itself it has stopped
  being a backup.

Shape:

```bash
SRC=/home/matteo/gdrive-sync/ManuAndI/
DST=/mnt/data/docker_persistent/nextcloud/data/matteofavaro@gmail.com/files/Documents/ManuAndI/

# no --delete;  --backup keeps superseded versions instead of losing them
rsync -a --backup --backup-dir="../_ManuAndI_versions/$(date +%F)/" "$SRC" "$DST"

# only after rsync exits 0, and always scoped
ssh 192.168.1.10 'sudo podman exec nextcloud-app php /app/www/public/occ \
  files:scan --path="/matteofavaro@gmail.com/files/Documents/ManuAndI"'
```

Notes specific to C:

- **The destination already exists and has content** — `Documents/ManuAndI`, 2888 files / 3.8 G,
  left by the old `upload_only` bridge. So the first run reconciles rather than seeds.
- **Runs over NFS, not WebDAV** — same reasoning as everywhere else in this plan.
- **Async by timer**, nightly. It must not be chained to pipeline B: a scan being filed should not
  wait on a backup, and a backup should not be skipped because no scans arrived.
- **Source is read-only** to this pipeline. C never writes into `gdrive-sync`, so it cannot
  disturb pipeline A or B.
- If local is empty (as it is right now), a no-`--delete` rsync copies nothing and harms nothing —
  which is exactly the failure mode this design is built to survive.

### "Backup Paperless" means two different things

| Want | Mechanism |
|---|---|
| Browsable archive of the PDFs | set `PAPERLESS_FILENAME_FORMAT` so media lands in a structured tree, sync that tree |
| **Restorable** backup | **`document_exporter`** → files + `manifest.json` |

Raw `media/` alone is **not restorable** — without the Postgres DB there are no tags,
correspondents or dates. The `export` volume already exists in the quadlet for this.

---

## Implementation steps

Ordered so that **nothing before step 7 can lose data.**

### Step 0 — reclaim the dead 8.8 GB

`state.db` is 4.4 G + 4.4 G WAL with 0 rows and 99.999% free pages. Needs the daemon stopped
(it holds the connection open):

```bash
sudo systemctl stop cloud-drive-sync
sudo sqlite3 /home/matteo/docker_persistent/cloud-drive-sync/data/state.db \
  "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"
sudo systemctl start cloud-drive-sync
```

**Verify:** file drops to KB; daemon starts and reopens the DB cleanly.

### Step 1 — one sync pair, and prove a round trip

Configure **only** the `ManuAndI` pair first, `two_way`. Drop a test file in Drive, confirm it
lands locally; create one locally, confirm it reaches Drive.

**Verify:** both directions work; `cloud-drive-sync.log` stays small (the logrotate rule now caps
it at 100 MB × 5, compressed).

### Track C (independent) — `ManuAndI` → Nextcloud safety copy

**Not part of the B sequence — build it before the Paperless work.** It needs neither n8n, Telegram
nor OCR, and is the cheapest real safety gain in this plan.

> ### ⛔ Prerequisite: wait for pipeline A to reach a STABLE sync first
>
> Do not build C while the initial `ManuAndI` download is still running. With no `--delete` an early
> run is *harmless* — it cannot lose anything — but it makes the **verification worthless**: a file
> absent from the backup is indistinguishable from a file that simply hasn't downloaded yet. A
> backup you cannot validate is not meaningfully a backup.
>
> "Stable" is measurable, not a feeling. All four should hold:
>
> 1. the pair reports **idle / sync complete** in the UI (:8090), not in-progress;
> 2. **no pending or partial transfers** — `partial_transfers` empty in `state.db`;
> 3. local file count **and** total bytes match the Drive folder;
> 4. **a full poll cycle (30 s) passes with zero changes**, twice in a row — one quiet cycle can
>    just be a gap between batches.
>
> Only then does the acceptance test below mean anything.

1. `.service` + `.timer` on bumblebee, nightly.
2. `rsync -a --backup --backup-dir=…` — **no `--delete`** — into the NFS-mounted Nextcloud path.
3. Scoped `occ files:scan --path=…` on OP, only on rsync exit 0.

**Verify:**
- a file added in Drive appears in Nextcloud on the next run **and is visible in the Nextcloud UI**
  (proves `files:scan` registered it, not just that bytes landed);
- a file **deleted** in Drive **still exists** in Nextcloud afterwards — this is the acceptance
  test for the whole pipeline, and the reason it exists;
- a file **modified** in Drive leaves its previous version under `_ManuAndI_versions/<date>/`.

### Step 2 — answer the rename question

**The single most important unknown.** Rename one synced file locally and watch what the tool does:

- Detected as a **move** → cheap metadata operation. Good.
- Detected as **delete + create** → the whole PDF re-uploads on every approval, and their issue
  **#35** ("delete_remote actions permanently fail with 'No remote ID'") suggests remote deletes
  have misbehaved before.

**Verify:** inspect the log and Drive for whether bytes moved. If it is delete+create, decide
whether that is acceptable before building anything on top.

### Step 3 — second sync pair

Add the personal-documents pair (the other scanner button target, outside `ManuAndI`).

**Verify:** both pairs sync independently; scanner button A and button B each land in the right
local directory.

### Step 4 — n8n can see the tree

Add a volume mount for `/home/matteo/gdrive-sync` to `n8n.container`, redeploy, restart.

**Verify:** n8n can list the directory. Nothing else yet.

### Step 5 — detection only, acts on nothing

n8n watches the scanned directories and **logs what it sees**. inotify works here because the
directory is local — this is exactly why the pipeline lives on bumblebee and not behind a mount.

Also handle the **pre-existing JSON** case now: if a file arrives with a sidecar proposal from a
previous round, its contents are authoritative and the model is not re-consulted.

**Verify:** every new scan is noticed exactly once; no duplicate or missed events.

### Step 6 — proposal, still acting on nothing

For each new file: OCR + classify in one model call, using the xlsx as the allowed set. Look for
familiarity with what is already filed in `ManuAndI` to infer both destination **and** a filename
pattern. Emit a proposal — **stored outside the synced tree.**

**Verify:** proposals are sane on a sample of real scans. Wrong ones cost nothing at this stage.

### Step 7 — Telegram approve / reject

Same shape as the movie pipeline. Reject → reply with the correct destination; quarantine only as
the "decide later" fallback.

**Verify:** both paths behave; a correction by reply produces the right destination.

### Step 8 — act on approval

1. **Copy** to `paperless/consume/` (from the stable `Scanned` path, before moving)
2. **Move + rename** into `ManuAndI/Documents/<category>/`
3. Let the sync engine carry the move up to Drive

**Verify:** original present in Drive at its new path; Paperless ingested and deleted its own copy;
nothing left in `Scanned`.

### Step 9 — the two backup legs (pipeline D)

- **Paperless → Nextcloud**: `document_exporter` → `rsync` over NFS → scoped `occ files:scan`
- **Paperless → Drive**: separate `cloud-drive-sync` pair

Drive by a **timer, not by chaining onto ingestion** — Paperless OCR is asynchronous and takes
minutes per document, so a timer is simpler and more robust than polling for task completion.

**Verify:** a restore rehearsal from the export actually works. An unverified backup is not a
backup.

### Step 10 — backlog, one-off

Bulk-load existing documents into Paperless as copies.

- **Filter by extension.** The old `ManuAndIDocs` tree contained `82 .dll`, `56 .pak`, `77 .png`
  alongside 993 PDFs — a software archive had been dumped in it. Feed only real document types.
- **Dedup is free** — Paperless rejects by content hash, so re-runs and overlap with live watching
  are safe.
- **Throttle.** ~1,400 real documents; OCR is the bottleneck, expect hours to days. Rate-limit the
  uploads so the celery queue doesn't balloon.

---

## Known hazards

| Hazard | Handling |
|---|---|
| Paperless empties its consume dir | it only ever receives copies; originals never placed there |
| `two_way` + pipeline churn | proposal state kept out of the synced tree |
| Rename → full re-upload | **step 2 answers this before anything depends on it** |
| Async OCR | backup legs run on a timer, not chained to ingestion |
| Edited file on retry | new content hash → Paperless treats it as a new document. Decide: skip on retry, or accept the duplicate |
| Nextcloud out-of-band writes | scoped `occ files:scan` **after** rsync; no versions/trash for such files (fine for a backup copy) |
| `occ files:scan --all` | never — heavy on a 4.2 T instance. Always `--path=` |
| **Backup mirroring a deletion** | pipeline C uses **no `--delete`**. Today's 7 GB→empty event would have emptied the backup too |
| Bad overwrite reaching the backup | `rsync --backup --backup-dir=` keeps the superseded copy; out-of-band writes get no Nextcloud versions/trash |
| Pipelines coupled together | A/B/C/D are independent; a Nextcloud outage must not stop filing or OCR |
| Backing up mid-download | C waits for a **stable** A sync — otherwise "missing from backup" and "not yet downloaded" look identical and the verification proves nothing |
| cloud-drive-sync log growth | capped by `/etc/logrotate.d/cloud-drive-sync` (100 MB × 5, compress, **copytruncate**) |

## Deferred

- **Whole-of-Drive → Nextcloud backup via rclone** — second iteration. Note pipeline C already
  covers `ManuAndI` specifically; this would extend the same idea to the rest of Drive. rsync over
  the NFS mount may make rclone unnecessary for anything already synced locally — rclone earns its
  keep only for Drive folders that are *not* mirrored to local disk.
- Whether `ManuAndIDocs` is a live tree or dead data. It had no sync pair and was stale since
  April; the local copy is now deleted, and Nextcloud holds `Documents/ManuAndI` (2888 files).
