# 🚗 CarMotion Daily — Automotive News Auto-Publishing Website

## 架構總覽

```
每日 08:00 HKT (Hermes cron)
   ↓
[existing cron] daily_news_fetcher.py → RSS fetch
   ↓ 產出 agent-meta/daily-brief.md (20條新聞)
   ↓
[existing cron] run_daily_pipeline.py  ← 一鍵 chain
   ├─ Step 1: daily_news_fetcher.py
   ├─ Step 2: news_to_website.py
   │    ├─ 讀取 daily-brief.md
   │    ├─ **Dedup pass**: scan 最近 7 日 _posts/ slug，skip 重複文章
   │    ├─ 每篇新聞：
   │    │    ├─ Decode Google News URL → fetch 真實 article body
   │    │    ├─ Extract 真實圖片 (og:image + article body images)
   │    │    ├─ **Hybrid Rewrite Engine** (Phase 1 v4):
   │    │    │    ├─ Step A: LLM rephrase (MiniMax-M2 via Anthropic SDK)
   │    │    │    │           — prompt 嚴格規定唔准 verbatim / 唔准 invent
   │    │    │    └─ Step B: regex fallback (if LLM fail)
   │    │    │                — _restate() / _merge_short_sentences()
   │    │    │                — _derive_why_it_matters() / _derive_take()
   │    │    └─ 生成 Markdown 格式文章 (全英文)
   │    └─ Git commit + push (main → gh-pages subtree)
   ↓
https://carmotion-daily.pages.dev  (Cloudflare Pages hosting)
```

## 技術 Stack

- **Static Site Generator**: Jekyll 4.3 + GitHub Pages + Cloudflare Pages
- **內容格式**: Markdown (front-matter + body), 全英文
- **改寫引擎**: Hybrid — MiniMax-M2 LLM (via Anthropic-compatible API) + regex fallback
- **圖片**: 真實 article images (og:image + body images), Wikipedia Commons fallback
- **Dedup**: 7-day rolling window, filename slug 比對
- **部署**: git push → GitHub Pages 自動建站 + Cloudflare Pages CDN

## news_to_website.py v4 — Hybrid Rewrite Pipeline

### 核心改動 (Phase 1, 2026-07-30)

#### 1. Dedup Logic
- `load_recent_slugs()` 掃描 `_posts/` 目錄
- 7-day rolling window，用 filename slug（唔計日期）做 unique key
- main() 入面 skip 重複 entries，queue 新嘢最多 5 篇/日

#### 2. Hybrid Rewrite Engine (LLM + Regex fallback)
- **Step A — LLM rephrase**（preferred）:
  - `_llm_rephrase()` 經 MiniMax CN API (Anthropic-compatible) call MiniMax-M2
  - `_load_llm_config()` 自動 detect provider: MiniMax CN 優先，NVIDIA fallback
  - System prompt 嚴格規定: 唔准 verbatim copy / 唔准 invent facts / keep 數字 unchanged
  - 每篇文章 1 次 LLM call，5 篇/日 = 5 calls
  - Fallback to regex engine if API fail
- **Step B — Regex fallback**:
  - `_restate()` — strip "According to...", "The company said...", "The Ferrari..." → "Ferrari..."
  - `_merge_short_sentences()` — 合併短句成段落，不再散亂
  - `_derive_why_it_matters()` — 搵 body 入面 consequence-cue words 嘅句子
  - `_derive_take()` — per-article editorial judgment, 唔再套模板
  - 移除舊版 `_CONNECTORS` 機械拼接 ("In other words,", "That is —", ...)

#### 3. CLI Flags
- `--no-llm` — 停用 LLM rephrase，淨用 regex engine
- `--dry-run` — 預覽唔寫檔
- `--date YYYY-MM-DD` — backfill 指定日期

### 已解決嘅 v1 問題
| v1 問題 | v4 解法 |
|---|---|
| 重複發文（日日同一篇） | 7-day dedup check |
| `ramRam` 品牌名大細楷混亂 | `_restate()` 正確處理品牌名 |
| 機械式 "In other words," 拼接 | 移除 `_CONNECTORS`，改用 LLM or context-aware restate |
| 模板式 "Why It Matters" | `_derive_why_it_matters()` 搵 body cue words |
| 死板 "60 days playbook" Take | `_derive_take()` or LLM 真 editorial judgment |
| 每篇 80% 重複 filler | LLM rephrase 每篇獨立生成，基於真實 article body |

