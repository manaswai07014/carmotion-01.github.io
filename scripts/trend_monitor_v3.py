#!/usr/bin/env python3
"""
trend_monitor_v3.py
===================
Google Trends monitoring with triple fallback chain:
  1. pytrends (Google Trends API) — if module installed + quota available
  2. Google News RSS — enhanced scoring (recency + velocity + diversity)
  3. Cached data + warning — if all above fail

Enhanced RSS scoring (v3 vs v2):
  - 24-hour article window (not all-time count)
  - Recency-weighted scoring
  - Velocity multiplier (today vs 7-day average)
  - Source diversity bonus
  - Async concurrent requests for speed

Usage:
    python3 scripts/trend_monitor_v3.py [--save]
"""

import json, ssl, time, re, sys, asyncio, aiohttp
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"
REPORT = BASE / "agent-meta" / "trend-report.md"
HISTORY = BASE / "agent-meta" / "trend-history.jsonl"
LOG   = BASE / "wiki" / "log.md"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ── Config ────────────────────────────────────────────────────────────────────
KEYWORDS = [
    "Ferrari", "Lamborghini", "Porsche 911", "Toyota Supra", "Nissan GT-R",
    "Honda NSX", "Mazda RX-7", "BMW M3", "Mercedes AMG", "Tesla Model 3",
    "GTR R35", "GR Supra", "JDM", "drift car", "electric supercar", "hypercar",
]

NEWS_QUERIES = {
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

SPIKE_THRESHOLD = 70
RECENCY_WINDOW_HOURS = 24
HISTORY_DAYS = 7
REGION = 'US'
RSS_BASE_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

# ── Scoring Weights ───────────────────────────────────────────────────────────
RECENCY_WEIGHTS = [
    (timedelta(hours=0),  timedelta(hours=6),  1.0),   # < 6h
    (timedelta(hours=6),  timedelta(hours=12), 0.8),  # 6-12h
    (timedelta(hours=12), timedelta(hours=24), 0.5),  # 12-24h
]

def article_age_to_weight(age_hours: float) -> float:
    """Return weight for article age in hours."""
    if age_hours < 0:
        return 0.0
    for lo, hi, weight in RECENCY_WEIGHTS:
        if age_hours < hi.total_seconds() / 3600:
            return weight
    return 0.0  # >= 24h

# ── RSS Fetch (async concurrent) ──────────────────────────────────────────────

async def fetch_keyword_rss(session: aiohttp.ClientSession, keyword: str,
                             semaphore: asyncio.Semaphore) -> dict:
    """Fetch and score one keyword from Google News RSS."""
    async with semaphore:
        query = NEWS_QUERIES.get(keyword, f"{keyword} news")
        url = RSS_BASE_URL.format(q=urllib.parse.quote(query))

        result = {
            "keyword": keyword,
            "score": 0,
            "status": "error",
            "articles": 0,
            "weighted_count": 0.0,
            "recent_articles": 0,
            "sources": [],
            "velocity": 1.0,
            "diversity_bonus": 0,
            "error": None,
        }

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            await asyncio.sleep(0.3)  # rate limit

            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=15, context=CTX).read()
            )

            root = ET.fromstring(raw)
            items = root.findall('.//item')

            now = datetime.now(timezone.utc)
            weighted_count = 0.0
            sources = set()
            recent_articles = 0

            for item in items:
                # Extract source
                source_elem = item.find('source')
                if source_elem is not None and source_elem.text:
                    sources.add(source_elem.text.strip())

                # Extract pubDate
                pub_date = None
                for child in item:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if tag in ('pubDate', 'date'):
                        pub_date = child.text
                        break

                # Parse date
                age_hours = None
                if pub_date:
                    try:
                        import email.utils
                        parsed = email.utils.parsedate_to_datetime(pub_date)
                        if parsed:
                            age = now - parsed.replace(tzinfo=timezone.utc)
                            age_hours = age.total_seconds() / 3600
                    except Exception:
                        pass

                if age_hours is not None and age_hours <= RECENCY_WINDOW_HOURS:
                    weight = article_age_to_weight(age_hours)
                    weighted_count += weight
                    recent_articles += 1

            result["articles"] = len(items)
            result["weighted_count"] = weighted_count
            result["recent_articles"] = recent_articles
            result["sources"] = list(sources)
            result["status"] = "google_news"

        except Exception as e:
            result["error"] = str(e)[:80]

        return result


async def fetch_all_rss(keywords: list) -> tuple[list, str]:
    """Fetch all keywords concurrently via Google News RSS."""
    connector = aiohttp.TCPConnector(ssl=CTX, limit=10)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        semaphore = asyncio.Semaphore(5)  # max 5 concurrent
        tasks = [fetch_keyword_rss(session, kw, semaphore) for kw in keywords]
        results = await asyncio.gather(*tasks)

    return results, "Google News RSS (v3: recency + velocity + diversity)"


# ── Scoring Engine ─────────────────────────────────────────────────────────────

