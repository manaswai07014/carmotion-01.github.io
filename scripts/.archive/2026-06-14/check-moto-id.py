import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyDDIEaTSmtifeVqzjQHVl6ikqaZmdWw4MM"

from googleapiclient.discovery import build
youtube = build("youtube", "v3", developerKey=os.environ["GOOGLE_API_KEY"])

# Try with forHandle
response = youtube.channels().list(
    part="id,snippet,statistics",
    forHandle="@motomorfosis"
).execute()

if response.get("items"):
    ch = response["items"][0]
    print("Title:", ch["snippet"]["title"])
    print("Channel ID:", ch["id"])
    print("Subs:", ch["statistics"]["subscriberCount"])
else:
    print("Not found via forHandle")

# Try with different case
response2 = youtube.channels().list(
    part="id,snippet,statistics",
    id="UCs3HXNAJ27auPVGuhKJyWAw"
).execute()
print("\nWith lowercase s - items:", len(response2.get("items", [])))

response3 = youtube.channels().list(
    part="id,snippet,statistics",
    id="UCS3HXNAJ27auPVGuhKJyWAw"
).execute()
print("With uppercase S - items:", len(response3.get("items", [])))
if response3.get("items"):
    print("Title:", response3["items"][0]["snippet"]["title"])
