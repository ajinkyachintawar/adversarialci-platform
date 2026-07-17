"""
Scraper Benchmark: requests+BeautifulSoup vs Firecrawl
======================================================
Same 6 real pricing pages, head to head. Measures success, latency,
extracted text volume, pricing-signal hits, and junk ratio.

Run:  .venv/bin/python eval/scraper_benchmark.py
Out:  eval/results/scraper_benchmark_<timestamp>.json
"""

import sys
import os
import re
import json
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FIRECRAWL_API_KEY

TEST_URLS = {
    "MongoDB":    "https://www.mongodb.com/pricing",
    "Pinecone":   "https://www.pinecone.io/pricing/",
    "Weaviate":   "https://weaviate.io/pricing",
    "AWS":        "https://aws.amazon.com/pricing/",
    "Salesforce": "https://www.salesforce.com/editions-pricing/sales-cloud/",
    "HubSpot":    "https://www.hubspot.com/pricing/crm",
}

PRICING_PATTERNS = [
    r"\$\d[\d,]*", r"free tier", r"free plan", r"per month", r"per user",
    r"per seat", r"/month", r"/mo\b", r"/year", r"monthly", r"annually",
    r"enterprise", r"professional", r"starter", r"standard", r"premium",
    r"serverless", r"dedicated", r"pay.as.you.go", r"on.demand",
]
JUNK_PATTERNS = [
    "cookie", "accept all", "privacy policy", "terms of service",
    "sign in", "log in", "subscribe", "newsletter",
]


def score_text(text: str) -> dict:
    low = text.lower()
    dollar_amounts = sorted(set(re.findall(r"\$\d[\d,]*(?:\.\d+)?", text)))
    return {
        "text_chars": len(text),
        "pricing_pattern_hits": sum(len(re.findall(p, low)) for p in PRICING_PATTERNS),
        "distinct_dollar_amounts": len(dollar_amounts),
        "dollar_amounts_sample": dollar_amounts[:15],
        "junk_hits": sum(low.count(p) for p in JUNK_PATTERNS),
    }


def scrape_bs4(url: str) -> dict:
    t0 = time.time()
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return {"success": r.status_code == 200 and len(text) > 200,
                "http_status": r.status_code,
                "seconds": round(time.time() - t0, 2),
                **score_text(text), "sample": text[:300]}
    except Exception as e:
        return {"success": False, "seconds": round(time.time() - t0, 2),
                "error": str(e)}


def scrape_firecrawl(url: str) -> dict:
    t0 = time.time()
    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                     "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            timeout=90,
        )
        data = r.json()
        md = (data.get("data") or {}).get("markdown", "")
        return {"success": bool(md) and len(md) > 200,
                "http_status": r.status_code,
                "seconds": round(time.time() - t0, 2),
                **score_text(md), "sample": md[:300]}
    except Exception as e:
        return {"success": False, "seconds": round(time.time() - t0, 2),
                "error": str(e)}


def run() -> dict:
    results = {}
    for company, url in TEST_URLS.items():
        print(f"\n── {company} — {url}")
        bs4_res = scrape_bs4(url)
        print(f"   bs4       : ok={bs4_res['success']} {bs4_res['seconds']}s "
              f"chars={bs4_res.get('text_chars', 0)} "
              f"$amounts={bs4_res.get('distinct_dollar_amounts', 0)} "
              f"junk={bs4_res.get('junk_hits', 0)}")
        fc_res = scrape_firecrawl(url)
        print(f"   firecrawl : ok={fc_res['success']} {fc_res['seconds']}s "
              f"chars={fc_res.get('text_chars', 0)} "
              f"$amounts={fc_res.get('distinct_dollar_amounts', 0)} "
              f"junk={fc_res.get('junk_hits', 0)}")
        results[company] = {"url": url, "bs4": bs4_res, "firecrawl": fc_res}

    def totals(key):
        rs = [r[key] for r in results.values()]
        ok = [r for r in rs if r.get("success")]
        return {
            "success_rate": f"{len(ok)}/{len(rs)}",
            "avg_seconds": round(sum(r["seconds"] for r in rs) / len(rs), 2),
            "total_dollar_amounts": sum(r.get("distinct_dollar_amounts", 0) for r in rs),
            "total_pricing_hits": sum(r.get("pricing_pattern_hits", 0) for r in rs),
            "total_junk_hits": sum(r.get("junk_hits", 0) for r in rs),
        }

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "note": "crawl4ai skipped: not installed, not a candidate (Firecrawl API chosen path)",
        "summary": {"bs4": totals("bs4"), "firecrawl": totals("firecrawl")},
        "results": results,
    }

    os.makedirs("eval/results", exist_ok=True)
    path = f"eval/results/scraper_benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n== SUMMARY ==")
    print(json.dumps(report["summary"], indent=2))
    print(f"saved -> {path}")
    return report


if __name__ == "__main__":
    run()
