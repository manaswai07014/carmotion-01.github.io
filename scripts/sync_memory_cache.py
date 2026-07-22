#!/usr/bin/env python3
"""
sync_memory_cache.py
====================
將 Wiki 數據同步到 triples.jsonl + hot-cache.json
保持記憶沉澱機制正常運作

Usage:
    python3 scripts/sync_memory_cache.py --brand Porsche
    python3 scripts/sync_memory_cache.py --all
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
MEMORY = BASE / 'memory'
TRIPLES = MEMORY / 'triples.jsonl'
HOT_CACHE = MEMORY / 'hot-cache.json'
WIKI = BASE / 'wiki'


def load_existing_triples():
    """Load existing triples to avoid duplicates"""
    if not TRIPLES.exists():
        return set()
    existing = set()
    with open(TRIPLES, encoding='utf-8') as f:
        for line in f:
            try:
                t = json.loads(line)
                key = f"{t.get('s', '')}|{t.get('p', '')}|{t.get('o', '')}"
                existing.add(key)
            except:
                pass
    return existing


def extract_hp_from_content(content):
    """Extract horsepower from wiki content"""
    hp_patterns = [
        r'(\d+[\d,]*)\s*(?:hp|HP|匹|馬力)',
        r'(\d+)\s*kW.*?(\d+)\s*PS',
        r'power[:\s]+(\d+[\d,]*)',
    ]
    for pattern in hp_patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).replace(',', '') + ' hp'
    return None


def extract_years_from_content(content):
    """Extract year range from wiki content"""
    year_pattern = r'(\d{4})[-–](\d{4}|present|now|current)'
    match = re.search(year_pattern, content)
    if match:
        return match.group(1), match.group(2)
    # Single year
    single = re.search(r'year[:\s]+(\d{4})', content, re.IGNORECASE)
    if single:
        return single.group(1), 'present'
    return None, None


def brand_to_slug(brand):
    """Convert brand name to slug"""
    return brand.lower().replace(' ', '-')


def sync_brand(brand, dry_run=False):
    """Sync a single brand's wiki data to triples.jsonl"""
    existing = load_existing_triples()
    new_count = 0
    
    brand_dir = WIKI / 'brands' / brand.lower()
    if not brand_dir.exists():
        print(f"⚠️  Brand wiki not found: {brand}")
        return 0
    
    # Collect all generation data
    gen_dir = WIKI / 'generations'
    brand_gens = []
    
    if gen_dir.exists():
        for gen_file in gen_dir.rglob('*.md'):
            content = gen_file.read_text(encoding='utf-8', errors='ignore')
            # Check if this generation belongs to this brand
            brand_slug = brand.lower()
            if brand_slug in gen_file.stem.lower() or brand_slug in content.lower():
                slug = gen_file.stem
                hp = extract_hp_from_content(content)
                year_start, year_end = extract_years_from_content(content)
                
                if hp:
                    key = f"{slug}|official_horsepower|{hp}"
                    if key not in existing:
                        new_count += 1
                        if not dry_run:
                            triple = {
                                's': slug,
                                'p': 'official_horsepower',
                                'o': hp,
                                'conf': 0.85,
                                'tier': 2,
                                'source': 'wiki',
                                'ts': datetime.now().strftime('%Y-%m-%d'),
                            }
                            with open(TRIPLES, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(triple, ensure_ascii=False) + '\n')
                
                if year_start:
                    key = f"{slug}|year_start|{year_start}"
                    if key not in existing:
                        new_count += 1
                        if not dry_run:
                            triple = {
                                's': slug,
                                'p': 'year_start',
                                'o': year_start,
                                'conf': 0.95,
                                'tier': 1,
                                'source': 'wiki',
                                'ts': datetime.now().strftime('%Y-%m-%d'),
                            }
                            with open(TRIPLES, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(triple, ensure_ascii=False) + '\n')
                
                if year_end:
                    key = f"{slug}|year_end|{year_end}"
                    if key not in existing:
                        new_count += 1
                        if not dry_run:
                            triple = {
                                's': slug,
                                'p': 'year_end',
                                'o': year_end,
                                'conf': 0.95,
                                'tier': 1,
                                'source': 'wiki',
                                'ts': datetime.now().strftime('%Y-%m-%d'),
                            }
                            with open(TRIPLES, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(triple, ensure_ascii=False) + '\n')
    
    # Update hot-cache.json for this brand
    hot = {}
    if HOT_CACHE.exists():
        try:
            hot = json.loads(HOT_CACHE.read_text(encoding='utf-8'))
        except:
            hot = {}
    
    brand_data = {'nodes': {}, 'last_updated': datetime.now().strftime('%Y-%m-%d')}
    
    # Find series for this brand
    series_dir = WIKI / 'series' / brand.lower()
    if series_dir.exists():
        for series_file in series_dir.glob('*.md'):
            content = series_file.read_text(encoding='utf-8', errors='ignore')
            model_name = series_file.stem.replace(f'{brand.lower()}-', '').replace('-', ' ').title()
            hp = extract_hp_from_content(content)
            years = extract_years_from_content(content)
            year_str = f"{years[0]}–{years[1]}" if years[0] else 'unknown'
            
            node_id = len(brand_data['nodes']) + 1
            brand_data['nodes'][model_name] = {
                'node_id': f'** {node_id}',
                'year': year_str,
                'hp': hp or 'n/a',
                'source': 'wiki',
            }
    
    hot[brand.lower()] = brand_data
    
    if not dry_run:
        HOT_CACHE.write_text(json.dumps(hot, ensure_ascii=False, indent=2), encoding='utf-8')
    
    return new_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sync wiki data to memory cache')
    parser.add_argument('--brand', type=str, help='Sync specific brand')
    parser.add_argument('--all', action='store_true', help='Sync all brands')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()
    
    if args.dry_run:
        print('[DRY RUN] Would sync:')
    
    if args.brand:
        count = sync_brand(args.brand, dry_run=args.dry_run)
        print(f"{'[DRY RUN] Would add' if args.dry_run else 'Added'} {count} triples for {args.brand}")
    elif args.all:
        brands = [d.name for d in (WIKI / 'brands').iterdir() if d.is_dir() and not d.name.startswith('.')]
        total = 0
        for brand in brands:
            count = sync_brand(brand, dry_run=args.dry_run)
            if count > 0:
                print(f"{'[DRY RUN] Would add' if args.dry_run else 'Added'} {count} triples for {brand}")
                total += count
        print(f"\nTotal: {total} new triples")
    else:
        print('Usage: sync_memory_cache.py --brand Porsche --dry-run')
        sys.exit(1)


if __name__ == '__main__':
    main()
