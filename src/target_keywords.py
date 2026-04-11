import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from config.settings import (
    CREDENTIALS_PATH, SHEET_ID,
    SITE_URL
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/webmasters.readonly"
]

# ── Sheet names ───────────────────────────────────────────────────────
SHEET_INPUT  = "🎯 Target Keywords"
SHEET_OUTPUT = "📌 Keyword Intel"

# ── Colours (muted elegant palette) ──────────────────────────────────
HEADER_DARK   = {"red": 0.192, "green": 0.212, "blue": 0.251}
HEADER_MID    = {"red": 0.271, "green": 0.298, "blue": 0.349}
ACCENT_GREEN  = {"red": 0.196, "green": 0.533, "blue": 0.384}
ACCENT_RED    = {"red": 0.757, "green": 0.267, "blue": 0.267}
ACCENT_AMBER  = {"red": 0.800, "green": 0.600, "blue": 0.200}
ACCENT_BLUE   = {"red": 0.271, "green": 0.431, "blue": 0.675}
WHITE         = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
OFF_WHITE     = {"red": 0.980, "green": 0.980, "blue": 0.984}
LIGHT_GREY    = {"red": 0.941, "green": 0.945, "blue": 0.953}
SUBTLE_TEXT   = {"red": 0.420, "green": 0.447, "blue": 0.502}
DARK_TEXT     = {"red": 0.133, "green": 0.149, "blue": 0.180}


# ══════════════════════════════════════════════════════════════════════
#  CLIENTS
# ══════════════════════════════════════════════════════════════════════
def _get_clients():
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    sheets_client = gspread.authorize(creds)
    gsc_service   = build("searchconsole", "v1", credentials=creds)
    return sheets_client, gsc_service


# ══════════════════════════════════════════════════════════════════════
#  READ TARGET KEYWORDS FROM INPUT SHEET
# ══════════════════════════════════════════════════════════════════════
def read_target_keywords(spreadsheet) -> list:
    """
    Read keywords + mode from 🎯 Target Keywords sheet.
    Returns list of dicts: {seed, mode}
    mode = 'exact' or 'expanded'
    """
    try:
        ws      = spreadsheet.worksheet(SHEET_INPUT)
        all_vals = ws.get_all_values()

        keywords = []
        for row in all_vals[1:]:   # skip header
            if not row or not row[0].strip():
                continue
            seed = row[0].strip().lower()
            mode = row[1].strip().lower() if len(row) > 1 and row[1].strip() else "exact"
            if mode not in ("exact", "expanded"):
                mode = "exact"
            keywords.append({"seed": seed, "mode": mode})

        exact    = [k for k in keywords if k["mode"] == "exact"]
        expanded = [k for k in keywords if k["mode"] == "expanded"]
        print(f"📋 Found {len(keywords)} target keywords "
              f"({len(exact)} exact, {len(expanded)} expanded)")
        return keywords

    except gspread.WorksheetNotFound:
        print(f"⚠️  Sheet '{SHEET_INPUT}' not found — create it first")
        return []

# ══════════════════════════════════════════════════════════════════════
#  Expands Targeted Keywords (like jee mains - jee mains syllabus,jee mains dates)
# ══════════════════════════════════════════════════════════════════════
def expand_keywords(targets: list) -> dict:
    """
    For expanded seeds, find all matching keywords from history.json.
    Returns dict: {seed: [matching_keyword, ...]}
    """
    import json, os

    history_file = "data/history.json"
    if not os.path.exists(history_file):
        print("⚠️  No history.json found — run a scan first")
        return {}

    with open(history_file) as f:
        history = json.load(f)

    # Get latest snapshot
    if not history:
        return {}

    latest_date = sorted(history.keys())[-1]
    all_kws     = list(history[latest_date].keys())

    expansion_map = {}

    for target in targets:
        seed = target["seed"]
        mode = target["mode"]

        if mode == "exact":
            expansion_map[seed] = [seed]
        else:
            # Find all keywords containing the seed
            matches = [
                kw for kw in all_kws
                if seed.lower() in kw.lower()
            ]
            # Sort by clicks descending
            matches.sort(
                key=lambda k: history[latest_date].get(k, {}).get("clicks", 0),
                reverse=True
            )
            if not matches:
                print(f"  ⚠️  No matches found for seed '{seed}' — tracking exact")
                expansion_map[seed] = [seed]
            else:
                print(f"  🔍 '{seed}' → {len(matches)} keywords found")
                for m in matches[:5]:   # preview top 5
                    clicks = history[latest_date].get(m, {}).get("clicks", 0)
                    print(f"      • {m} ({clicks} clicks)")
                expansion_map[seed] = matches

    return expansion_map


