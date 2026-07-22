#!/usr/bin/env python3
# scripts/daily_news_fetcher.py
# Fetches latest car news from RSS feeds with article summaries
# Run: python3 scripts/daily_news_fetcher.py

import urllib.request, urllib.error, ssl, re, time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE     = Path(__file__).parent.parent
DB       = BASE / 'data' / 'cars.db'
BRIEF    = BASE / 'agent-meta' / 'daily-brief.md'
NEWS_DIR = BASE / 'data' / 'daily-news'

RSS_FEEDS = [
    ('TopGear',      'https://news.google.com/rss/search?q=cars+site:topgear.com&hl=en-US&gl=US&ceid=US:en'),
    ('CarAndDriver', 'https://www.caranddriver.com/rss/all.xml'),
    ('RoadandTrack', 'https://www.roadandtrack.com/rss/all.xml'),
    ('Autocar',      'https://www.autocar.co.uk/rss'),
    ('Jalopnik',     'https://jalopnik.com/feed'),
    ('Evo-GN',       'https://news.google.com/rss/search?q=site:evo.co.uk&hl=en-US&gl=US&ceid=US:en'),
    ('MotorTrend',   'https://news.google.com/rss/search?q=site:motortrend.com+cars&hl=en-US&gl=US&ceid=US:en'),
    ('Motor1',       'https://www.motor1.com/rss/news/all/'),
    ('Autoblog',     'https://www.carscoops.com/feed'),
    ('InsideEVs',    'https://insideevs.com/feed/'),
    ('SupercarBlog', 'https://www.thesupercarblog.com/feed/'),
]

# Google News redirector fix — convert Google News URLs to direct article URLs
def fix_google_news_url(url):
    """Convert Google News redirect URLs to direct article URLs."""
    if 'news.google.com' in url and '/search?' in url:
        # Extract the actual URL from Google's redirect
        match = re.search(r'url=([^&]+)', url)
        if match:
            import urllib.parse
            return urllib.parse.unquote(match.group(1))
    return url

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def log(msg): print(f'[{datetime.now().strftime("%H:%M")}] {msg}')

def parse_date(date_str):
    """Parse various date formats and return datetime object."""
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',      # RFC 822: 'Thu, 01 May 2026 10:00:00 +0000'
        '%Y-%m-%dT%H:%M:%S%z',           # ISO 8601: '2026-05-01T10:00:00+0000'
        '%Y-%m-%dT%H:%M:%SZ',            # ISO 8601 UTC: '2026-05-01T10:00:00Z'
        '%Y-%m-%d %H:%M:%S',             # Simple: '2026-05-01 10:00:00'
        '%Y-%m-%d',                       # Date only: '2026-05-01'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.replace(' GMT', ' +0000'), fmt)
        except ValueError:
            continue
    return None

def is_recent(date_str, days=7, hard_cutoff_days=30):
    """Check if article is within the last N days.
    
    Args:
        date_str: Date string from RSS feed
        days: Soft window for preferred freshness (default 7)
        hard_cutoff_days: Articles older than this are ALWAYS rejected,
                          even if they can be parsed (default 30).
                          This prevents dead feeds from spamming stale articles.
    """
    dt = parse_date(date_str)
    if dt is None:
        return True  # If can't parse date, include it (might be fresh)
    # Make timezone naive for comparison
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    now = datetime.now()
    age_days = (now - dt).days
    # Hard cutoff: reject anything older than hard_cutoff_days
    if age_days >= hard_cutoff_days:
        return False
    return age_days < days

