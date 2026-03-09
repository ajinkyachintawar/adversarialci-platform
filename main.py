"""
AdversarialCI - Main Entry Point (v5)
=====================================
Clean CLI with single vendor registry.

Menu:
[1] Buyer      - Get vendor recommendation
[2] Seller     - Get competitive battlecard
[3] Analyst    - Get objective comparison
[4] Pre-fetch  - Scrape data only
[5] Eval       - Check data quality
[6] Sales Copilot - Chat prep
[7] Manage Vendors - Add/Edit/Delete vendors
[8] List Vendors - Show all registered vendors

Key Design:
- Single vendors.json for all vendors
- Block if vendor not in registry
- Scrape only happens in pipeline (not during add)
"""

from langgraph.graph import StateGraph, END
from state import WarRoomState, create_initial_state
from pipeline.db_check import db_check
from pipeline.aggregator import aggregator
from pipeline.verifier import verifier
from sources.router import source_router
from pipeline.court_session import court_session
from eval.source_quality import run_eval
from verticals import list_verticals, get_vertical
from vendor_registry import (
    list_vendors, get_vendor, add_vendor, update_vendor, delete_vendor,
    vendor_exists, validate_vendors_exist, get_vendor_status,
    validate_url, validate_github_repo
)


# ─── Routing Logic ──────────────────────────────────────────

def needs_scraping(state: WarRoomState) -> str:
    new = state.get("new_companies", [])
    stale = state.get("stale_companies", [])
    if new or stale:
        return "scrape"
    return "verify"


def should_run_court(state: WarRoomState) -> str:
    mode = state.get("mode", "buyer")
    if mode == "sourcing":
        return "end"
    return "court"


# ─── Graph Builders ─────────────────────────────────────────

def build_main_graph():
    graph = StateGraph(WarRoomState)
    graph.add_node("db_check", db_check)
    graph.add_node("source_router", source_router)
    graph.add_node("verifier", verifier)
    graph.add_node("court_session", court_session)
    graph.set_entry_point("db_check")
    graph.add_conditional_edges("db_check", needs_scraping,
                                {"scrape": "source_router", "verify": "verifier"})
    graph.add_edge("source_router", "verifier")
    graph.add_conditional_edges("verifier", should_run_court,
                                {"court": "court_session", "end": END})
    graph.add_edge("court_session", END)
    return graph.compile()


def build_sourcing_graph():
    graph = StateGraph(WarRoomState)
    graph.add_node("source_router", source_router)
    graph.add_node("verifier", verifier)
    graph.add_node("aggregator", aggregator)
    graph.set_entry_point("source_router")
    graph.add_edge("source_router", "verifier")
    graph.add_edge("verifier", "aggregator")
    graph.add_edge("aggregator", END)
    return graph.compile()


# ─── UI Components ──────────────────────────────────────────

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║                   ADVERSARIAL CI                         ║
║            Competitive Intelligence System               ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║   [1] 🛒 Buyer        - Get vendor recommendation        ║
║   [2] 🎯 Seller       - Get competitive battlecard       ║
║   [3] 📊 Analyst      - Get objective comparison         ║
║                                                          ║
║   ─────────────────────────────────────────────────────  ║
║                                                          ║
║   [4] 🔍 Pre-fetch    - Scrape data (no analysis)        ║
║   [5] 📈 Eval         - Check data quality               ║
║   [6] 💬 Sales Copilot- Chat-based prep                  ║
║                                                          ║
║   ─────────────────────────────────────────────────────  ║
║                                                          ║
║   [7] ➕ Manage Vendors - Add/Edit/Delete                ║
║   [8] 📋 List Vendors  - Show registered vendors         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


