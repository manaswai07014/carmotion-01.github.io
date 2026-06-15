#!/usr/bin/env python3
"""
test_regex_parsing.py
=====================
Unit tests for critical regex patterns used in car-evolution-project scripts.

Run: python3 scripts/test_regex_parsing.py
Exit 0 = all pass, Exit 1 = failures
"""

import re, sys
from pathlib import Path

BASE = Path(__file__).parent.parent

# ─────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────
FAILURES = []

def assert_equal(got, expected, test_name):
    if got == expected:
        print(f"  ✅ {test_name}")
        return True
    else:
        print(f"  ❌ {test_name}")
        print(f"     Expected: {expected!r}")
        print(f"     Got:      {got!r}")
        FAILURES.append(test_name)
        return False

def assert_match(pattern, text, expected, test_name):
    """Test regex match/search."""
    m = re.search(pattern, text)
    got = m.group(1) if m else None
    return assert_equal(got, expected, test_name)

# ─────────────────────────────────────────
# topic_priority_v2.py regex tests
# ─────────────────────────────────────────
print("=" * 60)
print("topic_priority_v2.py regex tests")
print("=" * 60)

# V2 trend parsing — em-dash, en-dash, hyphen
v2_trend_tests = [
    ("**Ferrari** — score: 85", "Ferrari", 85),
    ("**Porsche** — score: 72", "Porsche", 72),  # em-dash
    ("**McLaren** - score: 68", "McLaren", 68),
    ("**Bugatti**  score: 95", None, None),  # no separator
    ("No markdown here — score: 50", None, None),  # no bold
]
for text, exp_brand, exp_score in v2_trend_tests:
    pattern = r'\*\*(.+?)\*\*.*?[\u2014\-]\s+score:\s*(\d+)'
    m = re.search(pattern, text)
    if exp_brand is None:
        assert m is None, f"Expected no match for: {text!r}"
        print(f"  ✅ No match (expected): {text[:40]}")
    else:
        if m:
            assert_equal(m.group(1), exp_brand, f"V2 trend brand: {text[:40]}")
            assert_equal(int(m.group(2)), exp_score, f"V2 trend score: {text[:40]}")
        else:
            FAILURES.append(f"V2 trend match: {text[:40]}")
            print(f"  ❌ V2 trend match: {text[:40]} — expected ({exp_brand}, {exp_score})")

# V2 News parsing — bold items in daily-brief (strip leading "N. " prefix)
v2_news_tests = [
    ("**1. Ferrari 488 GTB** — some description here", "Ferrari 488 GTB"),
    ("**5. McLaren P1** — another description", "McLaren P1"),
    ("**10. Bugatti Chiron**", "Bugatti Chiron"),
    ("**Ferrari F40**", "Ferrari F40"),  # no number
    ("No bold here at all", None),
    ("*Italic text*", None),
]
for text, exp_title in v2_news_tests:
    m = re.search(r'\*\*(.+?)\*\*', text)
    got = m.group(1).strip() if m else None
    # Strip leading number
    if got and re.match(r'\d+\.\s+', got):
        got = re.sub(r'^\d+\.\s+', '', got)
    assert_equal(got, exp_title, f"V2 news title: {text[:40]}")

# Score normalization (actual formula: min(yt_total * 0.02, 25))
score_tests = [
    (0, 0),
    (500, 10),
    (1000, 20),
    (2000, 25),
    (5000, 25),
    (10000, 25),
    (20000, 25),
]
for raw, expected in score_tests:
    norm = min(int(raw * 0.02), 25)
    assert_equal(norm, expected, f"score_norm({raw})")

# ─────────────────────────────────────────
# daily_news_fetcher.py regex tests
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("daily_news_fetcher.py regex tests")
print("=" * 60)

