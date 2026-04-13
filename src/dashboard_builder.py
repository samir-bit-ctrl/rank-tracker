import gspread
from google.oauth2 import service_account
from datetime import datetime, timedelta
from config.settings import (
    CREDENTIALS_PATH, SHEET_ID,
    SHEET_NAME_DASHBOARD
)
import json
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ── Colours ───────────────────────────────────────────────────────────
HEADER_DARK  = {"red": 0.192, "green": 0.212, "blue": 0.251}
HEADER_MID   = {"red": 0.271, "green": 0.298, "blue": 0.349}
ACCENT_GREEN = {"red": 0.196, "green": 0.533, "blue": 0.384}
ACCENT_RED   = {"red": 0.757, "green": 0.267, "blue": 0.267}
ACCENT_AMBER = {"red": 0.800, "green": 0.600, "blue": 0.200}
ACCENT_BLUE  = {"red": 0.271, "green": 0.431, "blue": 0.675}
ACCENT_PURPLE= {"red": 0.580, "green": 0.400, "blue": 0.800}
WHITE        = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
OFF_WHITE    = {"red": 0.980, "green": 0.980, "blue": 0.984}
LIGHT_GREY   = {"red": 0.941, "green": 0.945, "blue": 0.953}
MID_GREY     = {"red": 0.827, "green": 0.843, "blue": 0.878}
DARK_TEXT    = {"red": 0.133, "green": 0.149, "blue": 0.180}
SUBTLE_TEXT  = {"red": 0.420, "green": 0.447, "blue": 0.502}


def _col(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}


# ══════════════════════════════════════════════════════════════════════
#  DATA COLLECTORS
# ══════════════════════════════════════════════════════════════════════
def _load_history() -> dict:
    if not os.path.exists("data/history.json"):
        return {}
    with open("data/history.json") as f:
        return json.load(f)


def _get_gsc_keywords(history: dict) -> list:
    """Get latest snapshot keywords."""
    if not history:
        return []
    latest = sorted(history.keys())[-1]
    return list(history[latest].values())


def _get_daily_clicks(history: dict) -> list:
    """Get total clicks per day for trend chart."""
    dates = sorted(history.keys())[-14:]   # last 14 days
    result = []
    for d in dates:
        total_clicks = sum(
            v.get("clicks", 0)
            for v in history[d].values()
        )
        result.append({"date": d, "clicks": total_clicks})
    return result


def _get_avg_position_trend(history: dict) -> list:
    """Get avg position per day."""
    dates = sorted(history.keys())[-14:]
    result = []
    for d in dates:
        positions = [
            v.get("position", 0)
            for v in history[d].values()
            if v.get("position", 0) > 0
        ]
        avg = round(sum(positions) / len(positions), 1) if positions else 0
        result.append({"date": d, "avg_position": avg})
    return result


