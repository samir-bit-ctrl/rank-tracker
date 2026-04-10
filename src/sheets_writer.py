import gspread
from google.oauth2 import service_account
from datetime import datetime
from config.settings import (
    CREDENTIALS_PATH, SHEET_ID,
    SHEET_NAME_DASHBOARD, SHEET_NAME_DAILY_LOG,
    SHEET_NAME_MOVERS, SHEET_NAME_LOST_NEW
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ── Colour palette ────────────────────────────────────────────────────────
HEADER_DARK    = {"red": 0.192, "green": 0.212, "blue": 0.251}   # #313640 slate
HEADER_MID     = {"red": 0.271, "green": 0.298, "blue": 0.349}   # #454C59 mid slate
ACCENT_GREEN   = {"red": 0.196, "green": 0.533, "blue": 0.384}   # #328862 muted green
ACCENT_RED     = {"red": 0.757, "green": 0.267, "blue": 0.267}   # #C14444 muted red
ACCENT_BLUE    = {"red": 0.271, "green": 0.431, "blue": 0.675}   # #456EAC muted blue
ACCENT_AMBER   = {"red": 0.800, "green": 0.600, "blue": 0.200}   # #CC9933 muted amber
WHITE          = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
OFF_WHITE      = {"red": 0.980, "green": 0.980, "blue": 0.984}   # #FAFAFB
LIGHT_GREY     = {"red": 0.941, "green": 0.945, "blue": 0.953}   # #F0F1F3
MID_GREY       = {"red": 0.878, "green": 0.886, "blue": 0.902}   # #E0E2E6
SUBTLE_TEXT    = {"red": 0.420, "green": 0.447, "blue": 0.502}   # #6B7280 grey text
DARK_TEXT      = {"red": 0.133, "green": 0.149, "blue": 0.180}   # #22262E

def _color(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}


def get_sheets_client():
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return gspread.authorize(creds)


def _get_or_create_sheet(spreadsheet, name: str):
    """Get sheet by name or create it if missing."""
    try:
        return spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=1000, cols=30)


def _clear_sheet(ws):
    ws.clear()


