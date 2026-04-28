#!/usr/bin/env python3
# scripts/backup.py
# Manual database backup
# Usage: python3 scripts/backup.py

import sqlite3, shutil, json
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent.parent
DB     = BASE / "data" / "cars.db"
BACKUP = BASE / "backups"

def main():
    if not DB.exists():
        print("No database found at {0}".format(DB))
        return

    BACKUP.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP / "car_wiki_{0}.db".format(ts)
    out_gz = BACKUP / "car_wiki_{0}.db.gz".format(ts)

    # SQLite backup
    conn = sqlite3.connect(str(DB))
    bak = sqlite3.connect(str(out))
    conn.backup(bak)
    bak.close()
    conn.close()

    # Compress
    import gzip
    with open(out, "rb") as f_in:
        with gzip.open(out_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    out.unlink()

    size = out_gz.stat().st_size
    print("Backup complete: {0} ({1:,} bytes)".format(out_gz.name, size))

    # Keep last 10 backups
    backups = sorted(BACKUP.glob("car_wiki_*.db.gz"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-10]:
        old.unlink()
        print("Removed old: {0}".format(old.name))

if __name__ == "__main__":
    main()
