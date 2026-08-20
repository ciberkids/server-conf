# Document filing pipeline — design & action plan

**Status:** design agreed, nothing built. **Written:** 2026-08-20.
**Goal:** when a scan lands in Google Drive, propose where it belongs, ask a human in Telegram, then
file and rename it on approval — and in parallel hand a copy to paperless-ngx for independent
categorisation, with paperless' work backed up to Nextcloud.

Every fact in *Verified current state* was checked on the hosts on 2026-08-20. Anything not verified
is marked ⚠️ **UNVERIFIED**. Do not re-derive what is already recorded here.

---

## 1. Why this shape

The pipeline is built around a skill the owner already wrote and proved:
`document-filing` v1.0.0 (`/home/matteo/Claude/Google Documents Helper]/exports/hermes-document-filing/`
— note the literal `]` in that directory name; quote all paths). It was distilled from clearing a
3,159-file household archive: 141 documents decided one at a time, two earlier mistakes found and
repaired, zero files lost, proved by hash reconciliation.

Its thesis is the pipeline's thesis: **the tools produce evidence, the owner decides, and every
mutation is provable afterwards.** Step 8 of its procedure is literally *"Present three things and
STOP."*

### 🔴 This supersedes the old auto-filing plan

`project_pending_tasks` (memory) describes an n8n design where *"Gemini classifies, confidence ≥ 0.8
→ auto-file"*. **That gate is empirically dead**, and the skill's own Pitfalls section is the evidence,
every entry from a real incident:

| What was assumed | What actually happened |
|---|---|
| text similarity identifies duplicates | **identical documents scored 0.58–0.71 OCR-vs-OCR** — a 0.8 gate rejects true matches |
| one scan is one document | an invoice fed through 2½ times; **five documents from three companies for two people** in nine pages — and a classifier "wrote off" a document the archive was missing |
| text is enough | two files trashed as duplicates were a delivery note and a **stamped, signed** copy — ink is invisible to text |
| identifiers are distinctive | an insurer's own payment **IBAN** matched one person's statement into another person's folder |
| bigger file = better scan | a **37 KB bitonal** scan was higher resolution than a 1 MB colour one |

**Keep:** OCR, evidence gathering, and `routing_map.json` as the destination oracle.
**Drop:** unattended auto-filing. A human approves every move.

### 🔑 Why a *multi-user* decision chat is required, not convenient

The skill insists on checking the addressee, and documents the case of *"five documents from three
companies for two different people"*. Half the paperwork is Manu's, and **she is frequently the only
person who can identify her own documents**. The shared Telegram chat is therefore a functional
requirement of the domain, not a UX nicety.

---

## 2. Verified current state

| Fact | Value |
|---|---|
| Archive location | `/home/matteo/Insync/matteofavaro@gmail.com/Google Drive/` — **on the workstation** |
| Archive size | 5.1 GB, 3,159 files, 634 folders |
| `Manu & I` | **3.9 GB — 76% of the whole archive** |
| `Scanned` | **empty** (both trays cleared 2026-08-19) |
| Sync client | Insync, running continuously on the workstation, **live two-way** |
| Hermes host | **bumblebee** (192.168.1.14), quadlet, `Network=host`, image `localhost/hermes-agent:latest` |
| Hermes model | `deepseek/deepseek-v4-flash-0731` (switched 2026-08-20) |
| bumblebee `/home` | 387 G, **347 G free** (11%) |
| bumblebee `/` | 70 G, 23 G free (**68% used** — the tight one) |
| GPU | GTX 1080 Ti 11 GB, **shared with Frigate** (~960 MiB, varies) |
| paperless | deployed, **completely empty** (0 documents / tags / correspondents / storage paths) |
| paperless consume | `/home/matteo/docker_persistent/paperless/consume` → `/usr/src/paperless/consume` |
| paperless media | `…/paperless/media` (on `/home`, not root ✅) |
| paperless export | `…/paperless/export` (empty) |
| `PAPERLESS_FILENAME_FORMAT` | **not set** |
| Nextcloud PROPFIND guard | ✅ **still in place** (`default.conf`, rejects bodies ≥100 KB) |
| cloud-drive-sync | service **active**, but **no sync pairs configured** (accounts only) |
| routing_map.json | 697 KB — 227 rules, 10-step `trunk_decision_order`, `owner_rulings_binding`, `anti_targets` |

