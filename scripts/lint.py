#!/usr/bin/env python3
# scripts/lint.py
# Full lint implementation — 8 checks
# Usage: python3 scripts/lint.py [--auto] [--checks 1,4,6]
# --auto runs only checks 1+4+6 (lightweight, used by !daily)

import sqlite3, sys, argparse, re
from pathlib import Path
from datetime import datetime, timedelta

BASE   = Path(__file__).parent.parent
DB     = BASE / 'data' / 'cars.db'
WIKI   = BASE / 'wiki'
META   = BASE / 'agent-meta'
LOG    = BASE / 'wiki' / 'log.md'
REPORT = META / 'lint-report.md'
NOW    = datetime.now().strftime('%Y-%m-%d %H:%M')

errors   = []
warnings = []
passed   = []
checked  = 0

def err(msg):  errors.append(f'[ERR]  {msg}')
def warn(msg): warnings.append(f'[WARN] {msg}')
def ok(msg):   passed.append(f'OK    {msg}')

def get_conn():
    if not DB.exists(): return None
    return sqlite3.connect(DB)

# ── CHECK 1: ORPHAN DETECTION ──────────────────────────────────────────────
def check1():
    gen_dir = WIKI / 'generations'
    if not gen_dir.exists(): warn('wiki/generations/ directory missing'); return
    index_path = WIKI / 'index.md'
    index_text = index_path.read_text(encoding='utf-8') if index_path.exists() else ''
    series_texts = []
    for p in (WIKI / 'series').rglob('*.md') if (WIKI/'series').exists() else []:
        series_texts.append(p.read_text(encoding='utf-8'))
    all_refs = index_text + ' '.join(series_texts)
    pages = list(gen_dir.glob('*.md'))
    global checked; checked += len(pages)
    for p in pages:
        slug = p.stem
        if slug not in all_refs:
            warn(f'orphan: wiki/generations/{slug}.md (not referenced in index or series)')
        else:
            ok(f'referenced: {slug}')

# ── CHECK 2: MISSING IMAGES ──────────────────────────────────────────────
def check2():
    gen_dir = WIKI / 'generations'
    if not gen_dir.exists(): return
    for p in gen_dir.glob('*.md'):
        txt  = p.read_text(encoding='utf-8')
        slug = p.stem
        has_url     = bool(re.search(r'primary_image_url:\s*https?://', txt))
        is_verified = bool(re.search(r'image_verified:\s*true', txt, re.I))
        if has_url and not is_verified:
            warn(f'unverified image: {slug}')
        elif not has_url:
            warn(f'no image set: {slug}')
        else:
            ok(f'image verified: {slug}')

# ── CHECK 3: MISSING HP SOURCE ───────────────────────────────────────────
def check3():
    gen_dir = WIKI / 'generations'
    if not gen_dir.exists(): return
    for p in gen_dir.glob('*.md'):
        txt  = p.read_text(encoding='utf-8')
        slug = p.stem
        hp_val  = re.search(r'hp_official:\s*(\d+)', txt)
        hp_src  = re.search(r'hp_source:\s*(\S+)', txt)
        hp_tier = re.search(r'hp_tier:\s*([1-5])', txt)
        if hp_val and (not hp_src or not hp_tier):
            err(f'hp without source: {slug} hp={hp_val.group(1)}')
        elif hp_val:
            ok(f'hp sourced: {slug}')

# ── CHECK 4: YEAR LOGIC ──────────────────────────────────────────────────
def check4():
    gen_dir = WIKI / 'generations'
    if not gen_dir.exists(): return
    for p in gen_dir.glob('*.md'):
        txt  = p.read_text(encoding='utf-8')
        slug = p.stem
        ys = re.search(r'year_start:\s*(\d{4})', txt)
        ye = re.search(r'year_end:\s*(\d{4})', txt)
        if ys and ye:
            if int(ye.group(1)) < int(ys.group(1)):
                err(f'invalid year range: {slug} start={ys.group(1)} end={ye.group(1)}')
            else:
                ok(f'year range valid: {slug}')

# ── CHECK 5: STALE DRAFTS ────────────────────────────────────────────────
def check5():
    gen_dir = WIKI / 'generations'
    if not gen_dir.exists(): return
    cutoff = datetime.now() - timedelta(days=30)
    for p in gen_dir.glob('*.md'):
        txt  = p.read_text(encoding='utf-8')
        slug = p.stem
        if not re.search(r'status:\s*draft', txt, re.I): continue
        m = re.search(r'updated_at:\s*(\d{4}-\d{2}-\d{2})', txt)
        if m:
            try:
                d = datetime.strptime(m.group(1), '%Y-%m-%d')
                if d < cutoff:
                    warn(f'stale draft: {slug} last={m.group(1)}')
            except ValueError:
                pass
        else:
            warn(f'stale draft (no updated_at): {slug}')

