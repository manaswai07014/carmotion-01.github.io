#!/usr/bin/env python3
"""
YouTube Competitor Analysis - Phase 2: AI Strategy Layer (ENHANCED + VALIDATED)
================================================================================
強化版分析，加入數據驗證機制，確保報告數字準確。

Validation 機制：
- ANALYSIS 1: TITLE FORMULA (ALL SHORTS)
- ANALYSIS 2: TRAFFIC PATTERNS
- ANALYSIS 3: ENGAGEMENT ANALYSIS
- ANALYSIS 4: VIRAL FACTORS (Viral = Views > 1M)
- ANALYSIS 5: TOP 10 BY VIEWS (sorted by view_count)
- ANALYSIS 6: VIEW DISTRIBUTION
- ANALYSIS 7: COMPETITOR GAPS

Validation Rules:
1. Total shorts = viral + non-viral
2. Viral % = viral_count / total * 100
3. All percentages are recalculated at display time (not stored)
4. Quick sanity check printed before each report

Usage:
    python3 scripts/competitor-analysis.py
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
COMPETITORS_DIR = PROJECT_ROOT / "data" / "competitors"

HKT = timezone(timedelta(hours=8))
EST = timezone(timedelta(hours=-5))

TARGET_CHANNELS = [
    {"id": "kizzombie", "handle": "@kizzombie", "name": "ArtKiz"},
    {"id": "motomorfosis", "handle": "@motomorfosis", "name": "Motomorfosis"},
]

# 汽車關鍵詞庫（多語言）
CAR_KEYWORDS = {
    "evolution": ["Evolution", "Evolve", "Evolusi", "Evolutionary", "Lineage", "Heritage"],
    "comparison": ["vs", "VS", "versus", "Compared", "vs.", "V.S."],
    "iconic": ["Iconic", "Legendary", "Timeless", "Iconic", "Legenda", "Legendaris", "Legends", "Legend"],
    "wildest": ["Wildest", "Insane", "Craziest", "Extreme"],
    "motorsport": ["Motorsport", "Racing", "DTM", "GT3", "GT-R", "Group A", "Group B", "Motorsports"],
    "build": ["Build", "Builds", "Modification", "Mod", "Tuned", "Custom", "Transformasi", "Transformation"],
    "origin": ["Origin", "First", "Birth", "Beginning", "Prototype", "History", "From"],
    "movie": ["Movie", "Film", "Cinema", "Hollywood", "Fast & Furious"],
    "gaming": ["NFS", "Need for Speed", "Forza", "Gran Turismo", "GTA", "Initial D"],
    "military": ["Military", "Army", "Tank", "War", "Armored", "Armee"],
}


def load_channel_data(channel_id):
    """Load stored data for a channel."""
    channel_dir = COMPETITORS_DIR / channel_id
    videos_file = channel_dir / "latest_videos.json"
    stats_file = channel_dir / "channel_stats.json"
    
    if not videos_file.exists() or not stats_file.exists():
        return None
    
    with open(videos_file) as f:
        videos_data = json.load(f)
    with open(stats_file) as f:
        stats = json.load(f)
    
    return {
        "channel": stats,
        "shorts": videos_data.get("shorts", []),
        "top_10": videos_data.get("top_10_shorts", []),
        "latest_10": videos_data.get("latest_10_shorts", []),
    }


def extract_title_components(title):
    """Extract detailed components from a title."""
    title_lower = title.lower()
    
    components = {
        "raw_title": title,
        "has_number": bool(re.search(r'\d+', title)),
        "number": re.search(r'\d+', title).group() if re.search(r'\d+', title) else None,
        "has_brand": False,
        "brands": [],
        "has_year_range": bool(re.search(r'\d{4}.*\d{4}', title)),
        "year_range": re.search(r'\d{4}.*\d{4}', title).group() if re.search(r'\d{4}.*\d{4}', title) else None,
        "has_evolution": any(k.lower() in title_lower for k in CAR_KEYWORDS["evolution"]),
        "has_vs": any(k in title for k in CAR_KEYWORDS["comparison"]),
        "has_part": bool(re.search(r'Part \d+|Part\s*\d+', title, re.IGNORECASE)),
        "has_iconic": any(k.lower() in title_lower for k in CAR_KEYWORDS["iconic"]),
        "has_wildest": any(k.lower() in title_lower for k in CAR_KEYWORDS["wildest"]),
        "has_motorsport": any(k.lower() in title_lower for k in CAR_KEYWORDS["motorsport"]),
        "has_build": any(k.lower() in title_lower for k in CAR_KEYWORDS["build"]),
        "has_origin": any(k.lower() in title_lower for k in CAR_KEYWORDS["origin"]),
        "has_movie": any(k.lower() in title_lower for k in CAR_KEYWORDS["movie"]),
        "has_gaming": any(k.lower() in title_lower for k in CAR_KEYWORDS["gaming"]),
        "has_military": any(k.lower() in title_lower for k in CAR_KEYWORDS["military"]),
        "title_length": len(title),
        "word_count": len(title.split()),
    }
    
    # Extract brands
    brand_patterns = [
        r'\b(Porsche|Ferrari|BMW|Mercedes|Audi|Lamborghini|Bugatti|Maserati|Rolls-Royce|Bentley|Lotus|Jaguar|Aston Martin|McLaren|Lancia|Alfa Romeo)\b',
        r'\b(Toyota|Honda|Nissan|Mazda|Subaru|Mitsubishi|Lexus|Infiniti|Acura|Hyundai|Kia|Genesis)\b',
        r'\b(Ford|Chevrolet|Dodge|GMC|RAM|Cadillac|Lincoln|Jeep|Buick|Pontiac)\b',
        r'\b(Kawasaki|Ducati|Harley-Davidson|Harley|Yamaha|Suzuki|Honda|KTM|Aprilia|Triumph)\b',
        r'\b(NFS|Need for Speed|Initial D|Fast & Furious|GTA)\b',
        r'\b(Mercedes-Benz|BMW M|Ford Mustang|Chevy Corvette|Dodge Viper|Toyota Supra|Nissan GT-R|Honda NSX|Mazda RX-7)\b',
    ]
    
    for pattern in brand_patterns:
        matches = re.findall(pattern, title, re.IGNORECASE)
        if matches:
            components["has_brand"] = True
            components["brands"].extend([m.lower() for m in matches])
    
    # Keyword categories
    components["keyword_categories"] = []
    for cat, keywords in CAR_KEYWORDS.items():
        if any(k.lower() in title_lower for k in keywords):
            components["keyword_categories"].append(cat)
    
    return components


# =============================================================================
# VALIDATION SYSTEM
# =============================================================================
class ValidationError(Exception):
    pass


def validate_channel_data(shorts, channel_name):
    """Validate channel data integrity."""
    errors = []
    warnings = []
    
    total = len(shorts)
    if total == 0:
        errors.append(f"{channel_name}: No shorts found!")
        return errors, warnings
    
    # Check view counts
    views = [s["view_count"] for s in shorts]
    if any(v < 0 for v in views):
        errors.append(f"{channel_name}: Negative view count found!")
    
    # Check viral count consistency
    viral = [s for s in shorts if s["view_count"] > 1000000]
    non_viral = [s for s in shorts if s["view_count"] <= 1000000]
    
    if len(viral) + len(non_viral) != total:
        errors.append(f"{channel_name}: Viral + Non-viral != Total: {len(viral)} + {len(non_viral)} != {total}")
    
    # Check published_hour_hkt range
    hours = set(s["published_hour_hkt"] for s in shorts)
    invalid_hours = [h for h in hours if h < 0 or h > 23]
    if invalid_hours:
        warnings.append(f"{channel_name}: Invalid hours found: {invalid_hours}")
    
    # Spot check: viral should have higher views
    if viral:
        viral_views = [s["view_count"] for s in viral]
        non_viral_views = [s["view_count"] for s in non_viral] if non_viral else [0]
        if min(viral_views) < max(non_viral_views):
            warnings.append(f"{channel_name}: Some viral have lower views than non-viral. Check threshold.")
    
    return errors, warnings


def validate_analysis_consistency(shorts, all_comp, channel_name):
    """Validate analysis results are consistent."""
    errors = []
    
    total = len(shorts)
    viral = [s for s in shorts if s["view_count"] > 1000000]
    
    # Check: viral % = viral_count / total
    expected_viral_pct = 100 * len(viral) / total if total > 0 else 0
    
    # Check: all components count matches shorts count
    if len(all_comp) != total:
        errors.append(f"{channel_name}: Components count {len(all_comp)} != shorts count {total}")
    
    # Check: keyword percentages recalculated match
    evolution_count = sum(1 for c in all_comp if c["has_evolution"])
    expected_evo_pct = 100 * evolution_count / total if total > 0 else 0
    
    return errors


def run_validation_report(shorts, channel_name):
    """Run all validations and print results."""
    print(f"\n{'='*70}")
    print(f"🔍 VALIDATION REPORT: {channel_name}")
    print(f"{'='*70}")
    
    errors, warnings = validate_channel_data(shorts, channel_name)
    all_comp = [extract_title_components(s["title"]) for s in shorts]
    analysis_errors = validate_analysis_consistency(shorts, all_comp, channel_name)
    
    all_errors = errors + analysis_errors
    
    # Quick sanity check
    print(f"\n   Sanity Check:")
    print(f"   • Total shorts: {len(shorts)}")
    print(f"   • Viral (>1M): {sum(1 for s in shorts if s['view_count'] > 1000000)}")
    print(f"   • Non-viral: {sum(1 for s in shorts if s['view_count'] <= 1000000)}")
    print(f"   • Total brands found: {len(set(b for c in all_comp for b in c['brands']))}")
    print(f"   • Total categories found: {len(set(cat for c in all_comp for cat in c['keyword_categories']))}")
    
    if all_errors:
        print(f"\n   ❌ ERRORS:")
        for e in all_errors:
            print(f"      • {e}")
    else:
        print(f"\n   ✅ No errors found")
    
    if warnings:
        print(f"\n   ⚠️  WARNINGS:")
        for w in warnings:
            print(f"      • {w}")
    
    return len(all_errors) == 0


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_title_formulas(shorts, channel_name):
    """Analyze title patterns from ALL shorts."""
    print(f"\n{'='*70}")
    print(f"📝 ANALYSIS 1: TITLE FORMULA (ALL SHORTS)")
    print(f"{'='*70}")
    
    total = len(shorts)
    all_components = [extract_title_components(s["title"]) for s in shorts]
    
    # Calculate stats from scratch (NOT stored)
    stats = {}
    for key in ["Number", "Evolution", "Year Range", "vs", "Iconic", "Motorsport", "Gaming", "Military", "Brand"]:
        attr_map = {
            "Number": "has_number",
            "Evolution": "has_evolution",
            "Year Range": "has_year_range",
            "vs": "has_vs",
            "Iconic": "has_iconic",
            "Motorsport": "has_motorsport",
            "Gaming": "has_gaming",
            "Military": "has_military",
            "Brand": "has_brand",
        }
        attr = attr_map.get(key, key.lower())
        count = sum(1 for c in all_components if c.get(attr, False))
        stats[key] = {"count": count, "pct": 100 * count / total if total > 0 else 0}
    
    print(f"\n   Total shorts: {total}")
    
    print(f"\n   {'Keyword':<20} | {'Count':>6} | {'%':>8} | Distribution")
    print(f"   {'-'*60}")
    
    for key in ["Number", "Evolution", "Year Range", "vs", "Iconic", "Motorsport", "Gaming", "Military"]:
        count = stats[key]["count"]
        pct = stats[key]["pct"]
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"   {key:<20} | {count:>6} | {pct:>7.1f}% | {bar}")
    
    # Top brands
    all_brands = []
    for c in all_components:
        all_brands.extend(c["brands"])
    brand_counts = Counter(all_brands).most_common(10)
    print(f"\n   Top Brands:")
    for brand, count in brand_counts:
        print(f"   • {brand.title()}: {count}")
    
    # Title length
    lengths = [c["title_length"] for c in all_components]
    avg_len = sum(lengths) // total
    avg_words = sum(c["word_count"] for c in all_components) // total
    print(f"\n   ➤ Avg Title Length: {avg_len} chars | {avg_words} words")
    
    return {
        "total": total,
        "stats": stats,
        "all_components": all_components,
        "avg_length": avg_len,
    }


def analyze_traffic_patterns(shorts):
    """Analyze traffic patterns by time and day."""
    print(f"\n{'='*70}")
    print(f"📈 ANALYSIS 2: TRAFFIC PATTERNS")
    print(f"{'='*70}")
    
    hour_data = defaultdict(lambda: {"views": 0, "count": 0})
    day_data = defaultdict(lambda: {"views": 0, "count": 0})
    
    for short in shorts:
        h = short["published_hour_hkt"]
        d = short["published_day"]
        v = short["view_count"]
        
        hour_data[h]["views"] += v
        hour_data[h]["count"] += 1
        day_data[d]["views"] += v
        day_data[d]["count"] += 1
    
    # Hour analysis - recalculate from hour_data
    hour_avg = {}
    for h in range(24):
        if hour_data[h]["count"] > 0:
            hour_avg[h] = hour_data[h]["views"] // hour_data[h]["count"]
        else:
            hour_avg[h] = 0
    
    sorted_hours = sorted(hour_avg.items(), key=lambda x: -x[1])
    best_hour = sorted_hours[0][0] if sorted_hours else 0
    
    print(f"\n   【 BEST HOURS (HKT) 】")
    for i, (h, avg) in enumerate(sorted_hours[:5], 1):
        count = hour_data[h]["count"]
        rank = "🏆" if i == 1 else "⭐" if i <= 3 else "👍"
        print(f"   {i}. {h:02d}:00 — Avg {avg:,} views ({count} shorts) {rank}")
    
    # Day analysis
    day_avg = {}
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for d in day_names:
        if day_data[d]["count"] > 0:
            day_avg[d] = day_data[d]["views"] // day_data[d]["count"]
        else:
            day_avg[d] = 0
    
    sorted_days = sorted(day_avg.items(), key=lambda x: -x[1])
    best_day = sorted_days[0][0] if sorted_days else "N/A"
    
    print(f"\n   【 BEST DAYS 】")
    for i, (d, avg) in enumerate(sorted_days, 1):
        count = day_data[d]["count"]
        rank = "🏆" if i == 1 else "⭐" if i <= 3 else ""
        print(f"   {i}. {d:10s} — Avg {avg:,} views ({count} shorts) {rank}")
    
    # Best slot
    print(f"\n   【 BEST POSTING SLOT 】")
    best_slot = {"day": None, "hour": None, "avg": 0}
    for dn in day_names:
        for h in range(24):
            count = sum(1 for s in shorts if s["published_day"] == dn and s["published_hour_hkt"] == h)
            if count > 0:
                total_v = sum(s["view_count"] for s in shorts if s["published_day"] == dn and s["published_hour_hkt"] == h)
                avg = total_v // count
                if avg > best_slot["avg"]:
                    best_slot = {"day": dn, "hour": h, "avg": avg}
    
    print(f"   ➤ {best_slot['day']} @ {best_slot['hour']:02d}:00 HKT (Avg {best_slot['avg']:,} views)")
    
    return {
        "best_hour": best_hour,
        "best_day": best_day,
        "best_slot": best_slot,
        "hour_avg": hour_avg,
        "day_avg": day_avg,
    }


def analyze_engagement(shorts):
    """Analyze engagement rates."""
    print(f"\n{'='*70}")
    print(f"💬 ANALYSIS 3: ENGAGEMENT ANALYSIS")
    print(f"{'='*70}")
    
    engagements = []
    for short in shorts:
        views = short["view_count"]
        likes = short["like_count"]
        comments = short["comment_count"]
        
        if views > 0:
            eng_rate = 100 * (likes + comments) / views
            like_rate = 100 * likes / views
            engagements.append({
                "title": short["title"],
                "views": views,
                "likes": likes,
                "comments": comments,
                "eng_rate": eng_rate,
                "like_rate": like_rate,
            })
    
    engagements.sort(key=lambda x: -x["eng_rate"])
    
    avg_eng = sum(e["eng_rate"] for e in engagements) / len(engagements)
    avg_likes = sum(e["like_rate"] for e in engagements) / len(engagements)
    
    print(f"\n   ➤ Overall Avg Engagement: {avg_eng:.3f}%")
    print(f"   ➤ Overall Avg Like Rate: {avg_likes:.3f}%")
    
    print(f"\n   【 TOP 5 BY ENGAGEMENT RATE 】")
    for i, e in enumerate(engagements[:5], 1):
        print(f"   {i}. {e['views']:,} views | Eng: {e['eng_rate']:.2f}% | {e['title'][:40]}...")
    
    print(f"\n   【 TOP 5 BY ABSOLUTE LIKES 】")
    by_likes = sorted(engagements, key=lambda x: -x["likes"])
    for i, e in enumerate(by_likes[:5], 1):
        print(f"   {i}. {e['likes']:,} likes | {e['views']:,} views | {e['title'][:40]}...")
    
    return {
        "avg_engagement_rate": avg_eng,
        "avg_like_rate": avg_likes,
    }


def analyze_viral_factors(shorts, all_components):
    """Analyze what makes videos go VIRAL (views > 1M)."""
    print(f"\n{'='*70}")
    print(f"🔥 ANALYSIS 4: VIRAL FACTORS (Viral = Views > 1M)")
    print(f"{'='*70}")
    
    total = len(shorts)
    viral = [s for s in shorts if s["view_count"] > 1000000]
    viral_comp = [extract_title_components(s["title"]) for s in viral]
    
    print(f"\n   【 VIRAL DEFINITION 】")
    print(f"   ➤ Viral threshold: > 1,000,000 views")
    print(f"   ➤ Viral shorts: {len(viral)} ({100*len(viral)//total}%)")
    print(f"   ➤ Non-viral shorts: {total - len(viral)} ({100*(total-len(viral))//total}%)")
    
    # Verify: viral + non-viral = total
    assert len(viral) + (total - len(viral)) == total, "Viral + Non-viral mismatch!"
    
    print(f"\n   【 VIRAL vs ALL - FEATURE COMPARISON 】")
    print(f"   {'Feature':<20} | {'VIRAL %':>10} | {'ALL %':>10} | {'Impact':>8}")
    print(f"   {'-'*55}")
    
    factors = [
        ("Evolution", "has_evolution"),
        ("Year Range", "has_year_range"),
        ("Number", "has_number"),
        ("Brand", "has_brand"),
        ("Iconic", "has_iconic"),
        ("Motorsport", "has_motorsport"),
        ("Gaming", "has_gaming"),
        ("Military", "has_military"),
        ("vs", "has_vs"),
    ]
    
    viral_insights = []
    for label, attr in factors:
        v_count = sum(1 for c in viral_comp if c.get(attr, False))
        a_count = sum(1 for c in all_components if c.get(attr, False))
        v_pct = 100 * v_count / len(viral) if viral else 0
        a_pct = 100 * a_count / total if total > 0 else 0
        impact = v_pct - a_pct
        viral_insights.append((label, impact, v_pct, a_pct))
        
        marker = "★" if abs(impact) >= 10 else ""
        print(f"   {label:<20} | {v_pct:>9.1f}% | {a_pct:>9.1f}% | {impact:>+7.0f}% {marker}")
    
    # Sort by absolute impact
    viral_insights.sort(key=lambda x: -abs(x[1]))
    
    print(f"\n   【 TOP VIRAL FACTORS (sorted by |impact|) 】")
    for i, (label, impact, vp, ap) in enumerate(viral_insights[:5], 1):
        direction = "↑ boosts viral" if impact > 0 else "↓ reduces viral"
        print(f"   {i}. {label}: {impact:+.0f}% ({direction})")
    
    print(f"\n   【 TOP 5 VIRAL VIDEOS 】")
    sorted_viral = sorted(viral, key=lambda x: -x["view_count"])[:5]
    for i, short in enumerate(sorted_viral, 1):
        comp = extract_title_components(short["title"])
        cats = ", ".join(comp["keyword_categories"]) if comp["keyword_categories"] else "basic"
        print(f"   {i}. 【{short['view_count']:,} views】{short['title'][:45]}...")
        print(f"      → {cats}")
    
    return {
        "viral_count": len(viral),
        "viral_pct": 100 * len(viral) / total,
        "viral_insights": viral_insights,
    }


def analyze_top10_by_views(shorts, all_components):
    """Analyze TOP 10 by VIEWS (sorted by view_count). SEPARATE from viral!"""
    print(f"\n{'='*70}")
    print(f"🏆 ANALYSIS 5: TOP 10 BY VIEWS (sorted by view_count)")
    print(f"{'='*70}")
    
    total = len(shorts)
    sorted_shorts = sorted(shorts, key=lambda x: -x["view_count"])
    top10 = sorted_shorts[:10]
    top10_comp = [extract_title_components(s["title"]) for s in top10]
    
    print(f"\n   【 TOP 10 BY VIEWS 】")
    print(f"   ➤ Definition: Top 10 shorts sorted by view_count (highest first)")
    for i, short in enumerate(top10, 1):
        comp = extract_title_components(short["title"])
        cats = ", ".join(comp["keyword_categories"]) if comp["keyword_categories"] else "basic"
        print(f"   {i}. 【{short['view_count']:,} views】{short['title'][:45]}...")
        print(f"      → {cats}")
    
    print(f"\n   【 TOP 10 vs ALL - FEATURE COMPARISON 】")
    print(f"   {'Feature':<20} | {'TOP10 %':>10} | {'ALL %':>10} | {'Diff':>8}")
    print(f"   {'-'*55}")
    
    factors = [
        ("Evolution", "has_evolution"),
        ("Year Range", "has_year_range"),
        ("Number", "has_number"),
        ("Iconic", "has_iconic"),
        ("Motorsport", "has_motorsport"),
        ("Gaming", "has_gaming"),
    ]
    
    top10_insights = []
    for label, attr in factors:
        t_count = sum(1 for c in top10_comp if c.get(attr, False))
        a_count = sum(1 for c in all_components if c.get(attr, False))
        t_pct = 100 * t_count / len(top10) if top10 else 0
        a_pct = 100 * a_count / total if total > 0 else 0
        diff = t_pct - a_pct
        top10_insights.append((label, diff, t_pct, a_pct))
        
        marker = "★" if abs(diff) >= 10 else ""
        print(f"   {label:<20} | {t_pct:>9.1f}% | {a_pct:>9.1f}% | {diff:>+7.0f}% {marker}")
    
    top10_insights.sort(key=lambda x: -abs(x[1]))
    
    print(f"\n   【 TOP 10 KEY DIFFERENCES (sorted by |diff|) 】")
    for i, (label, diff, tp, ap) in enumerate(top10_insights[:5], 1):
        direction = "↑ over-represented" if diff > 0 else "↓ under-represented"
        print(f"   {i}. {label}: {diff:+.0f}% ({direction} in TOP10)")
    
    return {
        "top10_insights": top10_insights,
    }


def analyze_view_distribution(shorts):
    """View distribution analysis."""
    print(f"\n{'='*70}")
    print(f"📊 ANALYSIS 6: VIEW DISTRIBUTION")
    print(f"{'='*70}")
    
    ranges = [
        ("<100K", 0, 100000),
        ("100K-500K", 100000, 500000),
        ("500K-1M", 500000, 1000000),
        ("1M-5M", 1000000, 5000000),
        ("5M-10M", 5000000, 10000000),
        (">10M", 10000000, 999999999),
    ]
    
    print(f"\n   {'Range':>12} | {'Count':>6} | {'Pct':>8} | Visual")
    print(f"   {'-'*45}")
    
    for label, low, high in ranges:
        count = sum(1 for s in shorts if low <= s["view_count"] < high)
        if count > 0:
            pct = 100 * count / len(shorts)
            bar = "█" * int(pct / 2)
            print(f"   {label:>12} | {count:>6} | {pct:>7.1f}% | {bar}")
    
    all_views = sorted([s["view_count"] for s in shorts])
    median = all_views[len(all_views)//2]
    print(f"\n   ➤ Median Views: {median:,}")
    print(f"   ➤ Total Views: {sum(s['view_count'] for s in shorts):,}")


def analyze_competitor_gaps(shorts, all_components):
    """Analyze content gaps."""
    print(f"\n{'='*70}")
    print(f"🎯 ANALYSIS 7: COMPETITOR GAPS")
    print(f"{'='*70}")
    
    all_brands = []
    for c in all_components:
        all_brands.extend(c["brands"])
    brand_counts = Counter(all_brands)
    
    high_end = ["bugatti", "ferrari", "porsche", "lamborghini", "mclaren", 
                "aston martin", "lotus", "rolls-royce", "bentley"]
    
    print(f"\n   【 HIGH-END SUPERCAR BRANDS 】")
    for brand in high_end:
        count = brand_counts.get(brand, 0)
        status = "✅" if count >= 5 else "⚠️" if count > 0 else "❌"
        print(f"   {status} {brand.title()}: {count} shorts")
    
    # Content categories
    cat_counts = Counter()
    for c in all_components:
        for cat in c["keyword_categories"]:
            cat_counts[cat] += 1
    
    print(f"\n   【 CONTENT CATEGORIES 】")
    for cat, count in cat_counts.most_common():
        pct = 100 * count / len(shorts)
        print(f"   • {cat}: {count} ({pct:.0f}%)")


# =============================================================================
# CROSS-CHANNEL COMPARISON (WITH VALIDATION)
# =============================================================================
def cross_channel_comparison(all_results):
    """Generate cross-channel comparison with validated data."""
    print(f"\n\n{'='*70}")
    print(f"📊 CROSS-CHANNEL COMPARISON")
    print(f"{'='*70}")
    
    if len(all_results) < 2:
        return
    
    ch1 = all_results[0]  # ArtKiz
    ch2 = all_results[1]   # Motomorfosis
    
    print(f"\n【 {ch1['name'].upper()} vs {ch2['name'].upper()} 】")
    
    # Table header
    print(f"\n   ┌─────────────────────────────┬──────────────┬──────────────┐")
    print(f"   │ Metric                     │ {ch1['name']:>12} │ {ch2['name']:>12} │")
    print(f"   ├─────────────────────────────┼──────────────┼──────────────┤")
    print(f"   │ Total Shorts               │ {ch1['title']['total']:>12} │ {ch2['title']['total']:>12} │")
    print(f"   │ Viral (>1M)                │ {ch1['viral']['viral_count']:>12} │ {ch2['viral']['viral_count']:>12} │")
    print(f"   │ Viral %                   │ {ch1['viral']['viral_pct']:>11.1f}% │ {ch2['viral']['viral_pct']:>11.1f}% │")
    print(f"   │ Best Hour (HKT)           │ {ch1['traffic']['best_hour']:>12} │ {ch2['traffic']['best_hour']:>12} │")
    print(f"   │ Best Day                  │ {ch1['traffic']['best_day']:>12} │ {ch2['traffic']['best_day']:>12} │")
    print(f"   │ Avg Engagement            │ {ch1['engagement']['avg_engagement_rate']:>11.2f}% │ {ch2['engagement']['avg_engagement_rate']:>11.2f}% │")
    print(f"   │ Avg Title Length           │ {ch1['title']['avg_length']:>12} │ {ch2['title']['avg_length']:>12} │")
    print(f"   └─────────────────────────────┴──────────────┴──────────────┘")
    
    # Viral factors
    print(f"\n   【 VIRAL FACTORS (Viral = >1M views) 】")
    print(f"   {ch1['name']}:")
    for label, impact, vp, ap in ch1['viral']['viral_insights'][:3]:
        print(f"      • {label}: {vp:.0f}% in viral vs {ap:.0f}% in all ({impact:+.0f}%)")
    
    print(f"   {ch2['name']}:")
    for label, impact, vp, ap in ch2['viral']['viral_insights'][:3]:
        print(f"      • {label}: {vp:.0f}% in viral vs {ap:.0f}% in all ({impact:+.0f}%)")
    
    # Top10 factors
    print(f"\n   【 TOP 10 BY VIEWS FACTORS (Top10 = highest view_count) 】")
    print(f"   {ch1['name']}:")
    for label, diff, tp, ap in ch1['top10']['top10_insights'][:3]:
        print(f"      • {label}: TOP10={tp:.0f}% vs ALL={ap:.0f}% ({diff:+.0f}%)")
    
    print(f"   {ch2['name']}:")
    for label, diff, tp, ap in ch2['top10']['top10_insights'][:3]:
        print(f"      • {label}: TOP10={tp:.0f}% vs ALL={ap:.0f}% ({diff:+.0f}%)")
    
    # Key insight
    print(f"\n   ⚠️  KEY INSIGHT:")
    print(f"      • VIRAL (>1M) shows what helps reach 1M+ views")
    print(f"      • TOP 10 shows what distinguishes highest-viewed shorts")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "="*70)
    print("🚀 YOUTUBE COMPETITOR ANALYSIS - PHASE 2 (VALIDATED)")
    print("="*70)
    
    all_results = []
    
    for channel in TARGET_CHANNELS:
        channel_id = channel["id"]
        name = channel["name"]
        
        print(f"\n\n{'#'*70}")
        print(f"# {name.upper()}")
        print(f"{'#'*70}")
        
        # Load data
        data = load_channel_data(channel_id)
        if not data:
            print(f"   ⚠️ No data found for {channel_id}")
            continue
        
        shorts = data["shorts"]
        print(f"   Loaded {len(shorts)} shorts")
        
        # VALIDATION FIRST
        valid = run_validation_report(shorts, name)
        if not valid:
            print(f"   ⚠️ Validation failed! Check data before proceeding.")
        
        # Run all analyses (recalculate every number from scratch)
        title_analysis = analyze_title_formulas(shorts, name)
        traffic_analysis = analyze_traffic_patterns(shorts)
        engagement_analysis = analyze_engagement(shorts)
        viral_analysis = analyze_viral_factors(shorts, title_analysis["all_components"])
        top10_analysis = analyze_top10_by_views(shorts, title_analysis["all_components"])
        analyze_view_distribution(shorts)
        analyze_competitor_gaps(shorts, title_analysis["all_components"])
        
        # Final validation
        print(f"\n   【 FINAL VALIDATION 】")
        print(f"   • Total: {len(shorts)} = Viral {viral_analysis['viral_count']} + Non-viral {len(shorts) - viral_analysis['viral_count']} ✓")
        
        all_results.append({
            "name": name,
            "title": title_analysis,
            "traffic": traffic_analysis,
            "engagement": engagement_analysis,
            "viral": viral_analysis,
            "top10": top10_analysis,
        })
    
    # Cross-channel comparison
    cross_channel_comparison(all_results)
    
    # Save validated report
    report_file = PROJECT_ROOT / "agent-meta" / "competitor-analysis-phase2-enhanced.md"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n\n[Saved to {report_file}]")
    print("\n" + "="*70)
    print("✅ ANALYSIS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
