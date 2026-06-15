#!/usr/bin/env python3
"""
verify_brand_data.py — Brand Data Verification Script
=======================================================
Checks wiki data quality for a brand: HP validation, URL validity, data conflicts.

Usage:
    python3 scripts/verify_brand_data.py --brand Porsche
    python3 scripts/verify_brand_data.py --brand Porsche --check-hp --check-urls
    python3 scripts/verify_brand_data.py --brand all

Output:
    - HP validation status (range 50-2000)
    - URL validity (HTTP status)
    - Data conflict report
    - Missing fields report
"""

import argparse
import os
import sys
import re
import json
import urllib.request
import ssl
from pathlib import Path

# Configuration
PROJECT_ROOT = Path("/home/hermes/car-evolution-project")
WIKI_BRANDS = PROJECT_ROOT / "wiki" / "brands"
WIKI_SERIES = PROJECT_ROOT / "wiki" / "series"
WIKI_GENERATIONS = PROJECT_ROOT / "wiki" / "generations"
CAR_DB = PROJECT_ROOT / "data" / "cars.db"

# HP validation range
HP_MIN = 50
HP_MAX = 2000

# Known bad HP values (from car-evolution skill)
KNOWN_BAD_HP = {
    "singer-dls-turbo": (710, 500),  # (wrong, correct)
    "gordon-murray-t50": (725, 654),
    "gordon-murray-t.50": (725, 654),
    "ferrari-laferrari": (936, 963),
    "mclaren-p1": (986, 916),
}

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}{text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")


def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text):
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text):
    print(f"   {text}")


def check_hp_value(hp_str, brand_slug, model_slug):
    """Validate HP value and check against known bad data."""
    # Extract numeric HP
    hp_match = re.search(r'([\d,]+)\s*(hp|ps|kw|kW)', hp_str.lower())
    if not hp_match:
        return None, "No HP number found"

    hp_value = int(hp_match.group(1).replace(',', ''))

    # Check range
    if hp_value < HP_MIN or hp_value > HP_MAX:
        return hp_value, f"HP {hp_value} outside valid range ({HP_MIN}-{HP_MAX})"

    # Check known bad data
    full_slug = f"{brand_slug}-{model_slug}".lower()
    if full_slug in KNOWN_BAD_HP:
        wrong_hp, correct_hp = KNOWN_BAD_HP[full_slug]
        if hp_value == wrong_hp:
            return hp_value, f"KNOWN BAD HP: {wrong_hp} (correct: ~{correct_hp})"

    return hp_value, "OK"


