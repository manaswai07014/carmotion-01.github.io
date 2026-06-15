#!/usr/bin/env python3
"""Full YouTube Data API analysis for @kizzombie"""
import urllib.request
import json
import re
from collections import Counter

API_KEY = 'AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM'
CHANNEL_ID = 'UC2IRZdo5HP4IjzuAjlsLjOg'

def yt_api(endpoint, params):
    base = 'https://www.googleapis.com/youtube/v3'
    p = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{base}/{endpoint}?{p}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# ============================================================
# STEP 1: Channel Info
# ============================================================
print("=" * 70)
print("STEP 1: CHANNEL INFO")
print("=" * 70)

ch = yt_api('channels', {'part': 'snippet,statistics,contentDetails', 'id': CHANNEL_ID})
if not ch['items']:
    print("ERROR: Channel not found!")
    exit(1)

item = ch['items'][0]
sn = item['snippet']
st = item['statistics']
uploads_id = item['contentDetails']['relatedPlaylists']['uploads']

print(f"Title: {sn['title']}")
print(f"Custom URL: @{sn.get('customUrl', 'N/A').replace('@','')}")
print(f"Subscribers: {int(st.get('subscriberCount', 0)):,}")
print(f"Total Views: {int(st.get('viewCount', 0)):,}")
print(f"Total Videos: {int(st.get('videoCount', 0))}")
print(f"Uploads Playlist: {uploads_id}")

# ============================================================
# STEP 2: Get ALL uploads (paginated)
# ============================================================
print("\n" + "=" * 70)
print("STEP 2: FETCHING ALL VIDEOS FROM UPLOADS PLAYLIST")
print("=" * 70)

all_video_ids = []
page_token = None
while True:
    pl_params = {
        'part': 'contentDetails',
        'playlistId': uploads_id,
        'maxResults': 50
    }
    if page_token:
        pl_params['pageToken'] = page_token

    pl = yt_api('playlistItems', pl_params)
    items = pl.get('items', [])
    video_ids = [it['contentDetails']['videoId'] for it in items if it['contentDetails'].get('videoId')]
    all_video_ids.extend(video_ids)

    print(f"  Fetched {len(items)} items (total: {len(all_video_ids)})")
    page_token = pl.get('nextPageToken')
    if not page_token:
        break

print(f"\nTotal videos in uploads playlist: {len(all_video_ids)}")

# ============================================================
# STEP 3: Get video details in batches (50 at a time)
# ============================================================
print("\n" + "=" * 70)
print("STEP 3: FETCHING VIDEO DETAILS (snippet + statistics)")
print("=" * 70)

all_videos = []
for i in range(0, len(all_video_ids), 50):
    batch = all_video_ids[i:i+50]
    ids_str = ','.join(batch)

    vd = yt_api('videos', {
        'part': 'snippet,statistics,contentDetails',
        'id': ids_str
    })

    for item in vd.get('items', []):
        sn = item['snippet']
        st = item['statistics']
        cd = item['contentDetails']

        # Determine if Short (duration <= 60s)
        duration = cd.get('duration', 'PT0S')
        # Parse ISO 8601 duration
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            s = int(match.group(3) or 0)
            total_sec = h*3600 + m*60 + s
        else:
            total_sec = 0

        is_short = total_sec <= 60

        all_videos.append({
            'id': item['id'],
            'title': sn['title'],
            'published': sn['publishedAt'],
            'view_count': int(st.get('viewCount', 0)),
            'like_count': int(st.get('likeCount', 0)),
            'comment_count': int(st.get('commentCount', 0)),
            'duration_sec': total_sec,
            'is_short': is_short,
            'category_id': sn.get('categoryId', ''),
        })

    print(f"  Batch {i//50 + 1}: fetched {len(vd.get('items', []))} videos ({len(all_videos)} total)")

print(f"\nTotal videos fetched: {len(all_videos)}")

# ============================================================
# STEP 4: Separate Shorts from regular videos
# ============================================================
print("\n" + "=" * 70)
print("STEP 4: SEPARATE SHORTS vs REGULAR VIDEOS")
print("=" * 70)

shorts = [v for v in all_videos if v['is_short']]
regulars = [v for v in all_videos if not v['is_short']]

print(f"Shorts (<=60s): {len(shorts)}")
print(f"Regular videos: {len(regulars)}")
print(f"Shorts ratio: {100*len(shorts)/len(all_videos):.1f}%")

# ============================================================
# STEP 5: View count distribution
# ============================================================
print("\n" + "=" * 70)
print("STEP 5: VIEW COUNT DISTRIBUTION")
print("=" * 70)

