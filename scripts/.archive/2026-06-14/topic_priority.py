#!/usr/bin/env python3
# scripts/topic_priority.py
# Daily Topic Priority System — ranks car series for next Shorts video
# Combines: Google Trends + News + Competitor Data + Wiki Readiness
# Output: Top 5 recommended topics with scores + rationale
# Usage: python3 scripts/topic_priority.py [--save]

import re, sys, json, time
from pathlib import Path
from datetime import datetime, timedelta

BASE       = Path(__file__).parent.parent
WIKI_DIR   = BASE / 'wiki'
EXPORT_DIR = BASE / 'exports'
TREND_REPORT = BASE / 'agent-meta' / 'trend-report.md'
LOG        = BASE / 'wiki' / 'log.md'

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
        m = re.match(r'\*\*(.+?)\*\*.*— score:\s*(\d+)', line)
        if m:
            trends[m.group(1).strip()] = int(m.group(2))
    return trends


def load_daily_news() -> list:
    """Load today's news items from daily news fetcher output."""
    # The daily news fetcher stores latest in agent-meta/daily-brief.md
    brief = BASE / 'agent-meta' / 'daily-brief.md'
    if not brief.exists():
        return []
    content = brief.read_text(encoding='utf-8')
    items = []
    # Extract news lines (lines starting with - or •)
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith(('- ', '• ')) and len(line) > 10:
            items.append(line[2:].strip())
    return items