def select_vertical() -> str:
    available = list_verticals()
    print("\n📂 SELECT VERTICAL")
    print("─" * 40)
    for i, v in enumerate(available, 1):
        config = get_vertical(v)
        vendor_names = list_vendors(v)[:3]
        print(f"  [{i}] {config['display_name']}")
        if vendor_names:
            print(f"      e.g. {', '.join(vendor_names)}")
    
    while True:
        choice = input(f"\nEnter choice (1-{len(available)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                selected = available[idx]
                config = get_vertical(selected)
                print(f"  ✅ Selected: {config['display_name']}")
                return selected
        except ValueError:
            pass
        print("  ⚠️  Invalid choice")


def get_companies_input(vertical: str, mode: str) -> tuple:
    """
    Get and validate vendor input.
    BLOCKS if any vendor is missing from registry.
    
    Returns: (companies: list, my_company: str or None)
    """
    vendor_names = list_vendors(vertical)[:3]
    example = ", ".join(vendor_names) if vendor_names else "Vendor1, Vendor2"
    
    mode_labels = {
        "buyer": "🛒 BUYER MODE",
        "seller": "🎯 SELLER MODE", 
        "analyst": "📊 ANALYST MODE",
        "sourcing": "🔍 PRE-FETCH MODE"
    }
    
    print(f"\n{mode_labels.get(mode, mode.upper())}")
    print("─" * 40)
    
    # Get input based on mode
    if mode == "seller":
        my_company = input(f"  Who do you sell for? (e.g. {vendor_names[0] if vendor_names else 'YourCompany'}): ").strip()
        competitors_input = input(f"  Competitors? (e.g. {', '.join(vendor_names[1:3]) if len(vendor_names) > 1 else 'Comp1, Comp2'}): ").strip()
        raw_companies = [my_company] + [c.strip() for c in competitors_input.split(",") if c.strip()]
    else:
        companies_input = input(f"  Enter vendors (e.g. {example}): ").strip()
        raw_companies = [c.strip() for c in companies_input.split(",") if c.strip()]
        my_company = None
    
    if not raw_companies:
        print("  ❌ No vendors entered")
        return [], None
    
    # Validate all vendors exist
    existing, missing = validate_vendors_exist(raw_companies, vertical)
    
    if missing:
        print(f"\n  ❌ BLOCKED: These vendors are not in registry:")
        for m in missing:
            print(f"     • {m}")
        print(f"\n  Add them first using option [7] Manage Vendors")
        print(f"  Then retry.\n")
        return [], None
    
    print(f"  ✅ All {len(existing)} vendors validated")
    
    # For seller mode, find canonical my_company
    if mode == "seller":
        for e in existing:
            if e.lower() == my_company.lower():
                my_company = e
                break
    
    return existing, my_company


def collect_profile(vertical: str, mode: str) -> dict:
    config = get_vertical(vertical)
    questions = config.get("plaintiff_questions", [])
    
    if mode == "analyst":
        print(f"\n📊 EVALUATION CRITERIA")
        print("─" * 40)
        priority = input("  Top priority (cost / performance / simplicity / enterprise): ").strip()
        return {"priority": priority, "mode": "analyst"}
    
    if mode == "buyer":
        print(f"\n📋 YOUR PROFILE (as the buyer)")
    else:
        print(f"\n📋 TARGET PROSPECT PROFILE")
    print("─" * 40)
    
    profile = {"mode": mode}
    for q in questions:
        key = q["key"]
        prompt = q["prompt"]
        example = q.get("example", "")
        if example:
            value = input(f"  {prompt} (e.g. {example}): ").strip()
        else:
            value = input(f"  {prompt}: ").strip()
        profile[key] = value
    
    return profile


# ─── Mode Runners ───────────────────────────────────────────

def run_court_mode(mode: str):
    vertical = select_vertical()
    companies, my_company = get_companies_input(vertical, mode)
    
    if not companies:
        return  # Blocked or no input
    
    profile = collect_profile(vertical, mode)
    
    if mode == "seller":
        primary = my_company
        competitors = [c for c in companies if c != my_company]
    else:
        primary = companies[0]
        competitors = companies[1:]
    
    state = create_initial_state(vertical, mode)
    state.update({
        "primary": primary,
        "competitors": competitors,
        "my_company": my_company,
        "plaintiff": profile,
        "stage": "db_check"
    })
    
    from db.atlas import connect, upsert_company
    connect()
    for company in companies:
        upsert_company(company)
    
    mode_labels = {"buyer": "🛒 BUYER EVALUATION", "seller": "🎯 SELLER BATTLECARD", "analyst": "📊 ANALYST COMPARISON"}
    print(f"\n{mode_labels[mode]}")
    print(f"   Vertical : {get_vertical(vertical)['display_name']}")
    if mode == "seller":
        print(f"   You sell : {my_company}")
        print(f"   Competing: {', '.join(competitors)}")
    else:
        print(f"   Comparing: {', '.join(companies)}")
    print(f"   Priority : {profile.get('priority', 'balanced')}")
    print(f"\n   Auto-scraping if data is stale...\n")
    
    app = build_main_graph()
    app.invoke(state)


def run_sourcing():
    vertical = select_vertical()
    companies, _ = get_companies_input(vertical, "sourcing")
    
    if not companies:
        return
    
    state = create_initial_state(vertical, "sourcing")
    state.update({
        "primary": companies[0],
        "competitors": companies[1:],
        "stale_companies": companies,
        "stage": "source_router"
    })
    
    from db.atlas import connect, upsert_company
    connect()
    for company in companies:
        upsert_company(company)
    
    print(f"\n🔍 PRE-FETCH DATA")
    print(f"   Vertical : {get_vertical(vertical)['display_name']}")
    print(f"   Companies: {', '.join(companies)}")
    print(f"   Scraping all sources...\n")
    
    app = build_sourcing_graph()
    app.invoke(state)
    
    print("\n✅ Pre-fetch complete. Data stored in Atlas.\n")


def run_sales_copilot():
    try:
        from pipeline.sales_copilot import run_sales_copilot as copilot
        copilot()
    except ImportError as e:
        print(f"❌ Sales Copilot not available: {e}")


# ─── [7] Manage Vendors ─────────────────────────────────────

def manage_vendors():
    vertical = select_vertical()
    
    print(f"\n➕ MANAGE VENDORS — {get_vertical(vertical)['display_name']}")
    print("─" * 40)
    print("  [1] Add new vendor")
    print("  [2] Edit existing vendor")
    print("  [3] Delete vendor")
    print("  [4] Back to main menu")
    
    choice = input("\nChoice: ").strip()
    
    if choice == "1":
        add_vendor_flow(vertical)
    elif choice == "2":
        edit_vendor_flow(vertical)
    elif choice == "3":
        delete_vendor_flow(vertical)
    elif choice == "4":
        return
    else:
        print("  ⚠️  Invalid choice")


def add_vendor_flow(vertical: str):
    print(f"\n➕ ADD NEW VENDOR")
    print("─" * 40)
    
    name = input("  Vendor name: ").strip()
    if not name:
        print("  ❌ Name required")
        return
    
    if vendor_exists(name, vertical):
        print(f"  ⚠️  '{name}' already exists. Use Edit instead.")
        return
    
    # Pricing URL (required)
    while True:
        pricing_url = input("  Pricing page URL (required): ").strip()
        if not pricing_url:
            print("  ❌ Pricing URL is required")
            continue
        valid, err = validate_url(pricing_url)
        if valid:
            break
        print(f"  ❌ {err}")
    
    # GitHub repo (optional)
    github_repo = input("  GitHub repo (optional, owner/repo): ").strip() or None
    if github_repo:
        valid, err = validate_github_repo(github_repo)
        if not valid:
            print(f"  ⚠️  {err} — skipping GitHub")
            github_repo = None
    
    # Blog RSS (optional)
    blog_rss = input("  Blog RSS URL (optional): ").strip() or None
    if blog_rss:
        valid, err = validate_url(blog_rss)
        if not valid:
            print(f"  ⚠️  {err} — skipping Blog")
            blog_rss = None
    
    # Save
    success = add_vendor(name, vertical, pricing_url, github_repo, blog_rss)
    
    if success:
        print(f"\n  ✅ '{name}' added to {vertical} registry!")
        print(f"  Run Pre-fetch [4] to scrape data for this vendor.")
    else:
        print(f"\n  ❌ Failed to add vendor")


def edit_vendor_flow(vertical: str):
    vendors = list_vendors(vertical)
    
    if not vendors:
        print(f"  No vendors in {vertical}")
        return
    
    print(f"\n✏️  EDIT VENDOR")
    print("─" * 40)
    for i, v in enumerate(vendors, 1):
        print(f"  [{i}] {v}")
    
    choice = input(f"\nSelect vendor (1-{len(vendors)}): ").strip()
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(vendors)):
            print("  ⚠️  Invalid choice")
            return
    except ValueError:
        print("  ⚠️  Invalid choice")
        return
    
    name = vendors[idx]
    config = get_vendor(name, vertical)
    
    print(f"\n  Current config for {name}:")
    print(f"    Pricing: {config.get('pricing_url') or '[not set]'}")
    print(f"    GitHub:  {config.get('github_repo') or '[not set]'}")
    print(f"    Blog:    {config.get('blog_rss') or '[not set]'}")
    
    print(f"\n  Enter new values (press Enter to keep current):")
    
    new_pricing = input(f"  Pricing URL [{config.get('pricing_url', '')}]: ").strip()
    new_github = input(f"  GitHub repo [{config.get('github_repo', '')}]: ").strip()
    new_blog = input(f"  Blog RSS [{config.get('blog_rss', [''])[0] if config.get('blog_rss') else ''}]: ").strip()
    
    # Only update if provided
    update_vendor(
        name, vertical,
        pricing_url=new_pricing if new_pricing else None,
        github_repo=new_github if new_github else None,
        blog_rss=new_blog if new_blog else None
    )
    
    print(f"\n  ✅ '{name}' updated!")


