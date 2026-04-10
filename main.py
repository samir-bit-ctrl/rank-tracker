from src.credentials_loader import setup_credentials
from src.gsc_fetcher import fetch_keyword_data
from src.history_manager import save_history
from src.analyzer import analyze_changes
from src.sheets_writer import write_all_sheets
from src.telegram_bot import send_report
from src.teams_notifier import send_teams_report
from src.dashboard_gen import generate_dashboard


def main():
    print("🚀 Rank Tracker starting...\n")

    # Load credentials (from env in GitHub Actions, file locally)
    setup_credentials()

    # Fetch
    keywords = fetch_keyword_data()
    if not keywords:
        print("❌ No data fetched. Exiting.")
        return

    # Process
    save_history(keywords)
    report = analyze_changes()

    if report:
        write_all_sheets(report)    # → Google Sheets
        send_report(report)         # → Telegram
        send_teams_report(report)   # → Microsoft Teams
        generate_dashboard(report)  # → dashboard/index.html

    print("\n🎉 All done!")


if __name__ == "__main__":
    main()