def load_competitor_data() -> dict:
    """Load competitor analysis to understand what's working."""
    comp_dir = EXPORT_DIR / 'competitor'
    if not comp_dir.exists():
        return {}
    # Look for latest competitor report
    reports = sorted(comp_dir.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
    data = {}
    for r in reports[:1]:
        content = r.read_text(encoding='utf-8')
        # Extract top performing videos / hashtags
        for line in content.split('\n'):
            m = re.match(r'#(\w+)', line.strip())
            if m:
                word = m.group(1)
                data[word] = data.get(word, 0) + 1
    return data


def get_wiki_coverage() -> set:
    """Return set of brand/model combos we already have wiki pages for."""
    covered = set()
    series_dir = WIKI_DIR / 'series'
    if not series_dir.exists():
        return covered
    for brand_dir in series_dir.iterdir():
        if brand_dir.is_dir():
            for f in brand_dir.glob('*.md'):
                # Extract model from filename: ferrari-458-italia.md → 458 Italia
                stem = f.stem  # ferrari-458-italia
                parts = stem.split('-', 1)
                if len(parts) == 2:
                    brand, model = parts[0], parts[1]
                    # Convert hyphenated model to readable: 458-italia → 458 Italia
                    model_readable = model.replace('-', ' ').title()
                    covered.add((brand.lower(), model.split('-')[0].lower()))
    return covered


# ─────────────────────────────────────────
# Candidate Generation
# ─────────────────────────────────────────

# Brand → likely series mapping (expand with research)
BRAND_SERIES = {
    'Ferrari': ['458 Italia', '488 GTB', 'F40', 'LaFerrari', '812 Superfast', '296 GTB', 'SF90 Stradale', 'Roma', 'Portofino', 'Mondial', '550 Maranello', '575M', '599 GTB', 'F12', 'FF', 'GTC4 Lusso', '365 GTB', '365 GT4', 'Z39'],
    'Porsche': ['911', '718 Cayman', 'Boxster', 'Panamera', 'Cayenne', 'Taycan', '918 Spyder', 'Carrera GT', '959'],
    'Lamborghini': ['Huracan', 'Aventador', 'Gallardo', 'Murcielago', 'Diablo', 'Countach', 'Miura', 'Urus', 'Revuelto'],
    'McLaren': ['720S', '570S', '600LT', '675LT', 'P1', 'F1', 'MP4-12C', 'Senna', 'Speedtail', 'Artura'],
    'Bugatti': ['Veyron', 'Chiron', 'Divo', 'Tourbillon', 'Centodieci', 'Bolide'],
    'BMW': ['M3', 'M4', 'M5', 'M8', 'i8', 'Z4', '8 Series', 'M2', 'X5 M', 'X3 M'],
    'Mercedes': ['AMG GT', 'AMG A45', 'C63 AMG', 'E63 AMG', 'SLS AMG', 'G-Wagon', 'AMG One'],
    'Mercedes-AMG': ['GT', 'A45', 'C63', 'E63', 'SLS', 'G-Wagon', 'One'],
    'Audi': ['R8', 'TT', 'RS6', 'RS7', 'RS3', 'e-tron GT', 'Quattro'],
    'Nissan': ['GT-R R35', 'GT-R R34', 'GT-R R33', 'GT-R R32', 'Skyline GT-R', 'Fairlady Z', 'Silvia', '370Z', '350Z', 'Z Proto'],
    'Toyota': ['Supra', 'GR Supra', '86', 'AE86', 'Land Cruiser', 'Hilux', 'Celica'],
    'Honda': ['NSX', 'Civic Type R', 'S2000', 'S660', 'Integra Type R', 'Accord Euro-R'],
    'Mazda': ['MX-5 Miata', 'RX-7', 'RX-8', '3', '6', 'MX-5'],
    'Ford': ['Mustang', 'GT', 'F-150', 'Focus RS', 'Fiesta ST'],
    'Chevrolet': ['Corvette', 'Camaro', 'C8', 'ZR1', ' Stingray'],
    'Dodge': ['Viper', 'Challenger', 'Charger', 'Demon', 'Hellcat'],
    'Aston Martin': ['DB11', 'DBS', 'Vantage', 'Valkyrie', 'DB9', 'One-77'],
    'Koenigsegg': ['Jesko', 'Regera', 'Agera', 'CC850', 'Gemera', 'CC8S'],
    'Tesla': ['Model S', 'Model 3', 'Model X', 'Model Y', 'Roadster', 'Cybertruck', 'Plaid'],
    'Range Rover': ['Sport', 'Velar', 'Evoque', 'Defender'],
    'KTM': ['X-Bow'],
}

def expand_candidates(trends: dict) -> list:
    """Generate list of (brand, model) candidates with trend scores."""
    candidates = []
    seen = set()

    # Prioritize brands from trend report
    for brand, score in sorted(trends.items(), key=lambda x: -x[1]):
        brand_norm = brand.strip()
        # Find matching brand in BRAND_SERIES
        for bkey in BRAND_SERIES:
            if bkey.lower() in brand_norm.lower() or brand_norm.lower() in bkey.lower():
                for model in BRAND_SERIES[bkey][:6]:  # top 6 series per brand
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

    # Fill in remaining with top brands (if not in trends)
    for bkey, models in BRAND_SERIES.items():
        for model in models[:3]:
            key = (bkey.lower(), model.lower().split()[0])
            if key not in seen:
                seen.add(key)
                candidates.append((bkey, model, trends.get(bkey, trends.get(f'{bkey} AMG', 20))))

    return candidates


# ─────────────────────────────────────────
# Scoring Engine
# ─────────────────────────────────────────

def score_candidate(brand: str, model: str, trend_score: int,
                    news_items: list, wiki_covered: set,
                    recent_topics: list) -> dict:
    """Score a candidate topic. Returns dict with breakdown."""
    scores = {}
    reasons = []

    # 1. Trend Score (0-40 points)
    scores['trend'] = min(trend_score * 0.4, 40)
    if trend_score >= 40:
        reasons.append(f"Strong trend: {trend_score}/100")
    elif trend_score >= 20:
        reasons.append(f"Moderate trend: {trend_score}/100")

    # 2. News Freshness (0-20 points)
    news_text = ' '.join(news_items).lower()
    model_lower = model.lower()
    brand_lower = brand.lower()
    news_hits = sum(1 for item in news_items
                    if model_lower in item.lower() or brand_lower in item.lower())
    news_score = min(news_hits * 7, 20)
    scores['news'] = news_score
    if news_hits >= 2:
        reasons.append(f"Hot news: {news_hits} articles")
    elif news_hits == 1:
        reasons.append(f"News mention: {news_hits} article")

    # 3. Wiki Readiness (0-15 points) — we have data = less production effort
    key = (brand_lower, model_lower.split()[0])
    covered = key in wiki_covered or any(
        brand_lower in c and model_lower.split()[0] in c[1]
        for c in wiki_covered
    )
    if covered:
        scores['wiki'] = 15
        reasons.append("Wiki data ready ✓")
    else:
        scores['wiki'] = 0
        reasons.append("Needs research (no wiki data)")

    # 4. Competition Heat (0-15 points) — competitors making videos = topic is hot
    # We don't have real-time competitor data here, so use trend as proxy
    if trend_score >= 35:
        scores['competition'] = 15
        reasons.append("Competitors likely covering")
    elif trend_score >= 20:
        scores['competition'] = 8
    else:
        scores['competition'] = 3

    # 5. Recency Penalty (0-10 deduction) — made recently?
    recent_lower = [t.lower() for t in recent_topics]
    if model_lower in recent_lower or brand_lower in recent_lower:
        scores['recency'] = -10
        reasons.append("Recently covered — low recency penalty")
    else:
        scores['recency'] = 0

    total = sum(scores.values())
    return {
        'brand': brand,
        'model': model,
        'total_score': round(total, 1),
        'breakdown': {k: round(v, 1) for k, v in scores.items()},
        'reasons': reasons,
        'wiki_ready': covered,
    }


def get_recent_topics() -> list:
    """Load recent topics from daily competitor report to avoid duplication."""
    comp_report = EXPORT_DIR / 'competitor' / 'latest-report.md'
    topics = []
    if comp_report.exists():
        content = comp_report.read_text(encoding='utf-8')
        # Extract mentions
        for brand in BRAND_SERIES:
            if brand.lower() in content.lower():
                topics.append(brand)
    return topics[:20]


# ─────────────────────────────────────────
# Output
# ─────────────────────────────────────────

def generate_priority_report(candidates: list, limit: int = 8) -> str:
    """Generate the full priority report markdown."""
    trend_data   = load_trend_report()
    news_items   = load_daily_news()
    wiki_covered = get_wiki_coverage()
    recent       = get_recent_topics()

    scored = []
    for brand, model, trend_score in candidates:
        r = score_candidate(brand, model, trend_score, news_items, wiki_covered, recent)
        scored.append(r)

    # Sort by total score
    scored.sort(key=lambda x: -x['total_score'])
    top = scored[:limit]

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f"# 📋 Topic Priority Report",
        f"**Generated:** {now} HKT",
        f"**Data:** Google Trends + Daily News + Wiki Coverage",
        "",
        "---",
        "",
        "## 🏆 Top Recommended Topics",
        "",
    ]

    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣']
    for i, r in enumerate(top):
        brand = r['brand']
        model = r['model']
        wiki_tag = '🟢' if r['wiki_ready'] else '🔴'
        lines.append(f"### {medals[i]} {brand} {model} {wiki_tag}")
        lines.append(f"**Score:** {r['total_score']}/100")
        lines.append(f"**Why:** {' | '.join(r['reasons'])}")
        lines.append(f"| Component | Score |")
        lines.append(f"|-----------|-------|")
        for k, v in r['breakdown'].items():
            sign = '+' if v >= 0 else ''
            lines.append(f"| {k.title()} | {sign}{v} |")
        lines.append(f"**Suggested title:** The EVOLUTION of {brand} {model} ({datetime.now().year}) 🚗")
        lines.append(f"**Script cmd:** `python3 scripts/script_generator.py {brand} {model} --save`")
        lines.append("")

    # Coverage summary
    lines += [
        "---",
        "",
        "## 📊 Wiki Coverage Summary",
        f"- Brands covered: {len(set(c[0] for c in wiki_covered))}",
        f"- Series covered: {len(wiki_covered)}",
        "",
    ]

    # Show gaps (trending brands with no wiki coverage)
    gaps = [r for r in scored if not r['wiki_ready']][:5]
    if gaps:
        lines.append("## 🔴 Priority Gaps (Trending but No Wiki Data)")
        for r in gaps:
            lines.append(f"- **{r['brand']} {r['model']}** (score: {r['total_score']}) — run `python3 scripts/auto_wiki_ingestion.py --brand {r['brand']}`")
        lines.append("")

    # News summary
    if news_items:
        lines += [
            "---",
            "",
            "## 📰 Today's News Highlights",
        ]
        for item in news_items[:5]:
            lines.append(f"- {item}")
        lines.append("")

    # Data sources
    lines += [
        "---",
        "",
        "## 📡 Data Sources",
        f"- Google Trends: `agent-meta/trend-report.md` (scanned: {len(trend_data)} keywords)",
        f"- Daily News: `agent-meta/daily-brief.md` ({len(news_items)} items)",
        f"- Wiki Coverage: `wiki/series/` ({len(wiki_covered)} series)",
        f"- Recency: last competitor report",
        "",
    ]

    return '\n'.join(lines)


