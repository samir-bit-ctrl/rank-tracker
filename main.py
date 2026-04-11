from dotenv import load_dotenv
load_dotenv()

from src.credentials_loader import setup_credentials
from src.gsc_fetcher import fetch_keyword_data
from src.history_manager import save_history
from src.analyzer import analyze_changes
from src.sheets_writer import write_all_sheets
from src.telegram_bot import send_report, send_message
from src.teams_notifier import send_teams_report
from src.dashboard_gen import generate_dashboard
from src.target_keywords import run_target_tracker


def main():
    print("🚀 Rank Tracker starting...\n")

    setup_credentials()

    # ── Main rank tracker ─────────────────────────────────────────────
    keywords = fetch_keyword_data()
    if not keywords:
        print("❌ No data fetched. Exiting.")
        return

    save_history(keywords)
    report = analyze_changes()

    if report:
        write_all_sheets(report)
        send_report(report)
        send_teams_report(report)
        generate_dashboard(report)

    # ── Target keyword tracker ────────────────────────────────────────
    result = run_target_tracker()

    if result and result["alert"]:
        send_message(result["alert"])   # separate Telegram alert
        print("✅ Target keyword alert sent")
    else:
        print("ℹ️  No significant changes in target keywords")

    print("\n🎉 All done!")


if __name__ == "__main__":
    main()