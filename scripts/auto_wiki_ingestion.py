#!/usr/bin/env python3
"""
auto_wiki_ingestion.py
======================
Auto-Wiki Ingestion Pipeline for Car Evolution Wiki V4.1

Purpose: 每日根據 competitor data + daily news 自動識別最熱門型號，
         自動攝取資料入 Wiki 知識庫，輸出完整圖譜格式（Node Card）。

Usage:
    python3 scripts/auto_wiki_ingestion.py --brand Porsche --dry-run
    python3 scripts/auto_wiki_ingestion.py --brand Porsche          # 實際寫入

Environment:
    GOOGLE_API_KEY - YouTube Data API v3 key (from .env)
"""

import os
import re
import sys
import json
import ssl
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── Project Paths ────────────────────────────────────────────────────────────
BASE          = Path(__file__).parent.parent
DB            = BASE / 'data' / 'cars.db'
WIKI          = BASE / 'wiki'
BRANDS_DIR    = WIKI / 'brands'
SERIES_DIR    = WIKI / 'series'
GEN_DIR       = WIKI / 'generations'
QUEUE_FILE    = BASE / 'tasks' / 'queue.jsonl'
TREND_REPORT  = BASE / 'agent-meta' / 'trend-report.md'
DAILY_BRIEF   = BASE / 'agent-meta' / 'daily-brief.md'
LOG_FILE      = WIKI / 'log.md'
INGEST_LOG    = WIKI / 'log-ingestion.md'
WIKI_INDEX    = WIKI / 'index.md'

# ── Config ────────────────────────────────────────────────────────────────────
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 每次運行限額
LIMIT_BRAND    = 1
LIMIT_SERIES   = 8
LIMIT_GEN      = 5
COOLDOWN_DAYS  = 7

# ─────────────────────────────────────────────────────────────────────────────
# HARDCODE MODEL LISTS (one source of truth, no generic regex guessing)
# ─────────────────────────────────────────────────────────────────────────────

# 呢個係唯一嘅 model 資料源 — 唔用 generic regex 估，全部來自呢度
BRAND_MODELS = {
    'Porsche': [
        '911', 'Boxster', 'Cayman', 'Cayenne', 'Macan', 'Panamera',
        'Taycan', '918 Spyder', 'Carrera GT', '356', '914', '924', '944',
        '968', '928', 'Cayman GT4',
    ],
    'Ferrari': [
        'F40', 'F50', 'Enzo', 'LaFerrari', 'F12berlinetta', 'FF', '458 Italia',
        '488 GTB', '458 Spider', '488 Spider', '599 GTB', '612 Scaglietti',
        '812 Superfast', '812 GTS', 'Portofino', 'Roma', 'SF90 Stradale',
        '296 GTB', '296 GTS', 'GTC4Lusso', 'F8 Tributo', 'Daytona SP3',
        '250 GTO', '250 GT', '275 GTB', '365 GTB', '365 GT4', '550 Maranello',
        '575M', '512 TR', '308 GTB', '328 GTB', 'Mondial',
    ],
    'Lamborghini': [
        'Miura', 'Countach', 'Diablo', 'Murciélago', 'Aventador', 'Huracán',
        'Gallardo', 'Urus', 'Revuelto', 'Temerario', '350 GT', '400 GT',
        'Islero', 'Espada', 'Jalpa', 'LM002',
    ],
    'Bugatti': [
        'Veyron', 'Chiron', 'Tourbillon', 'Divo', 'Centodieci', 'Bolide',
        'EB 110', 'EB 112', 'Type 57', 'Atlantic',
    ],
    'McLaren': [
        'F1', 'MP4-12C', '650S', '675LT', '720S', '765LT', 'Senna', 'Speedtail',
        'Elva', 'Artura', 'P1', '570S', '540C', '600LT', '620R',
    ],
    'Aston Martin': [
        'DB5', 'DB6', 'DB9', 'DB11', 'DBS', 'Vantage', 'Vanquish', 'DB4',
        'DB2', 'DB7', 'Virage', 'Zagato', 'DBS Superleggera', 'Valkyrie',
        'V12 Speedster',
    ],
    'Bentley': [
        'Continental GT', 'Flying Spur', 'Bentayga', 'Mulsanne', 'Arnage',
        'Azure', 'Brooklands', 'Turbo R',
    ],
    'Maserati': [
        'Ghibli', 'Quattroporte', 'Levante', 'GranTurismo', 'GranCabrio',
        'MC20', 'MC12', '3200 GT', 'Indy',
    ],
    'Rolls-Royce': [
        'Phantom', 'Ghost', 'Wraith', 'Cullinan', 'Dawn', 'Spectre',
        'Silver Ghost', 'Silver Cloud', 'Corniche',
    ],
    'Jaguar': [
        'F-Type', 'E-Type', 'F-Pace', 'XK', 'XJ', 'XE', 'I-Pace',
        'XK120', 'D-Type', 'XJS',
    ],
    'BMW': [
        'M3', 'M4', 'M5', 'M8', 'M2', 'X3 M', 'X5 M', 'X6 M',
        '3 Series', '5 Series', '7 Series', '8 Series', 'Z4',
        'Z3', 'Z8', 'X1', 'X2', 'X4', 'X6', 'X7',
        'i3', 'i4', 'i7', 'i8', 'iX',
    ],
    'Mercedes': [
        'AMG GT', 'AMG One', 'A45', 'C63', 'E63', 'S63', 'G63',
        'G-Class', 'S-Class', 'E-Class', 'C-Class', 'A-Class',
        'CLA', 'CLS', 'GLA', 'GLB', 'GLC', 'GLE', 'GLK', 'GLS',
    ],
    'Mercedes-AMG': [
        'AMG GT', 'AMG One', 'AMG GT3', 'AMG GT4', 'A45', 'C63', 'E63', 'S63', 'G63',
    ],
    'Audi': [
        'R8', 'TT', 'A1', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8',
        'Q3', 'Q5', 'Q7', 'Q8', 'e-tron', 'e-tron GT', 'RS3', 'RS4', 'RS5',
        'RS6', 'RS7', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8',
    ],
    'Toyota': [
        'Supra', 'GR86', 'BRZ', 'Land Cruiser', 'Hilux', 'Camry',
        'Prius', 'Corolla', 'Crown', 'Century', 'GR Supra',
    ],
    'Nissan': [
        'GT-R', 'Skyline', 'Z', 'Fairlady Z', 'Silvia', '180SX', 'S15',
        '370Z', '350Z', '300ZX', 'Cima', 'Teana', 'Ariya',
    ],
    'Honda': [
        'NSX', 'Civic Type R', 'Integra Type R', 'S2000', 'NSX Type R',
        'Civic', 'Accord', 'CR-V', 'HR-V',
    ],
    'Mazda': [
        'MX-5 Miata', 'RX-7', 'RX-8', 'Mazda3', 'Mazda6', 'CX-5', 'CX-9',
        'MX-30', 'Atenza',
    ],
    'Ford': [
        'Mustang', 'GT', 'F-150', 'Bronco', 'Explorer', 'Expedition',
        'Focus', 'Fiesta', 'Mustang Mach-E',
    ],
    'Chevrolet': [
        'Corvette', 'Camaro', 'Corvette C8', 'Tahoe', 'Suburban', 'Silverado',
        'Bolt', 'Equinox', 'Traverse',
    ],
    'Tesla': [
        'Model S', 'Model 3', 'Model X', 'Model Y', 'Cybertruck',
        'Roadster', 'Semi', 'Model S Plaid',
    ],
    'Subaru': [
        'Impreza', 'WRX', 'WRX STI', 'BRZ', 'Outback', 'Forester',
        'Crosstrek', 'Levorg',
    ],
    'Mitsubishi': [
        'Lancer Evolution', 'Lancer', 'Outlander', 'Pajero', 'Evo',
    ],
}

