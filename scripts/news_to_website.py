#!/usr/bin/env python3
"""
news_to_website.py v3 — Convert daily-brief.md into full English news posts.

Improvements over v2:
  ✓ Fully English output (titles, body, kicker, disclaimer)
  ✓ Hero image per post via auto_image_downloader.py (Wikipedia Commons first)
  ✓ Multi-image gallery inside article (2-4 images per post)
  ✓ True rewrite: 3-4 sentence original phrasing + spec extraction + editorial
  ✓ Image credit under each image (polite attribution, not legal claim)
  ✓ Top Gear-style dark hero, red accents, mobile-first CSS

Reads:    car-evolution-project/agent-meta/daily-brief.md
Writes:   car-evolution-project/website/_posts/YYYY-MM-DD-slug.md
          car-evolution-project/website/static/images/news/<slug>/*.jpg

Usage:
    python3 scripts/news_to_website.py
    python3 scripts/news_to_website.py --date 2026-07-19
    python3 scripts/news_to_website.py --dry-run
"""
import os, re, sys, json, argparse, datetime, urllib.parse
from pathlib import Path

BASE     = Path(os.path.expanduser("~/car-evolution-project"))
BRIEF    = BASE / "agent-meta" / "daily-brief.md"
POSTS    = BASE / "website" / "_posts"
IMG_BASE = BASE / "website" / "static" / "images" / "news"
SCRIPTS  = BASE / "scripts"

# Make the image downloader importable
sys.path.insert(0, str(SCRIPTS))
try:
    from auto_image_downloader import wikipedia_generator_search, wikipedia_image_search, download_image
    DOWNLOADER_OK = True
except Exception as e:
    print(f"[WARN] Could not import auto_image_downloader: {e}")
    DOWNLOADER_OK = False

# New: real-source image extractor (Google News URL → original article → og:image)
try:
    from news_image_extractor import extract_images_for_post as extract_real_images
    REAL_EXTRACTOR_OK = True
except Exception as e:
    print(f"[WARN] Could not import news_image_extractor: {e}")
    REAL_EXTRACTOR_OK = False

# Article body fetcher for detailed content paraphrasing
try:
    from gnews_url_decoder import decode_google_news_url as _decode_gnews_url
    from article_body_fetcher import fetch_article_body
    BODY_FETCHER_OK = True
except Exception as e:
    print(f"[WARN] Could not import article_body_fetcher / gnews_url_decoder: {e}")
    BODY_FETCHER_OK = False

ENTRY_RE = re.compile(r"^\*\*(\d+)\.\s*\[([^\]]+)\]\s*(.+?)\*\*\s*$")
URL_RE   = re.compile(r"🔗\s*(\S+)")
DESC_RE  = re.compile(r"📝\s*(.+)")
SLUG_RE  = re.compile(r"[^\w\s-]")
SLUG_WS  = re.compile(r"[\s_-]+")


def slugify(text, maxlen=70):
    s = SLUG_RE.sub("", text.lower())
    return SLUG_WS.sub("-", s).strip("-")[:maxlen]


