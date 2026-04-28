#!/usr/bin/env python3
# scripts/migrations/001_init_schema.py
# Initial schema migration — safe to re-run (idempotent)
import sqlite3, sys
from pathlib import Path
from datetime import datetime

DB   = Path(__file__).parent.parent.parent / 'data' / 'cars.db'
VERS = '001_init_schema'

def already_applied(conn):
    conn.execute(
        'CREATE TABLE IF NOT EXISTS migrations'
        '(id INTEGER PRIMARY KEY, version TEXT UNIQUE, applied_at TEXT)')
    r = conn.execute('SELECT 1 FROM migrations WHERE version=?', (VERS,)).fetchone()
    return r is not None

def up(conn):
    c = conn.cursor()
    c.execute('PRAGMA journal_mode=WAL;')
    ddl = [
        ('brands',
         'id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,'
         ' country TEXT, founded INTEGER, notes TEXT, wiki_page TEXT,'
         ' updated_at TEXT'),
        ('series',
         'id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL,'
         ' brand_id INTEGER REFERENCES brands(id), name TEXT NOT NULL,'
         ' category TEXT, notes TEXT, wiki_page TEXT,'
         ' updated_at TEXT'),
        ('generations',
         'id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL,'
         ' series_id INTEGER REFERENCES series(id), gen_code TEXT, name TEXT NOT NULL,'
         ' year_start INTEGER, year_end INTEGER, platform TEXT, primary_engine TEXT,'
         ' hp_official INTEGER, hp_source TEXT, hp_tier INTEGER,'
         ' primary_image_url TEXT, image_source_url TEXT, image_verified INTEGER,'
         ' market TEXT, status TEXT, completeness_score INTEGER,'
         ' wiki_page TEXT, updated_at TEXT'),
        ('engines',
         'id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, code TEXT NOT NULL,'
         ' type TEXT, displacement_cc INTEGER, hp_min INTEGER, hp_max INTEGER,'
         ' notes TEXT, wiki_page TEXT, updated_at TEXT'),
        ('aliases',
         'id INTEGER PRIMARY KEY, alias TEXT NOT NULL,'
         ' gen_slug TEXT REFERENCES generations(slug), source TEXT,'
         ' UNIQUE(alias,gen_slug)'),
        ('image_refs',
         'id INTEGER PRIMARY KEY, gen_slug TEXT, url TEXT NOT NULL,'
         ' source_url TEXT, source_type TEXT, priority INTEGER,'
         ' verified INTEGER, last_checked TEXT,'
         ' status TEXT'),
        ('source_refs',
         'id INTEGER PRIMARY KEY, url TEXT UNIQUE, title TEXT, site TEXT,'
         ' tier INTEGER, fetched_at TEXT, summary TEXT'),
    ]
    for name, cols in ddl:
        c.execute(f'CREATE TABLE IF NOT EXISTS {name} ({cols})')
    c.execute(
        'CREATE VIRTUAL TABLE IF NOT EXISTS gen_search USING fts5('
        'name,gen_code,platform,primary_engine,market,'
        'content="generations",content_rowid="id")')
    c.execute('INSERT OR IGNORE INTO migrations (version, applied_at) VALUES (?, ?)',
              (VERS, datetime.now().isoformat()))
    conn.commit()
    print(f'[OK] Migration {VERS} applied')

if __name__ == '__main__':
    if not DB.exists(): print(f'[ERR] DB not found: {DB}'); sys.exit(1)
    conn = sqlite3.connect(DB)
    if already_applied(conn): print(f'[SKIP] {VERS} already applied')
    else: up(conn)
    conn.close()
