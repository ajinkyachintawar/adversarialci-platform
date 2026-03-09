#!/usr/bin/env python3
"""
Check freshness of all data in Atlas.
Run: python3 scripts/check_freshness.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from db.atlas import connect, get_collection


def format_age(last_scraped) -> str:
    if not last_scraped:
        return "never scraped"
    now           = datetime.now(timezone.utc)
    delta         = now - last_scraped.replace(tzinfo=timezone.utc)
    total_seconds = int(delta.total_seconds())
    days          = delta.days
    hours         = (total_seconds % 86400) // 3600
    minutes       = (total_seconds % 3600) // 60
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


def run_freshness_check():
    print("""
╔══════════════════════════════════════════╗
║      DB WAR ROOM — FRESHNESS CHECK       ║
╚══════════════════════════════════════════╝
    """)

    connect()
    companies_col = get_collection("companies")
    research_col  = get_collection("research_data")
    companies     = list(companies_col.find({}, {"_id": 0}))

    if not companies:
        print("❌ No companies in Atlas. Run Mode 1 first.\n")
        return

    print(f"  {'Company':<25} {'Status':<12} {'Last Scraped':<22} {'Bullets':<10} {'Historical'}")
    print(f"  {'─'*25} {'─'*12} {'─'*22} {'─'*10} {'─'*10}")

    needs_refresh = []

    for company in sorted(companies, key=lambda x: x["name"]):
        name         = company["name"]
        last_scraped = company.get("last_scraped")
        historical   = company.get("historical_scraped", False)
        status_label, status_key = freshness_status(last_scraped)
        age          = format_age(last_scraped)

        docs          = list(research_col.find({"company": name}))
        total_bullets = sum(
            len(d.get("content_bullets", [])) for d in docs
        )

        hist_label = "✅ done" if historical else "❌ pending"

        print(f"  {name:<25} {status_label:<12} {age:<22} {total_bullets:<10} {hist_label}")

        if status_key in ["aging", "stale", "expired", "never"]:
            needs_refresh.append((name, status_key, age))

    print()

    if needs_refresh:
        print(f"  ⚠️  Companies needing refresh:")
        for name, status, age in needs_refresh:
            print(f"     • {name} — {status} ({age})")
        print(f"\n  Run: python3 scripts/refresh.py")
    else:
        print(f"  ✅ All companies are fresh.")

    print()


if __name__ == "__main__":
    run_freshness_check()