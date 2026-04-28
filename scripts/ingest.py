#!/usr/bin/env python3
# scripts/ingest.py
# Ingest a car brand/series/generation into the wiki
# Usage: python3 scripts/ingest.py <brand> [series] [generation]
# Example: python3 scripts/ingest.py Bugatti
#          python3 scripts/ingest.py Nissan GT-R R35

import re, sys, sqlite3, json
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
DB    = BASE / 'data' / 'cars.db'
WIKI  = BASE / 'wiki'
LOG   = WIKI / 'log.md'
INDEX = WIKI / 'index.md'

def log(msg):
    print(msg)

def slugify(text: str) -> str:
    text = text.lower().replace(' ', '-').replace('/', '-')
    return re.sub(r'[^a-z0-9\-]', '', text)

def append_log(action, detail=''):
    if not LOG.exists(): return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [INGEST] {action}'
    if detail: entry += f' — {detail}'
    entry += '\n'
    with open(LOG, 'a', encoding='utf-8') as f: f.write(entry)

def fetch_html(url: str) -> str:
    import urllib.request, ssl
    CTX = ssl.create_default_context()
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log(f'  [WARN] fetch failed: {e}')
        return ''

def extract_hp(text: str) -> str:
    m = re.search(r'(\d{3,4})\s*(?:hp|ps|cv)', text, re.I)
    return m.group(1) if m else ''

def extract_engine(text: str) -> str:
    m = re.search(r'([0-9.]+L|[0-9.]+l)\s*(?:twin[\-\s]?turbo\s*)?(V[0-9]|inline[0-9]|flat[0-9]|[IVX0-9]+\s*Cylinder)', text, re.I)
    return m.group(0) if m else ''

def research_brand(brand: str) -> dict:
    """Research a car brand — returns dict with info."""
    log(f'🔍 Researching brand: {brand}')
    info = {'name': brand, 'type': 'brand', 'models': [], 'slug': slugify(brand)}
    
    wiki_url = f'https://en.wikipedia.org/wiki/{brand.replace(" ", "_")}'
    html = fetch_html(wiki_url)
    
    if not html:
        info['notes'] = 'Research from web search'
        return info
    
    # Extract country
    country_m = re.search(r' headquartered in ([^.<]+)', html)
    if country_m:
        info['country'] = country_m.group(1).strip()
    
    # Extract founded year
    founded_m = re.search(r'founded.*?(\d{4})', html, re.I)
    if founded_m:
        info['founded'] = founded_m.group(1)
    
    # Extract description
    desc_m = re.search(r'<p>(.{200,800}?)</p>', html, re.I)
    if desc_m:
        text = re.sub(r'<[^>]+>', '', desc_m.group(1))
        text = re.sub(r'\[.*?\]', '', text)
        info['description'] = text[:500].strip()
    
    log(f'  ✅ {brand} — founded {info.get("founded","?")} in {info.get("country","?")}')
    return info

def research_series(brand: str, series: str) -> dict:
    """Research a car series."""
    log(f'🔍 Researching series: {series}')
    info = {'name': series, 'type': 'series', 'brand': brand, 'slug': slugify(series)}
    
    wiki_url = f'https://en.wikipedia.org/wiki/{series.replace(" ", "_")}'
    html = fetch_html(wiki_url)
    
    if not html:
        info['notes'] = 'Research from web'
        return info
    
    # Try to find model lineup
    models_m = re.findall(r'<li>.*?(?:GT|R|S|V8|V6|Turbo|AMG|M|Power|Coupe|Convertible|Sport).*?</li>', html, re.I)
    if models_m:
        info['models'] = [re.sub(r'<[^>]+>', '', m)[:80] for m in models_m[:8]]
    
    log(f'  ✅ {series} — {len(info["models"])} variants found')
    return info