def _fmt_request(sheet_id, requests: list):
    return requests


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — 📊 DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def write_dashboard(spreadsheet, report: dict):
    ws  = _get_or_create_sheet(spreadsheet, SHEET_NAME_DASHBOARD)
    _clear_sheet(ws)
    sid = ws.id

    today      = report["today_date"]
    top_gainer = report["improved"][0] if report["improved"] else None
    top_drop   = report["dropped"][0]  if report["dropped"]  else None

    rows = [
        ["", "", "", "", "", ""],                                          # row 1  spacer
        ["", "RANK TRACKER", "", "", "studyriserr.com", ""],              # row 2  title
        ["", f"Last updated: {today}", "", "", "Powered by GSC API", ""], # row 3  subtitle
        ["", "", "", "", "", ""],                                          # row 4  spacer
        ["", "Total Keywords", "Avg Position", "Improved", "Dropped", ""],# row 5  stat labels
        ["", report["total_keywords"], report["avg_position"],             # row 6  stat values
             len(report["improved"]), len(report["dropped"]), ""],
        ["", "", "", "", "", ""],                                          # row 7  spacer
        ["", "New Keywords", "Lost Keywords", "", "", ""],                 # row 8
        ["", len(report["new"]), len(report["lost"]), "", "", ""],         # row 9
        ["", "", "", "", "", ""],                                          # row 10 spacer
        ["", "Top Gainer", "", "Biggest Drop", "", ""],                   # row 11
        ["",
         top_gainer["keyword"] if top_gainer else "—",
         f"▲ +{top_gainer['delta']}" if top_gainer else "",
         top_drop["keyword"]   if top_drop   else "—",
         f"▼ {top_drop['delta']}" if top_drop else "",
         ""],                                                              # row 12
        ["", "", "", "", "", ""],                                          # row 13 spacer
        ["", "Rank Zone", "Keywords", "% of Total", "", ""],              # row 14 zone header
    ]

    all_kws = (report["improved"] + report["dropped"] +
               report["stable"]  + report["new"])
    total   = len(all_kws) or 1

    zones = [
        ("Top 3",   [k for k in all_kws if k["position"] <= 3]),
        ("Top 10",  [k for k in all_kws if 3  < k["position"] <= 10]),
        ("11 – 20", [k for k in all_kws if 10 < k["position"] <= 20]),
        ("20+",     [k for k in all_kws if k["position"] > 20]),
    ]
    for label, kws in zones:
        pct = round(len(kws) / total * 100, 1)
        rows.append(["", label, len(kws), f"{pct}%", "", ""])

    rows.append(["", "", "", "", "", ""])  # bottom spacer

    ws.update("A1", rows)

    requests = [
        # ── Whole sheet background ────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid},
            "cell": {"userEnteredFormat": {
                "backgroundColor": OFF_WHITE,
                "textFormat": {"fontFamily": "Inter", "fontSize": 10,
                               "foregroundColor": DARK_TEXT}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Title row ─────────────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE, "fontSize": 13,
                               "bold": True, "fontFamily": "Inter"}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Subtitle row ──────────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 3,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_MID,
                "textFormat": {"foregroundColor": MID_GREY, "fontSize": 9,
                               "fontFamily": "Inter"}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Stat labels row ───────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 4, "endRowIndex": 5,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": LIGHT_GREY,
                "textFormat": {"foregroundColor": SUBTLE_TEXT, "fontSize": 9,
                               "bold": True, "fontFamily": "Inter"}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Stat values row ───────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": WHITE,
                "textFormat": {"fontSize": 18, "bold": True,
                               "foregroundColor": DARK_TEXT, "fontFamily": "Inter"}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Improved stat value — muted green ─────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {
                "textFormat": {"foregroundColor": ACCENT_GREEN, "fontSize": 18,
                               "bold": True}
            }},
            "fields": "userEnteredFormat.textFormat"
        }},
        # ── Dropped stat value — muted red ────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 4, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "textFormat": {"foregroundColor": ACCENT_RED, "fontSize": 18,
                               "bold": True}
            }},
            "fields": "userEnteredFormat.textFormat"
        }},
        # ── New/Lost labels ───────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 7, "endRowIndex": 8,
                      "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": LIGHT_GREY,
                "textFormat": {"foregroundColor": SUBTLE_TEXT, "fontSize": 9,
                               "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── New/Lost values ───────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 8, "endRowIndex": 9,
                      "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": WHITE,
                "textFormat": {"fontSize": 14, "bold": True,
                               "foregroundColor": DARK_TEXT}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Top gainer/drop labels ────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 10, "endRowIndex": 11,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": LIGHT_GREY,
                "textFormat": {"foregroundColor": SUBTLE_TEXT, "fontSize": 9,
                               "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Top gainer value ──────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 11, "endRowIndex": 12,
                      "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": WHITE,
                "textFormat": {"foregroundColor": ACCENT_GREEN, "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Biggest drop value ────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 11, "endRowIndex": 12,
                      "startColumnIndex": 3, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {
                "backgroundColor": WHITE,
                "textFormat": {"foregroundColor": ACCENT_RED, "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Zone table header ─────────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 13, "endRowIndex": 14,
                      "startColumnIndex": 1, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9}
            }},
            "fields": "userEnteredFormat"
        }},
        # ── Zone rows alternating ─────────────────────────────────────────
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 14, "endRowIndex": 18,
                      "startColumnIndex": 1, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": WHITE}},
            "fields": "userEnteredFormat"
        }},
        # ── Column widths ─────────────────────────────────────────────────
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 24}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 260}, "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 2, "endIndex": 5},
            "properties": {"pixelSize": 140}, "fields": "pixelSize"
        }},
        # ── Row heights ───────────────────────────────────────────────────
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS",
                      "startIndex": 5, "endIndex": 6},
            "properties": {"pixelSize": 48}, "fields": "pixelSize"
        }},
        # ── Remove gridlines ──────────────────────────────────────────────
        {"updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {"hideGridlines": True}
            },
            "fields": "gridProperties.hideGridlines"
        }},
    ]

    spreadsheet.batch_update({"requests": requests})
    print("✅ Dashboard tab written")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — 📈 DAILY LOG
# ══════════════════════════════════════════════════════════════════════════════
def write_daily_log(spreadsheet, report: dict):
    ws     = _get_or_create_sheet(spreadsheet, SHEET_NAME_DAILY_LOG)
    sid    = ws.id
    today  = report["today_date"]

    # Check if today's column already exists
    existing = ws.row_values(1)
    if today in existing:
        print("ℹ️  Daily log already has today's data — skipping duplicate write")
        return

    all_kws = (report["improved"] + report["dropped"] +
               report["stable"] + report["new"])
    all_kws.sort(key=lambda x: x["clicks"], reverse=True)

    if not existing:
        # First ever write — build full sheet
        header = ["Keyword", "Clicks", "Impressions", "CTR %", today]
        rows   = [header]
        for kw in all_kws:
            rows.append([
                kw["keyword"], kw["clicks"],
                kw["impressions"], kw["ctr"], kw["position"]
            ])
        ws.update("A1", rows)
    else:
        # Append a new date column
        col_index = len(existing) + 1
        col_letter = chr(64 + col_index)  # works up to col Z (26 dates)

        # Get existing keywords in col A
        existing_kws = ws.col_values(1)[1:]   # skip header
        kw_map = {kw["keyword"]: kw["position"] for kw in all_kws}

        updates = [[today]]   # header cell
        for kw in existing_kws:
            updates.append([kw_map.get(kw, "")])

        ws.update(f"{col_letter}1", updates)

    # ── Format header row ─────────────────────────────────────────────────
    requests = [
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10}
            }},
            "fields": "userEnteredFormat"
        }},
        # Alternating row colors
        {"addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sid, "startRowIndex": 1}],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA",
                                  "values": [{"userEnteredValue": "=ISEVEN(ROW())"}]},
                    "format": {"backgroundColor": LIGHT_GREY}
                }
            },
            "index": 0
        }},
        # Freeze header + keyword column
        {"updateSheetProperties": {
            "properties": {"sheetId": sid,
                           "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
        }},
        # Keyword column width
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 300},
            "fields": "pixelSize"
        }},
    ]
    try:
        spreadsheet.batch_update({"requests": requests})
    except Exception:
        pass  # formatting already applied on first run

    print("✅ Daily log tab written")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — 🟢 MOVERS
