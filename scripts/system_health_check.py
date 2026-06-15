#!/usr/bin/env python3
"""
system_health_check.py
=====================
Hourly system health check for car-evolution-project.

Checks:
  1. All data files freshness (daily-brief, trend-report, competitor, topic-priority)
  2. YouTube API quota status (quick API probe)
  3. RSS feed connectivity (TopGear + CarAndDriver)
  4. Cron job last-run timestamps

Exit codes:
  0 = All healthy
  1 = Problems detected (alert sent to Telegram)

Outputs:
  - JSON status to stdout (for cron log)
  - Telegram alert on problems
"""

import os, sys, json, ssl, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timedelta

BASE        = Path(__file__).parent.parent
TOKEN       = "8726708023:AAFJVgysrbQczcQC1geUrezWYN8M6VUoLjM"
CHAT_ID     = "6394565017"
CTX         = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Thresholds
MAX_AGE_BRIEF     = timedelta(hours=14)   # Warn if daily-brief > 14h old
MAX_AGE_TREND     = timedelta(hours=14)
MAX_AGE_COMPETITOR= timedelta(hours=30)
MAX_AGE_TOPIC     = timedelta(hours=16)
STALE_DELTA       = timedelta(days=1)      # "stale" vs "fresh"

def age_of(path: Path) -> timedelta | None:
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime

def check_file(name, path, max_age) -> dict:
    age = age_of(path)
    if age is None:
        return {"name": name, "status": "❌ MISSING", "age_h": None, "fresh": False, "critical": True}
    age_h = age.total_seconds() / 3600
    if age > max_age:
        if age > max_age + STALE_DELTA:
            return {"name": name, "status": "🔴 STALE", "age_h": round(age_h,1), "fresh": False, "critical": True}
        return {"name": name, "status": "⚠️  OLD", "age_h": round(age_h,1), "fresh": False, "critical": False}
    return {"name": name, "status": "✅ FRESH", "age_h": round(age_h,1), "fresh": True, "critical": False}

def check_yt_api_quota() -> dict:
    """Probe YouTube API with a cheap call to check quota status."""
    import os
    api_key = ''
    env_path = BASE / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith('GOOGLE_API_KEY='):
                api_key = line.split('=',1)[1].strip()
                break
    if not api_key:
        return {"status": "❌ NO KEY", "ok": False}

    try:
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&forHandle=kizzombie&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
            data = json.loads(resp.read())
            if 'error' in data:
                err = data['error']
                if err.get('code') == 403:
                    for e in err.get('errors', []):
                        if e.get('reason') in ('quotaExceeded', 'dailyLimitExceeded'):
                            return {"status": "❌ QUOTA EXHAUSTED", "ok": False}
                return {"status": f"⚠️  API ERROR {err.get('code')}", "ok": False}
            return {"status": "✅ QUOTA OK", "ok": True}
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {"status": "❌ QUOTA EXHAUSTED (403)", "ok": False}
        return {"status": f"⚠️  HTTP {e.code}", "ok": False}
    except Exception as e:
        return {"status": f"⚠️  NETWORK ERROR: {e}", "ok": False}

def check_rss_feed(name, url) -> dict:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            if '<rss' in content.lower() or '<feed' in content.lower():
                return {"name": name, "status": "✅ OK", "ok": True}
            return {"name": name, "status": "⚠️  UNEXPECTED", "ok": False}
    except Exception as e:
        return {"name": name, "status": f"❌ {e}", "ok": False}

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
    try:
        req = urllib.request.Request(url, data=data.encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return None

def main():
    now = datetime.now()
    print(f"🔍 System Health Check — {now.strftime('%Y-%m-%d %H:%M HKT')}")
    print("=" * 60)

    problems = []
    warnings = []

    # 1. File freshness
    files = [
        ("daily-brief.md",       BASE/"agent-meta"/"daily-brief.md",               MAX_AGE_BRIEF),
        ("trend-report.md",      BASE/"agent-meta"/"trend-report.md",               MAX_AGE_TREND),
        ("competitor-report.md", BASE/"agent-meta"/"competitor-analysis-phase2-enhanced.md", MAX_AGE_COMPETITOR),
        ("topic-priority.md",    BASE/"exports"/"topic-priority"/"latest-report.md", MAX_AGE_TOPIC),
    ]
    file_results = []
    for name, path, max_age in files:
        r = check_file(name, path, max_age)
        file_results.append(r)
        print(f"  {r['status']}  {name} ({r['age_h']}h old)" if r['age_h'] else f"  {r['status']}  {name}")
        if r['critical']:
            problems.append(f"{r['status']} {name} ({r['age_h']}h old)" if r['age_h'] else f"{r['status']} {name}")
        elif not r['fresh']:
            warnings.append(f"{r['status']} {name} ({r['age_h']}h old)" if r['age_h'] else f"{r['status']} {name}")

    # 2. YouTube API quota
    print("\n📡 YouTube API Quota:")
    yt = check_yt_api_quota()
    print(f"  {yt['status']}")
    if not yt['ok']:
        problems.append(f"YouTube API: {yt['status']}")

    # 3. RSS feeds
    print("\n📡 RSS Feeds:")
    feeds = [
        ("TopGear RSS",    "https://news.google.com/rss/search?q=cars+site:topgear.com&hl=en-US&gl=US&ceid=US:en"),
        ("CarAndDriver",   "https://www.caranddriver.com/rss/all.xml"),
        ("Motor1 RSS",     "https://www.motor1.com/rss/news/all/"),
    ]
    feed_results = []
    for name, url in feeds:
        r = check_rss_feed(name, url)
        feed_results.append(r)
        print(f"  {r['status']}  {name}")
        if not r['ok']:
            warnings.append(f"RSS {name}: {r['status']}")

    # Summary
    print("\n" + "=" * 60)
    has_critical = len(problems) > 0

    if has_critical:
        msg = f"🚨 *System Health Alert*\n{datetime.now().strftime('%Y-%m-%d %H:%M HKT')}\n\n"
        msg += "*❌ CRITICAL Issues:*\n"
        for p in problems:
            msg += f"• {p}\n"
        if warnings:
            msg += "\n*⚠️  Warnings:*\n"
            for w in warnings:
                msg += f"• {w}\n"
        msg += f"\n_Cron jobs will continue with stale data._"
        send_telegram(msg)
        print(f"🚨 Alert sent: {len(problems)} critical, {len(warnings)} warnings")
        return 1
    elif warnings:
        print(f"⚠️  {len(warnings)} warning(s) — no Telegram alert sent (non-critical)")
        return 0
    else:
        print("✅ All systems healthy")
        return 0

if __name__ == '__main__':
    sys.exit(main())
