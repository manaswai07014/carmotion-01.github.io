#!/usr/bin/env python3
# scripts/script_generator.py
# Smart Shorts Script Generator — reads wiki series pages, outputs 45s script + YouTube description
# Usage: python3 scripts/script_generator.py <brand> <model> [--save]
# Example: python3 scripts/script_generator.py Ferrari 458 [--save]

import re, sys, json, time
from pathlib import Path
from datetime import datetime

BASE         = Path(__file__).parent.parent
WIKI_SERIES  = BASE / 'wiki' / 'series'
EXPORT_YT    = BASE / 'exports'  / 'youtube'
LOG          = BASE / 'wiki'    / 'log.md'
SCRIPTS_OUT  = BASE / 'wiki'    / 'generations'

# ─────────────────────────────────────────
# YouTube Description Template (from exports/youtube/description_template.md)
# ─────────────────────────────────────────
YOUTUBE_TEMPLATE = """{title}

{hook}

🔗 Subscribe for more car evolution documentaries:
https://youtube.com/shorts/[video_id]

{hashtags}"""


def get_hashtags(brand: str, model: str, topic: str = "") -> str:
    """Generate optimised YouTube hashtags based on description_template rules."""
    base = [
        f"#{brand}{model}",
        f"#{brand}",
        f"#{model}",
        "#autohistory",
        "#carsecrets",
        "#drivingevolution",
        "#supercar",
        "#shorts",
        "#ytshorts",
        "#viral",
        "#fyp",
        "#explore",
    ]
    seen = set()
    deduped = []
    for h in base:
        if h.lower() not in seen:
            seen.add(h.lower())
            deduped.append(h)
    return " ".join(deduped[:12])


# ─────────────────────────────────────────
# Read wiki series page → structured data
# ─────────────────────────────────────────
def read_series_page(brand: str, model: str) -> dict | None:
    """Try to load a wiki series page for brand/model.

    Matching strategy:
    1. Exact match: ferrari-458-italia.md for model="458 italia"
    2. Base model: ferrari-458-italia.md for model="458" (prefer base variant over spider/gtb/etc)
    3. Any match: ferrari-458-spider.md if no base model found
    """
    brand_l = brand.lower()
    model_l = model.lower().replace(' ', '-')

    series_dir = WIKI_SERIES / brand_l
    if not series_dir.is_dir():
        return None

    all_files = {p.stem: p for p in series_dir.glob('*.md')}

    # Strategy 1: exact stem match (e.g. "ferrari-458-italia")
    exact = f"{brand_l}-{model_l}"
    if exact in all_files:
        return _parse_series_page(all_files[exact].read_text(encoding='utf-8'), brand, model)

    # Strategy 2: base model without suffix (prefer "ferrari-458-italia" over "ferrari-458-spider")
    # For model="458", prefer files that are just "{brand}-{model}" or end with "-{model}"
    base_match = f"{brand_l}-{model_l}"
    base_candidates = [p for stem, p in all_files.items()
                        if stem == base_match or stem.startswith(base_match + '-')]
    if base_candidates:
        # Prefer shortest stem (base variant over specialized variants)
        chosen = min(base_candidates, key=lambda p: len(p.stem))
        return _parse_series_page(chosen.read_text(encoding='utf-8'), brand, model)

    # Strategy 3: model keyword appears anywhere in filename
    model_keywords = model_l.replace('-', ' ').split()
    for kw in model_keywords:
        matches = [p for stem, p in all_files.items() if kw in stem]
        if matches:
            chosen = min(matches, key=lambda p: len(p.stem))
            return _parse_series_page(chosen.read_text(encoding='utf-8'), brand, model)

    return None