def delete_vendor_flow(vertical: str):
    vendors = list_vendors(vertical)
    
    if not vendors:
        print(f"  No vendors in {vertical}")
        return
    
    print(f"\n🗑️  DELETE VENDOR")
    print("─" * 40)
    for i, v in enumerate(vendors, 1):
        print(f"  [{i}] {v}")
    
    choice = input(f"\nSelect vendor (1-{len(vendors)}): ").strip()
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(vendors)):
            print("  ⚠️  Invalid choice")
            return
    except ValueError:
        print("  ⚠️  Invalid choice")
        return
    
    name = vendors[idx]
    
    confirm = input(f"  Delete '{name}'? This cannot be undone. (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled")
        return
    
    success = delete_vendor(name, vertical)
    if success:
        print(f"\n  ✅ '{name}' deleted from registry")
    else:
        print(f"\n  ❌ Failed to delete")


# ─── [8] List Vendors ───────────────────────────────────────

def show_vendors():
    vertical = select_vertical()
    vendors = list_vendors(vertical)
    
    if not vendors:
        print(f"\n  No vendors registered in {vertical}")
        print(f"  Use [7] Manage Vendors to add some.\n")
        return
    
    print(f"\n📋 REGISTERED VENDORS — {get_vertical(vertical)['display_name']}")
    print("─" * 65)
    print(f"  {'Vendor':<25} {'Pricing':<10} {'GitHub':<10} {'Blog':<10}")
    print("─" * 65)
    
    for v in vendors:
        status = get_vendor_status(v, vertical)
        pricing = "✅" if status.get("has_pricing") else "❌"
        github = "✅" if status.get("has_github") else "❌"
        blog = "✅" if status.get("has_blog") else "❌"
        print(f"  {v:<25} {pricing:<10} {github:<10} {blog:<10}")
    
    print("─" * 65)
    print(f"  {len(vendors)} vendors registered\n")


# ─── Main ───────────────────────────────────────────────────

def main():
    print_banner()
    
    while True:
        choice = input("Enter choice (1-8): ").strip()
        
        if choice == "1":
            run_court_mode("buyer")
        elif choice == "2":
            run_court_mode("seller")
        elif choice == "3":
            run_court_mode("analyst")
        elif choice == "4":
            run_sourcing()
        elif choice == "5":
            run_eval()
        elif choice == "6":
            run_sales_copilot()
        elif choice == "7":
            manage_vendors()
        elif choice == "8":
            show_vendors()
        elif choice.lower() in ["q", "quit", "exit"]:
            print("Goodbye!")
            break
        else:
            print("  ⚠️  Please enter 1-8")
        
        # Show menu again after action
        print_banner()


if __name__ == "__main__":
    main()