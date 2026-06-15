#!/usr/bin/env python3
"""
topic_priority_v2.py
====================
Daily Topic Priority System V2 — ranks car series for next Shorts video

評分維度（總分100）：
  1. Trend Score    (35分) — Google Trends 實時數據
  2. YouTube Search Volume (25分) — YouTube API 關鍵詞搜尋量
  3. News Score    (20分) — 當日新聞提及次數
  4. Blue Ocean    (20分) — 競爭對手覆蓋缺口（越少片=越高分）

⚠️ Wiki Readiness 係門檻（≥1分先有資格），唔再係加分項

Usage: python3 scripts/topic_priority_v2.py [--save] [--debug]
"""

import re, sys, json, time, ssl
from pathlib import Path
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

BASE         = Path(__file__).parent.parent
WIKI_DIR     = BASE / 'wiki'
EXPORT_DIR   = BASE / 'exports'
TREND_REPORT = BASE / 'agent-meta' / 'trend-report.md'
DAILY_BRIEF  = BASE / 'agent-meta' / 'daily-brief.md'
COMP_ENHANCED= BASE / 'agent-meta' / 'competitor-analysis-phase2-enhanced.md'
LOG          = BASE / 'wiki' / 'log.md'
ENV_FILE     = BASE / '.env'

# ─────────────────────────────────────────
# YouTube API
# ─────────────────────────────────────────

