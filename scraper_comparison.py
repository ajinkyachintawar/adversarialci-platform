"""
Scraper Comparison: BeautifulSoup vs Crawl4AI (v2)
===================================================
Fixed version with better text extraction and keyword matching.

Setup:
    pip install beautifulsoup4 requests crawl4ai playwright
    playwright install chromium

Run:
    python scraper_comparison_v2.py
"""

import time
import asyncio
import re
from typing import Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

# Crawl4AI import (async)
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("crawl4ai not installed. Run: pip install crawl4ai")


TEST_URLS = {
    "MongoDB":    "https://www.mongodb.com/pricing",
    "Pinecone":   "https://www.pinecone.io/pricing/",
    "Weaviate":   "https://weaviate.io/pricing",
    "AWS":        "https://aws.amazon.com/pricing/",
    "Salesforce": "https://www.salesforce.com/editions-pricing/sales-cloud/",
    "HubSpot":    "https://www.hubspot.com/pricing/crm"
}

PRICING_PATTERNS = [
    r"\$\d+",
    r"free tier", r"free plan", r"per month", r"per user", r"per seat",
    r"/month", r"/mo", r"/year", r"monthly", r"annually", r"pricing",
    r"enterprise", r"professional", r"starter", r"standard", r"premium",
    r"serverless", r"dedicated", r"pay.as.you.go", r"on.demand"
]


@dataclass
class ScraperResult:
    scraper: str
    url: str
    success: bool
    time_seconds: float
    text_length: int
    pricing_bullets: list
    raw_sample: str = ""
    error: Optional[str] = None


def extract_pricing_bullets(text, max_bullets=15):
    bullets = []
    chunks = re.split(r'[.\n]|\s{2,}', text)
    
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 15 or len(chunk) > 400:
            continue
        
        chunk_lower = chunk.lower()
        has_pricing = any(re.search(p, chunk_lower) for p in PRICING_PATTERNS)
        
        if has_pricing:
            clean = re.sub(r'\s+', ' ', chunk).strip()
            if clean and clean not in bullets:
                bullets.append(clean)
                if len(bullets) >= max_bullets:
                    break
    return bullets


def scrape_beautifulsoup(url):
    start = time.time()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        bullets = extract_pricing_bullets(text)
        elapsed = time.time() - start
        
        return ScraperResult(
            scraper="BeautifulSoup", url=url, success=True,
            time_seconds=round(elapsed, 2), text_length=len(text),
            pricing_bullets=bullets, raw_sample=text[:500]
        )
    except Exception as e:
        return ScraperResult(
            scraper="BeautifulSoup", url=url, success=False,
            time_seconds=round(time.time() - start, 2), text_length=0,
            pricing_bullets=[], error=str(e)
        )


async def scrape_crawl4ai(url):
    if not CRAWL4AI_AVAILABLE:
        return ScraperResult(
            scraper="Crawl4AI", url=url, success=False,
            time_seconds=0, text_length=0, pricing_bullets=[],
            error="crawl4ai not installed"
        )
    
    start = time.time()
    try:
        async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
            result = await crawler.arun(url=url, bypass_cache=True)
            
            if not result.success:
                raise Exception(result.error_message or "Crawl failed")
            
            text = result.markdown or result.cleaned_html or ""
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            text = re.sub(r'[#*_`]', '', text)
            
            bullets = extract_pricing_bullets(text)
            elapsed = time.time() - start
            
            return ScraperResult(
                scraper="Crawl4AI", url=url, success=True,
                time_seconds=round(elapsed, 2), text_length=len(text),
                pricing_bullets=bullets, raw_sample=text[:500]
            )
    except Exception as e:
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg:
            error_msg = "Run: playwright install chromium"
        
        return ScraperResult(
            scraper="Crawl4AI", url=url, success=False,
            time_seconds=round(time.time() - start, 2), text_length=0,
            pricing_bullets=[], error=error_msg
        )


async def run_comparison():
    print("\n" + "=" * 60)
    print("  SCRAPER COMPARISON: BeautifulSoup vs Crawl4AI v2")
    print("=" * 60)
    
    results = []
    
    for name, url in TEST_URLS.items():
        print(f"\n--- {name} ---")
        print(f"URL: {url}")
        
        # BeautifulSoup
        bs_result = scrape_beautifulsoup(url)
        results.append(bs_result)
        
        if bs_result.success:
            print(f"  BS4:  {bs_result.time_seconds}s | {bs_result.text_length:,} chars | {len(bs_result.pricing_bullets)} bullets")
            if bs_result.pricing_bullets:
                print(f"        Sample: {bs_result.pricing_bullets[0][:70]}...")
        else:
            print(f"  BS4:  FAILED - {bs_result.error}")
        
        # Crawl4AI
        c4_result = await scrape_crawl4ai(url)
        results.append(c4_result)
        
        if c4_result.success:
            print(f"  C4AI: {c4_result.time_seconds}s | {c4_result.text_length:,} chars | {len(c4_result.pricing_bullets)} bullets")
            if c4_result.pricing_bullets:
                print(f"        Sample: {c4_result.pricing_bullets[0][:70]}...")
        else:
            print(f"  C4AI: FAILED - {c4_result.error}")
    
    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    
    bs_results = [r for r in results if r.scraper == "BeautifulSoup"]
    c4_results = [r for r in results if r.scraper == "Crawl4AI"]
    
    bs_success = sum(1 for r in bs_results if r.success)
    c4_success = sum(1 for r in c4_results if r.success)
    
    bs_bullets = sum(len(r.pricing_bullets) for r in bs_results if r.success)
    c4_bullets = sum(len(r.pricing_bullets) for r in c4_results if r.success)
    
    bs_time = sum(r.time_seconds for r in bs_results if r.success) / max(bs_success, 1)
    c4_time = sum(r.time_seconds for r in c4_results if r.success) / max(c4_success, 1)
    
    print(f"\n  {'Metric':<20} {'BeautifulSoup':<15} {'Crawl4AI':<15}")
    print(f"  {'-'*50}")
    print(f"  {'Success':<20} {bs_success}/{len(bs_results):<14} {c4_success}/{len(c4_results):<14}")
    print(f"  {'Avg Time':<20} {bs_time:.2f}s{'':<11} {c4_time:.2f}s")
    print(f"  {'Total Bullets':<20} {bs_bullets:<15} {c4_bullets:<15}")
    print(f"  {'JS Rendering':<20} {'No':<15} {'Yes':<15}")
    
    print("\n  Per-site bullets:")
    for name, url in TEST_URLS.items():
        bs = next((r for r in bs_results if r.url == url), None)
        c4 = next((r for r in c4_results if r.url == url), None)
        bs_b = len(bs.pricing_bullets) if bs and bs.success else "X"
        c4_b = len(c4.pricing_bullets) if c4 and c4.success else "X"
        print(f"    {name:<15} BS4: {bs_b:<3}  C4AI: {c4_b:<3}")
    
    print("\n" + "=" * 60)
    print("  RECOMMENDATION")
    print("=" * 60)
    
    if c4_success == 0:
        print("\n  Crawl4AI failed. Run: playwright install chromium")
    elif c4_bullets > bs_bullets * 1.3:
        print("\n  -> Crawl4AI wins. Better for JS-heavy pricing pages.")
    elif bs_bullets >= c4_bullets and bs_time < c4_time * 0.5:
        print("\n  -> BeautifulSoup wins. Fast and good enough.")
    else:
        print("\n  -> Hybrid: BS4 first, fallback to C4AI if < 3 bullets.")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_comparison())