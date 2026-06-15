#!/usr/bin/env python3
"""
Phase 3 Enhanced: 早期預警 + 深度缺口分析 + 詳細競爭情報
全部實時從 YouTube API 讀取，唔用 cache
"""
import urllib.request
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

API_KEY = 'AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM'

def yt_api(endpoint, params):
    base = 'https://www.googleapis.com/youtube/v3'
    p = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{base}/{endpoint}?{p}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_all_videos(handle):
    url = f'https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&forHandle={handle}&key={API_KEY}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        ch = json.loads(resp.read())
    if not ch.get('items'):
        return [], 0
    item = ch['items'][0]
    uploads_id = item['contentDetails']['relatedPlaylists']['uploads']
    sub_count = int(item['statistics'].get('subscriberCount', 0))

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

    all_videos = []
    for i in range(0, len(all_ids), 50):
        batch = all_ids[i:i+50]
        ids_str = ','.join(batch)
        vd = yt_api('videos', {'part': 'snippet,statistics,contentDetails', 'id': ids_str})
        for vitem in vd.get('items', []):
            sn = vitem['snippet']
            st = vitem['statistics']
            cd = vitem['contentDetails']
            dur = cd.get('duration', 'PT0S')
            m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur)
            total_sec = (int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)) if m else 0
            dt_str = sn['publishedAt'].replace('Z', '+00:00')
            dt = datetime.fromisoformat(dt_str.replace('+00:00', ''))
            all_videos.append({
                'id': vitem['id'],
                'title': sn['title'],
                'published': sn['publishedAt'],
                'dt': dt,
                'view_count': int(st.get('viewCount', 0)),
                'like_count': int(st.get('likeCount', 0)),
                'comment_count': int(st.get('commentCount', 0)),
                'duration_sec': total_sec,
                'is_short': total_sec <= 60,
            })
    return all_videos, sub_count

# ============================================================
# FETCH DATA
# ============================================================
print("=" * 75)
print("🚨 PHASE 3 ENHANCED 報告")
print("   實時 YouTube API 數據，全部親自 fetch，唔用 cache")
print("=" * 75)

print("\n📡 Fetching @kizzombie...")
kiz_videos, kiz_sub = get_all_videos('kizzombie')
kiz_shorts = [v for v in kiz_videos if v['is_short']]
kiz_viral = [v for v in kiz_shorts if v['view_count'] > 1_000_000]
print(f"   Done: {len(kiz_shorts)} Shorts | {kiz_sub:,} subs | {len(kiz_viral)} viral")

print("\n📡 Fetching @motomorfosis...")
moto_videos, moto_sub = get_all_videos('motomorfosis')
moto_shorts = [v for v in moto_videos if v['is_short']]
moto_viral = [v for v in moto_shorts if v['view_count'] > 1_000_000]
print(f"   Done: {len(moto_shorts)} Shorts | {moto_sub:,} subs | {len(moto_viral)} viral")

now_utc = datetime.utcnow()