def _compute_health_score(keywords: list, ai_results: list,
                           target_intel: list) -> dict:
    """Compute site health score out of 100."""
    if not keywords:
        return {"score": 0, "label": "No Data", "color": ACCENT_RED}

    total = len(keywords)

    # Component 1 — % in top 10 (40 points)
    top10     = len([k for k in keywords if k.get("position", 99) <= 10])
    top10_pct = top10 / total
    comp1     = round(top10_pct * 40, 1)

    # Component 2 — CTR benchmark score (30 points)
    expected_ctr = {1: 28, 2: 15, 3: 11, 4: 8, 5: 7,
                    6: 6,  7: 5,  8: 4,  9: 3, 10: 2}
    ctr_scores = []
    for k in keywords:
        pos     = int(k.get("position", 99))
        ctr     = k.get("ctr", 0) * 100 if k.get("ctr", 0) < 1 else k.get("ctr", 0)
        exp_ctr = expected_ctr.get(pos, 1.5)
        score   = min(ctr / exp_ctr, 1.0) if exp_ctr > 0 else 0
        ctr_scores.append(score)
    avg_ctr_score = sum(ctr_scores) / len(ctr_scores) if ctr_scores else 0
    comp2 = round(avg_ctr_score * 30, 1)

    # Component 3 — AI citations (20 points)
    if ai_results:
        cited     = len([r for r in ai_results if r.get("site_cited")])
        ai_score  = cited / len(ai_results)
        comp3     = round(ai_score * 20, 1)
    else:
        comp3 = 10   # neutral if no AI data yet

    # Component 4 — Stability (10 points)
    if target_intel:
        stable = len([
            k for k in target_intel
            if "Stable" in k.get("consistency", "")
        ])
        stab_score = stable / len(target_intel)
        comp4      = round(stab_score * 10, 1)
    else:
        comp4 = 5   # neutral

    total_score = round(comp1 + comp2 + comp3 + comp4)
    total_score = min(total_score, 100)

    if total_score >= 80:
        label = "🟢 Excellent"
        color = ACCENT_GREEN
    elif total_score >= 60:
        label = "🟡 Good"
        color = ACCENT_AMBER
    elif total_score >= 40:
        label = "🟠 Needs Work"
        color = {"red": 0.9, "green": 0.5, "blue": 0.1}
    else:
        label = "🔴 Critical"
        color = ACCENT_RED

    return {
        "score":  total_score,
        "label":  label,
        "color":  color,
        "comp1":  comp1,
        "comp2":  comp2,
        "comp3":  comp3,
        "comp4":  comp4,
    }


def _generate_action_items(keywords: list, report: dict,
                            target_intel: list,
                            ai_results: list) -> list:
    """Auto-generate prioritized action items."""
    actions = []

    # 🚨 Urgent drops
    big_drops = [
        k for k in report.get("dropped", [])
        if abs(k.get("delta", 0)) >= 5
    ]
    for k in big_drops[:3]:
        actions.append({
            "priority": "🚨 URGENT",
            "keyword":  k["keyword"][:45],
            "issue":    f"Dropped {abs(k['delta'])} positions",
            "action":   "Check for algorithm update or content issue",
            "color":    ACCENT_RED
        })

    # ⚡ Fix title/meta — good position bad CTR
    expected_ctr = {1: 28, 2: 15, 3: 11, 4: 8, 5: 7,
                    6: 6,  7: 5,  8: 4,  9: 3, 10: 2}
    for k in sorted(keywords,
                    key=lambda x: x.get("clicks", 0), reverse=True)[:50]:
        pos     = int(k.get("position", 99))
        ctr     = k.get("ctr", 0)
        ctr_pct = ctr * 100 if ctr < 1 else ctr
        exp     = expected_ctr.get(pos, 0)
        if exp > 0 and ctr_pct < exp * 0.5 and pos <= 10:
            actions.append({
                "priority": "⚡ HIGH",
                "keyword":  k["keyword"][:45],
                "issue":    f"CTR {round(ctr_pct, 1)}% (expected ~{exp}% at pos {pos})",
                "action":   "Rewrite title & meta description",
                "color":    ACCENT_AMBER
            })
            if len([a for a in actions if "HIGH" in a["priority"]]) >= 3:
                break

    # 📝 Content gap — high impressions low clicks
    for k in sorted(keywords,
                    key=lambda x: x.get("impressions", 0), reverse=True)[:30]:
        impr    = k.get("impressions", 0)
        clicks  = k.get("clicks", 0)
        pos     = k.get("position", 99)
        if impr > 200 and clicks < 5 and pos > 10:
            actions.append({
                "priority": "📝 MEDIUM",
                "keyword":  k["keyword"][:45],
                "issue":    f"{impr} impressions but only {clicks} clicks (pos {round(pos,1)})",
                "action":   "Improve content depth, add to page 1",
                "color":    ACCENT_BLUE
            })
            if len([a for a in actions if "MEDIUM" in a["priority"]]) >= 3:
                break

    # 🎯 Push to top 3
    for k in sorted(keywords,
                    key=lambda x: x.get("clicks", 0), reverse=True)[:30]:
        pos = k.get("position", 99)
        if 4 <= pos <= 7:
            actions.append({
                "priority": "🎯 OPPORTUNITY",
                "keyword":  k["keyword"][:45],
                "issue":    f"Sitting at position {round(pos, 1)} — so close!",
                "action":   "Add internal links, improve E-E-A-T signals",
                "color":    ACCENT_GREEN
            })
            if len([a for a in actions if "OPPORTUNITY" in a["priority"]]) >= 3:
                break

    # 💀 Lost keywords
    lost = report.get("lost", [])[:3]
    for k in lost:
        actions.append({
            "priority": "💀 LOST",
            "keyword":  k["keyword"][:45],
            "issue":    f"Disappeared from rankings (had {k.get('clicks',0)} clicks)",
            "action":   "Check if page was deleted or deindexed",
            "color":    SUBTLE_TEXT
        })

    # 🤖 AI Overview opportunities
    for r in ai_results:
        if r.get("has_overview") and not r.get("site_cited"):
            org_pos = r.get("organic_pos", 99)
            if org_pos and org_pos <= 5:
                actions.append({
                    "priority": "🤖 AI OPP",
                    "keyword":  r.get("ai_keyword", r.get("keyword", ""))[:45],
                    "issue":    f"AI Overview exists, we rank #{org_pos} but not cited",
                    "action":   "Add FAQ schema, improve answer format",
                    "color":    ACCENT_PURPLE
                })
                if len([a for a in actions if "AI OPP" in a["priority"]]) >= 2:
                    break

    return actions[:15]   # max 15 action items


