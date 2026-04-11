import time
import json
import os
from datetime import datetime
import gspread
from google.oauth2 import service_account
from serpapi import GoogleSearch
from config.settings import (
    CREDENTIALS_PATH, SHEET_ID, SERPAPI_KEY
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_NAME = "🤖 AI Overview"

# ── Colours ───────────────────────────────────────────────────────────
HEADER_DARK  = {"red": 0.192, "green": 0.212, "blue": 0.251}
HEADER_MID   = {"red": 0.271, "green": 0.298, "blue": 0.349}
ACCENT_GREEN = {"red": 0.196, "green": 0.533, "blue": 0.384}
ACCENT_RED   = {"red": 0.757, "green": 0.267, "blue": 0.267}
ACCENT_BLUE  = {"red": 0.271, "green": 0.431, "blue": 0.675}
ACCENT_AMBER = {"red": 0.800, "green": 0.600, "blue": 0.200}
WHITE        = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
OFF_WHITE    = {"red": 0.980, "green": 0.980, "blue": 0.984}
LIGHT_GREY   = {"red": 0.941, "green": 0.945, "blue": 0.953}
DARK_TEXT    = {"red": 0.133, "green": 0.149, "blue": 0.180}
SUBTLE_TEXT  = {"red": 0.420, "green": 0.447, "blue": 0.502}


# ══════════════════════════════════════════════════════════════════════
#  SERP FETCH
# ══════════════════════════════════════════════════════════════════════
def check_ai_overview(keyword: str, site: str) -> dict:
    """
    Check if a keyword has an AI Overview and if our site is cited.
    Returns structured result dict.
    """
    if not SERPAPI_KEY:
        return {"error": "No SERPAPI_KEY configured"}

    try:
        search = GoogleSearch({
            "q":           keyword,
            "api_key":     SERPAPI_KEY,
            "gl":          "in",      # India
            "hl":          "en",
            "num":         10,
            "no_cache":    False,     # use cache to save credits
        })

        results = search.get_dict()

        # ── Check for AI Overview ─────────────────────────────────────
        ai_overview  = results.get("ai_overview", {})
        has_overview = bool(ai_overview)

        # ── Extract cited sources ─────────────────────────────────────
        cited_urls   = []
        site_cited   = False
        cite_snippet = ""

        if has_overview:
            # Sources can be in different places depending on SERP format
            sources = (
                ai_overview.get("sources", []) or
                ai_overview.get("references", []) or
                []
            )
            for source in sources:
                url = source.get("link", "") or source.get("url", "")
                if url:
                    cited_urls.append(url)
                    if site.lower().replace("https://", "").replace("www.", "") \
                       in url.lower():
                        site_cited   = True
                        cite_snippet = source.get("title", "")

        # ── Organic position ──────────────────────────────────────────
        organic      = results.get("organic_results", [])
        organic_pos  = None
        organic_url  = ""
        for i, r in enumerate(organic):
            link = r.get("link", "")
            if site.lower().replace("https://", "").replace("www.", "") \
               in link.lower():
                organic_pos = i + 1
                organic_url = link
                break

        # ── Related searches ──────────────────────────────────────────
        related = [
            r.get("query", "")
            for r in results.get("related_searches", [])[:5]
        ]

        # ── People Also Ask ───────────────────────────────────────────
        paa = [
            q.get("question", "")
            for q in results.get("related_questions", [])[:4]
        ]

        # ── Credits used ──────────────────────────────────────────────
        credits_left = results.get(
            "search_metadata", {}
        ).get("credits_remaining", "?")

        return {
            "keyword":       keyword,
            "has_overview":  has_overview,
            "site_cited":    site_cited,
            "cite_snippet":  cite_snippet,
            "cited_count":   len(cited_urls),
            "cited_urls":    cited_urls[:3],
            "organic_pos":   organic_pos,
            "organic_url":   organic_url,
            "related":       related,
            "paa":           paa,
            "credits_left":  credits_left,
            "checked_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "error":         None
        }

    except Exception as e:
        return {
            "keyword":      keyword,
            "has_overview": False,
            "site_cited":   False,
            "error":        str(e),
            "checked_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


# ══════════════════════════════════════════════════════════════════════
#  READ TARGET KEYWORDS (reuse existing sheet)
# ══════════════════════════════════════════════════════════════════════
def read_target_keywords_simple(spreadsheet) -> list:
    """Read just the keyword names from 🎯 Target Keywords sheet."""
    try:
        ws   = spreadsheet.worksheet("🎯 Target Keywords")
        vals = ws.col_values(1)
        return [k.strip().lower() for k in vals[1:] if k.strip()]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════
#  WRITE AI OVERVIEW SHEET
# ══════════════════════════════════════════════════════════════════════
def write_ai_overview_sheet(spreadsheet, results: list):
    """Write AI Overview data to dedicated sheet."""
    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=SHEET_NAME, rows=500, cols=16
        )

    sid   = ws.id
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Summary counts ────────────────────────────────────────────────
    total        = len(results)
    has_overview = [r for r in results if r.get("has_overview")]
    site_cited   = [r for r in results if r.get("site_cited")]
    no_overview  = [r for r in results if not r.get("has_overview")]
    errors       = [r for r in results if r.get("error")]

    rows = [
        # Title
        [f"🤖 AI OVERVIEW TRACKER — {today}", "", "", "", "",
         "", "", "", "", ""],
        # Summary stats
        ["Total Checked", "AI Overview Exists",
         "We're Cited", "Not in Overview",
         "No AI Overview", ""],
        [total, len(has_overview), len(site_cited),
         len(has_overview) - len(site_cited),
         len(no_overview), ""],
        [""],   # spacer
        # Column headers
        [
            "Keyword",
            "AI Overview",
            "We're Cited",
            "Cite Snippet",
            "# Sources",
            "Our Organic Pos",
            "Our Ranking URL",
            "Opportunity",
            "People Also Ask",
            "Related Searches",
            "Credits Left",
            "Checked At",
        ]
    ]

    header_row = len(rows) - 1   # 0-indexed

    for r in results:
        if r.get("error"):
            rows.append([
                r["keyword"], "⚠️ Error", "", r["error"],
                "", "", "", "", "", "", "", r.get("checked_at", "")
            ])
            continue

        # AI Overview status
        overview_str = "✅ Yes" if r["has_overview"] else "❌ No"

        # Citation status
        if not r["has_overview"]:
            cited_str = "—"
        elif r["site_cited"]:
            cited_str = "🎯 Yes — We're In It!"
        else:
            cited_str = "❌ Not Cited"

        # Opportunity
        if r["site_cited"]:
            opportunity = "🏆 Maintain — We're cited"
        elif r["has_overview"] and r.get("organic_pos") and r["organic_pos"] <= 5:
            opportunity = "⚡ Optimize for citation"
        elif r["has_overview"] and not r["site_cited"]:
            opportunity = "📝 Add structured data"
        elif not r["has_overview"] and r.get("organic_pos") and r["organic_pos"] <= 3:
            opportunity = "✅ Strong organic — monitor"
        elif not r.get("organic_pos"):
            opportunity = "🚨 Not ranking organically"
        else:
            opportunity = "📈 Improve content depth"

        paa_str     = " | ".join(r.get("paa", [])[:2])
        related_str = " | ".join(r.get("related", [])[:3])

        rows.append([
            r["keyword"],
            overview_str,
            cited_str,
            r.get("cite_snippet", "—"),
            r.get("cited_count", 0),
            r.get("organic_pos", "Not ranking"),
            r.get("organic_url", "—"),
            opportunity,
            paa_str,
            related_str,
            r.get("credits_left", "?"),
            r.get("checked_at", ""),
        ])

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
        # Title row
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE,
                               "bold": True, "fontSize": 12}
            }},
            "fields": "userEnteredFormat"
        }},
        # Stats label row
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_MID,
                "textFormat": {"foregroundColor": WHITE,
                               "bold": True, "fontSize": 9}
            }},
            "fields": "userEnteredFormat"
        }},
        # Stats value row
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": 2, "endRowIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": WHITE,
                "textFormat": {"fontSize": 14, "bold": True,
                               "foregroundColor": DARK_TEXT}
            }},
            "fields": "userEnteredFormat"
        }},
        # Column headers
        {"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": header_row,
                      "endRowIndex":   header_row + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE,
                               "bold": True, "fontSize": 9}
            }},
            "fields": "userEnteredFormat"
        }},
        # Alternating rows
        {"addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sid,
                            "startRowIndex": header_row + 1}],
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
                    "frozenRowCount":    header_row + 1,
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
            "properties": {"pixelSize": 220}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": 3},
            "properties": {"pixelSize": 130}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 3, "endIndex": 4},
            "properties": {"pixelSize": 200}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 6, "endIndex": 7},
            "properties": {"pixelSize": 280}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 7, "endIndex": 8},
            "properties": {"pixelSize": 220}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 8, "endIndex": 10},
            "properties": {"pixelSize": 260}, "fields": "pixelSize"
        }},
    ]

    # Color-code cited column per row
    data_start = header_row + 1
    for i, r in enumerate(results):
        row_idx = data_start + i
        if r.get("site_cited"):
            color = ACCENT_GREEN
        elif r.get("has_overview") and not r.get("site_cited"):
            color = ACCENT_AMBER
        elif not r.get("has_overview"):
            color = SUBTLE_TEXT
        else:
            color = ACCENT_RED

        requests.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex":    row_idx,
                      "endRowIndex":      row_idx + 1,
                      "startColumnIndex": 2,
                      "endColumnIndex":   3},
            "cell": {"userEnteredFormat": {
                "textFormat": {"foregroundColor": color,
                               "bold": True}
            }},
            "fields": "userEnteredFormat.textFormat"
        }})

    try:
        spreadsheet.batch_update({"requests": requests})
    except Exception as e:
        print(f"⚠️  Formatting error: {e}")

    print(f"✅ AI Overview sheet written — {len(results)} keywords checked")
    print(f"   AI Overviews found: {len(has_overview)}")
    print(f"   We're cited in:     {len(site_cited)}")


