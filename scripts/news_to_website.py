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

# ---- 1000-word minimum body filter (2026-08-09 boss directive) ----
# Articles whose fetched body has fewer than this many words (combined
# across all paragraphs) are skipped. This drops short/brief news items
# and ensures every published post has substantial source content.
MIN_BODY_WORDS = 800


def slugify(text, maxlen=70):
    s = SLUG_RE.sub("", text.lower())
    return SLUG_WS.sub("-", s).strip("-")[:maxlen]


# ---------- Deduplication (防止日日發同一篇) ----------
# 7 天 rolling window: 用 slug (date 之外的檔名部分) 做 unique key
DEDUP_WINDOW_DAYS = 7
_post_slug_re = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$")


def load_recent_slugs(posts_dir: Path = POSTS, days: int = DEDUP_WINDOW_DAYS) -> set:
    """
    Scan the _posts/ directory for existing files within `days` window (by date
    in filename). Return the set of title slugs already published so we can
    skip duplicates in this run.

    Returns a set of slug strings (the title portion, without date prefix or .md).
    """
    seen = set()
    today = datetime.date.today()
    if not posts_dir.exists():
        return seen
    for f in posts_dir.iterdir():
        m = _post_slug_re.match(f.name)
        if not m:
            continue
        slug = m.group(1)
        # Try to extract date from the filename prefix
        date_part = f.name[:10]  # YYYY-MM-DD
        try:
            file_date = datetime.date.fromisoformat(date_part)
        except ValueError:
            # Can't parse date — be safe and include it (old post, won't match)
            seen.add(slug)
            continue
        # Skip files older than `days` — they won't collide with fresh entries
        if (today - file_date).days > days:
            continue
        seen.add(slug)
    return seen


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


# ---------- Q3: Strip source brand from title ----------
# Common source suffixes/prefixes that appear in RSS titles:
#   "... - topgear.com" | "... - evo.co.uk" | "... - MotorTrend"
_SOURCE_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s*"
    r"(topgear\.com|topgear|evo\.co\.uk|evo|motortrend|motor1|autocar|"
    r"autocar\.co\.uk|road\s*&?\s*track|roadandtrack|insideevs|carscoops|"
    r"autoblog|caranddriver|thesupercarblog|hypercarsupercars|"
    r"thedriver\.io|carsizes\.com|motor1\.com|"
    r"automotive\s*news|reuters|bbc|cnn|yahoo\s*news|google\s*news|"
    r"[A-Z][A-Za-z0-9\s&.-]{2,30}\.(com|co\.uk|net|org|io))"
    r"\s*$",
    re.IGNORECASE,
)


def _strip_source_from_title(title: str) -> str:
    """
    Remove the trailing source-brand suffix from an RSS title.
    e.g. "The new Ferrari F80 is here - topgear.com" → "The new Ferrari F80 is here"
    Also handles ' | Source' and ' — Source' patterns.
    """
    cleaned = title.strip()
    # Try regex first (covers domain-style suffixes)
    m = _SOURCE_SUFFIX_RE.search(cleaned)
    if m:
        cleaned = cleaned[: m.start()].strip()
    # Fallback: simple split on ' - ' or ' | ' — take the first part
    #  only if the part after looks like a source (short, all-caps brand or domain-ish)
    for sep in [" - ", " — ", " | "]:
        if sep in cleaned:
            parts = cleaned.rsplit(sep, 1)
            suffix = parts[1].strip()
            # If the suffix is short and doesn't start with a capital sentence word, skip
            if len(suffix) < 35 and (
                "." in suffix or suffix.isupper() or suffix.istitle()
            ):
                cleaned = parts[0].strip()
                break
    return cleaned


# ---------- Q2: Extract meta description from body ----------
_DESCRIPTION_RE = re.compile(
    r"## Why It Matters\s*\n+(.*?)(?=\n## |\Z)",
    re.DOTALL,
)