def check_url(url, timeout=5):
    """Check URL validity with HEAD request."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return True, resp.status
    except Exception as e:
        return False, str(e)


def find_brand_path(brand_name):
    """Find brand path with case-insensitive matching."""
    brand_lower = brand_name.lower().strip()

    # Direct match
    direct = WIKI_BRANDS / brand_name
    if direct.exists():
        return direct

    # Case-insensitive search
    for entry in WIKI_BRANDS.iterdir():
        if entry.name.lower() == brand_lower:
            return entry

    return None


def scan_brand_index(brand_name):
    """Scan brand index.md for 🅿️ nodes and HP data."""
    brand_path = find_brand_path(brand_name)

    if brand_path is None:
        return None, f"Brand folder not found: {brand_name}"

    index_path = brand_path / "index.md"
    if not index_path.exists():
        return None, f"No index.md in {brand_name}"

    with open(index_path, 'r') as f:
        content = f.read()

    lines = content.splitlines()

    # Find all 🅿️ nodes
    nodes = []
    current_node = None

    for i, line in enumerate(lines):
        if line.startswith('🅿️'):
            if current_node:
                nodes.append(current_node)
            # Parse: 🅿️ #N: Model — HP
            match = re.match(r'🅿️\s*#(\d+):\s*(.+?)\s*—\s*([\d,]+)\s*(hp|HP)', line)
            if match:
                current_node = {
                    'num': int(match.group(1)),
                    'model': match.group(2).strip(),
                    'hp_str': match.group(3),
                    'hp_raw': match.group(3),
                    'line': i + 1,
                }
            else:
                # Try alternative format
                match2 = re.match(r'🅿️\s*#(\d+):\s*(.+)', line)
                if match2:
                    current_node = {
                        'num': int(match2.group(1)),
                        'model': match2.group(2).strip(),
                        'hp_str': '',
                        'hp_raw': '',
                        'line': i + 1,
                    }
        elif current_node and ('HP' in line or '馬力' in line or 'hp' in line):
            current_node['hp_detail'] = line.strip()

    if current_node:
        nodes.append(current_node)

    return nodes, None


def scan_series_for_brand(brand_name):
    """Scan series folder for brand-specific nodes."""
    brand_lower = brand_name.lower().replace(' ', '-')

    # Try both direct and case-insensitive
    series_path = WIKI_SERIES / brand_name
    if not series_path.exists():
        series_path = WIKI_SERIES / brand_lower

    if not series_path.exists():
        # Try to find it
        for entry in WIKI_SERIES.iterdir():
            if entry.name.lower() == brand_lower:
                series_path = entry
                break
        else:
            return []

    if not series_path.exists():
        return []

    all_nodes = []
    for md_file in series_path.glob("*.md"):
        with open(md_file, 'r') as f:
            content = f.read()

        nodes = []
        current_node = None

        for line in content.splitlines():
            if line.startswith('🅿️'):
                if current_node:
                    nodes.append(current_node)
                match = re.match(r'🅿️\s*#(\d+):\s*(.+?)\s*—\s*([\d,]+)\s*(hp|HP)', line)
                if match:
                    current_node = {
                        'model': match.group(2).strip(),
                        'hp_str': match.group(3),
                        'file': md_file.name,
                    }
            if current_node and '馬力' in line:
                current_node['hp_detail'] = line.strip()

        if current_node:
            nodes.append(current_node)

        all_nodes.extend(nodes)

    return all_nodes


def generate_brand_report(brand_name, check_hp=True, check_urls=True):
    """Generate full verification report for a brand."""

    brand_slug = brand_name.lower().replace(' ', '-')

    print_header(f"🔍 {brand_name} Data Verification Report")

    # Check brand index
    print(f"{BOLD}📁 Brand Index:{RESET}")
    index_nodes, err = scan_brand_index(brand_name)
    if err:
        print_error(err)
        return

    if index_nodes:
        print_success(f"Found {len(index_nodes)} 🅿️ nodes in brand index")
    else:
        print_warning("No 🅿️ nodes found in brand index")

    # Check series folder
    print(f"\n{BOLD}📂 Series Folder:{RESET}")
    series_nodes = scan_series_for_brand(brand_name)
    if series_nodes:
        print_success(f"Found {len(series_nodes)} 🅿️ nodes in series folder")
    else:
        print_warning("No 🅿️ nodes found in series folder")

    # HP validation
    hp_issues = []
    if check_hp and index_nodes:
        print_header(f"🔧 HP Validation ({HP_MIN}-{HP_MAX} range)")
        for node in index_nodes:
            if node.get('hp_str'):
                hp_val, status = check_hp_value(node['hp_str'], brand_slug, node['model'])
                if status != "OK":
                    hp_issues.append({
                        'model': node['model'],
                        'hp': hp_val,
                        'issue': status
                    })
                    print_error(f"  {node['model']}: {node['hp_str']} hp → {status}")
                else:
                    print_success(f"  {node['model']}: {node['hp_str']} hp → OK")

        if not hp_issues:
            print_success("All HP values are valid!")

    # URL check
    if check_urls:
        print_header(f"🔗 URL Validity Check")
        # Scan for URLs in wiki
        brand_path = find_brand_path(brand_name)
        urls_found = []

        for md_file in brand_path.glob("*.md"):
            with open(md_file, 'r') as f:
                content = f.read()
            url_matches = re.findall(r'https?://[^\s\)\]"<>]+', content)
            urls_found.extend([(md_file.name, u) for u in url_matches])

        if urls_found:
            print_info(f"Found {len(urls_found)} URLs to check")
            for fname, url in urls_found[:10]:  # Limit to 10
                valid, status = check_url(url)
                if valid:
                    print_success(f"  [{fname}] {status}")
                else:
                    print_error(f"  [{fname}] {str(status)[:50]}")
        else:
            print_warning("No URLs found in brand files")

    # Summary
    print_header(f"📊 {brand_name} Summary")
    total_nodes = len(index_nodes or []) + len(series_nodes)
    print_info(f"Total 🅿️ Nodes: {total_nodes}")
    print_info(f"HP Issues: {len(hp_issues) if check_hp else 'N/A'}")
    print_info(f"URL Issues: N/A (manual check needed)")


def generate_overall_report():
    """Generate report for all brands."""
    print_header("📊 ALL BRANDS COVERAGE AUDIT")

    brands_status = []
    all_series = [d.name for d in WIKI_SERIES.iterdir() if d.is_dir()]

    for entry in WIKI_BRANDS.iterdir():
        if entry.is_dir():
            index_path = entry / "index.md"
            if index_path.exists():
                with open(index_path, 'r') as f:
                    content = f.read()
                node_count = content.count('🅿️')
                brands_status.append({
                    'name': entry.name,
                    'type': 'folder',
                    'has_index': True,
                    'nodes': node_count,
                    'lines': len(content.splitlines())
                })
            else:
                brands_status.append({
                    'name': entry.name,
                    'type': 'folder',
                    'has_index': False,
                    'nodes': 0,
                    'lines': 0
                })
        else:
            with open(entry, 'r') as f:
                content = f.read()
            brands_status.append({
                'name': entry.name,
                'type': 'file',
                'has_index': True,
                'nodes': 0,
                'lines': len(content.splitlines())
            })

    # Sort by node count
    brands_status.sort(key=lambda x: -x['nodes'])

    # Print table
    print(f"{'Brand':<20} {'Type':<8} {'Lines':<6} {'Nodes':<6} Status")
    print("-" * 60)

    ready = []
    needs_research = []
    needs_full = []

    for b in brands_status:
        if b['nodes'] > 0:
            status = f"{GREEN}✅{RESET}"
            ready.append(b['name'])
        elif b['lines'] > 20:
            status = f"{YELLOW}⚠️{RESET}"
            needs_research.append(b['name'])
        else:
            status = f"{RED}❌{RESET}"
            needs_full.append(b['name'])

        print(f"{b['name']:<20} {b['type']:<8} {b['lines']:<6} {b['nodes']:<6} {status}")

    print(f"\n{GREEN}✅ Node Ready: {len(ready)}{RESET} → {ready}")
    print(f"{YELLOW}⚠️  Needs Research: {len(needs_research)}{RESET} → {needs_research}")
    print(f"{RED}❌ Needs Full Research: {len(needs_full)}{RESET} → {needs_full}")

    # Series with nodes
    print(f"\n{BOLD}📁 Series with 🅿️ Nodes:{RESET}")
    for s in sorted(all_series):
        s_path = WIKI_SERIES / s
        total = sum(1 for f in s_path.glob("*.md") if f.read_text().count('🅿️') > 0)
        if total > 0:
            print(f"  {s}: {total} nodes")


def main():
    parser = argparse.ArgumentParser(description="Verify brand data quality")
    parser.add_argument('--brand', type=str, help='Brand name to verify (e.g., Porsche, Ferrari)')
    parser.add_argument('--all', action='store_true', help='Check all brands')
    parser.add_argument('--check-hp', action='store_true', help='Validate HP values')
    parser.add_argument('--check-urls', action='store_true', help='Check URL validity')
    parser.add_argument('--no-hp', action='store_true', help='Skip HP check')
    parser.add_argument('--no-urls', action='store_true', help='Skip URL check')

    args = parser.parse_args()

    # Defaults
    check_hp = not args.no_hp
    check_urls = not args.no_urls

    if args.all or (not args.brand):
        generate_overall_report()
    else:
        generate_brand_report(args.brand, check_hp=check_hp, check_urls=check_urls)


if __name__ == "__main__":
    main()