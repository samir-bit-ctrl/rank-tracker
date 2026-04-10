import json
import os
from datetime import datetime

HISTORY_FILE = "data/history.json"


def load_history():
    """Load existing history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(data: list):
    """Save today's fetch into history."""
    os.makedirs("data", exist_ok=True)
    history = load_history()

    today = datetime.today().strftime("%Y-%m-%d")
    history[today] = {row["keyword"]: row for row in data}

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

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