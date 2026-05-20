from dotenv import load_dotenv
load_dotenv()

from src.credentials_loader import setup_credentials
from src.gsc_fetcher import fetch_keyword_data
from src.history_manager import save_history
from src.analyzer import analyze_changes
from src.sheets_writer import write_all_sheets
from src.target_keywords import run_target_tracker
from src.ai_overview import run_ai_overview_check
from src.dashboard_builder import write_full_dashboard
from datetime import datetime
from src.data_exporter import export_all_data
from src.dashboard_builder import write_full_dashboard

def main():
    print("🚀 Rank Tracker starting...\n")

    setup_credentials()

    # ── Fetch & analyze ───────────────────────────────────────────────
    keywords = fetch_keyword_data()
    if not keywords:
        print("❌ No data fetched. Exiting.")
        return

    save_history(keywords)
    report = analyze_changes()
    if not report:
        return

    # ── Google Sheets ─────────────────────────────────────────────────
    write_all_sheets(report)

    # ── Target keywords ───────────────────────────────────────────────
    target_intel = []
    target_result = run_target_tracker()
    if target_result:
        target_intel = target_result.get("intel", [])

    # ── AI Overview (Mondays only) ────────────────────────────────────
    ai_results = []
    if datetime.today().weekday() == 0:
        print("\n📅 Monday — running AI Overview check...")
        ai_result = run_ai_overview_check()
        if ai_result:
            ai_results = ai_result.get("results", [])

    # ── Dashboard & JSON export ───────────────────────────────────────
    write_full_dashboard(
        report       = report,
        target_intel = target_intel,
        ai_results   = ai_results
    )
    export_all_data(
        report       = report,
        target_intel = target_intel,
        ai_results   = ai_results
    )

    print("\n🎉 All done!")


if __name__ == "__main__":
    main()