import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timezone, timedelta
import re

youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])
HKT = timezone(timedelta(hours=8))
EST = timezone(timedelta(hours=-5))

channels = [
    {"handle": "@kizzombie", "name": "ArtKiz", "channel_id": "UC2IRZdo5HP4IjzuAjlsLjOg"},
    {"handle": "@motomorfosis", "name": "Motomorfosis", "channel_id": "UCS3HXNAJ27auPVGuhKJyWAw"},
]

def parse_duration(duration):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        return h * 3600 + m * 60 + s
    return 999

def duration_str(duration):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        if h: return f"{h}h {m}m {s}s"
        if m: return f"{m}m {s}s"
        return f"{s}s"
    return "N/A"

for ch in channels:
    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE ANALYSIS: {ch['name']} ({ch['handle']})")
    print('='*70)
    
    channel_id = ch["channel_id"]
    
    # Method: Use search API to get ALL shorts from this channel
    # YouTube Search API returns max 50 per page, need pagination
    print(f"\n[Fetching ALL Shorts via Search API]")
    
    all_shorts = []
    next_token = None
    total_fetched = 0
    
    while total_fetched < 200:  # Fetch up to 200 to find all shorts
        try:
            search_params = {
                "part": "snippet,id",
                "channelId": channel_id,
                "maxResults": 50,
                "type": "video",
                "videoDuration": "short",
                "order": "date"
            }
            if next_token:
                search_params["pageToken"] = next_token
            
            response = youtube.search().list(**search_params).execute()
            
            items = response.get("items", [])
            all_shorts.extend(items)
            total_fetched += len(items)
            
            next_token = response.get("nextPageToken")
            if not next_token or not items:
                break
                
        except HttpError as e:
            print(f"  Error: {e}")
            break
    
    print(f"  Total Shorts found via Search API: {total_fetched}")
    
    if all_shorts:
        # Get video IDs
        short_ids = [s["id"]["videoId"] for s in all_shorts]
        
        # Fetch detailed stats in batches
        print(f"  Fetching detailed stats for {len(short_ids)} shorts...")
        
        all_stats = {}
        for i in range(0, len(short_ids), 50):
            batch = short_ids[i:i+50]
            try:
                stats_resp = youtube.videos().list(
                    part="statistics,contentDetails,snippet",
                    id=",".join(batch)
                ).execute()
                for item in stats_resp.get("items", []):
                    all_stats[item["id"]] = item
            except HttpError as e:
                print(f"  Error fetching batch: {e}")
        
        # Build detailed shorts list
        shorts_data = []
        for s in all_shorts:
            vid_id = s["id"]["videoId"]
            stats = all_stats.get(vid_id, {})
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
                "published_at_hkt": dt_hkt.strftime("%Y-%m-%d %H:%M:%S"),
                "published_day": dt_hkt.strftime("%A"),
                "published_hour_hkt": dt_hkt.hour,
                "published_hour_est": dt_est.hour,
                "duration": duration,
                "duration_sec": parse_duration(duration),
                "duration_str": duration_str(duration),
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count,
            })
        
        # Analysis
        days_count = {}
        hours_count = {}
        total_views = sum(v["view_count"] for v in shorts_data)
        avg_views = total_views // len(shorts_data) if shorts_data else 0
        
        for v in shorts_data:
            days_count[v["published_day"]] = days_count.get(v["published_day"], 0) + 1
            hours_count[v["published_hour_hkt"]] = hours_count.get(v["published_hour_hkt"], 0) + 1
        
        top_days = sorted(days_count.items(), key=lambda x: -x[1])[:3]
        top_hours = sorted(hours_count.items(), key=lambda x: -x[1])[:5]
        
        # Top videos
        top_10_shorts = sorted(shorts_data, key=lambda x: -x["view_count"])[:10]
        
        print(f"\n📊 SHORTSTOTAL: {len(shorts_data)}")
        print(f"📈 Total Views: {total_views:,}")
        print(f"📊 Average Views: {avg_views:,}")
        print(f"\n📅 Best Posting Days: {', '.join([f'{d}({c})' for d,c in top_days])}")
        print(f"🕐 Best Posting Hours (HKT): {', '.join([f'{h:02d}:00({c})' for h,c in top_hours])}")
        print(f"🕐 Best Posting Hours (EST): {', '.join([f'{h:02d}:00({hours_count.get(h, 0)})' for h in range(24) if hours_count.get(h, 0) > 0][:5])}")
        
        print(f"\n🔥 TOP 10 ALL-TIME SHORTS:")
        for i, v in enumerate(top_10_shorts, 1):
            print(f"  {i}. {v['title'][:50]}...")
            print(f"     Views: {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']}")
            print(f"     👍 {v['like_count']:,} | 💬 {v['comment_count']:,}")
        
        print(f"\n🆕 LATEST 10 SHORTS:")
        latest_10 = sorted(shorts_data, key=lambda x: x["published_at_hkt"], reverse=True)[:10]
        for i, v in enumerate(latest_10, 1):
            print(f"  {i}. {v['title'][:50]}...")
            print(f"     Views: {v['view_count']:,} | {v['duration_str']} | {v['published_at_hkt']} ({v['published_day']})")
        
    else:
        print(f"  No shorts found via search API")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