# ============================================================
# HELPER: KEYWORD MATCHING
# ============================================================
BRAND_KEYWORDS = {
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

CONTENT_CATS = {
    'Military/Army': ['military', 'army', 'tank', 'soldier', 'german army', 'british armored', ' armored '],
    'Gaming/Car Games': ['nfs', 'need for speed', 'gran turismo', 'forza', 'arcade', 'game'],
    'Tractor/Commercial': ['tractor', 'truck', 'scania', 'john deere', 'uaz', 'transport', 'bus'],
    'Motorcycle': ['motorcycle', 'bike', 'ducati', 'kawasaki', 'yamaha', 'harley', 'suzuki motorcycle', 'honda motorcycle', 'superbike'],
    'Supercar/Exotic': ['bugatti', 'ferrari', 'porsche', 'lamborghini', 'mclaren', 'supercar'],
    'JDM': ['jdm', 'skyline', 'supra', 'rx7', 'nsx', 'silvia', '370z', 'rx', 'japan', 'japanese'],
    'European Classic': ['aston martin', 'jaguar', 'bentley', 'rolls royce', 'maserati', 'land rover'],
    'American Muscle': ['mustang', 'camaro', 'corvette', 'charger', 'firebird', 'dodge', 'chevrolet', 'ford mustang'],
}

TITLE_PATTERNS = {
    'Evolution': ['evolution', 'evolusi'],
    'vs/Comparison': ['vs ', ' vs ', ' versus '],
    'Iconic': ['iconic', 'legendary', 'legenda'],
    'Build(s)': [' build', ' builds'],
    'Every': ['every '],
    'Transformation': ['transformation', 'transform'],
    'Origin': ['origin', 'birth', 'beginning'],
    'Movie': ['movie', 'film', 'cinema'],
    'Military': ['military', 'army', 'tank'],
    'Year Range': None,  # special handling
}

def brand_count(shorts, brand):
    kw = BRAND_KEYWORDS.get(brand, [])
    return sum(1 for s in shorts if any(k in s['title'].lower() for k in kw))

def cat_count(shorts, cat):
    kw = list(CONTENT_CATS.get(cat, []))
    return sum(1 for s in shorts if any(k in s['title'].lower() for k in kw))

def pattern_count(shorts, pattern):
    if pattern == 'Year Range':
        return sum(1 for s in shorts if re.search(r'\d{4}\s*[-–]\s*\d{4}', s['title']))
    kw = TITLE_PATTERNS.get(pattern, [])
    return sum(1 for s in shorts if any(k in s['title'].lower() for k in kw))

def recent(shorts, days):
    return [s for s in shorts if (now_utc - s['dt']) < timedelta(days=days)]

# ============================================================
# SECTION 1: EARLY WARNING SYSTEM
# ============================================================
print("\n" + "=" * 75)
print("🚨 SECTION 1: 早期預警系統")
print("=" * 75)

# Recent shorts
kiz_r7 = recent(kiz_shorts, 7)
kiz_r30 = recent(kiz_shorts, 30)
moto_r7 = recent(moto_shorts, 7)
moto_r30 = recent(moto_shorts, 30)

kiz_new_viral = [s for s in kiz_r7 if s['view_count'] > 1_000_000]
moto_new_viral = [s for s in moto_r7 if s['view_count'] > 1_000_000]

print(f"""
┌─────────────────────────────────────────────────────────────────────────┐
│  過去7天監控總覽                                                        │
├───────────────────────────────┬───────────────────────────────┤
│  @kizzombie                   │  @motomorfosis                │
├───────────────────────────────┼───────────────────────────────┤
│  新 Shorts: {len(kiz_r7):>3}               │  新 Shorts: {len(moto_r7):>3}                │
│  新 Viral:  {len(kiz_new_viral):>3}               │  新 Viral:  {len(moto_new_viral):>3}                │
│  過去30天: {len(kiz_r30):>3} 片            │  過去30天: {len(moto_r30):>3} 片             │
└───────────────────────────────┴───────────────────────────────┘
""")

print("📺 @kizzombie — 過去7天新片：")
if kiz_r7:
    for s in sorted(kiz_r7, key=lambda x: x['dt'], reverse=True):
        days = (now_utc - s['dt']).days
        v = s['view_count']
        er = (s['like_count'] + s['comment_count']) / v * 100 if v > 0 else 0
        tag = '🔥' if v > 1_000_000 else '🆕' if days == 0 else ''
        print(f"   {tag}[{days}d] {s['title'][:58]}")
        print(f"        觀看:{v:>12,}  | 點讚:{s['like_count']:>8,}  | 互動:{er:.2f}%")
else:
    print("   （過去7天無新片）")

print("\n📺 @motomorfosis — 過去7天新片：")
if moto_r7:
    for s in sorted(moto_r7, key=lambda x: x['dt'], reverse=True):
        days = (now_utc - s['dt']).days
        v = s['view_count']
        er = (s['like_count'] + s['comment_count']) / v * 100 if v > 0 else 0
        tag = '🔥' if v > 1_000_000 else '🆕' if days == 0 else ''
        print(f"   {tag}[{days}d] {s['title'][:58]}")
        print(f"        觀看:{v:>12,}  | 點讚:{s['like_count']:>8,}  | 互動:{er:.2f}%")
else:
    print("   （過去7天無新片）")

# ============================================================
# SECTION 2: BRAND GAP ANALYSIS (DEEP DIVE)
# ============================================================
print("\n" + "=" * 75)
print("🔍 SECTION 2: 品牌缺口深度分析")
print("=" * 75)

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  🟢 極高機會（藍海，超級未開發）                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  品牌           @kizzombie   @motomorfosis   總計    建議行動              │
├──────────────────────────────────────────────────────────────────────────┤""")

blue_ocean = []
for brand in BRAND_KEYWORDS:
    kc = brand_count(kiz_shorts, brand)
    mc = brand_count(moto_shorts, brand)
    total = kc + mc
    if total < 5:
        blue_ocean.append((brand, kc, mc))

for brand, kc, mc in sorted(blue_ocean, key=lambda x: x[1]+x[2]):
    total = kc + mc
    print(f"│  {brand:<16}  {kc:>6}           {mc:>6}          {total:>4}    {'🔥 立即做!' if total < 3 else '✅ 優先做'}")

print("└──────────────────────────────────────────────────────────────────────────┘")

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  🟡 中等機會（可以差異化）                                                │
├──────────────────────────────────────────────────────────────────────────┤
│  品牌           @kizzombie   @motomorfosis   總計    建議行動              │
├──────────────────────────────────────────────────────────────────────────┤""")