# ══════════════════════════════════════════════════════════════════════
#  CHART DATA HELPERS
# ══════════════════════════════════════════════════════════════════════
def _top_keywords_by_clicks(keywords: list, n=10) -> list:
    SPAM = ["http", "www.", ".com", ".in", ".org", "survey", "whitecastle"]
    clean = [
        k for k in keywords
        if not any(s in k.get("keyword", "").lower() for s in SPAM)
    ]
    return sorted(clean,
                  key=lambda x: x.get("clicks", 0),
                  reverse=True)[:n]

def _rank_zone_counts(keywords: list) -> dict:
    total = len(keywords) or 1
    zones = {
        "Top 3":   len([k for k in keywords if k.get("position", 99) <= 3]),
        "4-10":    len([k for k in keywords if 3  < k.get("position", 99) <= 10]),
        "11-20":   len([k for k in keywords if 10 < k.get("position", 99) <= 20]),
        "21-50":   len([k for k in keywords if 20 < k.get("position", 99) <= 50]),
        "50+":     len([k for k in keywords if k.get("position", 99) > 50]),
    }
    return {k: {"count": v, "pct": round(v/total*100, 1)}
            for k, v in zones.items()}


def _ctr_by_position_buckets(keywords: list) -> list:
    """Avg CTR grouped by position bucket for chart."""
    buckets = {}
    for k in keywords:
        pos = int(k.get("position", 99))
        if pos > 20:
            continue
        ctr = k.get("ctr", 0)
        ctr_pct = ctr * 100 if ctr < 1 else ctr
        if pos not in buckets:
            buckets[pos] = []
        buckets[pos].append(ctr_pct)
    return [
        {"position": p,
         "avg_ctr": round(sum(v)/len(v), 2)}
        for p, v in sorted(buckets.items())
        if v
    ]


