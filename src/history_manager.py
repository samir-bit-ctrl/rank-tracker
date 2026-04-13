import json
import os
from datetime import datetime

HISTORY_FILE = "data/history.json"


def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  history.json corrupted ({e}) — starting fresh")
        # Backup the corrupted file
        backup = HISTORY_FILE + ".corrupted"
        os.rename(HISTORY_FILE, backup)
        print(f"   Corrupted file saved as {backup}")
        return {}

def save_history(data: list):
    """Save today's fetch into history — atomic write to prevent corruption."""
    os.makedirs("data", exist_ok=True)
    history = load_history()

    today = datetime.today().strftime("%Y-%m-%d")
    history[today] = {row["keyword"]: row for row in data}

    # Write to temp file first, then rename (atomic — prevents partial writes)
    tmp_file = HISTORY_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(history, f, indent=2)

    # Only replace original after successful write
    os.replace(tmp_file, HISTORY_FILE)

    print(f"✅ History saved for {today} ({len(data)} keywords)")
    return today


def get_previous_date(history: dict, current_date: str):
    """Get the most recent date before current_date."""
    dates = sorted(history.keys())
    if current_date in dates:
        dates.remove(current_date)
    return dates[-1] if dates else None


def get_latest_two_snapshots():
    """Return (today_data, yesterday_data, today_date, yesterday_date)."""
    history = load_history()
    if not history:
        return None, None, None, None

    dates = sorted(history.keys())
    today_date = dates[-1]
    today_data = history[today_date]

    if len(dates) < 2:
        return today_data, None, today_date, None

    yesterday_date = dates[-2]
    yesterday_data = history[yesterday_date]

    return today_data, yesterday_data, today_date, yesterday_date