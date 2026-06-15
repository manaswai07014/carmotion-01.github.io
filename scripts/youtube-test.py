import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
from datetime import datetime

youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])

channels = {
    "kizzombie": "@kizzombie",
    "motomorfosis": "@motomorfosis"
}

for name, handle in channels.items():
    # Get channel info
    ch_response = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        forHandle=handle
    ).execute()
    
    if ch_response["items"]:
        ch = ch_response["items"][0]
        uploads_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Get latest 10 videos
        videos_response = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_id,
            maxResults=10
        ).execute()
        
        print(f"\n=== {ch['snippet']['title']} ({handle}) ===")
        print(f"Subscribers: {int(ch['statistics']['subscriberCount']):,}")
        print(f"Total Views: {int(ch['statistics']['viewCount']):,}")
        print(f"\nLatest 10 uploads:")
        
        for i, video in enumerate(videos_response["items"], 1):
            snippet = video["snippet"]
            published = snippet["publishedAt"]
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            title = snippet["title"]
            video_id = snippet["resourceId"]["videoId"]
            
            print(f"  {i}. [{dt.strftime('%Y-%m-%d %H:%M')}] {title[:50]}... (ID: {video_id})")
    else:
        print(f"Channel {handle} not found")