def fetch_feed_with_retry(name, url, retries=3, timeout=15):
    """
    Fetch RSS feed with retry on transient network errors.
    Transient errors: DNS fail, timeout, connection reset
    Non-transient: 404, 403, 500 — do NOT retry
    """
    transient_errors = (
        'Temporary failure in name resolution',  # DNS
        'Name or service not known',             # DNS
        'Connection reset',                       # Network
        'Connection refused',                      # Network
        'timed out',                              # Timeout
        'Read timed out',                          # Timeout
        'Connection aborted',                      # Network
        'Network is unreachable',                 # Network
    )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            entries = []

            # Atom format
            for e in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:10]:
                title     = e.find('{http://www.w3.org/2005/Atom}title')
                link_el   = e.find('{http://www.w3.org/2005/Atom}link')
                published = e.find('{http://www.w3.org/2005/Atom}updated') or e.find('{http://www.w3.org/2005/Atom}published')
                raw_link  = link_el.get('href') if link_el is not None else ''
                entries.append({
                    'title':     title.text if title is not None else '',
                    'link':      fix_google_news_url(raw_link) if 'google.com' in url else raw_link,
                    'published': published.text if published is not None else '',
                    'source':    name,
                })

            # RSS format
            if not entries:
                for e in root.findall('.//item')[:10]:
                    title     = e.find('title')
                    link_el   = e.find('link')
                    published = e.find('pubDate')
                    raw_link  = link_el.text if link_el is not None else ''
                    entries.append({
                        'title':     title.text if title is not None else '',
                        'link':      fix_google_news_url(raw_link) if 'google.com' in url else raw_link,
                        'published': published.text if published is not None else '',
                        'source':    name,
                    })

            # Filter by date: hard 30-day cutoff for ALL feeds,
            # soft 7-day window for Google News feeds (they mix old + new)
            entries = [e for e in entries if is_recent(e['published'], days=7, hard_cutoff_days=30)]

            # For Google News feeds, further limit to recent items
            if 'google.com' in url:
                entries = entries[:5]

            if entries:
                log(f'{name}: {len(entries)} articles')
                return entries
            else:
                # Empty feed — might be non-transient (e.g. feed removed)
                log(f'{name}: empty feed (no articles)')
                return []

        except urllib.error.HTTPError as e:
            # Non-transient — don't retry
            log(f'Error fetching {name}: HTTP {e.code} ({url})')
            return []
        except urllib.error.URLError as e:
            last_error = str(e)
            is_transient = any(err in last_error for err in transient_errors)
            if not is_transient or attempt == retries:
                log(f'Error fetching {name} (attempt {attempt}/{retries}): {last_error}')
                return []
            log(f'Retry {attempt}/{retries} for {name}: {last_error}')
            time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            last_error = str(e)
            log(f'Error fetching {name} (attempt {attempt}/{retries}): {last_error}')
            return []

    return []


# Backward-compatible alias
def fetch_feed(name, url):
    return fetch_feed_with_retry(name, url, retries=3, timeout=15)

