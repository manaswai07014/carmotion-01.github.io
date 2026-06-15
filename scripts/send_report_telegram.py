import json, subprocess, os

env_path = os.path.expanduser('~/.hermes/.env')
with open(env_path) as f:
    for line in f:
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            BOT_TOKEN = line.split('=', 1)[1].strip()
        elif line.startswith('TELEGRAM_ALLOWED_USERS='):
            CHAT_ID = line.split('=', 1)[1].strip().split(',')[0]

msg = """*Daily Competitor Report V2* | 2026-06-10

*Data Status:* LIVE (Updated Today)

*Recommended Topics:*

1. *Bugatti Veyron* - Score: 62.5 | Wiki Ready
   YT Search: 716,730 | Competitor Shorts: Only 2
   Suggested: Bugatti Veyron Evolution (2026)

2. *Bugatti Chiron* - Score: 62.5 | Wiki Ready
   YT Search: 931,222 | Competitor Shorts: Only 2
   Suggested: Bugatti Chiron Evolution (2026)

3. *Bugatti Divo* - Score: 62.5 | No Wiki Yet
   YT Search: 367,439 | Competitor Shorts: Only 2
   Need to build Wiki first

4. Audi R8 - Score 58.5 | No Wiki
5. Audi TT - Score 58.5 | No Wiki

*Wiki Gaps to Fill:*
Bugatti Divo, Audi R8, Audi TT, Audi RS6, Tesla Roadster

*Competitor Data:*
@kizzombie: 620 Shorts | 901K subs
@motomorfosis: 79 Shorts | 179K subs"""

payload = json.dumps({
    "text": msg,
    "parse_mode": "Markdown",
    "chat_id": CHAT_ID
})

result = subprocess.run(
    ["curl", "-s", "-X", "POST",
     f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
     "-H", "Content-Type: application/json",
     "-d", payload],
    capture_output=True, text=True
)
print(result.stdout)