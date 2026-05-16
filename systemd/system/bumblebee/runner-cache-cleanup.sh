#!/bin/bash
set -euo pipefail
find /var/lib/containers/storage/volumes -maxdepth 1 -name 'runner-*-cache-*' -type d | while read -r vol; do
    find "$vol/_data" -mindepth 3 -maxdepth 3 -type d -mtime +14 -exec rm -rf {} +
done