### ⛔ Constraint 1 — Hermes cannot see the archive

No Insync on bumblebee; `/home/matteo/gdrive-sync/` is **empty**; cloud-drive-sync has no pairs; every
NFS mount on bumblebee comes **from Optimus Prime**; the workstation **exports nothing** (no NFS/SMB
listener). Resolved by Phase 3 below.

### ⛔ Constraint 2 — the Hermes container has none of the toolchain

Checked inside the container: `python3` ✅, `sha256sum` ✅. **MISSING: `pdftotext`, `pdftoppm`,
`pdfimages`, `tesseract`, `rsync`, `gio`, python `pillow`.** Also **no podman/docker socket and no
client** — only `/opt/data` and `/etc/localtime` are mounted. Resolved by Phase 1.

### ✅ Enabler — Hermes *can* be called back

`gateway/platforms/api_server.py` exists but is not enabled. Knobs: `API_SERVER_HOST` (default
`127.0.0.1`), `API_SERVER_PORT` (default **8642**), `API_SERVER_KEY`, `API_SERVER_CORS_ORIGINS`,
`API_SERVER_MODEL_NAME`. It also exposes cron-job management
(`name`/`schedule`/`prompt`/`deliver`/`skills`/`repeat`/`enabled`).
Today Hermes listens **only** on `127.0.0.1:9119` (the dashboard).

**Fallback that needs no callback at all:** Hermes' cron ticker is alive (heartbeat updating) with
zero jobs. A polling job can pick up the pending queue on a schedule. Use the callback as primary and
a low-frequency poll as the dead-man's-switch — an error-only pipeline cannot distinguish "nothing
arrived" from "the callback is broken".

---

## 3. Architecture

```
  Google Drive  ──Insync──▶  workstation archive (canonical, 5.1 GB)
        ▲                                │
        │                          cloud-drive-sync
        │                                ▼
        │                    bumblebee: local copy of Manu & I + Scanned
        │                                │
        │                     (1) new file lands in Scanned
        │                                ▼
        │                    (2) watcher moves it OUT of the watched glob
        │                        into  pending/<job-id>/
        │                                │
        │                    (3) callback ──▶ Hermes API :8642 (API_SERVER_KEY)
        │                                         │
        │                        (4) Hermes runs /document-filing
        │                            calling OliveTin actions by JOB ID
        │                                         │
        │                        (5) proposal ──▶ Telegram (rendered page image
        │                                          + inline keyboard)
        │                                         │
        │                        (6) human approves / corrects
        │                                         ▼
        └────────── (7) move + rename in the synced tree ──┐
                                                            │
                             (8) copy ──▶ paperless consume/ ──▶ paperless store
                                                                      │
                             (9) document_exporter --zip ──▶ export/ ──┴──▶ Nextcloud
```

### Component decisions

| Decision | Choice | Why, and what was rejected |
|---|---|---|
| Tool execution for Hermes | **OliveTin** (`https://www.olivetin.app/`) | Predefined YAML actions, **typed+validated arguments**, per-action ACLs, API keys for scripts, webhooks. Its own docs name AI agents as a target user. 3.7 k★, pushed 2026-08-16. |
| — rejected | mounting host tool dirs into the container | not a PATH problem: an AlmaLinux `pdftotext` won't run in a Debian-based Python image without its whole shared-library tree |
| — rejected | podman socket + sidecar | socket access is **root-equivalent on bumblebee**, handed to an LLM-driven container. Also needs the socket mounted *and* a client installed — neither exists today. |
| — rejected | rebuild the Hermes image with the toolchain | viable fallback (one Dockerfile change, ~300 MB) but touches the homelab's **only locally-built image**, whose loss caused a 4-day outage |
| — considered | shell2http | ⚠️ **not outdated** as assumed — pushed 2026-08-08, 1.5 k★. Right shape, but no argument validation and no ACLs, which matter when the caller is an LLM. |
| — also on the shortlist | Cronicle (5.8 k★), Dagu, µTask, flowctl | heavier: schedulers/workflow engines rather than a constrained command surface |
| Argument passing | **opaque job id, never a path** | see below — this is the load-bearing decision |
| Canonical store | **the Drive tree** | human-navigable, already conventioned by `routing_map.json`, survives paperless |
| paperless role | **parallel index over a copy** | it *consumes and removes* from `consume/`, so feeding it a copy means it eats the copy and Drive stays authoritative. No ownership fight. |
| paperless backup | **`document_exporter --zip`** | see §5 |

