#!/usr/bin/env python3
"""
YouTube Competitor Tracker - Iris Edition v3
=============================================
Comprehensive competitor tracking with full Shorts coverage.

Features:
- Uses YouTube Search API (not uploads playlist) to get ALL shorts
- Pagination to get up to 200 shorts per channel
- Separate Shorts vs Regular videos
- Complete posting time analysis (HKT + EST/PST)
- TOP 10 + LATEST 10 shorts per channel
- Daily snapshots + historical tracking

Usage:
    python3 scripts/competitor-tracker.py              # Fetch + Report
    python3 scripts/competitor-tracker.py --report    # Report only
    python3 scripts/competitor-tracker.py --history   # 7-day trend

Environment:
    GOOGLE_API_KEY - YouTube Data API v3 key
"""

import os
import sys
import json
import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration
API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM")
COMPETITORS_DIR = PROJECT_ROOT / "data" / "competitors"
DATA_DIR = PROJECT_ROOT / "data"

# Timezones
HKT = timezone(timedelta(hours=8))
EST = timezone(timedelta(hours=-5))
PST = timezone(timedelta(hours=-8))

# Target channels
TARGET_CHANNELS = [
    {"id": "kizzombie", "handle": "@kizzombie", "name": "ArtKiz", "channel_id": "UC2IRZdo5HP4IjzuAjlsLjOg"},
    {"id": "motomorfosis", "handle": "@motomorfosis", "name": "Motomorfosis", "channel_id": "UCs3HXNAJ27auPVGuhKJyWAw"},
]


def parse_duration(duration):
    """Parse ISO 8601 duration to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        return h * 3600 + m * 60 + s
    return 999


def duration_str(duration):
    """Format ISO 8601 duration to human readable."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        if h: return f"{h}h {m}m {s}s"
        if m: return f"{m}m {s}s"
        return f"{s}s"
    return "N/A"


def get_channel_info(youtube, channel_id):
    """Get channel details using channel ID."""
    try:
        response = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id
        ).execute()
    except HttpError as e:
        print(f"  [ERROR] channels.list failed: {e}")
        return None
    
    items = response.get("items", [])
    if not items:
        print(f"  [ERROR] No channel found with ID: {channel_id}")
        return None
    
    ch = items[0]
    return {
        "channel_id": ch["id"],
        "title": ch["snippet"]["title"],
        "description": ch["snippet"]["description"][:500],
        "subscriber_count": int(ch["statistics"].get("subscriberCount", 0)),
        "total_views": int(ch["statistics"].get("viewCount", 0)),
        "video_count": int(ch["statistics"].get("videoCount", 0)),
        "uploads_playlist_id": ch["contentDetails"]["relatedPlaylists"]["uploads"],
        "thumbnails": ch["snippet"].get("thumbnails", {}).get("high", {}).get("url", ""),
        "published_at": ch["snippet"].get("publishedAt", ""),
        "fetched_at": datetime.now(HKT).isoformat(),
    }


def get_all_shorts_from_channel(youtube, channel_id, max_shorts=200):
    """Get all shorts from a channel using Search API with pagination."""
    all_shorts = []
    next_token = None
    total_fetched = 0
    
    while total_fetched < max_shorts:
        try:
            params = {
                "part": "snippet,id",
                "channelId": channel_id,
                "maxResults": min(50, max_shorts - total_fetched),
                "type": "video",
                "videoDuration": "short",
                "order": "date"
            }
            if next_token:
                params["pageToken"] = next_token
            
            response = youtube.search().list(**params).execute()
            items = response.get("items", [])
            
            if not items:
                break
            
            all_shorts.extend(items)
            total_fetched += len(items)
            next_token = response.get("nextPageToken")
            
            if not next_token:
                break
                
        except HttpError as e:
            print(f"  [ERROR] Search API error: {e}")
            break
    
    return all_shorts


def get_shorts_from_uploads_fallback(youtube, uploads_playlist_id, max_results=50):
    """Fallback: Get shorts from uploads playlist (for channels where search API returns 0)."""
    shorts = []
    
    try:
        response = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        ).execute()
        
        items = response.get("items", [])
        video_ids = [item["contentDetails"]["videoId"] for item in items]
        
        # Get durations
        durations = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            try:
                stats = youtube.videos().list(
                    part="contentDetails",
                    id=",".join(batch)
                ).execute()
                for item in stats.get("items", []):
                    durations[item["id"]] = item["contentDetails"].get("duration", "PT0S")
            except HttpError:
                pass
        
        for item in items:
            vid_id = item["contentDetails"]["videoId"]
            duration = durations.get(vid_id, "PT0S")
            if parse_duration(duration) < 60:
                shorts.append(item)
                
    except HttpError as e:
        print(f"  [ERROR] Playlist API error: {e}")
    
    return shorts


