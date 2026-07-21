# 🚗 CarMotion Daily — 汽車新聞自動更新網站

## 架構總覽

```
每日 7:00AM HKT
   ↓
[existing cron] daily_news_fetcher.py
   ↓ 產出 agent-meta/daily-brief.md (20條新聞)
   ↓
[new cron] news_to_website.py  ← 惠惠自動處理
   ├─ 讀取 daily-brief.md
   ├─ 淨化內容（去廣告/補中文摘要）
   ├─ 下載文章圖片（已有 auto_image_downloader.py）
   ├─ 改寫標題 + 口語化廣東話摘要（惠惠 LLM）
   ├─ 生成 Markdown 格式文章
   ├─ 更新 index.json
   └─ 寫入 website/content/news/YYYY-MM-DD.md
   
[new cron] 30min 後
   ↓
git push → GitHub Pages 自動建站
   ↓
https://carmotion-01.github.io （示例 URL）
```

## 技術 Stack

- **Static Site Generator**: Jekyll + GitHub Pages
- **內容格式**: Markdown (front-matter + body)
- **圖片**: 下載後放 `website/static/images/news/YYYY-MM-DD/`
- **部署**: git push 自動經 GitHub Pages -> 免費托管
- **Domain**: 可以駁 carmotion.com（老闆有 domain 的話）

## 惠惠日常工作流程（自動化）

### 每日 07:00 HKT — 新聞採集（現有）
`daily_news_fetcher.py` → DB + daily-brief.md

### 每日 08:00 HKT — 網頁生成（新增）
Hermes 自動 cron job:
1. 讀 `agent-meta/daily-brief.md`
2. 對每篇新聞：
   - 補通順廣東話口語化摘要（唔係機械翻譯）
   - 改寫標題（吸引點擊，唔標題黨）
   - 提取重點關鍵字做 tags
3. 叫 `auto_image_downloader.py` 搵圖
4. 生成每篇 1 個 MD 檔：
   ```
   website/content/news/2026-07-19-ferrari-849-testarossa.md
   ```
5. 更新首頁 `index.json` + RSS feed
6. git commit + push → GitHub Pages 自動建站

### 每日 08:30 HKT — 網頁上線
老闆同讀者即刻睇到： https://carmotion-01.github.io

## 我幫老闆修改新聞做咩？

1. **口語化標題** — 本來 "Ferrari 849 Testarossa Spider – pictures" 變做 "🏎️ Ferrari Testarossa Spider 罕有原型車曝光"
2. **廣東話摘要** — 將英文/機翻華文變做自然香港口語
3. **補背景知識** — 加返些「上年 Ferrari 出過咩版本」嘅 context
4. **揀靚圖** — auto_image_downloader 比起 Google 圖片搜尋搵最靚嗰張
5. **SEO meta** — meta description、keywords、Open Graph
6. **分類 tagging** —跑车/电动车/SUV/赛车... 讓讀者可以 filter

## 建站步驟（老闆 confirm 一聲我就做）

### Step 1: 建立網站骨架
- 寫 Jekyll config + layout
- 首4個模板：首頁 / 新聞列表 / 新聞文 / 關於
- Tailwind CSS 風格（黑紅跑車感）

### Step 2: 創建 GitHub repo
- 用 `gh repo create carmotion-01/carmotion-01.github.io --public`
- Set GitHub Pages → main branch /root

### Step 3: 新增 Hermes cron job
- 08:00 HKT 每日跑 news_to_website.py
- 08:30 HKT 自動 git push
- log 落 agent-meta/web-log.jsonl

### Step 4: 首次 launch
- 生成第一日新聞網頁
- 自動上架第一篇新聞  
- 俾老闆過目 + revise

## 我已經有嘅資產

✅ `daily_news_fetcher.py` — 11個 RSS feeds 已 tune 好
✅ `auto_image_downloader.py` — 自動搵圖已有
✅ `daily-brief.md` 既有格式
✅ Hermes telegram cron job 機制熟悉
✅ Canada Telegram group 有 8726708023 chat_id

## 需要老闆決定嘅嘢

1. **Domain** — 用 GitHub Pages 免費 subdomain 定你自己買 domain？
2. **語言** — 全廣東話定中英對照？
3. **廣告/Monetization** — 加 AdSense？定先純 content？
4. **歷史新聞** — 要唔要 backfill 之前幾個月新聞？
5. **版面風格** — 想似 Top Gear 紅黑風、Jalopnik 報紙感、定你 литə.ru 有自己想法?
