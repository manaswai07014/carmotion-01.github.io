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
id: r34-bnr34
brand: Nissan
series: Skyline GT-R
generation_code: BNR34
year_start: 1999
year_end: 2002
primary_engine: RB26DETT
horsepower_official: 280
horsepower_source_tier: 1
platform: PM
market: [JDM, EDM]
is_successor_of: r33-bcnr33
primary_image_url: ''
primary_image_verified: false
completeness_score: 0
missing_fields: []
status: draft
---
```
