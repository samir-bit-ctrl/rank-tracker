"""
aio_extractor.py — Free AI Overview citation extractor using Playwright.
Scrapes Google Search results for AI Overview citation URLs without using SerpAPI.
Runs headless Chromium with realistic browser fingerprint to avoid detection.
"""

import asyncio
import json
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import urlparse, unquote, quote_plus

import gspread
from google.oauth2 import service_account
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from config.settings import CREDENTIALS_PATH, SHEET_ID, SITE_URL

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_NAME = "🔍 AIO Citations"

# ── Selector targets for Google AI Overview citation modules ──────────
AIO_SELECTORS = [
    "div.Kevs9",           # primary citation container
    "div.VqeGe",           # secondary citation block
    "div.wDYxhc",          # AI overview wrapper
    "div.X5LH0c",          # citation list container
    "div[data-attrid='wa:/description']",  # structured answer
    "div.LLtSOc",          # sources panel
    "div.ayRjaf",          # cited links block
    "cite",                # fallback
]

# Desktop user agents — rotate to reduce fingerprinting
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

BLOCKED_DOMAINS = [
    "google.com", "google.co.in", "googleapis.com",
    "gstatic.com", "youtube.com", "googleusercontent.com",
    "accounts.google.com", "support.google.com",
]

CACHE_FILE = "data/aio_cache.json"


# ══════════════════════════════════════════════════════════════════════
#  CACHE OPERATORS
# ══════════════════════════════════════════════════════════════════════

def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict):
    os.makedirs("data", exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=2)
    os.replace(tmp, CACHE_FILE)


def _cache_key(keyword: str) -> str:
    return keyword.lower().strip()


def _is_cache_fresh(entry: dict, max_hours: int = 24) -> bool:
    ts = entry.get("timestamp", "")
    if not ts:
        return False
    try:
        cached_at = datetime.fromisoformat(ts)
        diff      = (datetime.now() - cached_at).total_seconds() / 3600
        return diff < max_hours
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════
#  URL CLEANER
# ══════════════════════════════════════════════════════════════════════

def _clean_url(raw: str) -> str | None:
    if not raw:
        return None

    if "/url?q=" in raw:
        match = re.search(r"/url\?q=([^&]+)", raw)
        if match:
            raw = unquote(match.group(1))

    raw = raw.strip().rstrip("/")

    try:
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        domain = parsed.netloc.lower().replace("www.", "")
        if any(bd in domain for bd in BLOCKED_DOMAINS):
            return None
        return raw
    except Exception:
        return None


def _is_our_site(url: str) -> bool:
    site = SITE_URL.replace("sc-domain:", "").replace("https://", "").replace("http://", "").strip("/")
    return site.lower() in url.lower()


# ══════════════════════════════════════════════════════════════════════
#  SINGLE KEYWORD SCRAPER
# ══════════════════════════════════════════════════════════════════════

