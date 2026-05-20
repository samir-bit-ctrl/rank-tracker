"""
api.py — FastAPI backend for the SEO Control Panel
Handles all button actions from the web dashboard.
Run with: uvicorn api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="SEO Rank Tracker API", version="1.0.0")

# Allow dashboard to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Job status tracker ────────────────────────────────────────────────
_job_status = {
    "running": False,
    "current_job": None,
    "last_run": None,
    "last_result": None,
}


def _is_running():
    return _job_status["running"]


def _set_running(job_name: str):
    _job_status["running"]     = True
    _job_status["current_job"] = job_name


def _set_done(result: dict):
    _job_status["running"]     = False
    _job_status["current_job"] = None
    _job_status["last_run"]    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _job_status["last_result"] = result


# ══════════════════════════════════════════════════════════════════════
#  HEALTH
# ══════════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"status": "ok", "service": "SEO Rank Tracker API"}


@app.get("/status")
def get_status():
    """Current job status + last scan info."""
    history_file = "data/history.json"
    history_info = {}

    if os.path.exists(history_file):
        try:
            with open(history_file) as f:
                h = json.load(f)
            dates = sorted(h.keys())
            if dates:
                last   = dates[-1]
                history_info = {
                    "last_scan_date": last,
                    "total_keywords": len(h[last]),
                    "total_snapshots": len(dates),
                    "dates_available": dates[-7:],
                }
        except Exception:
            pass

    return {
        "job_running":   _job_status["running"],
        "current_job":   _job_status["current_job"],
        "last_run":      _job_status["last_run"],
        **history_info
    }


# ══════════════════════════════════════════════════════════════════════
#  FULL SCAN
# ══════════════════════════════════════════════════════════════════════
def _run_full_scan():
    _set_running("Full Scan")
    try:
        from src.credentials_loader import setup_credentials
        from src.gsc_fetcher        import fetch_keyword_data
        from src.history_manager    import save_history
        from src.analyzer           import analyze_changes
        from src.sheets_writer      import write_all_sheets
        from src.dashboard_builder  import write_full_dashboard
        from src.target_keywords    import run_target_tracker
        from src.data_exporter      import export_all_data

        setup_credentials()
        keywords = fetch_keyword_data()
        if not keywords:
            _set_done({"success": False, "message": "No data from GSC"})
            return

        save_history(keywords)
        report = analyze_changes()

        target_intel = []
        target_result = run_target_tracker()
        if target_result:
            target_intel = target_result.get("intel", [])

        write_all_sheets(report)
        write_full_dashboard(report=report, target_intel=target_intel)
        export_all_data(report=report, target_intel=target_intel)

        _set_done({
            "success":  True,
            "message":  "Full scan complete",
            "keywords": report["total_keywords"],
            "improved": len(report["improved"]),
            "dropped":  len(report["dropped"]),
            "new":      len(report["new"]),
            "lost":     len(report["lost"]),
            "avg_pos":  report["avg_position"],
            "date":     report["today_date"],
        })
    except Exception as e:
        _set_done({"success": False, "message": str(e)})


@app.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    if _is_running():
        return JSONResponse(
            status_code=409,
            content={"error": f"Job already running: {_job_status['current_job']}"}
        )
    background_tasks.add_task(_run_full_scan)
    return {"message": "Full scan started", "job": "Full Scan"}


# ══════════════════════════════════════════════════════════════════════
#  TOP KEYWORDS
# ══════════════════════════════════════════════════════════════════════
@app.get("/top")
def get_top_keywords(n: int = 10):
    """Top N keywords by clicks from latest snapshot."""
    SPAM = ["http", "www.", ".com", ".in", ".org", "survey", "whitecastle"]
    try:
        with open("data/history.json") as f:
            history = json.load(f)
        dates   = sorted(history.keys())
        latest  = history[dates[-1]]
        clean   = [
            v for v in latest.values()
            if not any(s in v.get("keyword", "").lower() for s in SPAM)
        ]
        top     = sorted(clean, key=lambda x: x.get("clicks", 0), reverse=True)[:n]
        return {
            "date":     dates[-1],
            "keywords": [
                {
                    "rank":       i + 1,
                    "keyword":    k["keyword"],
                    "clicks":     k.get("clicks", 0),
                    "impressions":k.get("impressions", 0),
                    "position":   round(k.get("position", 0), 1),
                    "ctr":        round(k.get("ctr", 0) * 100
                                        if k.get("ctr", 0) < 1
                                        else k.get("ctr", 0), 2),
                }
                for i, k in enumerate(top)
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ══════════════════════════════════════════════════════════════════════
#  GAINERS & DROPS
# ══════════════════════════════════════════════════════════════════════
@app.get("/gainers")
def get_gainers(limit: int = 15):
    """Today's top gaining keywords."""
    try:
        from src.analyzer import analyze_changes
        report = analyze_changes()
        if not report:
            return {"gainers": [], "message": "No data yet"}
        return {
            "date":    report["today_date"],
            "vs":      report["yesterday_date"],
            "gainers": [
                {
                    "keyword":  k["keyword"],
                    "prev":     k["previous_position"],
                    "current":  k["position"],
                    "delta":    k["delta"],
                    "clicks":   k.get("clicks", 0),
                }
                for k in report["improved"][:limit]
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/drops")
def get_drops(limit: int = 15):
    """Today's top dropping keywords."""
    try:
        from src.analyzer import analyze_changes
        report = analyze_changes()
        if not report:
            return {"drops": [], "message": "No data yet"}
        return {
            "date":  report["today_date"],
            "vs":    report["yesterday_date"],
            "drops": [
                {
                    "keyword": k["keyword"],
                    "prev":    k["previous_position"],
                    "current": k["position"],
                    "delta":   k["delta"],
                    "clicks":  k.get("clicks", 0),
                }
                for k in report["dropped"][:limit]
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ══════════════════════════════════════════════════════════════════════
#  TARGET SCAN
# ══════════════════════════════════════════════════════════════════════
def _run_target_scan():
    _set_running("Target Scan")
    try:
        from src.credentials_loader import setup_credentials
        from src.target_keywords    import run_target_tracker
        from src.data_exporter      import export_all_data

        setup_credentials()
        result = run_target_tracker()

        if not result:
            _set_done({"success": False, "message": "No target keywords found"})
            return

        intel = result.get("intel", [])
        top3  = len([k for k in intel
                     if isinstance(k.get("current_position"), float)
                     and k["current_position"] <= 3])
        top10 = len([k for k in intel
                     if isinstance(k.get("current_position"), float)
                     and k["current_position"] <= 10])

        # Update targets.json
        try:
            from src.analyzer import analyze_changes
            report = analyze_changes()
            if report:
                export_all_data(report=report, target_intel=intel)
        except Exception:
            pass

        _set_done({
            "success":      True,
            "message":      "Target scan complete",
            "total":        len(intel),
            "top3":         top3,
            "top10":        top10,
            "not_ranking":  len([k for k in intel
                                  if k.get("current_position") == "—"]),
        })
    except Exception as e:
        _set_done({"success": False, "message": str(e)})


@app.post("/target-scan")
def trigger_target_scan(background_tasks: BackgroundTasks):
    if _is_running():
        return JSONResponse(
            status_code=409,
            content={"error": f"Job already running: {_job_status['current_job']}"}
        )
    background_tasks.add_task(_run_target_scan)
    return {"message": "Target scan started", "job": "Target Scan"}


@app.get("/targets")
def get_targets():
    """Current target keyword intel from latest JSON."""
    try:
        with open("dashboard/data/targets.json") as f:
            return json.load(f)
    except Exception as e:
        return JSONResponse(status_code=404,
                            content={"error": "No target data yet. Run a target scan first."})


# ══════════════════════════════════════════════════════════════════════
#  AI OVERVIEW SCAN
# ══════════════════════════════════════════════════════════════════════
def _run_ai_scan():
    _set_running("AI Overview Scan")
    try:
        from src.credentials_loader import setup_credentials
        from src.ai_overview        import run_ai_overview_check
        from src.data_exporter      import export_all_data

        setup_credentials()
        result = run_ai_overview_check()

        if not result:
            _set_done({"success": False,
                       "message": "No results. Check SERPAPI_KEY."})
            return

        ai_results = result.get("results", [])
        cited      = len([r for r in ai_results if r.get("site_cited")])
        has_ov     = len([r for r in ai_results if r.get("has_overview")])

        try:
            from src.analyzer import analyze_changes
            report = analyze_changes()
            if report:
                export_all_data(report=report, ai_results=ai_results)
        except Exception:
            pass

        _set_done({
            "success":      True,
            "message":      "AI Overview scan complete",
            "checked":      len(ai_results),
            "has_overview": has_ov,
            "cited":        cited,
            "not_cited":    has_ov - cited,
        })
    except Exception as e:
        _set_done({"success": False, "message": str(e)})


@app.post("/ai-scan")
def trigger_ai_scan(background_tasks: BackgroundTasks):
    if _is_running():
        return JSONResponse(
            status_code=409,
            content={"error": f"Job already running: {_job_status['current_job']}"}
        )
    background_tasks.add_task(_run_ai_scan)
    return {"message": "AI Overview scan started", "job": "AI Overview Scan"}


# ══════════════════════════════════════════════════════════════════════
#  JOB POLL — frontend polls this to get result
# ══════════════════════════════════════════════════════════════════════
@app.get("/job-status")
def job_status():
    return {
        "running":     _job_status["running"],
        "current_job": _job_status["current_job"],
        "last_run":    _job_status["last_run"],
        "last_result": _job_status["last_result"],
    }
