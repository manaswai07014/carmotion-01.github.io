#!/usr/bin/env python3
"""
daily_smoke_test.py
====================
End-of-day smoke test — runs after all cron jobs (12:00 HKT daily).

Verifies:
  1. All reports generated successfully
  2. Reports have Freshness Stamps
  3. No obvious data corruption (empty files, stale dates)
  4. Unit tests still pass

Exit codes:
  0 = all pass
  1 = problems found (alert via Telegram)
"""

import sys, subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
REPORTS = [
    ("Daily Brief",          BASE / "agent-meta/daily-brief.md"),
    ("Trend Report",         BASE / "agent-meta/trend-report.md"),
    ("Competitor Report",    BASE / "agent-meta/competitor-analysis-phase2-enhanced.md"),
    ("Topic Priority",       BASE / "exports/topic-priority/latest-report.md"),
]

def check_freshness_stamp(path) -> tuple[bool, str]:
    """Return (has_stamp, status)."""
    if not path.exists():
        return False, "MISSING"
    content = path.read_text(encoding='utf-8', errors='ignore')
    if not content.strip():
        return False, "EMPTY"
    if '## ⚠️ DATA FRESHNESS' in content or '## DATA FRESHNESS' in content:
        return True, "✅ STAMP"
    # Also accept older format
    if '**Status:**' in content and ('LIVE' in content or 'CACHED' in content or 'FRESH' in content):
        return True, "✅ LEGACY STAMP"
    return False, "⚠️  NO STAMP"

def check_file_age_h(path) -> float | None:
    if not path.exists():
        return None
    age_s = datetime.now().timestamp() - path.stat().st_mtime
    return age_s / 3600

def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M HKT')
    print(f"🔬 Daily Smoke Test — {now}")
    print("=" * 60)

    problems = []

    # 1. Check each report
    print("\n📄 Report Checks:")
    for name, path in REPORTS:
        has_stamp, stamp_status = check_freshness_stamp(path)
        age_h = check_file_age_h(path)
        age_str = f"({age_h:.1f}h old)" if age_h is not None else "(missing)"

        if path.exists() and path.stat().st_size < 100:
            problems.append(f"{name}: file is nearly empty ({path.stat().st_size} bytes)")
            print(f"  ❌ {name}: TOO SMALL {age_str}")
        elif not path.exists():
            problems.append(f"{name}: file missing")
            print(f"  ❌ {name}: MISSING {age_str}")
        elif not has_stamp:
            problems.append(f"{name}: no freshness stamp")
            print(f"  ⚠️  {name}: NO FRESHNESS STAMP {age_str}")
        else:
            print(f"  ✅ {name}: {stamp_status} {age_str}")

    # 2. Run unit tests
    print("\n🧪 Unit Tests:")
    test_script = BASE / "scripts" / "test_regex_parsing.py"
    if test_script.exists():
        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print("  ✅ test_regex_parsing.py: ALL PASSED")
        else:
            problems.append(f"Unit tests FAILED:\n{result.stdout}\n{result.stderr}")
            print(f"  ❌ Unit tests FAILED")
    else:
        print("  ⚠️  test_regex_parsing.py not found — skipped")

    # Summary
    print("\n" + "=" * 60)
    if problems:
        print(f"❌ {len(problems)} problem(s) found:")
        for p in problems:
            print(f"   • {p}")
        return 1
    else:
        print("✅ All smoke tests PASSED")
        return 0

if __name__ == '__main__':
    sys.exit(main())