## 惠惠日常工作流程（自動化 cron）

### 每日 08:00 HKT — Full Pipeline
`run_daily_pipeline.py` 一鍵執行:
1. `daily_news_fetcher.py` → 11 個 RSS feeds → `daily-brief.md` (20條)
2. `news_to_website.py` →
   - Dedup check (skip 最近 7 日重複)
   - 5 篇新文章：
     - Fetch real article body (gnews URL decode + body fetcher)
     - Extract real images (og:image + article images)
     - LLM rephrase (MiniMax-M2) 或 regex fallback
     - Generate Jekyll markdown post
3. `git commit + push` → main branch + gh-pages subtree rebuild

### 每日 08:30 HKT — 網頁上線
讀者即刻睇到: `https://carmotion-daily.pages.dev`

## Pipeline 構件

| Script | 功能 |
|---|---|
| `daily_news_fetcher.py` | 11 個 RSS feeds → daily-brief.md (20條) |
| `news_to_website.py` | brief → website posts (dedup + hybrid rewrite + images) |
| `news_image_extractor.py` | Google News URL → original article → og:image + body images |
| `gnews_url_decoder.py` | Google News redirect URL → real article URL |
| `article_body_fetcher.py` | Real article URL → paragraphs + lede |
| `auto_image_downloader.py` | Wikipedia Commons fallback image search |
| `run_daily_pipeline.py` | 一鍵 chain: fetch → rewrite → git push |

## LLM Provider 配置

`_load_llm_config()` 自動 detect provider:

### Priority 1: MiniMax CN (Anthropic-compatible)
- 讀 `~/.hermes/.env` 的 `MINIMAX_CN_API_KEY` + `MINIMAX_CN_BASE_URL`
- Model: `MiniMax-M2`
- Base URL: `https://api.minimaxi.com/anthropic`
- SDK: `anthropic` (Anthropic SDK v0.87+)

### Priority 2: NVIDIA (OpenAI-compatible, fallback)
- 讀 `~/.hermes/config.yaml` 的 `providers.nvidia`
- ⚠️ 2026-07-30 測試: API key 返回 403 Forbidden，需要更新

### 安全原則
- API key 只喺 script process 內，唔會 log 出嚟
- LLM call timeout 預設 60s/篇，5 篇 = 最多 300s
- 如果 LLM call fail → 自動 fallback 去 regex engine（唔會 block pipeline）

## 我已經有嘅資產

✅ `daily_news_fetcher.py` — 11個 RSS feeds 已 tune 好
✅ `news_to_website.py` v4 — Hybrid rewrite (LLM + regex fallback) + dedup
✅ `auto_image_downloader.py` — Wikipedia fallback image search
✅ `news_image_extractor.py` — Real article og:image + body image extraction
✅ `gnews_url_decoder.py` + `article_body_fetcher.py` — Google News URL + body fetch
✅ Jekyll website — Top Gear 紅黑風、mobile-first CSS
✅ Hermes telegram cron job 機制
✅ Cloudflare Pages hosting (carmotion-daily.pages.dev)

## 已知限制 / 下一步

| 項目 | 狀態 |
|---|---|
| NVIDIA API key 過期 (403) | MiniMax CN 已作為 primary provider |
| Category pages (reviews, electric, etc.) | 連結存在但頁面未 build — Phase 2 |
| Brand pages (Ferrari, Porsche, etc.) | 連結存在但頁面未 build — Phase 2 |
| Pagination | 首頁只 show 12，Archive 20，無分頁 — Phase 2 |
| About / Disclaimer / Contact | 空殼頁 — Phase 2 |
| SEO meta optimization | jekyll-seo-tag 自動，無手動優化 — Phase 3 |
| Sitemap + RSS feed | jekyll-sitemap 已裝，未確認 generate — Phase 3 |
| Health check cron | 每日 smoke test 未 set — Phase 3 |
| Client-side search | 未做 — Phase 3 |
