#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-/home/amine/sensors.db}"
BACKUP_DIR="${2:-/home/amine/backup}"

mkdir -p "$BACKUP_DIR"
cp "$DB_PATH" "$BACKUP_DIR/sensors_$(date +%F_%H-%M-%S).db"
ls -1t "$BACKUP_DIR" | head -n 5
