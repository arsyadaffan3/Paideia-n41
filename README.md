# Paideia-N41
Is a single-file Telegram bot for the PN41 home server. Runs as a systemd service.

## Setup
1. `pip install -r requirements.txt` (python-telegram-bot, requests, groq, google-auth-oauthlib, google-api-python-client)
2. Copy `.env.example` → export the real values (see script header) — no `.env` file is loaded, uses `os.environ`
3. For `/today`: place `credentials.json` (Google Calendar OAuth) next to the script; first run opens a browser link to authorize, saves `token.json`
4. Run: `python telebot.py`

## Commands
`/stats` `/health` `/sleep` `/timer` `/shutdown` `/restart` `/help` `/8ball` `/today` `/prayer` — plus file upload and plain-text AI chat (Groq).

## Notes
- Auth-gated to a single `CHAT_ID`
- Logs to stderr (journald picks it up under systemd)

In you .env file it should contain your:
TELEGRAM_TOKEN=
CHAT_ID=
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
