from dotenv import load_dotenv
load_dotenv()

from src.credentials_loader import setup_credentials
from src.gsc_fetcher import fetch_keyword_data
from src.history_manager import save_history
from src.analyzer import analyze_changes
from src.sheets_writer import write_all_sheets
from src.telegram_bot import send_report, send_message
from src.teams_notifier import send_teams_report
from src.target_keywords import run_target_tracker
from src.ai_overview import run_ai_overview_check
from src.dashboard_builder import write_full_dashboard
from datetime import datetime
from src.data_exporter import export_all_data

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

    # ── Other sheets ──────────────────────────────────────────────────
    write_all_sheets(report)
    send_report(report)
    send_teams_report(report)
    

    # ── Target keywords ───────────────────────────────────────────────
    target_result = run_target_tracker()
    target_intel  = target_result["intel"] if target_result else []
    if target_result and target_result["alert"]:
        send_message(target_result["alert"])

    # ── AI Overview (Mondays only) ────────────────────────────────────
    ai_result  = None
    ai_results = []
    if datetime.today().weekday() == 0:
        ai_result  = run_ai_overview_check()
        ai_results = ai_result["results"] if ai_result else []
        if ai_result and ai_result["alert"]:
            send_message(ai_result["alert"])

   
    # After all other calls:
    export_all_data(
        report       = report,
        target_intel = target_intel,
        ai_results   = ai_results
    )



    
    print("\n🎉 All done!")


if __name__ == "__main__":
    main()