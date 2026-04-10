import requests
import json
from config.settings import TEAMS_WEBHOOK_URL, DASHBOARD_URL, SITE_NAME


def _rank_zone(position: float) -> str:
    if position <= 3:  return "🥇"
    if position <= 10: return "🟢"
    if position <= 20: return "🟡"
    return "🔴"


def send_teams_report(report: dict):
    """Send a rich adaptive card to Microsoft Teams."""
    if not TEAMS_WEBHOOK_URL:
        print("⚠️  Teams webhook not configured — skipping")
        return

    today      = report["today_date"]
    prev       = report["yesterday_date"] or "first run"
    improved   = report["improved"]
    dropped    = report["dropped"]
    new_kws    = report["new"]
    lost_kws   = report["lost"]

    # ── Build facts rows ─────────────────────────────────────────────
    facts = [
        {"name": "📅 Date",             "value": f"{today} vs {prev}"},
        {"name": "🔑 Keywords Tracked", "value": str(report["total_keywords"])},
        {"name": "📍 Avg Position",     "value": str(report["avg_position"])},
        {"name": "🟢 Improved",         "value": str(len(improved))},
        {"name": "🔴 Dropped",          "value": str(len(dropped))},
        {"name": "🆕 New",              "value": str(len(new_kws))},
        {"name": "💀 Lost",             "value": str(len(lost_kws))},
    ]

    # ── Top gainers text ─────────────────────────────────────────────
    gainers_text = ""
    if improved:
        lines = []
        for kw in improved[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"{zone} **{kw['keyword'][:45]}**  "
                f"{kw['previous_position']} → {kw['position']}  *(+{kw['delta']})*"
            )
        gainers_text = "\n\n".join(lines)
    else:
        gainers_text = "*No improvements today*"

    # ── Top drops text ───────────────────────────────────────────────
    drops_text = ""
    if dropped:
        lines = []
        for kw in dropped[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"{zone} **{kw['keyword'][:45]}**  "
                f"{kw['previous_position']} → {kw['position']}  *({kw['delta']})*"
            )
        drops_text = "\n\n".join(lines)
    else:
        drops_text = "*No drops today*"

    # ── Adaptive Card payload ────────────────────────────────────────
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    # Header
                    {
                        "type": "Container",
                        "style": "emphasis",
                        "items": [{
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column", "width": "stretch",
                                    "items": [{
                                        "type": "TextBlock",
                                        "text": f"📊 Rank Tracker — {SITE_NAME}",
                                        "weight": "Bolder", "size": "Large",
                                        "color": "Accent"
                                    }, {
                                        "type": "TextBlock",
                                        "text": f"Daily report · {today}",
                                        "size": "Small", "isSubtle": True,
                                        "spacing": "None"
                                    }]
                                }
                            ]
                        }]
                    },
                    # Stats facts
                    {
                        "type": "Container",
                        "spacing": "Medium",
                        "items": [{
                            "type": "FactSet",
                            "facts": facts
                        }]
                    },
                    # Separator
                    {"type": "Separator"},
                    # Gainers
                    {
                        "type": "Container",
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "📈 Top Gainers",
                                "weight": "Bolder", "size": "Medium",
                                "color": "Good"
                            },
                            {
                                "type": "TextBlock",
                                "text": gainers_text,
                                "wrap": True, "spacing": "Small"
                            }
                        ]
                    },
                    # Drops
                    {
                        "type": "Container",
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "📉 Top Drops",
                                "weight": "Bolder", "size": "Medium",
                                "color": "Warning"
                            },
                            {
                                "type": "TextBlock",
                                "text": drops_text,
                                "wrap": True, "spacing": "Small"
                            }
                        ]
                    },
                ],
                # Dashboard button
                "actions": [{
                    "type": "Action.OpenUrl",
                    "title": "🔗 Open Live Dashboard",
                    "url": DASHBOARD_URL
                }]
            }
        }]
    }

    try:
        resp = requests.post(
            TEAMS_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(card),
            timeout=10
        )
        if resp.status_code == 200:
            print("✅ Teams notification sent")
        else:
            print(f"⚠️  Teams returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Teams notification failed: {e}")