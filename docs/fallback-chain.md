# 📋 Fallback Chain — car-evolution-project
## 數據源 fallback 優先順序（當前狀態）

---

## 1. Google Trends Data

| Step | Source | Condition | Status |
|------|--------|-----------|--------|
| 1 | `pytrends` (Google Trends API) | Module installed + quota available | ❌ Module missing |
| 2 | **Google News RSS** (site:news.google.com) | Always available | ✅ ACTIVE |
| 3 | Cached `trend-report.md` | File exists | ✅ Last resort |

**Script:** `trend_monitor_v2.py`
**Output:** `agent-meta/trend-report.md`

**Note:** Google News RSS gives article mention counts, not true search volume.
Scores normalized to 0-100. Treat relative ranking as directional only.

---

## 2. Daily News (RSS Feeds)

| Step | Source | Condition | Status |
|------|--------|-----------|--------|
| 1 | Direct RSS fetch | Network OK + feed alive | ✅ Primary |
| 2 | Retry 3x with 15s timeout | Transient network error | ✅ Retry logic |
| 3 | Skip failed feed, continue others | Persistent error | ✅ Partial report |
| 4 | Skip entire brief if ALL feeds fail | All 10 feeds down | ⚠️ Requires manual check |

**Script:** `daily_news_fetcher.py`
**Output:** `agent-meta/daily-brief.md`
**Feeds:** TopGear, CarAndDriver, RoadandTrack, Autocar, Jalopnik, Evo-GN, Motor1, Autoblog, InsideEVs, SupercarBlog

---

## 3. YouTube Competitor Data

| Step | Source | Condition | Status |
|------|--------|-----------|--------|
| 1 | YouTube Data API v3 | API key valid + quota available | ⚠️ Quota exhausted |
| 2 | `competitor-cache.json` | Cache exists + <48h old | ✅ Fallback active |
| 3 | Old cached report | Cache missing or >48h | ❌ No data |

**Script:** `daily_competitor_report_v2.py`
**Output:** `exports/competitor/latest-report.md`
**Cache:** `agent-meta/competitor-cache.json`
**Quota:** 10,000 units/day (resets HK midnight)

**Quota recovery:** HK midnight (00:00 HKT) daily reset.

---

## 4. Topic Priority Scoring

| Component | Source | Fallback |
|-----------|--------|----------|
| Trend Score | `trend-report.md` (via `topic_priority_v2.py`) | Google News RSS fallback |
| YouTube Search Volume | YouTube Data API v3 | Score = 0 if API fails |
| News Score | `daily-brief.md` | Score = 0 if brief missing |
| Blue Ocean Score | Competitor gaps analysis | Static scoring if report missing |

**Script:** `topic_priority_v2.py`
**Output:** `agent-meta/topic-priority-report.md`

---

## 5. System Health Monitoring

| Check | Tool | Frequency | Alert |
|-------|------|-----------|-------|
| Data file freshness | `system_health_check.py` | Every hour | Telegram if CRITICAL |
| YouTube API quota | `api_quota_monitor.py` | Daily (manual) | N/A |
| All scripts | `test_regex_parsing.py` | Daily noon smoke test | Telegram if fails |

**Health check threshold:**
- `daily-brief.md`: WARN if >14h old, CRITICAL if >38h old
- `trend-report.md`: WARN if >14h old, CRITICAL if >38h old
- `competitor-analysis`: WARN if >30h old, CRITICAL if >78h old
- `topic-priority-report.md`: WARN if >16h old, CRITICAL if >40h old

---

## Known Issues

1. **YouTube API quota exhausted (May 5):** Competitor reports use cached data. Quota resets HK midnight.
2. **Google News RSS (trend fallback):** Produces normalized scores (all 100 or near-100) — not true relative volume. Use only for directional trending.
3. **pytrends module missing:** Not installable via pip in WSL environment. Google News RSS is permanent fallback.

---

## How to Check System Status

```bash
# Quick health check
python3 scripts/system_health_check.py

# YouTube quota status
python3 scripts/api_quota_monitor.py

# Run unit tests
python3 scripts/test_regex_parsing.py

# Full smoke test
python3 scripts/daily_smoke_test.py
```
