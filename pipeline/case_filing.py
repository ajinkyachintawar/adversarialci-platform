"""
Case Filing - Entry point for Mode 1 (Sourcing) and Mode 2 (Courtroom)

Modified to use vendor_onboarding for inline new vendor registration.
"""

from state import WarRoomState
from db.atlas import connect, upsert_company, is_stale
from vendor_onboarding import process_vendors


def get_vendor_input() -> tuple[str, list[str]]:
    """
    Common vendor input for all modes.
    
    Returns:
        (primary, competitors)
    """
    primary = input(
        "Enter PRIMARY company (e.g. MongoDB): "
    ).strip()
    
    competitors_input = input(
        "Enter COMPETITORS separated by comma "
        "(e.g. Pinecone, Weaviate): "
    ).strip()
    
    competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
    
    return primary, competitors


# ─── MODE 1 — Sourcing only, no plaintiff ──────────────────

def sourcing_filing(state: WarRoomState) -> WarRoomState:
    """
    Mode 1: Sourcing Agent entry point.
    
    Collects vendor names, registers new vendors inline,
    then proceeds to scraping.
    """
    print("\n🔍 SOURCING AGENT — Company Setup")
    print("=" * 44)
    
    primary, competitors = get_vendor_input()
    all_companies = [primary] + competitors
    
    # ─── Process vendors (inline registration for new ones) ───
    valid_vendors = process_vendors(all_companies, scrape_new=True)
    
    if not valid_vendors:
        print("\n❌ No valid vendors. Exiting.")
        raise SystemExit(0)
    
    # First vendor is primary, rest are competitors
    primary = valid_vendors[0]
    competitors = valid_vendors[1:] if len(valid_vendors) > 1 else []
    
    # ─── Register in Atlas ──────────────────────────────────
    connect()
    for company in valid_vendors:
        upsert_company(company)
    
    print(f"\n✅ Companies registered:")
    print(f"   Primary     : {primary}")
    print(f"   Competitors : {', '.join(competitors) if competitors else 'None'}")
    print(f"   Proceeding to scrape...\n")
    
    return {
        **state,
        "primary": primary,
        "competitors": competitors,
        "plaintiff": {},
        "stage": "db_check"
    }


# ─── MODE 2 — Courtroom with full plaintiff profile ────────

def case_filing(state: WarRoomState) -> WarRoomState:
    """
    Mode 2: Courtroom entry point.
    
    Collects vendor names + plaintiff profile,
    registers new vendors inline if needed.
    """
    print("\n⚖️  WAR ROOM — CASE FILING")
    print("=" * 44)
    
    primary, competitors = get_vendor_input()
    all_companies = [primary] + competitors
    
    # ─── Process vendors (inline registration for new ones) ───
    # Don't scrape here - we'll check freshness below
    valid_vendors = process_vendors(all_companies, scrape_new=False)
    
    if not valid_vendors:
        print("\n❌ No valid vendors. Exiting.")
        raise SystemExit(0)
    
    primary = valid_vendors[0]
    competitors = valid_vendors[1:] if len(valid_vendors) > 1 else []
    
    # ─── Plaintiff profile ──────────────────────────────────
    print("\n📋 PLAINTIFF PROFILE")
    print("─" * 44)
    company_name = input("Company name: ").strip()
    team_size = input("Team size (e.g. 3 engineers): ").strip()
    budget = input("Monthly budget (e.g. $2000): ").strip()
    use_case = input(
        "Primary use case (e.g. RAG pipeline, semantic search): "
    ).strip()
    scale = input(
        "Current vector count + 18mo projection "
        "(e.g. 10M → 500M): "
    ).strip()
    cloud = input(
        "Cloud provider (e.g. AWS, GCP, Azure): "
    ).strip()
    priority = input(
        "Top priority "
        "(cost / performance / simplicity / no-lock-in): "
    ).strip()
    
    plaintiff = {
        "company_name": company_name,
        "team_size": team_size,
        "budget": budget,
        "use_case": use_case,
        "scale": scale,
        "cloud": cloud,
        "priority": priority
    }
    
    # ─── Register in Atlas ──────────────────────────────────
    connect()
    for company in valid_vendors:
        upsert_company(company)
    
    # ─── Check freshness ────────────────────────────────────
    missing = [c for c in valid_vendors if is_stale(c)]
    
    if missing:
        print(f"\n⚠️  No fresh data found for: {', '.join(missing)}")
        print(f"   Run Mode 1 first to scrape research data.")
        choice = input("\n   Scrape now before proceeding? (y/n): ").strip().lower()
        
        if choice == "y":
            from sources.router import source_router
            temp_state = {
                **state,
                "primary": primary,
                "competitors": competitors,
                "stale_companies": missing
            }
            source_router(temp_state)
            print("\n✅ Scraping complete. Proceeding to court...\n")
        else:
            print("\n❌ Exiting. Run Mode 1 first.\n")
            raise SystemExit(0)
    
    print(f"\n🔨 JUDGE: Case accepted.")
    print(f"   Primary    : {primary}")
    print(f"   Competitors: {', '.join(competitors) if competitors else 'None'}")
    print(f"   Plaintiff  : {company_name} | {budget}/mo | {use_case}")
    print(f"   Proceeding to court...\n")
    
    return {
        **state,
        "primary": primary,
        "competitors": competitors,
        "plaintiff": plaintiff,
        "stage": "court_opens"
    }