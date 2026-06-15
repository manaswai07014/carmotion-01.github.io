import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timezone, timedelta
import re

youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])
HKT = timezone(timedelta(hours=8))

channels = [
    {"handle": "@kizzombie", "name": "ArtKiz", "channel_id": "UC2IRZdo5HP4IjzuAjlsLjOg"},
    {"handle": "@motomorfosis", "name": "Motomorfosis", "channel_id": "UCR3J3RZQ-GRtKVJH-HjMEUQ"},
]

def parse_duration(duration):
    """Parse ISO 8601 duration to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        return h * 3600 + m * 60 + s
    return 999

def duration_str(duration):
    """Format duration in seconds to human readable."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if match:
        h, m, s = (int(x) if x else 0 for x in match.groups())
        if h: return f"{h}h {m}m {s}s"
        if m: return f"{m}m {s}s"
        return f"{s}s"
    return "N/A"

for ch in channels:
    print(f"\n{'='*70}")
    print(f"DETAILED ANALYSIS: {ch['name']} ({ch['handle']})")
    print('='*70)
    
    channel_id = ch["channel_id"]
    
    # =========================================================
    # PART A: SEARCH API - Get Shorts using videoDuration='short'
    # =========================================================
    print(f"\n[SHORTS via SEARCH API - videoDuration='short']")
    try:
        search_response = youtube.search().list(
            part="snippet,id",
            channelId=channel_id,
            maxResults=20,
            type="video",
            videoDuration="short"
        ).execute()
        
        shorts_search = search_response.get("items", [])
        print(f"Total Shorts found: {len(shorts_search)}")
        
        if shorts_search:
            # Get video IDs
            short_ids = [s["id"]["videoId"] for s in shorts_search]
            
            # Get detailed stats (need to batch due to quota)
            all_stats = {}
            for i in range(0, len(short_ids), 10):
                batch = short_ids[i:i+10]
                try:
                    stats_resp = youtube.videos().list(
                        part="statistics,contentDetails,snippet",
                        id=",".join(batch)
                    ).execute()
                    for item in stats_resp.get("items", []):
                        vid = item["id"]
                        all_stats[vid] = item
                except HttpError as e:
                    print(f"Error: {e}")
            
            total_views = 0
            recent_shorts = []
            
            for s in shorts_search:
                vid_id = s["id"]["videoId"]
                stats = all_stats.get(vid_id, {})
                
                title = s["snippet"]["title"]
                published = s["snippet"]["publishedAt"]
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                dt_hkt = dt.astimezone(HKT)
                
                views = 0
                duration = "PT0S"
                if stats:
                    views = int(stats["statistics"].get("viewCount", 0))
                    duration = stats["contentDetails"].get("duration", "PT0S")
                    total_views += views
                
                recent_shorts.append({
                    "title": title,
                    "vid": vid_id,
                    "views": views,
                    "duration": duration,
                    "duration_sec": parse_duration(duration),
                    "published_hkt": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                    "published_day": dt_hkt.strftime("%A"),
                    "published_hour": dt_hkt.hour,
                })
            
            avg_views = total_views // len(recent_shorts) if recent_shorts else 0
            
            # Analyze posting times
            days_count = {}
            hours_count = {}
            for v in recent_shorts:
                days_count[v["published_day"]] = days_count.get(v["published_day"], 0) + 1
                hours_count[v["published_hour"]] = hours_count.get(v["published_hour"], 0) + 1
            
            top_days = sorted(days_count.items(), key=lambda x: -x[1])[:3]
            top_hours = sorted(hours_count.items(), key=lambda x: -x[1])[:5]
            
            shorts_sample = recent_shorts[:5]
            
            print(f"\n📊 Posting Pattern (latest {len(recent_shorts)} Shorts):")
            print(f"   Days: {', '.join([f'{d}({c})' for d,c in top_days])}")
            print(f"   Hours (HKT): {', '.join([f'{h:02d}:00({c})' for h,c in top_hours])}")
            print(f"   Avg views: {avg_views:,}")
            
            print(f"\n📅 Recent Shorts samples:")
            for v in shorts_sample:
                dur = duration_str(v["duration"])
                print(f"   [{v['published_hkt']}] {v['title'][:45]}...")
                print(f"      Views: {v['views']:,} | Duration: {dur} | Day: {v['published_day']}")
            
    except HttpError as e:
        print(f"Error: {e}")
    
    # =========================================================
    # PART B: SEARCH API - Get Regular videos (videoDuration='medium' or 'long')
    # =========================================================
    print(f"\n[REGULAR VIDEOS via SEARCH API - videoDuration='medium' or 'long']")
    try:
        reg_response = youtube.search().list(
            part="snippet,id",
            channelId=channel_id,
            maxResults=20,
            type="video",
            videoDuration="any"
        ).execute()
        
        all_videos = reg_response.get("items", [])
        
        # Separate shorts and regular
        short_ids_search = set()
        regular_ids = []
        
        # We need stats to determine duration, so fetch stats for all
        all_video_ids = [v["id"]["videoId"] for v in all_videos]
        
        all_stats_reg = {}
        for i in range(0, len(all_video_ids), 10):
            batch = all_video_ids[i:i+10]
            try:
                stats_resp = youtube.videos().list(
                    part="statistics,contentDetails,snippet",
                    id=",".join(batch)
                ).execute()
                for item in stats_resp.get("items", []):
                    vid = item["id"]
                    dur_sec = parse_duration(item["contentDetails"].get("duration", "PT0S"))
                    all_stats_reg[vid] = {
                        "duration": item["contentDetails"].get("duration", "PT0S"),
                        "duration_sec": dur_sec,
                        "view_count": int(item["statistics"].get("viewCount", 0)),
                        "title": item["snippet"]["title"],
                        "publishedAt": item["snippet"]["publishedAt"],
                    }
            except HttpError as e:
                print(f"Error: {e}")
        
        shorts_list = []
        regular_list = []
        
        for v in all_videos:
            vid_id = v["id"]["videoId"]
            stats = all_stats_reg.get(vid_id, {})
            dur_sec = stats.get("duration_sec", 999)
            
            dt = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            dt_hkt = dt.astimezone(HKT)
            
            video_info = {
                "title": v["snippet"]["title"],
                "vid": vid_id,
                "views": stats.get("view_count", 0),
                "duration": stats.get("duration", "PT0S"),
                "duration_sec": dur_sec,
                "published_hkt": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "published_day": dt_hkt.strftime("%A"),
                "published_hour": dt_hkt.hour,
            }
            
            if dur_sec < 60:
                shorts_list.append(video_info)
            else:
                regular_list.append(video_info)
        
        # Get shorts via search (videoDuration=short)
        short_response = youtube.search().list(
            part="snippet,id",
            channelId=channel_id,
            maxResults=20,
            type="video",
            videoDuration="short"
        ).execute()
        short_ids_search = {s["id"]["videoId"] for s in short_response.get("items", [])}
        
        # Everything NOT in shorts list but in all_videos = regular
        regular_only = [v for v in all_videos if v["id"]["videoId"] not in short_ids_search]
        
        print(f"\n📊 Video Type Distribution (from uploads):")
        print(f"   Shorts (<60s): {len(shorts_list)}")
        print(f"   Regular videos: {len(regular_list)}")
        
        if regular_list:
            print(f"\n📅 Recent Regular Videos samples:")
            for v in regular_list[:5]:
                dur = duration_str(v["duration"])
                print(f"   [{v['published_hkt']}] {v['title'][:45]}...")
                print(f"      Views: {v['views']:,} | Duration: {dur}")
                
        # Posting time for regular
        if regular_list:
            days_count = {}
            hours_count = {}
            for v in regular_list:
                days_count[v["published_day"]] = days_count.get(v["published_day"], 0) + 1
                hours_count[v["published_hour"]] = hours_count.get(v["published_hour"], 0) + 1
            
            top_days = sorted(days_count.items(), key=lambda x: -x[1])[:3]
            top_hours = sorted(hours_count.items(), key=lambda x: -x[1])[:5]
            
            print(f"\n📊 Regular Videos Posting Pattern:")
            print(f"   Days: {', '.join([f'{d}({c})' for d,c in top_days])}")
            print(f"   Hours (HKT): {', '.join([f'{h:02d}:00({c})' for h,c in top_hours])}")
            
    except HttpError as e:
        print(f"Error: {e}")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