# ── CHECK 6: UNRESOLVED DISPUTES ─────────────────────────────────────────
def check6():
    disp_dir = WIKI / 'disputes'
    if not disp_dir.exists(): return
    cutoff = datetime.now() - timedelta(days=14)
    for p in disp_dir.glob('*.md'):
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        if mtime < cutoff:
            warn(f'unresolved dispute: {p.stem} (age {(datetime.now()-mtime).days}d)')
        else:
            ok(f'recent dispute: {p.stem}')

# ── CHECK 7: DB / WIKI SYNC ───────────────────────────────────────────────
def check7():
    conn = get_conn()
    if not conn: warn('DB not available for check 7'); return
    gen_dir = WIKI / 'generations'
    wiki_slugs = {p.stem for p in gen_dir.glob('*.md')} if gen_dir.exists() else set()
    db_slugs   = {r[0] for r in conn.execute('SELECT slug FROM generations').fetchall()}
    conn.close()
    for s in db_slugs - wiki_slugs:
        err(f'DB/wiki out of sync: DB has {s} but wiki/generations/{s}.md missing')
    for s in wiki_slugs - db_slugs:
        warn(f'DB/wiki out of sync: wiki/{s}.md exists but not in DB')
    if not (db_slugs - wiki_slugs) and not (wiki_slugs - db_slugs):
        ok(f'DB/wiki in sync ({len(db_slugs)} generations)')

# ── CHECK 8: INDEX STALENESS ──────────────────────────────────────────────
def check8():
    conn = get_conn()
    if not conn: warn('DB not available for check 8'); return
    db_count = conn.execute('SELECT COUNT(*) FROM generations').fetchone()[0]
    conn.close()
    index_path = WIKI / 'index.md'
    if not index_path.exists(): warn('wiki/index.md missing'); return
    txt = index_path.read_text(encoding='utf-8')
    m   = re.search(r'Total Generations:\s*(\d+)', txt)
    if m:
        idx_count = int(m.group(1))
        if idx_count != db_count:
            warn(f'index stale: index.md says {idx_count}, DB has {db_count}')
        else:
            ok(f'index in sync: {db_count} generations')
    else:
        warn('index.md has no Total Generations count')

# ── LOG ARCHIVE CHECK ────────────────────────────────────────────────────
def check_log_size():
    if not LOG.exists(): return
    size_mb = LOG.stat().st_size / (1024 * 1024)
    if size_mb > 10:
        month   = datetime.now().strftime('%Y-%m')
        archive = WIKI / f'log-{month}.md'
        content = LOG.read_text(encoding='utf-8')
        with open(archive, 'a', encoding='utf-8') as f: f.write(content)
        LOG.write_text(f'# Wiki Log (continued after archive {month})\n', encoding='utf-8')
        warn(f'log.md exceeded 10MB — archived to log-{month}.md')

# ── WRITE REPORT ─────────────────────────────────────────────────────────
def write_report(auto_mode=False):
    META.mkdir(exist_ok=True)
    lines = [
        f'# Lint Report — {NOW}',
        f'Mode: {"AUTO (checks 1+4+6)" if auto_mode else "FULL (all 8 checks)"}',
        f'## Summary',
        f'- Errors:   {len(errors)}',
        f'- Warnings: {len(warnings)}',
        f'- Passed:   {len(passed)}',
        f'- Pages:    {checked}',
        '',
    ]
    if errors:
        lines += ['## Errors (must fix)'] + errors + ['']
    if warnings:
        lines += ['## Warnings (should fix)'] + warnings + ['']
    if passed:
        lines += ['## Passed'] + [f'- {p}' for p in passed] + ['']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(f'[OK] Lint report -> {REPORT}')
    print(f'     Errors: {len(errors)}  Warnings: {len(warnings)}  Passed: {len(passed)}')

# ── APPEND TO LOG ────────────────────────────────────────────────────────
def append_log():
    entry = (f'[{NOW}] [LINT] errors={len(errors)}'
             f' warnings={len(warnings)} checked={checked}\n')
    with open(LOG, 'a', encoding='utf-8') as f: f.write(entry)

# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true',
                        help='Auto-lint mode: checks 1+4+6 only')
    parser.add_argument('--checks', default='',
                        help='Comma-separated check numbers, e.g. 1,4,6')
    args = parser.parse_args()

    if args.auto:
        run_set = {1, 4, 6}
        auto = True
    elif args.checks:
        run_set = set(int(x) for x in args.checks.split(','))
        auto = False
    else:
        run_set = {1, 2, 3, 4, 5, 6, 7, 8}
        auto = False

    check_log_size()
    if 1 in run_set: check1()
    if 2 in run_set: check2()
    if 3 in run_set: check3()
    if 4 in run_set: check4()
    if 5 in run_set: check5()
    if 6 in run_set: check6()
    if 7 in run_set: check7()
    if 8 in run_set: check8()
    write_report(auto_mode=auto)
    append_log()
    sys.exit(1 if errors else 0)

if __name__ == '__main__':
    main()
