#!/usr/bin/env python3
"""Targeted regression test: Aston Martin Dreadnought article.

Before fix: og:image (-1.jpg) passed but <img> candidates (-2,-3,-4) were
filtered out by overly strict title_tokens + year path filter.

After fix: expanded brand/model alias tokens + relaxed year-free publisher
paths + URL path substring match should let all 4 real images through.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Clear cached pyc to ensure fresh code
for mod in list(sys.modules):
    if 'news_image_extractor' in mod:
        del sys.modules[mod]

from news_image_extractor import extract_images_for_post, _decode_gnews, _extract_images_from_html, _fetch
import urllib.parse

# The Google News URL from the 2026-07-19 Aston Martin Dreadnought post
GNEWS_URL = ("https://news.google.com/rss/articles/CBMiswFBVV95cUxOS3ZkQWpNZGstaldBbURXMlFvZldh"
             "ZDBUM1hjUWlSc0tJdFdEdW9mdHJKM0pRMFhkaUR3YWNzdFBkUVdLR0lSY3djaE5UTmwwWWhI"
             "Zmo0SFpLZ3lOcW5za2FMVzR4dDd0TzFvMFBiNGZBcGNRR3RFbmprcVFmSzlTZUFOZE14WnFQ"
             "dkJPVnFJVkU5ajBfTndOaXhJYXladmRJaE9PS3otb3h2d1IwbnNuaEU2VQ?oc=5")
SLUG = "take-cover-aston-martin-has-built-a-massive-military-grade-v12-supertr"

print("=" * 72)
print("REGRESSION TEST: Aston Martin Dreadnought (TopGear article)")
print("=" * 72)

# Step 1: Decode URL to see original
print("\n[1] Decode Google News URL...")
real_url = _decode_gnews(GNEWS_URL)
if not real_url:
    print("  ✗ DECODE FAILED — cannot continue test")
    sys.exit(1)
print(f"  → {real_url}")

# Step 2: Fetch HTML
print("\n[2] Fetch source HTML...")
code, body = _fetch(real_url, timeout=15)
print(f"  HTTP {code}, {len(body) if isinstance(body,(bytes,bytearray)) else 0} bytes")
if code != 200:
    print("  ✗ FETCH FAILED")
    sys.exit(1)
html = body.decode("utf-8", errors="replace")

# Step 3: Extract candidates — inspect what filter lets through
print("\n[3] Extract image candidates (with NEW filter)...")
source_host = (urllib.parse.urlparse(real_url).hostname or "").replace("www.", "")
candidates = _extract_images_from_html(html, real_url, source_host)
print(f"  Found {len(candidates)} candidate images:")
for i, c in enumerate(candidates, 1):
    print(f"    [{i}] attr={c['attr']:14s} width_hint={c.get('width_hint',0):5d}  url={c['url'][:100]}")

# Step 4: Full download pipeline
print("\n[4] Run full extract_images_for_post() (downloads top 4)...")
results = extract_images_for_post(GNEWS_URL, SLUG, max_images=4)
print(f"\n  Downloaded {len(results)} images:")
for r in results:
    print(f"    ✓ {r['local_path']}  ({r['size_bytes']//1024}KB)  via {r['source_host']}")
    print(f"      src: {r['src_url'][:120]}")

# Step 5: Verdict
print("\n" + "=" * 72)
expected = 3  # at least 3 real images (1 og + 2+ img)
if len(results) >= expected:
    print(f"✅ PASS — got {len(results)} images (expected ≥{expected})")
else:
    print(f"❌ FAIL — got only {len(results)} images (expected ≥{expected})")
print("=" * 72)