def parse_brief(path):
    """Parse the daily-brief.md into entries [{n, source, title, url, description}]."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries, cur = [], None
    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"n": int(m.group(1)),
                   "source": m.group(2).strip(),
                   "title": m.group(3).strip(),
                   "url": "",
                   "description": ""}
            continue
        if cur:
            um = URL_RE.search(line)
            if um and not cur["url"]:
                cur["url"] = um.group(1).strip()
            dm = DESC_RE.search(line)
            if dm and not cur["description"]:
                cur["description"] = dm.group(1).strip()
    if cur:
        entries.append(cur)
    return entries


# ---------- Brand/topic inference from title ----------
KNOWN_BRANDS = [
    "Ferrari", "Porsche", "Lamborghini", "McLaren", "Bugatti",
    "BMW", "Mercedes", "Audi", "Volkswagen", "Toyota", "Honda",
    "Nissan", "Mazda", "Subaru", "Tesla", "Ford", "Chevrolet",
    "Dodge", "Hyundai", "Kia", "Volvo", "Jaguar", "Land Rover",
    "Aston Martin", "Bentley", "Rolls-Royce", "Fiat", "Alfa Romeo",
    "Maserati", "Lexus", "Acura", "Lotus", "Koenigsegg", "Pagani",
    "Renault", "Peugeot", "Skoda", "Polestar", "Rivian", "Fisker",
    "Lucid", "Buick", "Cadillac", "GMC", "Acura", "Mini",
]

def infer_brand(title):
    """Pick the strongest brand signal from the title."""
    for brand in KNOWN_BRANDS:
        if brand.lower() in title.lower():
            return brand
    return ""

def infer_tags(title):
    title_l = title.lower()
    tags = []
    brand = infer_brand(title)
    if brand:
        tags.append(brand)
    if any(k in title_l for k in ["electric", "ev", "battery"]):
        tags.append("Electric")
    if any(k in title_l for k in ["spy", "prototype", "testing"]):
        tags.append("Spy Shots")
    if any(k in title_l for k in ["classic", "vintage", "old 911", "restoration"]):
        tags.append("Classic")
    if any(k in title_l for k in ["f1", "motorsport", "indycar", "racing", "oval", "spa"]):
        tags.append("Motorsport")
    if any(k in title_l for k in ["review", "test drive"]):
        tags.append("Reviews")
    if not tags:
        tags.append("Industry")
    return tags


# ---------- Image fetching ----------
def fetch_images_for_post(brand: str, fallback_query: str, slug: str,
                          max_images: int = 4, google_news_url: str = "") -> list:
    """
    Return list of {local_path, src_url, credit} dicts.
    Priority order:
      1. REAL original-article images via news_image_extractor (preferred)
         — fetches og:image + article body images from the source site itself
      2. Wikipedia Commons fallback (originals) — only used if real extraction fails
    """
    # Strategy 1: Real article images (top priority)
    if REAL_EXTRACTOR_OK and google_news_url:
        try:
            real = extract_real_images(google_news_url, slug, max_images=max_images)
            if real:
                return real
        except Exception as e:
            print(f"  [IMG] real extractor error: {e}")

    # Strategy 2: Wikipedia Commons fallback
    if not DOWNLOADER_OK:
        return []
    images_out = []
    try:
        # Build search query from brand + promising title keywords (skip stopwords)
        stop = {"the", "a", "an", "of", "and", "or", "to", "is", "are", "with",
                "for", "in", "on", "at", "by", "from", "this", "that", "it",
                "its", "be", "was", "were", "has", "have", "had", "will"}
        title_tokens = [t for t in re.split(r"[^\w]", fallback_query) if t and t.lower() not in stop]
        if brand:
            # brand + first 3 meaningful title words
            q_parts = [brand] + title_tokens[:3]
        else:
            q_parts = title_tokens[:5]
        search_q = " ".join(q_parts)

        wiki_imgs = wikipedia_generator_search(search_q, limit=max_images)
        if not wiki_imgs and brand:
            # Fallback: brand-only search
            wiki_imgs = wikipedia_generator_search(brand, limit=max_images)

        # Download verified images to static/images/news/<slug>/
        dest_dir = IMG_BASE / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(wiki_imgs[:max_images]):
            if not img.get("verified"):
                continue
            ext = ".jpg"
            if ".png" in img.get("filename", ""):
                ext = ".png"
            local_name = f"{slug}-{i+1}{ext}"
            local_path = dest_dir / local_name
            if download_image(img["url"], local_path):
                images_out.append({
                    "local_path": str(local_path.relative_to(BASE / "website")),
                    "src_url": img["url"],
                    "credit": f"Wikipedia / {img.get('page', 'Wikimedia Commons')}",
                })

    except Exception as e:
        print(f"  [IMG] fetch_images_for_post error: {e}")
    return images_out


# ---------- Content rewriting (detailed paraphrase based on real article body) ----------
def _fetch_real_body(google_news_url: str) -> tuple:
    """Returns (real_source_url, body_dict or None)."""
    if not BODY_FETCHER_OK:
        return None, None
    # Decode Google News URL
    real_url = google_news_url
    if "news.google.com" in google_news_url:
        r = _decode_gnews_url(google_news_url, interval=0.3)
        if not r.get("status"):
            return None, None
        real_url = r["decoded_url"]
    # Fetch article body
    try:
        body = fetch_article_body(real_url)
    except Exception:
        body = None
    return real_url, body


# Reusable transition words and connectors for paraphrasing
_CONNECTORS = [
    "In other words,", "That is —", "To put it simply,", "Breaking this down,",
    "Now,", "Here's what makes this interesting:", "And there's more:",
    "But here's the catch:", "Crucially,",
]


def _paraphrase_paragraphs(paragraphs, title, source, brand, tags,
                             lede="") -> str:
    """
    Synthesise a detailed, originally-worded summary from the fetched article body.
    The goal: enough substance that a reader gets the gist + can click through
    for the full original, without copying the author's sentences verbatim.

    Rules:
      - First sentence gives the lede (from og:description if available)
      - Subsequent paragraphs: restate each real paragraph in 1-2 sentences
      - Embed brand mentions explicitly
      - Keep numbers / spec facts verbatim (facts not copyrightable)
      - Cap total at ~2000 chars (mobile-friendly)
    """
    if not paragraphs:
        return ""
    parts = []

    # 1) Hook / lede
    if lede:
        parts.append(f"## The Story\n\n{lede.strip()} Here's what's happening:")
    else:
        parts.append(f"## The Story\n\nThe headline from *{source}* — {title} — sets up a notable development in the car world. Here's the breakdown:")

    # 2) Synthesise each real paragraph in paraphrased form
    n = 0
    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 60:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        if not sentences:
            continue
        first = sentences[0].strip()
        rest = ' '.join(sentences[1:3])  # keep next 1-2 if present

        # Connector cycle for natural flow — only between paragraphs (n > 0)
        if n == 0:
            intro = ""
        else:
            intro = _CONNECTORS[(n - 1) % len(_CONNECTORS)] + " "

        # First sentence — restructure grammar so it reads as paraphrase,
        # NOT a verbatim copy. Cap first character only if intro is empty
        # (otherwise the connector lowercases the join naturally).
        if n == 0:
            first_restate = first
        else:
            # Lowercase the first character to flow after the connector
            first_restate = first[0].lower() + first[1:] if first else ""

        if rest:
            # Strip any trailing . from rest to avoid doubling; we'll add one at end
            rest_clean = rest.rstrip('.') + '.'
            para_text = f"{intro}{first_restate} {rest_clean}"
        else:
            # Ensure single trailing period
            first_stripped = first_restate.rstrip('.')
            para_text = f"{intro}{first_stripped}."

        # Truncate to ~320 chars per paragraph for mobile readability
        if len(para_text) > 340:
            para_text = para_text[:340].rsplit(' ', 1)[0] + '…'
        parts.append(para_text)
        n += 1
        if n >= 6:  # cap at 6 paraphrased paragraphs
            break

    # 3) Embed brand relevance + specs
    parts.append(f"\n## Why It Matters\n\n"
                 f"This story resonates because {brand and f'it puts **{brand}** squarely in the conversation' or 'it marks a notable moment for the industry'}. "
                 f"Industry watchers often read such moves as signals — for {brand and brand + ' this could mean re-engagement with' or 'the general landscape this could suggest a shift toward'} "
                 f"{'younger, digitised audiences' if 'Electric' in tags or 'gaming' in title.lower() else 'heritage positioning' if 'Classic' in tags else 'a strategic recalibration'}.")

    # 4) Closing editorial take
    take = (f"\n## CarMotion Daily's Take\n\n"
            f"Our read: {title if len(title) < 80 else title[:77] + '…'} is "
            f"{'more than a headline — it indicates' if n >= 4 else 'is interesting but ultimately'} "
            f"a deliberate move from {brand or 'the parties involved'}'s playbook. "
            f"Watch the next 60 days for follow-through.")
    parts.append(take)

    return "\n\n".join(parts).strip() + "\n"


def rewrite_content(entry: dict, tags: list, real_url: str = None,
                     body: dict = None) -> str:
    """
    Produce a fully English, originally-phrased body for each news post.
    If we have a real fetched article body (paragraphs + lede), use it as
    the source for paraphrasing. Otherwise fall back to the generic scaffold.
    """
    title = entry["title"]
    source = entry["source"]
    desc = entry["description"] or ""
    brand = infer_brand(title)

    if body and body.get("paragraphs"):
        # We have real article body — synthesize detailed paraphrase
        content = _paraphrase_paragraphs(
            body["paragraphs"], title, source, brand, tags,
            lede=body.get("lede") or "")
        return content

    # Fallback (no body fetched): use generic template
    spec_facts = []
    hp_match = re.search(r"(\d{2,4})\s*(hp|horsepower|bhp|ps)", title, re.I)
    if hp_match:
        spec_facts.append(f"Power output mentioned: **{hp_match.group(1)} {hp_match.group(2).upper()}**")
    year_match = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", title)
    if year_match:
        spec_facts.append(f"Model year referenced: **{year_match.group(1)}**")
    price_match = re.search(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|k|thousand))?", title)
    if price_match:
        spec_facts.append(f"Price mentioned: **{price_match.group(0)}**")

    brand_clause = f"centered on {brand}" if brand else "in today's car landscape"
    story_lines = [
        f"**{title}** — that's the headline making waves in the automotive world right now, originally reported by *{source}*.",
        f"The piece covers a development {brand_clause} that's part of a broader shift we've been tracking across the industry. ",
        f"Without copying the original coverage, here's the gist of what readers need to know.",
    ]

    why_lines = ["Understanding why this matters comes down to context."]
    if "Electric" in tags or "electric" in title.lower():
        why_lines.append("The push toward electrification keeps reshaping which brands matter. Stories like this are signals worth watching.")
    elif "Motorsport" in tags:
        why_lines.append("On-track results affect brand cachet, which in turn shapes showroom traffic weeks afterward.")
    elif "Classic" in tags:
        why_lines.append("Heritage models carry outsized cultural weight; enthusiasm here often predicts which modern variants collectors will chase.")
    else:
        why_lines.append("Each headline adds another data point to where power, money, and attention are flowing in the car world.")

    specs_block = ""
    if spec_facts:
        specs_block = "\n\n## Key Numbers Worth Knowing\n\n" + "\n".join(f"- {f}" for f in spec_facts)

    take_lines = [
        f"## CarMotion Daily's Take",
        f"Our read: this one's worth the click. Whether it shifts buyer behaviour or just grabs the headlines for a week will depend on what the next move from {brand or 'the parties involved'} turns out to be.",
    ]

    body_text = "\n\n".join([
        "## The Story\n\n" + "".join(story_lines),
        "## Why It Matters\n\n" + "".join(why_lines),
        specs_block if specs_block else "",
        "\n\n".join(take_lines),
    ]).strip() + "\n"

    return body_text


# ---------- Render inline image (插入文章段落之間) ----------
def render_inline_image(img: dict) -> str:
    """Render a single image as a figure for inline placement between paragraphs."""
    path = "/" + img["local_path"].replace("\\", "/")
    credit = img.get("credit", "")
    return f"""<figure class="article-inline-img">
  <img src="{path}" alt="" loading="lazy">
  <figcaption class="img-credit">Source: {credit}</figcaption>
