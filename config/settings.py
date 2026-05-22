import os

# ── Site ──────────────────────────────────────────────────────────────
SITE_URL  = os.environ.get("SITE_URL", "https://studyriserr.com")
SITE_NAME = "studyriserr.com"

# ── GSC ───────────────────────────────────────────────────────────────
CREDENTIALS_PATH = "credentials.json"
DAYS_TO_FETCH    = 7
MAX_KEYWORDS     = 500

# ── Sheets ────────────────────────────────────────────────────────────
SHEET_ID              = os.environ.get("SHEET_ID", "")
SHEET_NAME_DASHBOARD  = "📊 Dashboard"
SHEET_NAME_DAILY_LOG  = "Daily Log"
SHEET_NAME_MOVERS     = "🟢 Movers"
SHEET_NAME_LOST_NEW   = "💀 Lost & New"

# ── Thresholds ────────────────────────────────────────────────────────
POSITION_CHANGE_THRESHOLD = 3

# ── SerpAPI — Multiple accounts ───────────────────────────────────
# Add as many accounts as you have
SERPAPI_ACCOUNTS = [
    {
        "name":  "Account 1",
        "key":   os.environ.get("SERPAPI_KEY_1", ""),
        "limit": 250,
    }
    # Add more as needed
]

# Legacy single key support
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")


# ── Dashboard ─────────────────────────────────────────────────────────
GITHUB_USERNAME = "samir-bit-ctrl"
GITHUB_REPO     = "rank-tracker"
DASHBOARD_URL   = f"https://{GITHUB_USERNAME}.github.io/{GITHUB_REPO}/"




# ── AIO Extractor (Free Playwright scraper) ───────────────────────
# Manual keyword list — leave empty to auto-select from history
TRACKED_KEYWORDS = [
    # Add specific keywords you always want to check
    # e.g. "jee mains syllabus", "neet eligibility criteria"
]

# Max keywords to auto-select from history when TRACKED_KEYWORDS is empty
AIO_MAX_KEYWORDS = 50

# Cache duration in hours (avoids re-scraping same keyword)
AIO_CACHE_HOURS = 24