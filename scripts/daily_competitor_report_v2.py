#!/usr/bin/env python3
"""
daily_competitor_report_v2.py
==============================
Enhanced Daily Competitor Report with validation + quota handling + fallback.

Key improvements over v1:
  1. yt_api() catches 403 quota errors and raises QuotaExceededError
  2. Falls back to cached competitor data if API fails
  3. Freshness Stamp in every output
  4. API success/fail status reported
  5. Stores cache on successful fetch for next-time fallback

Usage:
    python3 scripts/daily_competitor_report_v2.py
"""

import os, sys, re, json, ssl, time
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import sqrt

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE        = Path(__file__).parent.parent
CACHE_FILE  = BASE / 'agent-meta' / 'competitor-cache.json'
REPORT_FILE = BASE / 'agent-meta' / 'competitor-analysis-phase2-enhanced.md'
CACHE_TTL   = timedelta(hours=48)  # Cache valid for 48h if API fails

# ─────────────────────────────────────────
# Load API Key
# ─────────────────────────────────────────
API_KEY = ''
env_path = BASE / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith('GOOGLE_API_KEY='):
            API_KEY = line.split('=', 1)[1].strip()
            break

if not API_KEY:
    print("❌ Error: GOOGLE_API_KEY not found in .env")
    sys.exit(1)

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ─────────────────────────────────────────
# API with quota error handling
# ─────────────────────────────────────────

class QuotaExceededError(Exception):
    """Raised when YouTube API returns 403 quota exceeded."""
    pass

def yt_api(endpoint, params):
    """Call YouTube Data API v3 with quota error detection."""
    import urllib.request, urllib.error
    base = 'https://www.googleapis.com/youtube/v3'
    p = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{base}/{endpoint}?{p}&key={API_KEY}'
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
            data = json.loads(resp.read())
            # Check for quota error in response
            if 'error' in data:
                err = data['error']
                if err.get('code') == 403:
                    for e_detail in err.get('errors', []):
                        if e_detail.get('reason') in ('quotaExceeded', 'dailyLimitExceeded'):
                            raise QuotaExceededError(f"Quota exceeded: {e_detail.get('message')}")
            return data
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise QuotaExceededError(f"HTTP 403: quota exceeded")
        raise


def get_all_videos(handle):
    """Fetch all videos for a channel handle. Raises QuotaExceededError on 403."""
    import urllib.request, urllib.error
    try:
        url = f'https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&forHandle={handle}&key={API_KEY}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
            ch = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise QuotaExceededError(f"Channel lookup 403: {handle}")
        raise

    if not ch.get('items'):
        return [], 0
    item = ch['items'][0]
    uploads_id = item['contentDetails']['relatedPlaylists']['uploads']
    sub_count = int(item['statistics'].get('subscriberCount', 0))

    all_videos = []
    all_ids = []
    page_token = None
    while True:
        pl_params = {'part': 'contentDetails', 'playlistId': uploads_id, 'maxResults': 50}
        if page_token:
            pl_params['pageToken'] = page_token
        pl = yt_api('playlistItems', pl_params)
        items = pl.get('items', [])
        ids = [it['contentDetails']['videoId'] for it in items if it['contentDetails'].get('videoId')]
        all_ids.extend(ids)
        page_token = pl.get('nextPageToken')
        if not page_token:
            break
        time.sleep(0.5)

    # Batch fetch statistics, contentDetails, AND snippet (titles) — 50 at a time
    for i in range(0, len(all_ids), 50):
        batch = all_ids[i:i+50]
        stats = yt_api('videos', {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(batch),
        })
        for item in stats.get('items', []):
            vid = item['id']
            duration_str = item['contentDetails'].get('duration', 'PT0S')
            views = int(item['statistics'].get('viewCount', 0))
            likes = int(item['statistics'].get('likeCount', 0))
            comments = int(item['statistics'].get('commentCount', 0))
            title = item.get('snippet', {}).get('title', '')
            published_at = item.get('snippet', {}).get('publishedAt', None)
            # Parse ISO 8601 duration
            m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            h  = int(m.group(1) or 0)
            mi = int(m.group(2) or 0)
            s  = int(m.group(3) or 0)
            duration_sec = h*3600 + mi*60 + s
            is_short = duration_sec < 60
            all_videos.append({
                'id': vid,
                'title': title,
                'view_count': views,
                'like_count': likes,
                'comment_count': comments,
                'duration_sec': duration_sec,
                'is_short': is_short,
                'published_at': published_at,
            })
        time.sleep(0.5)

    return all_videos, sub_count

