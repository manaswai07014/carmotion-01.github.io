#!/usr/bin/env python3
"""
trend_monitor_v2.py
===================
Google Trends monitoring with triple fallback chain:
  1. pytrends (Google Trends API) — if module installed + quota available
  2. Google News RSS — fallback, no quota needed
  3. Cached data + warning — if all above fail

Key improvements over v1:
  - pytrends import is conditional (no crash on missing module)
  - All exceptions are caught with meaningful error messages
  - Data freshness is ALWAYS reported
  - Fallback chain is guaranteed to produce output

Usage:
    python3 scripts/trend_monitor_v2.py [--save]
"""

import json, ssl, time, re, sys
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"
REPORT = BASE / "agent-meta" / "trend-report.md"
LOG   = BASE / "wiki" / "log.md"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Car-related keywords to monitor
KEYWORDS = [
    "Ferrari", "Lamborghini", "Porsche 911", "Toyota Supra", "Nissan GT-R",
    "Honda NSX", "Mazda RX-7", "BMW M3", "Mercedes AMG", "Tesla Model 3",
    "GTR R35", "GR Supra", "JDM", "drift car", "electric supercar", "hypercar",
]

SPIKE_THRESHOLD = 70
REGION = 'US'

# ─────────────────────────────────────────
# Data Source 1: Google News RSS (always works, no quota)
# ─────────────────────────────────────────

def fetch_google_news_scores() -> tuple[list, str]:
    """
    Fetch trend proxy scores from Google News RSS.
    Returns (results_list, source_label).
    """
    news_queries = {
        "Ferrari": "Ferrari supercar news",
        "Lamborghini": "Lamborghini supercar news",
        "Porsche 911": "Porsche 911 news",
        "Toyota Supra": "Toyota Supra news",
        "Nissan GT-R": "Nissan GT-R news",
        "Honda NSX": "Honda NSX news",
        "Mazda RX-7": "Mazda RX-7 news",
        "BMW M3": "BMW M3 news",
        "Mercedes AMG": "Mercedes AMG news",
        "Tesla Model 3": "Tesla Model 3 news",
        "GTR R35": "Nissan GT-R R35 news",
        "GR Supra": "Toyota GR Supra news",
        "JDM": "JDM cars news",
        "drift car": "drift car news",
        "electric supercar": "electric supercar news",
        "hypercar": "hypercar news",
    }

    results = []
    base_url = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

    for kw, query in news_queries.items():
        url = base_url.format(q=urllib.parse.quote(query))
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
                raw = resp.read()

            root = ET.fromstring(raw)
            items = root.findall('.//item')
            article_count = len(items)

            # Score: article count capped, boost for high coverage
            score = min(article_count * 3, 100)

            results.append({
                "keyword": kw,
                "score": score,
                "status": "google_news",
                "articles": article_count,
            })
            time.sleep(0.5)  # Be respectful

        except Exception as e:
            results.append({
                "keyword": kw,
                "score": 10,  # Minimal score on error
                "status": "error",
                "error": str(e)[:60],
            })

    return results, "Google News RSS (article mentions as trend proxy)"


# ─────────────────────────────────────────
# Data Source 2: pytrends (if available)
# ─────────────────────────────────────────

