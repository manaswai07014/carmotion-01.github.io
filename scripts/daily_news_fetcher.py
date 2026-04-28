#!/usr/bin/env python3
# scripts/daily_news_fetcher.py
# Fetches latest car news from RSS feeds (stdlib only — no feedparser needed)
# Run: python3 scripts/daily_news_fetcher.py
# Auto-schedule: 0 0 * * * (daily at 00:00 HKT)

import urllib.request, urllib.error, sqlite3, re, ssl
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

BASE     = Path(__file__).parent.parent
DB       = BASE / 'data' / 'cars.db'
BRIEF    = BASE / 'agent-meta' / 'daily-brief.md'
NEWS_DIR = BASE / 'data' / 'daily-news'

RSS_FEEDS = [
    ('TopGear HK',   'https://www.topgearhk.com/feed/'),
    ('CarAndDriver', 'https://www.caranddriver.com/rss/all.xml'),
    ('RoadandTrack', 'https://www.roadandtrack.com/rss/all.xml'),
    ('Autocar',      'https://www.autocar.co.uk/rss'),
    ('Jalopnik',     'https://jalopnik.com/feed'),
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def log(msg): print(f'[{datetime.now().strftime("%H:%M")}] {msg}')

def fetch_feed(name, url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        entries = []
        # Atom format
        for e in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:5]:
            title    = e.find('{http://www.w3.org/2005/Atom}title')
            link_el  = e.find('{http://www.w3.org/2005/Atom}link')
            published = e.find('{http://www.w3.org/2005/Atom}updated') or e.find('{http://www.w3.org/2005/Atom}published')
            entries.append({
                'title':    title.text if title is not None else '',
                'link':    link_el.get('href') if link_el is not None else '',
                'published': published.text if published is not None else '',
                'source':  name,
            })
        # RSS format
        if not entries:
            for e in root.findall('.//item')[:5]:
                title     = e.find('title')
                link_el   = e.find('link')
                published = e.find('pubDate')
                entries.append({
                    'title':    title.text if title is not None else '',
                    'link':    link_el.text if link_el is not None else '',
                    'published': published.text if published is not None else '',
                    'source':  name,
                })
        log(f'{name}: {len(entries)} articles')
        return entries
    except Exception as e:
        log(f'Error fetching {name}: {e}')
        return []

def update_brief(entries):
    lines = [
        f'# Daily Brief — {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '',
        f'## Top Headlines ({len(entries)} articles)',
        '',
    ]
    for i, e in enumerate(entries, 1):
        lines.append(f'{i}. [{e["source"]}] {e["title"]}')
        lines.append(f'   {e["link"]}')
        lines.append('')
    lines.append('---')
    lines.append(f'*Auto-generated at {datetime.now().strftime("%Y-%m-%d %H:%M")}*')
    BRIEF.write_text('\n'.join(lines), encoding='utf-8')
    log(f'Updated daily-brief.md with {len(entries)} articles')

def main():
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    all_entries = []
    for name, url in RSS_FEEDS:
        entries = fetch_feed(name, url)
        all_entries.extend(entries)
    all_entries.sort(key=lambda x: x.get('published', ''), reverse=True)
    update_brief(all_entries[:20])
    log(f'Done. Fetched {len(all_entries)} total articles')

if __name__ == '__main__':
    main()