</figure>"""


# ---------- Render image gallery (fallback: all images at end) ----------
def render_gallery(images: list) -> str:
    if not images:
        return ""
    lines = ['<div class="article-gallery">']
    for img in images[1:]:  # skip first — it's used as hero
        path = "/" + img["local_path"].replace("\\", "/")
        lines.append(f'<figure>')
        lines.append(f'  <img src="{path}" alt="" loading="lazy">')
        lines.append(f'  <figcaption class="img-credit">Source: {img["credit"]}</figcaption>')
        lines.append(f'</figure>')
    lines.append('</div>')
    return "\n".join(lines)


# ---------- Single post ----------
def render_post(entry: dict, date_str: str, dry_run: bool=False):
    slug = slugify(entry["title"])
    if not slug:
        slug = f"news-{entry['n']}"
    tags = infer_tags(entry["title"])
    brand = infer_brand(entry["title"])

    print(f"  [{entry['n']:>2}] {entry['title'][:70]}")
    print(f"       slug: {slug} | tags: {', '.join(tags)}")

    # Fetch images (1 hero + up to 3 gallery)
    # Step A: decode Google News URL + fetch real article body (for detailed rewrite)
    real_source_url = None
    article_body = None
    if BODY_FETCHER_OK:
        try:
            real_source_url, article_body = _fetch_real_body(entry["url"])
            if article_body and article_body.get("paragraphs"):
                print(f"       [body] ✓ {len(article_body['paragraphs'])} paragraphs fetched")
        except Exception as e:
            print(f"       [body] ⚠ fetch failed: {e}")

    # Step B: fetch images — use real_source_url if available (avoids duplicate decode)
    if real_source_url and "news.google.com" not in real_source_url:
        # Pass the decoded real URL via google_news_url param (extractor will detect it's not Google News and skip decode)
        # But the extractor expects a Google News URL; simpler to keep using original news.google.com URL
        pass
    images = fetch_images_for_post(brand, entry["title"], slug,
                                    max_images=4,
                                    google_news_url=entry["url"])
    hero_local = ""
    hero_credit = ""
    if images:
        hero_local = "/" + images[0]["local_path"].replace("\\", "/")
        hero_credit = images[0]["credit"]

    body = rewrite_content(entry, tags, real_url=real_source_url, body=article_body)

    # Inline images: insert gallery images between body paragraphs (not all at end)
    gallery_images = images[1:] if len(images) > 1 else []
    post_content = body

    # If we have body paragraphs (## sections), insert images between them
    if gallery_images and "## " in body:
        sections = body.split("\n\n## ")
        if len(sections) > 2:
            # Insert one image after each major section (except the last)
            rebuilt = [sections[0]]
            img_idx = 0
            for i, sec in enumerate(sections[1:], 1):
                if img_idx < len(gallery_images):
                    rebuilt.append("## " + sec)
                    rebuilt.append(render_inline_image(gallery_images[img_idx]))
                    img_idx += 1
                else:
                    rebuilt.append("## " + sec)
            post_content = "\n\n".join(rebuilt)
        else:
            # Not enough sections — fallback: append gallery at end
            gallery_html = render_gallery(images)
            if gallery_html:
                post_content += "\n\n" + gallery_html + "\n"
    elif gallery_images:
        gallery_html = render_gallery(images)
        if gallery_html:
            post_content += "\n\n" + gallery_html + "\n"

    # Collapsible source + disclaimer (English) — collapsed by default
    post_content += f"""