def save_report(content: str) -> Path:
    out = EXPORT_DIR / 'topic-priority' / f"priority-{datetime.now().strftime('%Y-%m-%d')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding='utf-8')
    # Also write as latest
    latest = EXPORT_DIR / 'topic-priority' / 'latest-report.md'
    latest.write_text(content, encoding='utf-8')
    return out


def append_log(action: str, detail: str = ''):
    if not LOG.exists():
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [TOPIC] {action}'
    if detail:
        entry += f' — {detail}'
    entry += '\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    save = '--save' in sys.argv

    print("🔥 Building Topic Priority Report...")
    trend_data = load_trend_report()
    print(f"  ✓ Loaded {len(trend_data)} trend keywords")

    news_items = load_daily_news()
    print(f"  ✓ Loaded {len(news_items)} news items")

    wiki_covered = get_wiki_coverage()
    print(f"  ✓ Wiki coverage: {len(wiki_covered)} series")

    candidates = expand_candidates(trend_data)
    print(f"  ✓ Expanded to {len(candidates)} candidates")

    report = generate_priority_report(candidates, limit=8)

    print()
    print("=" * 60)
    print(report)
    print("=" * 60)

    if save:
        path = save_report(report)
        append_log("Topic priority report generated", str(path))
        print(f"\n[OK] Saved to: {path}")
    else:
        print(f"\n[OK] Add --save to write to exports/topic-priority/")


if __name__ == '__main__':
    main()