# RSS date parsing (RFC 2822)
date_tests = [
    ("Mon, 05 May 2025 12:00:00 GMT", True),
    ("Tue, 01 Jan 2024 00:00:00 +0000", True),
    ("05 May 2025 12:00:00", False),  # missing day
]
for text, should_parse in date_tests:
    pattern = r'\w\w\w,?\s+\d{1,2}\s+\w\w\w\s+\d{4}\s+\d{2}:\d{2}:\d{2}'
    m = re.search(pattern, text)
    got = m is not None
    assert_equal(got, should_parse, f"RSS date: {text[:40]}")

# Article URL extraction from Google News RSS
url_tests = [
    ("https://news.google.com/rss/articles/ABC123?oc=5", "ABC123"),
    ("https://news.google.com/rss/search?q=test", None),  # search, not article
]
for text, exp_id in url_tests:
    m = re.search(r'articles/([A-Za-z0-9_-]+)', text)
    got = m.group(1) if m else None
    assert_equal(got, exp_id, f"article ID: {text[:50]}")

# ─────────────────────────────────────────
# trend_monitor_v2.py regex tests
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("trend_monitor_v2.py regex tests")
print("=" * 60)

# Keyword extraction from RSS title
# trend_monitor_v2 uses: re.match(r'([^:\-]+)', title) — takes text before first colon/dash
# If no colon/dash, captures the whole title
rss_title_tests = [
    ("Ferrari 488 GTB: everything you need to know", "Ferrari 488 GTB"),
    ("McLaren P1 - the ultimate hybrid hypercar", "McLaren P1"),
    ("Top Gear's Best Cars of 2025", "Top Gear's Best Cars of 2025"),  # whole title (no colon/dash)
    ("Bugatti Chiron Super Sport 300+ review", "Bugatti Chiron Super Sport 300+ review"),  # whole title
]
for title, exp_kw in rss_title_tests:
    # First keyword-like phrase before colon/dash
    m = re.match(r'([^:\-]+)', title)
    got = m.group(1).strip() if m else None
    assert_equal(got, exp_kw, f"RSS keyword: {title[:40]}")

# Score from Google News article count
gn_count_tests = [
    ("About 1,000 results", 1000),
    ("About 500 results", 500),
    ("About 2 results", 2),
    ("1 result", 1),
]
for text, exp_count in gn_count_tests:
    m = re.search(r'About\s+([\d,]+)\s+results', text)
    if m:
        got = int(m.group(1).replace(',', ''))
    else:
        m2 = re.search(r'([\d,]+)\s+result', text)
        got = int(m2.group(1).replace(',', '')) if m2 else 0
    assert_equal(got, exp_count, f"GN count: {text}")

# ─────────────────────────────────────────
# daily_competitor_report_v2.py regex tests
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("daily_competitor_report_v2.py regex tests")
print("=" * 60)

# Duration parsing (ISO 8601)
duration_tests = [
    ("PT1H30M45S", 1*3600 + 30*60 + 45),
    ("PT30S", 30),
    ("PT1H", 3600),
    ("PT2M30S", 150),
    ("PT0S", 0),
    ("PT1H2M3S", 3600 + 120 + 3),
]
for dur, exp_sec in duration_tests:
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur)
    h = int(m.group(1)) if m.group(1) else 0
    mi = int(m.group(2)) if m.group(2) else 0
    s = int(m.group(3)) if m.group(3) else 0
    got = h*3600 + mi*60 + s
    assert_equal(got, exp_sec, f"duration {dur}")

# Hashtag extraction
hashtag_tests = [
    ("#Ferrari #CarHistory #Shorts", ["Ferrari", "CarHistory", "Shorts"]),
    ("No hashtags here", []),
    ("#JDM #Evolution #Car", ["JDM", "Evolution", "Car"]),
]
for text, exp_tags in hashtag_tests:
    got = re.findall(r'#(\w+)', text)
    assert_equal(got, exp_tags, f"hashtags: {text}")

# ─────────────────────────────────────────
# Summary
# ─────────────────────────────────────────
print("\n" + "=" * 60)
if FAILURES:
    print(f"❌ {len(FAILURES)} test(s) FAILED:")
    for f in FAILURES:
        print(f"   - {f}")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED")
    sys.exit(0)
