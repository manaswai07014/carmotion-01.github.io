#!/usr/bin/env python3
# scripts/completeness.py
# Compute and update completeness_score for wiki/generations/*.md
# Also updates SQLite completeness_score column
# Usage: python3 scripts/completeness.py [slug]
# No arg = update ALL generation pages

import re, sqlite3, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
DB   = BASE / 'data' / 'cars.db'
GENS = BASE / 'wiki' / 'generations'
LOG  = BASE / 'wiki' / 'log.md'

# ── Scoring rubric (max 6 points) ───────────────────────────────────────────
CRITERIA = {
    'overview_written':    lambda t: len(re.findall(r'## Overview', t, re.I)) > 0
                                     and len(t.split('## Overview')[1].split('##')[0].strip()) > 50,
    'specs_complete':      lambda t: all(re.search(pat, t) for pat in [
                                     r'hp_official:\s*\d+',
                                     r'year_start:\s*\d{4}',
                                     r'primary_engine:\s*\S+',
                                     r'platform:\s*\S+'
                                 ]),
    'image_verified':       lambda t: bool(re.search(r'image_verified:\s*true', t, re.I)),
    'sources_tier1_or_2':  lambda t: bool(re.search(r'hp_tier:\s*([12])\b', t)),
    'cultural_section':     lambda t: bool(re.search(r'## (Cultural|Heritage|Culture)', t, re.I)),
    'shorts_script_done':   lambda t: bool(re.search(r'## Shorts Script Synthesis', t, re.I)),
}

def confidence_score(text):
    score = 0
    for name, fn in CRITERIA.items():
        try:
            if fn(text): score += 1
        except Exception:
            pass
    return score

def update_score(page_path):
    text  = page_path.read_text(encoding='utf-8')
    slug  = page_path.stem
    score = confidence_score(text)

    new_text = re.sub(r'completeness_score:\s*\d+',
                      f'completeness_score: {score}', text)
    if new_text == text and 'completeness_score:' not in text:
        new_text = text.rstrip() + f'\ncompleteness_score: {score}\n'
    page_path.write_text(new_text, encoding='utf-8')

    if DB.exists():
        conn = sqlite3.connect(DB)
        conn.execute('UPDATE generations SET completeness_score=?, updated_at=?'
                     ' WHERE slug=?',
                     (score, datetime.now().strftime('%Y-%m-%d'), slug))
        conn.commit(); conn.close()

    print(f'  {slug}: {score}/6')
    return slug, score

def show_breakdown(page_path):
    text = page_path.read_text(encoding='utf-8')
    print(f'  Breakdown for {page_path.stem}:')
    for name, fn in CRITERIA.items():
        try:
            result = fn(text)
        except Exception:
            result = False
        icon = 'V' if result else 'X'
        print(f'    [{icon}] {name}')

def append_log(updated):
    if not LOG.exists(): return
    now   = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [COMPLETENESS] updated {len(updated)} pages\n'
    with open(LOG, 'a', encoding='utf-8') as f: f.write(entry)

def main():
    if not GENS.exists():
        print('[ERR] wiki/generations/ not found'); sys.exit(1)

    target_slug = sys.argv[1] if len(sys.argv) > 1 else None

    if target_slug:
        p = GENS / f'{target_slug}.md'
        if not p.exists(): print(f'[ERR] {p} not found'); sys.exit(1)
        pages = [p]
    else:
        pages = list(GENS.glob('*.md'))

    print(f'Updating completeness_score for {len(pages)} page(s)...')
    updated = []
    for p in pages:
        slug, score = update_score(p)
        if target_slug: show_breakdown(p)
        updated.append((slug, score))

    avg = sum(s for _, s in updated) / len(updated) if updated else 0
    print(f'Done. Average: {avg:.1f}/6')
    append_log(updated)

if __name__ == '__main__':
    main()