# ══════════════════════════════════════════════════════════════════════
#  FETCH GSC DATA FOR TARGET KEYWORDS
# ══════════════════════════════════════════════════════════════════════
def fetch_target_data(gsc_service, keywords: list) -> dict:
    """
    Fetch 7-day GSC data for each target keyword individually.
    Returns dict: {keyword: {day: {position, clicks, impressions, ctr, url}}}
    """
    if not keywords:
        return {}

    end_date   = datetime.today() - timedelta(days=3)
    start_date = end_date - timedelta(days=6)  # 7 days total

    results = {}

    print(f"📡 Fetching GSC data for {len(keywords)} target keywords...")

    for kw in keywords:
        try:
            # ── Daily breakdown for trend ─────────────────────────────
            daily_response = gsc_service.searchanalytics().query(
                siteUrl=SITE_URL,
                body={
                    "startDate":  start_date.strftime("%Y-%m-%d"),
                    "endDate":    end_date.strftime("%Y-%m-%d"),
                    "dimensions": ["date", "query", "page"],
                    "dimensionFilterGroups": [{
                        "filters": [{
                            "dimension":  "query",
                            "operator":   "equals",
                            "expression": kw
                        }]
                    }],
                    "rowLimit": 50
                }
            ).execute()

            rows = daily_response.get("rows", [])

            # Aggregate by date
            by_date = {}
            top_url = {}
            for row in rows:
                date  = row["keys"][0]
                url   = row["keys"][2] if len(row["keys"]) > 2 else ""
                if date not in by_date:
                    by_date[date] = {
                        "position":    row["position"],
                        "clicks":      row["clicks"],
                        "impressions": row["impressions"],
                        "ctr":         row["ctr"] * 100
                    }
                    top_url[date] = url
                else:
                    # Keep best position for that day
                    if row["position"] < by_date[date]["position"]:
                        by_date[date]["position"] = row["position"]
                        top_url[date] = url
                    by_date[date]["clicks"]      += row["clicks"]
                    by_date[date]["impressions"] += row["impressions"]

            results[kw] = {
                "daily":   by_date,
                "top_url": top_url
            }

        except Exception as e:
            print(f"  ⚠️  Could not fetch '{kw}': {e}")
            results[kw] = {"daily": {}, "top_url": {}}

    return results


