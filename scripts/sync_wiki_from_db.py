#!/usr/bin/env python3
"""Sync wiki generation pages + index.md from DB.
Usage: python3 scripts/sync_wiki_from_db.py
"""
import sqlite3
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "cars.db")
WIKI_GEN_DIR = os.path.join(BASE, "wiki", "generations")
INDEX_PATH = os.path.join(BASE, "wiki", "index.md")

os.makedirs(WIKI_GEN_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute('''
    SELECT g.slug, g.gen_code, g.name, g.year_start, g.year_end,
           g.platform, g.primary_engine, g.hp_official, g.hp_source, g.hp_tier,
           g.primary_image_url, g.image_source_url, g.image_verified,
           g.market, g.status,
           s.name as series_name, s.slug as series_slug,
           b.name as brand_name, b.slug as brand_slug
    FROM generations g
    LEFT JOIN series s ON g.series_id = s.id
    LEFT JOIN brands b ON s.brand_id = b.id
    ORDER BY b.name, g.name
''')
rows = c.fetchall()
conn.close()

now = datetime.now().strftime("%Y-%m-%d %H:%M")
count = 0

for r in rows:
    slug = r[0]
    gen_code = r[1] or "—"
    name = r[2]
    year_start = r[3] if r[3] else "—"
    year_end = r[4] if r[4] else "present"
    platform = r[5] or "—"
    engine = r[6] or "—"
    hp = r[7] if r[7] else "—"
    hp_source = r[8] or "—"
    hp_tier = r[9] or ""
    image_url = r[10] or ""
    image_source = r[11] or ""
    image_verified = "✅" if r[12] else "❌"
    market = r[13] or "—"
    status = r[14] or "draft"
    series_name = r[15] or "—"
    brand_name = r[17] or "—"
    brand_slug = r[18] or "—"

    year_str = f"{year_start}–{year_end}" if year_start != "—" else "—"

    # Metadata block for lint compatibility (lint checks for these fields)
    img_verified_str = "true" if r[12] else "false"

    content = f"""# 🅿️ {name} ({year_str})

> Generation wiki page — synced from DB on {now}

## Spec Sheet
- **Brand/Series:** {brand_name} / {series_name}
- **Gen Code:** `{gen_code}`
- **Years:** {year_str}
- **Platform:** {platform}
- **Engine:** {engine}
- **HP:** {hp} PS (source: {hp_source})
- **Market:** {market}
- **Status:** {status}
- **Image Verified:** {image_verified}

"""
    if image_url:
        content += f"## Reference Image\n![{name}]({image_url})\n\nSource: {image_source}\n\n"
    else:
        content += f"## Reference Image\n⚠️ No image set — needs manual verification\n\n"

    content += f"""## Notes
- This page was auto-generated from DB sync on {now}
- All HP values should be verified against original sources before use in Shorts scripts
- See `wiki/brands/{brand_slug}/` for brand-level context

---
## Metadata (lint-readable)
primary_image_url: {image_url if image_url else ""}
image_verified: {img_verified_str}
gen_code: {gen_code}
hp_official: {hp}
hp_source: {hp_source if hp_source != "—" else ""}
hp_tier: {hp_tier if hp_tier else ""}
year_start: {year_start}
year_end: {year_end}
status: {status}

*Last updated: {now}*
"""

    out_path = os.path.join(WIKI_GEN_DIR, f"{slug}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    count += 1

# Update index.md
published = sum(1 for r in rows if r[14] == 'published')
draft = sum(1 for r in rows if r[14] != 'published')
brand_set = set(r[17] for r in rows if r[17])

index_content = f"""# Car Wiki — Index
Updated: {datetime.now().strftime('%Y-%m-%d')} | Architecture: V4.1

## Quick Stats
- Total Generations: {len(rows)} ({published} published, {draft} draft)
- Total Brands: {len(brand_set)}
- Last Ingest: {now}

## Brands
"""
for b in sorted(brand_set):
    brand_gens = [r for r in rows if r[17] == b]
    brand_slug = brand_gens[0][18] if brand_gens else ""
    index_content += f"- [{b}](brands/{brand_slug}/index.md) ({len(brand_gens)} generations)\n"

index_content += f"""
## Topics
- [JDM Regulations](topics/jdm-regulations.md)
- [Gentleman's Agreement](topics/gentlemans-agreement.md)

## Sub-Indexes
See individual brand pages for series and generation indexes.
"""

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(index_content)

print(f"[OK] Generated {count} wiki generation pages")
print(f"[OK] Updated index.md: {len(rows)} generations, {len(brand_set)} brands")
print(f"     Published: {published}, Draft: {draft}")