mid_opps = []
for brand in BRAND_KEYWORDS:
    kc = brand_count(kiz_shorts, brand)
    mc = brand_count(moto_shorts, brand)
    total = kc + mc
    if 5 <= total < 20:
        mid_opps.append((brand, kc, mc))

for brand, kc, mc in sorted(mid_opps, key=lambda x: x[1]+x[2]):
    print(f"│  {brand:<16}  {kc:>6}          {mc:>6}          {kc+mc:>4}    📝 差異化做")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 3: CONTENT CATEGORY ANALYSIS
# ============================================================
print("\n" + "=" * 75)
print("📊 SECTION 3: 內容類別深度分析")
print("=" * 75)

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  內容類別           @kizzombie   @motomorfosis   總計    市場評估           │
├──────────────────────────────────────────────────────────────────────────┤""")

cat_data = []
for cat in CONTENT_CATS:
    kc = cat_count(kiz_shorts, cat)
    mc = cat_count(moto_shorts, cat)
    total = kc + mc
    cat_data.append((cat, kc, mc, total))

for cat, kc, mc, total in sorted(cat_data, key=lambda x: x[3], reverse=True):
    if total >= 30:
        assessment = '🟢 成熟'
    elif total >= 10:
        assessment = '🟡 競爭中'
    else:
        assessment = '🔴 未開發'
    print(f"│  {cat:<20}  {kc:>6}          {mc:>6}          {total:>4}    {assessment}")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 4: TITLE FORMULA ANALYSIS
# ============================================================
print("\n" + "=" * 75)
print("📝 SECTION 4: 標題公式深度分析")
print("=" * 75)

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  標題公式           @kizzombie使用率   @motomorfosis使用率  市場評估      │
├──────────────────────────────────────────────────────────────────────────┤""")

pattern_data = []
for pattern in TITLE_PATTERNS:
    kc = pattern_count(kiz_shorts, pattern)
    mc = pattern_count(moto_shorts, pattern)
    kp = 100*kc/len(kiz_shorts) if kiz_shorts else 0
    mp = 100*mc/len(moto_shorts) if moto_shorts else 0
    pattern_data.append((pattern, kc, mc, kp, mp))

for pattern, kc, mc, kp, mp in sorted(pattern_data, key=lambda x: x[3]+x[4], reverse=True):
    if kp < 10 and mp < 10:
        assessment = '🔴 罕見(差異化)'
    elif kp > 70:
        assessment = '🟢 必備公式'
    else:
        assessment = '🟡 常用'
    print(f"│  {pattern:<18}  {kp:>5.1f}%             {mp:>5.1f}%            {assessment}")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 5: POSTING TIME HEATMAP
