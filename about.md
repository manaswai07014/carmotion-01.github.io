---
layout: default
title: About
---

<div class="hero">
  <h1>About CarMotion Daily</h1>
  <p class="tagline">Fresh automotive news, every morning — curated and rewritten by AI.</p>
</div>

<div class="article-body" style="max-width: 720px; margin: 0 auto;">
  <p><strong>CarMotion Daily</strong> is a fully automated automotive news website.</p>

  <p>Every morning at 7:00 AM HKT, our agent fetches headlines from 11 major automotive publications, rewrites them in clean English, tags them by topic, downloads the best available image, and publishes them to this site — all without a human touching anything.</p>

  <h2>Our Sources</h2>
  <p>TopGear, CarAndDriver, RoadandTrack, Autocar, Jalopnik, Evo, MotorTrend, Motor1, Autoblog, InsideEVs, SupercarBlog.</p>

  <h2>How It Works</h2>
  <p>
    🕖 07:00 — <code>daily_news_fetcher.py</code> pulls 20 articles from 11 RSS feeds.<br>
    🕗 08:00 — <code>news_to_website.py</code> parses the brief, infers tags, writes Jekyll-formatted Markdown.<br>
    🕗 08:30 — <code>git push</code> triggers GitHub Pages rebuild.<br>
    🕘 08:45 — Live on this website.
  </p>

  <h2>Built With</h2>
  <p>Jekyll · GitHub Pages · Hermes Agent · Python · Top Gear-inspired black-red theme.</p>

  <h2>What We Are Not</h2>
  <p>We are not a breaking-news site. We are a daily snapshot of the most interesting stories across the major automotive publications, rewritten cleanly without ads, popups, or paginated slideshows.</p>
</div>
