#!/bin/bash
# Nightly dump of the Infisical database (infisical-backup.timer: 03:15 daily + 20 min after boot).
#
# Where: /mnt/data/backups/infisical/ (root 0700), 14 days kept. That is the same RAID5 as the
# live database: it protects against corruption, bad upgrades and deletion, NOT against losing
# the array (owner's choice, 2026-11-12).
# No extra encryption: the secrets inside are already encrypted with Infisical's ENCRYPTION_KEY
# (in /etc/containers/secrets/infisical.env and the owner's LastPass); without that key a dump is
# useless, with it the dump plus infisical.env restores everything.
#
# Success signal: /tmp/node_exporter/infisical_backup.prom (alerts InfisicalBackupStale /
# InfisicalBackupMissing in config/prometheus/alerts.yml). Failure: OnFailure -> Telegram.
#
# Restore (into an EMPTY database, Infisical stopped):
#   systemctl stop infisical.service
#   podman exec infisical-db dropdb -U infisical infisical
#   podman exec infisical-db createdb -U infisical infisical
#   podman exec -i infisical-db pg_restore -U infisical -d infisical --no-owner < <dump>
#   systemctl start infisical.service      # needs the SAME ENCRYPTION_KEY in infisical.env
set -euo pipefail

DIR=/mnt/data/backups/infisical
KEEP_DAYS=14
PROM=/tmp/node_exporter/infisical_backup.prom
OUT="$DIR/infisical-$(date +%Y%m%d-%H%M%S).dump"

# After a boot the database may still be starting: wait up to 10 min for it to be healthy.
for _ in $(seq 1 120); do
    [ "$(podman inspect infisical-db --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ] && break
    sleep 5
done
[ "$(podman inspect infisical-db --format '{{.State.Health.Status}}')" = healthy ] \
    || { echo "infisical-db not healthy after 10 min"; exit 1; }

install -d -m 0700 -o root -g root "$DIR"
TMP=$(mktemp "$DIR/.partial-XXXXXX")
trap 'rm -f "$TMP"' EXIT

podman exec infisical-db pg_dump -U infisical -d infisical --format=custom > "$TMP"

# Verify before keeping it: the archive must be readable and contain the core tables' data.
TOC=$(podman exec -i infisical-db pg_restore --list < "$TMP")
ENTRIES=$(grep -c ' TABLE DATA public ' <<< "$TOC" || true)
for t in users organizations projects secrets_v2 kms_keys; do
    grep -q " TABLE DATA public $t " <<< "$TOC" || { echo "dump lacks table data for $t"; exit 1; }
done
[ "$ENTRIES" -gt 50 ] || { echo "dump looks incomplete: only $ENTRIES table-data entries"; exit 1; }

chmod 0600 "$TMP"
mv "$TMP" "$OUT"
trap - EXIT
SIZE=$(stat -c %s "$OUT")

find "$DIR" -maxdepth 1 -type f -name 'infisical-*.dump' -mtime +"$KEEP_DAYS" -delete
KEPT=$(find "$DIR" -maxdepth 1 -type f -name 'infisical-*.dump' | wc -l)

mkdir -p "$(dirname "$PROM")"
cat > "$PROM.tmp" <<EOF
# HELP infisical_backup_last_success_timestamp_seconds Unix time of the last verified Infisical DB dump.
# TYPE infisical_backup_last_success_timestamp_seconds gauge
infisical_backup_last_success_timestamp_seconds $(date +%s)
# HELP infisical_backup_last_size_bytes Size of the last verified Infisical DB dump.
# TYPE infisical_backup_last_size_bytes gauge
infisical_backup_last_size_bytes $SIZE
# HELP infisical_backup_table_data_entries Table-data entries in the last dump's table of contents.
# TYPE infisical_backup_table_data_entries gauge
infisical_backup_table_data_entries $ENTRIES
# HELP infisical_backup_files Infisical dumps currently kept.
# TYPE infisical_backup_files gauge
infisical_backup_files $KEPT
EOF
chmod 0644 "$PROM.tmp"
mv "$PROM.tmp" "$PROM"

echo "ok: $OUT ($SIZE bytes, $ENTRIES table-data entries, $KEPT dumps kept)"