# ══════════════════════════════════════════════════════════════════════
#  TELEGRAM ALERT
# ══════════════════════════════════════════════════════════════════════
def build_ai_alert(results: list) -> str:
    """Build Telegram message for AI Overview results."""
    total        = len(results)
    has_overview = [r for r in results if r.get("has_overview")]
    cited        = [r for r in results if r.get("site_cited")]
    missed       = [r for r in has_overview if not r.get("site_cited")]
    today        = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"🤖 <b>AI Overview Report — {today}</b>",
        f"{'─' * 30}",
        f"🔍 Keywords checked : <b>{total}</b>",
        f"✅ AI Overview exists: <b>{len(has_overview)}</b>",
        f"🎯 We're cited in   : <b>{len(cited)}</b>",
        f"❌ Not cited (yet)  : <b>{len(missed)}</b>",
        "",
    ]

    if cited:
        lines.append("🏆 <b>We're In the AI Overview!</b>")
        for r in cited:
            lines.append(
                f"  🎯 <code>{r['keyword'][:40]}</code>\n"
                f"     Organic: #{r.get('organic_pos', '?')} | "
                f"{r.get('cite_snippet', '')[:40]}"
            )
        lines.append("")

    if missed:
        lines.append("⚡ <b>AI Overview Exists — But Not Citing Us</b>")
        for r in missed[:5]:
            lines.append(
                f"  📝 <code>{r['keyword'][:40]}</code>\n"
                f"     Organic: #{r.get('organic_pos', 'Not ranking')} | "
                f"{r.get('opportunity', '')}"
            )
        lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════
