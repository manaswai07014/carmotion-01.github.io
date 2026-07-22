#!/usr/bin/env python3
"""
run_daily_pipeline.py — Full CarMotion Daily pipeline in one shot.

Chain:
  1. daily_news_fetcher.py     → fetch RSS → agent-meta/daily-brief.md (5 articles)
  2. news_to_website.py        → brief → website/_posts/*.md + images
  3. git add + commit + push   → publish to GitHub Pages

Usage:
  python3 scripts/run_daily_pipeline.py              # today
  python3 scripts/run_daily_pipeline.py --date 2026-07-20  # backfill
  python3 scripts/run_daily_pipeline.py --no-push     # skip git push
  python3 scripts/run_daily_pipeline.py --dry-run     # preview only

Author: 惠惠
Created: 2026-07-22
"""

import subprocess, sys, os, argparse, datetime
from pathlib import Path

BASE   = Path(os.path.expanduser("~/car-evolution-project"))
SCRIPTS = BASE / "scripts"
WEBSITE = BASE / "website"

def run(cmd, label, timeout=300):
    """Run a command, stream output, return exit code."""
    print(f"\n{'='*60}")
    print(f"▶ {label}")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    try:
        result = subprocess.run(
            cmd, cwd=str(BASE), timeout=timeout,
            capture_output=False,  # stream to console
        )
        if result.returncode != 0:
            print(f"\n⚠️ {label} exited with code {result.returncode}")
            return False
        print(f"\n✓ {label} — OK")
        return True
    except subprocess.TimeoutExpired:
        print(f"\n⏰ {label} — TIMEOUT after {timeout}s")
        return False
    except Exception as e:
        print(f"\n❌ {label} — ERROR: {e}")
        return False

def git_commit_push(date_str, dry_run=False, no_push=False):
    """
    Git add, commit, and push website changes to both main and gh-pages branches.
    main branch: website/ in subdirectory
    gh-pages branch: website/ contents at root (via subtree split) for GitHub Pages
    """
    print(f"\n{'='*60}")
    print(f"▶ Git commit{' + push' if not no_push else ' (no push)'}")
    print(f"{'='*60}\n")

    # Step A: commit website/ changes on main branch
    if dry_run:
        print(f"  [DRY RUN] would commit & push website/")
        return True

    # Commit on main
    subprocess.run(["git", "add", "-A", "website/"], cwd=str(BASE), capture_output=True)
    r = subprocess.run(["git", "commit", "-m", f"[daily-pipeline] CarMotion Daily {date_str} — 5 articles + images"],
                        cwd=str(BASE), capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✓ committed to main")
    elif "nothing to commit" in (r.stdout + r.stderr):
        print("  ✓ nothing to commit (already up to date)")

    if no_push:
        return True

    # Step B: push main branch
    r = subprocess.run(["git", "push", "origin", "main"], cwd=str(BASE), capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✓ pushed main")
    else:
        print(f"  ⚠️ push main: {r.stderr.strip()[:100]}")

    # Step C: rebuild gh-pages subtree and force push
    print("  → rebuilding gh-pages subtree...")
    subprocess.run(["git", "branch", "-D", "gh-pages-tmp"], cwd=str(BASE), capture_output=True)
    r = subprocess.run(["git", "subtree", "split", "--prefix=website", "-b", "gh-pages-tmp"],
                       cwd=str(BASE), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⚠️ subtree split failed: {r.stderr.strip()[:100]}")
        return False
    print("  ✓ subtree split done")

    r = subprocess.run(["git", "push", "--force", "origin", "gh-pages-tmp:gh-pages"],
                       cwd=str(BASE), capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✓ pushed gh-pages (GitHub Pages will rebuild)")
    else:
        print(f"  ⚠️ push gh-pages: {r.stderr.strip()[:100]}")

    # Cleanup temp branch
    subprocess.run(["git", "checkout", "main"], cwd=str(BASE), capture_output=True)
    subprocess.run(["git", "branch", "-D", "gh-pages-tmp"], cwd=str(BASE), capture_output=True)

    return True

def main():
    ap = argparse.ArgumentParser(description="CarMotion Daily full pipeline")
    ap.add_argument("--date", help="YYYY-MM-DD; defaults to today", default=None)
    ap.add_argument("--no-push", action="store_true", help="Skip git push")
    ap.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = ap.parse_args()

    date_str = args.date or datetime.date.today().isoformat()
    print(f"\n🚀 CarMotion Daily Pipeline — {date_str}")
    print(f"   base: {BASE}")
    print(f"   push: {not args.no_push}")
    print(f"   dry:  {args.dry_run}")

    if args.dry_run:
        print("\n[DRY RUN] Would execute:")
        print(f"  1. python3 scripts/daily_news_fetcher.py  → brief")
        print(f"  2. python3 scripts/news_to_website.py --date {date_str}  → posts + images")
        print(f"  3. git add + commit + push")
        return

    # Step 1: Fetch news → daily-brief.md (5 articles)
    ok1 = run(
        ["python3", str(SCRIPTS / "daily_news_fetcher.py")],
        "Step 1/3: Fetch RSS → daily-brief.md (5 articles)",
        timeout=120,
    )
    if not ok1:
        print("\n❌ Step 1 failed — aborting pipeline")
        sys.exit(1)

    # Step 2: Generate website posts + images
    ok2 = run(
        ["python3", str(SCRIPTS / "news_to_website.py"), "--date", date_str],
        f"Step 2/3: Generate website posts for {date_str}",
        timeout=300,
    )
    if not ok2:
        print("\n⚠️ Step 2 had issues — continuing to git anyway")

    # Step 3: Git commit + push
    git_commit_push(date_str, no_push=args.no_push)

    # Summary
    print(f"\n{'='*60}")
    print(f"📋 Pipeline Summary — {date_str}")
    print(f"{'='*60}")
    print(f"  Step 1 (fetch):  {'✅' if ok1 else '❌'}")
    print(f"  Step 2 (website): {'✅' if ok2 else '⚠️'}")
    print(f"  Step 3 (git):    {'✅' if not args.no_push else '⏭️ skipped'}")
    print(f"\n  Posts dir: {WEBSITE / '_posts'}")
    print(f"  Images:   {WEBSITE / 'static' / 'images' / 'news'}")
    print()

if __name__ == "__main__":
    main()