# 已知有多代嘅車系（用作代數偵測嘅捷徑）
KNOWN_MULTI_GEN = {
    '911', 'm3', 'm4', 'm5', 'm6',
    'gtr', 'gt-r', 'r35', 'r34', 'r33', 'r32',
    'supra', 'mk4', 'mk3',
    'rx-7', 'rx8',
    'nsx', 's2000',
    '370z', '350z',
    'z06', 'corvette',
    'type-r', 'integra',
    'impreza', 'wrx', 'sti',
    'evora', 'exige', 'elise',
    'gt86', 'brz', '86',
    'challenger', 'charger', 'mustang',
    'amg gt', 'rs3', 'rs4', 'rs5', 'rs6', 'rs7',
    's3', 's4', 's5', 's6', 's7',
    '3-series', '4-series', '5-series', '6-series', '7-series',
    'cayenne', 'panamera', 'macan',
    'tesla model s', 'tesla model x', 'tesla model 3',
}

# 代數車系關鍵字（喺 Wikipedia 搵到呢啲關鍵字就知道呢個係多代車系）
SERIES_KEYWORDS = [
    'generations', 'generations list', 'model history',
    'model timeline', 'model overview', 'production timeline',
]


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def log(msg, file=None):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'[{ts}] {msg}'
    print(line)
    if file:
        with open(file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

def slugify(text):
    """Convert brand/series name to URL-safe slug.
    
    Preserves underscores for alphanumeric patterns like '718 Boxster' → '718_boxster'
    (Wikipedia URL convention for model names with numbers).
    """
    text = text.lower().replace('/', '-').replace("'", '')
    # Keep underscores between alphanumeric tokens (e.g. "718 Boxster" → "718_boxster")
    text = re.sub(r'([a-z0-9])\s+([a-z0-9])', r'\1_\2', text)
    # Then replace remaining spaces with hyphens
    text = text.replace(' ', '-')
    return re.sub(r'[^a-z0-9\-_]', '', text)

_FETCH_CACHE = {}  # URL → HTML cache

def fetch_html(url, timeout=15, silent=False):
    """Fetch URL with SSL workaround + in-memory cache.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        silent: If True, suppress warnings (for variant URLs that may not exist)
    """
    if url in _FETCH_CACHE:
        return _FETCH_CACHE[url]
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            html = r.read().decode('utf-8', errors='ignore')
            _FETCH_CACHE[url] = html
            return html
    except Exception as e:
        if not silent:
            safe_url = url.encode('ascii', 'replace').decode('ascii')
            print(f'  [WARN] fetch failed: {safe_url} → {e}')
        return ''

def _fetch_with_retry(url, max_attempts=3, base_delay=2, silent_404=False):
    """Fetch with exponential backoff retry.
    
    Args:
        url: URL to fetch
        max_attempts: Max retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        silent_404: If True, suppress all warnings (for variant URLs that may not exist)
    """
    for attempt in range(max_attempts):
        html = fetch_html(url, silent=silent_404)
        if html:
            return html
        if attempt < max_attempts - 1:
            delay = base_delay * (2 ** attempt)
            if not silent_404:
                print(f'  [RETRY] attempt {attempt+1}/{max_attempts} failed, waiting {delay}s...')
            time.sleep(delay)
    return ''

def clean_html(text):
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    return text.strip()

def extract_wiki_infobox(html, key):
    """Extract value from Wikipedia infobox."""
    key_aliases = {
        'engine': ['engine', 'powertrainengine', 'motor', 'engines'],
        'power': ['power', 'power output', 'engine power', 'electrical power'],
    }
    lookup_keys = [key.lower()]
    if key.lower() in key_aliases:
        lookup_keys = key_aliases[key.lower()]
    for lkey in lookup_keys:
        for th_match in re.finditer(r'<th\b[^>]*>(.*?)</th>', html, re.DOTALL):
            th_content = th_match.group(1)
            if re.search(r'\b' + re.escape(lkey) + r'\b', th_content, re.I):
                after_th = th_match.end()
                td_match = re.search(r'<td\b[^>]*>(.*?)</td>', html[after_th:], re.DOTALL)
                if td_match:
                    return clean_html(td_match.group(1)).strip()
    return ''

def extract_hp(text):
    """Extract highest HP number from text."""
    matches = re.findall(r'(\d{3,4})\s*(?:hp|ps|cv)', text, re.I)
    if matches:
        hp_values = [int(m) for m in matches]
        if 50 <= max(hp_values) <= 2000:
            return str(max(hp_values))
    return ''

def extract_engine(text):
    """Extract engine displacement + configuration."""
    if not text:
        return ''
    m = re.search(
        r'\b([1-9]\.[0-9]+)\s*L\s*(?:twin[\-\s]?turbo[\-\s]?|turbo[\-\s]?)?'
        r'(?:V[0-9]|V[IVX]+|inline[\-\s]?[0-9]|flat[\-\s]?[0-9])?',
        text, re.I)
    if m:
        displacement = m.group(1) + 'L'
    else:
        m = re.search(r'\b([1-9]\.[0-9]+)L\b', text, re.I)
        if not m:
            return ''
        displacement = m.group(1) + 'L'
    after_disp = text[text.find(displacement) + len(displacement):][:50].strip()
    cyl_m = re.search(r'\b(V[0-9]|V[IVX]+|inline[\-\s]?[0-9]|flat[\-\s]?[0-9])\b', after_disp, re.I)
    cyl = cyl_m.group(1) if cyl_m else ''
    turbo = 'twin-turbo' if re.search(r'twin[\-\s]?turbo', text, re.I) else ('turbo' if 'turbo' in text.lower() else '')
    result = displacement
    if turbo:
        result += ' ' + turbo
    if cyl and cyl not in result:
        result += ' ' + cyl
    return result[:60].strip()

def extract_year(text):
    """Extract year from text."""
    m = re.search(r'(19[5-9]\d|20[0-5]\d)', text)
    return m.group(1) if m else ''

def read_jsonl(path):
    """Read a JSONL file, return list of dicts."""
    if not path.exists():
        return []
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]

