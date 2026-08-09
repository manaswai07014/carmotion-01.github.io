# Auto-Wiki Ingestion Report — 2026-07-25 10:20 HKT

**Status:** IDLE (no eligible brands)
**Script:** `scripts/auto_wiki_ingestion.py` (bare, no `--save`)
**Exit code:** 0 (clean run)

## Summary
- 0 brands ingested this run
- Trigger reason: all 17 hardcoded brands either have existing `wiki/brands/<slug>/index.md` OR within 7-day cooldown
- Permanent idle trap (known issue, see `references/auto-wiki-ingestion.md`)

## Priority Ranking (this run)
1. Porsche — score=0.2 (trend=911)
2. Mercedes — score=0.0 (trend=69)
3. Toyota — score=0.0 (trend=28)
4. Lamborghini — score=0.0 (trend=20)
5. Nissan — score=0.0 (trend=20)
6. Honda — score=0.0 (trend=20)
7. Mazda — score=0.0 (trend=7)
8. BMW — score=0.0 (trend=3)
9. Tesla — score=0.0 (trend=3)
10. Ferrari — score=0.0 (trend=0)

## State Snapshot
- **Brand folders:** 22 total (17 hardcoded + 5 duplicates/anomalies)
- **STALE brands (>30d):** 22/22 (100%)
  - Oldest: `bugatti` 81d, `ferrari` 81d
  - Newest: `porsche` 39d
  - `mitsubishi` 47d
- **Naming anomaly:** `aston-martin` (hyphen) + `aston_martin` (underscore) coexist — known anomaly, awaiting boss approval to consolidate
- **Series-level folders:** `mclaren-p1` and `mercedes-amg` — kept as series-level slugs

## DB State
- Brands: 4 | Series: 9 | Generations: 16
- Status breakdown: 15 published, 1 draft
- **Audi SQ9 entry (draft):** Confirmed non-existent car (2026-07-24) — left as draft per boss decision deferred to next free time
- DB/wiki sync gap: 22 wiki folders vs 4 DB brands — explains 19 orphan generation pages flagged by lint

## Latest Lint (2026-07-25 07:46)
- Errors: 0
- Warnings: 34 (19 orphan gen pages, 9 unverified images, 6 "no image set")
- Newest log entry: `[2026-07-24 15:47] [LINT] 0 errors, 34 warnings, 19 pages checked`
- Pre-existing `db5/db11/dbs-superleggera/vantage/f-type/i-pace/ix3` — HP/engine/image filled 2026-07-24, awaiting image verification

## Known Issues (unchanged)
1. `--save` flag in cron prompt still buggy — script argparse rejected it (would exit 2 silently). Operator must drop `--save` and run bare.
2. Permanent idle trap: once all 17 brands' `wiki/brands/<slug>/index.md` exists, `brand_exists()` always returns True → 7-day cooldown never triggers fresh ingest
3. `triples_auto_fill.py` (02:00 HKT cron) reported idle today — 24/25 brand pages are stubs, only `tesla` is fully populated
4. Trend monitor at 07:21 HKT today reported 0 spikes (Google News RSS fresh=LIVE)

## Actionable Next Steps (for boss to pick — NOT auto-executed)
1. **`--brand X` force refresh** — e.g. `.venv/bin/python3 scripts/auto_wiki_ingestion.py --brand Bugatti` to force re-ingest (oldest STALE brand, 81d)
2. **Add 07:45 HKT sync+lint cron** — `sync_wiki_from_db.py + lint.py` daily keeps index/lint fresh even when ingestion idle (recommended in `references/wiki-db-sync.md`)
3. **Consolidate `aston-martin` vs `aston_martin`** — needs boss approval (destructive folder move)
4. **Delete or rename `sq9` DB entry** — confirmed non-existent, currently draft
5. **Fix `--save` in cron prompt** — drop the flag permanently in the cron job config (requires boss approval — touches cron config)

## Log
`wiki/log.md` appended: `[2026-07-25 10:20] [INGEST] IDLE — ...`
