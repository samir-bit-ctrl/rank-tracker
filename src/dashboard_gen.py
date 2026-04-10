import os
import json
import shutil
from jinja2 import Template
from config.settings import SITE_URL

TEMPLATE_PATH = "dashboard/template.html"
OUTPUT_PATH   = "dashboard/index.html"


def _get_site_name():
    url = SITE_URL.replace("sc-domain:", "").replace("https://", "").replace("http://", "").strip("/")
    return url


def _build_dist_data(all_keywords: list) -> dict:
    """Build position distribution data for Chart.js."""
    buckets = {str(i): 0 for i in range(1, 16)}
    buckets["16+"] = 0
    for kw in all_keywords:
        pos = int(kw["position"])
        if pos <= 15:
            buckets[str(pos)] += 1
        else:
            buckets["16+"] += 1
    return {
        "labels": list(buckets.keys()),
        "values": list(buckets.values())
    }


def _build_rank_zones(all_keywords: list) -> list:
    total = len(all_keywords) or 1
    zones = [
        {"label": "Top 3",   "color": "#fbbf24",
         "count": len([k for k in all_keywords if k["position"] <= 3])},
        {"label": "4 – 10",  "color": "#34d399",
         "count": len([k for k in all_keywords if 3  < k["position"] <= 10])},
        {"label": "11 – 20", "color": "#60a5fa",
         "count": len([k for k in all_keywords if 10 < k["position"] <= 20])},
        {"label": "20+",     "color": "#f87171",
         "count": len([k for k in all_keywords if k["position"] > 20])},
    ]
    for z in zones:
        z["pct"] = round(z["count"] / total * 100, 1)
    return zones


def _enrich(kw: dict, status: str = "stable") -> dict:
    """Add status + safe delta to a keyword dict."""
    return {**kw, "status": status, "delta": kw.get("delta", 0)}


def generate_dashboard(report: dict):
    """Generate index.html from report data."""
    os.makedirs("dashboard", exist_ok=True)

    # Copy template if not already there
    if not os.path.exists(TEMPLATE_PATH):
        shutil.copy("dashboard/template.html", TEMPLATE_PATH)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = Template(f.read())

    # Build all_keywords list (improved + dropped + stable + new)
    improved = [_enrich(k, "improved") for k in report["improved"]]
    dropped  = [_enrich(k, "dropped")  for k in report["dropped"]]
    stable   = [_enrich(k, "stable")   for k in report["stable"]]
    new_kws  = [_enrich(k, "new")      for k in report["new"]]
    lost_kws = [_enrich(k, "lost")     for k in report["lost"]]

    all_keywords = improved + dropped + stable + new_kws
    all_keywords.sort(key=lambda x: x["clicks"], reverse=True)

    html = template.render(
        site_name        = _get_site_name(),
        today_date       = report["today_date"],
        total_keywords   = report["total_keywords"],
        avg_position     = report["avg_position"],
        improved_count   = len(report["improved"]),
        dropped_count    = len(report["dropped"]),
        new_count        = len(report["new"]),
        lost_count       = len(report["lost"]),
        improved         = improved[:10],
        dropped          = dropped[:10],
        new_keywords     = new_kws[:10],
        lost_keywords    = lost_kws[:10],
        all_keywords     = all_keywords,
        rank_zones       = _build_rank_zones(all_keywords),
        dist_data        = _build_dist_data(all_keywords),
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Dashboard generated → {OUTPUT_PATH}")