def fetch_article_summary(url, timeout=8):
    """Fetch article summary/description from the article page."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Accept': 'text/html,application/xhtml+xml',
        })
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        # Try meta description
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{50,})["\']',
            r'<meta[^>]+content=["\']([^"\']{50,})["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{50,})["\']',
            r'<meta[^>]+content=["\']([^"\']{50,})["\'][^>]+property=["\']og:description["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                desc = match.group(1)
                # Clean HTML tags
                desc = re.sub(r'<[^>]+>', '', desc)
                desc = desc.strip()[:200]
                if len(desc) > 50:
                    return desc
        
        # Try to extract first paragraph
        p_match = re.search(r'<p[^>]*>([^<]{100,})</p>', html, re.IGNORECASE)
        if p_match:
            return p_match.group(1).strip()[:200]
        
        return ''
    except Exception as e:
        return ''

def fetch_article_summary_with_retry(url, retries=2):
    """Fetch with retry on failure."""
    for attempt in range(retries):
        summary = fetch_article_summary(url)
        if summary:
            return summary
        time.sleep(1)
    return ''

# Simple Chinese translation for common car news terms
CHINESE_TERMS = {
    'suv': 'SUV 越野車', 'electric': '電動車', 'ev': '電動車', 'hybrid': '混合動力',
    'performance': '性能', 'luxury': '豪華', 'sport': '運動', 'gt': 'GT跑車',
    'hatchback': '揭背車', 'sedan': '轎車', 'coupe': '雙門轎跑', 'convertible': '開篷車',
    'pickup': '皮卡', 'van': '客貨車', 'wagon': '旅行車',
    'launch': '發布', 'review': '評測', 'test': '試駕', 'first drive': '首次試駕',
    'official': '官方', 'unveiled': '亮相', 'debut': '首發', 'price': '價格',
    'revealed': '揭曉', 'confirmed': '確認', 'coming': '來了', 'new': '全新',
    '2024': '2024年', '2025': '2025年', '2026': '2026年',
    'million': '百萬', 'hp': '匹', 'bhp': '匹', 'mph': 'mph',
    'automatic': '自動波', 'manual': '手波', 'awd': '四驅', 'fwd': '前驅', 'rwd': '後驅',
    'engine': '引擎', 'motor': '摩打', 'battery': '電池', 'range': '續航',
    'top speed': '極速', 'acceleration': '加速', '0-60': '0-100',
    'power': '馬力', 'torque': '扭力',
    ' BMW ': ' 寶馬 ', ' Mercedes': ' 奔馳 ', ' Audi ': ' 奧迪 ',
    ' Porsche ': ' 保時捷 ', ' Ferrari ': ' 法拉利 ', ' Lamborghini ': ' 林寶堅尼 ',
    ' McLaren ': ' 麥拿倫 ', ' Jaguar ': ' 積架 ', ' Land Rover ': ' 越野路華 ',
    ' Range Rover ': ' 攬勝 ', ' Bentley ': ' 賓利 ', ' Rolls-Royce ': ' 勞斯萊斯 ',
    ' Aston Martin ': ' 愛快羅密歐 ', ' Tesla ': ' 特斯拉 ',
    ' Toyota ': ' 豐田 ', ' Honda ': ' 本田 ', ' Nissan ': ' 日產 ',
    ' Mazda ': ' 萬事得 ', ' Subaru ': ' 富士 ', ' Mitsubishi ': ' 三菱 ',
    ' Hyundai ': ' 現代 ', ' Kia ': ' 起亞 ', ' Genesis ': ' 捷尼賽思 ',
    ' Ford ': ' 福特 ', ' Chevrolet ': ' 雪佛蘭 ', ' Dodge ': ' 道奇 ',
    ' Ram ': ' 公羊 ', ' GMC ': ' GMC ', ' Jeep ': ' 吉普 ',
    ' Polestar ': ' 極星 ', ' Rivian ': ' Rivian ', ' Lucid ': ' Lucid ',
    ' BYD ': ' 比亞迪 ', ' Xiaomi ': ' 小米 ', ' Huawei ': ' 華為 ',
}

def translate_to_chinese(title):
    """Simple rule-based translation of car news titles to Chinese."""
    result = title
    for eng, chi in CHINESE_TERMS.items():
        result = re.sub(eng, chi, result, flags=re.IGNORECASE)
    return result

def translate_titles_llm(titles, api_key=None):
    """Translate English titles to Traditional Chinese using MiniMax-M2.7 Anthropic API."""
    if not titles:
        return titles
    
    if not api_key:
        return [translate_to_chinese(t) for t in titles]
    
    import json
    
    # MiniMax-M2.7 Anthropic-compatible endpoint
    base_url = 'https://api.minimaxi.com/anthropic/v1/messages'
    
    brand_glossary = (
        "Brand translations: BMW=寶馬, Mercedes-Benz/AMG=平治, Audi=奧迪, Porsche=保時捷, "
        "Ferrari=法拉利, Lamborghini=林寶堅尼, McLaren=麥拿倫, Jaguar=積架, "
        "Land Rover=越野路華, Range Rover=攬勝, Bentley=賓利, Rolls-Royce=勞斯萊斯, "
        "Aston Martin=愛快羅密歐, Tesla=特斯拉, Toyota=豐田, Honda=本田, "
        "Nissan=日產, Mazda=萬事得, Subaru=富士, Mitsubishi=三菱, "
        "Hyundai=現代, Kia=起亞, Genesis=捷尼賽思, Ford=福特, "
        "Chevrolet=雪佛蘭, Dodge=道奇, Ram=公羊, Jeep=吉普, "
        "Polestar=極星, Rivian=Rivian, Lucid=Lucid, BYD=比亞迪, "
        "Xiaomi=小米, Huawei=華為, Cupra=Cupra, Alpine=Alpine, "
        "Caterham=Caterham, Morgan=Morgan, Lotus=蓮花, "
        "Bugatti=布加迪, Maserati=瑪莎拉蒂"
    )
    prompt = f"""Translate these car news titles to Cantonese Chinese. Use brand translations below.