def _parse_series_page(content: str, brand: str, model: str) -> dict:
    """Parse a wiki series markdown page into structured data."""
    data = {
        'brand': brand,
        'model': model,
        'production': None,
        'engine': None,
        'hp': None,
        'layout': None,
        'nodes': [],       # (year, name, hp, engine, note)
        'source_url': None,
    }

    # Production years from Overview
    prod_match = re.search(r'\*\*Production\*\*:\s*(\d{4})(?:[–\-–](\d{4}|present))?', content)
    if prod_match:
        data['production'] = (prod_match.group(1), prod_match.group(2) or "present")

    # Engine from Overview
    eng_match = re.search(r'\*\*Engine\*\*:\s*([^\n]+)', content)
    if eng_match:
        data['engine'] = eng_match.group(1).strip()

    # HP from Overview (may appear as part of a variant row in Summary Table)
    hp_match = re.search(r'\*\*HP\*\*:\s*(\d+)', content)
    if hp_match:
        data['hp'] = hp_match.group(1)

    # Layout
    lay_match = re.search(r'\*\*Layout\*\*:\s*([^\n]+)', content)
    if lay_match:
        data['layout'] = lay_match.group(1).strip()

    # Source URL
    src_match = re.search(r'Wikipedia:\s*(https?://[^\s]+)', content)
    if src_match:
        data['source_url'] = src_match.group(1)

    # Parse Summary Table rows
    in_table = False
    for line in content.split('\n'):
        line = line.strip()
        # Detect table header
        if re.match(r'\| # \|.*型號.*年.*', line):
            in_table = True
            continue
        if not in_table:
            continue
        # Skip separator row
        if re.match(r'\|[-:]+\|', line):
            continue
        # End of table
        if line.startswith('|') and '|' not in line[2:]:
            in_table = False
            break
        if not line.startswith('|'):
            in_table = False
            break
        # Parse data row: | # | 型號 | 年份 | 引擎 | 馬力 | 扭力 | 0-100 | 極速 | 車重 | 特色 |
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) >= 5:
            num_col  = cells[0]
            name_col = cells[1]
            year_col = cells[2]
            eng_col  = cells[3]
            hp_col   = cells[4] if len(cells) > 4 else ""
            note_col = cells[-1] if len(cells) > 8 else ""
            # Skip header mimic / index rows
            if num_col in ('#', '型號', '型号') or not name_col:
                continue
            # Skip rows that are clearly not car data
            if not re.search(r'\d', year_col):
                continue
            data['nodes'].append((year_col, name_col, hp_col, eng_col, note_col))

    return data


