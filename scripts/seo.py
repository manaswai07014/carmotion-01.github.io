#!/usr/bin/env python3
# scripts/seo.py
# Generates SEO metadata for a generation page
# Usage: python3 scripts/seo.py <gen_code>
# Example: python3 scripts/seo.py BNR34

import re, sys, json
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
WIKI  = BASE / "wiki" / "generations"
LOG   = BASE / "wiki" / "log.md"

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def extract_frontmatter(text):
    fm = {}
    for line in text.split('\n'):
        m = re.match(r'^(\w+):\s*(.+)$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def generate_seo(slug):
    page = WIKI / "{}.md".format(slug)
    
    if not page.exists():
        # Try fuzzy match
        candidates = list(WIKI.glob("*{}*.md".format(slug)))
        if candidates:
            page = candidates[0]
        else:
            print("[ERR] Page not found: {}.md".format(slug))
            return None
    
    text = page.read_text(encoding='utf-8')
    fm = extract_frontmatter(text)
    
    # Extract content
    lines = text.split('\n')
    title = fm.get('name', slug)
    year_start = fm.get('year_start', '')
    year_end = fm.get('year_end', '')
    hp = fm.get('hp_official', '')
    engine = fm.get('primary_engine', '')
    
    # Generate description
    if year_start and year_end:
        year_range = "{}-{}".format(year_start, year_end)
    elif year_start:
        year_range = year_start
    else:
        year_range = ''
    
    description = "{title} ({range}) — {hp}HP {engine}. Complete specs, history, and YouTube script for this generation. Find out everything about {title} before you buy.".format(
        title=title,
        range=year_range,
        hp=hp or 'Unknown',
        engine=engine or 'performance car',
    )
    
    if len(description) > 160:
        description = description[:157] + "..."
    
    # Generate tags
    tags = ["{title}".format(title=title), year_range, "{hp}HP".format(hp=hp) if hp else "car", engine.split()[0] if engine else "JDM"]
    tags = [t for t in tags if t][:8]
    
    # Generate JSON-LD structured data
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Car",
        "name": title,
        "productionDate": year_start,
        "vehicleEngine": {
            "@type": "EngineSpecification",
            "enginePower": {"@type": "QuantitativeValue", "value": hp, "unitCode": "HP"} if hp else None,
            "engineType": engine,
        } if engine else None,
    }
    
    return {
        "title": title,
        "slug": slug,
        "year_range": year_range,
        "description": description,
        "tags": tags,
        "jsonld": jsonld,
        "page_path": str(page),
    }


def append_log(msg):
    if not LOG.exists():
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[{0}] [SEO] {1}\n".format(now, msg))


def main():
    if not sys.argv[1:]:
        print("Usage: python3 scripts/seo.py <gen_code>")
        print("Example: python3 scripts/seo.py r35-gt-r")
        sys.exit(1)
    
    slug = sys.argv[1]
    result = generate_seo(slug)
    
    if not result:
        sys.exit(1)
    
    print("SEO Metadata for: {0}".format(result['title']))
    print()
    print("=" * 60)
    print("Title: {0}".format(result['title']))
    print("Slug: {0}".format(result['slug']))
    print("Year: {0}".format(result['year_range']))
    print()
    print("Meta Description:")
    print(result['description'])
    print()
    print("Tags:", ", ".join(result['tags']))
    print()
    print("JSON-LD:")
    print(json.dumps(result['jsonld'], indent=2))
    print("=" * 60)
    append_log("SEO generated: {0}".format(slug))


if __name__ == "__main__":
    main()
