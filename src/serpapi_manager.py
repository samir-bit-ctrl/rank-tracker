"""
Manages multiple SerpAPI accounts with automatic switching
when one account hits its monthly limit.
"""
import json
import os
from datetime import datetime
from config.settings import SERPAPI_ACCOUNTS, SERPAPI_KEY

USAGE_FILE = "data/serpapi_usage.json"


def _load_usage() -> dict:
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_usage(usage: dict):
    os.makedirs("data", exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def get_all_accounts_status() -> list:
    """
    Returns status of all configured accounts.
    Used by control panel to display credit counters.
    """
    usage  = _load_usage()
    month  = _current_month()
    result = []

    # Include legacy single key if set and not in accounts list
    accounts = SERPAPI_ACCOUNTS.copy()
    if SERPAPI_KEY and not any(a["key"] == SERPAPI_KEY for a in accounts):
        accounts.insert(0, {"name": "Default", "key": SERPAPI_KEY, "limit": 100})

    for acc in accounts:
        key        = acc.get("key", "")
        limit      = acc.get("limit", 100)
        used       = usage.get(key, {}).get(month, 0) if key else 0
        remaining  = max(0, limit - used)
        pct        = round(used / limit * 100) if limit > 0 else 0

        result.append({
            "name":      acc["name"],
            "key_hint":  key[:8] + "..." if key else "not set",
            "limit":     limit,
            "used":      used,
            "remaining": remaining,
            "pct":       pct,
            "active":    remaining > 0 and bool(key),
            "month":     month,
        })

    return result


def get_active_key() -> str | None:
    """
    Returns the first account key that still has credits.
    Automatically switches to next account when one is exhausted.
    """
    usage    = _load_usage()
    month    = _current_month()
    accounts = SERPAPI_ACCOUNTS.copy()

    # Include legacy key
    if SERPAPI_KEY and not any(a["key"] == SERPAPI_KEY for a in accounts):
        accounts.insert(0, {"name": "Default", "key": SERPAPI_KEY, "limit": 100})

    for acc in accounts:
        key   = acc.get("key", "")
        limit = acc.get("limit", 100)
        if not key:
            continue
        used = usage.get(key, {}).get(month, 0)
        if used < limit:
            print(f"  🔑 Using SerpAPI: {acc['name']} "
                  f"({used}/{limit} used this month)")
            return key

    print("⚠️  All SerpAPI accounts exhausted for this month")
    return None


def record_usage(key: str, count: int = 1):
    """Record that `count` searches were used on this key."""
    usage = _load_usage()
    month = _current_month()

    if key not in usage:
        usage[key] = {}
    if month not in usage[key]:
        usage[key][month] = 0

    usage[key][month] += count
    _save_usage(usage)


def reset_usage(key: str = None):
    """
    Reset usage for a specific key or all keys.
    Call this manually if you've upgraded/renewed an account.
    """
    usage = _load_usage()
    month = _current_month()

    if key:
        if key in usage and month in usage[key]:
            usage[key][month] = 0
            print(f"✅ Reset usage for key {key[:8]}...")
    else:
        for k in usage:
            if month in usage[k]:
                usage[k][month] = 0
        print("✅ Reset all account usage for current month")

    _save_usage(usage)