# ─────────────────────────────────────────
# Script Generation (core logic)
# ─────────────────────────────────────────
def generate_script(brand: str, model: str, wiki_data: dict | None = None) -> dict:
    """
    Generate a 45-second Shorts script from structured data.
    Returns dict with 'script_md', 'youtube_desc', 'info'.
    """
    import urllib.request, ssl, json as json_mod, re as re_mod

    CTX = ssl.create_default_context()
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE

    # ── Step 1: Gather data ──
    info = {
        'brand': brand,
        'model': model,
        'hp': None,
        'engine': None,
        'year_start': None,
        'year_end': None,
        'nodes': [],
        'sources': [],
        'topic_overrides': None,
    }

    # Use wiki data if available
    if wiki_data:
        info['hp']         = wiki_data.get('hp')
        info['engine']     = wiki_data.get('engine')
        _prod = wiki_data.get('production') or (None, None)
        info['year_start'] = _prod[0]
        info['year_end']   = _prod[1]
        info['nodes']      = wiki_data.get('nodes', [])
        # Only add source URL from wiki_data if we don't also fetch live Wikipedia
        # (live fetch adds it below at line 253)
        if wiki_data.get('source_url') and not wiki_data.get('hp'):
            info['sources'].append(('Wikipedia', wiki_data['source_url']))

    # ── Step 2: Fetch Wikipedia for additional data ──
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    wiki_url = f"https://en.wikipedia.org/wiki/{urllib.request.quote(brand.encode('ascii', 'replace').decode())}_{urllib.request.quote(model.encode('ascii', 'replace').decode())}"

    try:
        req = urllib.request.Request(wiki_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            html = r.read().decode('utf-8', errors='ignore')

        if not info['hp']:
            hp_matches = re_mod.findall(r'(\d{3,4})\s*(?:brake\s*)?horsepower', html, re_mod.I)
            if hp_matches:
                info['hp'] = max(hp_matches, key=lambda x: int(x))

        if not info['engine']:
            eng_match = re_mod.search(
                r'(\d\.\d[\dL\s]*?(?:Turbo)?\s*(?:V\d+|V\s*\d+|flat[- ]?\d+|H\d+|I\d+|W\d+|Inline-\d+|I\s*\d+))',
                html, re_mod.I)
            if eng_match:
                info['engine'] = eng_match.group(0).replace('\n', ' ').strip()[:40]

        if not info['year_start']:
            # Prefer production years from infobox (look for "2011–2015" pattern)
            prod_match = re_mod.search(r'(201[0-9]|202[0-9])[–\-](201[0-9]|202[0-9]|present)', html)
            if prod_match:
                info['year_start'] = prod_match.group(1)
                info['year_end']   = prod_match.group(2)
            else:
                # Fallback: look for any year in a plausible range
                year_matches = re_mod.findall(r'\b(19[8-9]\d|20[0-2]\d)\b', html)
                if year_matches:
                    years = sorted(set(int(y) for y in year_matches))
                    info['year_start'] = str(years[0])
                    info['year_end']   = str(years[-1])

        info['sources'].append(('Wikipedia', wiki_url))
        time.sleep(0.3)  # rate limit
    except Exception as e:
        pass

    # ── Step 3: Validate and correct years ──
    if info['year_start'] and info['year_end']:
        try:
            ys, ye = int(info['year_start']), int(info['year_end']) if info['year_end'] != 'present' else 9999
            # If start > end (nonsense), discard
            if ys > ye and ye < 3000:
                info['year_start'], info['year_end'] = None, None
            # If range is absurdly large (> 60 years), discard
            if ye != 9999 and ys and ye - ys > 60:
                info['year_start'], info['year_end'] = None, None
        except:
            pass
    # Override with wiki_data production if Wikipedia gave garbage
    if wiki_data and wiki_data.get('production') and not info['year_start']:
        prod = wiki_data['production']
        info['year_start'] = prod[0]
        info['year_end']   = prod[1] if prod[1] != 'present' else 'present'

    # ── Step 3: Build nodes from available data ──
    nodes = info['nodes']
    if not nodes:
        # Fallback: use year_start/year_end as single entry
        year = f"{info['year_start'] or '?'}"
        if info['year_end'] and info['year_end'] != info['year_start']:
            year = f"{info['year_start']}–{info['year_end']}"
        nodes = [(year, f"{brand} {model}", info['hp'] or "?", info['engine'] or "?", "")]

    # ── Step 4: Construct Hook ──
    hp_str    = f" {info['hp']}HP" if info['hp'] else ""
    eng_str   = f" with {info['engine']}" if info['engine'] else ""
    year_str  = f" from {info['year_start']}" if info['year_start'] else ""

    hook_options = [
        f"{brand} {model} — one car that defined a generation{year_str}{hp_str} 🔥",
        f"{brand} {model}: {info['hp'] or 'the'} HP machine that changed everything{year_str} 🚗",
        f"When {brand} built {model}{eng_str} — they changed supercars forever{year_str} 💨",
    ]
    hook = hook_options[0]

    # ── Step 5: Construct Beats ──
    # Group nodes by era for storytelling
    if len(nodes) >= 3:
        era1 = nodes[0]
        era_mid = nodes[len(nodes)//2] if len(nodes) > 2 else nodes[1]
        era_final = nodes[-1]

        beat1 = _build_beat_intro(brand, model, era1, hp_str, eng_str)
        beat2 = _build_beat_evolution(brand, model, era1, era_mid, nodes)
        beat3 = _build_beat_climax(brand, model, era_final, hp_str, nodes)
    elif len(nodes) == 2:
        beat1 = _build_beat_intro(brand, model, nodes[0], hp_str, eng_str)
        beat2 = _build_beat_evolution(brand, model, nodes[0], nodes[1], nodes)
        beat3 = _build_beat_climax(brand, model, nodes[1], hp_str, nodes)
    else:
        beat1 = _build_beat_intro(brand, model, nodes[0], hp_str, eng_str)
        beat2 = f"The {brand} {model} evolved over years — each generation pushing further."
        beat3 = _build_beat_climax(brand, model, nodes[0], hp_str, nodes)

    # ── Step 6: Ending CTA ──
    ending = (
        f"The {brand} {model} proved {brand} could build something truly special. "
        f"Follow for more car evolution documentaries. "
        f"Like if you learned something new today — I'll see you in the next one."
    )

    # ── Step 7: Specs block ──
    specs = f"""- Brand: {brand}
- Model: {model}
- Engine: {info['engine'] or 'See Wikipedia'}
- Power: {info['hp'] or 'See Wikipedia'} HP
- Years: {info['year_start'] or '?'}–{info['year_end'] or '?'}"""

    # ── Step 8: YouTube Description ──
    title = f"The EVOLUTION of {brand} {model} ({info['year_start'] or '???'}–{info['year_end'] or '???'}) 🚗"
    yt_hook = (
        f"From {info['year_start'] or '???'} to {info['year_end'] or '???'} — "
        f"see how {brand} transformed the supercar world."
    )
    youtube_desc = YOUTUBE_TEMPLATE.format(
        title=title,
        hook=yt_hook,
        hashtags=get_hashtags(brand, model),
    )

    # ── Step 9: Full script markdown ──
    script_md = f"""## Shorts Script — {brand} {model}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Topic:** {brand} {model}
**Format:** ~45 seconds (Hook 3s + 3 Beats ~12s each + CTA ~6s)

---

### 🎬 HOOK (0–3s)
{hook}

---

### 📖 BEAT 1 — The Beginning (3–15s)
{beat1}

---

### 📖 BEAT 2 — The Evolution (15–30s)
{beat2}

---

### 📖 BEAT 3 — The Legend (30–45s)
{beat3}

---

### 🔚 ENDING + CTA (45–50s)
{ending}

---

### 📊 Specs Referenced
{specs}

---

### 🔍 Sources
{chr(10).join(f"- [{n}]({u})" for n, u in list(dict.fromkeys(tuple(s) for s in info['sources'])) if info['sources']) if info['sources'] else "(web research)"}

---

## YouTube Description (copy-paste ready)

{youtube_desc}
"""

    return {
        'script_md':   script_md,
        'youtube_desc': youtube_desc,
        'title':       title,
        'info':        info,
    }


def _build_beat_intro(brand: str, model: str, node: tuple, hp_str: str, eng_str: str) -> str:
    year, name, hp, eng, note = node
    hp_part = f"{hp} HP" if hp and hp != "?" else (hp_str.replace('HP', 'HP') if hp_str else "")
    eng_part = eng if eng and eng != "?" else ""

    eng_hp = []
    if eng_part:
        eng_hp.append(eng_part)
    if hp_part:
        eng_hp.append(hp_part)
    specs_str = " with ".join(eng_hp) if eng_hp else eng_str

    return (
        f"The {brand} {model} arrived in {year}. "
        f"It packed {specs_str} into a design that turned heads everywhere. "
        f"{note if note else 'This was just the beginning.'}"
    )


def _build_beat_evolution(brand: str, model: str, era1: tuple, era2: tuple, all_nodes: list) -> str:
    y1, n1, hp1, _, note1 = era1
    y2, n2, hp2, _, note2 = era2

    evolved = ""
    if hp1 and hp2 and hp1 != "?" and hp2 != "?":
        try:
            diff = int(hp2) - int(hp1)
            if diff > 0:
                evolved = f"Power jumped from {hp1} to {hp2} HP — a gain of +{diff} HP. "
        except:
            pass

    same_eng = ""
    if y1 != y2:
        same_eng = f"By {y2}, the {model} was already a legend."

    return (
        f"{evolved}"
        f"{same_eng} "
        f"{note2 if note2 else f'The {model} kept getting better.'}"
    )


def _build_beat_climax(brand: str, model: str, final_node: tuple, hp_str: str, all_nodes: list) -> str:
    year, name, hp, eng, note = final_node
    hp_val = hp if hp and hp != '?' else (hp_str.replace(' HP', '').replace('HP', '') if hp_str else '')
    hp_str_full = f"{hp_val} HP" if hp_val else (hp_str if hp_str else '')
    eng_val = eng if eng and eng != '?' else ''

    specs = []
    if hp_str_full:
        specs.append(hp_str_full)
    if eng_val:
        specs.append(eng_val)
    specs_str = ", ".join(specs) if specs else "a screaming engine"

    return (
        f"And then came {name} in {year} — the pinnacle of the {model} bloodline. "
        f"{specs_str}. "
        f"{note if note else f'This was the {model} at its absolute finest.'}"
    )


# ─────────────────────────────────────────
# Save / Log
# ─────────────────────────────────────────
def save_script(brand: str, model: str, script_text: str, youtube_desc: str) -> Path:
    SCRIPTS_OUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', f"{brand}-{model}".lower()).strip('-')
    out_file = SCRIPTS_OUT / f"{slug}.md"

    # Append under brand header
    brand_header = f"# {brand} {model}"
    if out_file.exists():
        existing = out_file.read_text(encoding='utf-8')
        if brand_header in existing:
            # Append new version under existing header
            parts = existing.split(brand_header, 1)
            out_file.write_text(parts[0] + brand_header + f"\n\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n" + script_text + "\n\n" + parts[1], encoding='utf-8')
        else:
            out_file.write_text(brand_header + f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n" + script_text + "\n\n" + existing, encoding='utf-8')
    else:
        out_file.write_text(brand_header + f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n" + script_text, encoding='utf-8')

    # Also save YouTube description
    desc_file = SCRIPTS_OUT / f"{slug}-description.txt"
    desc_file.write_text(youtube_desc, encoding='utf-8')

    return out_file


def append_log(action: str, detail: str = ''):
    if not LOG.exists():
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [SCRIPT] {action}'
    if detail:
        entry += f' — {detail}'
    entry += '\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print('[ERR] Usage: python3 scripts/script_generator.py <brand> <model> [--save]')
        print('       python3 scripts/script_generator.py Ferrari 458 [--save]')
        sys.exit(1)

    brand = sys.argv[1]
    model = sys.argv[2]
    save  = '--save' in sys.argv

    print(f'🎬 Generating Shorts script for: {brand} {model}')

    # Try wiki data first
    wiki_data = read_series_page(brand, model)
    if wiki_data:
        print(f'  ✓ Wiki series page found — {len(wiki_data["nodes"])} nodes')
    else:
        print(f'  ℹ No wiki page — using web research')

    result = generate_script(brand, model, wiki_data)

    print()
    print('=' * 60)
    print(result['script_md'])
    print('=' * 60)

    if save:
        path = save_script(brand, model, result['script_md'], result['youtube_desc'])
        append_log(f'Script generated + saved: {brand} {model}', str(path))
        print(f'\n[OK] Saved to: {path}')
    else:
        append_log(f'Script generated: {brand} {model}')
        print(f'\n[OK] Add --save to write to wiki/generations/')


if __name__ == '__main__':
    main()
