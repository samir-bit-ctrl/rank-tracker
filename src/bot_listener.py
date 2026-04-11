import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(level=logging.WARNING)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Rank Tracker Bot*\n\n"
        "Available commands:\n"
        "*/scan* — Run a full rank scan now\n"
        "*/status* — Check last scan info\n"
        "*/top* — Show top 10 keywords by clicks\n"
        "*/gainers* — Show today's top gainers\n"
        "*/drops* — Show today's top drops",
        parse_mode="Markdown"
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run a full scan on demand."""
    await update.message.reply_text("🔄 Running scan... please wait.")

    try:
        # Import here to avoid circular imports
        from src.credentials_loader import setup_credentials
        from src.gsc_fetcher import fetch_keyword_data
        from src.history_manager import save_history
        from src.analyzer import analyze_changes
        from src.sheets_writer import write_all_sheets
        from src.teams_notifier import send_teams_report
        from src.dashboard_gen import generate_dashboard
        from src.telegram_bot import build_daily_summary

        setup_credentials()

        await update.message.reply_text("📡 Fetching GSC data...")
        keywords = fetch_keyword_data()

        if not keywords:
            await update.message.reply_text("❌ No data fetched from GSC.")
            return

        save_history(keywords)
        report = analyze_changes()

        if not report:
            await update.message.reply_text("❌ Could not generate report.")
            return

        await update.message.reply_text("📝 Updating Google Sheets...")
        write_all_sheets(report)

        await update.message.reply_text("🖥️ Rebuilding dashboard...")
        generate_dashboard(report)

        send_teams_report(report)

        # Send the full summary
        summary = build_daily_summary(report)
        await update.message.reply_text(summary, parse_mode="HTML")
        await update.message.reply_text("✅ Scan complete!")

    except Exception as e:
        await update.message.reply_text(f"❌ Error during scan:\n<code>{e}</code>",
                                         parse_mode="HTML")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show info about the last scan."""
    import json, os
    from src.credentials_loader import setup_credentials
    setup_credentials()
    history_file = "data/history.json"

    if not os.path.exists(history_file):
        await update.message.reply_text("⚠️ No scan history found yet. Run /scan first.")
        return

    with open(history_file) as f:
        history = json.load(f)

    dates     = sorted(history.keys())
    last_date = dates[-1]
    kw_count  = len(history[last_date])

    await update.message.reply_text(
        f"📋 <b>Last Scan Info</b>\n\n"
        f"📅 Date: <b>{last_date}</b>\n"
        f"🔑 Keywords tracked: <b>{kw_count}</b>\n"
        f"📊 Total scans stored: <b>{len(dates)}</b>",
        parse_mode="HTML"
    )


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 10 keywords by clicks."""
    import json, os
    from src.credentials_loader import setup_credentials
    setup_credentials()
    history_file = "data/history.json"

    if not os.path.exists(history_file):
        await update.message.reply_text("⚠️ No data yet. Run /scan first.")
        return

    with open(history_file) as f:
        history = json.load(f)

    last_date = sorted(history.keys())[-1]
    keywords  = list(history[last_date].values())
    keywords.sort(key=lambda x: x["clicks"], reverse=True)

    lines = [f"🏆 <b>Top 10 Keywords — {last_date}</b>\n"]
    for i, kw in enumerate(keywords[:10], 1):
        pos = kw["position"]
        if pos <= 3:    zone = "🥇"
        elif pos <= 10: zone = "🟢"
        elif pos <= 20: zone = "🟡"
        else:           zone = "🔴"

        lines.append(
            f"{i}. {zone} <code>{kw['keyword'][:40]}</code>\n"
            f"   Pos: <b>{pos}</b> · Clicks: <b>{kw['clicks']}</b> · CTR: {kw['ctr']}%"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's top gainers."""
    from src.analyzer import analyze_changes
    from src.credentials_loader import setup_credentials
    setup_credentials()
    report = analyze_changes()

    if not report or not report["improved"]:
        await update.message.reply_text("📊 No gainers detected yet.")
        return

    lines = [f"📈 <b>Top Gainers — {report['today_date']}</b>\n"]
    for kw in report["improved"][:10]:
        lines.append(
            f"🟢 <code>{kw['keyword'][:40]}</code>\n"
            f"   {kw['previous_position']} → <b>{kw['position']}</b> "
            f"<i>(+{kw['delta']})</i>"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def cmd_drops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's top drops."""
    from src.analyzer import analyze_changes
    from src.credentials_loader import setup_credentials
    setup_credentials()
    report = analyze_changes()

    if not report or not report["dropped"]:
        await update.message.reply_text("📊 No drops detected yet.")
        return

    lines = [f"📉 <b>Top Drops — {report['today_date']}</b>\n"]
    for kw in report["dropped"][:10]:
        lines.append(
            f"🔴 <code>{kw['keyword'][:40]}</code>\n"
            f"   {kw['previous_position']} → <b>{kw['position']}</b> "
            f"<i>({kw['delta']})</i>"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show live status of all target keywords."""
    await update.message.reply_text("🎯 Fetching target keyword data...")

    try:
        from src.credentials_loader import setup_credentials  # ← add this
        from src.target_keywords import run_target_tracker

        setup_credentials()   # ← add this — writes credentials.json from env

        result = run_target_tracker()

        if not result:
            await update.message.reply_text("⚠️ No target keywords found.")
            return

        intel = result["intel"]
        lines = [f"🎯 <b>Target Keywords — Live Status</b>\n"]

        for k in intel:
            pos = k["current_position"]
            if pos == "—":
                zone = "❌"
            elif pos <= 3:   zone = "🥇"
            elif pos <= 10:  zone = "🟢"
            elif pos <= 20:  zone = "🟡"
            else:            zone = "🔴"

            delta = k["delta"]
            delta_str = f"+{delta}" if delta > 0 else str(delta) if delta != 0 else "—"

            lines.append(
                f"{zone} <code>{k['keyword'][:38]}</code>\n"
                f"   Pos: <b>{pos}</b>  Δ: <i>{delta_str}</i>  "
                f"Clicks: {k['clicks_7d']}  CTR: {k['ctr']}%\n"
                f"   {k['status']}  ·  {k['opportunity']}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error:\n<code>{e}</code>", parse_mode="HTML"
        )


def run_bot():
    """Start the bot in polling mode — blocks until Ctrl+C."""
    print("🤖 Bot listener started — waiting for commands...")
    print("   Commands: /scan  /status  /top  /gainers  /drops")
    print("   Press Ctrl+C to stop\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("scan",    cmd_scan))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("top",     cmd_top))
    app.add_handler(CommandHandler("gainers", cmd_gainers))
    app.add_handler(CommandHandler("drops",   cmd_drops))
    app.add_handler(CommandHandler("targets", cmd_targets))

    app.run_polling(allowed_updates=Update.ALL_TYPES)