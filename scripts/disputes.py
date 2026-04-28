#!/usr/bin/env python3
# scripts/disputes.py
# List unresolved data disputes/conflicts
# Usage: python3 scripts/disputes.py

import json
from pathlib import Path

BASE   = Path(__file__).parent.parent
META   = BASE / "wiki" / ".meta"

def read_disputes():
    dfile = META / "disputes.jsonl"
    if not dfile.exists():
        return []
    with open(dfile, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def main():
    disputes = read_disputes()
    if not disputes:
        print("No disputes on record.")
        return
    
    print("Data Disputes — {0} unresolved".format(len(disputes)))
    print()
    for d in disputes:
        print("  [{0}] {1}".format(d.get("status", "?"), d.get("title", "unknown")))
        print("    Claim A: {0}".format(d.get("claim_a", "?")))
        print("    Claim B: {0}".format(d.get("claim_b", "?")))
        print("    Source:  {0}".format(d.get("source", "?")))
        print()

if __name__ == "__main__":
    main()