# ══════════════════════════════════════════════════════════════════════════════
def write_movers(spreadsheet, report: dict):
    ws  = _get_or_create_sheet(spreadsheet, SHEET_NAME_MOVERS)
    sid = ws.id
    _clear_sheet(ws)

    rows = [
        [f"🟢 TOP GAINERS — {report['today_date']}",
         "", "", "", "",
         f"🔴 TOP DROPS — {report['today_date']}"],
        ["Keyword", "Prev Pos", "New Pos", "Change", "",
         "Keyword", "Prev Pos", "New Pos", "Change"],
    ]

    improved = report["improved"][:20]
    dropped  = report["dropped"][:20]
    max_rows = max(len(improved), len(dropped))

    for i in range(max_rows):
        g = improved[i] if i < len(improved) else None
        d = dropped[i]  if i < len(dropped)  else None
        rows.append([
            g["keyword"]           if g else "",
            g["previous_position"] if g else "",
            g["position"]          if g else "",
            f"+{g['delta']}"       if g else "",
            "",
            d["keyword"]           if d else "",
            d["previous_position"] if d else "",
            d["position"]          if d else "",
            str(d["delta"])        if d else "",
        ])

    ws.update("A1", rows)

    requests = [
        # Gainers header
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {
                "backgroundColor": ACCENT_GREEN,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        # Drops header
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 5, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": {
                "backgroundColor": ACCENT_RED,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        # Column headers row
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE, "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
            "fields": "gridProperties.frozenRowCount"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 5, "endIndex": 6},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize"
        }},
    ]
    spreadsheet.batch_update({"requests": requests})
    print("✅ Movers tab written")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — 💀 LOST & NEW
# ══════════════════════════════════════════════════════════════════════════════
def write_lost_new(spreadsheet, report: dict):
    ws  = _get_or_create_sheet(spreadsheet, SHEET_NAME_LOST_NEW)
    sid = ws.id
    _clear_sheet(ws)

    rows = [
        [f"🆕 NEW KEYWORDS — {report['today_date']}",
         "", "", "",
         f"💀 LOST KEYWORDS — {report['today_date']}"],
        ["Keyword", "Position", "Clicks", "",
         "Keyword", "Last Position", "Clicks"],
    ]

    new  = report["new"][:50]
    lost = report["lost"][:50]
    max_rows = max(len(new), len(lost))

    for i in range(max_rows):
        n = new[i]  if i < len(new)  else None
        l = lost[i] if i < len(lost) else None
        rows.append([
            n["keyword"]   if n else "",
            n["position"]  if n else "",
            n["clicks"]    if n else "",
            "",
            l["keyword"]   if l else "",
            l["position"]  if l else "",
            l["clicks"]    if l else "",
        ])

    ws.update("A1", rows)

    requests = [
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": ACCENT_BLUE,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 4, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _color(80, 80, 80),
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 11}
            }},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_DARK,
                "textFormat": {"foregroundColor": WHITE, "bold": True}
            }},
            "fields": "userEnteredFormat"
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
            "fields": "gridProperties.frozenRowCount"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 4, "endIndex": 5},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize"
        }},
    ]
    spreadsheet.batch_update({"requests": requests})
    print("✅ Lost & New tab written")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════════════
def write_all_sheets(report: dict):
    print("\n📝 Writing to Google Sheets...")
    client       = get_sheets_client()
    spreadsheet  = client.open_by_key(SHEET_ID)

    write_dashboard(spreadsheet, report)
    write_daily_log(spreadsheet, report)
    write_movers(spreadsheet, report)
    write_lost_new(spreadsheet, report)

    url = f"https://docs.google.com/spreadsheets/d/"
    print(f"\n✅ All tabs written → {url}")
