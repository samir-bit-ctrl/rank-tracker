import os

# ── Site ──────────────────────────────────────────────────────────────
SITE_URL  = os.environ.get("SITE_URL", "https://studyriserr.com")
SITE_NAME = "studyriserr.com"

# ── GSC ───────────────────────────────────────────────────────────────
CREDENTIALS_PATH = "credentials.json"
DAYS_TO_FETCH    = 7
MAX_KEYWORDS     = 500

# ── Sheets ────────────────────────────────────────────────────────────
SHEET_ID              = os.environ.get("SHEET_ID", "1oI1sZyZxeMGLmL4H5TFl-PxOIvEQ3foQ4HreC1UOXV4")
SHEET_NAME_DASHBOARD  = "📊 Dashboard"
SHEET_NAME_DAILY_LOG  = "📈 Daily Log"
SHEET_NAME_MOVERS     = "🟢 Movers"
SHEET_NAME_LOST_NEW   = "💀 Lost & New"

# ── Telegram ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Teams ─────────────────────────────────────────────────────────────
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

# ── Thresholds ────────────────────────────────────────────────────────
POSITION_CHANGE_THRESHOLD = 3

# ── Dashboard ─────────────────────────────────────────────────────────
GITHUB_USERNAME = "samir-bit-ctrl"
GITHUB_REPO     = "rank-tracker"
DASHBOARD_URL   = f"https://{GITHUB_USERNAME}.github.io/{GITHUB_REPO}/"