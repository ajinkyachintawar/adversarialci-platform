#!/usr/bin/env python3
"""
Refresh stale current data.
Deletes and re-scrapes current data only.
Historical data is never touched.
Run: python3 scripts/refresh.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from db.atlas import connect, get_collection, mark_scraped
from sources.tavily_agent  import tavily_agent
from sources.hn_agent      import hn_agent
from sources.pricing_agent import pricing_agent
from sources.github_agent  import github_agent


CURRENT_SOURCES = [
    "tavily", "hn", "pricing_scrape", "github", "blog_rss"
]

REFRESH_THRESHOLD_HOURS = 24


from datetime import datetime, timezone


def format_age(last_scraped) -> str:
    if not last_scraped:
        return "never scraped"
    now          = datetime.now(timezone.utc)
    delta        = now - last_scraped.replace(tzinfo=timezone.utc)
    total_seconds = int(delta.total_seconds())
    days         = delta.days
    hours        = (total_seconds % 86400) // 3600
    minutes      = (total_seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h ago"
    elif hours > 0:
        return f"{hours}h {minutes}m ago"
    else:
        return f"{minutes}m ago"


def freshness_status(last_scraped) -> tuple:
    if not last_scraped:
        return "❌ NEVER", "never"
    now         = datetime.now(timezone.utc)
    delta       = now - last_scraped.replace(tzinfo=timezone.utc)
    total_hours = delta.total_seconds() / 3600
    if total_hours < 24:
        return "✅ FRESH", "fresh"
    elif total_hours < 72:
        return "🟡 AGING", "aging"
    elif total_hours < 168:
        return "🟠 STALE", "stale"
    else:
        return "❌ EXPIRED", "expired"

def delete_current_data(company: str):
    col = get_collection("research_data")
    result = col.delete_many({
        "company":     company,
        "source_type": {"$in": CURRENT_SOURCES}
    })
    return result.deleted_count


def run_refresh():
    print("""
╔══════════════════════════════════════════╗
║         DB WAR ROOM — REFRESH            ║
║         Replaces stale current data      ║
║         Historical data untouched        ║
╚══════════════════════════════════════════╝
    """)

    connect()
    companies_col = get_collection("companies")
    companies     = list(companies_col.find({}, {"_id": 0}))

    if not companies:
        print("❌ No companies in Atlas. Run Mode 1 first.\n")
        return

    now       = datetime.utcnow()
    threshold = now - timedelta(hours=REFRESH_THRESHOLD_HOURS)

    print("  Checking freshness...\n")
    print(f"  {'Company':<25} {'Status':<12} {'Age'}")
    print(f"  {'─'*25} {'─'*12} {'─'*20}")

    to_refresh = []

    for company in sorted(companies, key=lambda x: x["name"]):
        name         = company["name"]
        last_scraped = company.get("last_scraped")
        status_label, status_key = freshness_status(last_scraped)
        age          = format_age(last_scraped)

        print(f"  {name:<25} {status_label:<12} {age}")

        if last_scraped:
            if last_scraped.tzinfo:
                last_scraped = last_scraped.replace(tzinfo=None)
            if last_scraped < threshold:
                to_refresh.append(name)
        else:
            print(f"    ⚠️  Never scraped — run Mode 1 first")

    if not to_refresh:
        print("\n  ✅ All companies are fresh. No refresh needed.\n")
        return

    print(f"\n  🔄 Refreshing: {', '.join(to_refresh)}\n")
    print("=" * 40)

    for company in to_refresh:
        print(f"\n📦 Refreshing: {company}")
        print("─" * 40)

        # Delete current data only
        deleted = delete_current_data(company)
        print(f"  🗑️  Deleted {deleted} current docs")

        # Re-scrape current sources
        print(f"  Scraping fresh data...")
        tavily_agent(company)
        hn_agent(company)
        pricing_agent(company)
        github_agent(company)

        # Update timestamp
        mark_scraped(company)
        print(f"  ✅ {company} refreshed")

    print(f"""
╔══════════════════════════════════════════╗
║      REFRESH COMPLETE                    ║
║      {len(to_refresh)} companies refreshed
║      Historical data preserved           ║
║      Run Mode 3 to evaluate quality      ║
╚══════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    run_refresh()