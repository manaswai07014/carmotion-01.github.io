#!/usr/bin/env python3
"""
generate_weekly_roundup.py — L4 Original Content Generator

Reads the past 7 days of _posts/ markdown files, extracts titles + key facts,
and sends them to the LLM to generate a weekly roundup article.

Output: website/_posts/YYYY-MM-DD-this-week-in-cars.md
        (layout: news-item, tag: Original, original: true)

Usage:
    python3 scripts/generate_weekly_roundup.py
    python3 scripts/generate_weekly_roundup.py --dry-run
    python3 scripts/generate_weekly_roundup.py --days 7

Run via cron: every Tuesday 09:00 HKT (after daily posts)
"""

import os, re, sys, json, argparse, datetime, yaml
from pathlib import Path
from collections import defaultdict

BASE = Path(os.path.expanduser("~/car-evolution-project"))
POSTS = BASE / "website" / "_posts"
OUT_POSTS = BASE / "website" / "_posts"

# Reuse the LLM config loader from news_to_website.py
sys.path.insert(0, str(BASE / "scripts"))
try:
    from news_to_website import _load_llm_config, slugify
    LLM_OK = True
except Exception as e:
    print(f"[WARN] Could not import from news_to_website: {e}")
    LLM_OK = False


def get_recent_posts(days: int = 7) -> list:
    """
    Return list of post dicts from the past `days` days.
    Each dict: {title, date, source, tags, description, body, url}
    """
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    posts = []

    if not POSTS.exists():
        return posts

    for f in sorted(POSTS.iterdir(), reverse=True):
        if not f.name.endswith(".md"):
            continue
        date_part = f.name[:10]
        try:
            post_date = datetime.date.fromisoformat(date_part)
        except ValueError:
            continue
        if post_date < cutoff:
            continue

        content = f.read_text(encoding="utf-8")

        # Parse front matter
        fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not fm_match:
            continue
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except Exception:
            fm = {}
        body = fm_match.group(2)

        posts.append({
            "title": fm.get("title", ""),
            "date": post_date,
            "source": fm.get("source", ""),
            "tags": fm.get("tags", []),
            "description": fm.get("description", ""),
            "body": body,
            "url": f"/news/{post_date.strftime('%Y/%m/%d')}/{slugify(fm.get('title', ''))}/",
        })

    return posts


def extract_key_facts(posts: list) -> list:
    """
    Extract key facts from each post: title + description + first sentence of Why It Matters.
    Return a list of formatted strings for the LLM prompt.
    """
    facts = []
    for p in posts:
        # Extract Why It Matters section
        wim_match = re.search(r"## Why It Matters\s*\n+(.*?)(?=\n## |\Z)", p["body"], re.DOTALL)
        wim = ""
        if wim_match:
            wim = re.sub(r"\*+|#+|`+", "", wim_match.group(1).strip())
            wim = re.sub(r"\s+", " ", wim).strip()
            if len(wim) > 200:
                wim = wim[:200] + "..."

        entry = f"- [{p['date'].strftime('%a %b %d')}] {p['title']}"
        if p.get("description"):
            entry += f"\n  Summary: {p['description'][:150]}"
        if wim:
            entry += f"\n  Why it matters: {wim}"
        facts.append(entry)

    return facts


