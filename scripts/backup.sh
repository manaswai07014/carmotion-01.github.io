#!/bin/bash
# scripts/backup.sh
# Backup cars.db to data/backups/
# Run: bash scripts/backup.sh
# Auto-schedule: 0 2 * * 0 (weekly on Sunday at 02:00 HKT)

DATE=$(date +%Y%m%d_%H%M%S)
DB="$HOME/car-evolution-project/data/cars.db"
BACKUP_DIR="$HOME/car-evolution-project/data/backups"

mkdir -p "$BACKUP_DIR"

if [ -f "$DB" ]; then
    sqlite3 "$DB" ".backup $BACKUP_DIR/cars_${DATE}.db"
    echo "[$(date '+%Y-%m-%d %H:%M')] [BACKUP] cars_${DATE}.db saved"
    # Keep only last 8 backups
    cd "$BACKUP_DIR" && ls -t cars_*.db | tail -n +9 | xargs -r rm
    echo "Backup complete: cars_${DATE}.db"
else
    echo "[$(date '+%Y-%m-%d %H:%M')] [BACKUP] DB not found: $DB"
fi
