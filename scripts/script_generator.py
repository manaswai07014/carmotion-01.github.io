#!/usr/bin/env python3
# scripts/script_generator.py
# Generates Shorts scripts for car topics
# Usage: python3 scripts/script_generator.py <search_term> [--output FILE]
# Example: python3 scripts/script_generator.py "R35 GT-R"

import re, sys, json
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent.parent
SCRIPTS_DIR = BASE / 'wiki' / 'generations'
LOG    = BASE / 'wiki' / 'log.md'

TEMPLATE = """## Shorts Script Synthesis

**Generated:** {date}
**Confidence:** {{conf:.2f}}
**Tier:** {{tier}}

### 🎬 Hook (0-3s)
{hook}

### 📖 Story Beat 1 (3-15s)
{beat1}

### 📖 Story Beat 2 (15-30s)
{beat2}

### 📖 Story Beat 3 (30-50s)
{beat3}

### 🔚 Ending + CTA (50-60s)
{ending}

### 🔍 Sources
{sources}

### 📊 Specs Referenced
{specs}
"""

TEMPLATE_LEGACY = """## Shorts Script Synthesis

**Generated:** {date}
**Topic:** {topic}

### 🎬 Hook
{hook}

### 📖 Body
{body}

### 🔚 Ending
{ending}

### 🔍 Sources
{sources}
"""

def generate_script(topic: str) -> dict:
    """Generate a Shorts script for the given topic."""
    import urllib.request, ssl, json as json_mod, re
    
    CTX = ssl.create_default_context()
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
    
    # --- Search for info ---
    search_url = f"https://www.google.com/search?q={topic.replace(' ', '+')}+Nissan+GT-R+R35&num=5&hl=en"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    info = {
        'topic': topic,
        'hp': None,
        'engine': None,
        'year': None,
        'title': None,
        'sources': [],
    }
    
    # Try Wikipedia first
    wiki_topic = topic.replace(' ', '_').replace('-', '_')
    try:
        wiki_url = f"https://en.wikipedia.org/wiki/Nissan_GT-R"
        req = urllib.request.Request(wiki_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            html = r.read().decode('utf-8', errors='ignore')
        
        # Extract HP
        hp_match = re.search(r'(\d{3,4})\s*hp', html, re.I)
        if hp_match:
            info['hp'] = hp_match.group(1)
        
        # Extract engine
        engine_match = re.search(r'3\.8L\s*(?:Twin[\-\s]Turbo)?\s*V6', html, re.I)
        if engine_match:
            info['engine'] = engine_match.group(0)
        
        # Extract year
        year_match = re.search(r'(201[4-9]|202[0-5])', html)
        if year_match:
            info['year'] = year_match.group(1)
            
        info['sources'].append(('Wikipedia', wiki_url))
    except Exception as e:
        pass
    
    # Build script content
    hook = f"R35 GT-R — Japan's ultimate supercar killer 🔥"
    if info['hp']:
        hook += f" | {info['hp']} HP from the twin-turbo V6"
    
    beat1 = (
        "Born in 2007, the GT-R defied everything we knew about supercars. "
        "For the price of a Ferrari, you got a car that could embarrass exotics worth 3x the price. "
        "Nissan's engineers packed a 3.8L twin-turbo V6 and ATTESA E-TS all-wheel drive into a sedan body. "
        "Result: 0-100 in under 3 seconds. Factory."
    )
    
    beat2 = (
        f"The R35 evolved over nearly 2 decades — from {info['hp'] or '480'} PS in 2007 "
        f"to over 600 PS in the later Nismo variants. "
        "But it wasn't just power. The 6-speed dual-clutch gearbox, "
        "Bilstein dampers, and carbon ceramic brakes made it a complete weapon. "
        "Every edition — Base, Premium, V-Spec, Nismo — became a legend."
    )
    
    beat3 = (
        "The R35 also changed motorsport. It dominated GT3 racing worldwide. "
        "The GT-R GT3 won championships in Japan, Europe, and the US. "
        "And then the FIA World Endurance Championship — against Porsche, Ferrari, Aston Martin. "
        "This wasn't just a street car. It was a racing icon. "
        "And in 2024, Nissan confirmed: the R35 is ending. No direct replacement. "
        "The last chapter of the GT-R legend is being written right now."
    )
    
    ending = (
        "The GT-R proved Japan could build the world's best supercar. "
        "And it did it with engineering obsession, not just horsepower. "
        "Follow for more car history deep dives. "
        "Like if you think the R35 is the greatest GT car ever made."
    )
    
    specs = f"""
- Engine: {info['engine'] or '3.8L Twin-Turbo V6'}
- Power: {info['hp'] or '480-600'} HP (varies by year/variant)
- Torque: ~500 lb-ft
- 0-100 km/h: 2.7-3.0s
- Transmission: 6-speed dual-clutch (GR6)
- Drive: ATTESA E-TS AWD
- Years: 2007-2024
"""
    
    script = TEMPLATE_LEGACY.format(
        date=datetime.now().strftime('%Y-%m-%d %H:%M'),
        topic=topic,
        hook=hook,
        body=f"{beat1}\n\n{beat2}\n\n{beat3}",
        ending=ending,
        sources='\n'.join(f"- [{n}]({u})" for n, u in info['sources']) or "(web research)",
    )
    
    return {
        'script': script,
        'topic': topic,
        'info': info,
    }


def save_script(topic: str, script_text: str):
    """Save script to generations folder."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')
    out_file = SCRIPTS_DIR / f'{slug}.md'
    
    # Check for existing content
    if out_file.exists():
        existing = out_file.read_text(encoding='utf-8')
        if '## Shorts Script Synthesis' in existing:
            # Append new version with date header
            new_section = f"\n\n---\n\n{script_text}"
            # Find position before any existing Shorts Script Synthesis
            parts = existing.split('## Shorts Script Synthesis')
            out_file.write_text(parts[0] + f"## Shorts Script Synthesis{datetime.now().strftime(' [%Y-%m-%d]')}" + new_section, encoding='utf-8')
        else:
            out_file.write_text(existing.rstrip() + '\n\n' + script_text, encoding='utf-8')
    else:
        out_file.write_text(script_text, encoding='utf-8')
    
    return out_file


def append_log(action: str, detail: str = ''):
    if not LOG.exists():
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [SCRIPT] {action}'
    if detail:
        entry += f' — {detail}'
    entry += '\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


def main():
    if len(sys.argv) < 2:
        print('[ERR] Usage: python3 scripts/script_generator.py <topic> [--save]')
        sys.exit(1)
    
    topic = ' '.join([a for a in sys.argv[1:] if not a.startswith('--')]).strip()
    save  = '--save' in sys.argv
    
    if not topic:
        print('[ERR] Topic cannot be empty')
        sys.exit(1)
    
    print(f'🎬 Generating Shorts script for: {topic}')
    
    result = generate_script(topic)
    
    print()
    print('=' * 60)
    print(result['script'])
    print('=' * 60)
    
    if save:
        path = save_script(topic, result['script'])
        append_log(f'Script generated + saved: {topic}', str(path))
        print(f'\n[OK] Saved to: {path}')
    else:
        append_log(f'Script generated: {topic}')
        print(f'\n[OK] Add --save to write to wiki/generations/')


if __name__ == '__main__':
    main()