def research_generation(brand: str, series: str, gen: str) -> dict:
    """Research a specific car generation."""
    log(f'🔍 Researching generation: {gen}')
    info = {
        'name': gen, 'type': 'generation',
        'brand': brand, 'series': series,
        'slug': slugify(gen),
        'hp_official': '', 'hp_source': '', 'hp_tier': 3,
        'primary_engine': '', 'engine_code': '',
        'year_start': '', 'year_end': '',
        'platform': '', 'market': '',
        'primary_image_url': '',
        'status': 'draft', 'completeness_score': 0,
    }
    
    # Build search query
    search = f'{brand} {series} {gen}'.replace(' ', '+')
    wiki_url = f'https://en.wikipedia.org/wiki/{gen.replace(" ", "_")}'
    html = fetch_html(wiki_url)
    
    if not html:
        log(f'  [WARN] No Wikipedia page for {gen}, using general search')
        info['notes'] = 'Needs manual research'
        return info
    
    # Extract HP
    hp = extract_hp(html)
    if hp:
        info['hp_official'] = hp
        info['hp_source'] = 'Wikipedia'
        info['hp_tier'] = 3  # Tier 3 = Wikipedia
    
    # Extract engine
    engine = extract_engine(html)
    if engine:
        info['primary_engine'] = engine
    
    # Extract years
    year_m = re.search(r'(\d{4})\s*[–\-—]\s*(\d{4}|present)', html)
    if year_m:
        info['year_start'] = year_m.group(1)
        info['year_end'] = year_m.group(2).replace('present', datetime.now().strftime('%Y'))
    
    # Extract platform
    platform_m = re.search(r'platform[:\s]+([A-Z0-9\-]+)', html, re.I)
    if platform_m:
        info['platform'] = platform_m.group(1).strip()
    
    # Extract description
    desc_m = re.search(r'<p>(.{200,1000}?)</p>', html, re.I)
    if desc_m:
        text = re.sub(r'<[^>]+>', '', desc_m.group(1))
        text = re.sub(r'\[.*?\]', '', text)
        info['description'] = text[:600].strip()
    
    # Try to get an image
    img_m = re.search(r'file=([^"&]+(?:\.jpg|\.jpeg|\.png|\.webp))', html, re.I)
    if img_m:
        info['primary_image_url'] = f'https://en.wikipedia.org/wiki/Special:FilePath/{img_m.group(1)}'
    
    # Calculate completeness
    score = sum([
        bool(info.get('primary_engine')),
        bool(info.get('hp_official')),
        bool(info.get('year_start')),
        bool(info.get('platform')),
        bool(info.get('primary_image_url')),
    ])
    info['completeness_score'] = score
    
    tier_str = {3: 'Tier 3 (Wikipedia)', 2: 'Tier 2 (Auto media)', 1: 'Tier 1 (Official spec)'}
    log(f'  ✅ {gen} — {info.get("year_start","?")}-{info.get("year_end","?")} | {info.get("hp_official","?")} HP | Score: {score}/5')
    
    return info

def save_brand_to_db(info: dict) -> int:
    """Save brand to DB, return brand_id."""
    conn = sqlite3.connect(DB)
    cur = conn.execute(
        'INSERT OR IGNORE INTO brands (slug, name, country, founded, notes) VALUES (?, ?, ?, ?, ?)',
        (info['slug'], info['name'], info.get('country',''), info.get('founded',''), info.get('notes',''))
    )
    conn.commit()
    row = conn.execute('SELECT id FROM brands WHERE slug=?', (info['slug'],)).fetchone()
    conn.close()
    return row[0] if row else None

def save_series_to_db(info: dict, brand_id: int) -> int:
    """Save series to DB, return series_id."""
    slug = f"{info['slug']}-{slugify(info['brand'])}"
    conn = sqlite3.connect(DB)
    cur = conn.execute(
        'INSERT OR IGNORE INTO series (slug, brand_id, name, category, notes) VALUES (?, ?, ?, ?, ?)',
        (slug, brand_id, info['name'], info.get('category',''), info.get('notes',''))
    )
    conn.commit()
    row = conn.execute('SELECT id FROM series WHERE slug=?', (slug,)).fetchone()
    conn.close()
    return row[0] if row else None

