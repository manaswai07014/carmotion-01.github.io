import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re

youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])

# Get correct channel ID for motomorfosis
ch_response = youtube.channels().list(
    part="id,contentDetails,snippet",
    forHandle="@motomorfosis"
).execute()

if ch_response["items"]:
    ch = ch_response["items"][0]
    print(f"Channel: {ch['snippet']['title']}")
    print(f"Channel ID: {ch['id']}")
    print(f"Uploads ID: {ch['contentDetails']['relatedPlaylists']['uploads']}")
    
    # Search for all videos and filter by duration
    search_response = youtube.search().list(
        part="snippet,id",
        channelId=ch['id'],
        maxResults=50,
        type="video"
    ).execute()
    
    print(f"\nTotal videos found via search: {len(search_response.get('items', []))}")
    
    # Get video IDs
    video_ids = [s["id"]["videoId"] for s in search_response.get("items", [])]
    
    # Get durations for first 20
    stats_resp = youtube.videos().list(
        part="contentDetails,snippet,statistics",
        id=",".join(video_ids[:20])
    ).execute()
    
    shorts = []
    regular = []
    
    for item in stats_resp.get("items", []):
        dur = item["contentDetails"].get("duration", "PT0S")
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
        if match:
            h, m, s = (int(x) if x else 0 for x in match.groups())
            total_sec = h*3600 + m*60 + s
        else:
            total_sec = 999
        
        title = item["snippet"]["title"]
        views = int(item["statistics"].get("viewCount", 0))
        
        if total_sec < 60:
            shorts.append((title, dur, total_sec, views))
        else:
            regular.append((title, dur, total_sec, views))
    
    print(f"\nShorts (<60s): {len(shorts)}")
    for t, d, s, v in shorts[:5]:
        print(f"  - {t[:50]}... ({d}) {v:,} views")
    
    print(f"\nRegular: {len(regular)}")
    for t, d, s, v in regular[:5]:
        print(f"  - {t[:50]}... ({d}) {v:,} views")
else:
    print("Channel not found")