def append_log(action, detail=''):
    """Append to wiki/log.md (APPEND-ONLY)."""
    if not LOG_FILE.exists():
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [{action}] {detail}\n'
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(entry)

def append_ingest_log(action, detail=''):
    """Append to wiki/log-ingestion.md."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f'[{now}] [{action}] {detail}\n'
    with open(INGEST_LOG, 'a', encoding='utf-8') as f:
        f.write(entry + '\n')

def brand_exists(brand):
    """Check if brand already exists in wiki."""
    slug = slugify(brand)
    paths = [
        BRANDS_DIR / f'{slug}.md',
        BRANDS_DIR / slug / 'index.md',
        WIKI / 'overview' / f'{slug}.md',
    ]
    return any(p.exists() for p in paths)

def is_cooldown_ok(brand):
    """Return True if brand is not in cooldown."""
    if not INGEST_LOG.exists():
        return True
    slug = slugify(brand)
    with open(INGEST_LOG, encoding='utf-8') as f:
        for line in f:
            if f'[INGEST] brand={slug}' in line.lower():
                m = re.match(r'\[(\d{4}-\d{2}-\d{2})', line)
                if m:
                    days_since = (datetime.now() - datetime.strptime(m.group(1), '%Y-%m-%d')).days
                    return days_since >= COOLDOWN_DAYS
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Brand Page
# ─────────────────────────────────────────────────────────────────────────────

def research_brand_wikipedia(brand):
    """
    從 Wikipedia 抓取品牌資料。
    只用 BRAND_MODELS 硬編碼列表，唔用 generic regex 估。
    """
    slug = slugify(brand)
    url = f'https://en.wikipedia.org/wiki/{urllib.parse.quote(brand.replace(" ", "_"))}'
    html = _fetch_with_retry(url, max_attempts=3, base_delay=2)
    if not html:
        return None

    info = {
        'name': brand,
        'slug': slug,
        'country': '',
        'founded': '',
        'description': '',
        'models': [],
        'url': url,
        'source': 'Wikipedia',
        'tier': 2,
    }

    # Extract country
    m = re.search(r'headquartered in ([^.<\n]+)', html)
    if m:
        info['country'] = m.group(1).strip()

    # Extract founded year
    m = re.search(r'founded.*?(\d{4})', html, re.I)
    if m:
        info['founded'] = m.group(1)

    # Extract description (first paragraph)
    m = re.search(r'<p>(.{200,800}?)</p>', html, re.I)
    if m:
        text = clean_html(m.group(1))
        info['description'] = text[:300] + '...' if len(text) > 300 else text

    # ── Model extraction: BRAND_MODELS only, NO generic regex ──────────────
    brand_models = BRAND_MODELS.get(brand, [])
    found_models = set()

    for model in brand_models:
        # Exact word boundary match
        if re.search(r'\b' + re.escape(model) + r'\b', html):
            found_models.add(model)

    info['models'] = list(found_models)
    return info


# ─────────────────────────────────────────────────────────────────────────────
# Series Page
# ─────────────────────────────────────────────────────────────────────────────

def research_series_wikipedia(brand, series_name):
    """
    從 Wikipedia 抓取車系資料。
    Strategy: 直接構造 URL（完全繞過 Search API）。
    
    嘗試多種 URL 變體，特別處理數字代號系列（如 Boxster → Porsche_Boxster，
    而唔係 Porsche_718_boxster）。
    """
    slug = slugify(series_name)
    clean_name = series_name.strip()

    # URL 變體工廠（按優先順序嘗試）
    def make_urls(brand_s, series_s):
        b = urllib.parse.quote(brand_s.replace(' ', '_'))
        s = urllib.parse.quote(series_s.replace(' ', '_'))
        # Special case: Porsche 718 series uses "Boxster" not "718 Boxster" in Wikipedia URL
        if brand_s == 'Porsche' and series_s in ('Boxster', 'Cayman'):
            s = urllib.parse.quote(series_s)
        return [
            f'https://en.wikipedia.org/wiki/{b}_{s}',
            f'https://en.wikipedia.org/wiki/{s}',
        ]

    url_candidates = make_urls(brand, series_name)
    html = ''
    used_url = ''

    for candidate_url in url_candidates:
        test_html = _fetch_with_retry(candidate_url, max_attempts=2, base_delay=1)
        if test_html and _looks_like_car_page(test_html, clean_name):
            html = test_html
            used_url = candidate_url
            break

    if not html:
        return None

    return _parse_series_html(brand, series_name, used_url, html)


def _looks_like_car_page(html, model_name):
    """快速判斷係咪汽車頁面（避免撞到 disambiguation 之類）。"""
    # Must have some car-related content
    car_indicators = ['engine', 'horsepower', 'mph', '0-100', 'km/h', 'transmission', 'drivetrain', 'layout']
    text_lower = html.lower()
    score = sum(1 for kw in car_indicators if kw in text_lower)
    if score < 2:
        return False
    # Must NOT be a disambiguation or list page
    if re.search(r'<h1[^>]*>.*?\(disambiguation\)', html, re.I):
        return False
    if re.search(r'<title>.*?List of.*?</title>', html, re.I):
        return False
    return True


def _parse_series_html(brand, series_name, url, html):
    """Parse series info from Wikipedia HTML."""
    info = {
        'series': series_name,
        'brand': brand,
        'url': url,
        'production': '',
        'engine': '',
        'horsepower': '',
        'layout': '',
        'source': 'Wikipedia',
        'tier': 2,
    }

    # Extract from infobox
    infobox_power = extract_wiki_infobox(html, 'power')
    infobox_engine = extract_wiki_infobox(html, 'engine')

    if infobox_power:
        hp = extract_hp(infobox_power)
        info['horsepower'] = hp + ' hp' if hp else infobox_power[:40]
    if infobox_engine:
        eng = extract_engine(infobox_engine)
        info['engine'] = eng if eng else infobox_engine[:60]

    # Production years
    years = re.findall(r'(19[5-9]\d|20[0-5]\d)', html)
    if years:
        years = sorted(set(years))
        if len(years) >= 2:
            info['production'] = f'{years[0]}–{years[-1]}'
        else:
            info['production'] = years[0]

    # Layout / body style
    layout_kw = ['layout', 'drivetrain', 'body style', 'class']
    for kw in layout_kw:
        val = extract_wiki_infobox(html, kw)
        if val:
            info['layout'] = val[:40]
            break

    return info


# ─────────────────────────────────────────────────────────────────────────────
# Generation Detection
# ─────────────────────────────────────────────────────────────────────────────

def find_generations_from_series(brand, series_name):
    """
    從 Wikipedia 車系頁面搵出所有世代。

    策略：
    1. 直接 URL 訪問 Wikipedia 頁面
    2. 搵 Generations 章節
    3. 如果冇，試 Variant Keywords 掃描（如果係已知多代車系）
    4. 如果都冇，回傳空列表（呢個係 standalone 型號，唔需要代數）
    """
    slug = slugify(series_name)
    clean_name = series_name.strip()
    series_lower = clean_name.lower()

    # 決定用邊個 URL（與 research_series_wikipedia 同步）
    def make_urls(brand_s, series_s):
        b = urllib.parse.quote(brand_s.replace(' ', '_'))
        s = urllib.parse.quote(series_s.replace(' ', '_'))
        if brand_s == 'Porsche' and series_s in ('Boxster', 'Cayman'):
            s = urllib.parse.quote(series_s)
        return [
            f'https://en.wikipedia.org/wiki/{b}_{s}',
            f'https://en.wikipedia.org/wiki/{s}',
        ]

    url_candidates = make_urls(brand, series_name)

    html = ''
    for candidate_url in url_candidates:
        test_html = _fetch_with_retry(candidate_url, max_attempts=2, base_delay=1)
        if test_html and _looks_like_car_page(test_html, clean_name):
            html = test_html
            break

    if not html:
        return []

    generations = []

    # ── 策略1: Generations 章節 ────────────────────────────────────────────
    gen_section = re.search(r'==\s*Generations?\s*==\s*(.+?)(?:==|\Z)', html, re.DOTALL | re.I)
    if gen_section:
        section_text = gen_section.group(1)
        for m in re.finditer(r'<li[^>]*>\s*<a[^>]*title="([^"]*?)"[^>]*>([^<]*?(20\d{2}|19\d{2})[^<]*?)</a>', section_text, re.I):
            name = clean_html(m.group(1))
            year = m.group(3) or ''
            if 3 < len(name) < 80:
                generations.append({'name': name, 'year': year, 'source': 'generations_section'})

    # ── 策略2: Variant Keywords（只針對已知多代車系）────────────────────────
    if not generations:
        # 快速判斷：係咪已知多代車系？
        short_known = len(clean_name) < 6 and series_lower in {
            '911', 'r35', 'r34', 'r33', 'r32', 'm3', 'm4', 'm5', 'm6',
            'gt-r', 'gtr', 'nsx', 'supra', 'rx7', 'rx8', 's2000',
        }
        is_known = series_lower in KNOWN_MULTI_GEN or short_known

        if not is_known:
            # 不是已知多代車系，大概率係 standalone 型號
            return []

        # 已知多代車系：掃描 variant 關鍵詞
        generations = _scan_variant_keywords(series_name, html)

    return generations


def _scan_variant_keywords(series_name, html):
    """
    掃描頁面 variant 關鍵詞，推測可能嘅代數/版本。
    只用於已知多代車系（如 911、M3、GTR 等）。
    """
    generations = []
    seen = set()

    # Compound variants first (must not split GT3 RS into GT3 + RS separately)
    compound_patterns = [
        r'\b(GT3\s*RS)\b', r'\b(GT3\s*Evo)\b', r'\b(GT2\s*RS)\b',
        r'\b(GT-R\s*GT3)\b', r'\b(Turbo\s*S)\b', r'\b(Competition\s*Sport)\b',
    ]
    for pat in compound_patterns:
        for m in re.finditer(pat, html, re.I):
            variant = clean_html(m.group(1)).strip()
            if variant and variant not in seen and len(variant) < 30:
                seen.add(variant)
                year_m = re.search(r'(20\d{2}|19\d{2})', html[max(0, m.start()-100):m.end()+100])
                year = year_m.group(1) if year_m else ''
                generations.append({'name': variant, 'year': year, 'source': 'variant_compound'})

    # Single variants with negative lookahead (avoid "caused by GT3")
    VK = r'\b(?!caused|which|that|this|have|with|from|in|are|was|were|has|had|not|but|and|for|out|over|the|a|an|by|its|their|you|all|same)\b'
    single_patterns = [
        rf'{VK}(Coupe|Berlinetta|Targa|Convertible|Spider|Cabriolet)\b',
        rf'{VK}(GTR|RS|SVR|S|VXR|AMG|Performance|Competition|Sport|Plus)\b',
        rf'{VK}(GT3|GT2|GT1)\b(?!\s*RS|\s*Evo)',
        rf'{VK}(V8|V6|V12|V10|TwinPower|Turbo)\b',
        rf'{VK}(Base|Standard|Limited|Edition|Heritage)\b',
    ]
    for pat in single_patterns:
        for m in re.finditer(pat, html, re.I):
            variant = clean_html(m.group(1)).strip()
            if variant and variant not in seen and len(variant) < 25:
                seen.add(variant)
                year_m = re.search(r'(20\d{2}|19\d{2})', html[max(0, m.start()-80):m.end()+80])
                year = year_m.group(1) if year_m else ''
                generations.append({'name': variant, 'year': year, 'source': 'variant_keyword'})

    return generations[:LIMIT_GEN]


# ─────────────────────────────────────────────────────────────────────────────
# Generation Page
# ─────────────────────────────────────────────────────────────────────────────

def research_generation_wikipedia(brand, series, generation_name):
    """
    從 Wikipedia 搵特定代數嘅詳細資料。
    generation_name 可以係 "GT3 RS" 或 "Carrera S" 之類。
    """
    gen_slug = slugify(generation_name)

    # URL 變體（與 research_series_wikipedia 同步策略）
    def make_gen_urls(brand_s, series_s, gen_s):
        b = urllib.parse.quote(brand_s.replace(' ', '_'))
        s = urllib.parse.quote(series_s.replace(' ', '_'))
        g = urllib.parse.quote(gen_s.replace(' ', '_'))
        if brand_s == 'Porsche' and series_s in ('Boxster', 'Cayman'):
            s = urllib.parse.quote(series_s)
        return [
            f'https://en.wikipedia.org/wiki/{b}_{s}_{g}',
            f'https://en.wikipedia.org/wiki/{s}_{g}',
            f'https://en.wikipedia.org/wiki/{g}',
        ]

    html = ''
    used_url = ''
    for candidate_url in make_gen_urls(brand, series, generation_name):
        # Variant generation pages (e.g. "911 Turbo S") often don't exist as dedicated Wikipedia articles
        # Use silent_404=True to suppress expected 404 warnings
        test_html = _fetch_with_retry(candidate_url, max_attempts=2, base_delay=1, silent_404=True)
        if test_html and _looks_like_car_page(test_html, generation_name):
            html = test_html
            used_url = candidate_url
            break

    if not html:
        # Fallback: 用 series page 嘅資料，唔特别搵 generation page
        return {
            'name': generation_name,
            'series': series,
            'brand': brand,
            'url': '',
            'production': '',
            'engine': '',
            'horsepower': '',
            'layout': '',
            'source': 'inferred',
            'tier': 3,
        }

    return _parse_generation_html(brand, series, generation_name, used_url, html)


def _parse_generation_html(brand, series, generation_name, url, html):
    """Parse generation info from Wikipedia HTML."""
    info = {
        'name': generation_name,
        'series': series,
        'brand': brand,
        'url': url,
        'production': '',
        'engine': '',
        'horsepower': '',
        'layout': '',
        'source': 'Wikipedia',
        'tier': 2,
    }

    infobox_power = extract_wiki_infobox(html, 'power')
    infobox_engine = extract_wiki_infobox(html, 'engine')

    if infobox_power:
        hp = extract_hp(infobox_power)
        info['horsepower'] = hp + ' hp' if hp else infobox_power[:40]
    if infobox_engine:
        eng = extract_engine(infobox_engine)
        info['engine'] = eng if eng else infobox_engine[:60]

    years = re.findall(r'(19[5-9]\d|20[0-5]\d)', html)
    if years:
        years = sorted(set(years))
        if len(years) >= 2:
            info['production'] = f'{years[0]}–{years[-1]}'
        else:
            info['production'] = years[0]

    layout_kw = ['layout', 'drivetrain', 'body style', 'class']
    for kw in layout_kw:
        val = extract_wiki_infobox(html, kw)
        if val:
            info['layout'] = val[:40]
            break

    return info


# ─────────────────────────────────────────────────────────────────────────────
# Wiki Writers
# ─────────────────────────────────────────────────────────────────────────────

def get_brand_color(brand):
    """Return representative color for brand."""
    colors = {
        'Ferrari': ('Rosso Corsa', '#FF2800'),
        'Lamborghini': ('Verde Scandal', '#00A650'),
        'Porsche': ('GT Silver', '#8C8C8C'),
        'McLaren': ('Papaya Spark', '#FF8000'),
        'Bugatti': ('Matte Blue', '#0057B8'),
        'Aston Martin': ('Skyfall Silver', '#C0C0C0'),
        'BMW': ('M Blue', '#1E90FF'),
        'Mercedes': ('AMG Silver', '#C0C0C0'),
        'Audi': ('Progress Red', '#CC0000'),
        'Nissan': ('GT-R Pearl', '#2B65EC'),
        'Toyota': ('Racing Red', '#CC0000'),
    }
    return colors.get(brand, ('Brand Color', '#888888'))


def write_brand_page(info):
    """Write brand overview page."""
    brand = info['name']
    slug = info['slug']
    brand_slug_dir = BRANDS_DIR / slug

    # Ensure brand directory exists
    brand_slug_dir.mkdir(parents=True, exist_ok=True)

    color_name, color_hex = get_brand_color(brand)
    model_list = '\n'.join(f'- {m}' for m in sorted(info.get('models', [])))

    body = f"""# {brand} — Brand Overview

