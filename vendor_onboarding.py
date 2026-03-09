"""
Vendor Onboarding - Inline sequential registration flow

Handles:
- Detect new vendors from user input
- Prompt for URLs interactively
- Validate inputs
- Trigger FULL scraping for new vendors (present + historical)
"""

from vendor_registry import (
    find_vendor,
    add_vendor,
    validate_url,
    validate_github_repo,
    normalize_name
)


def prompt_new_vendor(vendor_name: str, vertical: str = "database") -> bool:
    """
    Interactive prompt to register a new vendor.
    
    Args:
        vendor_name: Name of the vendor to register
        vertical: Which vertical this vendor belongs to
        
    Returns:
        True if vendor registered successfully, False if skipped
    """
    print(f"\n  ┌{'─' * 44}┐")
    print(f"  │ NEW VENDOR: {vendor_name:<31}│")
    print(f"  └{'─' * 44}┘")
    
    # Ask to register
    choice = input(f"  Register now? (y/n): ").strip().lower()
    if choice != 'y':
        print(f"  ⏭️  Skipping {vendor_name}")
        return False
    
    print()
    
    # ─── Pricing URL (required) ─────────────────────────
    while True:
        pricing_url = input("  Pricing page URL (required): ").strip()
        
        if not pricing_url:
            print("  ❌ Pricing URL is required.")
            retry = input("  Try again? (y/n): ").strip().lower()
            if retry != 'y':
                print(f"  ⏭️  Skipping {vendor_name}")
                return False
            continue
        
        valid, err = validate_url(pricing_url)
        if valid:
            break
        print(f"  ❌ {err}")
    
    # ─── Blog RSS (optional) ────────────────────────────
    blog_rss = input("  Blog RSS URL (optional, Enter to skip): ").strip()
    if blog_rss:
        valid, err = validate_url(blog_rss)
        if not valid:
            print(f"  ⚠️  {err} — skipping blog RSS")
            blog_rss = None
    else:
        blog_rss = None
    
    # ─── GitHub repo (optional) ─────────────────────────
    github_repo = input("  GitHub repo (optional, format owner/repo): ").strip()
    if github_repo:
        valid, err = validate_github_repo(github_repo)
        if not valid:
            print(f"  ⚠️  {err} — skipping GitHub")
            github_repo = None
    else:
        github_repo = None
    
    # ─── Save to registry ───────────────────────────────
    success = add_vendor(
        name=vendor_name,
        pricing_url=pricing_url,
        blog_rss=blog_rss,
        github_repo=github_repo,
        vertical=vertical
    )
    
    if success:
        print(f"\n  ✅ '{vendor_name}' registered!")
        return True
    else:
        print(f"\n  ❌ Failed to save '{vendor_name}'")
        return False


def scrape_new_vendor(vendor_name: str, vertical: str = "database") -> dict:
    """
    FULL scrape for a newly registered vendor (present + historical).
    
    This calls the same functions as source_router to ensure
    new vendors get complete data for fair verdicts.
    
    Args:
        vendor_name: Vendor to scrape
        vertical: Vertical category
        
    Returns:
        Dict with scrape results
    """
    from db.atlas import connect, mark_scraped, upsert_company
    from sources.router import run_present_scrape, run_historical_scrape
    
    print(f"\n  ⏳ Full scrape for {vendor_name} (present + historical)...")
    print("  " + "─" * 42)
    
    # Ensure company exists in Atlas
    connect()
    upsert_company(vendor_name)
    
    results = {
        "present": 0,
        "historical": False
    }
    
    # ─── Present scrape ─────────────────────────────────
    # (tavily, hn, pricing, github, blog, migration)
    try:
        present_count = run_present_scrape(vendor_name, vertical)
        results["present"] = present_count
    except Exception as e:
        print(f"    ⚠️  Present scrape error: {e}")
    
    # ─── Historical scrape ──────────────────────────────
    # (HN 2024, HN 2025, blog historical)
    try:
        run_historical_scrape(vendor_name, vertical)
        results["historical"] = True
    except Exception as e:
        print(f"    ⚠️  Historical scrape error: {e}")
    
    # ─── Mark as scraped ────────────────────────────────
    mark_scraped(vendor_name)
    
    print(f"\n  ✅ Full scrape complete for {vendor_name}")
    print(f"     Present: {results['present']} bullets")
    print(f"     Historical: {'Done' if results['historical'] else 'Failed'}")
    
    return results


def process_vendors(
    vendor_list: list[str], 
    vertical: str = "database",
    scrape_new: bool = True
) -> list[str]:
    """
    Process list of vendors - find existing, prompt for new ones.
    
    This is the main entry point for all modes.
    
    Args:
        vendor_list: List of vendor names from user input
        vertical: Which vertical to search/register in
        scrape_new: If True, scrape data for newly registered vendors
        
    Returns:
        List of valid vendor names ready for use
    """
    if not vendor_list:
        return []
    
    # Dedupe and clean
    vendors = list(dict.fromkeys([v.strip() for v in vendor_list if v.strip()]))
    
    existing = []
    new_vendors = []
    
    # ─── Categorize vendors ─────────────────────────────
    print("\n🔍 Checking vendor registry...")
    print("─" * 44)
    
    for vendor in vendors:
        found, canonical_name, data = find_vendor(vendor, vertical)
        
        if found:
            print(f"  ✅ {canonical_name}")
            existing.append(canonical_name)  # Use canonical name from config
        else:
            new_vendors.append(vendor)
    
    # ─── Handle new vendors ─────────────────────────────
    if new_vendors:
        print(f"\n⚠️  {len(new_vendors)} new vendor(s) detected: {', '.join(new_vendors)}")
        
        for i, vendor in enumerate(new_vendors, 1):
            print(f"\n  [{i}/{len(new_vendors)}]", end="")
            
            success = prompt_new_vendor(vendor, vertical)
            
            if success:
                existing.append(vendor)  # Use original input name
                
                # Full scrape if enabled
                if scrape_new:
                    try:
                        scrape_new_vendor(vendor, vertical)
                    except Exception as e:
                        print(f"  ⚠️  Scraping failed: {e}")
                        print("  (Vendor registered, scrape manually later)")
    
    # ─── Summary ────────────────────────────────────────
    print("\n" + "─" * 44)
    
    if not existing:
        print("❌ No valid vendors to process.")
        return []
    
    skipped = len(vendors) - len(existing)
    if skipped > 0:
        print(f"⏭️  Skipped: {skipped} vendor(s)")
    
    print(f"✅ Proceeding with: {', '.join(existing)}")
    
    return existing


# ─── CLI for testing ─────────────────────────────────────

if __name__ == "__main__":
    print("Test vendor onboarding")
    print("=" * 44)
    
    test_input = input("Enter vendors (comma-separated): ").strip()
    vendors = [v.strip() for v in test_input.split(",")]
    
    # Disable scraping for testing without network
    valid = process_vendors(vendors, vertical="database", scrape_new=False)
    
    print(f"\nResult: {valid}")