# ══════════════════════════════════════════════════════════════════════
#  MAIN DASHBOARD WRITER
# ══════════════════════════════════════════════════════════════════════
def write_full_dashboard(report: dict,
                         target_intel: list = None,
                         ai_results:   list = None):
    """
    Master function — writes the complete dashboard sheet.
    Call this from main.py instead of the old write_dashboard().
    """
    target_intel = target_intel or []
    ai_results   = ai_results   or []

    print("\n📊 Building full dashboard...")

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    client      = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)

    # Get or create dashboard sheet
    try:
        ws = spreadsheet.worksheet(SHEET_NAME_DASHBOARD)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=SHEET_NAME_DASHBOARD, rows=200, cols=20
        )

    sid   = ws.id
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Load data ─────────────────────────────────────────────────────
    history      = _load_history()
    keywords     = _get_gsc_keywords(history)
    daily_clicks = _get_daily_clicks(history)
    pos_trend    = _get_avg_position_trend(history)
    health       = _compute_health_score(keywords, ai_results, target_intel)
    actions      = _generate_action_items(
        keywords, report, target_intel, ai_results
    )
    zones        = _rank_zone_counts(keywords)
    top_kws      = _top_keywords_by_clicks(keywords, 10)
    ctr_buckets  = _ctr_by_position_buckets(keywords)

    # ── Aggregate stats ───────────────────────────────────────────────
    total_kws    = len(keywords)
    avg_pos      = report.get("avg_position", 0)
    total_clicks = sum(k.get("clicks", 0) for k in keywords)
    total_impr   = sum(k.get("impressions", 0) for k in keywords)
    avg_ctr      = round(
        sum(k.get("ctr", 0) * 100 if k.get("ctr", 0) < 1
            else k.get("ctr", 0)
            for k in keywords) / total_kws, 2
    ) if total_kws else 0
    top3_count   = zones["Top 3"]["count"]
    top10_count  = zones["Top 3"]["count"] + zones["4-10"]["count"]
    ai_cited     = len([r for r in ai_results if r.get("site_cited")])
    ai_total     = len(ai_results)

    # ══════════════════════════════════════════════════════════════════
    #  BUILD ROWS
    # ══════════════════════════════════════════════════════════════════
    rows = []

    # ── Row 1: Title bar ──────────────────────────────────────────────
    rows.append([
        f"📊  SEO DASHBOARD — studyriserr.com",
        "", "", "", "", "", "", "", "", "",
        f"Updated: {today}", "", "", "", "", "", "", "", "", ""
    ])

    # ── Row 2: Spacer ─────────────────────────────────────────────────
    rows.append([""] * 20)

    # ── Rows 3-4: Health Score ────────────────────────────────────────
    rows.append([
        "SITE HEALTH SCORE", "", "",
        "Top 10 Rank", "CTR Score",
        "AI Citations", "Stability", "", "", "",
        "TOTAL KEYWORDS", "", "AVG POSITION", "",
        "TOTAL CLICKS", "", "AVG CTR", "", "", ""
    ])
    rows.append([
        f"{health['score']} / 100", "", "",
        f"{health['comp1']}/40",
        f"{health['comp2']}/30",
        f"{health['comp3']}/20",
        f"{health['comp4']}/10", "", "", "",
        total_kws, "", avg_pos, "",
        total_clicks, "", f"{avg_ctr}%", "", "", ""
    ])

    # ── Row 5: Spacer ─────────────────────────────────────────────────
    rows.append([""] * 20)

    # ── Rows 6-7: More stats ──────────────────────────────────────────
    rows.append([
        "TOP 3 KEYWORDS", "", "TOP 10 KEYWORDS", "",
        "TOTAL IMPRESSIONS", "", "IMPROVED TODAY", "",
        "DROPPED TODAY", "", "NEW TODAY", "",
        "LOST TODAY", "", "AI CITED", "", "", "", "", ""
    ])
    rows.append([
        top3_count, "", top10_count, "",
        total_impr, "", len(report.get("improved", [])), "",
        len(report.get("dropped", [])), "",
        len(report.get("new", [])), "",
        len(report.get("lost", [])), "",
        f"{ai_cited}/{ai_total}" if ai_total else "—",
        "", "", "", "", ""
    ])

    # ── Row 8: Spacer ─────────────────────────────────────────────────
    rows.append([""] * 20)

    

    # ── ACTION ITEMS SECTION ──────────────────────────────────────────
    action_start = len(rows)
    rows.append([""] * 20)
    rows.append([
        "⚡ ACTION ITEMS", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    ])
    rows.append([
        "Priority", "Keyword", "", "",
        "Issue", "", "", "",
        "Recommended Action", "", "", "",
        "", "", "", "", "", "", "", ""
    ])

    action_header_row = len(rows) - 1

    for a in actions:
        rows.append([
            a["priority"],
            a["keyword"], "", "",
            a["issue"], "", "", "",
            a["action"], "", "", "",
            "", "", "", "", "", "", "", ""
        ])

    # ── TARGET KEYWORDS SECTION ───────────────────────────────────────
    target_start = len(rows)
    rows.append([""] * 20)
    rows.append([
        "🎯 TARGET KEYWORDS SUMMARY", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    ])
    rows.append([
        "Keyword", "Status", "Position", "Change",
        "Clicks (7d)", "Impressions", "CTR %",
        "Consistency", "Opportunity", "",
        "", "", "", "", "", "", "", "", "", ""
    ])

    target_header_row = len(rows) - 1

    for k in target_intel:
        delta     = k.get("delta", 0)
        delta_str = f"+{delta}" if delta > 0 else str(delta) if delta != 0 else "—"
        rows.append([
            k.get("keyword", "")[:45],
            k.get("status", ""),
            k.get("current_position", "—"),
            delta_str,
            k.get("clicks_7d", 0),
            k.get("impressions_7d", 0),
            f"{k.get('ctr', 0)}%",
            k.get("consistency", ""),
            k.get("opportunity", ""),
            "", "", "", "", "", "", "", "", "", "", ""
        ])

    # ── AI OVERVIEW SECTION ───────────────────────────────────────────
    ai_start = len(rows)
    rows.append([""] * 20)
    rows.append([
        "🤖 AI OVERVIEW SUMMARY", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    ])
    rows.append([
        "Seed", "Checked Keyword", "AI Overview",
        "We're Cited", "Organic Pos", "Opportunity",
        "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    ])

    ai_header_row = len(rows) - 1

    for r in ai_results:
        overview_str = "✅ Yes" if r.get("has_overview") else "❌ No"
        cited_str    = (
            "🎯 Cited!" if r.get("site_cited")
            else "❌ Not cited" if r.get("has_overview")
            else "—"
        )
        rows.append([
            r.get("seed", "")[:35],
            r.get("ai_keyword", r.get("keyword", ""))[:35],
            overview_str,
            cited_str,
            r.get("organic_pos", "Not ranking"),
            r.get("opportunity", ""),
            "", "", "", "", "", "", "", "", "", "", "", "", "", ""
        ])

    # ── WRITE ALL ROWS ────────────────────────────────────────────────
    ws.update("A1", rows)

    # ══════════════════════════════════════════════════════════════════
    #  FORMATTING
    # ══════════════════════════════════════════════════════════════════
    fmt_requests = []

    
    # Whole sheet background
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid},
        "cell": {"userEnteredFormat": {
            "backgroundColor": OFF_WHITE,
            "textFormat": {"fontSize": 10,
                           "foregroundColor": DARK_TEXT}
        }},
        "fields": "userEnteredFormat"
    }})

    # Title bar
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_DARK,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 13}
        }},
        "fields": "userEnteredFormat"
    }})

    # Health score label row
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 2, "endRowIndex": 3},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_MID,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 9}
        }},
        "fields": "userEnteredFormat"
    }})

    # Health score value row
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 3, "endRowIndex": 4},
        "cell": {"userEnteredFormat": {
            "backgroundColor": WHITE,
            "textFormat": {"fontSize": 15, "bold": True,
                           "foregroundColor": DARK_TEXT}
        }},
        "fields": "userEnteredFormat"
    }})

    # Health score big number color
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 3, "endRowIndex": 4,
                  "startColumnIndex": 0, "endColumnIndex": 1},
        "cell": {"userEnteredFormat": {
            "textFormat": {"foregroundColor": health["color"],
                           "fontSize": 20, "bold": True}
        }},
        "fields": "userEnteredFormat.textFormat"
    }})

    # Second stats label row
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 5, "endRowIndex": 6},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_MID,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 9}
        }},
        "fields": "userEnteredFormat"
    }})

    # Second stats value row
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": 6, "endRowIndex": 7},
        "cell": {"userEnteredFormat": {
            "backgroundColor": WHITE,
            "textFormat": {"fontSize": 14, "bold": True,
                           "foregroundColor": DARK_TEXT}
        }},
        "fields": "userEnteredFormat"
    }})

    # Action items section title
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": action_start + 1,
                  "endRowIndex":   action_start + 2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_DARK,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 11}
        }},
        "fields": "userEnteredFormat"
    }})

    # Action items column header
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": action_header_row,
                  "endRowIndex":   action_header_row + 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_MID,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 9}
        }},
        "fields": "userEnteredFormat"
    }})

    # Color code action priority cells
    for i, a in enumerate(actions):
        row_idx = action_header_row + 1 + i
        fmt_requests.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex":    row_idx,
                      "endRowIndex":      row_idx + 1,
                      "startColumnIndex": 0,
                      "endColumnIndex":   1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"foregroundColor": a["color"],
                               "bold": True}
            }},
            "fields": "userEnteredFormat.textFormat"
        }})

    # Target keywords section title
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": target_start + 1,
                  "endRowIndex":   target_start + 2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_DARK,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 11}
        }},
        "fields": "userEnteredFormat"
    }})

    # Target keywords column header
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": target_header_row,
                  "endRowIndex":   target_header_row + 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_MID,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 9}
        }},
        "fields": "userEnteredFormat"
    }})

    # AI Overview section title
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": ai_start + 1,
                  "endRowIndex":   ai_start + 2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_DARK,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 11}
        }},
        "fields": "userEnteredFormat"
    }})

    # AI Overview column header
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": ai_header_row,
                  "endRowIndex":   ai_header_row + 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": HEADER_MID,
            "textFormat": {"foregroundColor": WHITE,
                           "bold": True, "fontSize": 9}
        }},
        "fields": "userEnteredFormat"
    }})

    # Alternating rows for all data sections
    for start_row in [action_header_row + 1,
                      target_header_row + 1,
                      ai_header_row + 1]:
        fmt_requests.append({"addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sid,
                            "startRowIndex": start_row}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": "=ISEVEN(ROW())"}]
                    },
                    "format": {"backgroundColor": LIGHT_GREY}
                }
            },
            "index": 0
        }})

    # Hide gridlines
    fmt_requests.append({"updateSheetProperties": {
        "properties": {
            "sheetId": sid,
            "gridProperties": {
                "frozenRowCount":    1,
                "hideGridlines":     True
            }
        },
        "fields": "gridProperties.frozenRowCount,"
                  "gridProperties.hideGridlines"
    }})

    # Column widths
    col_widths = [
        (0, 1,   200),   # A — keyword/metric
        (1, 2,   150),   # B
        (2, 4,   120),   # C-D
        (4, 6,   130),   # E-F
        (6, 8,   110),   # G-H
        (8, 10,  200),   # I-J action
        (10, 14, 100),   # K-N
        (14, 16, 130),   # O-P
        (16, 18, 200),   # Q-R top keywords
    ]
    for start, end, size in col_widths:
        fmt_requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": start, "endIndex": end},
            "properties": {"pixelSize": size},
            "fields": "pixelSize"
        }})

    # Row heights for stat rows
    for row_idx in [3, 6]:
        fmt_requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS",
                      "startIndex": row_idx,
                      "endIndex":   row_idx + 1},
            "properties": {"pixelSize": 44},
            "fields": "pixelSize"
        }})

    # Apply all formatting
    spreadsheet.batch_update({"requests": fmt_requests})
    
    print("✅ Full dashboard written")
    print(f"   Health Score : {health['score']}/100 {health['label']}")
    print(f"   Action Items : {len(actions)}")