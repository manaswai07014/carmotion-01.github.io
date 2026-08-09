# Auto-Wiki Ingestion Report

**Run date:** 2026-08-09 10:08 HKT
**Script:** `scripts/auto_wiki_ingestion.py` (bare run, `--save` dropped)
**Status:** ✅ Exit 1 — Idle (no eligible brands, all in cooldown)

---

## 執行狀態

- Script ran clean, no exceptions
- `--save` flag detected and dropped (unsupported by argparse, would silent-fail exit 2)
- Priority ranking computed for 10 brands; Porsche top (score=0.2)
- All 17 hardcoded brands have existing `wiki/brands/<slug>/index.md` → `brand_exists()` returns True → 7-day cooldown never engages → permanent idle trap (known issue)

## State Snapshot (Census)

| Layer | Count | Notes |
|-------|-------|-------|
| Wiki brand folders | 22 | 20 STALE >30d (newest: 2026-05-04 Ferrari) |
| Wiki series pages | 139 | Active maintenance layer |
| Wiki generation pages | 72 | — |
| DB brands | 4 | DB ↔ Wiki gap: 4 vs 22 |
| DB series | 9 | — |
| DB generations | 16 | 15 published + 1 draft |
| triples.jsonl | stable (last verified 2026-08-03) | — |

## Top 10 Priority Ranking (idle, no action triggered)

1. Porsche — score=0.2 (trend=911)
2. Ferrari — score=0.0 (trend=66)
3. Mercedes — score=0.0 (trend=64)
4. Lamborghini — score=0.0 (trend=61)
5. Toyota — score=0.0 (trend=27)
6. Mazda — score=0.0 (trend=7)
7. Honda — score=0.0 (trend=4)
8. BMW — score=0.0 (trend=3)
9. Tesla — score=0.0 (trend=3)
10. Bugatti — score=0.0 (trend=0)

## Observations

- ⚠️ **20/22 brand pages STALE >30d** — newest is Ferrari 2026-05-04 (96+ days old). auto_wiki_ingestion cannot refresh them due to permanent idle trap (no bypass for cooldown when `brand_exists()` is True).
- ⚠️ **Single-file brand `.md` anomaly persists**: `audi.md`, `bmw.md`, `jaguar.md`, `mercedes.md` at top level (not in subfolders) — `isdir()` check skips these for triples parsing.
- ⚠️ **Aston Martin dual folder** (`aston-martin` hyphen + `aston_martin` underscore) unresolved — awaiting boss decision on canonical color.
- ⚠️ **Audi SQ9 draft entry** (Audi brand, no production model) still in DB — awaiting boss decision to delete or rename.
- ℹ️ **log.md was touched 07:46 today** (sibling cron — Wiki Sync + Lint at 07:45 HKT). Skip log append this run to avoid concurrent write race (idle run = no data mutation, cosmetic only).

## Actionable Next-Step Options (boss picks, do not auto-execute)

1. **Force-refresh a specific brand**: `.venv/bin/python3 scripts/auto_wiki_ingestion.py --brand Porsche` — bypasses eligibility, overwrites stale page. Recommended for top-3 STALE: Porsche / Ferrari / Bugatti.
2. **Run `sync_wiki_from_db.py`**: rebuilds all generation pages + index.md from DB (07:45 HKT cron already runs this — verify freshness tomorrow).
3. **Consolidate Aston Martin folders**: needs boss approval on canonical color (Skyfall Silver #C0C0C0 vs Aston Martin Green #005B5B).
4. **Audit + resolve Audi SQ9 draft**: confirm Wikipedia "no SQ9 production model" assertion, then purge or rename DB entry.
5. **Refresh Memory Triples**: run `scripts/sync_memory_cache.py --brand <X>` after force-ingesting a brand to update `triples.jsonl`.
