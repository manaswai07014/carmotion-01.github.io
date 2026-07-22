#!/usr/bin/env python3
"""
preview.py v2 — Static HTML preview renderer (no Jekyll needed).
White evo.co.uk-inspired theme with featured article + images + full body.

Run:  python3 scripts/preview.py
Then: open public/index.html (or via HTTP server)
"""
import os, re, html, urllib.parse
from pathlib import Path
from datetime import datetime

BASE  = Path(os.path.expanduser("~/car-evolution-project/website"))
POSTS = BASE / "_posts"
CSS   = BASE / "assets" / "css" / "style.css"
OUT   = BASE / "public"

FM_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)

def parse_fm(text):
    m = FM_RE.match(text)
    if not m: return {}, text
    fm, body = m.group(1), m.group(2)
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip(); v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [t.strip() for t in v[1:-1].split(",")]
            elif v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            meta[k] = v
    return meta, body

def md_to_html(md):
    lines = md.split("\n")
    out, in_p = [], False
    for line in lines:
        s = line.strip()
        if not s:
            if in_p: out.append("</p>"); in_p = False
            continue
        if s.startswith("## "):
            if in_p: out.append("</p>"); in_p = False
            out.append(f"<h2>{html.escape(s[3:])}</h2>")
        elif s.startswith("# "):
            if in_p: out.append("</p>"); in_p = False
            out.append(f"<h1>{html.escape(s[2:])}</h1>")
        elif s.startswith("---"):
            if in_p: out.append("</p>"); in_p = False
            out.append("<hr>")
        elif s.startswith("👉 "):
            if in_p: out.append("</p>"); in_p = False
            # Extract [text](url)
            m = re.match(r"👉 \[([^\]]+)\]\(([^)]+)\)", s[3:])
            if m:
                out.append(f'<p><a href="{m.group(2)}" style="color:var(--accent);font-weight:600;font-size:18px;">👉 {html.escape(m.group(1))}</a></p>')
            else:
                out.append(f"<p>{s}</p>")
        elif s.startswith("- "):
            if in_p: out.append("</p>"); in_p = False
            content = s[2:]
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            out.append(f"<li>{content}</li>")
        else:
            # inline: **bold** and [text](url)
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
            s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
            if not in_p:
                if out and out[-1].startswith("<li>"):
                    out.append("</ul>")
                out.append("<p>"); in_p = True
            out.append(s + " ")
    if in_p: out.append("</p>")
    return "\n".join(out)

def article_html(meta, body_html, css):
    title = meta.get("title", "Untitled")
    tags = meta.get("tags", [])
    if isinstance(tags, str): tags = [tags]
    tags_html = " ".join(f'<span class="tag">#{t}</span>' for t in tags)
    image = meta.get("image", "")
    hero = f'<img src="{image}" alt="{html.escape(title)}" class="article-hero-img">' if image else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(title)} — CarMotion Daily</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>{css}</style>