### 🔑 Why the job id matters more than it looks

OliveTin validates arguments by type (`ascii_identifier`, `int`, …). **Real filenames in this archive
would fail that validation** — the skill documents names containing spaces, `&`, and **literal CRLF**,
plus two NFD-normalised folder names that byte comparison silently missed.

So: the watcher assigns a **job id**, moves the file to `pending/<job-id>/`, and every OliveTin action
takes only that id. The server-side script resolves the real filename from the queue.

Three benefits at once: validation stops fighting the data; the LLM can never name an arbitrary path,
so it cannot be talked into touching something outside the queue; and the CRLF/NFD filename hazards
never cross a shell boundary.

---

## 4. Risks and mitigations

### 🔴 R1 — the watcher will jam exactly like the movie pipeline did, twice

A systemd `.path` unit with `PathExistsGlob` is **level-triggered**. A file that isn't consumed
re-fires the oneshot immediately → 5-starts-in-10s limit → **both units latch FAILED**. This happened
twice in this homelab (`reference_movie_rename_pipeline`): 26 anime episodes, then a duplicate.

**Here it is not an edge case — it is the normal state**, because the design deliberately leaves a
file untouched while waiting for a human answer.

**Mitigation:** nothing awaiting a decision may ever sit in the watched location. On pickup, move
immediately to `pending/<job-id>/` (not watched) and act only on the reply. Every failure path
quarantines with a reason sidecar, exactly as `movieProcessor.py` was fixed to do.

### 🔴 R2 — a live two-way sync plus a mover

A wrong move propagates to Drive in seconds. Mitigations, all already in the skill:
- run `snapshot.sh` before the first mutation of a session; keep `snapshot_root` **outside every sync
  scope** (that is what the config key is for);
- never act on a partially-synced file — wait for `CLOSE_WRITE`, or require size+mtime stable for N
  seconds;
- `file_document.sh` only: hash → `mv` → re-hash, refuses to overwrite, deletes go to trash not `rm`;
- `reconcile_tray.py` at the end of every session — a file is either filed byte-identical or in the
  trash, or the run stops and restores.

### ⚠️ R3 — cloud-drive-sync has form

Issue **#47** (a 19 MB PROPFIND with 138 k repeated `nc:lock` props) starved Nextcloud's login and is
why the daemon was stopped. It runs today with **no pairs**, so it is idle; adding pairs re-arms that
code path. The fault was in the **Nextcloud** provider's `delete_remote`/`trash_file` path, so a
gdrive-only pair may be unaffected — **check #47's status before adding pairs.** The nginx guard is a
backstop, not a fix, and it only bounds oversized PROPFINDs.

🔒 **Per project rule, bugs in cloud-drive-sync get GitHub issues, never patches** — including the
callback feature. That work belongs to that repo's own agent.

### ⚠️ R4 — GPU contention if any local model is involved

The 1080 Ti is shared with Frigate. If Ollama starves it, Frigate's watchdog treats stalled detection
as fatal and **exits the whole process**. This pipeline needs no local model (Hermes uses OpenRouter),
so the mitigation is simply: **do not add one here.** If a local OCR/coder model is ever wanted, cap at
`qwen2.5-coder:7b` (4.7 GB) and set a short `OLLAMA_KEEP_ALIVE`.

### ⚠️ R5 — storage doubling

The export is a **second full copy** of every document, on top of paperless' own copy of the Drive
original. Roughly 2× document volume before Nextcloud's copy. Free today (0 documents, 347 G on
`/home`) but needs a retention rule on the dated zips from day one.

