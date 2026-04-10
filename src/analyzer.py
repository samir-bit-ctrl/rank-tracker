from src.history_manager import get_latest_two_snapshots

# ── Spam / junk keyword filter ─────────────────────────────────────────────
SPAM_PATTERNS = [
    "http", "www.", ".com", ".in", ".org",   # URLs as queries
    "survey", "whitecastle",                  # known spam
]

POSITION_THRESHOLD = 3   # minimum change to flag


def is_spam(keyword: str) -> bool:
    """Return True if keyword looks like spam/bot query."""
    kw = keyword.lower()
    return any(pattern in kw for pattern in SPAM_PATTERNS)


def clean_keywords(data: dict) -> dict:
    """Remove spam keywords from a snapshot dict."""
    return {k: v for k, v in data.items() if not is_spam(k)}


def analyze_changes():
    """
    Compare today vs yesterday snapshots.
    Returns a structured report dict.
    """
    today_raw, yesterday_raw, today_date, yesterday_date = get_latest_two_snapshots()

    if not today_raw:
        print("⚠️  No data in history yet. Run main.py first.")
        return None

    # Clean spam
    today     = clean_keywords(today_raw)
    yesterday = clean_keywords(yesterday_raw) if yesterday_raw else {}

    today_keys     = set(today.keys())
    yesterday_keys = set(yesterday.keys())

    improved = []
    dropped  = []
    new_kws  = []
    lost_kws = []
    stable   = []

    # New keywords (in today but not yesterday)
    for kw in today_keys - yesterday_keys:
        new_kws.append(today[kw])

    # Lost keywords (in yesterday but not today)
    for kw in yesterday_keys - today_keys:
        lost_kws.append(yesterday[kw])

    # Changed or stable keywords
    for kw in today_keys & yesterday_keys:
        today_pos     = today[kw]["position"]
        yesterday_pos = yesterday[kw]["position"]
        delta         = round(yesterday_pos - today_pos, 1)  # positive = improved

        entry = {
            **today[kw],
            "previous_position": yesterday_pos,
            "delta": delta
        }

        if delta >= POSITION_THRESHOLD:
            improved.append(entry)
        elif delta <= -POSITION_THRESHOLD:
            dropped.append(entry)
        else:
            stable.append(entry)

    # Sort each list
    improved.sort(key=lambda x: x["delta"], reverse=True)
    dropped.sort(key=lambda x: x["delta"])
    new_kws.sort(key=lambda x: x["clicks"], reverse=True)
    lost_kws.sort(key=lambda x: x["clicks"], reverse=True)

    # Summary stats
    all_positions = [v["position"] for v in today.values()]
    avg_position  = round(sum(all_positions) / len(all_positions), 1) if all_positions else 0

    report = {
        "today_date":     today_date,
        "yesterday_date": yesterday_date,
        "total_keywords": len(today),
        "avg_position":   avg_position,
        "improved":       improved,
        "dropped":        dropped,
        "new":            new_kws,
        "lost":           lost_kws,
        "stable":         stable,
    }

    _print_report(report)
    return report


def _print_report(r: dict):
    """Pretty print the analysis report to terminal."""
    print(f"\n{'='*55}")
    print(f"  📊 Rank Analysis — {r['today_date']}")
    print(f"  vs previous: {r['yesterday_date'] or 'N/A (first run)'}")
    print(f"{'='*55}")
    print(f"  Total Keywords : {r['total_keywords']}")
    print(f"  Avg Position   : {r['avg_position']}")
    print(f"  🟢 Improved    : {len(r['improved'])}")
    print(f"  🔴 Dropped     : {len(r['dropped'])}")
    print(f"  🆕 New         : {len(r['new'])}")
    print(f"  💀 Lost        : {len(r['lost'])}")
    print(f"{'='*55}")

    if r["improved"]:
        print("\n🟢 TOP GAINERS")
        for kw in r["improved"][:5]:
            print(f"  {kw['keyword']:<45} {kw['previous_position']} → {kw['position']} (+{kw['delta']})")

    if r["dropped"]:
        print("\n🔴 TOP DROPS")
        for kw in r["dropped"][:5]:
            print(f"  {kw['keyword']:<45} {kw['previous_position']} → {kw['position']} ({kw['delta']})")

    if r["new"]:
        print("\n🆕 NEW KEYWORDS")
        for kw in r["new"][:5]:
            print(f"  {kw['keyword']:<45} Pos: {kw['position']}  Clicks: {kw['clicks']}")

    if r["lost"]:
        print("\n💀 LOST KEYWORDS")
        for kw in r["lost"][:5]:
            print(f"  {kw['keyword']:<45} Was: {kw['position']}  Clicks: {kw['clicks']}")

    print()