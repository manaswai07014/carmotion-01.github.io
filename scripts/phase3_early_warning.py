#!/usr/bin/env python3
"""Phase 3: Early Warning + Gap Analysis + Unified Report"""
import urllib.request
import json
import re
from collections import Counter
from datetime import datetime, timedelta

API_KEY = 'AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM'

def yt_api(endpoint, params):
    base = 'https://www.googleapis.com/youtube/v3'
    p = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{base}/{endpoint}?{p}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_channel_info(handle):
    url = f'https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&forHandle={handle}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_all_videos(handle):
    ch = get_channel_info(handle)
    if not ch.get('items'):
        return [], 0
    item = ch['items'][0]
    uploads_id = item['contentDetails']['relatedPlaylists']['uploads']
    st = item['statistics']
    sub_count = int(st.get('subscriberCount', 0))

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
            dt_str = sn['publishedAt'].replace('Z', '+00:00')
            dt = datetime.fromisoformat(dt_str.replace('+00:00', ''))
            all_videos.append({
                'id': item['id'],
                'title': sn['title'],
                'published': sn['publishedAt'],
                'published_hkt': dt.strftime('%Y-%m-%d %H:%M HKT'),
                'view_count': int(st.get('viewCount', 0)),
                'like_count': int(st.get('likeCount', 0)),
                'comment_count': int(st.get('commentCount', 0)),
                'duration_sec': total_sec,
                'is_short': total_sec <= 60,
                'dt_obj': dt,
            })
    return all_videos, sub_count

# ============================================================
# FETCH DATA
# ============================================================
print("=" * 70)
print("PHASE 3: 早期預警 + 缺口分析 + 統一報告")
print("=" * 70)

print("\n📡 正在抓取 @kizzombie...")
kiz_videos, kiz_sub = get_all_videos('kizzombie')
kiz_shorts = [v for v in kiz_videos if v['is_short']]
kiz_viral = [v for v in kiz_shorts if v['view_count'] > 1_000_000]
print(f"   完成: {len(kiz_shorts)} Shorts, {kiz_sub:,} 訂閱")

print("\n📡 正在抓取 @motomorfosis...")
moto_videos, moto_sub = get_all_videos('motomorfosis')
moto_shorts = [v for v in moto_videos if v['is_short']]
moto_viral = [v for v in moto_shorts if v['view_count'] > 1_000_000]
print(f"   完成: {len(moto_shorts)} Shorts, {moto_sub:,} 訂閱")

# ============================================================
# TIME SETUP
# ============================================================
now_utc = datetime.utcnow()

# ============================================================
# BRAND GAP ANALYSIS
# ============================================================
CAR_BRANDS = {
    'Bugatti': ['bugatti'],
    'Ferrari': ['ferrari'],
    'Porsche': ['porsche'],
    'Lamborghini': ['lamborghini'],
    'BMW': ['bmw'],
    'Mercedes': ['mercedes'],
    'Audi': ['audi'],
    'Honda': ['honda'],
    'Toyota': ['toyota'],
    'Nissan': ['nissan'],
    'Mazda': ['mazda'],
    'Mitsubishi': ['mitsubishi'],
    'Subaru': ['subaru'],
    'Ford': ['ford'],
    'Volkswagen': ['volkswagen', 'vw '],
    'Land Rover': ['land rover'],
    'Jaguar': ['jaguar'],
    'Maserati': ['maserati'],
    'Bentley': ['bentley'],
    'Rolls-Royce': ['rolls'],
    'Aston Martin': ['aston martin'],
    'Lexus': ['lexus'],
    'Ducati': ['ducati'],
    'Kawasaki': ['kawasaki'],
    'Yamaha': ['yamaha'],
    'Suzuki': ['suzuki'],
    'Harley-Davidson': ['harley'],
    'Scania': ['scania'],
    'John Deere': ['john deere'],
    'UAZ': ['uaz'],
    'Peugeot': ['peugeot'],
    'Royal Enfield': ['royal enfield'],
    'Dodge': ['dodge'],
    'Chevrolet': ['chevrolet'],
    'Jeep': ['jeep'],
    'McLaren': ['mclaren'],
}

def count_brand(shorts, brands_dict):
    counts = {}
    for brand, keywords in brands_dict.items():
        cnt = sum(1 for s in shorts if any(k in s['title'].lower() for k in keywords))
        counts[brand] = cnt
    return counts

kiz_brands = count_brand(kiz_shorts, CAR_BRANDS)
moto_brands = count_brand(moto_shorts, CAR_BRANDS)

# ============================================================
# EARLY WARNING
# ============================================================
def recent_shorts(shorts, days):
    return [s for s in shorts if (now_utc - s['dt_obj']) < timedelta(days=days)]

kiz_recent7 = recent_shorts(kiz_shorts, 7)
kiz_recent30 = recent_shorts(kiz_shorts, 30)
moto_recent7 = recent_shorts(moto_shorts, 7)
moto_recent30 = recent_shorts(moto_shorts, 30)

kiz_new_viral = [s for s in kiz_recent7 if s['view_count'] > 1_000_000]
moto_new_viral = [s for s in moto_recent7 if s['view_count'] > 1_000_000]

# ============================================================
# PRINT: EARLY WARNING
# ============================================================
print("\n" + "=" * 70)
print("🚨 早期預警：新片仔追蹤（過去 7 天）")
print("=" * 70)

print(f"\n📺 @kizzombie — 過去 7 天新片: {len(kiz_recent7)} 條")
if kiz_recent7:
    for s in sorted(kiz_recent7, key=lambda x: x['dt_obj'], reverse=True):
        days_ago = (now_utc - s['dt_obj']).days
        viral_tag = '🔥' if s['view_count'] > 1_000_000 else ''
        print(f"   [{days_ago}d] {s['title'][:55]} {viral_tag}")
        print(f"       {s['view_count']:,} views | {s['like_count']:,} likes")