---

## 5. The paperless side, precisely

**Paperless never loses a file.** It stores the original in `media/documents/originals/`, optionally an
`archive/` PDF-A rendition, and serves downloads from the UI. A media-only backup keeps every byte.

What a media-only backup *loses* is **identity**. Verified from source, `models.py:436`:

```python
fname = str(self.filename) if self.filename else f"{self.pk:07}{self.file_type}"
```

and `generate_filename()` ends *"No template, use document ID"*. With **no
`PAPERLESS_FILENAME_FORMAT`** and **zero `storage_path` rows**, on-disk names are `0000042.pdf`. Tags,
correspondent, type and date live only in PostgreSQL.

Two legitimate options:

1. **Set `PAPERLESS_FILENAME_FORMAT`** (date / correspondent / title) — `media/` becomes
   self-describing and a plain folder sync becomes a decent backup. Limit: a path encodes one
   location, so multi-tag documents still lose their tags.
2. **Export (chosen).** Superset: human-named files **plus** `manifest.json`, restorable into an empty
   instance with `document_importer`.

```bash
podman exec paperless sh -lc \
  'cd /usr/src/paperless/src && python3 manage.py document_exporter \
     --zip --zip-name "paperless-$(date +%F)" \
     --no-thumbnail --split-manifest --compare-checksums \
     --no-progress-bar \
     /usr/src/paperless/export'
```

| Flag | Effect |
|---|---|
| `--zip` / `--zip-name` | one dated archive per run — far kinder to a sync client than thousands of small files |
| `--no-thumbnail` | thumbnails are regenerable; don't ship them |
| `--split-manifest` | per-document manifests instead of one large JSON rewritten every run |
| `--compare-checksums` | decide re-export by checksum, not size+mtime — catches same-size edits |
| `--no-progress-bar` | non-interactive |
| ⛔ `--delete` **omitted** | it prunes an *unzipped* target so it does not combine with `--zip`; and a deleting operation aimed at a synced folder is a hazard already met here |

⚠️ The bare `document_exporter …` form **fails** — the image's entrypoint is **s6**, so it hits the
supervisor (`execlineb: unable to exec ifelse`). The `sh -lc 'cd … && python3 manage.py …'` form is
required.

Schedule the export **before** the sync window so a half-written zip is never shipped.

---

## 6. Action plan

Each phase is independently testable and ordered so nothing waits on something unbuilt.
**Verification is part of the phase** — a phase is not done until its check passes.

### Phase 1 — tool execution surface (blocks everything)
1. Install OliveTin on bumblebee as a quadlet; native `dnf install poppler-utils tesseract
   tesseract-langpack-deu tesseract-langpack-ita rsync python3-pillow`.
2. Deploy the skill's six scripts to a host path OliveTin can run.
3. Define actions taking **only a job id**: `snapshot`, `index`, `identify`, `check_filed`,
   `compare`, `file`, `reconcile`.
4. Traefik route + API key; bind so Hermes (`Network=host`) reaches it locally.
- **Verify:** each action runs from `curl` with an API key and returns stdout + exit code; a
  deliberately bad job id is rejected.

### Phase 2 — the pending queue and watcher
1. `pending/` outside any watched glob and outside every sync scope.
2. Watcher on `CLOSE_WRITE` (or stable size+mtime), assigns a job id, moves the file in, writes a
   sidecar with origin path and hash.
3. Every failure path quarantines with a reason code — no file may remain where the trigger sees it.
- **Verify:** drop 3 files including one with a space and `&` in the name; all three land in
  `pending/` with correct hashes; the watcher unit is still `active` (not failed) afterwards; then
  deliberately fail one and confirm no start-limit latch.

### Phase 3 — sync pairs (resolves Constraint 1)
1. Check cloud-drive-sync **#47** status first.
2. Add gdrive pairs for `Manu & I` and `Scanned` → bumblebee. Skip `.gdlink`/`.gdsheet`/`.gddoc`
   stubs (Google-native docs have no real local content).
