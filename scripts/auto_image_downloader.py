#!/usr/bin/env python3
# scripts/auto_image_downloader.py
# Auto-download car images for YouTube Shorts from verified sources
# Strategy: Wikipedia API → verify with curl → save locally
# Falls back to Google Image Search links (never fabricated URLs)
# Usage: python3 scripts/auto_image_downloader.py <brand> <model> [--save]
# Example: python3 scripts/auto_image_downloader.py Ferrari 458

import re, sys, json, time, os, urllib.request, urllib.parse, ssl
from pathlib import Path
from datetime import datetime

BASE       = Path(__file__).parent.parent
CACHE_DIR  = BASE / 'cache' / 'images'
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG        = BASE / 'wiki' / 'log.md'

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


# ─────────────────────────────────────────
# Wikipedia API — image search
# ─────────────────────────────────────────

def wikipedia_image_search(brand: str, model: str, limit: int = 8) -> list:
    """
    Use Wikipedia API (pageimages + search) to find image URLs for a car model.
    Returns list of dicts: {url, filename, credit, verified}
    """
    images = []
    seen_urls = set()

    # Strategy 1: Direct pageimages API for the exact model
    page_titles = [
        f"{brand} {model}".strip(),
        f"{brand} {model} (Wikipedia)".strip(),
    ]

    for title in page_titles[:2]:
        safe_title = title.replace(' ', '_').encode('ascii', 'replace').decode()
        api_url = (
            f"https://en.wikipedia.org/w/api.php"
            f"?action=query&titles={urllib.request.quote(safe_title)}"
            f"&prop=pageimages&format=json&pithumbsize=800"
        )
        try:
            req = urllib.request.Request(api_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                data = json.loads(r.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                thumb = page_data.get('thumbnail')
                if thumb:
                    url = thumb['source']
                    if url not in seen_urls:
                        seen_urls.add(url)
                        filename = url.split('/')[-1].split('?')[0]
                        verified = _verify_url(url)
                        images.append({
                            'url': url,
                            'filename': filename,
                            'page': page_data.get('title', title),
                            'verified': verified,
                            'size': f"{thumb.get('width','?')}px",
                        })
            time.sleep(0.3)
        except Exception:
            pass

    # Strategy 2: Search API then get pageimages for top result
    search_url = (
        f"https://en.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.request.quote(brand)} {urllib.request.quote(model)} car"
        f"&format=json&srlimit=3"
    )
    try:
        req = urllib.request.Request(search_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            search_data = json.loads(r.read().decode('utf-8'))
        time.sleep(0.3)
        results = search_data.get('query', {}).get('search', [])
        for result in results[:2]:
            page_title = result['title']
            # Get full image for this page
            page_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&titles="
                f"{urllib.request.quote(page_title.replace(' ','_').encode('ascii','replace').decode())}"
                f"&prop=pageimages&format=json&pithumbsize=800"
            )
            try:
                req2 = urllib.request.Request(page_url, headers=HEADERS)
                with urllib.request.urlopen(req2, timeout=10, context=CTX) as r2:
                    page_data = json.loads(r2.read().decode('utf-8'))
                pages = page_data.get('query', {}).get('pages', {})
                for pid, pdat in pages.items():
                    thumb = pdat.get('thumbnail')
                    if thumb:
                        url = thumb['source']
                        if url not in seen_urls:
                            seen_urls.add(url)
                            filename = url.split('/')[-1].split('?')[0]
                            verified = _verify_url(url)
                            images.append({
                                'url': url,
                                'filename': filename,
                                'page': pdat.get('title', page_title),
                                'verified': verified,
                                'size': f"{thumb.get('width','?')}px",
                            })
                time.sleep(0.3)
            except Exception:
                pass
    except Exception:
        pass

    return images[:limit]


def wikipedia_generator_search(query: str, limit: int = 6) -> list:
    """
    Use Wikipedia's generator=search + prop=pageimages to find pages that
    DO have thumbnails (the plain pageimages API returns nothing for well-known
    brand articles because they use {{PAGEIMAGE}} logic that skips logos).
    This calls the search+harness combo in one request, which gives us pages
    like 'Aston Martin Vanquish' that actually have a thumbnail.
    """
    images = []
    seen_urls = set()

    params = (
        "https://en.wikipedia.org/w/api.php?"
        "action=query&format=json"
        "&generator=search&gsrsearch=" + urllib.parse.quote(query) +
        "&gsrlimit=" + str(limit * 2) +
        "&gsrnamespace=0"
        "&prop=pageimages&piprop=thumbnail&pithumbsize=800"
    )
    try:
        req = urllib.request.Request(params, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            data = json.loads(r.read().decode('utf-8'))
        pages = data.get('query', {}).get('pages', {})
        for pid, pdat in pages.items():
            thumb = pdat.get('thumbnail')
            if not thumb:
                continue
            url = thumb.get('source')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            verified = _verify_url(url)
            filename = url.split('/')[-1].split('?')[0]
            images.append({
                'url': url,
                'filename': filename,
                'page': pdat.get('title', query),
                'verified': verified,
                'size': f"{thumb.get('width', '?')}px",
            })
            if len(images) >= limit:
                break
            time.sleep(0.2)
    except Exception as e:
        print(f"  [wiki-gen] error: {e}")
    return images


def _verify_url(url: str, timeout: int = 5) -> bool:
    """Check if URL returns 200 OK via curl."""
    try:
        result = os.popen(f"curl -s -o /dev/null -w '%{{http_code}}' --max-time {timeout} -L '{url}'").read()
        return result.strip() == '200'
    except:
        return False


# ─────────────────────────────────────────
# Google Image Search Links (fallback, never 404s)
# ─────────────────────────────────────────

def google_image_search_link(brand: str, model: str, year: str = "") -> str:
    """Generate a Google Images search link (never 404s, always works)."""
    query = f"{brand}+{model}".replace(' ', '+')
    if year:
        query += f"+{year}"
    return f"https://www.google.com/search?tbm=isch&q={query}"


# ─────────────────────────────────────────
# Download + Save
# ─────────────────────────────────────────

def download_image(url: str, dest_path: Path, timeout: int = 15) -> bool:
    """Download an image to dest_path. Returns True if successful."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            data = r.read()
        dest_path.write_bytes(data)
        return True
    except Exception as e:
        return False


def generate_image_manifest(brand: str, model: str,
                            images: list,
                            wiki_url: str = "") -> dict:
    """Build image manifest for downstream use (script_generator, video editor)."""
    manifest = {
        'brand': brand,
        'model': model,
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'wikipedia_article': wiki_url,
        'google_image_search': google_image_search_link(brand, model),
        'images': [],
    }

    for img in images:
        manifest['images'].append({
            'url': img['url'],
            'filename': img['filename'],
            'page': img['page'],
            'verified': img['verified'],
            'local_path': None,  # filled if downloaded
        })

    return manifest


def save_manifest(manifest: dict, brand: str, model: str) -> Path:
    """Save manifest JSON to cache/images/."""
    slug = f"{brand.lower()}-{model.lower().replace(' ', '-')}"
    out = CACHE_DIR / f"{slug}-manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return out


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print('[ERR] Usage: python3 scripts/auto_image_downloader.py <brand> <model> [--save]')
        print('       python3 scripts/auto_image_downloader.py Ferrari 458 [--save]')
        sys.exit(1)

    brand = sys.argv[1]
    model = sys.argv[2]
    save  = '--save' in sys.argv

    print(f'🖼️  Searching images for: {brand} {model}')

    images = wikipedia_image_search(brand, model, limit=8)

    if not images:
        print('  ℹ No Wikipedia images found — using Google Image Search link')
        google_link = google_image_search_link(brand, model)
        manifest = {
            'brand': brand,
            'model': model,
            'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'wikipedia_article': '',
            'google_image_search': google_link,
            'images': [],
            'note': 'No Wikipedia images found — use Google Image Search link below',
        }
    else:
        verified_count = sum(1 for i in images if i['verified'])
        print(f'  ✓ Found {len(images)} images ({verified_count} verified live)')

        manifest = generate_image_manifest(brand, model, images)

        # Optionally download verified images
        if save:
            downloaded = 0
            for img in images:
                if not img['verified']:
                    continue
                filename = img['filename']
                slug = f"{brand.lower()}-{model.lower().replace(' ', '-')}"
                dest = CACHE_DIR / slug / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                if download_image(img['url'], dest):
                    img['local_path'] = str(dest)
                    downloaded += 1
            print(f'  ✓ Downloaded {downloaded} verified images')
            manifest['downloaded_count'] = downloaded

    print()
    print("=" * 60)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print("=" * 60)

    if save:
        path = save_manifest(manifest, brand, model)
        print(f"\n[OK] Manifest saved to: {path}")
        print(f"\n🌐 Google Image Search (always works):")
        print(f"    {manifest['google_image_search']}")
    else:
        print(f"\n[OK] Add --save to download verified images + save manifest")


if __name__ == '__main__':
    main()
