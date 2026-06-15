import json, subprocess, os

env_path = os.path.expanduser('~/.hermes/.env')
BOT_TOKEN = CHAT_ID = None
with open(env_path) as f:
    for line in f:
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            BOT_TOKEN = line.split('=',1)[1].strip()
        elif line.startswith('TELEGRAM_ALLOWED_USERS='):
            CHAT_ID = line.split('=',1)[1].strip().split(',')[0]

msg = """*Auto-Wiki Ingestion Pipeline — 2026-06-10*

*Result:* No eligible brands — all exist or in cooldown.

*Priority Ranking (Top 5):*
1. Porsche       score=0.2  (trend=911)
2. Mercedes      score=0.0  (trend=34)
3. Toyota        score=0.0  (trend=21)
4. Nissan        score=0.0  (trend=21)
5. Lamborghini   score=0.0  (trend=20)

*Errors/Warnings:* None — pipeline ran cleanly.

*Action:* Run with --brand <name> to force ingest a specific brand.

*Next Run:* Scheduled via cron (daily news fetch + trend monitor active)."""

payload = json.dumps({
    'text': msg,
    'parse_mode': 'Markdown',
    'chat_id': CHAT_ID
})

result = subprocess.run(
    ['curl', '-s', '-X', 'POST',
     f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
     '-H', 'Content-Type: application/json',
     '-d', payload],
    capture_output=True, text=True
)
print(result.stdout)
