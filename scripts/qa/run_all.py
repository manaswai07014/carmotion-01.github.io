#!/usr/bin/env python3
# scripts/qa/run_all.py v2 — 7 actual QA checks
# Usage: python3 scripts/qa/run_all.py

import sqlite3, sys, re, subprocess, ast as ast_mod
from pathlib import Path

BASE   = Path(__file__).parent.parent.parent
DB     = BASE / 'data' / 'cars.db'
WIKI   = BASE / 'wiki'
errors = []

def fail(msg): errors.append(f'FAIL: {msg}')
def note(msg): print(f'  [OK] {msg}')

# QA 1: required files exist
REQUIRED_FILES = [
    'AGENTS.md',
    'data/cars.db',
    'wiki/index.md',
    'wiki/log.md',
    'ontology/car-ontology.md',
    'agent-meta/daily-brief.md',
    'scripts/daily_news_fetcher.py',
    'scripts/trend_monitor.py',
    'scripts/backup.sh',
    'scripts/lint.py',
    'scripts/completeness.py',
    'wiki/templates/template-evolution.md',
    'wiki/templates/template-comparison.md',
    'wiki/templates/README.md',
]
for rel in REQUIRED_FILES:
    p = BASE / rel
    if p.exists(): note(f'exists: {rel}')
    else: fail(f'missing: {rel}')

# QA 2: SQLite — 7 required tables + FTS5
REQUIRED_TABLES = ['brands','series','generations','engines',
                   'aliases','image_refs','source_refs']
try:
    conn = sqlite3.connect(DB)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in REQUIRED_TABLES:
        if t in tables: note(f'table: {t}')
        else: fail(f'missing table: {t}')
    # FTS5 table is named 'gen_search' per migration script
    if 'gen_search' in tables: note('FTS5 gen_search exists')
    else: fail('FTS5 gen_search missing')
    conn.close()
except Exception as e:
    fail(f'DB error: {e}')

# QA 3: AGENTS.md has all 3 operation contracts
if (BASE/'AGENTS.md').exists():
    txt = (BASE/'AGENTS.md').read_text(encoding='utf-8')
    for kw in ['OPERATION 1', 'OPERATION 2', 'OPERATION 3', 'LOG.MD PROTOCOL',
               'WRITE-BACK', 'AUTO-LINT', 'append wiki/log.md']:
        if kw in txt: note(f'AGENTS.md has: {kw}')
        else: fail(f'AGENTS.md missing: {kw}')

# QA 4: crontab has 2 auto-schedule jobs
r = subprocess.run(['crontab','-l'], capture_output=True, text=True)
cron = r.stdout if r.returncode == 0 else ''
for job in ['daily_news_fetcher', 'trend_monitor']:
    if job in cron: note(f'cron job: {job}')
    else: fail(f'cron job missing: {job}')

# QA 5: wiki/log.md exists and is not empty
log_path = WIKI / 'log.md'
if log_path.exists() and log_path.stat().st_size > 0:
    note('wiki/log.md exists and non-empty')
else:
    fail('wiki/log.md missing or empty')

# QA 6: memory/triples.jsonl exists
triples = BASE / 'memory' / 'triples.jsonl'
if triples.exists(): note('memory/triples.jsonl exists')
else: fail('memory/triples.jsonl missing')

# QA 7: no Python syntax errors in scripts/
for py in (BASE/'scripts').rglob('*.py'):
    try:
        ast_mod.parse(py.read_text(encoding='utf-8'))
        note(f'syntax OK: scripts/{py.name}')
    except SyntaxError as e:
        fail(f'syntax error in {py.name} line {e.lineno}')

# ── summary ──────────────────────────────────────────────────────────────
print()
if errors:
    print(f'QA RESULT: {len(errors)} failure(s)')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print(f'QA RESULT: ALL PASSED')