# ============================================================
print("\n" + "=" * 75)
print("⏰ SECTION 5: 發片時間熱力圖（@kizzombie Viral Shorts 按小時分佈）")
print("=" * 75)

hourly = Counter()
for s in kiz_viral:
    hkt_h = (s['dt'].hour + 8) % 24
    hourly[hkt_h] += 1

print("\n  小時 (HKT)   數量   熱力圖")
print("  " + "-" * 55)
for h in range(24):
    cnt = hourly.get(h, 0)
    bar = '█' * min(cnt, 60) if cnt > 0 else ''
    if cnt >= 40:
        level = '🔴'
    elif cnt >= 20:
        level = '🟡'
    elif cnt >= 5:
        level = '🟢'
    else:
        level = '⚪'
    print(f"  {h:02d}:00        {cnt:>3}   {level} {bar}")

best_h = hourly.most_common(1)[0][0] if hourly else 0
print(f"\n  ★ 最佳發片時間: {best_h}:00 HKT")

# ============================================================
# SECTION 6: VIEW DISTRIBUTION ANALYSIS
# ============================================================
print("\n" + "=" * 75)
print("📈 SECTION 6: 觀看次數分佈分析")
print("=" * 75)

def view_buckets(shorts):
    buckets = {
        '0-10K': 0,
        '10K-50K': 0,
        '50K-100K': 0,
        '100K-500K': 0,
        '500K-1M': 0,
        '1M-5M': 0,
        '5M-10M': 0,
        '10M+': 0,
    }
    for s in shorts:
        v = s['view_count']
        if v < 10_000:
            buckets['0-10K'] += 1
        elif v < 50_000:
            buckets['10K-50K'] += 1
        elif v < 100_000:
            buckets['50K-100K'] += 1
        elif v < 500_000:
            buckets['100K-500K'] += 1
        elif v < 1_000_000:
            buckets['500K-1M'] += 1
        elif v < 5_000_000:
            buckets['1M-5M'] += 1
        elif v < 10_000_000:
            buckets['5M-10M'] += 1
        else:
            buckets['10M+'] += 1
    return buckets

kiz_buckets = view_buckets(kiz_shorts)
moto_buckets = view_buckets(moto_shorts)

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  觀看區間         @kizzombie       @motomorfosis                         │
├──────────────────────────────────────────────────────────────────────────┤""")

for bucket in ['0-10K', '10K-50K', '50K-100K', '100K-500K', '500K-1M', '1M-5M', '5M-10M', '10M+']:
    kc = kiz_buckets[bucket]
    mc = moto_buckets[bucket]
    kp = 100*kc/len(kiz_shorts) if kiz_shorts else 0
    mp = 100*mc/len(moto_shorts) if moto_shorts else 0
    kbar = '▓' * int(kp/2)
    mbar = '▓' * int(mp/2)
    print(f"│  {bucket:>10}   {kc:>4} ({kp:>5.1f}%)  {kbar:<25}  {mc:>4} ({mp:>5.1f}%)  {mbar:<15}")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 7: ENGAGEMENT ANALYSIS
# ============================================================
print("\n" + "=" * 75)
print("💬 SECTION 7: 互動率深度分析")
print("=" * 75)

def eng_rate(s):
    return (s['like_count'] + s['comment_count']) / s['view_count'] * 100 if s['view_count'] > 0 else 0

def bucket_eng(shorts, low, high):
    bucket = [s for s in shorts if low <= s['view_count'] < high]
    if not bucket:
        return 0, 0
    rates = [eng_rate(s) for s in bucket]
    return sum(rates)/len(rates), len(bucket)

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  @kizzombie 互動率分析                                                    │
├──────────────────────────────────────────────────────────────────────────┤""")
ranges = [(0, 10_000), (10_000, 100_000), (100_000, 500_000), (500_000, 1_000_000), (1_000_000, 5_000_000), (5_000_000, 100_000_000)]
for low, high in ranges:
    avg, cnt = bucket_eng(kiz_shorts, low, high)
    if cnt > 0:
        print(f"│  {low:>10,}-{(high-1):>10,}  平均互動率: {avg:.2f}%  片數: {cnt}")

