"""
Migration Agent
===============
Scrapes migration stories and complaints via Tavily.
Now vertical-aware — loads queries from verticals config.
"""

from tavily import TavilyClient
from config import TAVILY_API_KEY
from db.atlas import save_research
from verticals import get_vendor_config, get_vertical
from datetime import datetime


client = TavilyClient(api_key=TAVILY_API_KEY)


def migration_agent(company: str, vertical: str = "database") -> list:
    """
    Search for migration stories and complaints about a company.
    
    Args:
        company: Company name to research
        vertical: Industry vertical for query lookup
        
    Returns:
        List of bullet points with migrations and complaints
    """
    print(f"  🚀 [Migration] Scraping migrations + complaints "
          f"for {company}...")
    
    # Get vendor-specific queries from config
    vendor_config = get_vendor_config(vertical, company)
    migration_queries = vendor_config.get("migration_queries", [])
    complaint_queries = vendor_config.get("complaint_queries", [])
    
    # If no vendor-specific queries, use templates from vertical config
    if not migration_queries:
        config = get_vertical(vertical)
        templates = config.get("migration_query_templates", [])
        year = datetime.now().year
        migration_queries = [
            t.format(company=company, year=year) for t in templates
        ]
    
    if not complaint_queries:
        config = get_vertical(vertical)
        templates = config.get("complaint_query_templates", [])
        year = datetime.now().year
        complaint_queries = [
            t.format(company=company, year=year) for t in templates
        ]
    
    migration_bullets = []
    complaint_bullets = []
    
    # Migration queries
    for query in migration_queries:
        try:
            results = client.search(query=query, max_results=2)
            for r in results.get("results", []):
                content = r.get("content", "").strip()
                url     = r.get("url", "")
                if content:
                    migration_bullets.append(
                        f"[Migration] [{url}] {content[:800]}"
                    )
        except Exception as e:
            print(f"    ⚠️  Migration query error: {e}")
    
    # Complaint queries
    for query in complaint_queries:
        try:
            results = client.search(query=query, max_results=2)
            for r in results.get("results", []):
                content = r.get("content", "").strip()
                url     = r.get("url", "")
                if content:
                    complaint_bullets.append(
                        f"[Complaint] [{url}] {content[:800]}"
                    )
        except Exception as e:
            print(f"    ⚠️  Complaint query error: {e}")
    
    # Save migrations
    if migration_bullets:
        save_research(
            company=company,
            data_type="migration",
            source_type="migration_tavily",
            source_url="tavily_migration",
            bullets=migration_bullets
        )
    
    # Save complaints
    if complaint_bullets:
        save_research(
            company=company,
            data_type="complaint",
            source_type="complaint_tavily",
            source_url="tavily_complaint",
            bullets=complaint_bullets
        )
    
    total = len(migration_bullets) + len(complaint_bullets)
    print(f"    ✅ Migration: {len(migration_bullets)} bullets | "
          f"Complaints: {len(complaint_bullets)} bullets")
    return migration_bullets + complaint_bullets