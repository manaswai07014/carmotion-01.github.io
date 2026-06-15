#!/usr/bin/env python3
"""Debug analysis - full raw data verification"""
import json
import re
from collections import Counter

channels = [
    ('kizzombie', 'ArtKiz'),
    ('motomorfosis', 'Motomorfosis')
]

all_data = {}
for cid, cname in channels:
    with open(f'data/competitors/{cid}/latest_videos.json') as f:
        data = json.load(f)
    shorts = data['shorts']
    viral = [s for s in shorts if s['view_count'] > 1000000]
    all_data[cid] = {'shorts': shorts, 'viral': viral, 'cname': cname}

CAR_KEYWORDS = {
    'evolution': ['evolution', 'evolve', 'evolusi'],
    'iconic': ['iconic', 'legendary', 'legenda', 'legendaris'],
    'military': ['military', 'army', 'soldier'],
    'brand': ['bmw', 'mercedes', 'honda', 'toyota', 'ford', 'bugatti', 'ferrari', 'porsche',
              'lamborghini', 'mitsubishi', 'nissan', 'mazda', 'subaru', 'lexus', 'audi',
              'jaguar', 'maserati', 'bentley', 'rolls'],
    'number': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
}

YEAR_PATTERNS = [
    r'\d{4}\s*[-–]\s*\d{4}',  # 2000-2020
    r'\d{4}\s+to\s+\d{4}',    # 2000 to 2020
    r'gen\s*\d',              # gen 1, gen2
    r'\d{4}/\d{4}',           # 2000/2020
]

def has_keyword(title, keywords):
    t = title.lower()
    return any(k in t for k in keywords)

def has_year_range(title):
    for p in YEAR_PATTERNS:
        if re.search(p, title, re.IGNORECASE):
            return True
    return False

for cid, cname in channels:
    shorts = all_data[cid]['shorts']
    viral = all_data[cid]['viral']

    print(f"\n{'=' * 60}")
    print(f"【{cname}】Total: {len(shorts)}, Viral: {len(viral)}")
    print(f"{'=' * 60}")

    print("\n--- VIRAL ANALYSIS ---")
    for cat, keywords in CAR_KEYWORDS.items():
        v_cnt = sum(1 for s in viral if has_keyword(s['title'], keywords))
        a_cnt = sum(1 for s in shorts if has_keyword(s['title'], keywords))
        vp = 100*v_cnt/len(viral) if viral else 0
        ap = 100*a_cnt/len(shorts) if shorts else 0
        diff = vp - ap
        print(f"  {cat:12s}: viral={vp:5.1f}% ({v_cnt}/{len(viral)}) | all={ap:5.1f}% ({a_cnt}/{len(shorts)}) | diff={diff:+5.1f}%")

    v_yr = sum(1 for s in viral if has_year_range(s['title']))
    a_yr = sum(1 for s in shorts if has_year_range(s['title']))
    vp_yr = 100*v_yr/len(viral) if viral else 0
    ap_yr = 100*a_yr/len(shorts) if shorts else 0
    print(f"  {'year_range':12s}: viral={vp_yr:5.1f}% ({v_yr}/{len(viral)}) | all={ap_yr:5.1f}% ({a_yr}/{len(shorts)}) | diff={vp_yr-ap_yr:+5.1f}%")

    print("\n--- TOP 10 BY VIEWS ---")
    sorted_all = sorted(shorts, key=lambda x: x['view_count'], reverse=True)[:10]

    for cat, keywords in CAR_KEYWORDS.items():
        t_cnt = sum(1 for s in sorted_all if has_keyword(s['title'], keywords))
        a_cnt = sum(1 for s in shorts if has_keyword(s['title'], keywords))
        tp = 100*t_cnt/10
        ap = 100*a_cnt/len(shorts) if shorts else 0
        print(f"  {cat:12s}: top10={tp:5.1f}% ({t_cnt}/10) | all={ap:5.1f}% ({a_cnt}/{len(shorts)}) | diff={tp-ap:+5.1f}%")

    v_yr_top = sum(1 for s in sorted_all if has_year_range(s['title']))
    a_yr = sum(1 for s in shorts if has_year_range(s['title']))
    tp_yr = 100*v_yr_top/10
    ap_yr_all = 100*a_yr/len(shorts) if shorts else 0
    print(f"  {'year_range':12s}: top10={tp_yr:5.1f}% ({v_yr_top}/10) | all={ap_yr_all:5.1f}% ({a_yr}/{len(shorts)}) | diff={tp_yr-ap_yr_all:+5.1f}%")

    print("\nTOP 10 titles:")
    for i, s in enumerate(sorted_all, 1):
        print(f"  {i}. [{s['view_count']:,}] {s['title'][:70]}")

    print("\nSample viral titles:")
    for i, s in enumerate(sorted(viral, key=lambda x: x['view_count'], reverse=True)[:5], 1):
        print(f"  {i}. [{s['view_count']:,}] {s['title'][:70]}")
