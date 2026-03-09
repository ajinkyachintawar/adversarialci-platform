"""
Blog Agent - Scrapes blog RSS feeds or uses Tavily fallback

Modified to use vendor_registry instead of hardcoded dicts.
"""

import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from tavily import TavilyClient
from config import TAVILY_API_KEY
from db.atlas import save_research
from vendor_registry import get_vendor_urls


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def parse_rss(url: str, since: datetime = None) -> list:
    """Parse RSS feed and extract blog posts"""
    bullets = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"      ⚠️  RSS {response.status_code}: {url}")
            return bullets
        
        root = ET.fromstring(response.content)
        namespace = ""
        if "atom" in root.tag.lower():
            namespace = "{http://www.w3.org/2005/Atom}"
        
        items = root.findall(f".//{namespace}item")
        if not items:
            items = root.findall(f".//{namespace}entry")
        
        for item in items:
            title_el = item.find(f"{namespace}title")
            title = title_el.text.strip() if (
                title_el is not None and title_el.text
            ) else ""
            
            link_el = item.find(f"{namespace}link")
            link = ""
            if link_el is not None:
                link = link_el.text or link_el.get("href", "")
            link = link.strip() if link else ""
            
            date_el = (
                item.find(f"{namespace}pubDate") or
                item.find(f"{namespace}published") or
                item.find(f"{namespace}updated")
            )
            pub_date = None
            if date_el is not None and date_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(
                        date_el.text
                    ).replace(tzinfo=None)
                except Exception:
                    try:
                        pub_date = datetime.fromisoformat(
                            date_el.text[:19]
                        )
                    except Exception:
                        pass
            
            if since and pub_date and pub_date < since:
                continue
            
            desc_el = (
                item.find(f"{namespace}description") or
                item.find(f"{namespace}summary") or
                item.find(f"{namespace}content")
            )
            desc = ""
            if desc_el is not None and desc_el.text:
                desc = re.sub(r"<[^>]+>", " ", desc_el.text)
                desc = " ".join(desc.split())[:400]
            
            if title:
                date_str = pub_date.strftime(
                    "%Y-%m-%d"
                ) if pub_date else "unknown"
                bullet = (
                    f"[Blog {date_str}] {title}"
                    f"{f' — {desc}' if desc else ''}"
                    f"{f' ({link})' if link else ''}"
                )
                bullets.append(bullet)
    
    except Exception as e:
        print(f"      ⚠️  RSS error {url}: {e}")
    
    return bullets


def blog_tavily(company: str, queries: list[str], since: datetime = None) -> list:
    """Fallback: Search blogs via Tavily for companies without RSS"""
    client = TavilyClient(api_key=TAVILY_API_KEY)
    bullets = []
    
    for query in queries:
        try:
            results = client.search(query=query, max_results=3)
            for r in results.get("results", []):
                content = r.get("content", "").strip()
                url = r.get("url", "")
                if content:
                    bullets.append(
                        f"[Blog Tavily] [{url}] {content[:600]}"
                    )
        except Exception as e:
            print(f"      ⚠️  Blog Tavily error: {e}")
    
    return bullets


def blog_agent(company: str, vertical: str = "database", since: datetime = None) -> list:
    """
    Scrape blog posts for a company.
    
    Uses RSS if available, falls back to Tavily search.
    
    Args:
        company: Company name (looked up in registry)
        vertical: Vertical category (for future use)
        since: Optional datetime to filter posts
        
    Returns:
        List of blog post bullets
    """
    print(f"  📝 [Blog] Scraping blog for {company}...")
    
    bullets = []
    
    # Get config from registry
    vendor_data = get_vendor_urls(company, vertical)
    
    if not vendor_data:
        print(f"    ⚠️  {company} not found in registry")
        return bullets
    
    blog_rss = vendor_data.get("blog_rss", [])
    tavily_queries = vendor_data.get("blog_tavily", [])
    
    # Try RSS first (blog_rss is a list of URLs)
    if blog_rss:
        for rss_url in blog_rss:
            bullets.extend(parse_rss(rss_url, since))
    
    # Fallback to Tavily if no RSS or RSS returned nothing
    elif tavily_queries:
        bullets = blog_tavily(company, tavily_queries, since)
    
    # Generate default Tavily query if nothing configured
    elif not blog_rss and not tavily_queries:
        default_queries = [
            f"{company} blog announcement product update 2025 2026",
            f"{company} new feature release blog 2025"
        ]
        bullets = blog_tavily(company, default_queries, since)
    
    # Deduplicate by title prefix
    seen = set()
    unique = []
    for b in bullets:
        key = b[:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(b)
    
    # Save to Atlas
    if unique:
        save_research(
            company=company,
            data_type="blog",
            source_type="blog_rss",
            source_url=blog_rss or f"tavily_blog_{company.lower().replace(' ', '_')}",
            bullets=unique
        )
    
    print(f"    ✅ Blog: {len(unique)} posts saved")
    return unique