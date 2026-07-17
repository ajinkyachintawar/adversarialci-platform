"""
Firecrawl Client
================
Thin wrapper around the Firecrawl /v1/scrape endpoint.
Returns clean markdown for a URL (handles JS-heavy pages, unlike requests+bs4).
"""

import time
import requests
from config import FIRECRAWL_API_KEY

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"

CREDITS_USED = 0  # module-level spend counter, one credit per successful scrape


def get_credits_used() -> int:
    return CREDITS_USED


def scrape_url(url: str, timeout: int = 90) -> dict | None:
    """
    Scrape a URL via Firecrawl and return clean markdown.

    Returns:
        {"markdown": str, "title": str|None, "url": url, "status": int, "seconds": float}
        or None on failure (never raises).
    """
    global CREDITS_USED
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {"url": url, "formats": ["markdown"], "onlyMainContent": True}

    for attempt in range(2):
        start = time.time()
        try:
            resp = requests.post(FIRECRAWL_URL, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            print(f"  ⚠️  [Firecrawl] request error for {url}: {e}")
            return None
        elapsed = time.time() - start

        if resp.status_code == 200:
            payload = resp.json().get("data", {})
            CREDITS_USED += 1
            return {
                "markdown": payload.get("markdown", "") or "",
                "title": (payload.get("metadata") or {}).get("title"),
                "url": url,
                "status": resp.status_code,
                "seconds": round(elapsed, 2),
            }

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == 0:
                print(f"  ⚠️  [Firecrawl] {resp.status_code} for {url}, retrying in 5s...")
                time.sleep(5)
                continue

        print(f"  ⚠️  [Firecrawl] scrape failed ({resp.status_code}) for {url}")
        return None

    return None