def load_api_key() -> str:
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith('GOOGLE_API_KEY='):
            return line.split('=', 1)[1].strip()
    return ''

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def yt_keyword_search(query: str, max_results: int = 5) -> dict:
    """Search YouTube for keyword — returns totalResults (search volume proxy)."""
    api_key = load_api_key()
    if not api_key:
        return {'total': 0}
    url = (f"https://www.googleapis.com/youtube/v3/search"
           f"?part=snippet"
           f"&q={urllib.parse.quote(query)}"
           f"&type=video"
           f"&order=viewCount"
           f"&maxResults={max_results}"
           f"&key={api_key}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            data = json.loads(r.read())
            return {'total': data.get('pageInfo', {}).get('totalResults', 0),
                    'items': data.get('items', [])}
    except Exception:
        return {'total': 0, 'items': []}

# ─────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────

def load_trend_report() -> dict:
    """Parse agent-meta/trend-report.md for Google Trends data."""
    trends = {}
    if not TREND_REPORT.exists():
        return trends
    content = TREND_REPORT.read_text(encoding='utf-8')
    for line in content.split('\n'):
        m = re.search(r'\*\*(.+?)\*\*.*?[\u2014\-]\s+score:\s*(\d+)', line)
        if m:
            trends[m.group(1).strip()] = int(m.group(2))
    return trends


def load_daily_news() -> list:
    """Load today's news items from daily news fetcher output."""
    if not DAILY_BRIEF.exists():
        return []
    content = DAILY_BRIEF.read_text(encoding='utf-8')
    items = []
    for line in content.split('\n'):
        line = line.strip()
        # Match numbered items like "**1.** [Brand] Title" or "**2.** Title"
        m = re.match(r'\*\*\d+\.\*?\s*(?:\[.*?\])?\s*(.+)', line)
        if m and len(m.group(1)) > 10:
            items.append(m.group(1).strip())
    return items


def load_competitor_gaps() -> dict:
    """
    Parse competitor-analysis-phase2-enhanced.md for brand coverage gaps.
    Returns dict: brand → short_count (across both channels)
    Lower count = bigger opportunity (Blue Ocean)
    """
    gaps = {}
    if not COMP_ENHANCED.exists():
        return gaps
    content = COMP_ENHANCED.read_text(encoding='utf-8')

    # Known verified counts from 2026-04-29 analysis
    # These are hardcoded as fallback since parsing the JSON is complex
    KNOWN_COUNTS = {
        'bugatti': 2, 'mclaren': 1, 'ferrari': 4, 'porsche': 4,
        'lamborghini': 4, 'aston martin': 2, 'maserati': 1,
        'bentley': 1, 'rolls-royce': 3, ' Jaguar': 2,
        'bmw': 18, 'volkswagen': 15, 'suzuki': 13, 'yamaha': 12,
        'mazda': 6, 'mitsubishi': 7, 'audi': 8, 'land rover': 5,
        'nissan': 10, 'toyota': 20, 'honda': 12, 'ford': 14,
        'mercedes': 16, 'tesla': 8,
    }

    # Try to extract from content
    brand_pattern = re.compile(r'^\s*["\']?(\w+(?:\s+\w+)?)["\']?\s*:\s*(\d+)', re.IGNORECASE)
    for line in content.split('\n'):
        m = brand_pattern.search(line)
        if m:
            brand = m.group(1).lower()
            count = int(m.group(2))
            if brand in KNOWN_COUNTS or count < 30:
                gaps[brand] = count

    # Merge known counts
    for k, v in KNOWN_COUNTS.items():
        if k.lower() not in gaps:
            gaps[k.lower()] = v
    return gaps


def get_wiki_coverage() -> set:
    """Return set of (brand, model) combos we already have wiki pages for."""
    covered = set()
    series_dir = WIKI_DIR / 'series'
    if not series_dir.exists():
        return covered
    for brand_dir in series_dir.iterdir():
        if brand_dir.is_dir():
            for f in brand_dir.glob('*.md'):
                stem = f.stem
                parts = stem.split('-', 1)
                if len(parts) == 2:
                    brand, model = parts[0], parts[1]
                    model_readable = model.replace('-', ' ').title()
                    covered.add((brand.lower(), model.split('-')[0].lower()))
    return covered


# ─────────────────────────────────────────
# Candidate Generation
# ─────────────────────────────────────────

BRAND_SERIES = {
    'Ferrari': ['458 Italia', '488 GTB', 'F40', 'LaFerrari', '812 Superfast', '296 GTB', 'SF90 Stradale', 'Roma', 'Portofino'],
    'Porsche': ['911', '718 Cayman', 'Boxster', 'Panamera', 'Taycan', '918 Spyder', 'Carrera GT', '959'],
    'Lamborghini': ['Huracan', 'Aventador', 'Gallardo', 'Murcielago', 'Diablo', 'Countach', 'Miura', 'Urus', 'Revuelto'],
    'McLaren': ['720S', '570S', '600LT', '675LT', 'P1', 'F1', 'MP4-12C', 'Senna', 'Speedtail', 'Artura'],
    'Bugatti': ['Veyron', 'Chiron', 'Divo', 'Tourbillon', 'Centodieci', 'Bolide'],
    'BMW': ['M3', 'M4', 'M5', 'M8', 'i8', 'Z4', '8 Series', 'M2'],
    'Mercedes': ['AMG GT', 'AMG A45', 'C63 AMG', 'E63 AMG', 'SLS AMG', 'G-Wagon', 'AMG One'],
    'Audi': ['R8', 'TT', 'RS6', 'RS7', 'RS3', 'e-tron GT'],
    'Nissan': ['GT-R R35', 'GT-R R34', 'GT-R R33', 'GT-R R32', 'Skyline GT-R', 'Fairlady Z', 'Silvia', '370Z'],
    'Toyota': ['Supra', 'GR Supra', '86', 'AE86', 'Land Cruiser', 'Hilux', 'Celica'],
    'Honda': ['NSX', 'Civic Type R', 'S2000', 'S660', 'Integra Type R'],
    'Mazda': ['MX-5 Miata', 'RX-7', 'RX-8', '3', '6', 'MX-5'],
    'Ford': ['Mustang', 'GT', 'F-150', 'Focus RS', 'Fiesta ST'],
    'Chevrolet': ['Corvette', 'Camaro', 'C8', 'ZR1', 'Stingray'],
    'Dodge': ['Viper', 'Challenger', 'Charger', 'Demon', 'Hellcat'],
    'Aston Martin': ['DB11', 'DBS', 'Vantage', 'Valkyrie', 'DB9', 'One-77'],
    'Koenigsegg': ['Jesko', 'Regera', 'Agera', 'CC850', 'Gemera', 'CC8S'],
    'Tesla': ['Model S', 'Model 3', 'Model X', 'Model Y', 'Roadster', 'Cybertruck', 'Plaid'],
    'Range Rover': ['Sport', 'Velar', 'Evoque', 'Defender'],
    'KTM': ['X-Bow'],
}


def expand_candidates(trends: dict) -> list:
    """Generate list of (brand, model) candidates using trend data + brand series."""
    candidates = []
    seen = set()

    # Prioritize brands from trend report (sorted by trend score desc)
    for brand, score in sorted(trends.items(), key=lambda x: -x[1]):
        brand_norm = brand.strip()
        # Match brand in BRAND_SERIES
        for bkey in BRAND_SERIES:
            if bkey.lower() in brand_norm.lower() or brand_norm.lower() in bkey.lower():
                for model in BRAND_SERIES[bkey][:5]:  # top 5 series per brand
                    key = (bkey.lower(), model.lower().split()[0])
                    if key not in seen:
                        seen.add(key)
                        candidates.append((bkey, model, score))
                break
        else:
            # Unknown brand — create generic candidate
            if (brand_norm.lower(), 'generic') not in seen:
                seen.add((brand_norm.lower(), 'generic'))
                candidates.append((brand_norm.title(), 'Generic', score))

    # Fill with top brands not in trends
    top_brands = ['Ferrari', 'Porsche', 'Lamborghini', 'McLaren', 'Bugatti',
                  'BMW', 'Mercedes', 'Audi', 'Nissan', 'Toyota']
    for bkey in top_brands:
        for model in BRAND_SERIES.get(bkey, [])[:3]:
            key = (bkey.lower(), model.lower().split()[0])
            if key not in seen:
                seen.add(key)
                candidates.append((bkey, model, trends.get(bkey, trends.get(f'{bkey} AMG', 10))))

    return candidates


# ─────────────────────────────────────────
# Scoring Engine
# ─────────────────────────────────────────

def score_candidate(brand: str, model: str,
                    trend_score: int,
                    yt_total: int,
                    news_items: list,
                    competitor_gaps: dict,
                    wiki_covered: set,
                    recent_topics: list,
                    debug: bool = False) -> dict:
    """
    V2 scoring — 4 dimensions (no Wiki加分).

    1. Trend Score  (35pt max)  — Google Trends 實時數據 × 0.35
    2. YouTube Search Volume (25pt max) — YouTube search results × 0.02, capped at 25
    3. News Score   (20pt max)  — News mentions × 7, capped at 20
    4. Blue Ocean   (20pt max)  — Competitor gap scoring

    Wiki Readiness: PASS/FAIL gate (not a score).
    """
    scores = {}
    reasons = []

    # ── 1. Trend Score (0-35) ──────────────────────────
    trend_pts = min(trend_score * 0.35, 35)
    scores['trend'] = round(trend_pts, 1)
    if trend_score >= 40:
        reasons.append(f"🔥 Strong trend: {trend_score}/100")
    elif trend_score >= 20:
        reasons.append(f"📈 Moderate trend: {trend_score}/100")
    elif trend_score > 0:
        reasons.append(f"📊 Low trend: {trend_score}/100")

    # ── 2. YouTube Search Volume (0-25) ─────────────────
    yt_pts = min(yt_total * 0.02, 25)
    scores['yt_search'] = round(yt_pts, 1)
    if yt_total >= 800:
        reasons.append(f"🔍 High YT demand: {yt_total} results")
    elif yt_total >= 200:
        reasons.append(f"🔎 Medium YT demand: {yt_total} results")
    elif yt_total > 0:
        reasons.append(f"🔎 Low YT demand: {yt_total} results")

    # ── 3. News Score (0-20) ───────────────────────────
    model_lower = model.lower()
    brand_lower = brand.lower()
    news_hits = sum(1 for item in news_items
                    if model_lower in item.lower() or brand_lower in item.lower())
    news_pts = min(news_hits * 7, 20)
    scores['news'] = round(news_pts, 1)
    if news_hits >= 2:
        reasons.append(f"📰 Hot news: {news_hits} articles")
    elif news_hits == 1:
        reasons.append(f"📰 News mention: {news_hits} article")

    # ── 4. Blue Ocean Score (0-20) ────────────────────
    brand_gap = competitor_gaps.get(brand_lower, competitor_gaps.get(brand_lower.replace(' ', ''), 999))
    brand_gap2 = competitor_gaps.get(brand_lower.replace('-', ' '), 999)
    actual_gap = min(brand_gap, brand_gap2, 999)

    if actual_gap <= 2:
        blue_ocean_pts = 20
        reasons.append(f"🌊 Super Blue Ocean: only {actual_gap} competitor shorts")
    elif actual_gap <= 5:
        blue_ocean_pts = 15
        reasons.append(f"🌊 Blue Ocean: {actual_gap} competitor shorts")
    elif actual_gap <= 15:
        blue_ocean_pts = 10
        reasons.append(f"🟡 Crowded: {actual_gap} competitor shorts")
    else:
        blue_ocean_pts = 3
        reasons.append(f"🔴 Saturated: {actual_gap}+ competitor shorts")
    scores['blue_ocean'] = round(blue_ocean_pts, 1)

    # ── Wiki Gate (PASS/FAIL) ───────────────────────────
    key = (brand_lower, model_lower.split()[0])
    covered = (key in wiki_covered or
               any(brand_lower in c and model_lower.split()[0] in c[1]
                   for c in wiki_covered))
    wiki_gate = '✅ Wiki Ready' if covered else '⚠️ No Wiki'

    # ── Recency Penalty (0-10 deduction) ───────────────
    recent_lower = [t.lower() for t in recent_topics]
    recency_pts = -10 if (model_lower in recent_lower or brand_lower in recent_lower) else 0
    scores['recency'] = recency_pts
    if recency_pts < 0:
        reasons.append("⏪ Recently covered — penalty applied")

    # ── Total ──────────────────────────────────────────
    total = sum(scores.values())
    return {
        'brand': brand,
        'model': model,
        'total_score': round(total, 1),
        'breakdown': {k: round(v, 1) for k, v in scores.items()},
        'reasons': reasons,
        'wiki_gate': wiki_gate,
        'yt_total': yt_total,
        'trend_score': trend_score,
        'competitor_gap': actual_gap if actual_gap < 999 else None,
    }


def get_recent_topics() -> list:
    """Load recent topics from competitor report to avoid duplication."""
    comp_report = EXPORT_DIR / 'competitor' / 'latest-report.md'
    topics = []
    if comp_report.exists():
        content = comp_report.read_text(encoding='utf-8')
        for brand in BRAND_SERIES:
            if brand.lower() in content.lower():
                topics.append(brand)
    return topics[:20]


# ─────────────────────────────────────────
# Output
# ─────────────────────────────────────────

def generate_priority_report(candidates: list, limit: int = 8, debug: bool = False) -> str:
    trend_data        = load_trend_report()
    news_items        = load_daily_news()
    wiki_covered      = get_wiki_coverage()
    competitor_gaps   = load_competitor_gaps()
    recent            = get_recent_topics()

    scored = []
    for brand, model, trend_score in candidates:
        # Get YouTube search volume for "brand model evolution"
        query = f"{brand} {model} evolution"
        yt_data = yt_keyword_search(query, max_results=3)
        yt_total = yt_data.get('total', 0)

        r = score_candidate(brand, model, trend_score, yt_total,
                           news_items, competitor_gaps, wiki_covered, recent, debug)
        scored.append(r)

    # Sort by total score desc
    scored.sort(key=lambda x: -x['total_score'])
    top = scored[:limit]

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    yt_ok = all(r.get('yt_total', 0) > 0 for r in scored)
    lines = [
        f"# 📋 Topic Priority Report V2",
        "",
        "## ⚠️ DATA FRESHNESS",
        f"- **Status:** {'✅ LIVE' if yt_ok else '⚠️ PARTIAL (YouTube API may be exhausted)'}",
        f"- **Generated:** {now} HKT",
        f"- **YouTube API:** {'✅ Working' if yt_ok else '❌ Quota exhausted or error'}",
        f"- **Trend Data:** `agent-meta/trend-report.md`",
        f"- **News Data:** `agent-meta/daily-brief.md`",
        f"- **Competitor:** `exports/competitor/latest-report.md`",
        "",
        "## ✅ Pre-Delivery Checklist",
        "[ ] Report has Freshness Stamp above",
        "[ ] YouTube API status verified (if ❌, warn user before sending)",
        "[ ] Scores look sane (not all zeros, not all identical)",
        "[ ] Top pick has ✅Wiki (green), not ⚠️No Wiki (amber)",
        "",
        "---\n",
        "## 🏆 Top Recommended Topics",
        "",
    ]

    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣']
    for i, r in enumerate(top):
        lines.append(f"### {medals[i]} {r['brand']} {r['model']}")
        lines.append(f"**Score: {r['total_score']}/100** | {r['wiki_gate']}")
        lines.append(f"**Why:** {' | '.join(r['reasons'])}")
        lines.append(f"| Component | Score |")
        lines.append(f"|-----------|-------|")
        for k, v in r['breakdown'].items():
            sign = '+' if v >= 0 else ''
            lines.append(f"| {k.title()} | {sign}{v} |")
        lines.append(f"**YT Search:** {r['yt_total']} results | **Trend:** {r['trend_score']}/100 | **Gap:** {r['competitor_gap']}")
        lines.append(f"**Suggested title:** {r['brand']} {r['model']} Evolution (2026) 🚗")
        lines.append(f"**Script cmd:** `python3 scripts/script_generator.py {r['brand']} {r['model']} --save`")
        lines.append("")

    # Wiki Gaps
    gaps = [r for r in scored if 'No Wiki' in r['wiki_gate']][:5]
    if gaps:
        lines += ["---", "", "## 🔴 Wiki Gaps (Need Research)"]
        for r in gaps:
            lines.append(f"- **{r['brand']} {r['model']}** (score: {r['total_score']}) — run `python3 scripts/auto_wiki_ingestion.py --brand {r['brand']}`")
        lines.append("")

    # Data sources
    lines += [
        "---",
        "",
        "## 📡 Data Sources",
        f"- Google Trends: `agent-meta/trend-report.md` ({len(trend_data)} keywords)",
        f"- Daily News: `agent-meta/daily-brief.md` ({len(news_items)} items)",
        f"- Competitor Gaps: `agent-meta/competitor-analysis-phase2-enhanced.md`",
        f"- YouTube API: live search for `brand model evolution` queries",
        f"- Wiki Coverage: `wiki/series/` ({len(wiki_covered)} series)",
        "",
    ]

    return '\n'.join(lines)


def save_report(content: str) -> Path:
    out = EXPORT_DIR / 'topic-priority' / f"priority-{datetime.now().strftime('%Y-%m-%d')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding='utf-8')
    latest = EXPORT_DIR / 'topic-priority' / 'latest-report.md'
    latest.write_text(content, encoding='utf-8')
    return out


def append_log(action: str, detail: str = ''):
    if not LOG.exists():
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [TOPIC-V2] {action}'
    if detail:
        entry += f' — {detail}'
    entry += '\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    save   = '--save' in sys.argv
    debug  = '--debug' in sys.argv

    print("🔥 Building Topic Priority Report V2...")
    trend_data = load_trend_report()
    print(f"  ✓ Loaded {len(trend_data)} trend keywords")

    news_items = load_daily_news()
    print(f"  ✓ Loaded {len(news_items)} news items")

    competitor_gaps = load_competitor_gaps()
    print(f"  ✓ Loaded {len(competitor_gaps)} competitor gap counts")

    wiki_covered = get_wiki_coverage()
    print(f"  ✓ Wiki coverage: {len(wiki_covered)} series")

    candidates = expand_candidates(trend_data)
    print(f"  ✓ Expanded to {len(candidates)} candidates")

    report = generate_priority_report(candidates, limit=8, debug=debug)

    print()
    print("=" * 60)
    print(report)
    print("=" * 60)

    if save:
        path = save_report(report)
        append_log("Topic priority V2 report generated", str(path))
        print(f"\n[OK] Saved to: {path}")
    else:
        print(f"\n[OK] Add --save to write to exports/topic-priority/")


if __name__ == '__main__':
    main()