def get_video_details(youtube, video_ids):
    """Get detailed stats for a list of video IDs."""
    all_stats = {}
    
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            response = youtube.videos().list(
                part="statistics,contentDetails,snippet",
                id=",".join(batch)
            ).execute()
            
            for item in response.get("items", []):
                all_stats[item["id"]] = item
        except HttpError as e:
            print(f"  [ERROR] Video stats error: {e}")
    
    return all_stats


def build_shorts_data(shorts_items, stats_map):
    """Build structured shorts data from raw API response."""
    shorts_data = []
    
    for s in shorts_items:
        vid_id = s["id"]["videoId"]
        stats = stats_map.get(vid_id, {})
        snippet = s["snippet"]
        
        published = snippet.get("publishedAt", "")
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        dt_hkt = dt.astimezone(HKT)
        dt_est = dt.astimezone(EST)
        
        duration = "PT0S"
        view_count = 0
        like_count = 0
        comment_count = 0
        
        if stats:
            duration = stats["contentDetails"].get("duration", "PT0S")
            view_count = int(stats["statistics"].get("viewCount", 0))
            like_count = int(stats["statistics"].get("likeCount", 0))
            comment_count = int(stats["statistics"].get("commentCount", 0))
        
        shorts_data.append({
            "video_id": vid_id,
            "title": snippet["title"],
            "description": snippet.get("description", "")[:200],
            "published_at_utc": published,
            "published_at_hkt": dt_hkt.strftime("%Y-%m-%d %H:%M:%S"),
            "published_at_est": dt_est.strftime("%Y-%m-%d %H:%M:%S"),
            "published_day": dt_hkt.strftime("%A"),
            "published_hour_hkt": dt_hkt.hour,
            "published_hour_est": dt_est.hour,
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "duration": duration,
            "duration_sec": parse_duration(duration),
            "duration_str": duration_str(duration),
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "is_short": parse_duration(duration) < 60,
            "fetched_at": datetime.now(HKT).isoformat(),
        })
    
    return shorts_data


def analyze_posting_pattern(videos, label=""):
    """Analyze posting patterns for a list of videos."""
    if not videos:
        return {}
    
    days_count = {}
    hours_hkt_count = {}
    hours_est_count = {}
    
    for v in videos:
        days_count[v["published_day"]] = days_count.get(v["published_day"], 0) + 1
        hours_hkt_count[v["published_hour_hkt"]] = hours_hkt_count.get(v["published_hour_hkt"], 0) + 1
        hours_est_count[v["published_hour_est"]] = hours_est_count.get(v["published_hour_est"], 0) + 1
    
    return {
        "label": label,
        "total": len(videos),
        "best_days": [(d, c) for d, c in sorted(days_count.items(), key=lambda x: -x[1])[:3]],
        "best_hours_hkt": [(h, c) for h, c in sorted(hours_hkt_count.items(), key=lambda x: -x[1])[:5]],
        "best_hours_est": [(h, c) for h, c in sorted(hours_est_count.items(), key=lambda x: -x[1])[:5]],
        "avg_views": sum(v["view_count"] for v in videos) // len(videos),
        "total_views": sum(v["view_count"] for v in videos),
        "top_video": max(videos, key=lambda x: x["view_count"]) if videos else None,
    }


