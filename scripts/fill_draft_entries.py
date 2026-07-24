#!/usr/bin/env python3
"""Fill draft DB entries with researched specs.
Usage: python3 scripts/fill_draft_entries.py
Updates: hp_official, hp_source, hp_tier, primary_engine, platform,
         year_start, year_end, primary_image_url, image_source_url, image_verified, status
"""
import sqlite3
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "cars.db")

# Researched data — only verifiable data from Wikipedia / official sources
# Format: slug -> {field: value}
UPDATES = {
    "db5": {
        "hp_official": 286,
        "hp_source": "Wikipedia (Aston Martin DB5) — 282 bhp ≈ 286 PS",
        "hp_tier": 2,
        "primary_engine": "4.0L Tadek Marek I6 DOHC",
        "platform": "Aston Martin DB platform",
        "year_start": 1963,
        "year_end": 1965,
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Aston_Martin_DB5_%22FIA%22_001.jpg/330px-Aston_Martin_DB5_%22FIA%22_001.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Aston_Martin_DB5",
        "image_verified": 0,
        "status": "published",
    },
    "db11": {
        "hp_official": 608,
        "hp_source": "Wikipedia (Aston Martin DB11)",
        "hp_tier": 2,
        "primary_engine": "5.2L Twin-Turbo AMG V12",
        "platform": "Aston Martin DB11 platform",
        "year_start": 2017,
        "year_end": 2023,
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/2017_Aston_Martin_DB11_V12_5.2_Front.jpg/330px-2017_Aston_Martin_DB11_V12_5.2_Front.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Aston_Martin_DB11",
        "image_verified": 0,
        "status": "published",
    },
    "dbs-superleggera": {
        "hp_official": 725,
        "hp_source": "Wikipedia (Aston Martin DBS Superleggera)",
        "hp_tier": 2,
        "primary_engine": "5.2L Twin-Turbo AMG V12",
        "platform": "Aston Martin DB11 platform",
        "year_start": 2019,
        "year_end": 2024,
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/64/2019_Aston_Martin_DBS_Superleggera_V12%2C_Front_Left%2C_HK.jpg/330px-2019_Aston_Martin_DBS_Superleggera_V12%2C_Front_Left%2C_HK.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Aston_Martin_DBS_Superleggera",
        "image_verified": 0,
        "status": "published",
    },
    "vantage": {
        "hp_official": 510,
        "hp_source": "Wikipedia (Aston Martin Vantage)",
        "hp_tier": 2,
        "primary_engine": "4.0L Twin-Turbo AMG V8",
        "platform": "Aston Martin VH platform",
        "year_start": 2018,
        "year_end": None,  # present
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/2018_Aston_Martin_Vantage_V8.jpg/330px-2018_Aston_Martin_Vantage_V8.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Aston_Martin_Vantage_(2018)",
        "image_verified": 0,
        "status": "published",
    },
    "f-type": {
        "hp_official": 575,
        "hp_source": "Wikipedia (Jaguar F-Type)",
        "hp_tier": 2,
        "primary_engine": "5.0L Supercharged V8",
        "platform": "D6a platform",
        "year_start": 2013,
        "year_end": 2024,
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/2021_Jaguar_F-Type_P450_AWD%2C_front_8.16.21.jpg/330px-2021_Jaguar_F-Type_P450_AWD%2C_front_8.16.21.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Jaguar_F-Type",
        "image_verified": 0,
        "status": "published",
    },
    "i-pace": {
        "hp_official": 400,
        "hp_source": "Wikipedia (Jaguar I-Pace)",
        "hp_tier": 2,
        "primary_engine": "Dual Electric Motors (90 kWh battery)",
        "platform": "JLR D7e EV platform",
        "year_start": 2018,
        "year_end": 2024,
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Jaguar_I-PACE_%2821503556989%29.jpg/330px-Jaguar_I-PACE_%2821503556989%29.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/Jaguar_I-Pace",
        "image_verified": 0,
        "status": "published",
    },
    "ix3": {
        "hp_official": 286,
        "hp_source": "Wikipedia (BMW iX3)",
        "hp_tier": 2,
        "primary_engine": "Single Electric Motor (80 kWh battery)",
        "platform": "BMW G01 (X3) platform",
        "year_start": 2020,
        "year_end": None,  # present
        "primary_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/BMW_iX3_IMG_8651.jpg/330px-BMW_iX3_IMG_8651.jpg",
        "image_source_url": "https://en.wikipedia.org/wiki/BMW_iX3",
        "image_verified": 0,
        "status": "published",
    },
    "sq9": {
        # SQ9 does not exist as a production Audi model. Leave as draft.
        # Will be flagged for manual review.
        "status": "draft",
    },
}

FIELDS = [
    "hp_official", "hp_source", "hp_tier", "primary_engine",
    "platform", "year_start", "year_end",
    "primary_image_url", "image_source_url", "image_verified", "status",
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

updated = 0
skipped = 0
for slug, data in UPDATES.items():
    if not data:
        skipped += 1
        continue
    # Build UPDATE SET clause
    set_parts = []
    set_values = []
    for field in FIELDS:
        if field in data:
            set_parts.append(f"{field} = ?")
            set_values.append(data[field])
    
    if not set_parts:
        skipped += 1
        continue
    
    set_parts.append("updated_at = ?")
    set_values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    set_values.append(slug)
    
    sql = f"UPDATE generations SET {', '.join(set_parts)} WHERE slug = ?"
    c.execute(sql, set_values)
    
    if c.rowcount > 0:
        updated += 1
        print(f"  [OK] {slug}: updated {len(data)} fields")
    else:
        skipped += 1
        print(f"  [SKIP] {slug}: no matching row")

conn.commit()
conn.close()

print(f"\n[Done] Updated: {updated} | Skipped: {skipped}")
print("Note: SQ9 has no real production model — left as draft for manual review.")
