#!/usr/bin/env python3
# scripts/daily_news_fetcher.py
# Fetches latest car news from RSS feeds
# Run: python3 scripts/daily_news_fetcher.py
# Auto-schedule: 0 0 * * * (daily at 00:00 HKT)

import feedparser, sqlite3, sys, re
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent.parent
DB     = BASE / 'data' / 'cars.db'
BRIEF  = BASE / 'agent-meta' / 'daily-brief.md'
NEWS_DIR = BASE / 'data' / 'daily-news'

RSS_FEEDS = [
    ('TopGear', 'https://www.topgear.com carc/rss'),
    ('CarAndDriver', 'https://www.caranddriver.com/rss'),
    ('MotorTrend', 'https://www.motortrend.com/rss'),
    ('Autocar', 'https://www.autocar.co.uk/rss'),
    ('Evo', 'https://www.evo.co.uk/rss'),
    ('Jalopnik', 'https://jalopnik.com/rss'),
    ('RoadandTrack', 'https://www.roadandtrack.com/rss'),
    ('Autoblog', 'https://www.autoblog.com/rss'),
]

def log(msg): print(f'[{datetime.now().strftime("%H:%M")}] {msg}')

def fetch_feed(name, url):
    try:
        feed = feedparser.parse(url)
        entries = []
        for e in feed.entries[:5]:
            entries.append({
                'title': e.get('title', ''),
                'link': e.get('link', ''),
                'published': e.get('published', ''),
                'source': name,
            })
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
    # Sort by published date
    all_entries.sort(key=lambda x: x.get('published', ''), reverse=True)
    update_brief(all_entries[:20])
    log(f'Done. Fetched {len(all_entries)} total articles')

if __name__ == '__main__':
    main()
