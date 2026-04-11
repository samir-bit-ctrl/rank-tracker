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
from src.ai_overview import run_ai_overview_check
from datetime import datetime


def main():
    print("🚀 Rank Tracker starting...\n")

    setup_credentials()

    # ── Daily: main rank tracker ──────────────────────────────────────
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

    # ── Daily: target keyword tracker ────────────────────────────────
    result = run_target_tracker()
    if result and result["alert"]:
        send_message(result["alert"])

    # ── Weekly: AI Overview check (Mondays only) ──────────────────────
    if datetime.today().weekday() == 0:   # 0 = Monday
        print("\n📅 Monday — running weekly AI Overview check...")
        ai_result = run_ai_overview_check()
        if ai_result and ai_result["alert"]:
            send_message(ai_result["alert"])
    else:
        print(f"\nℹ️  AI Overview check runs on Mondays only")

    print("\n🎉 All done!")


if __name__ == "__main__":
    main()