# ─────────────────────────────────────────
# Cache management
# ─────────────────────────────────────────

def load_cache():
    """Load cached competitor data if available and not stale.

    Tries three sources in order:
      1. competitor-cache.json (v2 format: {timestamp, kiz: {videos, subs}, moto: {videos, subs}})
      2. competitor-analysis-phase2-enhanced.md (v1 JSON format: [{name, ...}, {name, ...}])
    Returns None if all sources fail or are stale (>48h).
    """
    from datetime import datetime as dt

    # Source 1: v2 JSON cache
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            cache_time = dt.fromisoformat(data['timestamp'])
            if dt.now() - cache_time <= CACHE_TTL:
                return data
        except Exception:
            pass

    # Source 2: enhanced report JSON fallback (last resort, no TTL check)
    if REPORT_FILE.exists():
        try:
            raw = REPORT_FILE.read_text().strip()
            # Check if it starts with JSON array (v1 format)
            if raw.startswith('['):
                items = json.loads(raw)
                kiz_data = next((x for x in items if x.get('name') == 'ArtKiz'), None)
                moto_data = next((x for x in items if x.get('name') == 'Motomorfosis'), None)
                if kiz_data or moto_data:
                    # Extract what we can — return in v2 cache format
                    kiz_subs = kiz_data.get('subscribers', 0) if kiz_data else 0
                    moto_subs = moto_data.get('subscribers', 0) if moto_data else 0
                    mtime = dt.fromtimestamp(REPORT_FILE.stat().st_mtime)
                    return {
                        'timestamp': mtime.isoformat(),
                        'kiz': {'videos': [], 'subs': kiz_subs},
                        'moto': {'videos': [], 'subs': moto_subs},
                    }
        except Exception:
            pass

    return None

