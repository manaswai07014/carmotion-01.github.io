#!/usr/bin/env python3
"""
backup.py — Python backup for cars.db using SQLite VACUUM INTO
Replaces backup.sh which requires sqlite3 CLI (may not be installed)
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import sys, os

HOME = Path.home()
DB = HOME / "car-evolution-project" / "data" / "cars.db"
BACKUP_DIR = HOME / "car-evolution-project" / "data" / "backups"
KEEP = 8  # keep last N backups

def backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"cars_{ts}.db"

    if not DB.exists():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] [BACKUP] DB not found: {DB}")
        return False

    BACKUP_DIR.mkdir(exist_ok=True)

    try:
        conn = sqlite3.connect(DB)
        conn.execute(f"VACUUM INTO '{backup_file}'")  # atomic, no sqlite3 CLI needed
        conn.close()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] [BACKUP] cars_{ts}.db saved")

        # Keep only last KEEP backups
        backups = sorted(BACKUP_DIR.glob("cars_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[KEEP:]:
            old.unlink()
            print(f"  [CLEANUP] removed: {old.name}")

        print(f"Backup complete: cars_{ts}.db")
        return True
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] [BACKUP] ERROR: {e}")
        return False

if __name__ == "__main__":
    backup()
