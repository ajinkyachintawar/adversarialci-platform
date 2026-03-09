"""
Tavily Agent
============
Web search agent using Tavily API.
Now vertical-aware — loads query templates from verticals config.
"""

from datetime import datetime
from tavily import TavilyClient
from config import TAVILY_API_KEY
from db.atlas import save_research
from verticals import get_vertical, get_tavily_templates


client = TavilyClient(api_key=TAVILY_API_KEY)


def tavily_agent(company: str, vertical: str = "database") -> list[str]:
    """
    Search web for company intel using Tavily.
    
    Args:
        company: Company name to research
        vertical: Industry vertical for query templates
        
    Returns:
        List of bullet points with findings
    """
    print(f"  🌐 [Tavily] Scraping web for {company}...")
    
    # Get query templates from vertical config
    templates = get_tavily_templates(vertical)
    year = datetime.now().year
    
    # Build queries from templates
    queries = [
        template.format(company=company, year=year)
        for template in templates
    ]
    
    bullets = []
    
    for query in queries:
        try:
            results = client.search(
                query=query,
                max_results=3
            )
            for r in results.get("results", []):
                content = r.get("content", "").strip()
                url     = r.get("url", "")
                if content:
                    bullets.append(f"[{url}] {content[:800]}")
        except Exception as e:
            print(f"    ⚠️  Tavily error: {e}")
    
    save_research(
        company=company,
        data_type="tech",
        source_type="tavily",
        source_url="tavily_search",
        bullets=bullets
    )
    
    print(f"    ✅ Tavily: {len(bullets)} bullets saved")
    return bullets


# ─── Backward Compatibility ──────────────────────────────────
# Old signature still works, defaults to database vertical

def tavily_agent_legacy(company: str) -> list[str]:
    """Legacy wrapper for backward compatibility."""
    return tavily_agent(company, vertical="database")