#!/usr/bin/env python3
# scripts/trend_monitor.py
# Monitors Google Trends for car-related keywords
# Run: python3 scripts/trend_monitor.py
# Auto-schedule: 0 1 */2 * * (every 2 days at 01:00 HKT)

import sys, re
from pathlib import Path
from datetime import datetime, timedelta

BASE   = Path(__file__).parent.parent
REPORT = BASE / 'agent-meta' / 'trend-report.md'

CAR_KEYWORDS = [
    'GT-R', 'Supra', 'Miata', 'M3', 'Cayman', '911',
    'Skyline', 'RX-7', 'Evo', 'STI', 'Type R', 'AMG',
    'Ferrari', 'Lamborghini', 'Porsche 911', 'Honda Civic',
]

def log(msg): print(f'[{datetime.now().strftime("%H:%M")}] {msg}')

def fetch_trends(keywords):
    """Fetch Google Trends for keywords. Returns mock data if pytrends unavailable."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=360)
        trends = {}
        for kw in keywords:
            try:
                pytrends.build_payload([kw], timeframe='now 7-d')
                data = pytrends.interest_over_time()
                if not data.empty:
                    trends[kw] = float(data[kw].iloc[-1])
            except Exception:
                trends[kw] = 0
        return trends
    except ImportError:
        log('pytrends not available, using mock data')
        return {kw: 50 for kw in keywords}

def update_report(trends):
    sorted_trends = sorted(trends.items(), key=lambda x: x[1], reverse=True)
    lines = [
        f'# Trend Report — {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '',
        '## Top Rising Car Searches (7-day window)',
        '',
    ]
    for kw, score in sorted_trends[:10]:
        bar = '█' * int(score / 10)
        lines.append(f'{kw:20s} {bar} ({score})')
    lines.append('')
    lines.append('---')
    lines.append(f'*Auto-generated at {datetime.now().strftime("%Y-%m-%d %H:%M")}*')
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    log(f'Updated trend-report.md with {len(trends)} keywords')

def main():
    trends = fetch_trends(CAR_KEYWORDS)
    update_report(trends)
    log('Done')

if __name__ == '__main__':
    main()
