"""
Argument Builder
================
Builds argument banks per company from research data.
Now vertical-aware — loads dimensions and keywords from verticals config.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.atlas import connect, get_collection
from verticals import get_dimensions, get_dimension_keywords


# ─── Source priority for argument quality ───────────────────
# These are universal across verticals
SOURCE_PRIORITY = {
    "pricing_scrape":   1.0,
    "github":           0.9,
    "migration_tavily": 0.9,
    "complaint_tavily": 0.8,
    "hn_2024":          0.8,
    "hn_2025":          0.8,
    "hn":               0.7,
    "blog_rss":         0.7,
    "tavily":           0.6,
    "hn_delta":         0.7,
    "github_delta":     0.9,
    "tavily_delta":     0.6
}

# ─── Per-source minimum weight thresholds ───────────────────
SOURCE_MIN_WEIGHT = {
    "pricing_scrape":   0.35,
    "github":           0.35,
    "migration_tavily": 0.30,
    "complaint_tavily": 0.30,
    "hn_2024":          0.35,
    "hn_2025":          0.35,
    "hn":               0.35,
    "blog_rss":         0.28,
    "tavily":           0.35,
    "hn_delta":         0.35,
    "github_delta":     0.35,
    "tavily_delta":     0.35
}


def route_bullet_to_dimension(bullet: str, dimension_keywords: dict, default_dim: str) -> str:
    """
    Route a bullet to the best matching dimension.
    
    Args:
        bullet: The text to classify
        dimension_keywords: Dict of dimension -> keywords from vertical config
        default_dim: Fallback dimension if no match
        
    Returns:
        Best matching dimension name
    """
    bullet_lower = bullet.lower()
    scores = {}
    
    for dimension, keywords in dimension_keywords.items():
        score = sum(1 for k in keywords if k in bullet_lower)
        if score > 0:
            scores[dimension] = score
    
    if not scores:
        return default_dim
    
    return max(scores, key=scores.get)


def build_arguments(company: str, vertical: str = "database") -> dict:
    """
    Build argument bank for a company.
    
    Args:
        company: Company name
        vertical: Industry vertical for dimension config
        
    Returns:
        Dict of dimension -> list of arguments
    """
    # Get dimensions and keywords from vertical config
    dimensions = get_dimensions(vertical)
    dimension_keywords = get_dimension_keywords(vertical)
    
    # Default dimension is last one (usually ecosystem/integrations)
    default_dim = dimensions[-1] if dimensions else "ecosystem"
    
    connect()
    col = get_collection("research_data")
    docs = list(col.find({
        "company":  company,
        "verified": True
    }, {"_id": 0}))
    
    if not docs:
        print(f"  ⚠️  No verified data found for {company}")
        return {}
    
    # Build argument bank per dimension
    argument_bank = {dim: [] for dim in dimensions}
    
    for doc in docs:
        source_type = doc.get("source_type", "tavily")
        confidence  = doc.get("confidence_score", 0.5)
        priority    = SOURCE_PRIORITY.get(source_type, 0.5)
        weight      = round(confidence * priority, 3)
        min_w       = SOURCE_MIN_WEIGHT.get(source_type, 0.35)
        bullets     = doc.get("content_bullets", [])
        
        # Skip entire doc if weight below source-specific threshold
        if weight < min_w:
            continue
        
        for bullet in bullets:
            dimension = route_bullet_to_dimension(
                bullet, dimension_keywords, default_dim
            )
            
            # Safety check - dimension must be in our list
            if dimension not in argument_bank:
                dimension = default_dim
            
            argument_bank[dimension].append({
                "claim":       bullet[:500],
                "source_type": source_type,
                "confidence":  confidence,
                "priority":    priority,
                "weight":      weight
            })
    
    # Sort by weight and apply per-source filter
    for dim in dimensions:
        argument_bank[dim] = sorted(
            [a for a in argument_bank[dim]
             if a["weight"] >= SOURCE_MIN_WEIGHT.get(
                 a["source_type"], 0.35
             )],
            key=lambda x: x["weight"],
            reverse=True
        )
    
    # Summary stats
    total = sum(len(v) for v in argument_bank.values())
    active_dims = len([d for d in dimensions if argument_bank[d]])
    
    print(f"  📋 {company}: {total} arguments built across "
          f"{active_dims} dimensions (per-source weight filter)")
    
    for dim in dimensions:
        count = len(argument_bank[dim])
        if count > 0:
            top = argument_bank[dim][0]
            print(f"     {dim:<20} {count:>3} args | "
                  f"top weight: {top['weight']}")
    
    return argument_bank


def build_all_arguments(companies: list, vertical: str = "database") -> dict:
    """
    Build argument banks for all companies.
    
    Args:
        companies: List of company names
        vertical: Industry vertical
        
    Returns:
        Dict of company -> argument bank
    """
    print("\n⚖️  ARGUMENT BUILDER")
    print("=" * 40)
    print(f"  Vertical: {vertical}")
    
    all_arguments = {}
    for company in companies:
        print(f"\n  Building arguments: {company}")
        all_arguments[company] = build_arguments(company, vertical)
    
    return all_arguments


# ─── Helper for advocates ────────────────────────────────────

def get_dimensions_for_vertical(vertical: str) -> list:
    """Get dimensions list for a vertical (for use by advocates)."""
    return get_dimensions(vertical)


if __name__ == "__main__":
    # Test with database vertical
    print("\n=== Testing Database Vertical ===")
    companies = ["MongoDB", "Pinecone", "Weaviate"]
    args = build_all_arguments(companies, vertical="database")
    
    print("\n\n📊 ARGUMENT BANK SUMMARY")
    print("=" * 40)
    for company, bank in args.items():
        total = sum(len(v) for v in bank.values())
        print(f"\n  {company}: {total} total arguments")
        for dim, arguments in bank.items():
            if arguments:
                print(f"    {dim:<20} {len(arguments)} args")
    
    # Show dimensions for each vertical
    print("\n\n📂 DIMENSIONS BY VERTICAL")
    print("=" * 40)
    for v in ["database", "cloud", "crm"]:
        dims = get_dimensions(v)
        print(f"\n  {v}: {dims}")