"""
GitHub Agent - Scrapes GitHub issues and releases

Modified to use vendor_registry instead of hardcoded GITHUB_REPOS dict.
"""

import requests
from config import GITHUB_TOKEN
from db.atlas import save_research
from vendor_registry import get_vendor_urls


HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def github_agent(company: str, vertical: str = "database") -> list[str]:
    """
    Scrape GitHub issues and releases for a company.
    
    Args:
        company: Company name (looked up in registry)
        vertical: Vertical category (for future use)
        
    Returns:
        List of GitHub-related bullets
    """
    print(f"  🐙 [GitHub] Scraping issues for {company}...")
    
    bullets = []
    
    # Get repo from registry
    vendor_data = get_vendor_urls(company, vertical)
    
    if not vendor_data:
        print(f"    ⚠️  {company} not found in registry")
        return bullets
    
    repo = vendor_data.get("github_repo")
    
    if not repo:
        print(f"    ⚠️  No GitHub repo configured for {company}")
        return bullets
    
    try:
        # Recent issues with complaints
        url = f"https://api.github.com/repos/{repo}/issues"
        params = {"state": "open", "per_page": 10, "sort": "created"}
        response = requests.get(
            url, headers=HEADERS, params=params, timeout=10
        )
        issues = response.json()
        
        for issue in issues:
            if isinstance(issue, dict):
                title = issue.get("title", "")
                body = (issue.get("body") or "")[:200]
                link = issue.get("html_url", "")
                bullets.append(
                    f"[GitHub Issue] {title} — {body} ({link})"
                )
        
        # Recent releases
        rel_url = f"https://api.github.com/repos/{repo}/releases"
        rel_resp = requests.get(
            rel_url, headers=HEADERS, params={"per_page": 3}, timeout=10
        )
        releases = rel_resp.json()
        
        for release in releases:
            if isinstance(release, dict):
                name = release.get("name", "")
                date = release.get("published_at", "")[:10]
                bullets.append(f"[GitHub Release] {name} — {date}")
    
    except Exception as e:
        print(f"    ⚠️  GitHub error: {e}")
    
    # Save to Atlas
    if bullets:
        save_research(
            company=company,
            data_type="tech",
            source_type="github",
            source_url=f"https://github.com/{repo}",
            bullets=bullets
        )
    
    print(f"    ✅ GitHub: {len(bullets)} bullets saved")
    return bullets