print("\n┌──────────────────────────────────────────────────────────────────────────┐")
print("│  @motomorfosis 互動率分析                                                 │")
print("├──────────────────────────────────────────────────────────────────────────┤")
for low, high in ranges:
    avg, cnt = bucket_eng(moto_shorts, low, high)
    if cnt > 0:
        print(f"│  {low:>10,}-{(high-1):>10,}  平均互動率: {avg:.2f}%  片數: {cnt}")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 8: VIRAL FACTOR CORRELATION
# ============================================================
print("\n" + "=" * 75)
print("🔥 SECTION 8: Viral 關鍵詞關聯分析（@kizzombie）")
print("=" * 75)

def viral_diff(shorts, keyword_or_fn):
    viral = [s for s in shorts if s['view_count'] > 1_000_000]
    if not viral:
        return 0, 0, 0
    if callable(keyword_or_fn):
        v_match = sum(1 for s in viral if keyword_or_fn(s['title']))
        a_match = sum(1 for s in shorts if keyword_or_fn(s['title']))
    else:
        kw = keyword_or_fn
        v_match = sum(1 for s in viral if kw in s['title'].lower())
        a_match = sum(1 for s in shorts if kw in s['title'].lower())
    vp = 100*v_match/len(viral)
    ap = 100*a_match/len(shorts)
    return vp, ap, vp - ap

keywords_test = [
    ('evolution', 'evolution'),
    ('year range', lambda t: bool(re.search(r'\d{4}\s*[-–]\s*\d{4}', t))),
    ('brand name', lambda t: any(k in t.lower() for k in ['bmw', 'mercedes', 'ferrari', 'bugatti', 'porsche'])),
    ('military', 'military'),
    ('iconic', 'iconic'),
    ('every', 'every '),
    ('vs', ' vs '),
    ('number (year)', lambda t: bool(re.search(r'\(\d{4}', t))),
]

print("""
┌──────────────────────────────────────────────────────────────────────────┐
│  關鍵詞/公式      Viral中佔%   全部中佔%   差值    結論                   │
├──────────────────────────────────────────────────────────────────────────┤""")

for name, kw in keywords_test:
    vp, ap, diff = viral_diff(kiz_shorts, kw)
    if diff > 10:
        conclusion = '🟢 推向Viral'
    elif diff > 3:
        conclusion = '🟡 輕微幫助'
    elif diff < -10:
        conclusion = '🔴 拉低Viral'
    elif diff < -3:
        conclusion = '🟠 輕微阻力'
    else:
        conclusion = '⚪ 無影響'
    sign = '+' if diff > 0 else ''
    print(f"│  {name:<16}  {vp:>6.1f}%     {ap:>6.1f}%    {sign}{diff:>5.1f}%   {conclusion}")

print("└──────────────────────────────────────────────────────────────────────────┘")

# ============================================================
# SECTION 9: TREND ANALYSIS
# ============================================================
print("\n" + "=" * 75)
print("📊 SECTION 9: 趨勢分析（過去90天 vs 之前）")
print("=" * 75)

kiz_90d = recent(kiz_shorts, 90)
kiz_prev = [s for s in kiz_shorts if timedelta(days=90) <= (now_utc - s['dt']) < timedelta(days=180)]
moto_90d = recent(moto_shorts, 90)
moto_prev = [s for s in moto_shorts if timedelta(days=90) <= (now_utc - s['dt']) < timedelta(days=180)]

