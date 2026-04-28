#!/usr/bin/env python3
# scripts/compare.py
# Generates comparison Shorts script for two cars
# Usage: python3 scripts/compare.py R33 R34

import re, sys
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent.parent
OUT    = BASE / "wiki" / "comparisons"
LOG    = BASE / "wiki" / "log.md"

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def fetch_specs(topic):
    """Fetch basic specs from Wikipedia."""
    import urllib.request, ssl
    CTX = ssl.create_default_context()
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
    
    url = "https://en.wikipedia.org/wiki/{}".format(topic.replace(' ', '_'))
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            html = r.read().decode('utf-8', errors='ignore')
        
        hp = ''
        m = re.search(r'(\d{3,4})\s*(?:hp|PS|cv)', html, re.I)
        if m: hp = m.group(1)
        
        engine = ''
        m = re.search(r'([0-9.]+L|[0-9.]+l)\s*(?:twin[\-\s]?turbo\s*)?(V[0-9]|inline[0-9]|flat[0-9])', html, re.I)
        if m: engine = m.group(0)
        
        year = ''
        m = re.search(r'(201[0-9]|202[0-5])', html)
        if m: year = m.group(1)
        
        return {'hp': hp, 'engine': engine, 'year': year, 'url': url}
    except:
        return {'hp': '', 'engine': '', 'year': '', 'url': ''}


def generate_comparison(a_name, b_name, a_specs, b_specs):
    """Generate comparison script."""
    
    hook = "R33 vs R34 — which generation is the REAL king of the Skyline? Crown or Crown? Let's settle this."
    
    body = """
BEAT 1 — {a} ({a_year})
{engine_a} | {hp_a} HP | {a_name} was the refined GT. Comfortable, beautiful, and still terrifyingly fast.

BEAT 2 — {b} ({b_year})
{engine_b} | {hp_b} HP | {b_name} was the raw driver's car. Harder, faster, angrier. The last manual GT-R.

BEAT 3 — HEAD TO HEAD
Both: Twin-turbo RB26 / RB26 DETT | AWD | 2 doors
{year_diff} years apart | The R34 makes {hp_diff} more horsepower
But the R33 has something the R34 doesn't — and it's not what you think.
""".format(
        a=a_name, b=b_name,
        a_name=a_name, b_name=b_name,
        a_year=a_specs.get('year', '1993'),
        b_year=b_specs.get('year', '1999'),
        engine_a=a_specs.get('engine', '2.6L Twin-Turbo RB26DETT'),
        hp_a=a_specs.get('hp', '276'),
        engine_b=b_specs.get('engine', '2.6L Twin-Turbo RB26DETT'),
        hp_b=b_specs.get('hp', '280'),
        year_diff=max(0, int(b_specs.get('year') or 1999) - int(a_specs.get('year') or 1993)),
        hp_diff=max(0, int(b_specs.get('hp') or 280) - int(a_specs.get('hp') or 276)),
    )
    
    verdict = """
VERDICT: If you want the purist's GT car — R33. Beautiful lines, twin-turbo soundtrack, and still used in professional racing today.

But if you want the ultimate expression of the Skyline GT-R — R34. The last of the hand-built legends. The one Godzilla himself would choose.

Which would you take? Drop it in the comments.
"""
    
    ending = "Follow for more JDM deep dives. Like if you learned something new about the Skyline dynasty."
    
    sources = "- [{a} specs]({a_url})\n- [{b} specs]({b_url})".format(
        a=a_name, b=b_name,
        a_url=a_specs.get('url', '#'),
        b_url=b_specs.get('url', '#'),
    )
    
    return hook, body, verdict, ending, sources


def save_comparison(a, b, content):
    OUT.mkdir(parents=True, exist_ok=True)
    filename = "{a}-vs-{b}.md".format(a=slugify(a), b=slugify(b))
    path = OUT / filename
    path.write_text(content, encoding='utf-8')
    return path


def append_log(msg):
    if not LOG.exists():
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[{0}] [COMPARE] {1}\n".format(now, msg))


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/compare.py <car_a> <car_b>")
        print("Example: python3 scripts/compare.py R33 R34")
        sys.exit(1)
    
    a_name = ' '.join(sys.argv[1:sys.argv.index('--save') if '--save' in sys.argv else len(sys.argv)])
    b_name = sys.argv[sys.argv.index('--save') + 1] if '--save' in sys.argv else (sys.argv[2] if len(sys.argv) > 2 else '')
    
    # Actually simple approach
    a_name = sys.argv[1]
    b_name = sys.argv[2]
    
    print("Generating comparison: {0} vs {1}".format(a_name, b_name))
    
    print("Fetching specs for {0}...".format(a_name))
    a_specs = fetch_specs(a_name)
    print("Fetching specs for {0}...".format(b_name))
    b_specs = fetch_specs(b_name)
    
    hook, body, verdict, ending, sources = generate_comparison(a_name, b_name, a_specs, b_specs)
    
    content = """# {a} vs {b} — Comparison Script

**Generated:** {date}

## Hook
{hook}

## Script

{body}

## Verdict
{verdict}

## Ending + CTA
{ending}

## Sources
{sources}
""".format(
        a=a_name, b=b_name,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        hook=hook, body=body, verdict=verdict, ending=ending, sources=sources,
    )
    
    path = save_comparison(a_name, b_name, content)
    append_log("Comparison generated: {0} vs {1}".format(a_name, b_name))
    
    print("")
    print("=" * 60)
    print(hook)
    print("=" * 60)
    print(content)
    print("=" * 60)
    print("Saved: {0}".format(path))


if __name__ == "__main__":
    main()