3. Decide snapshot location outside the synced tree.
- **Verify:** file counts and a sha256 sample match the workstation; Nextcloud login stays responsive
  (`probe_success` for `nextcloud.optimusprime` stays 1) throughout the first full sync.

### Phase 4 — Hermes tooling + skill install
1. Install `document-filing` into `/opt/data/skills/`. ⚠️ **`hermes skills install` takes a registry
   identifier or an HTTPS URL to a SKILL.md — the README's local-directory form is UNVERIFIED.** The
   manual copy is known to work (discovery is `rglob("SKILL.md")`).
2. Keep the canonical copy **in this repo** and add an ansible task — `/opt/data` is not in git.
3. Point the skill's config keys at the bumblebee paths; teach it to call OliveTin rather than run
   scripts locally.
- **Verify:** `hermes skills list` shows it; `/document-filing` resolves as a slash command; ownership
  is uid 1000.

### Phase 5 — the ask, in Telegram
1. `TELEGRAM_ALLOWED_USERS` += Manu's numeric ID (from `@userinfobot`); **she must message the bot
   once** — bots cannot open a conversation.
2. Create the group, add both + the bot, capture the negative chat id.
3. 🔴 **Set `group_sessions_per_user: false`** — currently `true`, which gives each participant their
   own session and would send her answer to a different session from the one that asked. Affects
   groups only; the two DMs are unchanged.
4. Keep privacy mode **on** (`can_read_all_group_messages: False`) and answer by **replying** to the
   bot — that is precisely the "Hermes asks, either answers" flow, without ingesting other chatter.
5. Render the page (`pdftoppm`) and send it as a photo with the proposal; inline keyboard for
   approve / correct.
6. Route by detected addressee: Manu's documents → shared chat, yours → your DM, via
   `deliver: telegram:<chat_id>[:<thread_id>]`.
- **Verify:** a real proposal reaches the group; **she** answers; the answer reaches the same session.

### Phase 6 — callback
1. Enable the api_server platform with `API_SERVER_KEY`; keep it on loopback.
2. File the gdrive-sync callback request as a **GitHub issue**.
3. Add a low-frequency Hermes cron poll of `pending/` as the dead-man's-switch.
- **Verify:** a `curl` to `:8642` with the key starts a filing conversation; then break the callback
  deliberately and confirm the poll still picks the job up.

### Phase 7 — paperless copy + backup
1. On approval, copy (not move) the filed file into `consume/`.
2. Schedule `document_exporter` per §5, before the sync window; add a retention rule for the zips.
3. gsync `export/` → Nextcloud.
- **Verify:** a document appears in paperless with the Drive original untouched; a
  `document_importer` dry-run against a scratch instance restores from the zip.

---

## 7. Open decisions

1. **Whole archive or just `Manu & I`?** 3.9 of 5.1 GB gets most of it, and `routing_map.json` covers
   *destination* choice — but "already filed?" dedup and convention-derivation want the full tree.
   Syncing everything costs ~1.2 GB more on a volume with 347 GB free.
2. **`PAPERLESS_FILENAME_FORMAT` as well as the export?** Cheap belt-and-braces; makes `media/`
   legible without the DB.
3. **Zipped or incremental export?** Zip is simpler and safer; incremental transfers less but needs
   `--delete` against a synced folder.
4. **Should paperless see everything, or only newly-filed documents?** Backfilling 3,159 documents
   would give full-text search over the whole archive — a much bigger ingest, and its OCR would run
   on the GPU box.
5. **Second Hermes instance for Manu?** Memory and toolset are global today: her chat shares
   `MEMORY.md`/`USER.md` and gets the HA admin token. Isolation needs a separate instance.

---

## 8. Related records

- Skill and its blockers: `project_document_filing_skill` (memory)
- Hermes multi-chat mechanics, API server, skills install: `project_hermes_migration` (memory)
- Level-triggered `.path` jam and the quarantine fix: `reference_movie_rename_pipeline` (memory)
- Nextcloud PROPFIND DoS and the nginx guard: `project_cloud_drive_sync_propfind_dos` (memory)
- GPU shared with Frigate: `reference_frigate_nvr` (memory)
- Superseded auto-filing design: `project_pending_tasks` (memory)