else:
    print("   （過去7天冇新片）")

print(f"\n📺 @motomorfosis — 過去 7 天新片: {len(moto_recent7)} 條")
if moto_recent7:
    for s in sorted(moto_recent7, key=lambda x: x['dt_obj'], reverse=True):
        days_ago = (now_utc - s['dt_obj']).days
        viral_tag = '🔥' if s['view_count'] > 1_000_000 else ''
        print(f"   [{days_ago}d] {s['title'][:55]} {viral_tag}")
        print(f"       {s['view_count']:,} views | {s['like_count']:,} likes")
else:
    print("   （過去7天冇新片）")

# ============================================================
# PRINT: GAP ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("🔍 缺口分析：品牌覆蓋")
print("=" * 70)

print("\n🔴 極高機會（兩台總覆蓋 <5 條）：")
gap_extreme = []
for brand, keywords in CAR_BRANDS.items():
    kc = kiz_brands.get(brand, 0)
    mc = moto_brands.get(brand, 0)
    total = kc + mc
    if total < 5:
        gap_extreme.append((brand, kc, mc))
for brand, kc, mc in sorted(gap_extreme, key=lambda x: x[1]+x[2]):
    print(f"   {brand:<18} @kizzombie: {kc:3d}  @motomorfosis: {mc:3d}  總: {kc+mc}")

print("\n🟡 高機會（兩台總覆蓋 5-20 條）：")
gap_high = []
for brand, keywords in CAR_BRANDS.items():
    kc = kiz_brands.get(brand, 0)
    mc = moto_brands.get(brand, 0)
    total = kc + mc
    if 5 <= total < 20:
        gap_high.append((brand, kc, mc))
for brand, kc, mc in sorted(gap_high, key=lambda x: x[1]+x[2]):
    print(f"   {brand:<18} @kizzombie: {kc:3d}  @motomorfosis: {mc:3d}  總: {kc+mc}")

# ============================================================
# OPPORTUNITY MATRIX
# ============================================================
print("\n" + "=" * 70)
print("🎯 機會矩陣：老闆 Bugatti 頻道切入點")
print("=" * 70)

top_opps = [
    ('Bugatti', kiz_brands.get('Bugatti', 0), moto_brands.get('Bugatti', 0)),
    ('Ferrari', kiz_brands.get('Ferrari', 0), moto_brands.get('Ferrari', 0)),
    ('Porsche', kiz_brands.get('Porsche', 0), moto_brands.get('Porsche', 0)),
    ('McLaren', kiz_brands.get('McLaren', 0), moto_brands.get('McLaren', 0)),
    ('Aston Martin', kiz_brands.get('Aston Martin', 0), moto_brands.get('Aston Martin', 0)),
    ('Lamborghini', kiz_brands.get('Lamborghini', 0), moto_brands.get('Lamborghini', 0)),
]
print("\n超級藍海（幾乎冇人做）：")
for brand, kc, mc in top_opps:
    total = kc + mc
    status = '🟢' if total < 5 else '🟡' if total < 20 else '🔴'
    print(f"   {status} {brand}: @kizzombie {kc}條, @motomorfosis {mc}條 (總{total})")

# ============================================================
# UNIFIED SUMMARY TABLE
# ============================================================
print("\n" + "=" * 70)
print("📊 兩台統一對比總結")
print("=" * 70)

kiz_avg30 = sum(s['view_count'] for s in kiz_recent30) / len(kiz_recent30) if kiz_recent30 else 0
moto_avg30 = sum(s['view_count'] for s in moto_recent30) / len(moto_recent30) if moto_recent30 else 0

kiz_viral_pct = 100*len(kiz_viral)/len(kiz_shorts) if kiz_shorts else 0
moto_viral_pct = 100*len(moto_viral)/len(moto_shorts) if moto_shorts else 0

print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                     兩台對比總結                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  指標                  @kizzombie       @motomorfosis            ║
╠══════════════════════════════════════════════════════════════════╣
║  Shorts 總數            {len(kiz_shorts):>6}            {len(moto_shorts):>6}                      ║
║  訂閱                  {kiz_sub:>9,}      {moto_sub:>9,}                   ║
║  Viral (>1M)            {len(kiz_viral):>6} ({kiz_viral_pct:.1f}%)      {len(moto_viral):>6} ({moto_viral_pct:.1f}%)               ║
║  過去30天發片           {len(kiz_recent30):>6}            {len(moto_recent30):>6}                      ║
║  過去30天平均觀看       {kiz_avg30:>10,.0f}    {moto_avg30:>10,.0f}                ║
║  過去7天新片            {len(kiz_recent7):>6}             {len(moto_recent7):>6}                      ║
║  過去7天新viral         {len(kiz_new_viral):>6}               {len(moto_new_viral):>6}                      ║
╚══════════════════════════════════════════════════════════════════╝
""")

print("\n🎯 老闆嘅 Bugatti 頻道建議：")
print("   ✅ Bugatti 幾乎冇競爭 — 極大藍海")
print("   ✅ Ferrari、Porsche、McLaren 同樣極少覆蓋")
print("   ✅ 用 @kizzombie 爆片公式：[品牌] + Evolution + [年份範圍]")
print("   ✅ 建議標題格式：Bugatti Chiron Evolution (2016-2026)")
print("   ✅ 最佳發片時間：14:00-15:00 HKT")
print("   ✅ 標題長度目標：40字以內")
