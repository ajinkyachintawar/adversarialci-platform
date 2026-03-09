"""
Hacker News Agent
=================
Scrapes HN discussions via Algolia API.
Now vertical-aware — loads relevance keywords from verticals config.
"""

import requests
from db.atlas import save_research
from verticals import get_hn_keywords


HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def hn_agent(company: str, vertical: str = "database") -> list[str]:
    """
    Search Hacker News for company discussions.
    
    Args:
        company: Company name to research
        vertical: Industry vertical for relevance keywords
        
    Returns:
        List of bullet points with HN discussions
    """
    print(f"  🟡 [HN] Scraping discussions for {company}...")
    
    # Get relevance keywords from vertical config
    relevance_keywords = get_hn_keywords(vertical)
    
    bullets = []
    company_lower = company.lower()
    
    try:
        params = {
            "query":       company,
            "tags":        "story",
            "hitsPerPage": 20
        }
        response = requests.get(HN_SEARCH_URL, params=params, timeout=10)
        data     = response.json()
        
        for hit in data.get("hits", []):
            title  = hit.get("title", "")
            url    = hit.get("url", "")
            points = hit.get("points", 0)
            
            if not title:
                continue
            
            title_lower = title.lower()
            
            # Must mention company name directly
            if company_lower not in title_lower:
                continue
            
            # Must have at least one relevant keyword
            has_relevance = any(
                k in title_lower for k in relevance_keywords
            )
            
            # OR must have significant upvotes (community found it important)
            if not has_relevance and points < 100:
                continue
            
            bullets.append(f"[HN {points}pts] {title} — {url}")
    
    except Exception as e:
        print(f"    ⚠️  HN error: {e}")
    
    save_research(
        company=company,
        data_type="sentiment",
        source_type="hn",
        source_url="hn_algolia_api",
        bullets=bullets
    )
    
    print(f"    ✅ HN: {len(bullets)} bullets saved")
    return bullets