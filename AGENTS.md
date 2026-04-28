# AGENTS.md — Car Evolution YouTube Wiki V4.1
# Version: 4.1-FINAL | Updated: 2026-04-28
# Status: ALL GAPS PATCHED (Karpathy LLM Wiki compliant)
# Hermes reads this file automatically on every session start

---

## PROJECT PURPOSE
Build a continuously updated car knowledge wiki to support
YouTube Shorts car evolution channel production.
Primary outputs: Shorts scripts / SEO metadata / wiki nodes / daily news brief.

---

## DIRECTORY LAYOUT

    ~/car-evolution-project/
    ├── AGENTS.md                         ← this file
    ├── ontology/car-ontology.md
    ├── wiki/
    │   ├── index.md                      master index (< 120 lines)
    │   ├── log.md                        APPEND-ONLY operation journal
    │   ├── templates/
    │   │   ├── README.md                 template index (when to use which)
    │   │   ├── template-evolution.md
    │   │   └── template-comparison.md
    │   ├── brands/ series/ generations/ engines/
    │   ├── comparisons/ disputes/ platforms/
    │   ├── overview/ topics/ queries/
    ├── data/
    │   ├── cars.db                       SQLite WAL mode
    │   └── daily-news/ backups/
    ├── memory/
    │   ├── hot-cache.json
    │   └── triples.jsonl                 auto-populated by ingest/query
    ├── agent-meta/
    │   ├── daily-brief.md
    │   ├── trend-report.md
    │   ├── lint-report.md                output of !lint
    │   ├── install-report.md
    │   └── work-log.jsonl
    ├── tasks/queue.jsonl
    └── scripts/
        ├── daily_news_fetcher.py
        ├── trend_monitor.py
        ├── backup.sh
        ├── migrations/001_init_schema.py
        └── qa/run_all.py

---

## ABSOLUTE RULES
1. raw/ is READ-ONLY — never modify original sources
2. Tier 4/5 data cannot overwrite Tier 1/2 existing data
3. Any data conflict → write wiki/disputes/[slug]_dispute_[date].md + mark 🔴 + STOP + ask user
4. Validate all numbers before writing to wiki
5. After every operation: MUST append to wiki/log.md (see LOG PROTOCOL)
6. Never fabricate URLs, image URLs, or horsepower values
7. Mark image_verified: false until manually confirmed
8. deepdive template REMOVED — never generate deepdive scripts
9. log.md is APPEND-ONLY — never delete or modify existing entries
10. BATCH LIMIT — any batch operation (loop/scan/delete) max 20 items per run; if >20, process in chunks and report progress, wait for confirmation before continuing
11. TIMEOUT GUARD — if any single operation stalls >60 seconds with no progress, STOP immediately and report: [TIMEOUT] completed X/Y, input !continue to resume
12. DESTRUCTIVE OPS — DELETE/DROP/TRUNCATE operations require user confirmation: display "Will delete X rows, confirm?" and wait for user reply "yes" before executing

---

## SESSION STARTUP (auto-execute on every session)
1. Read agent-meta/daily-brief.md
2. Read agent-meta/trend-report.md
3. Read tasks/queue.jsonl
4. Read memory/hot-cache.json
5. Read wiki/index.md
6. Run AUTO-LINT (checks 1 + 4 + 6 only — lightweight)
7. Output: Top 3 Shorts topics + trend alerts + top queue task + lint summary

---

## SHORTCUT COMMANDS

### Core Operations
!daily           Full session startup (steps 1-7 above)
!ingest [URL]    Full ingest pipeline (9 steps, see OPERATION 1)
!query [?]       Answer + auto write-back to wiki (see OPERATION 2)
!lint            Full lint (all 8 checks) → agent-meta/lint-report.md

### Content Generation (with write-back)
!script [code]   Generate Shorts evolution script → exports/youtube/ + write-back to wiki/generations/
!compare [A][B]  Generate comparison script → exports/youtube/ + write-back to wiki/comparisons/
!seo [code]      Generate SEO metadata → exports/youtube/[code]_seo.md

### News & Trends
!news            Run scripts/daily_news_fetcher.py immediately
!trend           Run scripts/trend_monitor.py immediately

