from src.gsc_fetcher import fetch_keyword_data
from src.history_manager import save_history
from src.analyzer import analyze_changes
from src.sheets_writer import write_all_sheets
from src.telegram_bot import send_report
from src.dashboard_gen import generate_dashboard


def main():
    print("🚀 Rank Tracker starting...\n")

    keywords = fetch_keyword_data()
    if not keywords:
        print("❌ No data fetched. Exiting.")
        return

    save_history(keywords)
    report = analyze_changes()

    if report:
        write_all_sheets(report)
        send_report(report)
        generate_dashboard(report)
        print("\n🎉 All done!")


if __name__ == "__main__":
    main()