# ══════════════════════════════════════════════════════════════════════
#  COMPUTE INTEL FOR EACH KEYWORD
# ══════════════════════════════════════════════════════════════════════
def compute_intel(keyword: str, data: dict, history: dict) -> dict:
    """
    Compute all metrics for a single target keyword.
    """
    daily   = data.get("daily", {})
    top_url = data.get("top_url", {})
    dates   = sorted(daily.keys())

    if not dates:
        return {
            "keyword":          keyword,
            "current_position": "—",
            "prev_position":    "—",
            "delta":            0,
            "clicks_7d":        0,
            "impressions_7d":   0,
            "ctr":              0,
            "best_position":    "—",
            "worst_position":   "—",
            "trend":            [],
            "ranking_url":      "—",
            "status":           "❌ Not Ranking",
            "opportunity":      "—",
            "consistency":      "—",
        }

    # Current = most recent day
    latest      = daily[dates[-1]]
    curr_pos    = round(latest["position"], 1)
    ranking_url = top_url.get(dates[-1], "—")

    # Previous day position
    prev_pos = None
    if len(dates) >= 2:
        prev_pos = round(daily[dates[-2]]["position"], 1)

    delta = round(prev_pos - curr_pos, 1) if prev_pos else 0

    # 7-day aggregates
    total_clicks      = sum(d["clicks"]      for d in daily.values())
    total_impressions = sum(d["impressions"] for d in daily.values())
    avg_ctr = round(
        sum(d["ctr"] for d in daily.values()) / len(daily), 2
    ) if daily else 0

    # Best / worst positions
    positions    = [round(d["position"], 1) for d in daily.values()]
    best_pos     = min(positions)
    worst_pos    = max(positions)

    # 7-day trend list (for sparkline)
    all_dates = [
        (datetime.today() - timedelta(days=3) - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(6, -1, -1)
    ]
    trend = []
    for d in all_dates:
        if d in daily:
            trend.append(round(daily[d]["position"], 1))
        else:
            trend.append(None)

    # Status
    if curr_pos <= 3:
        status = "🚀 Top 3"
    elif curr_pos <= 10:
        status = "✅ Top 10"
    elif curr_pos <= 20:
        status = "📊 Page 2"
    elif delta > 0:
        status = "📈 Rising"
    elif delta < -3:
        status = "📉 Falling"
    else:
        status = "➡️ Stable"

    # Opportunity score
    # Expected CTR by position (rough benchmarks)
    expected_ctr = {1: 28, 2: 15, 3: 11, 4: 8, 5: 7,
                    6: 6,  7: 5,  8: 4,  9: 3, 10: 2}
    pos_int      = int(curr_pos)
    exp          = expected_ctr.get(pos_int, 1.5)
    if avg_ctr < exp * 0.6:
        opportunity = "⚡ Fix Title/Meta"
    elif avg_ctr < exp * 0.8:
        opportunity = "🔍 Improve Snippet"
    elif total_impressions > 500 and curr_pos > 10:
        opportunity = "📝 Needs Content"
    elif delta >= 3:
        opportunity = "🎯 Keep Pushing"
    else:
        opportunity = "✅ On Track"

    # Consistency (std deviation of positions)
    if len(positions) >= 3:
        mean  = sum(positions) / len(positions)
        std   = (sum((p - mean) ** 2 for p in positions) / len(positions)) ** 0.5
        if std <= 1.5:
            consistency = "🟢 Very Stable"
        elif std <= 3:
            consistency = "🟡 Moderate"
        else:
            consistency = "🔴 Volatile"
    else:
        consistency = "⚪ Insufficient data"

    return {
        "keyword":          keyword,
        "current_position": curr_pos,
        "prev_position":    prev_pos or "—",
        "delta":            delta,
        "clicks_7d":        int(total_clicks),
        "impressions_7d":   int(total_impressions),
        "ctr":              avg_ctr,
        "best_position":    best_pos,
        "worst_position":   worst_pos,
        "trend":            trend,
        "ranking_url":      ranking_url,
        "status":           status,
        "opportunity":      opportunity,
        "consistency":      consistency,
    }

# ══════════════════════════════════════════════════════════════════════
#  COMPUTE INTEL FOR GROUP OF KEYWORDS
# ══════════════════════════════════════════════════════════════════════
def compute_group_intel(seed: str, matched_keywords: list,
                        raw_data: dict) -> dict:
    """
    For expanded seeds, aggregate intel across all matched keywords.
    Returns one summary row + individual breakdown.
    """
    # Compute intel for each matched keyword
    individuals = []
    for kw in matched_keywords:
        intel = compute_intel(kw, raw_data.get(kw, {}), {})
        individuals.append(intel)

    # Filter out not-ranking
    ranking = [k for k in individuals if k["current_position"] != "—"]

    if not ranking:
        return {
            "seed":          seed,
            "mode":          "expanded",
            "total_variants": len(matched_keywords),
            "ranking_count": 0,
            "best_keyword":  "—",
            "best_position": "—",
            "total_clicks":  0,
            "total_impressions": 0,
            "avg_ctr":       0,
            "avg_position":  "—",
            "top_opportunity": "❌ Nothing Ranking",
            "individuals":   individuals,
        }

    # Aggregate
    total_clicks       = sum(k["clicks_7d"]      for k in ranking)
    total_impressions  = sum(k["impressions_7d"] for k in ranking)
    avg_ctr            = round(
        sum(k["ctr"] for k in ranking) / len(ranking), 2
    )
    avg_position       = round(
        sum(k["current_position"] for k in ranking) / len(ranking), 1
    )

    # Best performing keyword
    best = min(ranking, key=lambda k: k["current_position"])

    # Top opportunity across group
    opportunities = [k["opportunity"] for k in ranking]
    fix_title  = opportunities.count("⚡ Fix Title/Meta")
    needs_content = opportunities.count("📝 Needs Content")
    if fix_title >= len(ranking) * 0.4:
        top_opp = f"⚡ Fix Title/Meta ({fix_title} pages)"
    elif needs_content >= len(ranking) * 0.3:
        top_opp = f"📝 Needs Content ({needs_content} pages)"
    else:
        top_opp = "✅ On Track"

    return {
        "seed":              seed,
        "mode":              "expanded",
        "total_variants":    len(matched_keywords),
        "ranking_count":     len(ranking),
        "best_keyword":      best["keyword"],
        "best_position":     best["current_position"],
        "total_clicks":      total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr":           avg_ctr,
        "avg_position":      avg_position,
        "top_opportunity":   top_opp,
        "individuals":       individuals,
    }



# ══════════════════════════════════════════════════════════════════════
#  WRITE KEYWORD INTEL SHEET
# ══════════════════════════════════════════════════════════════════════
def write_intel_sheet(spreadsheet, intel_list: list,
                      group_intel_list: list):
    """
    Write two sections:
    - Section 1: Expanded seed groups summary
    - Section 2: All individual keywords (exact + expanded variants)
    """
    try:
        ws = spreadsheet.worksheet(SHEET_OUTPUT)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=SHEET_OUTPUT, rows=1000, cols=22
        )

    sid   = ws.id
    today = datetime.today().strftime("%Y-%m-%d %H:%M")
    rows  = []

    # ══════════════════════════════════════════════════════════════════
    #  SECTION 1 — SEED GROUP SUMMARY (expanded keywords only)
    # ══════════════════════════════════════════════════════════════════
    expanded_groups = [g for g in group_intel_list if g["mode"] == "expanded"]

    if expanded_groups:
        rows.append([f"🔍 SEED GROUP SUMMARY — {today}",
                     "", "", "", "", "", "", "", "", ""])
        rows.append([
            "Seed Keyword", "Variants Found", "Ranking",
            "Best Keyword", "Best Pos", "Avg Pos",
            "Total Clicks", "Total Impr", "Avg CTR %",
            "Top Opportunity"
        ])

        for g in expanded_groups:
            rows.append([
                g["seed"],
                g["total_variants"],
                g["ranking_count"],
                g["best_keyword"][:45] if g["best_keyword"] != "—" else "—",
                g["best_position"],
                g["avg_position"],
                g["total_clicks"],
                g["total_impressions"],
                f"{g['avg_ctr']}%",
                g["top_opportunity"],
            ])

        rows.append([""])   # spacer

    # ══════════════════════════════════════════════════════════════════
    #  SECTION 2 — INDIVIDUAL KEYWORD INTEL
    # ══════════════════════════════════════════════════════════════════
    trend_dates = [
        (datetime.today() - timedelta(days=3) - timedelta(days=i)
         ).strftime("%d %b")
        for i in range(6, -1, -1)
    ]

    section2_start = len(rows)

    rows.append([f"📌 INDIVIDUAL KEYWORD INTEL", "", "", "", "",
                 "", "", "", "", "", "", "", "", ""] + trend_dates)
    rows.append([
        "Keyword", "Seed", "Mode",
        "Status", "Current Pos", "Prev Pos", "Change (Δ)",
        "Best (7d)", "Worst (7d)",
        "Clicks (7d)", "Impressions (7d)", "CTR %",
        "Consistency", "Opportunity", "Ranking URL",
    ] + trend_dates)

    section2_header = len(rows) - 1   # row index of column header

    for intel in intel_list:
        delta     = intel["delta"]
        delta_str = f"+{delta}" if delta > 0 else str(delta) if delta != 0 else "—"
        trend_vals = [
            str(p) if p is not None else "—"
            for p in intel["trend"]
        ]
        rows.append([
            intel["keyword"],
            intel.get("seed", intel["keyword"]),
            intel.get("mode", "exact"),
            intel["status"],
            intel["current_position"],
            intel["prev_position"],
            delta_str,
            intel["best_position"],
            intel["worst_position"],
            intel["clicks_7d"],
            intel["impressions_7d"],
            f"{intel['ctr']}%",
            intel["consistency"],
            intel["opportunity"],
            intel["ranking_url"],
        ] + trend_vals)

    ws.update("A1", rows)

    # ── Formatting ────────────────────────────────────────────────────
    requests = [
        # Whole sheet background
        {"repeatCell": {
            "range": {"sheetId": sid},
            "cell": {"userEnteredFormat": {
                "backgroundColor": OFF_WHITE,
                "textFormat": {"fontSize": 10,
                               "foregroundColor": DARK_TEXT}
            }},
            "fields": "userEnteredFormat"
        }},
        # Section 1 title
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE,
                               "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        # Section 1 column headers
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_MID,
                "textFormat": {"foregroundColor": LIGHT_GREY,
                               "bold": True, "fontSize": 9}
            }},
            "fields": "userEnteredFormat"
        }},
        # Section 2 title
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": section2_start,
                      "endRowIndex": section2_start + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE,
                               "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        # Section 2 column headers
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": section2_header,
                      "endRowIndex":   section2_header + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_MID,
                "textFormat": {"foregroundColor": LIGHT_GREY,
                               "bold": True, "fontSize": 9}
            }},
            "fields": "userEnteredFormat"
        }},
        # Alternating rows section 2
        {"addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sid,
                            "startRowIndex": section2_header + 1}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": "=ISEVEN(ROW())"}]
                    },
                    "format": {"backgroundColor": LIGHT_GREY}
                }
            },
            "index": 0
        }},
        # Freeze
        {"updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {
                    "frozenRowCount":    section2_header + 1,
                    "frozenColumnCount": 1,
                    "hideGridlines":     True
                }
            },
            "fields": "gridProperties.frozenRowCount,"
                      "gridProperties.frozenColumnCount,"
                      "gridProperties.hideGridlines"
        }},
        # Column widths
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 240}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": 15},
            "properties": {"pixelSize": 110}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 14, "endIndex": 15},
            "properties": {"pixelSize": 260}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 15, "endIndex": 22},
            "properties": {"pixelSize": 65}, "fields": "pixelSize"
        }},
    ]

    # Delta color coding
    individual_start = section2_header + 1
    for i, intel in enumerate(intel_list):
        row_idx = individual_start + i
        delta   = intel["delta"]
        if delta >= 3:      color = ACCENT_GREEN
        elif delta <= -3:   color = ACCENT_RED
        elif delta != 0:    color = ACCENT_AMBER
        else:               color = {"red": 0.6, "green": 0.6, "blue": 0.6}

        requests.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex":    row_idx,
                      "endRowIndex":      row_idx + 1,
                      "startColumnIndex": 6,
                      "endColumnIndex":   7},
            "cell": {"userEnteredFormat": {
                "textFormat": {"foregroundColor": color, "bold": True}
            }},
            "fields": "userEnteredFormat.textFormat"
        }})

        # Trend cell colors
        for j, pos in enumerate(intel["trend"]):
            if pos is None:
                continue
            col_idx = 15 + j
            if pos <= 3:    tc = ACCENT_AMBER
            elif pos <= 10: tc = ACCENT_GREEN
            elif pos <= 20: tc = ACCENT_BLUE
            else:           tc = ACCENT_RED
            requests.append({"repeatCell": {
                "range": {"sheetId": sid,
                          "startRowIndex":    row_idx,
                          "endRowIndex":      row_idx + 1,
                          "startColumnIndex": col_idx,
                          "endColumnIndex":   col_idx + 1},
                "cell": {"userEnteredFormat": {
                    "textFormat": {"foregroundColor": tc, "bold": True}
                }},
                "fields": "userEnteredFormat.textFormat"
            }})

    try:
        spreadsheet.batch_update({"requests": requests})
    except Exception as e:
        print(f"⚠️  Formatting error: {e}")

    print(f"✅ Keyword Intel sheet written — "
          f"{len(expanded_groups)} seed groups, "
          f"{len(intel_list)} individual keywords")