def load_history() -> dict:
    """Load history from JSONL. Returns {keyword: [daily_entries]}."""
    history = defaultdict(list)
    if not HISTORY.exists():
        return history

    try:
        cutoff = datetime.now() - timedelta(days=HISTORY_DAYS + 1)
        lines = HISTORY.read_text(encoding='utf-8').strip().split('\n')
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry.get("ts", "2000-01-01"))
                if ts < cutoff:
                    continue
                kw = entry.get("keyword", "")
                history[kw].append({
                    "ts": entry.get("ts", ""),
                    "weighted_count": entry.get("weighted_count", 0),
                    "sources": entry.get("sources", []),
                })
            except Exception:
                continue
    except Exception:
        pass

    return history


def save_today_to_history(results: list):
    """Append today's results to history file."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for r in results:
        if r["status"] != "google_news":
            continue
        lines.append(json.dumps({
            "ts": now,
            "keyword": r["keyword"],
            "weighted_count": r.get("weighted_count", 0),
            "recent_articles": r.get("recent_articles", 0),
            "sources": r.get("sources", []),
        }, ensure_ascii=False))

    if lines:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def calc_velocity(keyword: str, history: dict, today_wc: float) -> float:
    """
    Calculate velocity multiplier:
    today_weighted_count / avg(weighted_count of past 7 days)
    """
    days = history.get(keyword, [])
    if not days:
        return 1.0  # no history, neutral

    past_7 = [d["weighted_count"] for d in days[-HISTORY_DAYS:] if d.get("weighted_count", 0) > 0]
    if not past_7:
        return 1.0

    avg = sum(past_7) / len(past_7)
    if avg == 0:
        return 2.0  # surge from zero

    ratio = today_wc / avg
    return min(max(ratio, 0.3), 2.0)  # clamp 0.3 - 2.0


def source_diversity_bonus(sources: list) -> int:
    """Bonus points for source diversity."""
    n = len(sources)
    if n >= 8:
        return 20
    elif n >= 5:
        return 10
    elif n >= 3:
        return 5
    return 0


def score_keyword(r: dict, history: dict) -> dict:
    """Compute enhanced score for one keyword result."""
    wc = r.get("weighted_count", 0)

    # No recent articles = 0 score (no diversity bonus bailing out)
    if wc == 0:
        r["score"] = 0
        r["velocity"] = 1.0
        r["diversity_bonus"] = 0
        return r

    velocity = calc_velocity(r["keyword"], history, wc)
    diversity_bonus = source_diversity_bonus(r.get("sources", []))

    raw_score = wc * velocity + diversity_bonus
    final_score = min(int(raw_score), 100)

    r["score"] = final_score
    r["velocity"] = round(velocity, 2)
    r["diversity_bonus"] = diversity_bonus
    return r


# ── pytrends (same as v2) ─────────────────────────────────────────────────────

def fetch_pytrends_scores() -> tuple[list, str, bool]:
    """Try to fetch using pytrends. Returns (results, source, success)."""
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
                    "velocity": 1.0,
                    "diversity_bonus": 0,
                })
            time.sleep(1)

        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                return [], "google_trends_quota_exceeded", False
            for kw in chunk:
                results.append({
                    "keyword": kw,
                    "score": 0,
                    "status": "error",
                    "error": err_msg[:60],
                    "velocity": 1.0,
                    "diversity_bonus": 0,
                })

    return results, "Google Trends API (live)", len(results) > 0


# ── Cache fallback ────────────────────────────────────────────────────────────

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
                "velocity": 1.0,
                "diversity_bonus": 0,
            })
        if 'Data Source' in line and ':' in line:
            source = line.split(':', 1)[1].strip()
    return results, source


# ── Queue Management ──────────────────────────────────────────────────────────

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
        f.write(f"[{now}] [TREND-V3] {msg}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    save = '--save' in sys.argv
    results = []
    data_source = ""
    data_freshness = ""

    print(f"🔍 Fetching trend data for {len(KEYWORDS)} keywords (v3 enhanced scoring)...")

    # ── Step 1: pytrends ────────────────────────────────────────────────────
    pytrends_results, pytrends_source, pytrends_ok = fetch_pytrends_scores()

    if pytrends_ok and pytrends_results:
        results = pytrends_results
        data_source = pytrends_source
        data_freshness = "LIVE"
        print(f"  ✅ Source 1: pytrends — {len(results)} keywords")
    else:
        print(f"  ⚠️  Source 1: pytrends {'quota exceeded' if pytrends_source == 'google_trends_quota_exceeded' else 'failed/missing'}")

        # ── Step 2: RSS ─────────────────────────────────────────────────────
        print(f"  🔄 Source 2: Google News RSS (v3 enhanced)...")
        try:
            rss_results, rss_source = asyncio.run(fetch_all_rss(KEYWORDS))
            history = load_history()

            valid = [r for r in rss_results if r['status'] == 'google_news']
            if not valid:
                raise Exception("No valid RSS results")

            scored = [score_keyword(r, history) for r in rss_results]
            results = scored
            data_source = rss_source
            data_freshness = "LIVE"
            save_today_to_history(scored)

            print(f"  ✅ Source 2: RSS OK — {len(valid)} keywords (v3)")
            for r in scored[:5]:
                print(f"      {r['keyword']:<20} score={r['score']:>3} "
                      f"wc={r.get('weighted_count',0):.1f} "
                      f"vel={r.get('velocity',1.0):.2f}x "
                      f"src={len(r.get('sources',[]))}")

        except Exception as e:
            print(f"  ⚠️  Source 2: RSS failed — {e}")

            cached_results, cached_source = load_cached_report()
            if cached_results:
                results = cached_results
                data_source = f"CACHED (original: {cached_source})"
                data_freshness = "STALE"
                print(f"  ⚠️  Source 3: Cached data ({len(cached_results)} keywords)")
            else:
                print(f"  ❌ ALL SOURCES FAILED")
                return 1

    # ── Sort & Spike Detection ─────────────────────────────────────────────
    results.sort(key=lambda x: x["score"], reverse=True)
    spikes = [r for r in results if r["score"] >= SPIKE_THRESHOLD]

    print(f"\n📊 Top 5 Keywords ({data_source}):")
    print("-" * 65)
    for i, r in enumerate(results[:5], 1):
        spike_icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 40 else "⚪")
        vel = r.get("velocity", 1.0)
        vel_icon = "📈" if vel >= 1.5 else ("📉" if vel < 0.7 else "➡️")
        print(f"  {i}. {r['keyword']:<20} score={r['score']:>3} {spike_icon} {vel_icon} vel={vel:.2f}x "
              f"src={len(r.get('sources',[]))}")

    print(f"\n📋 Fresh: {data_freshness} | 24h window | Velocity vs 7-day avg")

    # ── Queue ────────────────────────────────────────────────────────────────
    if spikes:
        print(f"\n🔴 Spikes (>= {SPIKE_THRESHOLD}):")
        queue = read_queue()
        new_tasks = 0
        for s in spikes:
            already = any(q.get("keyword") == s["keyword"] for q in queue)
            if not already:
                task = {
                    "keyword": s["keyword"],
                    "score": s["score"],
                    "velocity": s.get("velocity", 1.0),
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": data_source,
                    "priority": "high" if s["score"] >= 80 else "medium",
                    "status": "pending",
                }
                queue.append(task)
                new_tasks += 1
                print(f"  + Added: {s['keyword']} (score={s['score']}, vel={s.get('velocity',1.0):.2f}x)")
            else:
                print(f"  = Already queued: {s['keyword']}")

        if new_tasks > 0:
            write_queue(queue)
            append_log(f"{new_tasks} spike(s) from {data_source}")

    # ── Write Report ────────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top5 = results[:5]

    report_lines = [
        f"# Trend Report — {now}",
        "",
        "## ⚠️ DATA FRESHNESS",
        f"- **Status:** {data_freshness}",
        f"- **Source:** {data_source}",
        f"- **Generated:** {now} HKT",
        f"- **Scoring:** v3 (24h window + velocity vs 7-day avg + source diversity)",
        "",
        "## Data Source",
        f"- **{data_source}**",
        f"- Region: {REGION} | Timeframe: 7 days | Category: Autos & Vehicles",
        f"- RSS Window: {RECENCY_WINDOW_HOURS}h | Velocity: today vs {HISTORY_DAYS}-day avg",
        "",
        "## Scan Summary",
        f"- Keywords scanned: {len(KEYWORDS)}",
        f"- Spikes (>= {SPIKE_THRESHOLD}): {len(spikes)}",
        "",
        "## Top 5 Keywords",
    ]

    for i, r in enumerate(top5, 1):
        icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 50 else "⚪")
        vel = r.get("velocity", 1.0)
        vel_str = f"📈{vel:.2f}x" if vel >= 1.5 else (f"📉{vel:.2f}x" if vel < 0.7 else f"➡️{vel:.2f}x")
        report_lines.append(
            f"{i}. **{r['keyword']}** — score: {r['score']} {icon} | "
            f"velocity: {vel_str} | sources: {len(r.get('sources', []))}"
        )

    report_lines += ["", "## All Keywords"]
    for r in results:
        icon = "🔴" if r["score"] >= SPIKE_THRESHOLD else ("🟡" if r["score"] >= 50 else "⚪")
        vel = r.get("velocity", 1.0)
        report_lines.append(
            f"- {r['keyword']}: {r['score']} {icon} "
            f"vel={vel:.2f}x src={len(r.get('sources', []))}"
        )

    report_lines.append("")
    report_lines.append(f"_Report generated: {now}_")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report_lines), encoding="utf-8")
    append_log(f"v3 scan: {len(spikes)} spikes — {data_source} — Fresh={data_freshness}")

    print(f"\n✅ Report saved: {REPORT}")
    print(f"📋 Queue: {len(read_queue())} task(s)")
    if data_freshness == "STALE":
        print("\n⚠️  WARNING: Using STALE cached data.")

    return 0 if data_freshness != "STALE" else 1


if __name__ == "__main__":
    sys.exit(main())