views = [v['view_count'] for v in shorts]
views_sorted = sorted(views, reverse=True)

print(f"Total Shorts: {len(shorts)}")
print(f"Max views: {max(views):,}")
print(f"Min views: {min(views):,}")
print(f"Avg views: {sum(views)//len(views):,}")
print(f"Median views: {views_sorted[len(views_sorted)//2]:,}")

# Milestones
for threshold in [1_000_000, 5_000_000, 10_000_000, 20_000_000]:
    cnt = sum(1 for v in views if v >= threshold)
    print(f"  >= {threshold:,} views: {cnt} ({100*cnt/len(shorts):.1f}%)")

viral = [v for v in shorts if v['view_count'] > 1_000_000]
print(f"\nVIRAL (>1M views): {len(viral)} ({100*len(viral)/len(shorts):.1f}%)")

# ============================================================
# STEP 6: VIRAL analysis - keyword frequency
# ============================================================
print("\n" + "=" * 70)
print("STEP 6: VIRAL KEYWORD ANALYSIS (>1M views)")
print("=" * 70)

CAR_KEYWORDS = {
    'evolution': ['evolution', 'evolve', 'evolusi'],
    'iconic': ['iconic', 'legendary', 'legenda', 'legendaris'],
    'military': ['military', 'army', 'soldier'],
    'brand': ['bmw', 'mercedes', 'honda', 'toyota', 'ford', 'bugatti', 'ferrari', 'porsche',
              'lamborghini', 'mitsubishi', 'nissan', 'mazda', 'subaru', 'lexus', 'audi',
              'jaguar', 'maserati', 'bentley', 'rolls', 'royal enfield', 'yamaha', 'kawasaki',
              'ducati', 'suzuki', 'jupiter', 'mio', 'rx'],
    'year_range': ['-', 'to', 'gen'],
    'number': ['1', '2', '3', '4', '5'],
}

def has_kw(title, keywords):
    t = title.lower()
    return any(k in t for k in keywords)

def has_year_range(title):
    t = title.lower()
    return bool(re.search(r'\d{4}\s*[-–]\s*\d{4}', t)) or bool(re.search(r'\d{4}\s+to\s+\d{4}', t))

print(f"\nViral count: {len(viral)}")
print("\nKeyword analysis (viral vs ALL shorts):")
print(f"{'Keyword':<15} {'Viral%':>8} {'All%':>8} {'Diff':>8} {'Viral#':>8} {'All#':>8}")
print("-" * 60)

viral_results = {}
for cat, keywords in CAR_KEYWORDS.items():
    if cat == 'year_range':
        v_cnt = sum(1 for s in viral if has_year_range(s['title']))
        a_cnt = sum(1 for s in shorts if has_year_range(s['title']))
    else:
        v_cnt = sum(1 for s in viral if has_kw(s['title'], keywords))
        a_cnt = sum(1 for s in shorts if has_kw(s['title'], keywords))

    vp = 100*v_cnt/len(viral) if viral else 0
    ap = 100*a_cnt/len(shorts) if shorts else 0
    diff = vp - ap
    viral_results[cat] = (vp, ap, diff, v_cnt, a_cnt)
    print(f"{cat:<15} {vp:>7.1f}% {ap:>7.1f}% {diff:>+7.1f}% {v_cnt:>8} {a_cnt:>8}")

# ============================================================
# STEP 7: TOP 10 BY VIEWS analysis
# ============================================================
print("\n" + "=" * 70)
print("STEP 7: TOP 10 BY VIEWS KEYWORD ANALYSIS")
print("=" * 70)

sorted_shorts = sorted(shorts, key=lambda x: x['view_count'], reverse=True)
top10 = sorted_shorts[:10]

print(f"\n{'Keyword':<15} {'Top10%':>8} {'All%':>8} {'Diff':>8} {'T10#':>6} {'All#':>8}")
print("-" * 60)

top10_results = {}
for cat, keywords in CAR_KEYWORDS.items():
    if cat == 'year_range':
        t_cnt = sum(1 for s in top10 if has_year_range(s['title']))
        a_cnt = sum(1 for s in shorts if has_year_range(s['title']))
    else:
        t_cnt = sum(1 for s in top10 if has_kw(s['title'], keywords))
        a_cnt = sum(1 for s in shorts if has_kw(s['title'], keywords))

    tp = 100*t_cnt/10
    ap = 100*a_cnt/len(shorts) if shorts else 0
    diff = tp - ap
    top10_results[cat] = (tp, ap, diff, t_cnt, a_cnt)
    print(f"{cat:<15} {tp:>7.1f}% {ap:>7.1f}% {diff:>+7.1f}% {t_cnt:>6} {a_cnt:>8}")