Reply: one translation per line only, no numbers, no explanations, no quotes.

Brand translations: {brand_glossary}

{chr(10).join(f'{t}' for i, t in enumerate(titles))}"""
    
    try:
        data = json.dumps({
            'model': 'MiniMax-M2.7',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 2000,
            'thinking': {'type': 'off'},
        }).encode('utf-8')
        
        req = urllib.request.Request(
            base_url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'anthropic-version': '2023-06-01',
            },
            method='POST',
        )
        
        with urllib.request.urlopen(req, timeout=120, context=CTX) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result.get('content', [])
            
            # Get text from content blocks - expect plain text, one translation per line
            for c in content:
                if c.get('type') == 'text':
                    response_text = c.get('text', '').strip()
                    lines_raw = response_text.split('\n')
                    translations = []
                    for line in lines_raw:
                        line = line.strip()
                        # Skip empty lines and explanatory lines
                        if not line or re.match(r'^[A-Z][a-z]', line) or line.startswith(('Here', 'The', 'A ', 'This', 'These', 'That', 'These')):
                            continue
                        # Remove leading numbers/dots like "1. " or "1) "
                        line = re.sub(r'^[\d\.\)\-]+\s*', '', line).strip()
                        if line and len(line) > 3:
                            translations.append(line)
                    if len(translations) >= len(titles):
                        log(f'Translated {len(translations)} titles via MiniMax-M2.7')
                        return translations[:len(titles)]
    except Exception as e:
        log(f'MiniMax translation failed: {e}')
    
    return [translate_to_chinese(t) for t in titles]

def update_brief(entries, max_articles=20, llm_api_key=None, feed_status=None):
    """Generate detailed brief with article summaries and bilingual titles."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build feed status summary
    feed_ok = sum(1 for s in (feed_status or []) if s['ok'])
    feed_fail = sum(1 for s in (feed_status or []) if not s['ok'])
    freshness = f"✅ LIVE ({feed_ok} feeds OK" + (f", {feed_fail} failed)" if feed_fail else ")")

    lines = [
        f'# 📰 Daily Brief — {datetime.now().strftime("%Y-%m-%d")}',
        '',
        f'## ⚠️ DATA FRESHNESS',
        f'- **Status:** {freshness}',
        f'- **Generated:** {now_str} HKT',
        f'- **Articles:** {len(entries)}',
        '',
        f'## 🏎️ Top Headlines ({len(entries)} articles from {feed_ok} sources)',
        '',
    ]

    if feed_status:
        status_parts = [f'{s["name"]}: {"✅" if s["ok"] else "❌"}' for s in feed_status]
        lines.append(f'📡 **Feeds:** {", ".join(status_parts)}')
        lines.append('')

    # Fetch summaries in parallel (faster)
    entries = entries[:max_articles]
    links = [e['link'] for e in entries]
    summaries = [''] * len(entries)
    
    # Parallel fetch (limited concurrency to avoid overwhelming servers)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_idx = {
            executor.submit(fetch_article_summary_with_retry, link): i 
            for i, link in enumerate(links)
        }
        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            try:
                summaries[i] = future.result()
            except:
                summaries[i] = ''
    
    # Prepare English titles for translation
    titles_en = []
    for e in entries:
        title_en = e['title']
        title_en = re.sub(r'&amp;', '&', title_en)
        title_en = re.sub(r'&[a-z]+;', '', title_en)
        title_en = title_en.strip()
        titles_en.append(title_en)
    
    # Translate titles (LLM or rule-based fallback)
    titles_cn = translate_titles_llm(titles_en, api_key=llm_api_key)
    if llm_api_key:
        log(f'Using API key for {len(titles_en)} titles')
    
    for i, (e, title_en, title_cn) in enumerate(zip(entries, titles_en, titles_cn), 1):
        lines.append(f'**{i}. [{e["source"]}] {title_en}**')
        lines.append(f'   🇨🇳 {title_cn}')
        lines.append(f'🔗 {e["link"]}')
        
        # Add summary if available
        if summaries[i-1]:
            summary = summaries[i-1][:150] + '...' if len(summaries[i-1]) > 150 else summaries[i-1]
            lines.append(f'   📝 {summary}')
        lines.append('')
    
    lines.append('---')
    lines.append(f'*🤖 Auto-generated at {datetime.now().strftime("%Y-%m-%d %H:%M")}*')
    lines.append(f'*📊 Data: {len(entries)} articles with summaries from 9 RSS feeds*')
    
    BRIEF.write_text('\n'.join(lines), encoding='utf-8')
    log(f'Updated daily-brief.md with {len(entries)} detailed articles (bilingual)')

