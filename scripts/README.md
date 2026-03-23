# Scripts

Utility scripts for managing homelab services. All scripts are designed to run on **Optimus Prime** (192.168.1.10) unless noted otherwise.

## Directory Structure

```
scripts/
├── jellyfin/        # Jellyfin media server utilities
├── influxdb/        # InfluxDB data migration & maintenance
└── grafana/         # Grafana dashboard management
```

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