def generate_roundup(posts: list) -> str:
    """
    Send the week's post summaries to the LLM and generate a roundup article.
    Returns the markdown content (## The Story / ## Why It Matters / ## Take).
    """
    cfg = _load_llm_config() if LLM_OK else None
    if not cfg:
        return generate_roundup_fallback(posts)

    facts = extract_key_facts(posts)
    facts_text = "\n".join(facts)

    system_prompt = (
        "You are a clean, professional automotive news editor for CarMotion Daily. "
        "Write a weekly roundup article synthesizing the week's top car news stories. "
        "The roundup should have editorial value — not just a list, but a narrative "
        "with connecting themes and forward-looking commentary.\n\n"
        "Structure:\n"
        "## The Story\nGive a 3-4 sentence overview of the week's big themes.\n\n"
        "## This Week's Top 5\nList 5 key stories with 1-2 sentences each (not verbatim from source).\n\n"
        "## Why It Matters\n2-3 sentences on the bigger picture trends.\n\n"
        "## CarMotion Daily's Take\n2-3 sentences of editorial opinion on what to watch next week.\n\n"
        "Rules:\n"
        "1. DO NOT copy sentences verbatim from the source.\n"
        "2. Keep numbers/brands/medel names exactly as given.\n"
        "3. Output Markdown only — no preamble, no code fences.\n"
        "4. Under 500 words total."
    )

    user_prompt = (
        f"Here are the car news stories from the past 7 days at CarMotion Daily:\n\n"
        f"{facts_text}\n\n"
        f"Write a weekly roundup article following the system instructions. "
        f"Start with '## The Story' immediately."
    )

    provider_type = cfg.get("provider_type", "openai")
    try:
        text = ""
        if provider_type == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"])
            resp = client.messages.create(
                model=cfg["model"],
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.6,
            )
            for block in resp.content:
                if hasattr(block, "text"):
                    text += block.text
        else:
            from openai import OpenAI
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
            resp = client.chat.completions.create(
                model=cfg["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=1200,
            )
            text = resp.choices[0].message.content or ""

        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        if "## The Story" not in text:
            print("[LLM] output missing required sections — using fallback")
            return generate_roundup_fallback(posts)

        print(f"[LLM] + roundup generated ({len(text)} chars) [{cfg['model']}]")
        return text.strip() + "\n"

    except Exception as e:
        print(f"[LLM] failed: {e} — using fallback")
        return generate_roundup_fallback(posts)


def generate_roundup_fallback(posts: list) -> str:
    """
    Fallback roundup without LLM — just format the posts into a markdown list.
    """
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)

    lines = [
        "## The Story\n",
        f"This week at CarMotion Daily covered {len(posts)} stories. Here are the highlights.\n",
        "\n## This Week's Top Stories\n",
    ]

    for i, p in enumerate(posts[:10], 1):
        lines.append(f"{i}. **{p['title']}** — {p.get('description', 'No summary available.')[:150]}")
    lines.append("")
    lines.append("\n## Why It Matters\n")
    lines.append(f"These {len(posts)} stories span electric vehicles, new model reveals, spy shots, and industry moves — ")
    lines.append("a snapshot of the automotive world this week.\n")
    lines.append("\n## CarMotion Daily's Take\n")
    lines.append("Watch for next week's reveals and whether this week's trends continue.")
    lines.append(" New stories drop daily at 08:00 HKT.\n")

    return "\n".join(lines) + "\n"


def render_roundup_post(posts: list, date_str: str, dry_run: bool = False) -> Path:
    """Generate the full Jekyll markdown file and write it."""
    body = generate_roundup(posts)

    # Determine main theme from most common tag
    tag_counts = defaultdict(int)
    for p in posts:
        for t in p.get("tags", []):
            tag_counts[t] += 1
    top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])[:3]]

    # Extract description from body
    desc_match = re.search(r"## Why It Matters\s*\n+(.*?)(?=\n## |\Z)", body, re.DOTALL)
    desc = ""
    if desc_match:
        desc = re.sub(r"\*+|#+|`+", "", desc_match.group(1).strip())
        desc = re.sub(r"\s+", " ", desc).strip()[:157]
    if not desc:
        desc = f"CarMotion Daily weekly roundup: {len(posts)} top car news stories this week."

    date_obj = datetime.date.fromisoformat(date_str)
    title = f"This Week in Cars: {date_obj.strftime('%B %d, %Y')} Roundup"
    slug = slugify(title)

    front_matter = f"""---
layout: news-item
title: "{title.replace('"', "'")}"
description: "{desc.replace('"', "'").replace(chr(10), ' ')}"
date: {date_str} 09:00 +0800
source: CarMotion Daily
source_url: ""
original: true
tags: [{', '.join(top_tags + ['Original'])}]
---

"""

    full = front_matter + body

    out_path = OUT_POSTS / f"{date_str}-{slug}.md"
    if dry_run:
        print(f"  [DRY RUN] would write {out_path}")
        print(f"  Title: {title}")
        print(f"  Tags: {', '.join(top_tags + ['Original'])}")
        print(f"  Description: {desc}")
        print(f"  Body length: {len(body)} chars")
    else:
        out_path.write_text(full, encoding="utf-8")
        print(f"  ✓ wrote {out_path.name}")

    return out_path


def main():
    ap = argparse.ArgumentParser(description="Generate weekly roundup article")
    ap.add_argument("--date", help="YYYY-MM-DD; defaults to today", default=None)
    ap.add_argument("--days", type=int, default=7, help="How many days to look back (default: 7)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write any files")
    args = ap.parse_args()

    date_str = args.date or datetime.date.today().isoformat()

    print(f"📰 generate_weekly_roundup.py — {date_str}")
    print(f"   Looking back {args.days} days\n")

    posts = get_recent_posts(days=args.days)
    if not posts:
        print("[ERR] No posts found in the past {args.days} days.")
        sys.exit(1)

    print(f"Found {len(posts)} posts from the past {args.days} days:")
    for p in posts:
        print(f"  • [{p['date'].strftime('%a %b %d')}] {p['title'][:70]}")
    print()

    render_roundup_post(posts, date_str, dry_run=args.dry_run)
    print("\n✓ Done.")


if __name__ == "__main__":
    main()