def fetch_pytrends_scores() -> tuple[list, str, bool]:
    """
    Try to fetch using pytrends. Returns (results, source, success).
    Does NOT crash on import error — returns (empty, '', False) instead.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return [], "", False

    results = []
    pytrends = TrendReq(hl='en-US', tz=360, timeout=15)

    chunk_size = 5
    for i in range(0, len(KEYWORDS), chunk_size):
        chunk = KEYWORDS[i:i + chunk_size]
        try:
            pytrends.build_payload(chunk, cat=47, timeframe='now 7-d', geo=REGION)
            interest = pytrends.interest_over_time()

            for kw in chunk:
                if kw in interest.columns and not interest[kw].empty:
                    avg = interest[kw].mean()
                    score = min(int(avg), 100)
                else:
                    score = 0
                results.append({
                    "keyword": kw,
                    "score": score,
                    "status": "google_trends",
                })
            time.sleep(1)

        except Exception as e:
            err_msg = str(e)
            # 429 = quota exceeded
            if "429" in err_msg or "quota" in err_msg.lower():
                return [], "google_trends_quota_exceeded", False
            # Other errors — add error markers
            for kw in chunk:
                results.append({
                    "keyword": kw,
                    "score": 0,
                    "status": "error",
                    "error": err_msg[:60],
                })

    return results, "Google Trends API (live)", len(results) > 0


# ─────────────────────────────────────────
# Data Source 3: Read from cache (last resort)
# ─────────────────────────────────────────

def load_cached_report() -> tuple[list, str]:
    """Load last successful trend report as fallback."""
    if not REPORT.exists():
        return [], ""
    content = REPORT.read_text(encoding='utf-8')
    results = []
    source = ""
    for line in content.split('\n'):
        m = re.search(r'\*\*(.+?)\*\*.*?[\u2014\-]\s+score:\s*(\d+)', line)
        if m:
            results.append({
                "keyword": m.group(1).strip(),
                "score": int(m.group(2)),
                "status": "cached",
            })
        if 'Data Source' in line and ':' in line:
            source = line.split(':', 1)[1].strip()
    return results, source


# ─────────────────────────────────────────
# Queue Management
# ─────────────────────────────────────────

def read_queue():
    if not QUEUE.exists():
        return []
    with open(QUEUE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def write_queue(items):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

def append_log(msg):
    if not LOG.exists():
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{now}] [TREND-V2] {msg}\n")


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    save = '--save' in sys.argv
    results = []
    data_source = ""
    data_freshness = ""

    # ── Step 1: Try pytrends ──────────────────────────
    print(f"🔍 Fetching trend data for {len(KEYWORDS)} keywords...")
    pytrends_results, pytrends_source, pytrends_ok = fetch_pytrends_scores()

    if pytrends_ok and pytrends_results:
        results = pytrends_results
        data_source = pytrends_source
        data_freshness = "LIVE"
        print(f"  ✅ Source 1: pytrends succeeded — {len(results)} keywords")
    else:
        print(f"  ⚠️  Source 1: pytrends {'unavailable (quota exceeded)' if pytrends_source == 'google_trends_quota_exceeded' else 'failed or missing'}")

        # ── Step 2: Try Google News RSS ─────────────────
        print(f"  🔄 Trying Google News RSS fallback...")
        try:
            gn_results, gn_source = fetch_google_news_scores()
            valid_gn = [r for r in gn_results if r['status'] == 'google_news' and r['articles'] > 0]
            if valid_gn:
                results = gn_results
                data_source = gn_source
                data_freshness = "LIVE"
                print(f"  ✅ Source 2: Google News RSS succeeded — {len(valid_gn)} keywords with articles")
            else:
                raise Exception("No valid Google News results")
        except Exception as e:
            print(f"  ⚠️  Source 2: Google News RSS failed — {e}")

            # ── Step 3: Load cached data ───────────────
            cached_results, cached_source = load_cached_report()
            if cached_results:
                results = cached_results
                data_source = f"CACHED (original: {cached_source})"
                data_freshness = "STALE"
                print(f"  ⚠️  Source 3: Using cached data from {REPORT.stat().st_mtime}")
            else:
                print(f"  ❌ ALL SOURCES FAILED — cannot generate trend report")
                return

    # ── Sort and analyze ───────────────────────────────
    results.sort(key=lambda x: x["score"], reverse=True)
    spikes = [r for r in results if r["score"] >= SPIKE_THRESHOLD]

    # ── Display ────────────────────────────────────────
    print(f"\n📊 Top 5 Keywords ({data_source}):")
    print("-" * 55)
    for i, r in enumerate(results[:5], 1):
        spike_icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 40 else "⚪")
        status_tag = f"[{r['status']}]" if r['status'] not in ('google_trends', 'google_news') else ""
        print(f"  {i}. {r['keyword']:<20} █{'█' * (r['score']//5):<20} {r['score']:>3} {spike_icon} {status_tag}")

    print(f"\n📋 Data Freshness: {data_freshness}")

    if spikes:
        print(f"\n🔴 Spikes detected (>= {SPIKE_THRESHOLD}):")
        queue = read_queue()
        new_tasks = 0
        for s in spikes:
            already = any(q.get("keyword") == s["keyword"] for q in queue)
            if not already:
                task = {
                    "keyword": s["keyword"],
                    "score": s["score"],
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": data_source,
                    "priority": "high" if s["score"] >= 80 else "medium",
                    "status": "pending",
                }
                queue.append(task)
                new_tasks += 1
                print(f"  + Added: {s['keyword']} (score: {s['score']})")
            else:
                print(f"  = Already queued: {s['keyword']}")

        if new_tasks > 0:
            write_queue(queue)
            append_log(f"{new_tasks} new spike task(s) added from {data_source}")

    # ── Write Report ────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top5 = results[:5]

    report_lines = [
        f"# Trend Report — {now}",
        "",
        "## ⚠️ DATA FRESHNESS",
        f"- **Status:** {data_freshness}",
        f"- **Source:** {data_source}",
        f"- **Generated:** {now} HKT",
        "",
        "## Data Source",
        f"- **{data_source}**",
        f"- Region: {REGION} | Timeframe: 7 days | Category: Autos & Vehicles",
        "",
        "## Scan Summary",
        f"- Keywords scanned: {len(KEYWORDS)}",
        f"- Spikes (>= {SPIKE_THRESHOLD}): {len(spikes)}",
        "",
        "## Top 5 Keywords",
    ]

    for i, r in enumerate(top5, 1):
        icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 50 else "⚪")
        status_tag = f"[{r['status']}]" if r['status'] not in ('google_trends', 'google_news') else ""
        report_lines.append(f"{i}. **{r['keyword']}** — score: {r['score']} {icon} {status_tag}")

    report_lines += ["", "## All Keywords"]
    for r in results:
        icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 50 else "⚪")
        status_tag = f"[{r['status']}]" if r['status'] not in ('google_trends', 'google_news') else ""
        report_lines.append(f"- {r['keyword']}: {r['score']} {icon} {status_tag}")

    report_lines.append("")
    report_lines.append(f"_Report generated: {now}_")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report_lines), encoding="utf-8")
    append_log(f"Trend scan complete — {len(spikes)} spikes — {data_source} — Freshness: {data_freshness}")

    print(f"\n✅ Report saved: {REPORT}")
    print(f"📋 Queue: {len(read_queue())} task(s)")

    if data_freshness == "STALE":
        print("\n⚠️  WARNING: Using STALE cached data. Check network/API status.")

    return 0 if data_freshness != "STALE" else 1  # exit code 1 = warning


if __name__ == "__main__":
    sys.exit(main())
