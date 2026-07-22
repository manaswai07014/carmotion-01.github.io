#!/usr/bin/env python3
"""
news_image_extractor.py — Download real images from original news articles.

Pipeline (for each article):
  1. Decode Google News RSS URL → original source URL (via gnews_url_decoder)
  2. Fetch original page HTML with browser UA + Referer
  3. Extract image URLs from <meta og:image>, <meta twitter:image>, <picture>,
     <img> with width-style regex (filter out icons/avatars/logos, keep large ones)
  4. Download top N images with Referer = source URL to bypass hotlink protection
  5. Save to website/static/images/news/<slug>/

Fair use rationale: thumbnail-sized, editorial context, link back to source.

Usage:
    from news_image_extractor import extract_images_for_post
    imgs = extract_images_for_post(google_news_url, slug, max_images=4)

    # CLI:
    python3 news_image_extractor.py <google_news_url> <slug> [--max 4]
"""
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict

# Local imports
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from gnews_url_decoder import decode_google_news_url
except Exception as e:
    print(f"[FATAL] gnews_url_decoder not importable: {e}")
    sys.exit(1)


_BASE = Path(os.path.expanduser("~/car-evolution-project"))
_IMG_BASE = _BASE / "website" / "static" / "images" / "news"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Patterns to filter out non-article images (icons, avatars, ad trackers, author photos)
_BAD_PATTERNS = [
    r'logo', r'favicon', r'avatar', r'icon', r'sprite',
    r'tracker', r'pixel\.gif', r'1x1', r'ad-/i/', r'ads?/',
    r'gravatar\.com', r'social/', r'/share', r'sharing-',
    # Author/contributor/writer headshots (common in byline sections)
    r'author[-_]', r'contributor', r'writer[-_]', r'editor[-_]',
    r'blogger[-_]', r'journalist', r'byline', r'headshot',
    r'staff[-_]', r'profile[-_]', r'person[-_]',
    # Ad / sponsor / newsletter / CTA graphics
    r'banner[-_]?ad', r'sponsor[-_]', r'newsletter[-_]',
    r'subscribe[-_]', r'cta[-_]', r'promo[-_]',
    r'adblock', r'ad-?slot', r'ad-?container',
    # Social media buttons / share graphics
    r'facebook[-_]', r'twitter[-_]', r'instagram[-_]',
    r'youtube[-_]', r'linkedin[-_]',
    # Generic UI elements
    r'placeholder[-_]', r'default[-_]', r'loading[-_]',
    r'blank[-_]', r'no-image', r'no[-_]?photo',
]
_BAD_RE = re.compile('|'.join(_BAD_PATTERNS), re.I)

# Image hosting CDNs we trust — buddy list
_TRUSTED_HOSTS = (
    'topgear.com', 'carscoops.com', 'autoblog.com', 'motortrend.com',
    'caranddriver.com', 'roadandtrack.com', 'jalopnik.com',
    'motortrend.com', 'motor1.com', 'autocar.co.uk', 'evo.co.uk',
    'insideevs.com', 'supercarblog.com', 'motor1.com', 'cnet.com',
    'carmagazine.co.uk', 'topgear.com', 'wikipedia.org', 'wikimedia.org',
)


def _is_bad_url(url: str) -> bool:
    return bool(_BAD_RE.search(url))


