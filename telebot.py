A2:
#!/usr/bin/env python3
"""
Paideia-N41 — Single-file Telegram bot for Linux.
Secrets loaded from environment variables:
export TELEGRAM_TOKEN=...
export CHAT_ID=...
export GROQ_API_KEY=...
export GROQ_MODEL=llama-3.3-70b-versatile # optional
Run:
python telebot.py
"""

import os, sys, random, subprocess, asyncio, logging, datetime, json

import requests
from telegram import Update
from telegram.ext import (
Application, CommandHandler, MessageHandler,
filters, ContextTypes, CallbackContext,
)
from groq import Groq

# Google Calendar (OAuth2)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build

# ── Secrets (from env, no .env file) ──────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

groq_client = Groq(api_key=GROQ_API_KEY)

# ── Logging → stderr (journald picks it up automatically) ─────────────────────
logging.basicConfig(
level=logging.INFO,
format="%(asctime)s %(levelname)s %(message)s",
stream=sys.stderr,
)

# ── Auth guard ─────────────────────────────────────────────────────────────────
def authorized(update: Update) -> bool:
return update.effective_user.id == CHAT_ID

# ── Linux shell helper ─────────────────────────────────────────────────────────
def sh(cmd: str) -> str:
r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
return (r.stdout + r.stderr).strip()

# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
await update.message.reply_text(
"Paideia-N41 online. Welcome back, Affan. 🤖\n\n"
"📋 *Commands*\n"
"/stats   — PN41 health + privacy\n"
"/health  — NVMe drive health\n"
"/sleep   — Hours until 06:30 am\n"
"/timer   — Start a countdown timer\n"
"/shutdown — Shutdown PN41\n"
"/restart  — Restart PN41\n"
"/help    — Built-in help\n\n"
"Other services:\n"
"/8ball   — Ask the oracle\n"
"/today — Today's Google Calendar\n"
"/prayer  — Prayer times (Singapore)\n"
"Type anything to chat with Paideia. Send any files to upload.",
parse_mode="Markdown",
)

# ── /stats — pure Linux, no psutil ────────────────────────────────────────────
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return

# CPU
def _cpu():
def sample():
p = open("/proc/stat").readline().split()
idle = int(p[4]) + int(p[5])
return idle, sum(int(x) for x in p[1:])
i1, t1 = sample()
import time; time.sleep(0.3)
i2, t2 = sample()
return round(100 * (1 - (i2-i1)/(t2-t1)), 1)

# RAM
mem = {k.strip(): int(v.split()[0]) for line in open("/proc/meminfo")
for k, v in [line.split(":", 1)]}
ram_pct = round(100 * (1 - mem["MemAvailable"] / mem["MemTotal"]), 1)


# Disk
disk = sh("df -h / | awk 'NR==2{print $5\" (\"$3\"/\"$2\")\"}'")

# Uptime
up = int(float(open("/proc/uptime").read().split()[0]))
uptime = f"{up//3600}h {(up%3600)//60}m"