def save_generation_to_db(info: dict, series_id: int) -> int:
    """Save generation to DB, return gen_id."""
    conn = sqlite3.connect(DB)
    conn.execute('''
        INSERT OR IGNORE INTO generations
        (slug, series_id, name, year_start, year_end, platform, primary_engine,
         hp_official, hp_source, hp_tier, primary_image_url, market, status, completeness_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        info['slug'], series_id, info['name'],
        info.get('year_start',''), info.get('year_end',''),
        info.get('platform',''), info.get('primary_engine',''),
        info.get('hp_official',''), info.get('hp_source',''),
        info.get('hp_tier', 3), info.get('primary_image_url',''),
        info.get('market',''), info.get('status','draft'),
        info.get('completeness_score', 0),
    ))
    conn.commit()
    row = conn.execute('SELECT id FROM generations WHERE slug=?', (info['slug'],)).fetchone()
    conn.close()
    return row[0] if row else None

def create_wiki_page(info: dict):
    """Create a wiki markdown page for the entity."""
    page_path = WIKI / 'generations' / f"{info['slug']}.md"
    
    if info['type'] == 'generation':
        content = f"""# {info['name']}

**Brand:** {info['brand']} | **Series:** {info['series']}
**Status:** {info.get('status', 'draft')} | **Completeness:** {info.get('completeness_score', 0)}/5

## Overview
{info.get('description', 'Research in progress...')}

## Specs
- **Year:** {info.get('year_start', '?')}–{info.get('year_end', '?')}
- **Engine:** {info.get('primary_engine', 'Unknown')}
- **Platform:** {info.get('platform', 'Unknown')}
- **Horsepower:** {info.get('hp_official', '?')} HP (Source: {info.get('hp_source', 'TBD')})
- **Market:** {info.get('market', 'Global')}

## Sources
- [Wikipedia](https://en.wikipedia.org/wiki/{info['slug'].replace('-', '_')})
"""
    else:
        content = f"# {info['name']}\n\n**Type:** {info['type']}\n\n## Overview\n{info.get('description', 'Research in progress...')}\n"
    
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding='utf-8')
    return page_path

def update_index():
    """Update wiki/index.md with latest counts."""
    if not INDEX.exists(): return
    conn = sqlite3.connect(DB)
    brands = conn.execute('SELECT COUNT(*) FROM brands').fetchone()[0]
    gens   = conn.execute('SELECT COUNT(*) FROM generations').fetchone()[0]
    conn.close()
    
    text = INDEX.read_text(encoding='utf-8')
    text = re.sub(r'Total Generations:\s*\d+', f'Total Generations: {gens}', text)
    text = re.sub(r'Total Brands:\s*\d+', f'Total Brands: {brands}', text)
    INDEX.write_text(text, encoding='utf-8')

def main():
    args = sys.argv[1:]
    if not args:
        print('[ERR] Usage: python3 scripts/ingest.py <brand> [series] [generation]')
        print('Examples:')
        print('  python3 scripts/ingest.py Bugatti')
        print('  python3 scripts/ingest.py Nissan GT-R')
        print('  python3 scripts/ingest.py Nissan GT-R R35')
        sys.exit(1)
    
    brand  = args[0]
    series = args[1] if len(args) > 1 else ''
    gen    = args[2] if len(args) > 2 else ''
    
    print(f'🚀 Ingest: {brand} {series} {gen}'.strip())
    print()
    
    # Research brand
    brand_info = research_brand(brand)
    brand_id = save_brand_to_db(brand_info)
    
    # Create brand wiki page
    brand_page = WIKI / 'brands' / f"{brand_info['slug']}.md"
    brand_page.parent.mkdir(parents=True, exist_ok=True)
    brand_content = f"""# {brand_info['name']}

**Type:** Brand
**Founded:** {brand_info.get('founded', 'Unknown')}
**Country:** {brand_info.get('country', 'Unknown')}

## Overview
{brand_info.get('description', 'Research in progress...')}

## Series
*(Series pages will appear here as they are added)*
"""
    brand_page.write_text(brand_content, encoding='utf-8')
    
    append_log(f'Brand ingested: {brand}', f'ID={brand_id} page={brand_page.name}')
    
    result_msg = f'{brand}'
    
    if series:
        series_info = research_series(brand, series)
        series_id = save_series_to_db(series_info, brand_id)
        append_log(f'Series ingested: {series}', f'brand={brand} ID={series_id}')
        result_msg += f' > {series}'
        
        if gen:
            gen_info = research_generation(brand, series, gen)
            gen_id = save_generation_to_db(gen_info, series_id)
            page_path = create_wiki_page(gen_info)
            append_log(f'Generation ingested: {gen}', f'ID={gen_id} page={page_path.name}')
            result_msg += f' > {gen} → {page_path.name}'
    
    update_index()
    
    print()
    print(f'✅ Done: {result_msg}')
    print(f'📄 Page: wiki/generations/{gen or series or slugify(brand)}.md')
    log(f'Updated wiki/index.md')

if __name__ == '__main__':
    main()