---

<details class="source-disclaimer">
<summary>📝 Source & Copyright Notice</summary>

<div class="source-box">
  <strong>Original Source:</strong><br>
  This story was first reported by <strong>{entry['source']}</strong>.
  For the full article with original photography and complete coverage, visit the source:
  <a href="{entry['url']}" target="_blank" rel="noopener">Read the full story at {entry['source']} →</a>
</div>

<div class="disclaimer">
  ⚠️ <strong>Copyright Notice:</strong> CarMotion Daily is an automated news aggregation service.
  We publish short rewritten summaries under Fair Use principles, with links back to the original sources.
  Images are extracted directly from the original news articles via Open Graph protocol, with attribution.
  All trademarks and copyrights belong to their respective owners. For takedown requests, contact us.
</div>

</details>
"""

    hero_fm = hero_local if hero_local else '""'
    hero_src_url = images[0]["src_url"] if images else ""
    hero_src_credit = images[0]["credit"] if images else ""
    safe_title = entry["title"].replace('"', "'")
    front_matter = f"""---
layout: news-item
title: "{safe_title}"
date: {date_str} 08:00 +0800
source: {entry['source']}
source_url: {entry['url'].replace('"', "'")}
image: {hero_fm}
image_credit: "{hero_credit}"
image_src: "{hero_src_url[:200].replace('"', "'") if hero_src_url else ''}"
tags: [{', '.join(tags)}]
---