def fetch_competitor(channel):
    """Fetch all data for a competitor."""
    channel_id = channel["id"]
    handle = channel["handle"]
    name = channel["name"]
    yt_channel_id = channel["channel_id"]
    
    print(f"\n[{channel_id}] Fetching {handle}...")
    
    youtube = build("youtube", "v3", developerKey=API_KEY)
    channel_dir = COMPETITORS_DIR / channel_id
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Get channel info
    print(f"  [-] Getting channel info...")
    channel_info = get_channel_info(youtube, yt_channel_id)
    
    if not channel_info:
        print(f"  [ERROR] Could not find channel")
        return None
    
    print(f"  [OK] {channel_info['title']} | {channel_info['subscriber_count']:,} subs")
    
    # Save channel stats
    with open(channel_dir / "channel_stats.json", "w", encoding="utf-8") as f:
        json.dump(channel_info, f, indent=2, ensure_ascii=False)
    
    # 2. Fetch ALL shorts using Search API
    print(f"  [-] Fetching shorts via Search API (up to 200)...")
    shorts_items = get_all_shorts_from_channel(youtube, yt_channel_id, max_shorts=200)
    print(f"  [OK] Found {len(shorts_items)} shorts via Search API")
    
    # 3. If 0 shorts from search API, try uploads playlist fallback
    if len(shorts_items) == 0:
        print(f"  [-] Search API returned 0, trying uploads playlist fallback...")
        fallback_items = get_shorts_from_uploads_fallback(youtube, channel_info["uploads_playlist_id"], max_results=50)
        if fallback_items:
            print(f"  [OK] Found {len(fallback_items)} shorts via uploads fallback")
            shorts_items = fallback_items
    
    # 4. Get detailed stats for all shorts
    short_ids = [s["id"]["videoId"] for s in shorts_items]
    stats_map = get_video_details(youtube, short_ids) if short_ids else {}
    
    # 5. Build shorts data
    shorts_data = build_shorts_data(shorts_items, stats_map)
    
    # 6. Analyze
    shorts_analysis = analyze_posting_pattern(shorts_data, "Shorts")
    
    # 7. Get TOP 10 and LATEST 10
    top_10_shorts = sorted(shorts_data, key=lambda x: -x["view_count"])[:10]
    latest_10_shorts = sorted(shorts_data, key=lambda x: x["published_at_hkt"], reverse=True)[:10]
    
    # 8. Save data
    videos_data = {
        "fetched_at": datetime.now(HKT).isoformat(),
        "shorts": shorts_data,
        "shorts_analysis": shorts_analysis,
        "top_10_shorts": top_10_shorts,
        "latest_10_shorts": latest_10_shorts,
    }
    
    with open(channel_dir / "latest_videos.json", "w", encoding="utf-8") as f:
        json.dump(videos_data, f, indent=2, ensure_ascii=False)
    
    # 9. Daily snapshot
    today = datetime.now(HKT).strftime("%Y%m%d")
    snapshot = {
        "fetched_date": today,
        "channel": channel_info,
        "shorts_count": len(shorts_data),
        "shorts_analysis": shorts_analysis,
        "top_10_shorts": top_10_shorts[:5],  # Store top 5 in snapshot
        "latest_10_shorts": latest_10_shorts,
    }
    
    with open(channel_dir / f"snapshot_{today}.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    print(f"  [OK] Snapshot saved: {today}")
    
    # 10. Append to history
    jsonl_file = COMPETITORS_DIR / f"{channel_id}_history.jsonl"
    history_entry = {
        "timestamp": datetime.now(HKT).isoformat(),
        "subscriber_count": channel_info["subscriber_count"],
        "total_views": channel_info["total_views"],
        "shorts_count": len(shorts_data),
        "latest_short_views": shorts_data[0]["view_count"] if shorts_data else 0,
        "top_short_views": top_10_shorts[0]["view_count"] if top_10_shorts else 0,
        "avg_short_views": shorts_analysis.get("avg_views", 0),
    }
    
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
    
    print(f"  [DONE] {channel_info['title']}: {len(shorts_data)} Shorts")
    
    return {
        "channel": channel_info,
        "shorts": shorts_data,
        "shorts_analysis": shorts_analysis,
        "top_10_shorts": top_10_shorts,
        "latest_10_shorts": latest_10_shorts,
    }


def generate_report(results):
    """Generate detailed text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("📊 YOUTUBE COMPETITOR REPORT - " + datetime.now(HKT).strftime("%Y-%m-%d %H:%M"))
    lines.append("=" * 70)
    
    for data in results:
        ch = data["channel"]
        shorts = data["shorts"]
        analysis = data["shorts_analysis"]
        top_10 = data["top_10_shorts"]
        latest_10 = data["latest_10_shorts"]
        
        lines.append(f"\n🏆 {ch['title']} ({ch.get('handle', '@unknown')})")
        lines.append(f"   📈 {ch['subscriber_count']:,} subscribers")
        lines.append(f"   👁️  {ch['total_views']:,} total views")
        lines.append(f"   🎬 Total Shorts tracked: {len(shorts)}")
        
        if shorts:
            lines.append(f"\n   ═══ POSTING PATTERN ═══")
            lines.append(f"   📅 Best days: {', '.join([f'{d}({c})' for d,c in analysis['best_days']])}")
            lines.append(f"   🕐 Best hours (HKT): {', '.join([f'{h:02d}:00({c})' for h,c in analysis['best_hours_hkt']])}")
            lines.append(f"   🕐 Best hours (EST): {', '.join([f'{h:02d}:00({c})' for h,c in analysis['best_hours_est']])}")
            lines.append(f"   👁️  Avg views: {analysis['avg_views']:,}")
            lines.append(f"   👁️  Total views: {analysis['total_views']:,}")
            
            lines.append(f"\n   ═══ TOP 10 ALL-TIME SHORTS ═══")
            for i, v in enumerate(top_10, 1):
                lines.append(f"   {i:2d}. {v['title'][:50]}...")
                lines.append(f"       👁️ {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']}")
                lines.append(f"       👍 {v['like_count']:,} | 💬 {v['comment_count']:,}")
            
            lines.append(f"\n   ═══ LATEST 10 SHORTS ═══")
            for i, v in enumerate(latest_10, 1):
                lines.append(f"   {i:2d}. {v['title'][:50]}...")
                lines.append(f"       👁️ {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']} ({v['published_day']})")
        else:
            lines.append(f"\n   ⚠️  No shorts found")
        
        lines.append("")
    
    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_markdown_report(results):
    """Generate markdown report for wiki."""
    lines = []
    lines.append(f"# Competitor Report - {datetime.now(HKT).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    for data in results:
        ch = data["channel"]
        shorts = data["shorts"]
        analysis = data["shorts_analysis"]
        top_10 = data["top_10_shorts"]
        latest_10 = data["latest_10_shorts"]
        
        lines.append(f"## {ch['title']}")
        lines.append(f"- **Handle:** {ch.get('handle', 'N/A')}")
        lines.append(f"- **Subscribers:** {ch['subscriber_count']:,}")
        lines.append(f"- **Total Views:** {ch['total_views']:,}")
        lines.append(f"- **Shorts Tracked:** {len(shorts)}")
        lines.append("")
        
        if shorts:
            lines.append(f"### Posting Pattern")
            lines.append(f"- **Best Days:** {', '.join([f'{d}({c})' for d,c in analysis['best_days']])}")
            lines.append(f"- **Best Hours (HKT):** {', '.join([f'{h:02d}:00({c})' for h,c in analysis['best_hours_hkt']])}")
            lines.append(f"- **Best Hours (EST):** {', '.join([f'{h:02d}:00({c})' for h,c in analysis['best_hours_est']])}")
            lines.append(f"- **Avg Views:** {analysis['avg_views']:,}")
            lines.append("")
            
            lines.append(f"### TOP 10 All-Time Shorts")
            lines.append(f"| # | Title | Views | Duration | Posted (HKT) |")
            lines.append(f"|---|-------|-------|----------|--------------|")
            for i, v in enumerate(top_10, 1):
                lines.append(f"| {i} | {v['title'][:40]}... | {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']} |")
            lines.append("")
            
            lines.append(f"### Latest 10 Shorts")
            lines.append(f"| # | Title | Views | Duration | Posted (HKT) | Day |")
            lines.append(f"|---|-------|-------|----------|--------------|-----|")
            for i, v in enumerate(latest_10, 1):
                lines.append(f"| {i} | {v['title'][:40]}... | {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']} | {v['published_day']} |")
            lines.append("")
    
    return "\n".join(lines)


def load_existing():
    """Load existing data."""
    results = []
    for channel in TARGET_CHANNELS:
        channel_dir = COMPETITORS_DIR / channel["id"]
        stats_file = channel_dir / "channel_stats.json"
        videos_file = channel_dir / "latest_videos.json"
        
        if stats_file.exists() and videos_file.exists():
            with open(stats_file) as f:
                channel_info = json.load(f)
            with open(videos_file) as f:
                videos_data = json.load(f)
            
            results.append({
                "channel": channel_info,
                "shorts": videos_data.get("shorts", []),
                "shorts_analysis": videos_data.get("shorts_analysis", {}),
                "top_10_shorts": videos_data.get("top_10_shorts", []),
                "latest_10_shorts": videos_data.get("latest_10_shorts", []),
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="YouTube Competitor Tracker v3")
    parser.add_argument("--report", action="store_true", help="Report only")
    parser.add_argument("--history", action="store_true", help="Show history")
    args = parser.parse_args()
    
    if args.history:
        print("\n[COMPETITOR TRACKER] Historical Trend")
        for channel in TARGET_CHANNELS:
            jsonl_file = COMPETITORS_DIR / f"{channel['id']}_history.jsonl"
            if not jsonl_file.exists():
                continue
            
            print(f"\n--- {channel['name']} ---")
            with open(jsonl_file) as f:
                lines = f.readlines()
            
            for line in lines[-7:]:
                e = json.loads(line)
                print(f"  {e['timestamp'][:10]}: {e['subscriber_count']:,} subs | {e['shorts_count']} shorts | avg {e['avg_short_views']:,} views")
    
    elif args.report:
        results = load_existing()
        if results:
            print(generate_report(results))
            # Save markdown
            report_file = PROJECT_ROOT / "agent-meta" / "competitor-report.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(generate_markdown_report(results))
            print(f"\n[Saved to {report_file}]")
        else:
            print("No data. Run without --report first.")
    
    else:
        # Fetch all
        results = []
        for channel in TARGET_CHANNELS:
            data = fetch_competitor(channel)
            if data:
                results.append(data)
        
        if results:
            print(generate_report(results))
            
            # Save markdown
            report_file = PROJECT_ROOT / "agent-meta" / "competitor-report.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(generate_markdown_report(results))
            print(f"\n[Saved to {report_file}]")


if __name__ == "__main__":
    main()
