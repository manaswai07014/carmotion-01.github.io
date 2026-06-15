#!/usr/bin/env python3
"""@kizzombie 完整報告 - 中文版"""
import urllib.request
import json
import re
from collections import Counter
from datetime import datetime

API_KEY = 'AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM'
CHANNEL_ID = 'UC2IRZdo5HP4IjzuAjlsLjOg'

def yt_api(endpoint, params):
    base = 'https://www.googleapis.com/youtube/v3'
    p = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{base}/{endpoint}?{p}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Channel info
ch = yt_api('channels', {'part': 'snippet,statistics,contentDetails', 'id': CHANNEL_ID})
item = ch['items'][0]
sn = item['snippet']
st = item['statistics']
uploads_id = item['contentDetails']['relatedPlaylists']['uploads']

# Get all video IDs
all_video_ids = []
page_token = None
while True:
    pl_params = {'part': 'contentDetails', 'playlistId': uploads_id, 'maxResults': 50}
    if page_token:
        pl_params['pageToken'] = page_token
    pl = yt_api('playlistItems', pl_params)
    items = pl.get('items', [])
    video_ids = [it['contentDetails']['videoId'] for it in items if it['contentDetails'].get('videoId')]
    all_video_ids.extend(video_ids)
    page_token = pl.get('nextPageToken')
    if not page_token:
        break

# Get video details
all_videos = []
for i in range(0, len(all_video_ids), 50):
    batch = all_video_ids[i:i+50]
    ids_str = ','.join(batch)
    vd = yt_api('videos', {'part': 'snippet,statistics,contentDetails', 'id': ids_str})
    for item in vd.get('items', []):
        sn = item['snippet']
        st = item['statistics']
        cd = item['contentDetails']
        duration = cd.get('duration', 'PT0S')
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            s = int(match.group(3) or 0)
            total_sec = h*3600 + m*60 + s
        else:
            total_sec = 0
        is_short = total_sec <= 60
        dt = datetime.fromisoformat(sn['publishedAt'].replace('Z', '+00:00'))
        all_videos.append({
            'id': item['id'],
            'title': sn['title'],
            'published': sn['publishedAt'],
            'published_hkt': dt.strftime('%Y-%m-%d %H:%M HKT'),
            'view_count': int(st.get('viewCount', 0)),
            'like_count': int(st.get('likeCount', 0)),
            'comment_count': int(st.get('commentCount', 0)),
            'duration_sec': total_sec,
            'is_short': is_short,
        })

shorts = [v for v in all_videos if v['is_short']]
viral = [v for v in shorts if v['view_count'] > 1_000_000]

# Sort by views
top10_views = sorted(shorts, key=lambda x: x['view_count'], reverse=True)[:10]

# Sort by published date (latest first)
latest10 = sorted(shorts, key=lambda x: x['published'], reverse=True)[:10]

print("=" * 70)
print("最新 10 條 SHORTS（按發布時間）")
print("=" * 70)
for i, v in enumerate(latest10, 1):
    er = (v['like_count'] + v['comment_count']) / v['view_count'] * 100 if v['view_count'] > 0 else 0
    print(f"\n【{i}】{v['title']}")
    print(f"   發布：{v['published_hkt']}")
    print(f"   觀看：{v['view_count']:,}｜点赞：{v['like_count']:,}｜留言：{v['comment_count']:,}")
    print(f"   互動率：{er:.2f}%｜時長：{v['duration_sec']}秒")
    print(f"   連結：https://youtube.com/shorts/{v['id']}")

print("\n" + "=" * 70)
print("最高觀看 10 條 SHORTS（按觀看次數）")
print("=" * 70)
for i, v in enumerate(top10_views, 1):
    er = (v['like_count'] + v['comment_count']) / v['view_count'] * 100 if v['view_count'] > 0 else 0
    print(f"\n【{i}】{v['title']}")
    print(f"   觀看：{v['view_count']:,}｜点赞：{v['like_count']:,}｜留言：{v['comment_count']:,}")
    print(f"   互動率：{er:.2f}%｜時長：{v['duration_sec']}秒")
    print(f"   發布：{v['published_hkt']}")
    print(f"   連結：https://youtube.com/shorts/{v['id']}")
