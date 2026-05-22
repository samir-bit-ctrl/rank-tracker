from dotenv import load_dotenv
load_dotenv()

from src.credentials_loader import setup_credentials
from src.gsc_fetcher        import fetch_keyword_data
from src.history_manager    import save_history
from src.analyzer           import analyze_changes
from src.sheets_writer      import write_all_sheets
from src.dashboard_builder  import write_full_dashboard
from src.target_keywords    import run_target_tracker
from src.ai_overview        import run_ai_overview_check
from src.aio_extractor      import run_aio_extractor
from src.data_exporter      import export_all_data
from config.settings        import AIO_MAX_KEYWORDS
from datetime               import datetime


def main():
    print("🚀 Rank Tracker starting...\n")
    setup_credentials()

    # ── Phase 1: Fetch & analyze ──────────────────────────────────────
    keywords = fetch_keyword_data()
    if not keywords:
        print("❌ No data fetched. Exiting.")
        return

    save_history(keywords)
    report = analyze_changes()
    if not report:
        return

    # ── Phase 2: Sheets ───────────────────────────────────────────────
    write_all_sheets(report)

    # ── Phase 3: Target keywords ──────────────────────────────────────
    target_intel  = []
    target_result = run_target_tracker()
    if target_result:
        target_intel = target_result.get("intel", [])

    # ── Phase 4: SerpAPI AI Overview (Mondays, uses credits) ──────────
    ai_results = []
    if datetime.today().weekday() == 0:
        print("\n📅 Monday — running SerpAPI AI Overview check...")
        ai_result = run_ai_overview_check()
        if ai_result:
            ai_results = ai_result.get("results", [])

    # ── Phase 5: FREE Playwright AIO extractor (runs daily) ───────────
    print("\n🆓 Running free Playwright AIO extractor...")
    run_aio_extractor(
        max_keywords = AIO_MAX_KEYWORDS,
        use_cache    = True,
        write_sheet  = True,
        write_json   = True,
    )

    # ── Phase 6: Dashboard ────────────────────────────────────────────
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