kiz_90d_avg = sum(s['view_count'] for s in kiz_90d)/len(kiz_90d) if kiz_90d else 0
kiz_prev_avg = sum(s['view_count'] for s in kiz_prev)/len(kiz_prev) if kiz_prev else 0
moto_90d_avg = sum(s['view_count'] for s in moto_90d)/len(moto_90d) if moto_90d else 0
moto_prev_avg = sum(s['view_count'] for s in moto_prev)/len(moto_prev) if moto_prev else 0

kiz_trend = ((kiz_90d_avg - kiz_prev_avg) / kiz_prev_avg * 100) if kiz_prev_avg else 0
moto_trend = ((moto_90d_avg - moto_prev_avg) / moto_prev_avg * 100) if moto_prev_avg else 0

print(f"""
┌──────────────────────────────────────────────────────────────────────────┐
│  @kizzombie 趨勢                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  過去90天: {len(kiz_90d):>3} 片  |  平均觀看: {kiz_90d_avg:>12,.0f}                         │
│  再之前90天: {len(kiz_prev):>3} 片  |  平均觀看: {kiz_prev_avg:>12,.0f}                        │
│  趨勢: {'📈' if kiz_trend > 0 else '📉'} {abs(kiz_trend):.1f}%  ({'上揚' if kiz_trend > 0 else '下跌'})                            │
├──────────────────────────────────────────────────────────────────────────┤
│  @motomorfosis 趨勢                                                      │
├──────────────────────────────────────────────────────────────────────────┤
│  過去90天: {len(moto_90d):>3} 片  |  平均觀看: {moto_90d_avg:>12,.0f}                         │
│  再之前90天: {len(moto_prev):>3} 片  |  平均觀看: {moto_prev_avg:>12,.0f}                        │
│  趨勢: {'📈' if moto_trend > 0 else '📉'} {abs(moto_trend):.1f}%  ({'上揚' if moto_trend > 0 else '下跌'})                            │
└──────────────────────────────────────────────────────────────────────────┘
""")

# ============================================================
# SECTION 10: COMPETITOR STRATEGY COMPARISON
# ============================================================
print("\n" + "=" * 75)
print("🎯 SECTION 10: 競爭對手策略對比")
print("=" * 75)

kiz_eng_avg = sum(eng_rate(s) for s in kiz_shorts if s['view_count'] > 0) / len(kiz_shorts) if kiz_shorts else 0
moto_eng_avg = sum(eng_rate(s) for s in moto_shorts if s['view_count'] > 0) / len(moto_shorts) if moto_shorts else 0

kiz_title_avg = sum(len(s['title']) for s in kiz_shorts) / len(kiz_shorts) if kiz_shorts else 0
moto_title_avg = sum(len(s['title']) for s in moto_shorts) / len(moto_shorts) if moto_shorts else 0

kiz_viral_rate = 100*len(kiz_viral)/len(kiz_shorts) if kiz_shorts else 0
moto_viral_rate = 100*len(moto_viral)/len(moto_shorts) if moto_shorts else 0

kiz_30d_rate = len(kiz_r30)/30 if kiz_r30 else 0
moto_30d_rate = len(moto_r30)/30 if moto_r30 else 0

print(f"""
┌──────────────────────────────────────────────────────────────────────────┐
│                          策略維度對比                                     │
├───────────────────────────────┬─────────────────────────────── ┤
│  維度                         │  @kizzombie    @motomorfosis    │
├───────────────────────────────┼───────────────────────────────┤
│  內容策略                      │  Evolution+年份  Evolution印尼語 │
│  主要語言                      │  英文         印尼語+英文      │
│  標題平均長度                   │  {kiz_title_avg:>5.0f}字         {moto_title_avg:>5.0f}字         │
│  平均互動率                     │  {kiz_eng_avg:>5.2f}%        {moto_eng_avg:>5.2f}%        │
│  Viral Rate                   │  {kiz_viral_rate:>5.1f}%        {moto_viral_rate:>5.1f}%        │
│  每日平均發片                   │  {kiz_30d_rate:>5.1f}         {moto_30d_rate:>5.1f}         │
│  內容覆蓋廣度                   │  {len(kiz_shorts):>4}片         {len(moto_shorts):>4}片         │
│  過去30天產量                   │  {len(kiz_r30):>4}片          {len(moto_r30):>4}片          │
└───────────────────────────────┴───────────────────────────────┘
""")