# ══════════════════════════════════════════════════════════════════════
#  BUILD ALERT REPORT
# ══════════════════════════════════════════════════════════════════════
def build_target_alert(intel_list: list) -> str | None:
    """
    Build a Telegram alert specifically for target keywords.
    Only sends if something significant happened.
    """
    big_gains  = [k for k in intel_list if k["delta"] >= 3]
    big_drops  = [k for k in intel_list if k["delta"] <= -3]
    not_ranking = [k for k in intel_list if k["current_position"] == "—"]
    top3       = [k for k in intel_list if
                  isinstance(k["current_position"], float)
                  and k["current_position"] <= 3]

    if not big_gains and not big_drops and not not_ranking:
        return None

    today = datetime.today().strftime("%Y-%m-%d")
    lines = [
        f"🎯 <b>Target Keywords Alert</b>",
        f"📅 {today}",
        f"{'─' * 30}",
        f"Tracking <b>{len(intel_list)}</b> target keywords\n",
    ]

    if top3:
        lines.append("🥇 <b>In Top 3</b>")
        for k in top3:
            lines.append(
                f"  <code>{k['keyword'][:40]}</code> → Pos <b>{k['current_position']}</b>"
            )
        lines.append("")

    if big_gains:
        lines.append("📈 <b>Big Jumps</b>")
        for k in big_gains:
            lines.append(
                f"  🟢 <code>{k['keyword'][:40]}</code>\n"
                f"     {k['prev_position']} → <b>{k['current_position']}</b> "
                f"<i>(+{k['delta']})</i>  {k['opportunity']}"
            )
        lines.append("")

    if big_drops:
        lines.append("📉 <b>Big Drops</b>")
        for k in big_drops:
            lines.append(
                f"  🔴 <code>{k['keyword'][:40]}</code>\n"
                f"     {k['prev_position']} → <b>{k['current_position']}</b> "
                f"<i>({k['delta']})</i>  {k['opportunity']}"
            )
        lines.append("")

    if not_ranking:
        lines.append("❌ <b>Not Ranking</b>")
        for k in not_ranking:
            lines.append(f"  ⚪ <code>{k['keyword'][:40]}</code>")
        lines.append("")

    lines.append(f"{'─' * 30}")
    lines.append(f"📊 <b>Quick Summary</b>")
    lines.append(f"  Top 3: <b>{len(top3)}</b>  |  Improved: <b>{len(big_gains)}</b>  |  Dropped: <b>{len(big_drops)}</b>")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════