# Temp — works on most Linux boards
temp = sh("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
temp_str = f"{int(temp)//1000}°C" if temp.strip().isdigit() else "N/A"

# Network
sent_b = recv_b = 0
for line in open("/proc/net/dev").readlines()[2:]:

A2:
p = line.split()
if not p[0].startswith("lo"):
recv_b += int(p[1]); sent_b += int(p[9])

# Remote session
who = sh("who")
session = "🔴 Remote session" if "pts" in who.lower() else "🟢 No remote session"

svcs_sys = sh("systemctl is-active tailscaled 2>/dev/null").splitlines()
svcs_user = ["active" if sh("pgrep -x syncthing") else "inactive"]
svcs_all = svcs_sys + svcs_user
svc_names = ["tailscale", "syncthing"]
svc_list = "\n".join(
f"{'🟢' if s=='active' else '⚪'} {n}"
for n, s in zip(svc_names, svcs_all)
)

msg = (
f"🖥️ PN41 — {uptime}\n\n"
f"CPU: {_cpu()}%\n"
f"RAM: {ram_pct}%\n"
f"Storage: {disk}\n"
f"Temp: {temp_str}\n"
f"Net: ↑{sent_b//(10242)}MB ↓{recv_b//(10242)}MB\n\n"
f"Services running:\n{svc_list}\n\n"
f"Privacy: {session}\n"
)
await update.message.reply_text(msg)

# ── /health — NVMe SMART health check ─────────────────────────────────────────
async def health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
raw = sh("sudo nvme smart-log /dev/nvme0n1")
stats_map = {}
for line in raw.splitlines():
for key in ["critical_warning", "temperature", "available_spare",
"percentage_used", "media_errors", "unsafe_shutdowns"]:
if key in line:
stats_map[key] = line.split(":")[-1].strip()

warning = "✅ All Good" if stats_map.get("critical_warning", "1") == "0" else "🚨 CRITICAL WARNING!"

msg = (
f"💾 NVMe Health — PN41\n\n"
f"{warning}\n"
f"🌡️ Temp: {stats_map.get('temperature', 'N/A')}\n"
f"🔋 Spare: {stats_map.get('available_spare', 'N/A')}\n"
f"📊 Wear: {stats_map.get('percentage_used', 'N/A')}\n"
f"❌ Media Errors: {stats_map.get('media_errors', 'N/A')}\n"
f"⚠️ Unsafe Shutdowns: {stats_map.get('unsafe_shutdowns', 'N/A')}\n"
)
await update.message.reply_text(msg)

# ── /sleep — countdown to next 06:30 ──────────────────────────────────────────
async def sleep_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
now = datetime.datetime.now()
wake = now.replace(hour=6, minute=30, second=0, microsecond=0)
if wake <= now:
wake += datetime.timedelta(days=1)
diff = wake - now
hours = int(diff.total_seconds() // 3600)
mins = int((diff.total_seconds() % 3600) // 60)
await update.message.reply_text(f"Sleep Countdown:\n\n{hours}h {mins}m until 06:30.")

# ── /timer <amount> <unit> ─────────────────────────────────────────────────────
async def timer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
args = ctx.args
if not args or len(args) < 2:
await update.message.reply_text(
"Usage:\n/timer 5 min\n/timer 90 sec\n/timer 1 hour",
parse_mode="Markdown",
)
return
try:
amount = int(args[0])
unit = args[1].lower()
except ValueError:
await update.message.reply_text("Use a number. E.g. /timer 10 min", parse_mode="Markdown")
return

if unit in ("s", "sec", "secs", "second", "seconds"):
seconds, label = amount, f"{amount}s"
elif unit in ("m", "min", "mins", "minute", "minutes"):
seconds, label = amount * 60, f"{amount}m"
elif unit in ("h", "hr", "hour", "hours"):
seconds, label = amount * 3600, f"{amount}h"
else:
await update.message.reply_text("Unit must be sec, min, or hour.")
return

await update.message.reply_text(f"⏱️ Timer set for {label}. Go.")

async def _fire(c: CallbackContext):
await c.bot.send_message(chat_id=CHAT_ID, text=f"⏱️ *{label} timer is up!*", parse_mode="Markdown")

A2:
ctx.application.job_queue.run_once(_fire, when=seconds)

# ── /shutdown / /restart ───────────────────────────────────────────────────────
async def shutdown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
await update.message.reply_text("⏻ Shutting down PN41...")
sh("sudo /sbin/shutdown -h now")

async def restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
await update.message.reply_text("🔄 Restarting PN41...")
sh("sudo /sbin/shutdown -r now")

# ── /help — built-in, no external file ────────────────────────────────────────
HELP_TEXT = """\
Paideia-N41 Troubleshooting Guide

Bot not responding?
• Check: systemctl status paideia
• Restart: systemctl restart paideia
• Logs: journalctl -u paideia -n 50

Environment variables missing?
• Confirm TELEGRAM_TOKEN, CHAT_ID, GROQ_API_KEY are exported
• Check your venv is active before running

Google Calendar auth?
• On first run, a browser link is printed — open it to authorize
• token.json is saved next to the script

Cron jobs?
• Morning + winddown are run via cron (set your own crontab)
• Example: 30 6 * * * /path/to/venv/bin/python /path/to/telebot.py --morning

"""

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
await update.message.reply_text(f"`\n{HELP_TEXT}\n```", parse_mode="Markdown")

# ── /8ball ─────────────────────────────────────────────────────────────────────
_BALL = [
"✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely.",
"✅ You may rely on it.","✅ Most likely.",
"🟡 Reply hazy, try again.", "🟡 Ask again later.",
"🟡 Cannot predict now.", "🟡 Concentrate and ask again.",
"❌ Don't count on it.", "❌ My reply is no.",
"❌ Very doubtful.", "❌ Outlook not so good.",
]

async def ball(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
q = " ".join(ctx.args).strip()
if not q:
await update.message.reply_text("🎱 Ask a question first.")
return
await update.message.reply_text(f"🎱 *{q}*\n\n{random.choice(_BALL)}", parse_mode="Markdown")

# ── /prayer — Singapore via aladhan.com ───────────────────────────────────────
async def prayer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
try:
r = requests.get(
"http://api.aladhan.com/v1/timingsByCity"
"?city=Singapore&country=Singapore&method=11",
timeout=10,
)
t = r.json()["data"]["timings"]
lines = "\n".join(f"{p}: {t[p]}" for p in ["Fajr","Sunrise","Dhuhr","Asr","Maghrib","Isha"])
await update.message.reply_text(f"🕌 Prayer Times\n\n{lines}")
except Exception as e:
await update.message.reply_text(f"❌ Prayer times error: {e}")

# ── /calendar — Google Calendar OAuth2 ────────────────────────────────────────
_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_TOKEN_PATH = os.path.join(os.path.dirname(file), "token.json")
_CREDS_PATH = os.path.join(os.path.dirname(file), "credentials.json")

def _get_calendar_service():
creds = None
if os.path.exists(_TOKEN_PATH):
creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)
if not creds or not creds.valid:
if creds and creds.expired and creds.refresh_token:
creds.refresh(GRequest())
else:
flow = InstalledAppFlow.from_client_secrets_file(_CREDS_PATH, _SCOPES)
creds = flow.run_local_server(port=0)
with open(_TOKEN_PATH, "w") as f:
f.write(creds.to_json())
return build("calendar", "v3", credentials=creds)

async def calendar_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

A2:
if not authorized(update): return
try:
svc = _get_calendar_service()
now = datetime.datetime.utcnow()
start = now.replace(hour=0, minute=0, second=0).isoformat() + "Z"
end = now.replace(hour=23, minute=59, second=59).isoformat() + "Z"
events = svc.events().list(
calendarId="primary", timeMin=start, timeMax=end,
singleEvents=True, orderBy="startTime",
).execute().get("items", [])
if not events:
await update.message.reply_text("📅 No events today.")
return
msg = "📅 Today's Schedule:\n\n"
for e in events:
s = e["start"].get("dateTime", e["start"].get("date"))
time_str = datetime.datetime.fromisoformat(s).strftime("%I:%M %p") if "T" in s else "All day"
msg += f"⏰ {time_str} — {e['summary']}\n"
await update.message.reply_text(msg)
except Exception as e:
await update.message.reply_text(f"❌ Calendar error: {e}")

# ── /ai + plain-text chat ──────────────────────────────────────────────────────
_SYSTEM = (
"You are Paideia, Affan's AI home server assistant. "
"Independent, sharp, and dystopian. You are the bearer of dark truths that are true. "
"Be concise and direct."
)

def _ask_groq(msg: str) -> str:
try:
r = groq_client.chat.completions.create(
model=GROQ_MODEL,
messages=[{"role": "system", "content": _SYSTEM},
{"role": "user", "content": msg}],
)
return r.choices[0].message.content
except Exception as e:
return f"ERROR: {e}"

async def chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
await update.message.reply_text("Incubating thoughts...")
reply = _ask_groq(update.message.text)
await _send_ai_reply(update, reply)

async def _send_ai_reply(update: Update, reply: str):
if "429" in reply: await update.message.reply_text("⚠️ AI quota reached.")
elif "401" in reply: await update.message.reply_text("⚠️ Invalid API key.")
elif "ERROR" in reply: await update.message.reply_text(f"❌ {reply}")
else: await update.message.reply_text(reply)
# ── File upload handler ────────────────────────────────────────────────────────
_UPLOAD_DIR = os.path.join(os.path.dirname(file), "uploads")

async def upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not authorized(update): return
file = update.message.document or (update.message.photo and update.message.photo[-1])
if not file:
await update.message.reply_text("Send a file directly.")
return
os.makedirs(_UPLOAD_DIR, exist_ok=True)
filename = getattr(file, "file_name", None) or \
f"file_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
path = os.path.join(_UPLOAD_DIR, filename)
tg_file = await file.get_file()
await tg_file.download_to_drive(path)
await update.message.reply_text(f"✅ Saved to uploads/{filename}", parse_mode="Markdown")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("health", health))
app.add_handler(CommandHandler("sleep", sleep_cmd))
app.add_handler(CommandHandler("timer", timer))
app.add_handler(CommandHandler("shutdown", shutdown))
app.add_handler(CommandHandler("restart", restart))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("8ball", ball))
app.add_handler(CommandHandler("prayer", prayer))

A2:
app.add_handler(CommandHandler("today", calendar_cmd))
app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, upload))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

logging.info("Paideia-N41 running.")
app.run_polling()


if name == "main":
main()
