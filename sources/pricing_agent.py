"""
Pricing Agent - Scrapes pricing pages

Modified to use vendor_registry instead of hardcoded PRICING_URLS dict.
"""

import requests
from bs4 import BeautifulSoup
from db.atlas import save_research
from vendor_registry import get_vendor_urls


def pricing_agent(company: str, vertical: str = "database") -> list[str]:
    """
    Scrape pricing page for a company.
    
    Args:
        company: Company name (will be looked up in registry)
        vertical: Vertical category (for future use)
        
    Returns:
        List of pricing bullet points
    """
    print(f"  💰 [Pricing] Scraping pricing for {company}...")
    
    bullets = []
    
    # Get URL from registry
    vendor_data = get_vendor_urls(company, vertical)
    
    if not vendor_data:
        print(f"    ⚠️  {company} not found in registry")
        return bullets
    
    url = vendor_data.get("pricing_url")
    
    if not url:
        print(f"    ⚠️  No pricing URL configured for {company}")
        return bullets
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        
        # Extract pricing-relevant chunks
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            keywords = [
                "$", "free", "price", "plan", "month",
                "tier", "cost", "billing", "credit"
            ]
            if any(k in line.lower() for k in keywords) and len(line) > 20:
                bullets.append(f"[pricing] {line[:500]}")
                if len(bullets) >= 20:
                    break
    
    except Exception as e:
        print(f"    ⚠️  Pricing scrape error: {e}")
    
    # Save to Atlas
    if bullets:
        save_research(
            company=company,
            data_type="pricing",
            source_type="pricing_scrape",
            source_url=url,
            bullets=bullets
        )
    
    print(f"    ✅ Pricing: {len(bullets)} bullets saved")
    return bullets