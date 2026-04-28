#!/usr/bin/env python3
# scripts/gaps.py
# Identify knowledge gaps in wiki
# Usage: python3 scripts/gaps.py [--brand ferrari]

import json, sys, re
from pathlib import Path

BASE  = Path(__file__).parent.parent
WIKI  = BASE / "wiki"
BRANDS = ["bugatti", "ferrari", "lamborghini", "porsche", "nissan", "toyota", "honda", "bmw", "mclaren", "aston-martin"]

def get_all_generations():
    gens = []
    # Direct generations folder
    gens_dir = WIKI / "generations"
    if gens_dir.exists():
        for gen_file in gens_dir.glob("*.md"):
            content = gen_file.read_text(encoding="utf-8")
            # Try to extract brand from frontmatter
            brand = "unknown"
            for b in BRANDS:
                if b in gen_file.name.lower() or b in content.lower():
                    brand = b
                    break
            gens.append({"brand": brand, "file": gen_file.name, "content": content})
    return gens

def check_frontmatter(content):
    return bool(re.match(r'^---\n', content))

def check_image_refs(content):
    return "🖼️" in content or "wiki/images/" in content

def main():
    brand_filter = None
    if "--brand" in sys.argv:
        idx = sys.argv.index("--brand")
        if idx + 1 < len(sys.argv):
            brand_filter = sys.argv[idx + 1].lower()

    gens = get_all_generations()
    if brand_filter:
        gens = [g for g in gens if g["brand"] == brand_filter]

    if not gens:
        print("No generations found.")
        return

    print("Knowledge Gaps — {0} generation(s) scanned".format(len(gens)))
    print()

    gap_types = {
        "no_frontmatter": "Missing frontmatter",
        "no_hp": "Missing HP/horsepower data",
        "no_engine": "Missing engine specs",
        "no_image": "Missing image reference",
    }

    gap_counts = {k: 0 for k in gap_types}
    issues = []

    for g in gens:
        c = g["content"]
        brand = g["brand"]
        fname = g["file"]
        gissues = []

        if not check_frontmatter(c):
            gissues.append("no_frontmatter")
        if "馬力" not in c and "HP" not in c and "hp" not in c.lower():
            gissues.append("no_hp")
        if "引擎" not in c and "engine" not in c.lower():
            gissues.append("no_engine")
        if not check_image_refs(c):
            gissues.append("no_image")

        for issue in gissues:
            gap_counts[issue] += 1
            issues.append((brand, fname, issue))

    if not issues:
        print("No gaps found — all generations are complete!")
        return

    for brand, fname, issue in issues:
        print("  [{0}] {1} — {2}".format(brand, fname, gap_types[issue]))

    print()
    print("Summary:")
    for k, v in gap_counts.items():
        if v:
            print("  {0}: {1} generation(s)".format(gap_types[k], v))

if __name__ == "__main__":
    main()
