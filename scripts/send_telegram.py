import json, re, subprocess, os

with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            BOT_TOKEN = line.split('=', 1)[1].strip()
        elif line.startswith('TELEGRAM_ALLOWED_USERS='):
            CHAT_ID = line.split('=', 1)[1].strip().split(',')[0]

TEXT = """*Topic Priority Report V2*
2026-06-09 HKT | LIVE

Top 8 Recommendations

1. Bugatti Veyron - 62.5/100 | Wiki Ready
   Trend: 10 | YT: 716K | News: 2 | Gap: 2

2. Bugatti Chiron - 62.5/100 | Wiki Ready
   Trend: 10 | YT: 931K | News: 2 | Gap: 2

3. Bugatti Divo - 62.5/100 | No Wiki
   Trend: 10 | YT: 367K | News: 2 | Gap: 2

4. Audi R8 - 58.5/100 | No Wiki
   Trend: 10 | YT: 985K | News: 3 | Gap: 8

5. Audi TT - 58.5/100 | No Wiki
   Trend: 10 | YT: 832K | News: 7 | Gap: 8

6. Audi RS6 - 58.5/100 | No Wiki
   Trend: 10 | YT: 731K | News: 3 | Gap: 8

7. Tesla Model S - 53.9/100 | Wiki Ready
   Trend: 34 | YT: 1M | News: 1 | Gap: 8

8. Tesla Roadster - 53.9/100 | No Wiki
   Trend: 34 | YT: 460K | News: 1 | Gap: 8

36 candidates | 5 trends | 20 news items"""

payload = json.dumps({
    "text": TEXT,
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
print(result.stderr)