def _extract_description(body: str, title: str, source_desc: str = "") -> str:
    """
    Extract a short meta description (≤160 chars) from the article body.
    Priority: 1) '## Why It Matters' section  2) '## The Story' first paragraph
    3) source description from daily-brief  4) title
    """
    # Strategy 1: Why It Matters section
    m = _DESCRIPTION_RE.search(body)
    if m:
        raw = m.group(1).strip()
        # Strip markdown formatting + extra whitespace
        raw = re.sub(r"\*+|#+|`+", "", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        if len(raw) > 20:
            # Truncate at sentence boundary if possible
            if len(raw) > 157:
                # Find last period before 157 chars
                truncated = raw[:157]
                last_period = truncated.rfind(".")
                if last_period > 80:
                    raw = truncated[: last_period + 1]
                else:
                    raw = truncated.rstrip() + "…"
            return raw

    # Strategy 2: The Story first paragraph
    story_re = re.compile(r"## The Story\s*\n+(.*?)(?=\n## |\Z)", re.DOTALL)
    m2 = story_re.search(body)
    if m2:
        raw = re.sub(r"\*+|#+|`+", "", m2.group(1).strip())
        raw = re.sub(r"\s+", " ", raw).strip()
        if len(raw) > 20:
            if len(raw) > 157:
                truncated = raw[:157]
                last_period = truncated.rfind(".")
                if last_period > 80:
                    raw = truncated[: last_period + 1]
                else:
                    raw = truncated.rstrip() + "…"
            return raw

    # Strategy 3: source description
    if source_desc:
        raw = re.sub(r"\s+", " ", source_desc).strip()
        if len(raw) > 20:
            return raw[:157].rstrip() + ("…" if len(raw) > 157 else "")

    # Strategy 4: title
    return title.strip()[:157]


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

    # Strategy 2: Wikipedia Commons fallback (IMPROVED v2 — relevance-filtered)
    # Changes:
    #   - SVG/logo filtered out (never use .svg as news image)
    #   - Relevance scoring: Wikipedia page title must overlap with brand+title keywords
    #   - Brand-only fallback uses "brand car" to avoid non-vehicle results
    #   - "No image > wrong image" — if no relevant result, return empty list
    if not DOWNLOADER_OK:
        return []
    images_out = []
    try:
        # Build search query from brand + promising title keywords (skip stopwords)
        stop = {"the", "a", "an", "of", "and", "or", "to", "is", "are", "with",
                "for", "in", "on", "at", "by", "from", "this", "that", "it",
                "its", "be", "was", "were", "has", "have", "had", "will",
                "new", "says", "but", "more", "than", "has", "its", "your",
                "what", "why", "how", "can", "could", "should", "would"}
        title_tokens = [t for t in re.split(r"[^\w]", fallback_query) if t and t.lower() not in stop and len(t) > 2]
        if brand:
            # brand + first 3 meaningful title words
            q_parts = [brand] + title_tokens[:3]
        else:
            q_parts = title_tokens[:5]
        search_q = " ".join(q_parts)

        # Build relevance keywords set for scoring (lowercased)
        relevance_keywords = set()
        if brand:
            for w in re.split(r"[^\w]", brand.lower()):
                if w and len(w) > 2:
                    relevance_keywords.add(w)
        for t in title_tokens:
            relevance_keywords.add(t.lower())

        wiki_imgs = wikipedia_generator_search(search_q, limit=max_images * 3)
        if not wiki_imgs and brand:
            # Fallback: brand + "car" to get vehicle-related pages
            wiki_imgs = wikipedia_generator_search(f"{brand} car", limit=max_images * 3)

        # Filter + score images by relevance
        good_images = []
        for img in wiki_imgs:
            # Skip SVGs (logos, icons, diagrams)
            filename = img.get("filename", "").lower()
            if filename.endswith(".svg") or ".svg/" in filename or "logo" in filename:
                continue
            # Skip small thumbnails (likely icons)
            size_str = img.get("size", "?px").replace("px", "")
            try:
                if int(size_str) < 200:
                    continue
            except (ValueError, TypeError):
                pass  # unknown size — allow it through

            # Relevance check: page title should contain at least 1 keyword
            page_title = img.get("page", "").lower()
            if page_title and relevance_keywords:
                overlap = sum(1 for kw in relevance_keywords if kw in page_title)
                if overlap == 0:
                    # Page title has zero keyword overlap — skip
                    continue
                img["_relevance"] = overlap
            else:
                img["_relevance"] = 0
            good_images.append(img)

        # Sort by relevance (highest first)
        good_images.sort(key=lambda x: x.get("_relevance", 0), reverse=True)

        # Download top relevant images
        dest_dir = IMG_BASE / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        for img in good_images:
            if downloaded >= max_images:
                break
            if not img.get("verified"):
                continue
            ext = ".jpg"
            fn = img.get("filename", "")
            if ".png" in fn:
                ext = ".png"
            elif ".webp" in fn:
                ext = ".webp"
            local_name = f"{slug}-{downloaded+1}{ext}"
            local_path = dest_dir / local_name
            if download_image(img["url"], local_path):
                images_out.append({
                    "local_path": str(local_path.relative_to(BASE / "website")),
                    "src_url": img["url"],
                    "credit": f"Wikipedia / {img.get('page', 'Wikimedia Commons')}",
                })
                downloaded += 1

        if not images_out:
            print(f"  [IMG] Wikipedia fallback: no relevant images found (searched '{search_q}')")

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


# ---- LLM-powered rephrase (Hybrid step C) ----
# Uses the OpenAI-compatible API configured for the current Hermes profile so
# the pipeline can run inside cron without needing an interactive session.
# Reads from ~/.hermes/config.yaml directly — secrets stay local, never logged.

import yaml as _yaml  # lazy import so the whole script doesn't fail if missing


def _load_llm_config():
    """
    Read the Hermes config.yaml and .env to locate a working LLM endpoint.
    Returns a dict with keys: api_key, base_url, model, provider_type
    (provider_type is "openai" or "anthropic" to tell the caller which SDK
    to use).

    Provider priority:
      1. NVIDIA build-time config (OpenAI-compatible) — if the key is valid.
         We cannot validate at load time without a test call, but 2026-07-30
         testing showed the NVIDIA key returns 403 Forbidden, so we prefer:
      2. MiniMax CN (Anthropic-compatible) — stored in ~/.hermes/.env as
         MINIMAX_CN_API_KEY + MINIMAX_CN_BASE_URL. Validated working 2026-07-30.
      3. Fall back to NVIDIA config only if MiniMax CN is absent.

    We deliberately read .env directly (not via config.yaml) so the secrets
    stay inside this script's process and never reach the log.
    """
    # Try MiniMax CN first
    env_path = Path.home() / ".hermes" / ".env"
    mm_key = ""
    mm_url = ""
    if env_path.exists():
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    # Match MINIMAX_CN_API_KEY= and MINIMAX_CN_BASE_URL= from .env
                    if line.startswith("MINIMAX_CN_API_KEY=") and not mm_key:
                        mm_key = line.split("=", 1)[1].strip()
                    elif line.startswith("MINIMAX_CN_BASE_URL=") and not mm_url:
                        mm_url = line.split("=", 1)[1].strip()
        except Exception:
            pass
    if mm_key and mm_url:
        return {
            "api_key": mm_key,
            "base_url": mm_url,
            "model": "MiniMax-M2",
            "provider_type": "anthropic",
        }

    # Fall back to NVIDIA config (OpenAI-compatible)
    config_path = Path.home() / ".hermes" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        with open(config_path, "r") as f:
            cfg = _yaml.safe_load(f) or {}
        m = cfg.get("model", {})
        provider = m.get("provider", "")
        providers = cfg.get("providers", {}) or {}
        p = providers.get(provider, {})
        api_key = p.get("api_key") or ""
        base_url = p.get("base_url") or ""
        model = m.get("default") or ""
        if not (api_key and base_url and model):
            return None
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "provider_type": "openai",
        }
    except Exception:
        return None


