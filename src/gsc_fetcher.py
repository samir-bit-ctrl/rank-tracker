from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from config.settings import (
    SITE_URL, DAYS_TO_FETCH, MAX_KEYWORDS, CREDENTIALS_PATH
)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def get_gsc_service():
    """Authenticate and return GSC service client."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("searchconsole", "v1", credentials=creds)


def fetch_keyword_data():
    """
    Fetch keyword performance data from GSC.
    Returns list of dicts: {keyword, position, clicks, impressions, ctr}
    """
    service = get_gsc_service()

    end_date   = datetime.today() - timedelta(days=3)  # GSC has ~3 day delay
    start_date = end_date - timedelta(days=DAYS_TO_FETCH)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate":   end_date.strftime("%Y-%m-%d"),
        "dimensions": ["query"],
        "rowLimit": MAX_KEYWORDS,
        "dataState": "final"
    }

    response = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body=request_body
    ).execute()

    rows = response.get("rows", [])

    if not rows:
        print("⚠️  No data returned from GSC. Check site URL and permissions.")
        return []

    results = []
    for row in rows:
        results.append({
            "keyword":     row["keys"][0],
            "position":    round(row["position"], 1),
            "clicks":      row["clicks"],
            "impressions": row["impressions"],
            "ctr":         round(row["ctr"] * 100, 2),  # as percentage
            "date":        end_date.strftime("%Y-%m-%d")
        })

    # Sort by clicks descending
    results.sort(key=lambda x: x["clicks"], reverse=True)

    print(f"✅ Fetched {len(results)} keywords from GSC")
    return results


if __name__ == "__main__":
    data = fetch_keyword_data()
    for row in data[:10]:   # preview top 10
        print(row)