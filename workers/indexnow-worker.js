/**
 * CarMotion Daily — IndexNow Worker
 * 
 * Runs via Cloudflare Worker Cron Trigger at 0 0 * * * (00:00 UTC = 08:00 HKT)
 * Fetches the latest sitemap URLs from carmotion-daily.pages.dev
 * and POSTs them to IndexNow for instant Bing/Yandex indexing.
 * 
 * Setup:
 * 1. Go to Cloudflare Dashboard → Workers & Pages → Create Worker
 * 2. Paste this code as the Worker
 * 3. Add Cron Trigger: 0 0 * * *
 * 4. The KEY.txt file at site root must match the key below
 */

const INDEXNOW_KEY = "ZbwATA4xOiSKlX0bsYodfQ4k0hn58kZHRzh-BvjHpzI";
const SITEMAP_URL = "https://carmotion-daily.pages.dev/sitemap.xml";
const INDEXNOW_API = "https://api.indexnow.org/IndexNow";
const SITE = "carmotion-daily.pages.dev";

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(this.submitUrls());
  },

  async fetch(request, env, ctx) {
    // Manual trigger via HTTP
    const result = await this.submitUrls();
    return new Response(JSON.stringify(result, null, 2), {
      headers: { "Content-Type": "application/json" },
    });
  },

  async submitUrls() {
    // 1. Fetch sitemap
    const resp = await fetch(SITEMAP_URL);
    if (!resp.ok) {
      return { error: `Failed to fetch sitemap: ${resp.status}`, urlsSubmitted: 0 };
    }
    const xml = await resp.text();

    // 2. Extract URLs from <loc> tags
    const urls = [];
    const locRegex = /<loc>(.*?)<\/loc>/g;
    let match;
    while ((match = locRegex.exec(xml)) !== null) {
      urls.push(match[1].trim());
    }

    if (urls.length === 0) {
      return { error: "No URLs found in sitemap", urlsSubmitted: 0 };
    }

    // 3. Submit to IndexNow (batch of up to 10,000 URLs)
    const payload = {
      host: SITE,
      key: INDEXNOW_KEY,
      keyLocation: `https://${SITE}/KEY.txt`,
      urlList: urls,
    };

    const indexNowResp = await fetch(INDEXNOW_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    return {
      status: indexNowResp.status,
      statusText: indexNowResp.statusText,
      urlsSubmitted: urls.length,
      firstUrl: urls[0],
      lastUrl: urls[urls.length - 1],
      timestamp: new Date().toISOString(),
    };
  },
};