### Wiki Management
!writeback       Force write-back of last query answer to appropriate wiki/
!disputes        Show all open wiki/disputes/ files
!gaps            Show all wiki/queries/*-gap.md files (knowledge gaps)
!logview [n]     Show last n lines of wiki/log.md (default: 20)
!queue           Show tasks/queue.jsonl
!status          brief / trend / queue count / DB size / lint status
!lint            Run full lint → agent-meta/lint-report.md

### Maintenance
!backup          Run scripts/backup.sh
!qa              Run scripts/qa/run_all.py
!graph [brand]   Export D3 JSON → exports/graph-json/

---

## OPERATION 1: ingest(source_url_or_path)
Purpose: Absorb external knowledge into wiki permanently.

    Step 1  FETCH
            output: raw/articles/[slug]_[date].md (READ-ONLY after write)

    Step 2  EXTRACT
            fields: brand / series / gen_code / year_start / year_end /
                    hp_official / engine_code / platform / market / source_tier

    Step 3  VALIDATE
            hp_official:  50 ≤ hp ≤ 2000 (outside → ⚠️ flag, ask user)
            year_start:   1885 ≤ year ≤ current_year + 2
            year_end:     year_end ≥ year_start OR "present"
            source_tier:  must be explicitly 1–5
            FAIL → stop, append log: [INGEST] FAIL [reason] [slug]

    Step 4  CONFLICT_CHECK
            if existing wiki page exists AND data differs:
              new_tier >= existing_tier → write disputes/ + mark 🔴 + ask user
              new_tier <  existing_tier → update wiki + log tier change

    Step 5  UPDATE_WIKI
            write/update wiki/generations/[slug].md
            sync: wiki/series/[series].md + wiki/brands/[brand].md

    Step 6  AUTO_FILL_TRIPLES (⭐ auto-populate memory)
            append memory/triples.jsonl:
            {"s":"[slug]","p":"official_horsepower","o":"[hp]ps",
             "conf":0.95,"tier":[n],"source":"[site]","ts":"[date]"}
            also add: year_start / year_end / primary_engine / platform

    Step 7  SYNC_DB
            INSERT OR REPLACE: generations / series / brands / source_refs / aliases

    Step 8  UPDATE_INDEX
            update wiki/index.md: Total Generations / Last Ingest

    Step 9  LOG + COMMIT
            append wiki/log.md:
            [YYYY-MM-DD HH:MM] [INGEST] [slug] src=[site] tier=[n] hp=[n]ps
            git commit: "[ingest] {title} {MM/DD}"

---

## OPERATION 2: query(question) → WRITE-BACK
Purpose: Every answer IS new wiki knowledge — must be written back.

    Step 1  CLASSIFY
            Type A: Factual lookup    → answer from wiki directly
            Type B: Synthesis query   → cross-page wiki synthesis needed
            Type C: Gap query         → wiki does not have this knowledge

    Step 2  ANSWER
            source priority: wiki/ > hot-cache.json > triples.jsonl

    Step 3  WRITE-BACK (MANDATORY for Type B and C)
            comparison query  → wiki/comparisons/[a]-vs-[b].md
            brand overview    → wiki/overview/[brand].md
            topic synthesis   → wiki/topics/[topic].md
            gen deep-dive     → append to wiki/generations/[slug].md
            unknown / gap     → wiki/queries/[date]-[slug]-gap.md

            !script [code]    → exports/youtube/[code]_[date].md
                               + append synthesis to wiki/generations/[slug].md
                               section: "## Shorts Script Synthesis [date]"

            !compare [A][B]   → exports/youtube/[A]vs[B]_[date].md
                               + write wiki/comparisons/[A]-vs-[B].md

    Step 4  UPDATE_MEMORY
            if conf >= 0.85: append new triple to memory/triples.jsonl

    Step 5  LOG
            append wiki/log.md:
            [YYYY-MM-DD HH:MM] [QUERY] "[question]" → [wiki_page] (Type[A/B/C])

---

## OPERATION 3: lint() → structured health check
Purpose: Periodically scan wiki health. Auto-lint (checks 1+4+6) runs on every !daily.

    Check 1  ORPHAN_DETECTION
             wiki/generations/*.md not referenced in index.md or any series page
             output: [WARN] orphan: [slug]

    Check 2  MISSING_IMAGES
             image_verified: false AND primary_image_url non-empty
             output: [WARN] unverified image: [slug]

    Check 3  MISSING_HP_SOURCE
             hp_official set BUT hp_source empty OR hp_tier empty
             output: [WARN] hp without source: [slug] hp=[n]

    Check 4  YEAR_LOGIC
             year_end < year_start
             output: [ERR] invalid year range: [slug]

    Check 5  STALE_DRAFTS
             status: draft AND updated_at < (today - 30 days)
             output: [WARN] stale draft: [slug] last=[date]

    Check 6  UNRESOLVED_DISPUTES
             wiki/disputes/ files older than 14 days
             output: [WARN] unresolved dispute: [slug]

    Check 7  DB_WIKI_SYNC
             DB record exists but wiki/generations/[slug].md missing (or vice versa)
             output: [ERR] DB/wiki out of sync: [slug]

    Check 8  INDEX_STALENESS
             wiki/index.md count != DB count
             output: [WARN] index stale: index=[n] DB=[m]

    Output:  write agent-meta/lint-report.md
    Log:     append wiki/log.md: [LINT] errors=[n] warnings=[n] checked=[n]
    AUTO-LINT (on every !daily): checks 1 + 4 + 6 only

---

## LOG.MD PROTOCOL (APPEND-ONLY — STRICT ENFORCEMENT)

FORBIDDEN:
- Never delete any line from wiki/log.md
- Never modify any existing line
- Never truncate or rotate the file (archive instead if > 10MB)

MANDATORY LOG EVENTS:
Event                   Format
------                  ------
session start           [YYYY-MM-DD HH:MM] [SESSION] started queue=[n]
ingest success          [YYYY-MM-DD HH:MM] [INGEST] [slug] src=[site] tier=[n] hp=[n]ps
ingest fail             [YYYY-MM-DD HH:MM] [INGEST] FAIL [reason] [slug]
query write-back        [YYYY-MM-DD HH:MM] [QUERY] "[question]" → [wiki_page] (Type[X])
lint run                [YYYY-MM-DD HH:MM] [LINT] errors=[n] warnings=[n] checked=[n]
dispute found           [YYYY-MM-DD HH:MM] [DISPUTE] [slug] [detail]
backup executed         [YYYY-MM-DD HH:MM] [BACKUP] [filename] size=[n]KB
script generated        [YYYY-MM-DD HH:MM] [SCRIPT] [gen_code] → [export_path]
comparison generated    [YYYY-MM-DD HH:MM] [COMPARE] [A]vs[B] → [wiki_path]

---

## INGEST WORKFLOW (quick reference)
READ raw/ → EXTRACT → VALIDATE → CONFLICT_CHECK → UPDATE wiki →
AUTO-FILL triples → SYNC DB → UPDATE index → LOG → GIT COMMIT

---

## YOUTUBE SHORTS WORKFLOW
Template: see wiki/templates/README.md for which template to use
Hook:     ≤ 10 words / first 3 seconds / create tension or question
Scoring:  6 items × 1pt — rewrite if < 4/6
Output:   exports/youtube/[gen_code]_[YYYYMMDD].md
Write-back: MANDATORY (see OPERATION 2 Step 3)

---

## GENERATION PAGE FRONTMATTER
type: generation
slug: [gen-slug]
brand: [brand]
series: [series]
gen_code: [e.g. BNR34]
name: [full name]
year_start: [year]
year_end: [year or present]
platform: [chassis]
primary_engine: [engine code]
hp_official: [PS]
hp_source: [source name]
hp_tier: [1-5]
primary_image_url: [URL]
image_source_url: [URL]
image_verified: false
market: [JDM/USDM/EUDM/Global]
status: draft
completeness_score: 0

Body sections:
## Overview / Key Improvements / Technical Specs /
## Market Variants / Cultural Heritage / Sources / 🔴 Pending

completeness_score auto-update rule:
+1 each: overview written / specs complete / image verified /
         sources cited (tier ≤ 2) / cultural section / Shorts script generated

---

## AUTO-SCHEDULE (crontab active)
0 0 * * *   cd ~/car-evolution-project && python3 scripts/daily_news_fetcher.py
0 1 */2 * * cd ~/car-evolution-project && python3 scripts/trend_monitor.py
0 2 * * 0   cd ~/car-evolution-project && bash scripts/backup.sh

---

## NEWS SOURCES (8 sites, daily RSS fetch)
topgear.com | caranddriver.com | motortrend.com
autocar.co.uk | evo.co.uk | jalopnik.com | roadandtrack.com | autoblog.com

---

## SOURCE TIER SYSTEM
Tier 1: Official manufacturer press releases / homologation docs
Tier 2: Top Gear / Car and Driver / Motor Trend / Autocar / evo
Tier 3: Wikipedia / Wikidata (cross-check required)
Tier 4: Other auto media (flag for verification)
Tier 5: Forums / personal blogs (NEVER primary citation)

Auto-apply rule: tier >= 4 → automatically add ⚠️ verification flag
                 tier == 5 → do not write to wiki, store in raw/ only

---

## MEMORY TRIPLE FORMAT
{"s":"[subject]","p":"[predicate]","o":"[object]",
 "conf":0.9,"tier":[1-5],"source":"[id]","ts":"[YYYY-MM-DD]"}

predicates: official_horsepower / disputed_horsepower /
            primary_engine / year_start / year_end /
            successor_of / platform / available_in_market
