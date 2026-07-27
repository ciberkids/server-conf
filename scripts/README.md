# Scripts

Utility scripts for managing homelab services.

**Where each runs:** `optimus-prime/` on OP (192.168.1.10), `bumblebee/` on bumblebee
(192.168.1.14), `file-tools/` on either (host-agnostic). Everything else defaults to
**Optimus Prime** unless noted.

Note that scripts under `optimus-prime/` and `bumblebee/` are the git copy — editing them here does
**not** deploy them. They must be copied to the host (see `feedback_deploy_quadlets_to_server` in
memory); several are referenced by systemd units in `systemd/` or by `ansible/setup-workstation.yml`.

## Directory Structure

```
scripts/
├── optimus-prime/    # Host-specific: OP systemd units, metrics, movie pipeline, PTZ bridge
├── bumblebee/        # Host-specific: notifications, nvidia-reboot, opencode setup
├── file-tools/       # Host-agnostic: compare/dedupe/merge directory trees
├── jellyfin/         # Jellyfin media server utilities
├── influxdb/         # InfluxDB data migration & maintenance
├── grafana/          # Grafana dashboard management
├── city_hunter_rip/  # One-off DVD rip/encode pipelines
├── gits_rip/         # ditto
├── yattaman_split/   # ditto
└── alarm             # Alertmanager per-service silence helper
```

## file-tools

Host-agnostic utilities for reconciling two directory trees — written 2026-07-27 while
consolidating the PS2 ROM collection (see `reference_ps2_rom_collection` in memory).
They are a **deliberate pair**, and picking the wrong one is the main hazard:

| Script | Compares by | Use when |
|--------|-------------|----------|
| `find_missing_or_duplicated.sh` | **content** (sha256) | You need to know what's genuinely redundant regardless of filename. Read-only — reports, never modifies. |
| `merge_dirs.sh` | **name / relative path** | You want to actually merge A into B. Dry-run by default; quarantines duplicates instead of deleting them. |

`merge_dirs.sh` says so itself: *"this is NAME/PATH-based, not content-based… same content under a
different name/path is NOT detected (use the hash script for that)."*

### find_missing_or_duplicated.sh

```bash
./find_missing_or_duplicated.sh [--format text|json] [--summary] \
    [--cache FILE] [--resume] <original_dir> <other_dir1> [other_dir2] ...
```

Hashes every file in `<original_dir>` and looks for that hash in the other directories. JSON
output needs `jq`. `--cache FILE` persists hashes so an interrupted run resumes and only
new/changed files (by size+mtime) are re-hashed — worth using on hundreds of GB.

> ### ⚠️ "missing" does NOT mean the file is gone
>
> It means **missing from the *other* directories** — i.e. the file exists **only** in
> `<original_dir>`. So in the output:
>
> - **`missing` = unique = the files to KEEP** (often the only copy in existence)
> - **`duplicated` = redundant in the original = safe to delete there**
>
> Reading it the intuitive way deletes exactly the wrong files. On 2026-07-27 the 19 "missing"
> entries were the only surviving copies of the alphabetical head of the PS2 collection.

### merge_dirs.sh

```bash
./merge_dirs.sh [--apply] [--duplicates DIR] <A_dir> <B_dir>
```

Without `--apply` it is a **dry run** (`rsync -n`) and changes nothing. With `--apply`:

1. `rsync --ignore-existing --remove-source-files` copies only files unique to A into B, removing
   them from A as they transfer. Files already in B are skipped, so they stay in A.
2. Whatever is left in A is therefore a duplicate → moved to `--duplicates DIR`
   (default `./duplicates`) rather than deleted.
3. The empty directory skeleton left in A is removed.

You then review the quarantine directory and delete it yourself. Nothing is destroyed by the
script itself.

### Checks worth repeating for any dedupe of media

- **Never split a `.cue`/`.bin` pair** — deleting one half silently breaks the disc image. Group by
  filename stem and confirm both halves have the same status before acting.
- **Re-verify the copy you're keeping still exists, immediately before each delete** — a report is
  a point-in-time claim, not a live fact.
- **Relocate irreplaceable files first, delete redundant ones second**, so aborting mid-run can't
  lose anything.
- **Same filesystem → `mv`/`rename` is instant** (metadata only). Check with `stat -c %d` first;
  only reach for `rsync` across filesystems.

## Jellyfin

| Script | Description | When to use |
|--------|-------------|-------------|
| `fix_jellyfin_metadata.py` | Auto-identifies movies without TMDB metadata by extracting name and year from filename, searching TMDB, and applying the match | After adding new movies that Jellyfin failed to identify |
| `fix_jellyfin_remaining.py` | Manually fixes specific movies that the auto-fix couldn't match, and creates collections | One-off fixes for edge cases |
| `create_nfo_files.py` | Generates `.nfo` sidecar files (with TMDB/IMDB IDs) for all movies in `1 Sagas/`, `2 Anime/`, `5 SD Movies/` folders | After fixing metadata — prevents Jellyfin from re-guessing names from folder structure on next scan |

### Jellyfin NFO workflow

Jellyfin reads parent folder names as movie titles, which breaks the `1 Sagas/FolderName/` structure. The `.nfo` files override this behavior:

1. Add new movie to a saga folder
2. Open Jellyfin UI → find the movie → click **Identify** → search and confirm
3. Run `create_nfo_files.py` to generate `.nfo` for any movie that doesn't have one yet
4. Future library scans will use the `.nfo` instead of guessing

## InfluxDB

| Script | Description | When to use |
|--------|-------------|-------------|
| `backport_ha.py` | Exports **all** Home Assistant hourly statistics from PostgreSQL (TimescaleDB) to InfluxDB `homeassistant` bucket | One-time migration after setting up InfluxDB |
| `backport_solar.py` | Exports **solar and energy** statistics specifically, with integer timestamp fix | Run after `backport_ha.py` if solar/energy data is missing |

### Backport notes

- Source: PostgreSQL at `192.168.1.10:5432` (database `homedata`, user `homeassistant`)
- Destination: InfluxDB at `192.168.1.10:8086` (org `favarohome`, bucket `homeassistant`)
- Backported data is tagged with `source=backport` to distinguish from live HA data
- Safe to re-run — InfluxDB deduplicates by timestamp+tags

## Grafana

| Script | Description | When to use |
|--------|-------------|-------------|
| `create_yoy_dashboard.py` | Creates/updates the Solar Production Year-over-Year dashboard via Grafana API | After changing the dashboard layout or adding new years |

### Grafana API access

All Grafana scripts use `admin:admin` basic auth at `http://localhost:3000`. Dashboard UIDs are hardcoded — update them if dashboards are recreated.
