#!/usr/bin/env python3
# scripts/queue.py
# View and manage task queue
# Usage: python3 scripts/queue.py [--clear] [--done]

import json, sys
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
QUEUE = BASE / "tasks" / "queue.jsonl"

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

def main():
    if "--clear" in sys.argv:
        write_queue([])
        print("Queue cleared.")
        return
    
    queue = read_queue()
    if not queue:
        print("Queue is empty.")
        return
    
    pending = [q for q in queue if q.get("status") == "pending"]
    done = [q for q in queue if q.get("status") == "done"]
    
    print("Task Queue — {0} pending, {1} done".format(len(pending), len(done)))
    print()
    
    if pending:
        print("PENDING:")
        for i, q in enumerate(pending, 1):
            priority_icon = chr(128308) if q.get("priority") == "high" else chr(129314) if q.get("priority") == "medium" else chr(128308)
            print("  {0}. {1} [{2}] (score: {3})".format(
                i, q.get("keyword", q.get("title", "unknown")),
                q.get("priority", "?"), q.get("score", "?")))
            print("     Source: {0} | Added: {1}".format(q.get("source", "?"), q.get("ts", "?")))
    
    if done and "--done" in sys.argv:
        print()
        print("DONE:")
        for q in done[-5:]:
            print("  - {0} (completed: {1})".format(
                q.get("keyword", "unknown"), q.get("completed_at", "?")))


if __name__ == "__main__":
    main()
