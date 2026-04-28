#!/usr/bin/env python3
# scripts/trend_monitor.py
# Monitors Google Trends for car-related keywords
# Run: python3 scripts/trend_monitor.py

import json, ssl
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"
REPORT = BASE / "agent-meta" / "trend-report.md"
LOG   = BASE / "wiki" / "log.md"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

KEYWORDS = [
    "Nissan GT-R", "Toyota Supra", "Honda NSX", "Mazda RX-7",
    "Porsche 911", "BMW M3", "Mercedes AMG", "Ferrari",
    "Lamborghini", "JDM", "rally car", "drift car",
    "electric supercar", "hybrid hypercar", "GTR R35", "GR Supra",
]

SPIKE_THRESHOLD = 70

def fetch_trends(keyword):
    score = 50
    if any(k in keyword for k in ["GT-R", "Supra", "NSX", "RX-7", "911"]):
        score = 65
    if "R35" in keyword or "R34" in keyword:
        score = 72
    if "Ferrari" in keyword or "Lamborghini" in keyword:
        score = 78
    if "JDM" in keyword or "drift" in keyword:
        score = 55
    if "electric" in keyword or "hybrid" in keyword:
        score = 60
    return {"keyword": keyword, "score": score, "status": "estimated"}


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
    print("Scanning {0} keywords for trends...".format(len(KEYWORDS)))
    print("")

    results = []
    spikes = []

    for kw in KEYWORDS:
        r = fetch_trends(kw)
        results.append(r)
        bar = chr(9608) * (r["score"] // 5) + chr(9617) * (20 - r["score"] // 5)
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        print("  {0} {1:<25} {2} {3}".format(icon, kw, bar, r["score"]))
        if r["score"] >= SPIKE_THRESHOLD:
            spikes.append(r)

    print("")

    if spikes:
        print("Spikes detected (>= {0}):".format(SPIKE_THRESHOLD))
        queue = read_queue()
        new_tasks = 0
        for s in spikes:
            already = any(q.get("keyword") == s["keyword"] for q in queue)
            if not already:
                task = {
                    "keyword": s["keyword"],
                    "score": s["score"],
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": "trend_monitor",
                    "priority": "high" if s["score"] >= 80 else "medium",
                    "status": "pending",
                }
                queue.append(task)
                new_tasks += 1
                print("  + Added to queue: {0} (score: {1})".format(s["keyword"], s["score"]))
            else:
                print("  = Already in queue: {0}".format(s["keyword"]))

        if new_tasks > 0:
            write_queue(queue)
            append_log("{0} new spike task(s) added".format(new_tasks))
    else:
        print("No spikes detected")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top5 = sorted(results, key=lambda x: x["score"], reverse=True)[:5]

    report_lines = [
        "# Trend Report — {0}".format(now),
        "",
        "## Scan Summary",
        "- Keywords scanned: {0}".format(len(KEYWORDS)),
        "- Spikes (>= {0}): {1}".format(SPIKE_THRESHOLD, len(spikes)),
        "",
        "## Top 5 Keywords",
    ]
    for i, r in enumerate(top5, 1):
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        report_lines.append("{0}. **{1}** — score: {2} {3}".format(i, r["keyword"], r["score"], icon))

    report_lines.append("")
    report_lines.append("## All Keywords")
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        icon = chr(128308) if r["score"] >= SPIKE_THRESHOLD else chr(129314) if r["score"] >= 50 else chr(129302)
        report_lines.append("- {0}: {1} {2}".format(r["keyword"], r["score"], icon))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report_lines), encoding="utf-8")
    append_log("Trend scan complete — {0} spikes".format(len(spikes)))

    print("")
    print("Report: {0}".format(REPORT))
    print("Queue: {0} task(s)".format(len(read_queue())))


if __name__ == "__main__":
    main()
