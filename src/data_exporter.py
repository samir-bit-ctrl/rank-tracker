import json
import os
from datetime import datetime


SPAM = ["http", "www.", ".com", ".in", ".org", "survey", "whitecastle"]


def _is_spam(keyword: str) -> bool:
    return any(s in keyword.lower() for s in SPAM)


def _load_history() -> dict:
    if not os.path.exists("data/history.json"):
        return {}
    with open("data/history.json") as f:
        return json.load(f)


def export_all_data(report: dict,
                    target_intel: list = None,
                    ai_results:   list = None):
    """
    Export all data to JSON files in dashboard/data/
    Called from main.py after every run.
    """
    target_intel = target_intel or []
    ai_results   = ai_results   or []

    os.makedirs("dashboard/data", exist_ok=True)

    history      = _load_history()
    dates        = sorted(history.keys())
    today        = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── overview.json ─────────────────────────────────────────────────
    keywords = []
    if dates:
        latest  = history[dates[-1]]
        keywords = [
            v for v in latest.values()
            if not _is_spam(v.get("keyword", ""))
        ]

    # Daily trend (14 days)
    pos_trend    = []
    clicks_trend = []
    for d in dates[-14:]:
        snap      = history[d]
        positions = [v.get("position", 0) for v in snap.values()
                     if v.get("position", 0) > 0]
        avg_pos   = round(sum(positions) / len(positions), 1) if positions else 0
        total_cl  = sum(v.get("clicks", 0) for v in snap.values())
        pos_trend.append({"date": d[-5:], "value": avg_pos})
        clicks_trend.append({"date": d[-5:], "value": total_cl})

    # Rank zones
    total = len(keywords) or 1
    zones = {
        "Top 3":  len([k for k in keywords if k.get("position", 99) <= 3]),
        "4–10":   len([k for k in keywords if 3  < k.get("position", 99) <= 10]),
        "11–20":  len([k for k in keywords if 10 < k.get("position", 99) <= 20]),
        "21–50":  len([k for k in keywords if 20 < k.get("position", 99) <= 50]),
        "50+":    len([k for k in keywords if k.get("position", 99) > 50]),
    }

    # CTR by position buckets
    ctr_buckets = {}
    for k in keywords:
        pos     = int(k.get("position", 99))
        if pos > 20: continue
        ctr     = k.get("ctr", 0)
        ctr_pct = ctr * 100 if ctr < 1 else ctr
        if pos not in ctr_buckets:
            ctr_buckets[pos] = []
        ctr_buckets[pos].append(ctr_pct)
    ctr_by_pos = [
        {"position": p, "ctr": round(sum(v)/len(v), 2)}
        for p, v in sorted(ctr_buckets.items()) if v
    ]

    # Top keywords
    top_kws = sorted(
        [k for k in keywords if not _is_spam(k.get("keyword", ""))],
        key=lambda x: x.get("clicks", 0), reverse=True
    )[:10]

    # Health score
    top10_count  = len([k for k in keywords if k.get("position", 99) <= 10])
    top10_pct    = top10_count / total
    health_score = min(round(top10_pct * 100), 100)
    if health_score >= 80:   health_label = "Excellent"
    elif health_score >= 60: health_label = "Good"
    elif health_score >= 40: health_label = "Needs Work"
    else:                    health_label = "Critical"

    overview = {
        "updated":      today,
        "site":         "studyriserr.com",
        "health": {
            "score": health_score,
            "label": health_label
        },
        "stats": {
            "total_keywords":  len(keywords),
            "avg_position":    report.get("avg_position", 0),
            "total_clicks":    sum(k.get("clicks", 0) for k in keywords),
            "total_impressions": sum(k.get("impressions", 0) for k in keywords),
            "avg_ctr":         round(
                sum(k.get("ctr", 0) * 100 if k.get("ctr", 0) < 1
                    else k.get("ctr", 0) for k in keywords) / total, 2
            ),
            "improved":        len(report.get("improved", [])),
            "dropped":         len(report.get("dropped", [])),
            "new_today":       len(report.get("new", [])),
            "lost_today":      len(report.get("lost", [])),
            "top3":            zones["Top 3"],
            "top10":           top10_count,
        },
        "zones":        [
            {"label": k, "count": v,
             "pct": round(v/total*100, 1)}
            for k, v in zones.items()
        ],
        "pos_trend":    pos_trend,
        "clicks_trend": clicks_trend,
        "ctr_by_pos":   ctr_by_pos,
        "top_keywords": [
            {"keyword": k["keyword"],
             "clicks":  k.get("clicks", 0),
             "position": round(k.get("position", 0), 1)}
            for k in top_kws
        ],
        "improved": [
            {"keyword": k["keyword"],
             "prev":    k.get("previous_position", 0),
             "current": k.get("position", 0),
             "delta":   k.get("delta", 0)}
            for k in report.get("improved", [])[:10]
        ],
        "dropped": [
            {"keyword": k["keyword"],
             "prev":    k.get("previous_position", 0),
             "current": k.get("position", 0),
             "delta":   k.get("delta", 0)}
            for k in report.get("dropped", [])[:10]
        ],
    }

    with open("dashboard/data/overview.json", "w") as f:
        json.dump(overview, f, indent=2)
    print("✅ overview.json exported")

    # ── targets.json ──────────────────────────────────────────────────
    targets_data = {
        "updated": today,
        "keywords": []
    }

    # Group by seed
    seeds = {}
    for k in target_intel:
        seed = k.get("seed", k["keyword"])
        if seed not in seeds:
            seeds[seed] = {
                "seed":       seed,
                "mode":       k.get("mode", "exact"),
                "variants":   [],
                "total_clicks":      0,
                "total_impressions": 0,
                "best_position":     999,
                "ranking_count":     0,
            }
        pos = k.get("current_position", "—")
        seeds[seed]["variants"].append({
            "keyword":    k["keyword"],
            "position":   pos,
            "prev":       k.get("prev_position", "—"),
            "delta":      k.get("delta", 0),
            "clicks":     k.get("clicks_7d", 0),
            "impressions":k.get("impressions_7d", 0),
            "ctr":        k.get("ctr", 0),
            "best":       k.get("best_position", "—"),
            "worst":      k.get("worst_position", "—"),
            "trend":      k.get("trend", []),
            "status":     k.get("status", ""),
            "opportunity":k.get("opportunity", ""),
            "consistency":k.get("consistency", ""),
            "url":        k.get("ranking_url", ""),
        })
        seeds[seed]["total_clicks"]      += k.get("clicks_7d", 0)
        seeds[seed]["total_impressions"] += k.get("impressions_7d", 0)
        if isinstance(pos, (int, float)) and pos < seeds[seed]["best_position"]:
            seeds[seed]["best_position"] = pos
            seeds[seed]["ranking_count"] += 1

    targets_data["keywords"] = list(seeds.values())
    targets_data["summary"] = {
        "total_seeds":    len(seeds),
        "total_variants": len(target_intel),
        "top3":  len([k for k in target_intel
                      if isinstance(k.get("current_position"), float)
                      and k["current_position"] <= 3]),
        "top10": len([k for k in target_intel
                      if isinstance(k.get("current_position"), float)
                      and k["current_position"] <= 10]),
        "not_ranking": len([k for k in target_intel
                            if k.get("current_position") == "—"]),
    }

    with open("dashboard/data/targets.json", "w") as f:
        json.dump(targets_data, f, indent=2)
    print("✅ targets.json exported")

    # ── ai.json ───────────────────────────────────────────────────────
    if ai_results:
        ai_data = {
            "updated":   today,
            "summary": {
                "total":        len(ai_results),
                "has_overview": len([r for r in ai_results
                                     if r.get("has_overview")]),
                "cited":        len([r for r in ai_results
                                     if r.get("site_cited")]),
                "not_cited":    len([r for r in ai_results
                                     if r.get("has_overview")
                                     and not r.get("site_cited")]),
                "no_overview":  len([r for r in ai_results
                                     if not r.get("has_overview")]),
            },
            "keywords": [
                {
                    "seed":         r.get("seed", ""),
                    "ai_keyword":   r.get("ai_keyword",
                                         r.get("keyword", "")),
                    "has_overview": r.get("has_overview", False),
                    "site_cited":   r.get("site_cited", False),
                    "cite_snippet": r.get("cite_snippet", ""),
                    "cited_count":  r.get("cited_count", 0),
                    "organic_pos":  r.get("organic_pos", None),
                    "organic_url":  r.get("organic_url", ""),
                    "opportunity":  r.get("opportunity", ""),
                    "paa":          r.get("paa", []),
                    "related":      r.get("related", []),
                }
                for r in ai_results
            ]
        }

        with open("dashboard/data/ai.json", "w") as f:
            json.dump(ai_data, f, indent=2)
        print("✅ ai.json exported")

    print("✅ All JSON data exported to dashboard/data/")
