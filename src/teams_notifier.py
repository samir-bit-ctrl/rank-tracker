import requests
import json
from config.settings import TEAMS_WEBHOOK_URL, DASHBOARD_URL, SITE_NAME


def _rank_zone(position: float) -> str:
    if position <= 3:  return "🥇"
    if position <= 10: return "🟢"
    if position <= 20: return "🟡"
    return "🔴"


def _build_body(report: dict) -> str:
    """Build plain HTML body for Power Automate webhook."""
    today    = report["today_date"]
    prev     = report["yesterday_date"] or "first run"
    improved = report["improved"]
    dropped  = report["dropped"]
    new_kws  = report["new"]
    lost_kws = report["lost"]

    lines = []

    # ── Summary ───────────────────────────────────────────────────────
    lines.append(f"<h2>📊 Rank Tracker — {SITE_NAME}</h2>")
    lines.append(f"<p><b>Date:</b> {today} &nbsp;|&nbsp; <b>vs:</b> {prev}</p>")
    lines.append("<table>")
    lines.append("<tr>"
                 f"<td>🔑 <b>Keywords</b>: {report['total_keywords']}</td>"
                 f"<td>&nbsp;&nbsp;</td>"
                 f"<td>📍 <b>Avg Position</b>: {report['avg_position']}</td>"
                 "</tr>")
    lines.append("<tr>"
                 f"<td>🟢 <b>Improved</b>: {len(improved)}</td>"
                 f"<td>&nbsp;&nbsp;</td>"
                 f"<td>🔴 <b>Dropped</b>: {len(dropped)}</td>"
                 "</tr>")
    lines.append("<tr>"
                 f"<td>🆕 <b>New</b>: {len(new_kws)}</td>"
                 f"<td>&nbsp;&nbsp;</td>"
                 f"<td>💀 <b>Lost</b>: {len(lost_kws)}</td>"
                 "</tr>")
    lines.append("</table>")
    lines.append("<hr/>")

    # ── Top Gainers ───────────────────────────────────────────────────
    lines.append("<h3>📈 Top Gainers</h3>")
    if improved:
        lines.append("<ul>")
        for kw in improved[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"<li>{zone} <b>{kw['keyword']}</b> &nbsp;"
                f"{kw['previous_position']} → <b>{kw['position']}</b> "
                f"<i>(+{kw['delta']})</i></li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p><i>No improvements today</i></p>")

    # ── Top Drops ─────────────────────────────────────────────────────
    lines.append("<h3>📉 Top Drops</h3>")
    if dropped:
        lines.append("<ul>")
        for kw in dropped[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"<li>{zone} <b>{kw['keyword']}</b> &nbsp;"
                f"{kw['previous_position']} → <b>{kw['position']}</b> "
                f"<i>({kw['delta']})</i></li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p><i>No drops today</i></p>")

    # ── New Keywords ──────────────────────────────────────────────────
    if new_kws:
        lines.append("<h3>🆕 New Keywords</h3><ul>")
        for kw in new_kws[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"<li>{zone} <b>{kw['keyword']}</b> &nbsp;"
                f"Pos: <b>{kw['position']}</b> · Clicks: {kw['clicks']}</li>"
            )
        lines.append("</ul>")

    # ── Lost Keywords ─────────────────────────────────────────────────
    if lost_kws:
        lines.append("<h3>💀 Lost Keywords</h3><ul>")
        for kw in lost_kws[:5]:
            lines.append(
                f"<li>⚪ <b>{kw['keyword']}</b> &nbsp;"
                f"Was pos: <b>{kw['position']}</b> · Clicks: {kw['clicks']}</li>"
            )
        lines.append("</ul>")

    # ── Dashboard Link ────────────────────────────────────────────────
    lines.append("<hr/>")
    lines.append(
        f'<p>🔗 <a href="{DASHBOARD_URL}"><b>Open Live Dashboard</b></a></p>'
    )

    return "\n".join(lines)