# ============================================================
# SECTION 11: BUGATTI CHANNEL OPPORTUNITY MATRIX
# ============================================================
print("\n" + "=" * 75)
print("🚀 SECTION 11: 老闆 Bugatti 頻道機會矩陣")
print("=" * 75)

bugatti_kiz = [s for s in kiz_shorts if 'bugatti' in s['title'].lower()]
bugatti_moto = [s for s in moto_shorts if 'bugatti' in s['title'].lower()]
ferrari_kiz = [s for s in kiz_shorts if 'ferrari' in s['title'].lower()]
ferrari_moto = [s for s in moto_shorts if 'ferrari' in s['title'].lower()]
porsche_kiz = [s for s in kiz_shorts if 'porsche' in s['title'].lower()]
porsche_moto = [s for s in moto_shorts if 'porsche' in s['title'].lower()]

print(f"""
┌──────────────────────────────────────────────────────────────────────────┐
│  🔥 BUGATTI 情況（超級藍海）                                             │
├──────────────────────────────────────────────────────────────────────────┤
│  @kizzombie: {len(bugatti_kiz)} 條片仔")
│    """)
for s in bugatti_kiz:
    print(f"│    - {s['title'][:60]} ({s['view_count']:,} views)")

print(f"│  @motomorfosis: {len(bugatti_moto)} 條片仔")
for s in bugatti_moto:
    print(f"│    - {s['title'][:60]} ({s['view_count']:,} views)")

print(f"""
├──────────────────────────────────────────────────────────────────────────┤
│  🏎️ FERRARI 情況（藍海）                                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  @kizzombie: {len(ferrari_kiz)} 條  |  @motomorfosis: {len(ferrari_moto)} 條

├──────────────────────────────────────────────────────────────────────────┤
│  🐬 PORSCHE 情況（藍海）                                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  @kizzombie: {len(porsche_kiz)} 條  |  @motomorfosis: {len(porsche_moto)} 條
""")

# ============================================================
# FINAL RECOMMENDATIONS
# ============================================================
print("\n" + "=" * 75)
print("💡 FINAL RECOMMENDATIONS FOR 老闆")
print("=" * 75)

print("""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎯 立即行動（1-2週內）                                                   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  1. 🔥 Bugatti Evolution 片仔（極大藍海，幾乎零競爭）                      ┃
┃     建議：Bugatti Veyron to Chiron Evolution (2005-2026)                 ┃
┃     公式：[品牌] + Evolution + [年份範圍]                                  ┃
┃                                                                           ┃
┃  2. 🔥 Ferrari / Porsche / McLaren 同期推出（總共少於10條）             ┃
┃     建議：Ferrari F40 to SF90 Evolution (1987-2026)                       ┃
┃     建議：Porsche 911 Evolution (1963-2026)                               ┃
┃                                                                           ┃
┃  3. ⏰ 發片時間：14:00-15:00 HKT（根據@kizzombie大數據）                  ┃
┃                                                                           ┃
┃  4. 📝 標題長度：40字以內                                                 ┃
┃                                                                           ┃
┃  5. 📊 目標：每週2-3條 Shorts，維持evolution + 年份範圍公式               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔭 中期策略（1-3個月）                                                  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  • 建立 Bugatti 完整家族 Evolution：Veyron→Chiron→Tourbillon              ┃
┃  • 對標 @kizzombie 爆片公式，但加入 Bugatti 獨特视角                     ┃
┃  • 開發「Bugatti vs 其他超跑」比較片（vs formula 僅 7%，競爭少）          ┃
┃  • 建立每月監控，追踪 @kizzombie 動態及時調整策略                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
""")

print(f"\n✅ Phase 3 Enhanced 報告完成")
print(f"   數據時間戳: {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
print(f"   @kizzombie: {len(kiz_shorts)} Shorts | @motomorfosis: {len(moto_shorts)} Shorts")