def run_ai_overview_check():
    """Full pipeline for AI Overview checking."""
    if not SERPAPI_KEY:
        print("⚠️  SERPAPI_KEY not set — skipping AI Overview check")
        return None

    print("\n🤖 Running AI Overview Check...")

    creds       = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    sheets_client = gspread.authorize(creds)
    spreadsheet   = sheets_client.open_by_key(SHEET_ID)

    # Read target keywords
    keywords = read_target_keywords_simple(spreadsheet)
    if not keywords:
        print("⚠️  No target keywords found")
        return None

    # Respect 100/month limit — check unique seeds only
    # Deduplicate and cap at 80 to leave buffer
    keywords = list(dict.fromkeys(keywords))[:80]
    print(f"🔍 Checking {len(keywords)} keywords for AI Overview...")

    results = []
    for i, kw in enumerate(keywords):
        print(f"  [{i+1}/{len(keywords)}] {kw}...", end=" ")
        result = check_ai_overview(kw, "studyriserr.com")

        if result.get("error"):
            print(f"❌ {result['error']}")
        elif result["has_overview"]:
            cited = "🎯 CITED!" if result["site_cited"] else "not cited"
            print(f"✅ AI Overview exists — {cited}")
        else:
            print("— no AI Overview")

        results.append(result)

        # Rate limiting — be respectful to API
        if i < len(keywords) - 1:
            time.sleep(1.5)

    # Write sheet
    write_ai_overview_sheet(spreadsheet, results)

    # Build alert
    alert = build_ai_alert(results)

    print(f"\n✅ AI Overview check complete")
    return {"results": results, "alert": alert}