def run_target_tracker():
    """Full pipeline — handles both exact and expanded keywords."""
    print("\n🎯 Running Target Keyword Tracker...")

    sheets_client, gsc_service = _get_clients()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)

    # Step 1 — Read seeds + modes from sheet
    targets = read_target_keywords(spreadsheet)
    if not targets:
        print("⚠️  No target keywords found — skipping")
        return None

    # Step 2 — Expand seeds into full keyword lists
    expansion_map = expand_keywords(targets)

    # Step 3 — Collect all unique keywords to fetch from GSC
    all_keywords_to_fetch = list({
        kw
        for kws in expansion_map.values()
        for kw in kws
    })
    print(f"\n📡 Total unique keywords to fetch: {len(all_keywords_to_fetch)}")

    # Step 4 — Fetch GSC data
    raw_data = fetch_target_data(gsc_service, all_keywords_to_fetch)

    # Step 5 — Compute intel
    intel_list        = []
    group_intel_list  = []

    for target in targets:
        seed    = target["seed"]
        mode    = target["mode"]
        matches = expansion_map.get(seed, [seed])

        if mode == "expanded":
            # Group summary
            group = compute_group_intel(seed, matches, raw_data)
            group_intel_list.append(group)

            # Individual rows with seed tag
            for intel in group["individuals"]:
                intel["seed"] = seed
                intel["mode"] = "expanded"
                intel_list.append(intel)
        else:
            # Exact — single keyword
            intel = compute_intel(seed, raw_data.get(seed, {}), {})
            intel["seed"] = seed
            intel["mode"] = "exact"
            intel_list.append(intel)
            group_intel_list.append({
                "seed": seed, "mode": "exact",
                **intel
            })

    # Step 6 — Write sheet
    write_intel_sheet(spreadsheet, intel_list, group_intel_list)

    # Step 7 — Build alert
    alert = build_target_alert(intel_list)

    print(f"✅ Done — {len(targets)} seeds → {len(intel_list)} keywords tracked")
    return {"intel": intel_list, "groups": group_intel_list, "alert": alert}