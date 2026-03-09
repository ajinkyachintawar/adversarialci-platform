"""
DB Check v3
===========
Checks Atlas for vendor data and categorizes by freshness.
Routing decisions are made by the graph, not this node.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from state import WarRoomState
from db.atlas import connect, get_collection
from config import FRESHNESS_DAYS


def get_vendor_status(company: str) -> str:
    col = get_collection("companies")
    doc = col.find_one({"name": company})
    
    if not doc or not doc.get("last_scraped"):
        return "new"
    
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    return "stale" if doc["last_scraped"] < cutoff else "fresh"


def check_historical_done(company: str, vertical: str) -> bool:
    col = get_collection("companies")
    doc = col.find_one({"name": company})
    if not doc:
        return False
    return doc.get(f"historical_scraped_{vertical}", False)


def get_days_since_scrape(company: str) -> str:
    col = get_collection("companies")
    doc = col.find_one({"name": company})
    
    if not doc or not doc.get("last_scraped"):
        return "never"
    
    delta = datetime.utcnow() - doc["last_scraped"]
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    return f"{hours}h ago" if hours > 0 else "just now"


def db_check(state: WarRoomState) -> WarRoomState:
    """Categorize companies by freshness. Routing handled by graph."""
    
    print("\n" + "=" * 50)
    print("  DB CHECK - Analyzing data freshness")
    print("=" * 50)
    
    connect()
    
    vertical = state.get("vertical", "database")
    mode = state.get("mode", "buyer")
    
    # Get unique companies
    all_companies = [state["primary"]] if state.get("primary") else []
    all_companies.extend(state.get("competitors", []))
    unique_companies = list(dict.fromkeys(c for c in all_companies if c))
    
    if not unique_companies:
        print("  [!] No companies to check")
        return {**state, "new_companies": [], "stale_companies": [], "fresh_companies": []}
    
    print(f"  Vertical: {vertical}")
    print(f"  Mode: {mode}")
    print(f"  Companies: {', '.join(unique_companies)}")
    print("-" * 50)
    
    new_companies, stale_companies, fresh_companies = [], [], []
    
    for company in unique_companies:
        status = get_vendor_status(company)
        
        if status == "new":
            new_companies.append(company)
            print(f"  [NEW]   {company} (never scraped)")
            if not check_historical_done(company, vertical):
                print(f"          -> Will run historical scrape")
        elif status == "stale":
            stale_companies.append(company)
            print(f"  [STALE] {company} ({get_days_since_scrape(company)})")
        else:
            fresh_companies.append(company)
            print(f"  [FRESH] {company} ({get_days_since_scrape(company)})")
    
    print("-" * 50)
    total = len(unique_companies)
    print(f"  Summary: {len(fresh_companies)}/{total} fresh, "
          f"{len(stale_companies)}/{total} stale, {len(new_companies)}/{total} new")
    
    if new_companies or stale_companies:
        print(f"  -> Scraping: {', '.join(new_companies + stale_companies)}")
    else:
        print(f"  -> All fresh, proceeding to analysis")
    
    print("=" * 50 + "\n")
    
    return {
        **state,
        "new_companies": new_companies,
        "stale_companies": stale_companies,
        "fresh_companies": fresh_companies
    }