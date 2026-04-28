#!/usr/bin/env python3
# scripts/logview.py
# View recent wiki log entries
# Usage: python3 scripts/logview.py [count]
# Default: 10 entries

import sys, re
from pathlib import Path

BASE = Path(__file__).parent.parent
LOG  = BASE / "wiki" / "log.md"

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    
    if not LOG.exists():
        print("[ERR] log.md not found")
        sys.exit(1)
    
    lines = LOG.read_text(encoding='utf-8').split('\n')
    # Skip header lines
    content_lines = [l for l in lines if l.strip() and not l.startswith('#')]
    total = len(content_lines)
    
    print("Wiki Log — last {0} of {1} entries".format(min(count, total), total))
    print("=" * 60)
    
    for line in content_lines[-count:]:
        print(line)
    
    print("=" * 60)


if __name__ == "__main__":
    main()