def main():
    import os
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    # Try to get MiniMax CN API key from environment or .env file
    llm_api_key = os.environ.get('MINIMAX_CN_API_KEY', None)
    if not llm_api_key or llm_api_key in ('', '***'):
        env_file = Path.home() / '.hermes' / '.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith('MINIMAX_CN_API_KEY='):
                    val = line.split('=', 1)[1].strip()
                    if val and val not in ('', '***'):
                        llm_api_key = val
                        break
    # Fallback 2: read from backup key file
    if not llm_api_key or llm_api_key in ('', '***'):
        key_file = Path.home() / '.hermes' / '.env.minimax-key'
        if key_file.exists():
            llm_api_key = key_file.read_text().strip()
    # Fallback 3: environment variable
    if not llm_api_key or llm_api_key in ('', '***'):
        llm_api_key = os.environ.get('MINIMAX_CN_API_KEY_FALLBACK', None)
    all_entries = []
    feed_status = []
    stale_feeds = []
    for name, url in RSS_FEEDS:
        entries = fetch_feed(name, url)
        is_ok = len(entries) > 0
        feed_status.append({'name': name, 'ok': is_ok})

        # Check if feed is stale (all articles older than 30 days)
        if entries:
            newest_date = max(
                (parse_date(e.get('published', '')) for e in entries),
                key=lambda d: d or datetime.min
            )
            if newest_date:
                if newest_date.tzinfo is not None:
                    newest_date = newest_date.replace(tzinfo=None)
                age_days = (datetime.now() - newest_date).days
                if age_days >= 30:
                    stale_feeds.append(f'{name} (newest={age_days}d old)')
                    log(f'⚠️ STALE feed: {name} — newest article is {age_days} days old, skipping')
                    feed_status[-1]['ok'] = False
                    continue  # Skip stale feed entirely

        all_entries.extend(entries)
    all_entries.sort(key=lambda x: x.get('published', ''), reverse=True)
    # Telegram delivery needs ALL 20 headlines (per AGENTS.md + cron task spec).
    # Website pipeline (news_to_website.py) has its own MAX_POSTS=5 cap,
    # so raising this to 20 only affects the brief / Telegram, not the website.
    TOP_N = 20
    update_brief(all_entries[:TOP_N], max_articles=TOP_N, llm_api_key=llm_api_key, feed_status=feed_status)
    log(f'Done. Fetched {len(all_entries)} total articles, keeping top {TOP_N}')

if __name__ == '__main__':
    main()
