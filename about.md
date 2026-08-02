---
layout: default
title: About
---

<div class="hero">
  <h1>About CarMotion Daily</h1>
  <p class="tagline">Fresh automotive news, every morning — curated, rewritten, and published with editorial oversight.</p>
</div>

<div class="article-body" style="max-width: 720px; margin: 0 auto;">
  <p><strong>CarMotion Daily</strong> is an automated automotive news website that curates and rewrites the most interesting stories from major publications every morning.</p>

  <p>Every morning at 08:00 HKT, our pipeline fetches headlines from 11 major automotive publications, rewrites them in clean English using a large language model, tags them by topic, downloads the best available image, and publishes them to this site.</p>

  <h2>Editorial Team</h2>
  <p>
    CarMotion Daily is maintained by the <strong>CarMotion Editorial Team</strong>.
    While the daily pipeline runs automatically, the team provides editorial
    oversight, reviews content quality, handles corrections, and publishes
    original analysis pieces weekly. The team can be reached via our
    <a href="/contact.html">contact page</a>.
  </p>

  <h2>Our Sources</h2>
  <p>TopGear, CarAndDriver, Road & Track, Autocar, Jalopnik, evo, MotorTrend, Motor1, Autoblog, InsideEVs, SupercarBlog.</p>

  <h2>How It Works</h2>
  <p>
    🕗 08:00 — <code>daily_news_fetcher.py</code> pulls RSS feeds from 11 publications.<br>
    🕗 08:15 — <code>news_to_website.py</code> rewrites articles using an LLM, infers tags, downloads images.<br>
    🕗 08:30 — <code>git push</code> triggers Cloudflare Pages rebuild.<br>
    🕘 08:45 — Live on this website.
  </p>

  <h2>Built With</h2>
  <p>Jekyll · Cloudflare Pages · Hermes Agent · Python · MiniMax-M2 LLM · Top Gear-inspired dark theme.</p>

  <h2>What We Are Not</h2>
  <p>We are not a breaking-news site. We are a daily snapshot of the most interesting stories across the major automotive publications, rewritten cleanly without ads, popups, or paginated slideshows. We do not claim to be the original source of any news story.</p>

  <h2>Policies</h2>
  <ul>
    <li><a href="/ai-disclosure.html">AI & Automation Disclosure</a> — How we use AI to curate and rewrite news</li>
    <li><a href="/editorial-policy.html">Editorial Policy</a> — Our standards for content selection and rewriting</li>
    <li><a href="/corrections-policy.html">Corrections Policy</a> — How to report errors and our correction process</li>
    <li><a href="/disclaimer.html">Disclaimer</a></li>
    <li><a href="/contact.html">Contact Us</a></li>
  </ul>
</div>