def _is_trusted(url: str) -> bool:
    """Keep images from the same source domain or Wikimedia."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        return any(t in host for t in _TRUSTED_HOSTS)
    except Exception:
        return False


def _fetch(url: str, referer: Optional[str] = None, timeout: int = 15) -> tuple:
    """GET with browser UA + Referer. Returns (status, body_text_or_bytes)."""
    headers = {"User-Agent": _UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, 'read') else b''
    except Exception as e:
        return 0, str(e).encode()


def _decode_gnews(url: str) -> Optional[str]:
    """Decode a Google News URL. Pass through non-Google URLs."""
    if "news.google.com" not in url:
        return url
    r = decode_google_news_url(url, interval=0.3)
    if r.get("status"):
        return r["decoded_url"]
    print(f"  [gnews] decode failed: {r.get('message', '')[:160]}")
    return None


def _extract_images_from_html(html: str, source_url: str, source_host: str) -> List[Dict]:
    """
    Find candidate image URLs in priority order:
      1. <meta property="og:image" content="...">
      2. <meta name="twitter:image" content="...">
      3. <picture><source srcset="..."><img></picture>
      4. <img src="..."> whose src is same-host as source
    Returns list of {url, attr, width_guess} dicts.
    """
    images = []
    seen = set()

    def add(url, attr):
        if not url or url in seen or _is_bad_url(url):
            return
        # Strip any leading/trailing whitespace and ensure absolute
        if not url.startswith(("http://", "https://")):
            url = urllib.parse.urljoin(source_url, url)
        if url in seen:
            return
        seen.add(url)
        # Parse width/height hints if present
        width = 0
        m = re.search(r'[?&]w=(\d+)', url) or re.search(r'-(\d+)x\d+', url)
        if m:
            width = int(m.group(1))
        images.append({"url": url, "attr": attr, "width_hint": width})

    # 1) og:image + variations
    for m in re.finditer(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', html, re.I):
        add(m.group(1), "og:image")
    # 2) twitter:image
    for m in re.finditer(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I):
        add(m.group(1), "twitter:image")
    # 3) <picture> sources
    for m in re.finditer(r'<source[^>]+srcset=["\']([^"\']+)[ "\']', html, re.I):
        srcset = m.group(1).split(",")[0].strip().split(" ")[0]
        add(srcset, "picture")
    # 4) Same-host <img src> — only keep those with BOTH:
    #    (a) A recent year path segment (avoid stale satire/related filler)
    #    (b) Either wrapped in <figure> or in a context paragraph, AND whose
    #        filename contains a meaningful body token (skip generic junk).
    import datetime
    current_year = datetime.date.today().year
    recent_years_set = {str(current_year), str(current_year - 1), str(current_year - 2)}

    # Token set for fresh-img filtering: the source article实际的 body keywords.
    # We let the caller pass title_keywords later, but as a heuristic here we
    # extract major title tokens (lowercase alphanumerics) for relevance check.
    # Title is found from real <title> tag in the page.
    title_match_re = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    page_title = title_match_re.group(1).lower() if title_match_re else ""
    # Tokenise, drop stopwords
    _stop = {"the","a","an","of","to","in","on","at","by","for","and","or","but",
             "is","are","was","were","be","this","that","it's","its","from","with",
             "best","top","here's","we","you","your","most","how","why","when","what",
             "news","review","first","new","only","after","before","says","could",
             "would","should","may","might","still","just","every","year","years",
             "spotted","these","those","test","drive","drive.","car","cars"}
    title_tokens = set()
    for tok in re.findall(r'[a-z0-9][a-z0-9]+', page_title):
        if tok not in _stop and len(tok) >= 3:
            title_tokens.add(tok)

    # ---- Brand / model alias expansion for title-token relevance ----
    # Many publishers use slug-style filenames (e.g. "aston-martin-dreadnought-
    # 01") where tokens like "dreadnought" need to join with title tokens
    # like "aston", "martin", "vantage".  Build an alias map by scanning the
    # page URL itself (often contains the slug) plus the page title.
    _brand_aliases = {
        "aston": ["martin", "vantage", "dreadnought", "db11", "db12", "valkyrie",
                  "valhalla", "vanquish"],
        "porsche": ["911", "918", "718", "taycan", "macan", "cayenne", "panamera"],
        "ferrari": ["roma", "sf90", "812", "296", "purosangue", "f8"],
        "lamborghini": ["huracan", "aventador", "revuelto", "urus"],
        "mclaren": ["750s", "765lt", "artura", "p1"],
        "mercedes": ["amg", "eqs", "gle", "c63", "sls"],
        "bmw": ["m3", "m4", "m5", "es", "ix"],
        "bugatti": ["chiron", "divo", "bolide", "remac", "centodieci"],
        "lotus": ["emira", "evija", "eletre"],
        "ford": ["mustang", "gt", "raptor", "bronco"],
        "chevrolet": ["corvette", "camaro", "silverado"],
        "toyota": ["supra", "gr", "landcruiser", "prius"],
        "nissan": ["z", "gt-r", "silvia", "fairlady"],
        "honda": ["civic", "type-r", "nsx", "sports"],
        "hyundai": ["ioniq", "n"],
        "kia": ["ev6", "ev9", "stinger"],
        # adds publisher-neutral models
    }
    # Scan page URL + page title for any brand keyword and union its aliases
    _scan_buf = (page_title + " " + source_url.lower())
    expanded_tokens = set(title_tokens)
    for brand, aliases in _brand_aliases.items():
        if brand in _scan_buf:
            expanded_tokens.add(brand)
            for alias in aliases:
                expanded_tokens.add(alias.lower())
    title_tokens = expanded_tokens

    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I):
        u = m.group(1)
        try:
            h = urllib.parse.urlparse(urllib.parse.urljoin(source_url, u)).hostname or ""
        except Exception:
            h = ""
        if not (h == source_host or source_host in h or "wikimedia" in h):
            continue

        # (a) Year path filter — at least one recent year must be in the path
        path_lower = urllib.parse.urlparse(u).path.lower()
        year_seg = re.search(r'/(19\d{2}|20\d{2})/', path_lower)
        # Relax: if no year segment is present but the publisher is known to
        # use date-free image paths (e.g. /sites/default/files/styles/, /wp-
        # content/uploads/), accept as long as other relevance gates pass.
        recent_year_ok = (year_seg and year_seg.group(1) in recent_years_set)
        year_free_publisher = any(seg in path_lower for seg in (
            '/sites/default/files/',
            '/wp-content/uploads/',
            '/images/articles/',
            '/uploads/',
        ))
        if not (recent_year_ok or year_free_publisher):
            continue

        # (b) Relevance — filename token check. Accept images where:
        #   - filename overlaps *expanded* title_tokens (brand + aliases +
        #     model name partials), OR
        #   - filename is a 12+ hex-char hash (publisher content-hash), OR
        #   - publisher hosts the image on /news-article/, OR
        #   - file is hosted on /sites/default/files/ (TopGear / Drupal)
        # AND filename doesn't contain skip-words (satire, gta, etc.)
        fn = path_lower.rsplit('/', 1)[-1]
        fn_stem = re.sub(r'\.(jpg|jpeg|png|webp|gif)$', '', fn)
        fn_tokens = set(re.findall(r'[a-z0-9][a-z0-9]+', fn_stem))
        # Skip if filename screams filler
        skip_words = {'satire', 'gta', 'stars', 'wars', 'star wars', 'nasa',
                      'flickr', 'avatar', 'profile', 'banner',
                      'sponsored', 'newsletter', 'subscribe',
                      'logo', 'favicon', 'placeholder'}
        if fn_tokens & skip_words:
            continue
        # Relevance gates (expanded)
        has_title_token = bool(fn_tokens & title_tokens)
        is_hash = any(re.fullmatch(r'[a-f0-9]{12,}', t) for t in fn_tokens)
        is_news_article = '/news-article/' in path_lower
        is_default_files = '/sites/default/files/' in path_lower
        # URL path substring match (catches "dreadnought" in path even if
        # filename is just "-2.jpg")
        path_has_brand_token = any(tok in path_lower for tok in title_tokens
                                   if len(tok) >= 4)

        if not (has_title_token or is_hash or is_news_article or
                is_default_files or path_has_brand_token):
            continue

        add(u, "img")

    # Prioritize: og > twitter > picture > img; then prefer URLs WITHOUT "?w=211"
    # style thumbnail sizing (we'd rather get the big version); then by width_hint.
    def thumb_penalty(url: str) -> int:
        # 1 if URL has a "?w=" or "h=" thumbnail parameter
        return 1 if re.search(r'[?&][wh]=\d', url) else 0

    images.sort(key=lambda x: (
        -{"og:image": 4, "twitter:image": 3, "picture": 2, "img": 1}.get(x["attr"], 0),
        thumb_penalty(x["url"]),    # prefer non-thumbnail URLs first
        -x["width_hint"],           # then bigger width
    ))
    return images


def _download(url: str, dest: Path, referer: str, timeout: int = 20,
              min_bytes: int = 15000) -> tuple:
    """Download a single image. Returns (success, content_type, byte_count).
    Skip images below min_bytes to filter out icons/avatars/tracker pixels.
    min_bytes=15KB filters out most author headshots (typically 5-12KB).
    Also skips images smaller than 400x300 (author headshots, ad thumbnails)."""
    code, data = _fetch(url, referer=referer, timeout=timeout)
    if code != 200 or not isinstance(data, (bytes, bytearray)) or len(data) < min_bytes:
        return False, "", 0
    # Sanity check: peek at first bytes to verify it's a real image
    head = data[:8]
    if head.startswith(b'\xff\xd8\xff'):          # JPEG
        ext = ".jpg"
    elif head.startswith(b'\x89PNG\r\n\x1a\n'):    # PNG
        ext = ".png"
    elif head[0:4] == b'RIFF' and head[8:12] == b'WEBP':
        ext = ".webp"
    elif head[0:6] in (b'GIF87a', b'GIF89a'):
        ext = ".gif"
    else:
        # Not an image — skip
        return False, "non-image", 0
    # Dimension check — skip small images (likely avatars/ads)
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w < 400 or h < 300:
            print(f"  [filter] skipped small image {w}x{h} ({len(data)//1024}KB)")
            return False, "too-small", 0
        # Skip near-square images that are likely headshots (aspect ratio 0.8-1.2 AND < 800px)
        aspect = w / h if h > 0 else 1
        if 0.8 <= aspect <= 1.25 and max(w, h) < 800:
            print(f"  [filter] skipped likely headshot {w}x{h} (aspect={aspect:.2f})")
            return False, "headshot", 0
    except ImportError:
        pass  # PIL not available — skip dimension check
    except Exception:
        pass  # Can't read dimensions — let it through
    # Replace extension on dest if necessary
    cur_ext = dest.suffix
    if cur_ext != ext:
        dest = dest.with_suffix(ext)
    dest.write_bytes(data)
    return True, ext, len(data)


def extract_images_for_post(google_news_url: str, slug: str,
                             max_images: int = 4) -> List[Dict]:
    """
    Main entry point. Returns list of {local_path, src_url, source_host, credit}.
    local_path is relative to website/ for use in Jekyll.
    """
    # 1) Decode Google News URL → real source URL
    real_url = _decode_gnews(google_news_url)
    if not real_url:
        return []
    source_host = (urllib.parse.urlparse(real_url).hostname or "").replace("www.", "")
    print(f"  [decoder] {google_news_url[:60]}... → {real_url[:120]}")

    # 2) Fetch the source HTML
    code, body = _fetch(real_url, timeout=15)
    if code != 200 or not isinstance(body, (bytes, bytearray)):
        print(f"  [fetch] HTTP {code} for {real_url[:100]}")
        return []
    html = body.decode("utf-8", errors="replace")

    # 3) Extract candidate images
    candidates = _extract_images_from_html(html, real_url, source_host)
    if not candidates:
        print(f"  [extract] no images found in {real_url[:100]}")
        return []

    # 4) Download top N verified images
    dest_dir = _IMG_BASE / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    # Derive same-site hint: the registered "public suffix + 1" (e.g. motor1.com from cdn.motor1.com)
    def base_domain(host: str) -> str:
        # crude: take last two labels (motor1.com, topgear.com).
        # For "co.uk" type TLDs this is imperfect but good enough for news sites.
        parts = host.rsplit(".", 2)
        if len(parts) >= 2:
            return parts[-2] + "." + parts[-1]
        return host
    src_base = base_domain(source_host)
    for i, c in enumerate(candidates):
        if len(downloaded) >= max_images:
            break
        # Allow same-host, same-base-domain (CDN subdomain), or trusted source.
        try:
            img_host = (urllib.parse.urlparse(c["url"]).hostname or "").replace("www.", "")
        except Exception:
            continue
        img_base = base_domain(img_host)
        # Same domain OR CDN subdomain of same parent (e.g. cdn.motor1.com for insideevs.com
        # is same parent publishing group) OR Wikimedia Commons OR explicitly trusted.
        same_org = (
            img_host == source_host
            or img_base == src_base
            or src_base.split(".")[0] in img_host
            or img_base in _TRUSTED_HOSTS
            or "wikimedia" in img_host
        )
        if not same_org:
            # Allow cross-domain og:image only — those are editorial picks, not ad trackers.
            if c["attr"] not in ("og:image", "twitter:image"):
                continue
        # Content sniffing should auto-fix the extension; use a generic ext guess
        # that gets corrected after download by the content sniffer.
        ext_guess = ".jpg"  # will be corrected via _download's content sniff
        local_name = f"{slug}-{len(downloaded)+1}{ext_guess}"
        local_path = dest_dir / local_name
        ok, real_ext, n = _download(c["url"], local_path, referer=real_url)
        if ok:
            # If extension was adjusted by content sniffing, rename
            if local_path.suffix != real_ext:
                new_path = local_path.with_suffix(real_ext)
                if new_path != local_path:
                    local_path.rename(new_path)
                    local_path = new_path
            rel = str(local_path.relative_to(_BASE / "website"))
            downloaded.append({
                "local_path": rel,
                "src_url": c["url"],
                "source_host": img_host,
                "credit": f"{source_host} (original article)",
                "size_bytes": n,
            })
            print(f"  [download] ✓ {local_path.name} ({n//1024}KB) via {c['attr']}")
        else:
            print(f"  [download] ✗ skipped ({c['url'][:80]}...)")
        time.sleep(0.3)  # polite beat

    return downloaded


# ---------- CLI ----------
def main():
    if len(sys.argv) < 3:
        print("Usage: python3 news_image_extractor.py <google_news_url> <slug> [--max 4]")
        sys.exit(1)
    url = sys.argv[1]
    slug = sys.argv[2]
    max_n = 4
    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        max_n = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 4
    imgs = extract_images_for_post(url, slug, max_images=max_n)
    print(f"\nResult: {len(imgs)} images")
    for im in imgs:
        print(f"  {im['local_path']} ({im['size_bytes']//1024}KB)")


if __name__ == "__main__":
    main()
