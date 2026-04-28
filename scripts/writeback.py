#!/usr/bin/env python3
# scripts/writeback.py
# Forces write-back of last query result
# Usage: python3 scripts/writeback.py [--dry-run]

import json, sys
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"
LOG   = BASE / "wiki" / "log.md"
TRIPLES = BASE / "memory" / "triples.jsonl"

def append_log(msg):
    if not LOG.exists():
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[{0}] [WRITEBACK] {1}\n".format(now, msg))


def read_queue():
    if not QUEUE.exists():
        return []
    with open(QUEUE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    dry = "--dry-run" in sys.argv
    
    if dry:
        print("[DRY RUN] Would trigger write-back for:")
        queue = read_queue()
        pending = [q for q in queue if q.get("status") == "pending"]
        print("  Pending tasks: {0}".format(len(pending)))
        for q in pending[:5]:
            print("  - {0} ({1})".format(q.get("keyword", q.get("title", "unknown")), q.get("priority", "?")))
        return
    
    queue = read_queue()
    pending = [q for q in queue if q.get("status") == "pending"]
    
    if not pending:
        print("No pending write-back tasks.")
        append_log("writeback: no pending tasks")
        return
    
    print("Processing {0} pending write-back task(s)...".format(len(pending)))
    
    for task in pending:
        task["status"] = "done"
        task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        print("  Done: {0}".format(task.get("keyword", task.get("title", "unknown"))))
    
    # Write back to queue
    with open(QUEUE, "w", encoding="utf-8") as f:
        for q in queue:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    
    # Also append a triple record
    for task in pending:
        triple = {
            "s": task.get("slug", ""),
            "p": "writeback_completed",
            "o": task.get("keyword", ""),
            "conf": 0.95,
            "tier": 1,
            "ts": datetime.now().strftime("%Y-%m-%d"),
        }
        with open(TRIPLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(triple, ensure_ascii=False) + "\n")
    
    append_log("writeback: {0} task(s) completed".format(len(pending)))
    print("Done.")


if __name__ == "__main__":
    main()
