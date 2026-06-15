#!/usr/bin/env python3
# scripts/trend_monitor.py
# Real Google Trends monitoring using pytrends (with fallback to Google News RSS)
# Note: queue.py was renamed to queue_tool.py to avoid stdlib conflict

import json, ssl, time, re, urllib.parse
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib.request

# Lazy import pytrends — if missing, fallback to Google News RSS automatically
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"
REPORT = BASE / "agent-meta" / "trend-report.md"
LOG   = BASE / "wiki" / "log.md"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Real car-related keywords to monitor
KEYWORDS = [
    "Ferrari",
    "Lamborghini",
    "Porsche 911",
    "Toyota Supra",
    "Nissan GT-R",
    "Honda NSX",
    "Mazda RX-7",
    "BMW M3",
    "Mercedes AMG",
    "Tesla Model 3",
    "GTR R35",
    "GR Supra",
    "JDM",
    "drift car",
    "electric supercar",
    "hypercar",
]

SPIKE_THRESHOLD = 70
REGION = 'US'

def _parse_pubdate(text):
    """Parse RFC 822 / RFC 2822 pubDate. Returns datetime or None."""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(text)
    except Exception:
        return None


def fetch_trends_google_news():
    """
    Fetch real trend data from Google News RSS feeds.
    Scoring: recency-weighted article count (0-100 scale, normalized across all keywords).
    """
    news_queries = {
        "Ferrari": "Ferrari supercar",
        "Lamborghini": "Lamborghini supercar",
        "Porsche 911": "Porsche 911",
        "Toyota Supra": "Toyota Supra",
        "Nissan GT-R": "Nissan GT-R",
        "Honda NSX": "Honda NSX",
        "Mazda RX-7": "Mazda RX-7",
        "BMW M3": "BMW M3",
        "Mercedes AMG": "Mercedes AMG",
        "Tesla Model 3": "Tesla Model 3",
        "GTR R35": "Nissan GT-R R35",
        "GR Supra": "Toyota GR Supra",
        "JDM": "JDM cars",
        "drift car": "drift car",
        "electric supercar": "electric supercar",
        "hypercar": "hypercar",
    }

    results = []
    base_url = "https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en"
    now = datetime.utcnow()

    for kw, query in news_queries.items():
        try:
            url = base_url.format(q=urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
                raw = resp.read()

            root = ET.fromstring(raw)
            items = root.findall('.//item')

            article_count = len(items)
            total_score = 0

            for item in items:
                pub = item.find('pubDate')
                if pub is None or not pub.text:
                    total_score += 0   # no date = no score
                    continue

                dt = _parse_pubdate(pub.text)
                if dt is None:
                    total_score += 0
                    continue

                # Make it timezone-naive UTC for comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                age_hours = (now - dt).total_seconds() / 3600

                # Recency weight: articles in last 24h get up to 3pts, decaying linearly
                if age_hours <= 24:
                    weight = 3.0 * (1 - age_hours / 24)   # 3→0 over 24h
                elif age_hours <= 72:
                    weight = 1.0 * (1 - (age_hours - 24) / 48)  # 1→0 over next 48h
                else:
                    weight = 0  # older than 72h = 0

                total_score += weight

            results.append({
                "keyword": kw,
                "raw_score": total_score,
                "article_count": article_count,
                "status": "google_news",
            })
            time.sleep(0.3)  # Be respectful

        except Exception as e:
            results.append({
                "keyword": kw,
                "raw_score": 0,
                "article_count": 0,
                "status": "error",
                "error": str(e),
            })

    # Normalize: highest raw_score → 100, others proportional
    if results:
        max_raw = max(r["raw_score"] for r in results)
        if max_raw > 0:
            for r in results:
                r["score"] = int(round(r["raw_score"] / max_raw * 100))
        else:
            for r in results:
                r["score"] = 0

    return results


def fetch_trends_pytrends():
    """Fetch real Google Trends data using pytrends."""
    pytrends = TrendReq(hl='en-US', tz=360, timeout=15)
    
    results = []
    
    # Google Trends limits: max 5 keywords per request
    chunk_size = 5
    
    for i in range(0, len(KEYWORDS), chunk_size):
        chunk = KEYWORDS[i:i + chunk_size]
        try:
            pytrends.build_payload(chunk, cat=47, timeframe='now 7-d', geo=REGION)
            interest = pytrends.interest_over_time()
            
            for kw in chunk:
                if kw in interest.columns:
                    avg = interest[kw].mean()
                    score = min(int(avg), 100) if not interest[kw].empty else 0
                else:
                    score = 0
                    
                results.append({"keyword": kw, "score": score, "status": "google_trends"})
                
            time.sleep(1)  # Respect rate limits
            
        except Exception as e:
            print(f"  Error fetching chunk {chunk}: {e}")
            for kw in chunk:
                results.append({"keyword": kw, "score": 0, "status": "error"})
    
    return results


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
        f.write("[{0}] [TREND] {1}\n".format(now, msg))


def main():
    print(f"Fetching REAL trend data for {len(KEYWORDS)} keywords...")
    print(f"Region: {REGION} | Timeframe: 7 days")
    print("")
    
    # Try Google Trends first (only if pytrends is installed), fall back to Google News
    results = None
    data_source = ""

    if PYTRENDS_AVAILABLE:
        try:
            pytrends_results = fetch_trends_pytrends()
            # Check if we got valid data (at least some non-error results)
            valid_results = [r for r in pytrends_results if r['status'] == 'google_trends' and r['score'] > 0]

            if valid_results:
                results = pytrends_results
                data_source = "Google Trends API (live)"
                print("Using: Google Trends API")
            else:
                raise Exception("No valid Google Trends data (all 429 or errors)")
        except Exception as e:
            print(f"Google Trends unavailable ({e})")
            print("Falling back to Google News RSS...")
            results = fetch_trends_google_news()
            data_source = "Google News RSS (article mentions)"
            print("Using: Google News RSS")
    else:
        print("pytrends not installed — using Google News RSS fallback...")
        results = fetch_trends_google_news()
        data_source = "Google News RSS (article mentions)"
        print("Using: Google News RSS")
    
    results.sort(key=lambda x: x["score"], reverse=True)
    
    spikes = [r for r in results if r["score"] >= SPIKE_THRESHOLD]
    
    print(f"\nTop 5 Keywords ({data_source}):")
    print("-" * 50)
    for i, r in enumerate(results[:5], 1):
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        bar = chr(9608) * (r["score"] // 5) + chr(9617) * (20 - r["score"] // 5)
        status_note = f"[{r['status']}]" if r['status'] != 'google_trends' else ''
        print(f"  {i}. {r['keyword']:<20} {bar} {r['score']} {icon} {status_note}")
    
    print("")
    
    if spikes:
        print(f"Spikes detected (>= {SPIKE_THRESHOLD}):")
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
                print(f"  + Added to queue: {s['keyword']} (score: {s['score']})")
            else:
                print(f"  = Already in queue: {s['keyword']}")
        
        if new_tasks > 0:
            write_queue(queue)
            append_log(f"{new_tasks} new spike task(s) added from {data_source}")
    else:
        print("No spikes detected")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top5 = results[:5]

    report_lines = [
        f"# Trend Report — {now}",
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
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        arts = r.get("article_count", "?")
        report_lines.append(f"{i}. **{r['keyword']}** — score: {r['score']} {icon} | {arts} articles [{r['status']}]")

    report_lines.append("")
    report_lines.append("## All Keywords")
    for r in results:
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        arts = r.get("article_count", "?")
        raw = r.get("raw_score", 0)
        report_lines.append(f"- {r['keyword']}: {r['score']} {icon} | {arts} arts | raw={raw:.1f} [{r['status']}]")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report_lines), encoding="utf-8")
    append_log(f"Trend scan complete — {len(spikes)} spikes — {data_source}")

    print("")
    print(f"Report: {REPORT}")
    print(f"Queue: {len(read_queue())} task(s)")


if __name__ == "__main__":
    main()
