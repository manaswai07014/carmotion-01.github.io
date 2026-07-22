#!/usr/bin/env python3
"""
article_body_fetcher.py — Extract readable body text from a news article.

Strategy (in order, return on first hit):
  1. Next.js __NEXT_DATA__ → props.pageProps.content (TopGear, Motor1, InsideEVs)
  2. JSON-LD NewsArticle → articleBody or description
  3. <meta og:description> + visible <article><p> paragraphs
  4. <meta description>

For each source, return:
  - title (if detectable)
  - lede (1-2 sentence summary)
  - paragraphs (list of plain-text body paragraphs, original wording)

Usage:
    from article_body_fetcher import fetch_article_body
    body = fetch_article_body(real_source_url)
    if body:
        for p in body['paragraphs']:
            print(p)
"""
import json
import re
import ssl
import urllib.parse
import urllib.request

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _fetch(url: str, timeout: int = 15) -> tuple:
    headers = {"User-Agent": _UA, "Accept": "text/html,*/*"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.getcode(), r.read()
    except Exception as e:
        return 0, str(e).encode()


def _html_to_plain(html_fragment: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    # Replace <p> and <br> with newlines
    s = re.sub(r'<br\s*/?>', '\n', html_fragment, flags=re.I)
    s = re.sub(r'</p>', '\n\n', s, flags=re.I)
    # Strip all other tags
    s = re.sub(r'<[^>]+>', '', s)
    # Decode common entities
    s = s.replace('&nbsp;', ' ').replace('&', '&').replace('"', '"')
    s = s.replace('&#39;', "'").replace('<', '<').replace('>', '>')
    s = s.replace('&hellip;', '...').replace('&pound;', '£').replace('&euro;', '€')
    # Collapse whitespace per line, strip empties
    lines = [re.sub(r'\s+', ' ', l).strip() for l in s.split('\n')]
    return '\n'.join(l for l in lines if l)


def _try_next_data(html: str) -> dict:
    """Strategy 1: Next.js __NEXT_DATA__ script-tag."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None
    # Walk for a "content" or "body" field longer than 300 chars
    found_body = None
    found_summary = None
    def walk(obj):
        nonlocal found_body, found_summary
        if isinstance(obj, dict):
            for k in ('content', 'body', 'articleBody'):
                if k in obj and isinstance(obj[k], str) and len(obj[k]) > 300:
                    found_body = obj[k]
                    return
            for k in ('description', 'summary', 'lede'):
                if k in obj and isinstance(obj[k], str) and 30 < len(obj[k]) < 500:
                    if not found_summary:
                        found_summary = obj[k]
            for v in obj.values():
                if found_body:
                    return
                walk(v)
        elif isinstance(obj, list):
            for item in obj[:30]:
                walk(item)
                if found_body:
                    return
    walk(data)
    if not found_body:
        return None
    # The "content" field is typically raw HTML with <p> tags
    paragraphs = []
    for m in re.findall(r'<p[^>]*>(.*?)</p>', found_body, re.S):
        text = _html_to_plain(m)
        if text and len(text) > 30:
            paragraphs.append(text)
    if not paragraphs:
        # parsed no <p> — fall back to plain text
        plain = _html_to_plain(found_body).strip()
        paragraphs = [p.strip() for p in plain.split('\n\n') if p.strip() and len(p) > 30]
    return {"lede": found_summary or "", "paragraphs": paragraphs}


def _try_json_ld(html: str) -> dict:
    """Strategy 2: JSON-LD NewsArticle.articleBody or description."""
    ld_matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S)
    for m in ld_matches:
        try:
            data = json.loads(m)
        except json.JSONDecodeError:
            continue
        if data.get('@type') not in ('NewsArticle', 'Article', 'ReportageNewsArticle'):
            continue
        body = data.get('articleBody') or ''
        summary = data.get('description') or ''
        if body and len(body) > 300:
            # Could be plain text or HTML
            paragraphs = []
            for m2 in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S):
                text = _html_to_plain(m2)
                if text and len(text) > 30:
                    paragraphs.append(text)
            if not paragraphs:
                # Plain text — split on double newline
                paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body)
                             if p.strip() and len(p.strip()) > 30]
            return {"lede": summary, "paragraphs": paragraphs}
    return None


def _try_article_paragraphs(html: str) -> dict:
    """Strategy 3: visible <article><p> paragraph scraping."""
    m = re.search(r'<article[^>]*>(.*?)</article>', html, re.S)
    article_html = m.group(1) if m else html
    # Strip script/style/aside/nav inside article
    article_html = re.sub(r'<script[^>]*>.*?</script>', '', article_html, flags=re.S)
    article_html = re.sub(r'<style[^>]*>.*?</style>', '', article_html, flags=re.S)
    article_html = re.sub(r'<aside[^>]*>.*?</aside>', '', article_html, flags=re.S)
    article_html = re.sub(r'<nav[^>]*>.*?</nav>', '', article_html, flags=re.S)
    paragraphs = []
    for m2 in re.findall(r'<p[^>]*>(.*?)</p>', article_html, re.S):
        text = _html_to_plain(m2)
        if text and len(text) > 50:
            # Skip ad/promo signatures
            if not re.match(r'^(subscribe|sign up|read more|follow us|share this)',
                            text, re.I):
                paragraphs.append(text)
    og_desc_match = re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I)
    lede = og_desc_match.group(1) if og_desc_match else ""
    return {"lede": lede, "paragraphs": paragraphs}


def _try_og_description(html: str) -> dict:
    """Strategy 4: only og:description. Last resort."""
    desc = None
    for prop in ("og:description", "description"):
        m = re.search(
            f'<meta[^>]+(?:property|name)=["\\\']({re.escape(prop)})["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
            html, re.I)
        if m:
            desc = m.group(2)
            break
    if not desc:
        return None
    return {"lede": desc, "paragraphs": []}


def fetch_article_body(url: str) -> dict:
    """Main entry. Returns {lede, paragraphs} or None."""
    if not url or not url.startswith(('http://', 'https://')):
        return None
    code, body = _fetch(url, timeout=15)
    if code != 200 or not isinstance(body, (bytes, bytearray)):
        return None
    html = body.decode('utf-8', errors='replace')
    if len(html) < 500:
        return None
    # Try each strategy in order
    for fn in (_try_next_data, _try_json_ld, _try_article_paragraphs, _try_og_description):
        try:
            result = fn(html)
        except Exception:
            continue
        if result and (result.get('paragraphs') or result.get('lede')):
            # Sanity: too few paragraphs + too short lede = not a real article body
            if not result['paragraphs'] and len(result.get('lede', '')) < 100:
                continue
            return result
    return None


# CLI test
if __name__ == '__main__':
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.topgear.com/car-news/gaming/take-cover-aston-martin-has-built-a-massive-military-grade-v12-supertruck"
    r = fetch_article_body(url)
    if not r:
        print("Nothing extracted")
        sys.exit(1)
    print(f"Lede ({len(r['lede'])} chars):\n  {r['lede']}\n")
    print(f"{len(r['paragraphs'])} paragraphs:\n")
    for i, p in enumerate(r['paragraphs'], 1):
        print(f"[{i}] {p[:250]}{'...' if len(p)>250 else ''}\n")
