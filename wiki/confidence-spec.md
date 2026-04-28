# Confidence Score Specification
# How Hermes assigns conf values when writing to memory/triples.jsonl

## Why this matters
Hermes uses conf >= 0.85 to decide whether a triple gets persisted.
Without a clear definition, this degrades to subjective guessing.

## Confidence Calculation Table

| Situation | conf value |
|-----------|------------|
| Directly quoted from Tier 1 source (official spec) | 0.99 |
| Cross-confirmed by 2+ Tier 2 sources | 0.95 |
| Single Tier 2 source (Top Gear / C&D / Motor Trend) | 0.90 |
| Single Tier 3 source (Wikipedia, cross-checked) | 0.80 |
| Tier 3 without cross-check | 0.70 |
| Tier 4 source only | 0.55 |
| Tier 5 / forum / unverified | 0.35 |
| Synthesized by LLM from multiple wiki pages (no external source) | 0.75 |
| LLM synthesis with citation to Tier 1/2 | 0.88 |

## Persistence Rule
- conf >= 0.85: append to memory/triples.jsonl
- conf 0.70-0.84: store in raw/ only, mark for verification
- conf < 0.70: do NOT store as triple; note in wiki page as ⚠️ unverified

## Triple Format with confidence
{"s":"nissan-skyline-bnr34","p":"official_horsepower","o":"276ps",
 "conf":0.99,"tier":1,"source":"nissan-press-1998","ts":"2026-04-28"}

## Predicates reference
official_horsepower | disputed_horsepower | primary_engine
year_start | year_end | successor_of | platform | available_in_market
manufacturer | designer | production_count

## Write-back duplicate handling
When !script [code] is run more than once:
- Check if '## Shorts Script Synthesis' section already exists
- If YES: APPEND a new section with the new date, do NOT overwrite
  Format: '## Shorts Script Synthesis [YYYY-MM-DD]'
- This ensures version history is preserved in the wiki page

## log.md archive rule
- When log.md exceeds 10 MB:
  1. Copy full content to wiki/log-YYYY-MM.md (current month)
  2. Reset log.md to: '# Wiki Log (continued — archived YYYY-MM)\n'
  3. Append: '[YYYY-MM-DD HH:MM] [ARCHIVE] log-YYYY-MM.md created'
  4. Never delete archived files
- scripts/lint.py check_log_size() handles this automatically
