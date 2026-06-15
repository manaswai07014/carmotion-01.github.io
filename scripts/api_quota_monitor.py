#!/usr/bin/env python3
"""
api_quota_monitor.py
====================
Daily YouTube API quota usage monitor.
Checks how much of the 10,000-unit daily quota has been used.

YouTube Data API v3 free tier: 10,000 units/day
- search: 100 units/call
- channels: 1 unit/call
- playlistItems: 1 unit/call
- videos: 1 unit/call

This script estimates usage from cached API responses.
"""

import json, sys, ssl, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timedelta

BASE    = Path(__file__).parent.parent
CTX     = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE

QUOTA_LIMIT = 10_000

def get_api_key():
    env = BASE / '.env'
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith('GOOGLE_API_KEY='):
                return line.split('=', 1)[1].strip()
    return None

def estimate_units_from_logs() -> dict:
    """Count estimated API units from news/trend/competitor logs."""
    # We track rough call counts per script run
    # This is an ESTIMATE based on typical script behavior
    log_dir = BASE / 'agent-meta'
    today   = datetime.now().strftime('%Y-%m-%d')

    units = {
        'search_calls': 0,
        'channel_calls': 0,
        'playlist_calls': 0,
        'video_calls': 0,
        'total_estimate': 0,
    }

    # Check news cron log
    news_log = log_dir / 'news-cron.log'
    if news_log.exists():
        content = news_log.read_text()
        # news fetcher does channel lookups + video stats batches
        # rough: 2 channels × 5 pages × 50 items = 500 video stats = 500 units
        # + 2 channel calls = 2 units
        units['channel_calls'] += 2
        units['video_calls'] += 500
        units['total_estimate'] += 502

    # Check trend cron log
    trend_log = log_dir / 'trend-cron.log'
    if trend_log.exists():
        content = trend_log.read_text()
        # trend uses pytrends (free) or Google News RSS (free) — no API cost
        pass

    # For actual quota check, use the API probe
    return units

def probe_api_quota() -> dict:
    """
    Make a minimal API call to check if quota is exhausted.
    Returns: {"quota_exhausted": bool, "http_status": int, "error_reason": str}
    """
    api_key = get_api_key()
    if not api_key:
        return {"quota_exhausted": False, "http_status": 0, "error_reason": "NO_KEY"}

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
                            return {"quota_exhausted": True, "http_status": 403, "error_reason": "quotaExceeded"}
                    return {"quota_exhausted": True, "http_status": 403, "error_reason": "forbidden"}
                return {"quota_exhausted": False, "http_status": err.get('code'), "error_reason": str(err)}
            return {"quota_exhausted": False, "http_status": 200, "error_reason": "ok"}
    except urllib.error.HTTPError as e:
        if e.code == 403:
            try:
                err_data = json.loads(e.read())
                reason = "unknown"
                if 'error' in err_data:
                    for err in err_data['error'].get('errors', []):
                        reason = err.get('reason', 'unknown')
            except Exception:
                reason = "unparseable"
            return {"quota_exhausted": True, "http_status": 403, "error_reason": reason}
        return {"quota_exhausted": False, "http_status": e.code, "error_reason": f"HTTP_{e.code}"}
    except Exception as e:
        return {"quota_exhausted": False, "http_status": 0, "error_reason": str(e)}

def main():
    print("📊 YouTube API Quota Monitor")
    print("=" * 50)
    print(f"Daily limit: {QUOTA_LIMIT:,} units")
    print(f"Check time: {datetime.now().strftime('%Y-%m-%d %H:%M HKT')}")
    print()

    # Probe quota
    result = probe_api_quota()
    print(f"API Status: {result['error_reason']}")
    print(f"HTTP Status: {result['http_status']}")
    print(f"Quota Exhausted: {result['quota_exhausted']}")
    print()

    if result['quota_exhausted']:
        print("🚨 QUOTA EXHAUSTED — YouTube API calls will fail until HK midnight")
        print("   Competitor reports will use CACHED data")
        print("   Topic Priority scores will have YouTube=0")
        print()
        print("💡 Solutions:")
        print("   1. Wait for HK midnight (quota resets daily)")
        print("   2. Apply for higher quota: https://console.cloud.google.com")
        print("   3. Use cached data as fallback (already implemented)")
    else:
        print("✅ API responding normally — quota appears available")

    print()
    print("--- Estimated usage from log analysis ---")
    units = estimate_units_from_logs()
    print(f"Channel calls: ~{units['channel_calls']} units")
    print(f"Video stats calls: ~{units['video_calls']} units")
    print(f"Total estimated: ~{units['total_estimate']} units")
    print(f"Quota headroom: ~{QUOTA_LIMIT - units['total_estimate']:,} units remaining")
    print()
    print("Note: Actual quota may differ from estimate.")
    print("      Only the Google Cloud Console shows real usage.")

    return 0 if not result['quota_exhausted'] else 1

if __name__ == '__main__':
    sys.exit(main())
