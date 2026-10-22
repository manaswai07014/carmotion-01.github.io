#!/usr/bin/env python3
"""
og_image_generator.py — V4-C5
Build-time generator for branded Open Graph (1200x630) images.
Reads each Jekyll _posts/*.md, downloads the hero image, overlays title +
brand bar, and saves to static/og/<slug>.jpg.

Triggered by run_daily_pipeline.py after website posts are written.

Usage:
    python3 scripts/og_image_generator.py            # process latest 7 days
    python3 scripts/og_image_generator.py --days 30  # process last 30 days
    python3 scripts/og_image_generator.py --post PATH  # process single post
"""

import os, re, sys, json, argparse, datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from io import BytesIO

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("[ERROR] Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

BASE = Path(os.path.expanduser("~/car-evolution-project"))
POSTS = BASE / "website" / "_posts"
OG_DIR = BASE / "website" / "static" / "og"
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

# ---------- helpers ----------

def load_font(size: int):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

def fetch_image(url: str) -> Image.Image:
    """Download image and return PIL Image (RGB). Never raises."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 CarMotion-OGBot"})
        with urlopen(req, timeout=15) as r:
            data = r.read()
        if len(data) < 4096:
            return None
        img = Image.open(BytesIO(data)).convert("RGB")
        return img
    except Exception as e:
        print(f"[OG] fetch fail ({url[:80]}): {e}")
        return None

def parse_post(path: Path) -> dict:
    """Pull title + image + slug from frontmatter."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm = {}
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm_block = text[4:end]
            for line in fm_block.split("\n"):
                m = re.match(r'^([a-z_]+):\s*(.*)$', line.strip())
                if m:
                    k, v = m.group(1), m.group(2).strip().strip('"').strip("'")
                    if v.startswith("[") and v.endswith("]"):
                        fm[k] = [t.strip().strip('"').strip("'") for t in v[1:-1].split(",") if t.strip()]
                    else:
                        fm[k] = v
    slug = path.stem
    return {
        "title": fm.get("title", slug),
        "source": fm.get("source", "CarMotion Daily"),
        "image_src": fm.get("image_src", ""),
        "image": fm.get("image", ""),
        "slug": slug,
        "date": fm.get("date", "")[:10],
    }

def crop_to_og(img: Image.Image, size=(1200, 630)) -> Image.Image:
    """Cover-crop image to 1200x630."""
    target_ratio = size[0] / size[1]
    src_ratio = img.width / img.height
    if src_ratio > target_ratio:
        # source is wider — crop sides
        new_w = int(img.height * target_ratio)
        x0 = (img.width - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, img.height))
    else:
        # source is taller — crop top/bottom
        new_h = int(img.width / target_ratio)
        y0 = (img.height - new_h) // 2
        img = img.crop((0, y0, img.width, y0 + new_h))
    return img.resize(size, Image.LANCZOS)

def wrap_text(text: str, font, max_width: int, draw) -> list:
    """Break text into lines that fit max_width pixels."""
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                # word too long — just keep it
                lines.append(w)
                cur = []
    if cur:
        lines.append(" ".join(cur))
    return lines

def render_og(post: dict) -> Path:
    """Generate the 1200x630 OG image, return path."""
    OG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OG_DIR / f"{post['slug']}.jpg"

    # Try to use hero image
    hero_url = post.get("image_src") or ""
    hero_local_rel = post.get("image", "")
    hero_local = None
    if hero_local_rel and hero_local_rel.startswith("/"):
        candidate = BASE / "website" / hero_local_rel.lstrip("/")
        if candidate.exists():
            try:
                hero_local = Image.open(candidate).convert("RGB")
            except Exception:
                hero_local = None

    bg = None
    if hero_local:
        bg = hero_local
    elif hero_url:
        bg = fetch_image(hero_url)

    if bg is None:
        # Fallback: gradient placeholder
        bg = Image.new("RGB", (1200, 630), "#0a0a0a")
        draw = ImageDraw.Draw(bg)
        for y in range(630):
            t = y / 630
            r = int(10 + (40 - 10) * t)
            g = int(10 + (10 - 10) * t)
            b = int(10 + (10 - 10) * t)
            draw.line([(0, y), (1200, y)], fill=(r, g, b))

    img = crop_to_og(bg, (1200, 630))
    # Darken with a semi-transparent gradient so text reads
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # bottom gradient — fully transparent at top, 200 alpha at bottom
    for y in range(630):
        t = max(0, (y - 250) / 380)
        a = int(min(220, max(0, t * 220)))
        od.line([(0, y), (1200, y)], fill=(0, 0, 0, a))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Brand bar (top-left)
    brand_font = load_font(28)
    draw.rectangle([(0, 0), (1200, 56)], fill=(213, 0, 28))  # accent red
    draw.text((28, 14), "CarMotion Daily", font=brand_font, fill=(255, 255, 255))

    # Source label (top-right)
    src_font = load_font(20)
    src = post.get("source", "")[:30]
    src_bbox = draw.textbbox((0, 0), src, font=src_font)
    draw.text((1200 - src_bbox[2] - 28, 18), src, font=src_font, fill=(255, 255, 255))

    # Title — wrap to fit, max 2 lines for cleanliness
    title_font = load_font(54)
    title_lines = wrap_text(post["title"], title_font, 1100, draw)[:3]
    y = 360
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        w = bbox[2] - bbox[0]
        # Drop shadow
        draw.text(((1200 - w) / 2 + 2, y + 2), line, font=title_font, fill=(0, 0, 0))
        draw.text(((1200 - w) / 2, y), line, font=title_font, fill=(255, 255, 255))
        y += 64

    # Date footer
    if post.get("date"):
        date_font = load_font(22)
        draw.text((28, 590), post["date"], font=date_font, fill=(220, 220, 220))

    img.save(out_path, "JPEG", quality=85, optimize=True)
    return out_path

# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--post", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.post:
        posts = [parse_post(Path(args.post))]
    else:
        cutoff = datetime.date.today() - datetime.timedelta(days=args.days)
        posts = []
        for p in sorted(POSTS.glob("*.md"), reverse=True):
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", p.name)
            if not m:
                continue
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d >= cutoff:
                posts.append(parse_post(p))

    print(f"[OG] processing {len(posts)} posts")
    n_ok = n_skip = 0
    for post in posts:
        out = OG_DIR / f"{post['slug']}.jpg"
        if out.exists() and out.stat().st_mtime > (datetime.date.today() - datetime.timedelta(days=args.days)).toordinal():
            # Skip if fresh enough
            n_skip += 1
            continue
        try:
            if not args.dry_run:
                render_og(post)
            n_ok += 1
        except Exception as e:
            print(f"[OG] fail {post['slug']}: {e}")

    print(f"[OG] done. {n_ok} generated, {n_skip} cached, {len(posts) - n_ok - n_skip} failed")

if __name__ == "__main__":
    main()