def save_cache(kiz_videos, kiz_sub, moto_videos, moto_sub):
    """Save competitor data to cache."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'timestamp': datetime.now().isoformat(),
        'kiz': {'videos': kiz_videos, 'subs': kiz_sub},
        'moto': {'videos': moto_videos, 'subs': moto_sub},
    }
    CACHE_FILE.write_text(json.dumps(data))

# ─────────────────────────────────────────
# Analysis functions
# ─────────────────────────────────────────

def brand_count(shorts, brand):
    keywords = {
        'bugatti': ['bugatti'],
        'ferrari': ['ferrari'],
        'porsche': ['porsche'],
        'lamborghini': ['lamborghini'],
        'mclaren': ['mclaren'],
        'aston martin': ['aston martin'],
        'maserati': ['maserati'],
        'bentley': ['bentley'],
        'rolls-royce': ['rolls-royce'],
        'bmw': ['bmw'],
        'mercedes': ['mercedes', 'amg'],
        'audi': ['audi'],
        'nissan': ['nissan', 'gtr', 'skyline'],
        'toyota': ['toyota', 'supra', 'gr86', 'ae86'],
        'honda': ['honda', 'nsx', 'civic'],
        'mazda': ['mazda', 'rx-7', 'rx-8', 'miata'],
        'ford': ['ford', 'mustang', 'gt40'],
        'chevrolet': ['chevrolet', 'corvette', 'camaro'],
        'dodge': ['dodge', 'viper', 'challenger', 'hellcat'],
        'tesla': ['tesla'],
        'jdm': ['jdm'],
    }
    kw = keywords.get(brand.lower(), [brand.lower()])
    return sum(1 for s in shorts if any(k in str(s.get('title', '')).lower() for k in kw))

def eng_rate(s):
    return (s['like_count'] + s['comment_count']) / s['view_count'] * 100 if s['view_count'] > 0 else 0

def percentile(p, shorts):
    if not shorts:
        return 0
    sorted_v = sorted(s['view_count'] for s in shorts)
    idx = int(len(sorted_v) * p / 100)
    return sorted_v[min(idx, len(sorted_v)-1)]

# ─────────────────────────────────────────
# Build report
# ─────────────────────────────────────────

def build_report(kiz_videos, kiz_sub, moto_videos, moto_sub, api_status):
    """Build the full report markdown."""
    kiz_shorts = [v for v in kiz_videos if v['is_short']]
    moto_shorts = [v for v in moto_videos if v['is_short']]
    kiz_viral = [v for v in kiz_shorts if v['view_count'] > 1_000_000]
    moto_viral = [v for v in moto_shorts if v['view_count'] > 1_000_000]
    kiz_top10 = sorted(kiz_shorts, key=lambda x: x['view_count'], reverse=True)[:10]
    now_utc = datetime.utcnow()
    # 7-day recent shorts (using published_at timestamp)
    cutoff = datetime.utcnow() - timedelta(days=7)
    def parse_dt(iso_str):
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        except ValueError:
            return None

    kiz_r7 = []
    kiz_r7_viral = []
    for s in kiz_shorts:
        dt = parse_dt(s.get('published_at'))
        if dt and dt.replace(tzinfo=None) >= cutoff:
            kiz_r7.append(s)
            if s['view_count'] > 1_000_000:
                kiz_r7_viral.append(s)

    moto_r7 = []
    moto_r7_viral = []
    for s in moto_shorts:
        dt = parse_dt(s.get('published_at'))
        if dt and dt.replace(tzinfo=None) >= cutoff:
            moto_r7.append(s)
            if s['view_count'] > 1_000_000:
                moto_r7_viral.append(s)

    freshness = "✅ LIVE" if api_status == 'live' else (f"⚠️ CACHED ({api_status})")

    lines = [
        f"# 📊 Daily Competitor Report — {datetime.now().strftime('%Y-%m-%d %H:%M HKT')}",
        "",
        "## ⚠️ DATA FRESHNESS",
        f"- **Status:** {freshness}",
        f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')} HKT",
        f"- **API Status:** {'✅ Successful' if api_status == 'live' else f'❌ Failed ({api_status})'}",
        "",
        "## 📱 Channel Overview",
        f"| Channel | Subscribers | Shorts | Viral |",
        f"|---------|------------|--------|-------|",
        f"| @kizzombie | {kiz_sub:,} | {len(kiz_shorts)} | {len(kiz_viral)} |",
        f"| @motomorfosis | {moto_sub:,} | {len(moto_shorts)} | {len(moto_viral)} |",
        "",
        "## 🚨 Early Warning (Past 7 Days)",
        f"| Channel | New Shorts | New Viral |",
        f"|---------|-----------|----------|",
        f"| @kizzombie | {len(kiz_r7)} | {len(kiz_r7_viral)} |",
        f"| @motomorfosis | {len(moto_r7)} | {len(moto_r7_viral)} |",
    ]

    # Show recent shorts detail if any
    for ch_name, r7_list, r7_viral_list in [
        ('@kizzombie', kiz_r7, kiz_r7_viral),
        ('@motomorfosis', moto_r7, moto_r7_viral),
    ]:
        if r7_list:
            lines.append(f"**{ch_name} recent uploads:**")
            for s in sorted(r7_list, key=lambda x: x.get('published_at', ''), reverse=True)[:5]:
                dt_str = s.get('published_at', '?')[:10] if s.get('published_at') else '?'
                lines.append(f"  • {s['title'][:60]} ({dt_str}) | {s['view_count']:,} views")
            if r7_viral_list:
                lines.append(f"  🆕 New viral: **{r7_viral_list[0]['title'][:60]}** ({r7_viral_list[0]['view_count']:,} views)")
            lines.append("")

    lines += [
        "| Brand | kizzombie | motomorfosis | Opportunity |",
        "|-------|----------|--------------|-------------|",
    ]

    # Real brand gap analysis from actual shorts titles
    brands_to_check = [
        'Bugatti', 'Ferrari', 'McLaren', 'Porsche', 'Lamborghini',
        'Aston Martin', 'Maserati', 'Bentley', 'Rolls-Royce',
        'BMW', 'Mercedes', 'Nissan', 'Toyota', 'Honda',
    ]
    brand_counts = [
        (brand, brand_count(kiz_shorts, brand), brand_count(moto_shorts, brand))
        for brand in brands_to_check
    ]
    for brand, kc, mc in brand_counts:
        total = kc + mc
        if total == 0:
            opp = '🌊🌊🌊 SUPER'
        elif total <= 2:
            opp = '🌊🌊 HIGH'
        elif total <= 5:
            opp = '🌊 MEDIUM'
        else:
            opp = '🔴 CROWDED'
        lines.append(f"| {brand} | {kc} | {mc} | {opp} |")

    lines += [
        "",
        "## 📡 Data Source",
        "- **Source:** YouTube Data API v3 (live) OR cached data",
        "- **Cache validity:** 48 hours if API fails",
        "",
    ]
    return '\n'.join(lines)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    print("📊 Daily Competitor Report v2 — Enhanced with Quota Handling")
    print("=" * 70)

    api_status = 'unknown'
    cache_hit = False

    # Try live fetch
    try:
        print("\n📡 Fetching @kizzombie...")
        kiz_videos, kiz_sub = get_all_videos('kizzombie')
        kiz_shorts = [v for v in kiz_videos if v['is_short']]
        print(f"   ✅ {len(kiz_shorts)} Shorts | {kiz_sub:,} subs")

        print("\n📡 Fetching @motomorfosis...")
        moto_videos, moto_sub = get_all_videos('motomorfosis')
        moto_shorts = [v for v in moto_videos if v['is_short']]
        print(f"   ✅ {len(moto_shorts)} Shorts | {moto_sub:,} subs")

        api_status = 'live'
        save_cache(kiz_videos, kiz_sub, moto_videos, moto_sub)
        print("   💾 Cached for fallback")

    except QuotaExceededError as e:
        print(f"\n⚠️  YouTube API Quota Exceeded: {e}")
        print("    → Loading cached data...")

        cache = load_cache()
        if cache:
            kiz_videos = cache['kiz']['videos']
            kiz_sub    = cache['kiz']['subs']
            moto_videos = cache['moto']['videos']
            moto_sub   = cache['moto']['subs']
            api_status = f"CACHED ({cache['timestamp'][:10]})"
            cache_hit = True
            print(f"   ✅ Loaded cache from {cache['timestamp'][:10]}")
        else:
            print("   ❌ No cache available — cannot generate report")
            return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        cache = load_cache()
        if cache:
            kiz_videos = cache['kiz']['videos']
            kiz_sub    = cache['kiz']['subs']
            moto_videos = cache['moto']['videos']
            moto_sub   = cache['moto']['subs']
            api_status = f"CACHED ({cache['timestamp'][:10]}) — API error"
            print(f"   ⚠️  Falling back to cache from {cache['timestamp'][:10]}")
        else:
            print("   ❌ No cache — cannot generate report")
            return 1

    # Build and save report
    report = build_report(kiz_videos, kiz_sub, moto_videos, moto_sub, api_status)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report)
    print(f"\n✅ Report saved: {REPORT_FILE}")
    print(f"📋 Data freshness: {api_status}")

    if api_status != 'live':
        print("\n⚠️  WARNING: Report uses CACHED data.")
        print("    YouTube API quota may be exceeded. Check Google Cloud Console.")

    return 0 if api_status == 'live' else 1


if __name__ == '__main__':
    sys.exit(main())