# ============================================================
# STEP 8: TOP 10 titles
# ============================================================
print("\n" + "=" * 70)
print("STEP 8: TOP 10 SHORTS BY VIEWS")
print("=" * 70)

for i, v in enumerate(top10, 1):
    print(f"\n  {i}. [{v['view_count']:,} views]")
    print(f"     {v['title']}")
    print(f"     Duration: {v['duration_sec']}s | Likes: {v['like_count']:,} | Comments: {v['comment_count']:,}")

# ============================================================
# STEP 9: Best posting time analysis
# ============================================================
print("\n" + "=" * 70)
print("STEP 9: BEST POSTING TIME (for viral shorts)")
print("=" * 70)

from datetime import datetime

viral_by_hour = Counter()
viral_by_day = Counter()

for v in viral:
    dt = datetime.fromisoformat(v['published'].replace('Z', '+00:00'))
    h = dt.hour
    viral_by_hour[h] += 1

    # Convert UTC to HKT (UTC+8)
    hkt_h = (h + 8) % 24
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    viral_by_day[day_names[dt.weekday()]] += 1

print("Viral Shorts by hour (HKT):")
for h in range(24):
    cnt = viral_by_hour.get(h, 0)
    bar = '#' * cnt
    print(f"  {h:02d}:00 HKT | {cnt:3d} | {bar}")

best_h = viral_by_hour.most_common(1)[0][0] if viral_by_hour else 0
print(f"\nBest hour (HKT): {best_h}:00")

print("\nViral Shorts by day of week:")
for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
    cnt = viral_by_day.get(d, 0)
    bar = '#' * cnt
    print(f"  {d:4s} | {cnt:3d} | {bar}")

best_d = viral_by_day.most_common(1)[0][0] if viral_by_day else ''
print(f"\nBest day: {best_d}")

# ============================================================
# STEP 10: Title length analysis
# ============================================================
print("\n" + "=" * 70)
print("STEP 10: TITLE LENGTH ANALYSIS")
print("=" * 70)

title_lens = [len(v['title']) for v in shorts]
viral_title_lens = [len(v['title']) for v in viral]

print(f"Average title length (all shorts): {sum(title_lens)//len(title_lens):.0f} chars")
print(f"Average title length (viral): {sum(viral_title_lens)//len(viral_title_lens):.0f} chars")
print(f"Average title length (top 10): {sum(len(v['title']) for v in top10)//10:.0f} chars")

# ============================================================
# STEP 11: Engagement analysis
# ============================================================
print("\n" + "=" * 70)
print("STEP 11: ENGAGEMENT ANALYSIS (viral shorts)")
print("=" * 70)

engagement_rates = []
for v in viral:
    if v['view_count'] > 0:
        er = (v['like_count'] + v['comment_count']) / v['view_count'] * 100
        engagement_rates.append(er)

if engagement_rates:
    print(f"Average engagement rate (viral): {sum(engagement_rates)/len(engagement_rates):.2f}%")
    print(f"Max engagement rate: {max(engagement_rates):.2f}%")
    print(f"Min engagement rate: {min(engagement_rates):.2f}%")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY FOR KIZZOMBIE (@kizzombie)")
print("=" * 70)
print(f"Total Shorts analyzed: {len(shorts)}")
print(f"Viral (>1M): {len(viral)} ({100*len(viral)/len(shorts):.1f}%)")
print(f"Best hour (HKT): {best_h}:00")
print(f"Best day: {best_d}")

print("\nVIRAL FACTORS (diff = viral% - all%):")
for cat in sorted(viral_results, key=lambda x: viral_results[x][2], reverse=True):
    vp, ap, diff, vc, ac = viral_results[cat]
    sign = '+' if diff > 0 else ''
    print(f"  {cat:<15}: {sign}{diff:.1f}% ({vp:.0f}% viral vs {ap:.0f}% all)")

print("\nTOP 10 FACTORS (diff = top10% - all%):")
for cat in sorted(top10_results, key=lambda x: top10_results[x][2], reverse=True):
    tp, ap, diff, tc, ac = top10_results[cat]
    sign = '+' if diff > 0 else ''
    print(f"  {cat:<15}: {sign}{diff:.1f}% ({tp:.0f}% top10 vs {ap:.0f}% all)")
