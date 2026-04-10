import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def _send(message: str):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    async with bot:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )


def send_message(message: str):
    asyncio.run(_send(message))


# ══════════════════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════════════════

def _rank_zone(position: float) -> str:
    if position <= 3:   return "🥇"
    if position <= 10:  return "🟢"
    if position <= 20:  return "🟡"
    return "🔴"


def build_daily_summary(report: dict) -> str:
    today     = report["today_date"]
    prev      = report["yesterday_date"] or "first run"
    total     = report["total_keywords"]
    avg_pos   = report["avg_position"]
    improved  = report["improved"]
    dropped   = report["dropped"]
    new_kws   = report["new"]
    lost_kws  = report["lost"]

    lines = [
        f"📊 <b>Rank Tracker — studyriserr.com</b>",
        f"📅 <b>{today}</b>  <i>vs {prev}</i>",
        f"{'─' * 30}",
        f"🔑 Keywords tracked : <b>{total}</b>",
        f"📍 Avg position     : <b>{avg_pos}</b>",
        f"",
        f"🟢 Improved  : <b>{len(improved)}</b>",
        f"🔴 Dropped   : <b>{len(dropped)}</b>",
        f"🆕 New       : <b>{len(new_kws)}</b>",
        f"💀 Lost      : <b>{len(lost_kws)}</b>",
    ]

    # Top gainers
    if improved:
        lines += ["", "📈 <b>Top Gainers</b>"]
        for kw in improved[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"{zone} <code>{kw['keyword'][:40]}</code>\n"
                f"   {kw['previous_position']} → <b>{kw['position']}</b>  "
                f"<i>(+{kw['delta']})</i>"
            )

    # Top drops
    if dropped:
        lines += ["", "📉 <b>Top Drops</b>"]
        for kw in dropped[:5]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"{zone} <code>{kw['keyword'][:40]}</code>\n"
                f"   {kw['previous_position']} → <b>{kw['position']}</b>  "
                f"<i>({kw['delta']})</i>"
            )

    # New keywords (top 3 by clicks)
    if new_kws:
        lines += ["", "🆕 <b>New Keywords</b>"]
        for kw in new_kws[:3]:
            zone = _rank_zone(kw["position"])
            lines.append(
                f"{zone} <code>{kw['keyword'][:40]}</code>\n"
                f"   Pos: <b>{kw['position']}</b>  Clicks: <b>{kw['clicks']}</b>"
            )

    # Lost keywords (top 3 by clicks)
    if lost_kws:
        lines += ["", "💀 <b>Lost Keywords</b>"]
        for kw in lost_kws[:3]:
            lines.append(
                f"⚪ <code>{kw['keyword'][:40]}</code>\n"
                f"   Was: <b>{kw['position']}</b>  Clicks: <b>{kw['clicks']}</b>"
            )

    lines += [
        "",
        f"{'─' * 30}",
        f"📝 <a href='https://docs.google.com/spreadsheets/d/{_get_sheet_id()}'>Open Full Report</a>"
    ]

    return "\n".join(lines)


def build_alert_message(report: dict) -> str | None:
    """
    Only send an urgent alert if something significant happened.
    Returns None if nothing worth alerting about.
    """
    big_drops = [k for k in report["dropped"] if abs(k["delta"]) >= 5]
    big_gains = [k for k in report["improved"] if k["delta"] >= 5]
    lost      = report["lost"][:3]

    if not big_drops and not big_gains and not lost:
        return None

    lines = ["⚡ <b>Rank Alert — studyriserr.com</b>", ""]

    if big_gains:
        lines.append("🚀 <b>Big Jumps (5+ positions)</b>")
        for kw in big_gains[:3]:
            lines.append(
                f"🟢 <code>{kw['keyword'][:40]}</code>  "
                f"{kw['previous_position']} → <b>{kw['position']}</b> "
                f"<i>(+{kw['delta']})</i>"
            )
        lines.append("")

    if big_drops:
        lines.append("🚨 <b>Big Drops (5+ positions)</b>")
        for kw in big_drops[:3]:
            lines.append(
                f"🔴 <code>{kw['keyword'][:40]}</code>  "
                f"{kw['previous_position']} → <b>{kw['position']}</b> "
                f"<i>({kw['delta']})</i>"
            )
        lines.append("")

    if lost:
        lines.append("💀 <b>Keywords Lost</b>")
        for kw in lost:
            lines.append(
                f"⚪ <code>{kw['keyword'][:40]}</code>  "
                f"Was pos: <b>{kw['position']}</b>"
            )

    return "\n".join(lines)


def _get_sheet_id():
    try:
        from config.settings import SHEET_ID
        return SHEET_ID
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════
def send_report(report: dict):
    print("\n📨 Sending Telegram messages...")

    # Always send daily summary
    summary = build_daily_summary(report)
    send_message(summary)
    print("✅ Daily summary sent")

    # Only send alert if something significant happened
    alert = build_alert_message(report)
    if alert:
        send_message(alert)
        print("✅ Alert message sent")
    else:
        print("ℹ️  No significant changes — alert skipped")