def _build_plain_text(report: dict) -> str:
    """Plain text version — most compatible with Power Automate."""
    today    = report["today_date"]
    prev     = report["yesterday_date"] or "first run"
    improved = report["improved"]
    dropped  = report["dropped"]
    new_kws  = report["new"]
    lost_kws = report["lost"]

    lines = [
        f"📊 Rank Tracker — {SITE_NAME}",
        f"📅 {today} vs {prev}",
        f"─────────────────────────",
        f"🔑 Keywords: {report['total_keywords']}  |  📍 Avg Pos: {report['avg_position']}",
        f"🟢 Improved: {len(improved)}  |  🔴 Dropped: {len(dropped)}",
        f"🆕 New: {len(new_kws)}  |  💀 Lost: {len(lost_kws)}",
        "",
    ]

    if improved:
        lines.append("📈 Top Gainers")
        for kw in improved[:5]:
            lines.append(f"  ▲ {kw['keyword']} | {kw['previous_position']} → {kw['position']} (+{kw['delta']})")
        lines.append("")

    if dropped:
        lines.append("📉 Top Drops")
        for kw in dropped[:5]:
            lines.append(f"  ▼ {kw['keyword']} | {kw['previous_position']} → {kw['position']} ({kw['delta']})")
        lines.append("")

    if new_kws:
        lines.append("🆕 New Keywords")
        for kw in new_kws[:3]:
            lines.append(f"  • {kw['keyword']} | Pos: {kw['position']} | Clicks: {kw['clicks']}")
        lines.append("")

    if lost_kws:
        lines.append("💀 Lost Keywords")
        for kw in lost_kws[:3]:
            lines.append(f"  • {kw['keyword']} | Was: {kw['position']} | Clicks: {kw['clicks']}")
        lines.append("")

    lines.append(f"🔗 Dashboard: {DASHBOARD_URL}")

    return "\n".join(lines)

def send_teams_report(report: dict):
    if not TEAMS_WEBHOOK_URL:
        print("⚠️  Teams webhook not configured — skipping")
        return

    today    = report["today_date"]
    prev     = report["yesterday_date"] or "first run"
    improved = report["improved"]
    dropped  = report["dropped"]
    new_kws  = report["new"]
    lost_kws = report["lost"]

    # Build facts
    facts = [
        {"title": "📅 Date",         "value": f"{today} vs {prev}"},
        {"title": "🔑 Keywords",     "value": str(report["total_keywords"])},
        {"title": "📍 Avg Position", "value": str(report["avg_position"])},
        {"title": "🟢 Improved",     "value": str(len(improved))},
        {"title": "🔴 Dropped",      "value": str(len(dropped))},
        {"title": "🆕 New",          "value": str(len(new_kws))},
        {"title": "💀 Lost",         "value": str(len(lost_kws))},
    ]

    # Build gainers text
    if improved:
        gainers = "\n".join([
            f"▲ {kw['keyword'][:45]}  {kw['previous_position']} → {kw['position']} (+{kw['delta']})"
            for kw in improved[:5]
        ])
    else:
        gainers = "No improvements today"

    # Build drops text
    if dropped:
        drops = "\n".join([
            f"▼ {kw['keyword'][:45]}  {kw['previous_position']} → {kw['position']} ({kw['delta']})"
            for kw in dropped[:5]
        ])
    else:
        drops = "No drops today"

    # Proper AdaptiveCard — type must be exactly "AdaptiveCard"
    adaptive_card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📊 Rank Tracker — {SITE_NAME}",
                "weight": "Bolder",
                "size": "Large",
                "color": "Accent"
            },
            {
                "type": "TextBlock",
                "text": f"Daily report · {today}",
                "isSubtle": True,
                "spacing": "None"
            },
            {
                "type": "FactSet",
                "spacing": "Medium",
                "facts": facts
            },
            {
                "type": "TextBlock",
                "text": "📈 Top Gainers",
                "weight": "Bolder",
                "spacing": "Medium",
                "color": "Good"
            },
            {
                "type": "TextBlock",
                "text": gainers,
                "wrap": True,
                "spacing": "Small",
                "fontType": "Monospace"
            },
            {
                "type": "TextBlock",
                "text": "📉 Top Drops",
                "weight": "Bolder",
                "spacing": "Medium",
                "color": "Warning"
            },
            {
                "type": "TextBlock",
                "text": drops,
                "wrap": True,
                "spacing": "Small",
                "fontType": "Monospace"
            }
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "🔗 Open Live Dashboard",
                "url": DASHBOARD_URL
            }
        ]
    }

    # Power Automate expects the card wrapped like this
    payload = {
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": adaptive_card
            }
        ]
    }

    try:
        resp = requests.post(
            TEAMS_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=15
        )
        if resp.status_code in (200, 202):
            print("✅ Teams notification sent")
        else:
            print(f"⚠️  Teams returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Teams notification failed: {e}")