</head><body>
<header class="site-header"><div class="header-inner">
<a href="/" class="logo">Car<span class="accent">Motion</span> Daily</a>
<nav class="nav-menu">
<div class="nav-item">Category
<div class="dropdown">
<a href="../index.html">All News</a>
<a href="#">Reviews</a>
<a href="#">Spy Shots</a>
<a href="#">Electric</a>
<a href="#">Classic</a>
<a href="#">Motorsport</a>
</div></div>
<div class="nav-item">Brand
<div class="dropdown">
<a href="#">Ferrari</a><a href="#">Porsche</a><a href="#">Lamborghini</a>
<a href="#">BMW</a><a href="#">Mercedes</a><a href="#">Tesla</a>
</div></div>
<a href="../about.html" class="nav-item">About</a>
</nav></div></header>
<main class="container">
<article class="article">
<header class="article-header">
<div class="kicker">{meta.get('source','')}</div>
<h1>{html.escape(title)}</h1>
<div class="meta-line">{meta.get('date','')[:10]} · Source: {meta.get('source','')} · Curated by CarMotion Daily</div>
</header>
{hero}
<div class="article-body">{body_html}</div>
<div class="tags-row">{tags_html}</div>
</article>
</main>
<footer class="site-footer">
<div class="footer-inner">
<div><h4>CarMotion Daily</h4>
<p style="font-size:13px;color:#b6b8b9;line-height:1.6;">Auto-curated automotive news from 11 major publications.<br>Rewritten, tagged, and published fresh every morning at 8 AM HKT.</p></div>
<div><h4>Categories</h4><a href="#">Reviews</a><a href="#">Spy Shots</a><a href="#">Electric</a><a href="#">Classic</a></div>
<div><h4>Legal</h4><a href="#">About</a><a href="#">Disclaimer</a><a href="#">Contact</a></div>
</div>
<div class="footer-bottom">© 2026 CarMotion Daily · Powered by Hermes Agent · All trademarks belong to their respective owners</div>
</footer>
</body></html>"""

def main():
    css = CSS.read_text()
    OUT.mkdir(exist_ok=True)
    (OUT / "news").mkdir(exist_ok=True)

    all_posts = []
    for p in sorted(POSTS.glob("*.md"), reverse=True):
        meta, body = parse_fm(p.read_text())
        body_html = md_to_html(body)
        slug = p.stem
        out_file = OUT / "news" / f"{slug}.html"
        out_file.write_text(article_html(meta, body_html, css))
        all_posts.append((meta, slug))

    # Build index.html — featured (first) + grid (rest)
    if not all_posts:
        print("No posts found.")
        return 1

    featured_meta, featured_slug = all_posts[0]
    featured_title = html.escape(featured_meta.get("title", ""))
    featured_img = featured_meta.get("image", "")
    featured_excerpt = re.sub(r"<[^>]+>", "", md_to_html(featured_meta.get("description", "")))[:200]
    featured_img_html = f'<img src="{featured_img}" alt="{featured_title}">' if featured_img else ""
    featured_tags = featured_meta.get("tags", [])
    if isinstance(featured_tags, str): featured_tags = [featured_tags]
    featured_kicker = featured_tags[0] if featured_tags else "Breaking"

    cards = []
    for meta, slug in all_posts[1:13]:
        title = html.escape(meta.get("title", ""))
        excerpt = re.sub(r"<[^>]+>", "", md_to_html(meta.get("description", "")))[:120]
        tags = meta.get("tags", [])
        if isinstance(tags, str): tags = [tags]
        kicker = tags[0] if tags else "News"
        img = meta.get("image", "")
        img_html = f'<div class="card-media"><img src="{img}" alt="{title}" loading="lazy"></div>' if img else ""
        cards.append(f"""<article class="news-card">
{img_html}
<div class="card-body">
<div class="kicker">{kicker}</div>
<h3><a href="news/{slug}.html">{title}</a></h3>
<p class="excerpt">{excerpt}</p>
<div class="card-footer"><span>{meta.get('source','')}</span><span>{meta.get('date','')[:10]}</span></div>
</div></article>""")

    archive = []
    for meta, slug in all_posts[13:]:
        archive.append(f'<li><span class="date">{meta.get("date","")[:10]}</span><a href="news/{slug}.html">{html.escape(meta.get("title",""))}</a></li>')

    index_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>CarMotion Daily — Automotive News</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>{css}</style>
</head><body>
<header class="site-header"><div class="header-inner">
<a href="/" class="logo">Car<span class="accent">Motion</span> Daily</a>
<nav class="nav-menu">
<div class="nav-item">Category
<div class="dropdown">
<a href="#">All News</a><a href="#">Reviews</a><a href="#">Spy Shots</a>
<a href="#">Electric</a><a href="#">Classic</a><a href="#">Motorsport</a>
</div></div>
<div class="nav-item">Brand
<div class="dropdown">
<a href="#">Ferrari</a><a href="#">Porsche</a><a href="#">Lamborghini</a>
<a href="#">BMW</a><a href="#">Mercedes</a><a href="#">Tesla</a>
</div></div>
<a href="about.html" class="nav-item">About</a>
</nav></div></header>
<main class="container">
<div class="hero">
<h1>Automotive News, Fresh Daily</h1>
<p class="tagline">Curated from 11 major publications · Rewritten, tagged, and published at 8 AM HKT.</p>
<p class="meta">{datetime.now().strftime("%Y-%m-%d %H:%M")} HKT · {len(all_posts)} articles today</p>
</div>

<div class="featured">
<div class="featured-content">
<div class="kicker">⭐ {featured_kicker}</div>
<h2><a href="news/{featured_slug}.html">{featured_title}</a></h2>
<p class="excerpt">{featured_excerpt}</p>
<div class="meta-line">{featured_meta.get('source','')} · {featured_meta.get('date','')[:10]}</div>
</div>
<div class="featured-media">{featured_img_html}</div>
</div>

<section class="news-grid">
{"".join(cards)}
</section>

<section class="archive-section">
<h3>Archive</h3>
<ul class="archive-list">{"".join(archive)}</ul>
</section>
</main>
<footer class="site-footer">
<div class="footer-inner">
<div><h4>CarMotion Daily</h4>
<p style="font-size:13px;color:#b6b8b9;line-height:1.6;">Auto-curated automotive news from 11 major publications.<br>Rewritten, tagged, and published fresh every morning.</p></div>
<div><h4>Categories</h4><a href="#">Reviews</a><a href="#">Spy Shots</a><a href="#">Electric</a><a href="#">Classic</a></div>
<div><h4>Legal</h4><a href="#">About</a><a href="#">Disclaimer</a><a href="#">Contact</a></div>
</div>
<div class="footer-bottom">© 2026 CarMotion Daily · Powered by Hermes Agent · All trademarks belong to their respective owners</div>
</footer>
</body></html>"""

    (OUT / "index.html").write_text(index_html)
    print(f"✅ Rendered {len(all_posts)} posts → {OUT}")
    print(f"   Open: file://{OUT}/index.html")
    print(f"   HTTP: http://localhost:8888/")

if __name__ == "__main__":
    main()