async def scrape_aio_for_keyword(page, keyword: str) -> dict:
    encoded_query = quote_plus(keyword)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&gl=in"

    try:
        await page.goto(url, wait_until="load", timeout=30000)
        await page.wait_for_timeout(random.randint(4000, 6000))

        # Light scroll execution to trigger responsive asset layouts
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(1500)

        has_aio    = False
        cited_urls = []
        we_are_cited = False
        cite_snippet = ""

        for selector in AIO_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    has_aio = True
                    for el in elements:
                        links = await el.query_selector_all("a[href]")
                        for link in links:
                            href = await link.get_attribute("href")
                            text = await link.inner_text()
                            clean = _clean_url(href)
                            if clean and clean not in cited_urls:
                                cited_urls.append(clean)
                                if _is_our_site(clean):
                                    we_are_cited = True
                                    cite_snippet = text[:80] if text else ""
                    if cited_urls:
                        break
            except Exception:
                continue

        # Organic parsing
        organic_pos  = None
        organic_url  = ""
        our_site     = SITE_URL.replace("sc-domain:", "").replace("https://", "").strip("/")

        try:
            search_results = await page.query_selector_all("div.g a[href]")
            rank = 0
            for result in search_results:
                href = await result.get_attribute("href")
                if href and href.startswith("http") and "google" not in href:
                    rank += 1
                    if our_site.lower() in href.lower():
                        organic_pos = rank
                        organic_url = href
                        break
                    if rank > 15:
                        break
        except Exception:
            pass

        # PAA Block parsing
        paa = []
        try:
            paa_els = await page.query_selector_all("div.related-question-pair span")
            for el in paa_els[:4]:
                text = await el.inner_text()
                if text and len(text) > 10:
                    paa.append(text.strip())
        except Exception:
            pass

        return {
            "keyword":       keyword,
            "has_aio":       has_aio,
            "cited_urls":    cited_urls,
            "cited_count":   len(cited_urls),
            "we_are_cited":  we_are_cited,
            "cite_snippet":  cite_snippet,
            "organic_pos":   organic_pos,
            "organic_url":   organic_url,
            "paa":           paa,
            "timestamp":     datetime.now().isoformat(),
            "error":         None,
        }

    except PWTimeout:
        return {
            "keyword":   keyword,
            "has_aio":   False,
            "error":     "Timeout",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "keyword":   keyword,
            "has_aio":   False,
            "error":     str(e),
            "timestamp": datetime.now().isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════
#  BATCH SCRAPER
# ══════════════════════════════════════════════════════════════════════

async def _run_batch(keywords: list, use_cache: bool = True, delay_range: tuple = (4, 8)) -> list:
    cache    = _load_cache() if use_cache else {}
    results  = []
    to_scrape = []

    for kw in keywords:
        key   = _cache_key(kw)
        entry = cache.get(key)
        if use_cache and entry and _is_cache_fresh(entry):
            print(f"  📦 Cache hit: '{kw}'")
            results.append(entry)
        else:
            to_scrape.append(kw)

    if not to_scrape:
        print(f"  ✅ All {len(results)} keywords served from cache")
        return results

    print(f"  🌐 Scraping {len(to_scrape)} keywords ({len(results)} from cache)...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--lang=en-IN",
            ]
        )

        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        # FIX: Inject the anti-bot evasion parameters BEFORE creating the new page object
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            window.chrome = {runtime: {}};
        """)

        page = await context.new_page()

        for i, kw in enumerate(to_scrape):
            print(f"  [{i+1}/{len(to_scrape)}] '{kw}'...", end=" ", flush=True)

            result = await scrape_aio_for_keyword(page, kw)

            if result.get("error"):
                print(f"❌ {result['error']}")
            elif result.get("has_aio"):
                cited = "🎯 WE'RE CITED!" if result.get("we_are_cited") else f"{result.get('cited_count', 0)} sources"
                print(f"✅ AIO found — {cited}")
            else:
                print("— no AI Overview")

            results.append(result)

            cache[_cache_key(kw)] = result
            _save_cache(cache)

            if i < len(to_scrape) - 1:
                delay = random.uniform(*delay_range)
                await asyncio.sleep(delay)

        await browser.close()

    return results


# ══════════════════════════════════════════════════════════════════════
#  KEYWORD SELECTOR
# ══════════════════════════════════════════════════════════════════════

def get_priority_keywords(max_keywords: int = 50) -> list:
    from config.settings import TRACKED_KEYWORDS

    keywords = []

    if TRACKED_KEYWORDS:
        keywords.extend([k.lower().strip() for k in TRACKED_KEYWORDS])
        print(f"  📋 {len(TRACKED_KEYWORDS)} keywords from TRACKED_KEYWORDS")

    try:
        with open("data/history.json") as f:
            history = json.load(f)

        dates   = sorted(history.keys())
        latest  = history[dates[-1]]

        INFO_SIGNALS = [
            "how", "what", "when", "where", "which", "who", "why",
            "syllabus", "eligibility", "result", "admit card", "date",
            "fee", "college", "university", "exam", "form", "application",
            "course", "career", "salary", "scope",
        ]

        def is_informational(kw: str) -> bool:
            kw_lower = kw.lower()
            return any(sig in kw_lower for sig in INFO_SIGNALS)

        sorted_kws = sorted(
            latest.items(),
            key=lambda x: x[1].get("impressions", 0),
            reverse=True
        )

        added = 0
        for kw, data in sorted_kws:
            if kw not in keywords and is_informational(kw):
                keywords.append(kw)
                added += 1
            if added >= max_keywords - len(keywords):
                break

        print(f"  📊 Added {added} high-impression informational keywords from history")

    except Exception as e:
        print(f"  ⚠️  Could not load history keywords: {e}")

    seen = set()
    final = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            final.append(kw)
        if len(final) >= max_keywords:
            break

    print(f"  🎯 Total keywords selected: {len(final)}")
    return final


# ══════════════════════════════════════════════════════════════════════
#  GOOGLE SHEETS WRITER
# ══════════════════════════════════════════════════════════════════════

def write_aio_sheet(results: list):
    HEADER_DARK  = {"red": 0.192, "green": 0.212, "blue": 0.251}
    HEADER_MID   = {"red": 0.271, "green": 0.298, "blue": 0.349}
    ACCENT_GREEN = {"red": 0.196, "green": 0.533, "blue": 0.384}
    ACCENT_RED   = {"red": 0.757, "green": 0.267, "blue": 0.267}
    ACCENT_AMBER = {"red": 0.800, "green": 0.600, "blue": 0.200}
    WHITE        = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
    OFF_WHITE    = {"red": 0.980, "green": 0.980, "blue": 0.984}
    LIGHT_GREY   = {"red": 0.941, "green": 0.945, "blue": 0.953}
    DARK_TEXT    = {"red": 0.133, "green": 0.149, "blue": 0.180}
    SUBTLE_TEXT  = {"red": 0.420, "green": 0.447, "blue": 0.502}

    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        client      = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)

        try:
            ws = spreadsheet.worksheet(SHEET_NAME)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=500, cols=14)

        sid   = ws.id
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        total       = len(results)
        has_aio     = [r for r in results if r.get("has_aio")]
        we_cited    = [r for r in results if r.get("we_are_cited")]
        not_cited   = [r for r in has_aio  if not r.get("we_are_cited")]
        errors      = [r for r in results  if r.get("error")]

        rows = [
            [f"🔍 AIO CITATIONS — LOCAL SCRAPER — {today}", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["Total Checked", "Has AI Overview", "We're Cited", "Not Cited", "No AIO", "Errors", "", "", "", "", "", "", "", ""],
            [total, len(has_aio), len(we_cited), len(not_cited), total - len(has_aio), len(errors), "", "", "", "", "", "", "", ""],
            [""] * 14,
            ["Keyword", "Has AIO", "We're Cited", "Cite Snippet", "# Sources", "Source URLs", "Organic Pos", "Our URL", "PAA Questions", "Opportunity", "Method", "Last Checked", "", ""]
        ]

        header_row = len(rows) - 1

        for r in results:
            if r.get("error"):
                rows.append([r.get("keyword", ""), "⚠️ Error", "", r["error"], "", "", "", "", "", "", "Playwright", r.get("timestamp", "")[:16], "", ""])
                continue

            has_str   = "✅ Yes" if r.get("has_aio") else "❌ No"
            cited_str = "🎯 Yes — We're Cited!" if r.get("we_are_cited") else "❌ Not cited" if r.get("has_aio") else "—"

            org_pos = r.get("organic_pos")
            if r.get("we_are_cited"):
                opp = "🏆 Maintain — keep content fresh"
            elif r.get("has_aio") and org_pos and org_pos <= 5:
                opp = "⚡ Optimize — add FAQ schema"
            elif r.get("has_aio") and not r.get("we_are_cited"):
                opp = "📝 Add structured data + E-E-A-T"
            elif not r.get("has_aio") and org_pos and org_pos <= 3:
                opp = "✅ Strong organic — monitor"
            elif not org_pos:
                opp = "🚨 Not ranking — create content"
            else:
                opp = "📈 Improve content depth"

            urls      = r.get("cited_urls", [])
            urls_str  = "\n".join(urls[:3])
            paa_str   = " | ".join(r.get("paa", [])[:3])
            timestamp = r.get("timestamp", "")[:16]

            rows.append([
                r.get("keyword", ""), has_str, cited_str, r.get("cite_snippet", "—"),
                r.get("cited_count", 0), urls_str, r.get("organic_pos", "Not ranking"),
                r.get("organic_url", "—"), paa_str, opp, "Playwright (Free)", timestamp, "", ""
            ])

        ws.update("A1", rows)

        # Format layout engine
        formatting_requests = [
            {"repeatCell": {"range": {"sheetId": sid}, "cell": {"userEnteredFormat": {"backgroundColor": OFF_WHITE, "textFormat": {"fontSize": 10, "foregroundColor": DARK_TEXT}}}, "fields": "userEnteredFormat"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_DARK, "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 12}}}, "fields": "userEnteredFormat"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_MID, "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9}}}, "fields": "userEnteredFormat"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 3}, "cell": {"userEnteredFormat": {"backgroundColor": WHITE, "textFormat": {"fontSize": 14, "bold": True, "foregroundColor": DARK_TEXT}}}, "fields": "userEnteredFormat"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": header_row, "endRowIndex": header_row + 1}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_DARK, "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9}}}, "fields": "userEnteredFormat"}},
            {"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": sid, "startRowIndex": header_row + 1}], "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": "=ISEVEN(ROW())"}]}, "format": {"backgroundColor": LIGHT_GREY}}}, "index": 0}},
            {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": header_row + 1, "frozenColumnCount": 1, "hideGridlines": True}}, "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount,gridProperties.hideGridlines"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 240}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 3}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4}, "properties": {"pixelSize": 200}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6}, "properties": {"pixelSize": 280}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 8}, "properties": {"pixelSize": 280}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 8, "endIndex": 9}, "properties": {"pixelSize": 260}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 9, "endIndex": 10}, "properties": {"pixelSize": 220}, "fields": "pixelSize"}}
        ]

        data_start = header_row + 1
        for i, r in enumerate(results):
            row_idx = data_start + i
            color = ACCENT_GREEN if r.get("we_are_cited") else (ACCENT_AMBER if r.get("has_aio") else SUBTLE_TEXT)
            formatting_requests.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 2, "endColumnIndex": 3},
                "cell": {"userEnteredFormat": { "textFormat": {"foregroundColor": color, "bold": True}}},
                "fields": "userEnteredFormat.textFormat"
            }})

        spreadsheet.batch_update({"requests": formatting_requests})
        print(f"✅ AIO Citations sheet written — {len(results)} keywords")
        return True

    except Exception as e:
        print(f"❌ Failed to write AIO sheet: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════
#  EXPORT TO JSON
# ══════════════════════════════════════════════════════════════════════

def export_aio_json(results: list):
    os.makedirs("dashboard/data", exist_ok=True)
    total     = len(results)
    has_aio   = [r for r in results if r.get("has_aio")]
    we_cited  = [r for r in results if r.get("we_are_cited")]

    data = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "method":  "Playwright (Free — Local Scraper)",
        "summary": {
            "total":        total,
            "has_aio":      len(has_aio),
            "cited":        len(we_cited),
            "not_cited":    len(has_aio) - len(we_cited),
            "no_aio":       total - len(has_aio),
        },
        "keywords": [
            {
                "keyword":       r.get("keyword", ""),
                "has_aio":       r.get("has_aio", False),
                "we_are_cited":  r.get("we_are_cited", False),
                "cite_snippet":  r.get("cite_snippet", ""),
                "cited_count":   r.get("cited_count", 0),
                "cited_urls":    r.get("cited_urls", [])[:5],
                "organic_pos":   r.get("organic_pos"),
                "organic_url":   r.get("organic_url", ""),
                "paa":           r.get("paa", []),
                "error":         r.get("error"),
                "last_checked":  r.get("timestamp", "")[:16],
            }
            for r in results
        ]
    }

    path = "dashboard/data/aio_local.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ AIO JSON exported → {path}")


# ══════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def run_aio_extractor(
    keywords:    list  = None,
    max_keywords: int  = 50,
    use_cache:   bool  = True,
    write_sheet: bool  = True,
    write_json:  bool  = True,
) -> dict | None:
    print("\n🔍 Running AIO Extractor (Free Playwright Scraper)...")

    if keywords is None:
        keywords = get_priority_keywords(max_keywords)

    if not keywords:
        print("⚠️  No keywords to check")
        return None

    try:
        results = asyncio.run(_run_batch(keywords, use_cache=use_cache))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(_run_batch(keywords, use_cache=use_cache))

    if not results:
        print("⚠️  No results returned")
        return None

    if write_sheet:
        write_aio_sheet(results)
    if write_json:
        export_aio_json(results)

    has_aio  = len([r for r in results if r.get("has_aio")])
    cited    = len([r for r in results if r.get("we_are_cited")])
    print(f"\n📊 AIO Extraction Summary:")
    print(f"   Checked    : {len(results)}")
    print(f"   Has AIO    : {has_aio}")
    print(f"   We're cited: {cited}")
    print(f"   Not cited  : {has_aio - cited}")

    return {
        "results":  results,
        "summary": {
            "total":     len(results),
            "has_aio":   has_aio,
            "cited":     cited,
            "not_cited": has_aio - cited,
        }
    }

if __name__ == "__main__":
    # Standard standalone file testing block
    run_aio_extractor(max_keywords=2)