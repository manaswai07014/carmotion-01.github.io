# Car Domain Ontology V4

## Classes
Brand, Series, Generation, Engine, Platform, Market, Trim

## Relations
- is_successor_of (Generation → Generation)
- shares_platform_with (Generation → Generation)
- uses_engine (Generation → Engine)
- belongs_to_series (Generation → Series)
- manufactured_by (Series → Brand)
- available_in_market (Generation → Market)

## Generation Page Required Frontmatter
```yaml
---
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
image_verified: false
market: [JDM/USDM/EUDM/Global]
status: draft
completeness_score: 0
---
```

## Predicates Reference
- official_horsepower: Direct from Tier 1-2 source
- disputed_horsepower: Conflicting values from different sources
- primary_engine: Engine code used in this generation
- year_start: First production year
- year_end: Last production year (or "present")
- successor_of: Previous generation
- platform: Chassis/platform code
- available_in_market: Market regions where sold

## Confidence Score (see wiki/confidence-spec.md)
- conf >= 0.85: persist to memory/triples.jsonl
- conf 0.70-0.84: store in raw/ only
- conf < 0.70: do NOT store as triple