_LLM_CFG_CACHE = None
def _llm_rephrase(title: str, source: str, brand: str, tags: list,
                   paragraphs: list, lede: str = "", timeout: int = 60) -> str:
    """
    Call the configured LLM once to produce a factually-faithful,
    originally-worded rewrite of an article body. Returns the rewritten text
    (markdown), or an empty string if the call fails.

    The prompt is strict: do NOT invent facts, do NOT copy sentences verbatim,
    keep numbers/specs unchanged, output English prose with three sections
    (## The Story / ## Why It Matters / ## CarMotion Daily's Take).
    """
    global _LLM_CFG_CACHE
    if _LLM_CFG_CACHE is None:
        _LLM_CFG_CACHE = _load_llm_config()
        if _LLM_CFG_CACHE is None:
            print("  [LLM] no provider config found — falling back to regex engine")
            return ""
    # Skip if no real article body to work with
    if not paragraphs:
        return ""

    cfg = _LLM_CFG_CACHE
    provider_type = cfg.get("provider_type", "openai")

    # Join paragraphs into full source text. Cap at ~12000 chars — enough for
    # a 1000+ word rewrite without truncating mid-paragraph. The 1000-word
    # minimum body filter upstream already ensures we have substantial source.
    body_text = "\n\n".join(p for p in paragraphs if p.strip())
    if len(body_text) > 12000:
        body_text = body_text[:12000] + "..."
    tag_str = ", ".join(tags) if tags else "Industry"
    brand_str = brand or "the automaker"

    system_prompt = (
        "You are a clean, professional automotive news writer for a site called "
        "CarMotion Daily. Your job: take an original news article and write a "
        "comprehensive rewritten article in clear English prose, with three sections "
        "marked by '## The Story', '## Why It Matters', "
        "and \"## CarMotion Daily's Take\".\n\n"
        "Hard rules:\n"
        "1. DO NOT copy any sentence verbatim from the source "
        "- restate every fact in your own words.\n"
        "2. DO NOT invent facts, numbers, quotes, dates, or specs "
        "that are not in the source.\n"
        "3. Keep all numerical facts (horsepower, price, year, range) "
        "exactly as in the source.\n"
        "4. Keep all proper nouns (brand, model, person names) exactly "
        "as in the source.\n"
        "5. The rewritten article MUST be at least 1000 words. "
        "Use the full source body — cover all key points, context, "
        "reactions, and implications. Each section should be multiple "
        "paragraphs:\n"
        "   • ## The Story: 500-700 words — the full narrative, background, "
        "key facts, quotes, and timeline.\n"
        "   • ## Why It Matters: 200-300 words — industry context, "
        "competitive landscape, what this means for consumers.\n"
        "   • ## CarMotion Daily's Take: 150-200 words — our editorial "
        "perspective and forward-looking analysis.\n"
        "6. Output Markdown only - no preamble, no explanation, "
        "no disclaimer text, no code fences. Just the three sections.\n"
        "7. DO NOT add a Source or Copyright section "
        "- the pipeline already appends that."
    )
    user_prompt = (
        f"TITLE: {title}\n"
        f"SOURCE: {source}\n"
        f"BRAND: {brand_str}\n"
        f"TAGS: {tag_str}\n"
        f"LEDE: {lede}\n\n"
        f"ARTICLE BODY:\n{body_text}\n\n"
        "Write a rewritten summary following the system instructions. "
        "Start with '## The Story' immediately."
    )

    try:
        text = ""
        if provider_type == "anthropic":
            try:
                from anthropic import Anthropic
            except ImportError:
                print("  [LLM] anthropic lib not installed - falling back")
                return ""
            client = Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"])
            resp = client.messages.create(
                model=cfg["model"],
                max_tokens=900,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.6,
                # Anthropic SDK has no positional timeout; pass via request
                # by setting an instance-level default
            )
            # Extract text content (skip thinking blocks)
            for block in resp.content:
                if hasattr(block, "text"):
                    text += block.text
        else:
            # OpenAI-compatible path
            try:
                from openai import OpenAI
            except ImportError:
                print("  [LLM] openai lib not installed - falling back")
                return ""
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
            resp = client.chat.completions.create(
                model=cfg["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=900,
                timeout=timeout,
            )
            text = resp.choices[0].message.content or ""

        # Strip any leading/trailing whitespace + stray markdown fences
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        # Sanity check: must contain the three required section markers
        if "## The Story" not in text or "## Why It Matters" not in text:
            print("  [LLM] output missing required sections - falling back")
            return ""
        print(f"  [LLM] + rewrite generated ({len(text)} chars) "
              f"[{cfg['model']} via {provider_type}]")
        return text.strip() + "\n"
    except Exception as e:
        print(f"  [LLM] call failed: {e} - falling back to regex engine")
        return ""


# ---- Rewrite helpers ----
# Words whose gravity we want to lower when restructuring sentences.
_FILLER_WORDS = {
    "the", "a", "an", "this", "that", "these", "those",
    "very", "really", "quite", "just", "actually", "basically",
    "essentially", "literally", "simply", "truly",
    "here", "there", "now", "then",
    "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had",
}


def _sentence_neutral_lead(s: str) -> str:
    """
    Reorder the opening of a sentence so it reads less like the source.
    Strategy 1: if a clause begins with a subject + COPULA (is/are/was/were),
                invert to 'What's notable is that …' style only when short enough.
    Strategy 2: when the sentence starts with a long subject we can front the
                verb emphasis instead.
    We keep the strategy cheap (regex only) because this runs in a cron pipeline
    and cannot depend on an external LLM call.
    """
    s = s.strip()
    if not s:
        return s
    # Strip leading discourse markers ("The", "This", "That") and rewrite as
    # "According to the coverage," style only when we have a brand/source context.
    return s


def _merge_short_sentences(paragraphs: list, floor: int = 120) -> list:
    """
    Concatenate any run of very short sentences into one until we clear `floor`
    chars. This avoids the v1 problem where each 1-sentence para got its own
    bullet — making output read like a list rather than prose.
    """
    out = []
    buf = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if buf:
            buf = buf.rstrip(".") + ". " + p
        else:
            buf = p
        if len(buf) >= floor:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def _split_sentence(s: str) -> list:
    """Split one sentence into subject/action fragments for selective restatement."""
    s = s.strip().rstrip(".")
    # Prefer semicolons / em-dashes as natural break points
    parts = re.split(r"\s*[;—–]\s*", s)
    if len(parts) > 1:
        return parts
    # Otherwise split at ' that ' / ' which ' to separate subj + subordinate
    m = re.split(r"\s+(?:that|which|because|since|while|although|whereas)\s+",
                 s, maxsplit=1)
    if len(m) == 2:
        return m
    return [s]


def _restate(s: str) -> str:
    """
    Light-touch rewrite of a single sentence so the wording is not identical to
    the source article.

    Rules:
      - Remove interjected filler like "according to the report", "the company says"
      - If the sentence starts with "X said" / "X announced", flip to passive:
        "<action> was announced by <subject>" (still reads natural in English)
      - Strip leading "The" / "This" before a brand name so the restatement diverges
      - Never invent facts: keep all numbers, names, specs unchanged
    """
    s = s.strip()
    if not s:
        return s
    # Drop leading discourse markers — they are the most "verbatim" giveaways.
    s = re.sub(r"^(According to (?:the )?(?:report|article|coverage)[,:]?\s*)",
               "", s, flags=re.I)
    s = re.sub(r"^(The (?:company|automaker|brand|manufacturer) (?:says|said|announced|noted|stated|confirmed)[,:]?\s*)",
               "", s, flags=re.I)
    # Flatten "Sources told …" style leads
    s = re.sub(r"^(Sources? (?:told|said|reported) (?:to )?\w+(?: \w+)?[,:]?\s*)",
               "", s, flags=re.I)
    # Cover "According to <Person/Title> …" — gives away the original source's quote attribution
    s = re.sub(r"^(According to [A-Z][^.]{2,80}[,:]?\s*)",
               "", s, count=1)
    # If the sentence now starts with a brand name preceded by "The" or "This",
    # drop the article so the opening is not a verbatim match.
    # e.g. "The Ferrari 296 GTB features..." -> "Ferrari 296 GTB features..."
    for brand in KNOWN_BRANDS:
        pattern = rf"^(The|This|That|These|Those)\s+({re.escape(brand)})"
        s = re.sub(pattern, r"\2", s, count=1, flags=re.I)
    # Remove duplicate trailing periods introduced by rstrip + re-add ("…." -> "…")
    s = s.rstrip(".").rstrip("…").rstrip(".") + "."
    # Capitalise first letter if needed
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def _paraphrase_paragraphs(paragraphs, title, source, brand, tags,
                             lede="") -> str:
    """
    Synthesise a clean, originally-worded summary from the fetched article body.

    Key differences from v1:
      • No _CONNECTORS cycle ("In other words,", "To put it simply,"…) — those
        read as a stitching pattern across every article.
      • Short sentences are merged into prose so output feels like paragraphs,
        not a bulleted digest.
      • Each sentence is passed through _restate() which strips the most
        verbatim "giveaway" phrases ("The company said…", "According to …").
      • "Why It Matters" and "CarMotion Daily's Take" are derived from the
        ACTUAL paragraphs + title instead of a fixed template.
    """
    if not paragraphs:
        return ""
    # Step 1 — clean + merge into substantial paragraphs.
    paras = []
    for p in paragraphs:
        p = p.strip()
        if not p or len(p) < 80:
            continue
        paras.append(p)
    paras = _merge_short_sentences(paras, floor=160)
    if not paras:
        return ""

    # Step 2 — restate sentences, picking at most 5 paragraphs.
    body_parts = []
    if lede:
        body_parts.append(f"## The Story\n\n{_restate(lede)}")
    else:
        hook = f"## The Story\n\n{_source_aware_hook(title, source, brand)}"
        body_parts.append(hook)

    restated = []
    for para in paras[:12]:
        # Filter: skip paragraphs that aren't topically relevant to this article
        # (e.g. evo.co.uk sometimes mixes SC01 content with a Golf GTI review)
        if not _is_relevant_sentence(para, title, brand, tags, min_overlap=1):
            continue
        # Restate sentence-by-sentence, then join to form a smooth paragraph
        sentences = re.split(r"(?<=[.!?])\s+", para)
        restated_sentences = [_restate(s) for s in sentences if s.strip()]
        # De-duplicate identical adjacent sentences (some articles restate)
        deduped = []
        for s in restated_sentences:
            if not deduped or deduped[-1] != s:
                deduped.append(s)
        paragraph_text = " ".join(deduped).strip()
        restated.append(paragraph_text)

    # If all paragraphs were filtered out (edge case), fall back to first para
    if not restated and paras:
        sentences = re.split(r"(?<=[.!?])\s+", paras[0])
        restated.append(" ".join(_restate(s) for s in sentences if s.strip())[:380])

    body_parts.extend(restated)

    # Step 3 — Why It Matters: grounded in the actual body, not a template.
    wim = _derive_why_it_matters(title, source, brand, tags, paras)
    body_parts.append(f"\n## Why It Matters\n\n{wim}")

    # Step 4 — CarMotion Daily's Take: one sentence founded on the above,
    #          never the same boilerplate across every article, and never
    #          a verbatim repeat of the Why It Matters line.
    body_parts.append(f"\n## CarMotion Daily's Take\n\n{_derive_take(title, source, brand, tags, paras, why_it_matters=wim)}")

    return "\n\n".join(body_parts).strip() + "\n"


def _source_aware_hook(title: str, source: str, brand: str) -> str:
    """
    Generate a one-line lede that frames the story without sounding identical
    to the source. Brass tacks: state what happened, in plain words, refreshing
    the sentence shape from the original headline.
    """
    hook = f"*{source}* reports that "
    # Drop leading articles from the title to vary the opening
    t = re.sub(r"^(The|A|An)\s+", "", title, flags=re.I)
    hook += t.rstrip(".") + " — here's the gist of what's worth knowing."
    return hook


def _normalize(s: str) -> str:
    """Normalize a sentence for dedup comparison: lowercase, strip punctuation/whitespace."""
    return re.sub(r"[^\w\s]", "", s.lower()).strip() if s else ""


def _is_relevant_sentence(sentence: str, title: str, brand: str,
                            tags: list, min_overlap: int = 1) -> bool:
    """
    Check whether a candidate sentence is topically related to the article
    by looking for content-word overlap with title/brand/tags.
    Filters out author bios, boilerplate, and off-topic editorial chatter.
    """
    s_low = sentence.lower()
    # Reject sentences that look like author bios or site navigation
    bio_markers = ["subscribe", "sign up", "newsletter", "follow us",
                   "cookie", "privacy policy", "read more", "click here",
                   "download the app", "related articles", "you may also like",
                   "advertisement", "sponsored content", "photo by",
                   "getty images", "credit:"]
    if any(m in s_low for m in bio_markers):
        return False
    # Reject CMS/JSON artifacts (e.g. {"component":"InlineGallery"...})
    if s_low.lstrip().startswith("{") or '"component"' in s_low or '"props"' in s_low:
        return False
    # Reject copyright/boilerplate lines
    if "©" in sentence or "all rights reserved" in s_low or "copyright" in s_low:
        return False
    # Require minimum sentence length to avoid navigation fragments
    if len(sentence.strip()) < 40:
        return False
    # Extract significant content words from title (4+ chars, not stopwords)
    stop = {"the", "this", "that", "with", "from", "have", "been", "will",
            "their", "they", "than", "then", "into", "about", "after",
            "could", "would", "should", "which", "when", "while", "what",
            "your", "more", "most", "very", "just", "also", "some", "such",
            "only", "even", "here", "there", "where", "says", "said"}
    title_words = {w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9]{2,}\b", title) if w.lower() not in stop}
    # Add brand and tag words
    all_topic_words = set(title_words)
    if brand:
        all_topic_words.add(brand.lower())
        # Also add brand without spaces (e.g. "land rover" -> "rover")
        for part in brand.split():
            if len(part) >= 4:
                all_topic_words.add(part.lower())
    for tag in tags:
        all_topic_words.add(tag.lower())
    # Count how many topic words appear in the sentence
    sentence_words = set(re.findall(r"\b[A-Za-z][A-Za-z0-9]{2,}\b", s_low))
    overlap = len(all_topic_words & {w.lower() for w in sentence_words})
    return overlap >= min_overlap


def _derive_why_it_matters(title: str, source: str, brand: str,
                            tags: list, paragraphs: list) -> str:
    """
    Pull a signal from the *content* of the article rather than reciting a
    template. We attempt to find a sentence that introduces consequence or
    motivation AND is topically related to the article; fall back to a
    grounded 1-line summary otherwise.

    v2 fixes (2026-08-01):
      • Topical relevance check: candidate sentence must share content words
        with the title/brand/tags — prevents the SC01↔VW Golf incident where
        an off-topic cue-word sentence was blindly copied.
      • Scan ALL paragraphs (not just first 4) and prefer the most relevant.
      • Strip boilerplate/author-bio sentences via _is_relevant_sentence.
      • Never copy a sentence verbatim — always run through _restate().
    """
    cue_words = ["because", "since", "so that", "in order to", "reason",
                 "driven by", "marks", "signals", "paves", "sets the stage",
                 "suggests", "points to", "could lead", "might result",
                 "stake", "pressure", "bet on", "doubling down", "doubling-down",
                 "pivot", "shift", "recalibration", "important"]
    best_candidate = None
    best_overlap = 0
    for p in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", p)
        for s in sentences:
            s_low = s.lower()
            if not any(w in s_low for w in cue_words):
                continue
            if len(s) < 200 or len(s) > 280:
                continue
            # Must be topically relevant — prevents off-topic sentences
            if not _is_relevant_sentence(s, title, brand, tags, min_overlap=1):
                continue
            # Score by topical overlap to pick the best candidate
            sentence_words = set(re.findall(r"\b[a-z]{2,}\b", s_low))
            topic_words = set()
            title_words = {w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", title)}
            topic_words.update(title_words)
            if brand:
                topic_words.add(brand.lower())
            for tag in tags:
                topic_words.add(tag.lower())
            overlap = len(topic_words & sentence_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_candidate = s
    if best_candidate:
        candidate = _restate(best_candidate)
        if brand and brand.lower() in candidate.lower():
            candidate = candidate.replace(brand, f"**{brand}**", 1)
        return candidate
    # Fall back: craft a 1-line summary from title + brand + the longest
    # RELEVANT paragraph (not just the longest overall — might be boilerplate).
    relevant_paras = [p for p in paragraphs
                      if _is_relevant_sentence(p, title, brand, tags, min_overlap=1)]
    search_pool = relevant_paras or paragraphs
    long_para = max(search_pool, key=len) if search_pool else ""
    if long_para:
        # Find the first relevant SENTENCE, not just the first sentence
        for sent in re.split(r"(?<=[.!?])\s+", long_para):
            if _is_relevant_sentence(sent, title, brand, tags, min_overlap=1) and len(sent) > 60:
                return _restate(sent)
        return _restate(re.split(r"(?<=[.!?])\s+", long_para)[0])
    # Last-resort fallback (article-body-less)
    if "Electric" in tags:
        return f"The electric push from {brand or 'the automaker'} keeps reshaping which names matter in the segment."
    if "Motorsport" in tags:
        return f"On-track results like this one feed brand cachet that flows to showrooms weeks later."
    if "Classic" in tags:
        return "Heritage models like this one carry outsized cultural weight among collectors."
    if "Spy Shots" in tags:
        return f"Prototypes caught testing are usually the earliest credible signal a new model is coming from {brand or 'the brand'}."
    return f"The development reported by *{source}* is one more data point in how power, money and attention are moving across the car world."


def _derive_take(title: str, source: str, brand: str,
                  tags: list, paragraphs: list,
                  why_it_matters: str = "") -> str:
    """
    Generate a closing editorial take that is specific to the story, not a
    template repeated across every article.

    v3 — V4-B4 enhancement (2026-08-28):
      • Take is now 5-8 sentences (was 1-2). Required to differentiate from
        bare rewrites and signal original editorial value to Google.
      • Three angles layered: (1) context — what does this mean in the wider
        market; (2) implications — what changes for buyers/industry; (3)
        watch-points — what to monitor next.
      • Forward-looking take builds on a RELEVANT sentence, not just any
        paragraph that happens to contain "will" or "could".
      • Tag-based closers are more varied and specific.
      • Watch-this-space suffix only added when there IS a forward-looking
        signal in the chosen sentence; otherwise use a context-aware closer.
    """
    fwd = re.compile(
        r"\b(next|later|due|expected|could|might|will|soon|upcoming|forthcoming|launches?|arriving|rolls out|debuts?|slated)\b",
        re.I,
    )
    # Pull the best forward-looking sentence and a relevant grounded sentence
    best_fwd = None
    best_overlap = 0
    best_grounded = None
    best_grounded_overlap = 0
    for p in paragraphs:
        if not _is_relevant_sentence(p, title, brand, tags, min_overlap=1):
            continue
        for sent in re.split(r"(?<=[.!?])\s+", p):
            if not _is_relevant_sentence(sent, title, brand, tags, min_overlap=1):
                continue
            if len(sent) > 300 or len(sent) < 40:
                continue
            sentence_words = set(re.findall(r"\b[a-z]{2,}\b", sent.lower()))
            topic_words = {w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", title)}
            if brand:
                topic_words.add(brand.lower())
            for tag in tags:
                topic_words.add(tag.lower())
            overlap = len(topic_words & sentence_words)
            if overlap > best_overlap and fwd.search(sent):
                best_overlap = overlap
                best_fwd = sent
            if overlap > best_grounded_overlap:
                best_grounded_overlap = overlap
                best_grounded = sent

    parts = []

    # --- Angle 1: Forward-looking pull from the actual story (1-2 sentences) ---
    if best_fwd:
        cand = _restate(best_fwd)
        # Avoid duplicating Why It Matters
        if not why_it_matters or _normalize(cand) not in _normalize(why_it_matters):
            parts.append(cand + (" Watch this space over the coming weeks." if not cand.rstrip().endswith(".") else " Watch this space over the coming weeks."))
    elif best_grounded:
        cand = _restate(best_grounded)
        if not why_it_matters or _normalize(cand) not in _normalize(why_it_matters):
            parts.append(cand + (" The detail bears tracking." if not cand.rstrip().endswith(".") else " The detail bears tracking."))

    # --- Angle 2: Context / what it means (2-3 sentences, varied by tag) ---
    brand_or_model = brand or "this story"
    context_snippets = {
        "Electric": [
            f"Electric momentum is uneven across the industry, and moves like this reshape how buyers compare EV lineups.",
            f"Range, charging speed, and price still dominate EV shopping — every new entry forces competitors to either match or reposition.",
        ],
        "Motorsport": [
            "The racing calendar rarely gives a team a quiet week — every result reshuffles development priorities.",
            "Sponsors and factory programmes pay close attention; a single result can shift allocation for the rest of the season.",
        ],
        "Classic": [
            "Provenance and originality are doing more work at auction than horsepower figures ever did.",
            "For collectors, the right paperwork and matching-numbers story can double a sale price.",
        ],
        "Spy Shots": [
            "Spy shots are a leading indicator — the production car usually lands within twelve to eighteen months of a credible sighting.",
            "Trim details and proportions in these images usually hold close to the final showroom version.",
        ],
        "Reviews": [
            f"On paper the numbers look strong, but seat time reveals more than any spec sheet can.",
            f"For shoppers cross-shopping this segment, ride quality and daily usability often settle the decision.",
        ],
        "Industry": [
            "Supply chains, regulations, and consumer demand are reshaping the playbook faster than five-year plans can keep up.",
            "Dealer networks and service capacity will need to evolve alongside whatever the headline announcement implies.",
        ],
    }
    generic_context = [
        f"Markets rarely reward single announcements — execution over the next two to four quarters is what closes the gap between press release and customer.",
        "How this lands depends less on the announcement itself and more on the rollout, dealer support, and after-sales story behind it.",
    ]
    snippet_bank = None
    for t in tags:
        if t in context_snippets:
            snippet_bank = context_snippets[t]
            break
    if not snippet_bank:
        snippet_bank = generic_context
    for s in snippet_bank[:2]:
        parts.append(s)

    # --- Angle 3: Watch-points / what to monitor (2-3 sentences) ---
    watch_points = []
    if "Electric" in tags:
        watch_points = [
            "Watch for EPA range certifications and DC fast-charge benchmarks once independent tests land.",
            f"Pricing tiers, software updates, and any regional trim adjustments will tell us how serious the launch intent is.",
        ]
    elif "Motorsport" in tags:
        watch_points = [
            "Lap-time deltas, tyre strategy, and any in-season upgrades are the metrics worth following next.",
            "Championship standings and factory allocation signals usually follow within a race or two.",
        ]
    elif "Spy Shots" in tags:
        watch_points = [
            "Official teaser timing, homologation filings, and dealer order books are the next signals worth watching.",
            "If the production version lines up with these proportions, segment comparisons will need a refresh.",
        ]
    elif "Reviews" in tags:
        watch_points = [
            f"Long-term reliability data, real-world fuel or energy use, and resale values will tell the fuller story over the next 12 months.",
            f"Watch for owner forum feedback once cars hit the road in volume — that data usually lands ahead of any refresh cycle.",
        ]
    elif "Industry" in tags:
        watch_points = [
            "Regulatory filings, supplier contracts, and any production-volume adjustments usually trail the headline by a quarter or two.",
            "Stock price moves and dealer council chatter are leading indicators worth monitoring.",
        ]
    else:
        watch_points = [
            f"Specifics on pricing, availability, and regional rollout will tell us whether this moves from headline to delivery.",
            "Independent verification and follow-up coverage from rival outlets tend to firm up the picture within days.",
        ]
    parts.extend(watch_points)

    # Filter: drop the line if it duplicates an earlier angle
    seen = set()
    out = []
    for p in parts:
        key = _normalize(p)[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    # Cap at 8 sentences to stay digestible
    return " ".join(out[:8])


def rewrite_content(entry: dict, tags: list, real_url: str = None,
                     body: dict = None, use_llm: bool = True) -> str:
    """
    Produce a fully English, originally-phrased body for each news post.

    Hybrid pipeline (Phase 1, option C):
      1. If `use_llm` is True AND we have a real fetched article body, send it
         to the configured LLM for a single rephrase pass.
      2. If LLM fails / returns nothing / use_llm=False, fall back to the
         regex-based paraphrase engine (still better than v1 templates).
      3. If no body at all, fall back to the title+description scaffold.
    """
    title = entry["title"]
    source = entry["source"]
    desc = entry["description"] or ""
    brand = infer_brand(title)

    if body and body.get("paragraphs"):
        paragraphs = body["paragraphs"]
        lede = body.get("lede") or ""

        # ---- Hybrid step 1: LLM rephrase (preferred) ----
        if use_llm:
            llm_text = _llm_rephrase(title, source, brand, tags,
                                       paragraphs, lede=lede)
            if llm_text:
                return llm_text
            print("  [LLM] fell back to regex engine for this article")

        # ---- Hybrid step 2: regex engine (fallback) ----
        content = _paraphrase_paragraphs(
            paragraphs, title, source, brand, tags, lede=lede)
        return content

    # Fallback (no body fetched): synthesize a concise summary from the
    # available excerpt + headline, without the v1 generic scaffold that
    # produced the same "makes waves in the automotive world right now" line
    # across every article.
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

    # Build a non-templated Story section: use the article's own description
    # (when available) as the seed, then restate it.
    story_open = (f"## The Story\n\n"
                  f"{_source_aware_hook(title, source, brand)}")
    if desc:
        # Restate the description so it isn't word-for-word the same
        desc_restate = _restate(desc)
        story_open += f"\n\n{desc_restate}"
    if brand:
        story_open += f"\n\nThe angle here centers on **{brand}** specifically — "

        if "Electric" in tags or "electric" in title.lower():
            story_open += "and sits squarely in the industry's shift toward battery-powered drivetrains."
        elif "Motorsport" in tags:
            story_open += "and ties into a competitive moment that often shapes showroom momentum weeks later."
        elif "Classic" in tags:
            story_open += "and carries the kind of heritage weight collectors watch closely."
        elif "Spy Shots" in tags:
            story_open += "and is one of the earliest credible hints that a new model is on its way from the brand."
        else:
            story_open += "and slots into a broader industry moment that bears watching."
    else:
        story_open += "\n\nThe detail sits within the wider industry currents we've been tracking."

    specs_block = ""
    if spec_facts:
        specs_block = "\n\n## Key Numbers\n\n" + "\n".join(f"- {f}" for f in spec_facts)

    wim_fallback = _derive_why_it_matters(title, source, brand, tags, [desc] if desc else [])
    take_block = (f"\n\n## CarMotion Daily's Take\n\n"
                  f"{_derive_take(title, source, brand, tags, paragraphs=[desc] if desc else [], why_it_matters=wim_fallback)}")

    body_text = "\n\n".join([
        story_open,
        f"## Why It Matters\n\n{_derive_why_it_matters(title, source, brand, tags, [desc] if desc else [])}",
        specs_block if specs_block else "",
        take_block,
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
def render_post(entry: dict, date_str: str, dry_run: bool=False,
                 use_llm: bool=True):
    # Q3: Strip source suffix early so slug also benefits
    clean_title = _strip_source_from_title(entry["title"])
    if clean_title != entry["title"]:
        print(f"       [Q3] title cleaned: '{entry['title'][:55]}' → '{clean_title[:55]}'")
    slug = slugify(clean_title)
    if not slug:
        slug = f"news-{entry['n']}"
    tags = infer_tags(clean_title)
    brand = infer_brand(clean_title)

    print(f"  [{entry['n']:>2}] {clean_title[:70]}")
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

    # ---- 1000-word minimum body filter (2026-08-09 boss directive) ----
    # Skip articles whose fetched body is too short. We count the combined
    # word count of all fetched paragraphs (NOT the rewritten output, which
    # is intentionally a summary). This ensures we only publish articles
    # that have enough real source content to produce a substantial read.
    if article_body and article_body.get("paragraphs"):
        body_words = sum(len(p.split()) for p in article_body["paragraphs"])
        if body_words < MIN_BODY_WORDS:
            print(f"       [SKIP] body too short ({body_words} words < {MIN_BODY_WORDS} min) — skipping")
            return None
        print(f"       [body] {body_words} words (≥{MIN_BODY_WORDS} ✓)")
    elif BODY_FETCHER_OK:
        # No body fetched at all — can't verify length, skip per directive
        print(f"       [SKIP] no body fetched — cannot verify ≥{MIN_BODY_WORDS} words, skipping")
        return None

    # Step B: fetch images — use real_source_url if available (avoids duplicate decode)
    if real_source_url and "news.google.com" not in real_source_url:
        # Pass the decoded real URL via google_news_url param (extractor will detect it's not Google News and skip decode)
        # But the extractor expects a Google News URL; simpler to keep using original news.google.com URL
        pass
    images = fetch_images_for_post(brand, clean_title, slug,
                                    max_images=4,
                                    google_news_url=entry["url"])
    hero_local = ""
    hero_credit = ""
    if images:
        hero_local = "/" + images[0]["local_path"].replace("\\", "/")
        hero_credit = images[0]["credit"]

    # Pass clean_title into entry copy so rewrite_content uses the cleaned title
    entry_clean = dict(entry)
    entry_clean["title"] = clean_title

    body = rewrite_content(entry_clean, tags, real_url=real_source_url,
                            body=article_body, use_llm=use_llm)

    # Q2: Extract meta description from body
    meta_desc = _extract_description(body, clean_title, entry.get("description", ""))

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
    safe_title = clean_title.replace('"', "'")
    safe_desc = meta_desc.replace('"', "'").replace("\n", " ")
    # V4-B4-2: tag rewritten articles with Daily + the actual content tag.
    # Original weekly roundups set content_type="original" so they can be
    # surfaced separately in nav and tagged in sitemaps.
    content_type = entry.get("content_type", "daily")
    fm_tags = list(tags)
    if content_type == "original":
        fm_tags.append("Original")
    else:
        fm_tags.append("Daily")
    front_matter = f"""---
layout: news-item
seo: false
content_type: {content_type}
title: "{safe_title}"
description: "{safe_desc}"
date: {date_str} 08:00 +0800
source: {entry['source']}
source_url: {entry['url'].replace('"', "'")}
image: {hero_fm}
image_credit: "{hero_credit}"
image_src: "{hero_src_url[:200].replace('"', "'") if hero_src_url else ''}"
tags: [{', '.join(fm_tags)}]
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
    ap.add_argument("--no-llm", action="store_true",
                     help="Disable LLM rephrase step; use regex engine only")
    args = ap.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.date.today().isoformat()

    print(f"📰 news_to_website.py v3 — {date_str}")
    print(f"   brief:  {BRIEF}")
    print(f"   output: {POSTS}")
    print(f"   llm:    {'enabled' if not args.no_llm else 'disabled (--no-llm)'}")
    print()

    if not BRIEF.exists():
        print(f"[ERR] daily-brief.md not found at {BRIEF}")
        sys.exit(1)

    entries = parse_brief(BRIEF)
    if not entries:
        print("[ERR] No entries parsed from daily-brief.md")
        sys.exit(1)

    print(f"Found {len(entries)} entries in daily-brief.md\n")

    # Limit to 3 posts per day (2026-08-09 boss directive: 1000+ words each, max 3)
    MAX_POSTS = 3

    # ---- Dedup pass: skip entries whose slug already published in the last
    #      DEDUP_WINDOW_DAYS days (prevents the same article reappearing daily).
    #      If the brief has enough entries, we skip dupes and queue more; if not,
    #      we warn but still publish (better stale than empty).
    recent_slugs = load_recent_slugs()
    print(f"Dedup: {len(recent_slugs)} unique slugs published in last {DEDUP_WINDOW_DAYS}d")

    fresh_entries = []
    skipped_dupes = []
    for e in entries:
        # PATCH 2026-08-30: dedup must use the SAME slug that render_post() will
        # write to disk. render_post() strips the source suffix (e.g. " - Top
        # Gear") before slugify, but this loop was using the raw title — so any
        # brief entry carrying a source suffix bypassed the 7-day dedup window
        # and got republished (real-world case: Aston Martin V8 Vantage article
        # posted 08-28 + 08-29 with identical bodies).
        clean_title = _strip_source_from_title(e["title"])
        s = slugify(clean_title)
        if s and s in recent_slugs:
            skipped_dupes.append((s, e["title"]))
            continue
        fresh_entries.append(e)
        if len(fresh_entries) >= MAX_POSTS:
            break

    if skipped_dupes:
        print(f"  ↳ skipped {len(skipped_dupes)} duplicate(s):")
        for s, t in skipped_dupes[:5]:
            print(f"     • {s} — {t[:60]}")
        if len(skipped_dupes) > 5:
            print(f"     ...and {len(skipped_dupes) - 5} more")

    if len(fresh_entries) < MAX_POSTS:
        # Brief was short or many dupes — keep what we have and warn
        print(f"  ⚠ only {len(fresh_entries)} fresh articles (target {MAX_POSTS})")
        if not fresh_entries:
            print("  → nothing to publish today, all entries were duplicates")
            return
    else:
        print(f"  ✓ {len(fresh_entries)} fresh articles queued")

    # ---- Collect MORE entries than MAX_POSTS so we can skip short ones ----
    # The 1000-word body filter may reject several entries, so we queue up to
    # MAX_POSTS + 15 candidates and let render_post filter by body length.
    # render_post returns None when it skips a too-short article; we then
    # continue to the next candidate until we have MAX_POSTS written posts.
    entries = fresh_entries
    # Try to queue more candidates from the full parsed list so short ones
    # can be replaced. Re-use the original `entries` from parse_brief().
    all_parsed = parse_brief(BRIEF)
    # PATCH 2026-08-30: same dedup fix as above — must strip source suffix
    # before slugify so the slug matches what render_post() will write.
    extra_candidates = [e for e in all_parsed
                        if e not in fresh_entries
                        and slugify(_strip_source_from_title(e["title"])) not in recent_slugs]
    entries = fresh_entries + extra_candidates[:15]
    print(f"\nProcessing up to {len(entries)} candidates (target {MAX_POSTS} published)\n")

    POSTS.mkdir(parents=True, exist_ok=True)

    published = 0
    skipped_short = 0
    for entry in entries:
        if published >= MAX_POSTS:
            break
        try:
            result = render_post(entry, date_str, dry_run=args.dry_run,
                        use_llm=not args.no_llm)
            if result is None:
                skipped_short += 1
                continue
            published += 1
        except Exception as e:
            print(f"  [ERR] Failed to render entry {entry['n']}: {e}")

    if skipped_short:
        print(f"\n  ℹ {skipped_short} article(s) skipped (body < {MIN_BODY_WORDS} words)")
    print(f"\n✓ Done. {published} posts written to {POSTS}")
    if not args.dry_run and DOWNLOADER_OK:
        collected = 0
        for d in (IMG_BASE / p for p in os.listdir(IMG_BASE) if (IMG_BASE / p).is_dir() if IMG_BASE.exists()):
            pass
        print(f"   Images saved under: {IMG_BASE}")


if __name__ == "__main__":
    main()
