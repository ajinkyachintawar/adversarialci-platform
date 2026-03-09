"""
Source Router v3
================
Routes to appropriate source agents based on vendor status.
- New vendors: Full scrape (present + historical)
- Stale vendors: Present scrape only (delta refresh)
- Fresh vendors: Skip

Fixed: migration_agent returns list, not dict
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from state import WarRoomState
from db.atlas import connect, get_collection, save_research, mark_scraped

# Source agents
from sources.tavily_agent import tavily_agent
from sources.hn_agent import hn_agent
from sources.pricing_agent import pricing_agent
from sources.github_agent import github_agent
from sources.blog_agent import blog_agent
from sources.migration_agent import migration_agent

# Vertical config
from verticals import get_hn_keywords


# ─── Historical Scrape Functions ────────────────────────────

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def hn_historical_year(company: str, year: int, vertical: str = "database") -> list:
    """Fetch HN posts for a company in a specific year."""
    import requests
    
    start = int(datetime(year, 1, 1).timestamp())
    end = int(datetime(year, 12, 31, 23, 59).timestamp())
    company_lower = company.lower()
    
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
            
            bullets.append(f"[HN {year} {points}pts {created}] {title} — {url}")
    
    except Exception as e:
        print(f"      ⚠️  HN {year} error: {e}")
    
    return bullets


def run_historical_scrape(company: str, vertical: str):
    """Run historical scrape for a new vendor."""
    print(f"  📜 Historical scrape for {company}...")
    
    total = 0
    current_year = datetime.now().year
    
    # HN for recent years (2024, 2025, 2026...)
    for year in [2024, 2025, current_year]:
        if year > current_year:
            continue
        print(f"    🟡 [HN {year}] Fetching...")
        hn_bullets = hn_historical_year(company, year, vertical)
        if hn_bullets:
            save_research(
                company=company,
                data_type="sentiment",
                source_type=f"hn_{year}",
                source_url=f"hn_algolia_{year}",
                bullets=hn_bullets
            )
        print(f"      ✅ HN {year}: {len(hn_bullets)} bullets")
        total += len(hn_bullets)
    
    # Blog historical
    print(f"    📝 [Blog Historical] Fetching 2024-present...")
    since = datetime(2024, 1, 1)
    blog_bullets = blog_agent(company, vertical, since=since)
    total += len(blog_bullets) if blog_bullets else 0
    
    print(f"    📊 Historical total: {total} bullets")
    
    # Mark historical done for this vertical
    col = get_collection("companies")
    col.update_one(
        {"name": company},
        {"$set": {
            f"historical_scraped_{vertical}": True,
            f"historical_scraped_{vertical}_at": datetime.utcnow()
        }}
    )


def run_present_scrape(company: str, vertical: str) -> int:
    """Run present scrape (all current sources)."""
    total = 0
    
    # Tavily
    tavily_bullets = tavily_agent(company, vertical)
    tavily_count = len(tavily_bullets) if tavily_bullets else 0
    total += tavily_count
    
    # HN Recent
    hn_bullets = hn_agent(company, vertical)
    hn_count = len(hn_bullets) if hn_bullets else 0
    total += hn_count
    
    # Pricing
    pricing_bullets = pricing_agent(company, vertical)
    pricing_count = len(pricing_bullets) if pricing_bullets else 0
    total += pricing_count
    
    # GitHub
    github_bullets = github_agent(company, vertical)
    github_count = len(github_bullets) if github_bullets else 0
    total += github_count
    
    # Blog
    blog_bullets = blog_agent(company, vertical)
    blog_count = len(blog_bullets) if blog_bullets else 0
    total += blog_count
    
    # Migration + Complaints
    # NOTE: migration_agent returns a list of bullets, not a dict
    migration_bullets = migration_agent(company, vertical)
    migration_count = len(migration_bullets) if migration_bullets else 0
    total += migration_count
    
    return total


# ─── Main Router ────────────────────────────────────────────

def source_router(state: WarRoomState) -> WarRoomState:
    """
    Route companies to appropriate scraping based on status.
    
    - new_companies: Full scrape (present + historical)
    - stale_companies: Refresh (present only)
    """
    vertical = state.get("vertical", "database")
    
    new_companies = state.get("new_companies", [])
    stale_companies = state.get("stale_companies", [])
    
    all_to_scrape = new_companies + stale_companies
    
    if not all_to_scrape:
        print("  ✅ All data fresh, skipping scrape")
        return {**state, "stage": "verifier"}
    
    print(f"\n🔀 SOURCE ROUTER — Starting research phase")
    print("=" * 40)
    print(f"  Vertical: {vertical}")
    
    connect()
    research = {}
    
    # Process NEW vendors (full scrape)
    for company in new_companies:
        print(f"\n📦 New Vendor: {company}")
        print("─" * 40)
        
        # Present scrape
        present_count = run_present_scrape(company, vertical)
        
        # Historical scrape (one-time)
        run_historical_scrape(company, vertical)
        
        # Mark as scraped
        mark_scraped(company)
        
        print(f"\n  📊 {company} total: Present + Historical complete")
        research[company] = {"status": "new", "present": present_count}
    
    # Process STALE vendors (refresh only)
    for company in stale_companies:
        print(f"\n📦 Refreshing: {company}")
        print("─" * 40)
        
        # Present scrape only
        present_count = run_present_scrape(company, vertical)
        
        # Mark as scraped
        mark_scraped(company)
        
        print(f"\n  📊 {company} total: {present_count} bullets (refresh)")
        research[company] = {"status": "refreshed", "present": present_count}
    
    return {
        **state,
        "research": research,
        "stage": "verifier"
    }


if __name__ == "__main__":
    # Test
    from state import create_initial_state
    
    state = create_initial_state("database", "buyer")
    state.update({
        "primary": "MongoDB",
        "competitors": ["Pinecone"],
        "new_companies": ["TestVendor"],
        "stale_companies": [],
    })
    
    result = source_router(state)
    print(f"\nResult: {result['research']}")