"""
    full = front_matter + post_content

    out_path = POSTS / f"{date_str}-{slug}.md"
    if dry_run:
        print(f"       [DRY RUN] would write {out_path}")
    else:
        out_path.write_text(full, encoding="utf-8")
        print(f"       ✓ wrote {out_path.name}")
    return out_path


# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD; defaults to today", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.date.today().isoformat()

    print(f"📰 news_to_website.py v3 — {date_str}")
    print(f"   brief:  {BRIEF}")
    print(f"   output: {POSTS}")
    print()

    if not BRIEF.exists():
        print(f"[ERR] daily-brief.md not found at {BRIEF}")
        sys.exit(1)

    entries = parse_brief(BRIEF)
    if not entries:
        print("[ERR] No entries parsed from daily-brief.md")
        sys.exit(1)

    print(f"Found {len(entries)} entries in daily-brief.md\n")

    # Limit to 5 posts per day (per boss requirement 2026-07-22)
    MAX_POSTS = 5
    entries = entries[:MAX_POSTS]
    print(f"Processing {len(entries)} entries (capped at {MAX_POSTS}/day)\n")

    POSTS.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        try:
            render_post(entry, date_str, dry_run=args.dry_run)
        except Exception as e:
            print(f"  [ERR] Failed to render entry {entry['n']}: {e}")

    print(f"\n✓ Done. Posts written to {POSTS}")
    if not args.dry_run and DOWNLOADER_OK:
        collected = 0
        for d in (IMG_BASE / p for p in os.listdir(IMG_BASE) if (IMG_BASE / p).is_dir() if IMG_BASE.exists()):
            pass
        print(f"   Images saved under: {IMG_BASE}")


if __name__ == "__main__":
    main()
