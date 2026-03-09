#!/usr/bin/env python3
"""
Historical scrape — runs ONCE per company.
Fetches HN 2024 + 2025, blog posts, migrations, complaints.
Now vertical-aware.

Run: python3 historical_scrape.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime, timezone
from db.atlas import connect, get_collection, save_research
from config import TAVILY_API_KEY
from sources.blog_agent import blog_agent
from sources.migration_agent import migration_agent
from verticals import list_verticals, get_vertical, get_hn_keywords


HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def hn_historical_year(company: str, year: int, vertical: str = "database") -> list:
    """Fetch HN posts for a company in a specific year."""
    start = int(datetime(year, 1, 1).timestamp())
    end = int(datetime(year, 12, 31, 23, 59).timestamp())
    company_lower = company.lower()
    
    # Get relevance keywords from vertical config
    relevance_keywords = get_hn_keywords(vertical)
    
    bullets = []
    
    try:
        params = {
            "query": company,
            "tags": "story",
            "hitsPerPage": 50,
            "numericFilters": f"created_at_i>{start},created_at_i<{end}"
        }
        response = requests.get(HN_SEARCH_URL, params=params, timeout=10)
        data = response.json()
        
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            url = hit.get("url", "")
            points = hit.get("points", 0)
            created = hit.get("created_at", "")[:10]
            title_lower = title.lower()
            
            if company_lower not in title_lower:
                continue
            
            has_relevance = any(k in title_lower for k in relevance_keywords)
            if not has_relevance and points < 50:
                continue
            
            bullets.append(
                f"[HN {year} {points}pts {created}] {title} — {url}"
            )
    
    except Exception as e:
        print(f"      ⚠️  HN {year} error: {e}")
    
    return bullets


def blog_historical(company: str, vertical: str = "database") -> list:
    """Fetch blog posts since 2024."""
    since = datetime(2024, 1, 1)
    return blog_agent(company, vertical, since=since)


def mark_historical_done(company: str, vertical: str):
    """Mark company as historically scraped for this vertical."""
    col = get_collection("companies")
    col.update_one(
        {"name": company},
        {"$set": {
            f"historical_scraped_{vertical}": True,
            f"historical_scraped_{vertical}_at": datetime.now(timezone.utc).replace(tzinfo=None)
        }}
    )


def is_historical_done(company: str, vertical: str) -> bool:
    """Check if historical scrape done for this vertical."""
    col = get_collection("companies")
    doc = col.find_one({"name": company})
    return doc.get(f"historical_scraped_{vertical}", False) if doc else False


def select_vertical() -> str:
    """Prompt user to select vertical."""
    available = list_verticals()
    
    print("\n📂 SELECT VERTICAL")
    print("─" * 40)
    for i, v in enumerate(available, 1):
        config = get_vertical(v)
        print(f"  [{i}] {config['display_name']}")
    
    while True:
        choice = input(f"\nEnter choice (1-{len(available)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                return available[idx]
        except ValueError:
            pass
        print(f"  ⚠️  Invalid choice")


def run_historical_scrape():
    print("""
╔══════════════════════════════════════════╗
║     HISTORICAL SCRAPE                    ║
║     Runs once per company per vertical   ║
╚══════════════════════════════════════════╝
    """)
    
    # Select vertical
    vertical = select_vertical()
    config = get_vertical(vertical)
    print(f"\n  ✅ Selected: {config['display_name']}")
    
    connect()
    companies_col = get_collection("companies")
    companies = list(companies_col.find({}, {"_id": 0}))
    
    if not companies:
        print("❌ No companies in Atlas. Run Mode 1 first.\n")
        return
    
    to_scrape = []
    skipped = []
    
    for company in companies:
        name = company["name"]
        if is_historical_done(name, vertical):
            skipped.append(name)
        else:
            to_scrape.append(name)
    
    if skipped:
        print(f"\n  ⏭️  Already done for {vertical}, skipping:")
        for name in skipped:
            print(f"     • {name}")
    
    if not to_scrape:
        print(f"\n  ✅ Historical scrape complete for all {vertical} companies.\n")
        return
    
    print(f"\n  📦 Scraping history for: {', '.join(to_scrape)}")
    print("=" * 40)
    
    total_new = 0
    
    for company in to_scrape:
        print(f"\n📦 Historical: {company}")
        print("─" * 40)
        
        company_total = 0
        
        # HN 2024
        print(f"  🟡 [HN 2024] Fetching...")
        hn_2024 = hn_historical_year(company, 2024, vertical)
        if hn_2024:
            save_research(
                company=company,
                data_type="sentiment",
                source_type="hn_2024",
                source_url="hn_algolia_2024",
                bullets=hn_2024
            )
        print(f"    ✅ HN 2024: {len(hn_2024)} bullets")
        company_total += len(hn_2024)
        
        # HN 2025
        print(f"  🟡 [HN 2025] Fetching...")
        hn_2025 = hn_historical_year(company, 2025, vertical)
        if hn_2025:
            save_research(
                company=company,
                data_type="sentiment",
                source_type="hn_2025",
                source_url="hn_algolia_2025",
                bullets=hn_2025
            )
        print(f"    ✅ HN 2025: {len(hn_2025)} bullets")
        company_total += len(hn_2025)
        
        # Blog RSS historical
        print(f"  📝 [Blog Historical] Fetching 2024-2025...")
        blog_bullets = blog_historical(company, vertical)
        company_total += len(blog_bullets)
        
        # Migration + complaints (vertical-aware)
        migration_bullets = migration_agent(company, vertical)
        company_total += len(migration_bullets)
        
        # Mark done for this vertical
        mark_historical_done(company, vertical)
        
        print(f"\n  📊 {company}: {company_total} historical bullets added")
        total_new += company_total
    
    print(f"""
╔══════════════════════════════════════════╗
║      HISTORICAL SCRAPE COMPLETE          ║
║      {total_new:>4} total bullets added             ║
║      Vertical: {config['display_name']:<24} ║
║      Run Mode 3 to evaluate quality      ║
╚══════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    run_historical_scrape()