## Brand Identity
- **Full Name**: {brand}
- **Country**: {info.get('country', 'N/A')}
- **Founded**: {info.get('founded', 'N/A')}
- **Representative Color**: {color_name} -> {color_hex}
- **Wikipedia**: {info.get('url', '')}
- **Data Source Tier**: {info.get('tier', 2)}

---

## Description

{info.get('description', 'No description available.')}

---

## Notable Models ({len(info.get('models', []))} found)
{model_list or '- No models found'}

---

## Sources
- {info.get('url', '')}
"""

    out_path = brand_slug_dir / 'index.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(body)
    log(f'  ✓ Brand page written: {out_path}')
    return out_path


def write_series_page(brand_info, series_info, generations_data):
    """Write series overview page (NO TABLE — Telegram compliant)."""
    brand = brand_info['name']
    series = series_info['series']
    slug = slugify(series)
    series_dir = SERIES_DIR / slugify(brand) / slug

    series_dir.mkdir(parents=True, exist_ok=True)

    hp = series_info.get('horsepower', 'N/A')
    hp_flag = ''
    if hp and hp not in ('N/A', ''):
        m = re.search(r'\d+', hp)
        if m:
            val = int(m.group())
            if val < 50 or val > 2000:
                hp_flag = ' ⚠️'

    # Build generations nodes
    gen_nodes = []
    for i, gen in enumerate(generations_data[:LIMIT_GEN], 1):
        gen_hp = gen.get('horsepower', 'N/A')
        gen_eng = gen.get('engine', 'N/A')
        gen_prod = gen.get('production', 'N/A')
        gen_url = gen.get('url', series_info.get('url', ''))
        gen_nodes.append(f"""🅿️ Node {i}: {gen.get('name', 'Unknown')} ({gen_prod}) — {gen.get('name', '')}

    • 品牌/車系: {brand} / {series}
    • 引擎核心: {gen_eng}
    • 馬力資料: {gen_hp}{hp_flag}
    • 傳動配置: {gen.get('layout', 'N/A')}
    • 進化點: 【Generation variant】{gen.get('name', '')}
    • 🖼️ [Google Images](https://www.google.com/search?tbm=isch&q={urllib.parse.quote(f'{brand} {series} {gen.get("name", "")}')})""")

    gen_block = '\n\n'.join(gen_nodes) if gen_nodes else '*No generations detected — this may be a standalone model.*'

    body = f"""# {brand} {series} — Evolution Wiki

## Series Overview
- **Brand**: {brand}
- **Production**: {series_info.get('production', 'N/A')}
- **Engine**: {series_info.get('engine', 'N/A')}
- **Horsepower**: {hp}{hp_flag}
- **Layout**: {series_info.get('layout', 'N/A')}
- **Data Source Tier**: {series_info.get('tier', 2)}

---

## Generations

{gen_block}

---

## Sources
- Wikipedia: {series_info.get('url', '')}
"""

    out_path = series_dir / f'{slug}.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(body)
    log(f'  ✓ Series page written: {out_path}')
    return out_path


def write_generation_page(brand_info, series_info, gen_info):
    """Write individual generation/deep-dive page."""
    brand = brand_info['name']
    series = series_info['series']
    gen = gen_info['name']
    slug = slugify(gen)

    gen_dir = GEN_DIR / slugify(brand) / slugify(series)
    gen_dir.mkdir(parents=True, exist_ok=True)

    color_name, color_hex = get_brand_color(brand)

    hp = gen_info.get('horsepower', 'N/A')
    hp_flag = ''
    if hp and hp not in ('N/A', ''):
        m = re.search(r'\d+', hp)
        if m:
            val = int(m.group())
            if val < 50 or val > 2000:
                hp_flag = ' ⚠️'

    body = f"""# {brand} {series} {gen} — Generation

## Generation Overview
- **Brand/Series**: {brand} / {series}
- **Generation Name**: {gen}
- **Production**: {gen_info.get('production', 'N/A')}
- **Engine**: {gen_info.get('engine', 'N/A')}
- **Horsepower**: {hp}{hp_flag}
- **Layout**: {gen_info.get('layout', 'N/A')}
- **Representative Color**: {color_name} -> {color_hex}
- **Data Source Tier**: {gen_info.get('tier', 3)}

---

## Evolution Point
【Core variant】 {gen}

---

## Sources
- Wikipedia: {gen_info.get('url', series_info.get('url', ''))}
"""

    out_path = gen_dir / f'{slug}.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(body)
    log(f'  ✓ Generation page written: {out_path}')
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Wiki Index
# ─────────────────────────────────────────────────────────────────────────────

def update_wiki_index():
    """Update wiki/index.md with current counts."""
    # Count brand pages (brand dirs and brand .md files)
    brands = []
    for p in BRANDS_DIR.iterdir():
        if p.is_dir():
            brands.append(p.name)
        elif p.suffix == '.md':
            brands.append(p.stem)
    # Count series pages
    series = []
    for brand_dir in SERIES_DIR.iterdir():
        if brand_dir.is_dir():
            for p in brand_dir.iterdir():
                if p.suffix == '.md':
                    series.append(p.stem)
    # Count generation pages
    gens = []
    for brand_dir in GEN_DIR.iterdir():
        if brand_dir.is_dir():
            for series_dir in brand_dir.iterdir():
                if series_dir.is_dir():
                    for p in series_dir.iterdir():
                        if p.suffix == '.md':
                            gens.append(p.stem)

    brands_count = len(brands)
    series_count = len(series)
    gen_count = len(gens)

    log(f'  ✓ Index updated: {brands_count} brands, {series_count} series, {gen_count} generations')
    return brands_count, series_count, gen_count


# ─────────────────────────────────────────────────────────────────────────────
# Priority Scoring (keep existing)
# ─────────────────────────────────────────────────────────────────────────────

def load_competitor_blue_ocean():
    """Load competitor report blue ocean brands."""
    path = BASE / 'agent-meta' / 'competitor-report.md'
    if not path.exists():
        return []
    with open(path, encoding='utf-8') as f:
        content = f.read()
    blues = re.findall(r'\*\*(.+?)\*\*', content)
    return [b for b in blues if 3 < len(b) < 30]

def load_news_mentions():
    """Count brand mentions in recent news."""
    news_dir = BASE / 'data' / 'daily-news'
    if not news_dir.exists():
        return defaultdict(int)
    mentions = defaultdict(int)
    today = datetime.now()
    for f in news_dir.glob('*.md'):
        if (today - datetime.fromtimestamp(f.stat().st_mtime)).days > 3:
            continue
        with open(f, encoding='utf-8', errors='ignore') as fh:
            text = fh.read().lower()
        for brand in BRAND_MODELS:
            if brand.lower() in text:
                mentions[brand] += 1
    return mentions

def load_trends():
    """Load Google Trends data."""
    path = BASE / 'agent-meta' / 'trend-report.md'
    if not path.exists():
        return {}
    with open(path, encoding='utf-8') as f:
        content = f.read()
    trends = {}
    for line in content.split('\n'):
        for brand in BRAND_MODELS:
            if brand in line and re.search(r'\d+', line):
                m = re.search(r'(\d+)', line)
                if m:
                    trends[brand] = int(m.group(1))
    return trends

def load_queue_priority():
    """Load queue.jsonl priority scores."""
    items = read_jsonl(QUEUE_FILE)
    priority = {}
    for item in items:
        brand = item.get('brand', '')
        if brand and brand in BRAND_MODELS:
            priority[brand] = item.get('priority', 0)
    return priority

def compute_priority_scores():
    """Compute weighted priority scores across all sources."""
    blues = load_competitor_blue_ocean()
    news = load_news_mentions()
    trends = load_trends()
    queue = load_queue_priority()

    scores = []
    for brand in BRAND_MODELS:
        blue = 1.0 if brand in blues else 0.0
        news_s = news.get(brand, 0)
        trend_s = trends.get(brand, 0)
        queue_s = queue.get(brand, 0)

        max_news = max(news.values(), default=1) or 1
        max_trend = max(trends.values(), default=1) or 1
        max_queue = max(queue.values(), default=1) or 1

        score = (
            0.40 * blue +
            0.30 * (news_s / max_news) +
            0.20 * (trend_s / max_trend) +
            0.10 * (queue_s / max_queue)
        )
        scores.append((brand, score, {
            'competitor': blue,
            'news_mentions': news_s,
            'trends': trend_s,
            'queue_priority': queue_s,
        }))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Main Ingestion Logic
# ─────────────────────────────────────────────────────────────────────────────

def ingest_brand(brand_name, dry_run=False):
    """
    攝取單一品牌的完整資料（brand → series → generations）。
    完全重新設計：每一步都有明確 error handling。
    """
    log(f'🔍 Ingesting brand: {brand_name}', file=INGEST_LOG if not dry_run else None)

    # Step 1: Research brand
    log(f'  → Researching brand from Wikipedia...')
    brand_info = research_brand_wikipedia(brand_name)
    if not brand_info:
        log(f'  ✗ Brand research failed for {brand_name}', file=INGEST_LOG if not dry_run else None)
        return None

    log(f'  ✓ Found {len(brand_info.get("models", []))} models for {brand_name}')

    if not dry_run:
        write_brand_page(brand_info)
        append_log('INGEST', f'Brand ingested: {brand_name} — tier={brand_info["tier"]}')
        append_ingest_log('INGEST', f'brand={brand_name} slug={brand_info["slug"]} tier={brand_info["tier"]}')

    # Step 2: Find and research series
    models = brand_info.get('models', [])
    if not models:
        log(f'  ⚠️  No models found for {brand_name}, skipping series')
    else:
        log(f'  → Finding series from {len(models)} models...')

    series_results = []
    for model in models[:LIMIT_SERIES]:
        log(f'    → Researching series: {model}')
        series_info = research_series_wikipedia(brand_name, model)
        if not series_info:
            log(f'      ✗ Failed to research {model}')
            continue

        # Step 3: Find generations for this series
        generations_data = []
        gen_candidates = find_generations_from_series(brand_name, model)

        # Deduplicate by slug before writing
        seen_slugs = set()
        unique_candidates = []
        for gc in gen_candidates:
            slug = slugify(gc['name'])
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                unique_candidates.append(gc)
        gen_candidates = unique_candidates[:LIMIT_GEN]

        log(f'      → Found {len(gen_candidates)} generation candidates for {model}')

        for gen_candidate in gen_candidates[:LIMIT_GEN]:
            gen_info = research_generation_wikipedia(
                brand_name, model, gen_candidate['name']
            )
            if gen_info:
                gen_info['evolution_point'] = f'Generation: {gen_candidate.get("name", "?")}'
                gen_info['description'] = f'{brand_name} {gen_candidate.get("name", "")}'
                # Avoid duplicate slug in generations_data
                if slugify(gen_info['name']) not in {slugify(g['name']) for g in generations_data}:
                    generations_data.append(gen_info)
                    if not dry_run:
                        write_generation_page(brand_info, series_info, gen_info)

        series_info['series'] = model
        series_results.append((series_info, generations_data[:LIMIT_GEN]))

        if not dry_run:
            write_series_page(brand_info, series_info, generations_data[:LIMIT_GEN])
            append_log('INGEST', f'Series ingested: {model} — brand={brand_name}')
            append_ingest_log('INGEST', f'series={model} brand={brand_name} generations={len(generations_data)}')

    # Step 4: Update index
    if not dry_run:
        update_wiki_index()

    total_gens = sum(len(g) for _, g in series_results)
    log(f'  ✓ Brand {brand_name} ingested: 1 brand, {len(series_results)} series, {total_gens} generations',
        file=INGEST_LOG if not dry_run else None)

    return {
        'brand': brand_info,
        'series': series_results,
    }


def run_ingestion(dry_run=False, brand=None):
    """
    主入口：運行自動攝取流程。
    """
    log('═' * 60, file=INGEST_LOG if not dry_run else None)
    log(f'AUTO WIKI INGESTION — {"DRY RUN" if dry_run else "LIVE"}', file=INGEST_LOG if not dry_run else None)
    log(f'Started: {datetime.now().strftime("%Y-%m-%d %H:%M")}', file=INGEST_LOG if not dry_run else None)

    if brand:
        result = ingest_brand(brand, dry_run=dry_run)
        return [result] if result else []

    # Compute priorities
    log('\n📊 Computing priority scores...')
    scores = compute_priority_scores()

    log('\n📈 Priority Ranking:')
    for i, (brand_name, score, breakdown) in enumerate(scores[:10], 1):
        log(f'  {i:2}. {brand_name:<20} score={score:.1f}  '
            f'(comp={breakdown["competitor"]} news={breakdown["news_mentions"]} '
            f'trend={breakdown["trends"]} queue={breakdown["queue_priority"]})')

    candidates = [
        (b, s, br) for b, s, br in scores
        if not brand_exists(b) and is_cooldown_ok(b)
    ]

    if not candidates:
        log('⚠️  No eligible brands (all exist or in cooldown). '
            'Run with --brand <name> to force.')
        return []

    results = []
    for brand_name, score, breakdown in candidates[:LIMIT_BRAND]:
        log(f'\n🎯 Ingesting #{1}: {brand_name} (score={score:.1f})')
        result = ingest_brand(brand_name, dry_run=dry_run)
        if result:
            results.append(result)

    log('\n' + '═' * 60)
    log(f'INGESTION COMPLETE — {"DRY RUN" if dry_run else "LIVE"}')
    log(f'Brands: {len(results)}')
    total_series = sum(len(r["series"]) for r in results)
    total_gens   = sum(sum(len(g) for _, g in r["series"]) for r in results)
    log(f'Series: {total_series}')
    log(f'Generations: {total_gens}')
    log(f'Log: {INGEST_LOG}', file=INGEST_LOG if not dry_run else None)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Auto-Wiki Ingestion Pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Test mode (no writes)')
    parser.add_argument('--brand', type=str, help='Specify brand to ingest')
    parser.add_argument('--limit', type=int, default=LIMIT_BRAND, help='Max brands per run')

    args = parser.parse_args()

    if args.brand:
        result = run_ingestion(dry_run=args.dry_run, brand=args.brand)
    else:
        result = run_ingestion(dry_run=args.dry_run)

    if not result:
        print('\nNo brands ingested. Use --dry-run to test, or --brand <name> to force.')
        sys.exit(1)

    sys.exit(0)
