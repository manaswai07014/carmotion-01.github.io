import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta

youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])
HKT = timezone(timedelta(hours=8))

channels = [
    {"handle": "@kizzombie", "name": "ArtKiz"},
    {"handle": "@motomorfosis", "name": "Motomorfosis"},
]

for ch in channels:
    print(f"\n{'='*60}")
    print(f"Checking Shorts for: {ch['name']} ({ch['handle']})")
    print('='*60)
    
    # Method 1: Search for shorts from this channel
    print("\n[Method 1] Search API - Shorts only:")
    search_response = youtube.search().list(
        part="snippet",
        channelId=youtube.channels().list(
            part="contentDetails",
            forHandle=ch["handle"]
        ).execute()["items"][0]["id"],
        maxResults=20,
        type="video",
        videoDuration="short"
    ).execute()
    
    shorts = search_response.get("items", [])
    print(f"Found {len(shorts)} Shorts via search API")
    
    for item in shorts[:5]:
        snippet = item["snippet"]
        print(f"  - {snippet['title'][:50]}... ({snippet.get('publishedAt', 'N/A')[:10]})")
    
    # Method 2: Get ALL videos and check duration
    print("\n[Method 2] Check uploads playlist for short videos:")
    uploads_id = youtube.channels().list(
        part="contentDetails",
        forHandle=ch["handle"]
    ).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    all_videos = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_id,
        maxResults=50
    ).execute().get("items", [])
    
    import re
    short_videos = []
    regular_videos = []
    
    for item in all_videos:
        duration = item.get("contentDetails", {}).get("duration", "PT0S")
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if match:
            h, m, s = match.groups()
            total_sec = (int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0))
            if total_sec < 60:
                short_videos.append(item)
            else:
                regular_videos.append(item)
    
    print(f"Total uploads: {len(all_videos)}")
    print(f"Shorts (<60s): {len(short_videos)}")
    print(f"Regular videos: {len(regular_videos)}")
    
    if short_videos:
        print("\nSample Shorts from uploads playlist:")
        for item in short_videos[:5]:
            snippet = item["snippet"]
            duration = item.get("contentDetails", {}).get("duration", "N/A")
            print(f"  - {snippet['title'][:50]}... | Duration: {duration}")
    
    if regular_videos:
        print("\nSample Regular videos:")
        for item in regular_videos[:3]:
            snippet = item["snippet"]
            duration = item.get("contentDetails", {}).get("duration", "N/A")
            print(f"  - {snippet['title'][:50]}... | Duration: {duration}")
