"""
Vendor Registry v2
==================
Single source of truth for all vendors.
Reads/writes to vendors.json only.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

VENDORS_FILE = Path(__file__).parent / "vendors.json"


def load_vendors() -> dict:
    if not VENDORS_FILE.exists():
        return {"database": {}, "cloud": {}, "crm": {}}
    try:
        with open(VENDORS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  Warning: Error loading vendors.json: {e}")
        return {"database": {}, "cloud": {}, "crm": {}}


def save_vendors(data: dict) -> bool:
    try:
        with open(VENDORS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"  Warning: Error saving vendors.json: {e}")
        return False


def normalize_name(name: str) -> str:
    return name.strip().lower()


def find_canonical_name(name: str, vertical: str) -> Optional[str]:
    vendors = load_vendors()
    vertical_vendors = vendors.get(vertical, {})
    normalized = normalize_name(name)
    for canonical, config in vertical_vendors.items():
        if normalize_name(canonical) == normalized:
            return canonical
    return None


def list_vendors(vertical: str) -> list[str]:
    vendors = load_vendors()
    return list(vendors.get(vertical, {}).keys())


def get_vendor(name: str, vertical: str) -> Optional[dict]:
    vendors = load_vendors()
    vertical_vendors = vendors.get(vertical, {})
    if name in vertical_vendors:
        return vertical_vendors[name]
    normalized = normalize_name(name)
    for canonical, config in vertical_vendors.items():
        if normalize_name(canonical) == normalized:
            return config
    return None


def vendor_exists(name: str, vertical: str) -> bool:
    return get_vendor(name, vertical) is not None


def add_vendor(name: str, vertical: str, pricing_url: str,
               github_repo: Optional[str] = None,
               blog_rss: Optional[str] = None) -> bool:
    vendors = load_vendors()
    if vertical not in vendors:
        vendors[vertical] = {}
    if vendor_exists(name, vertical):
        print(f"  Warning: Vendor '{name}' already exists in {vertical}")
        return False
    vendors[vertical][name.strip()] = {
        "pricing_url": pricing_url,
        "github_repo": github_repo,
        "blog_rss": [blog_rss] if blog_rss else [],
        "blog_tavily": [],
        "migration_queries": [],
        "complaint_queries": [],
        "added_at": datetime.now().strftime("%Y-%m-%d"),
        "added_by": "user"
    }
    return save_vendors(vendors)


def update_vendor(name: str, vertical: str,
                  pricing_url: Optional[str] = None,
                  github_repo: Optional[str] = None,
                  blog_rss: Optional[str] = None) -> bool:
    vendors = load_vendors()
    canonical = find_canonical_name(name, vertical)
    if not canonical:
        print(f"  Warning: Vendor '{name}' not found in {vertical}")
        return False
    config = vendors[vertical][canonical]
    if pricing_url is not None:
        config["pricing_url"] = pricing_url
    if github_repo is not None:
        config["github_repo"] = github_repo
    if blog_rss is not None:
        if blog_rss:
            if blog_rss not in config.get("blog_rss", []):
                config["blog_rss"] = config.get("blog_rss", []) + [blog_rss]
        else:
            config["blog_rss"] = []
    config["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    return save_vendors(vendors)


def delete_vendor(name: str, vertical: str) -> bool:
    vendors = load_vendors()
    canonical = find_canonical_name(name, vertical)
    if not canonical:
        print(f"  Warning: Vendor '{name}' not found in {vertical}")
        return False
    del vendors[vertical][canonical]
    return save_vendors(vendors)


def get_vendor_urls(name: str, vertical: str) -> Optional[dict]:
    config = get_vendor(name, vertical)
    if not config:
        return None
    canonical = find_canonical_name(name, vertical)
    return {
        "display_name": canonical,
        "pricing_url": config.get("pricing_url"),
        "github_repo": config.get("github_repo"),
        "blog_rss": config.get("blog_rss", []),
        "blog_tavily": config.get("blog_tavily", []),
        "migration_queries": config.get("migration_queries", []),
        "complaint_queries": config.get("complaint_queries", [])
    }


def validate_url(url: str) -> tuple[bool, str]:
    if not url:
        return True, ""
    url = url.strip()
    if not re.match(r'^https?://', url):
        return False, "URL must start with http:// or https://"
    pattern = r'^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(/[^\s]*)?$'
    if re.match(pattern, url):
        return True, ""
    return False, f"Invalid URL format: {url}"


def validate_github_repo(repo: str) -> tuple[bool, str]:
    if not repo:
        return True, ""
    repo = repo.strip()
    if re.match(r'^[\w.-]+/[\w.-]+$', repo):
        return True, ""
    return False, "Invalid format. Use: owner/repo (e.g. mongodb/mongo)"


def validate_vendors_exist(vendors: list[str], vertical: str) -> tuple[list[str], list[str]]:
    existing = []
    missing = []
    for vendor in vendors:
        canonical = find_canonical_name(vendor, vertical)
        if canonical:
            existing.append(canonical)
        else:
            missing.append(vendor)
    return existing, missing


def get_vendor_status(name: str, vertical: str) -> dict:
    config = get_vendor(name, vertical)
    if not config:
        return {"exists": False}
    return {
        "exists": True,
        "has_pricing": bool(config.get("pricing_url")),
        "has_github": bool(config.get("github_repo")),
        "has_blog": bool(config.get("blog_rss")),
        "added_at": config.get("added_at", "unknown"),
        "added_by": config.get("added_by", "unknown")
    }


if __name__ == "__main__":
    print("Vendor Registry Test")
    print("=" * 50)
    print("\nDatabase vendors:")
    for v in list_vendors("database"):
        status = get_vendor_status(v, "database")
        pricing = "Y" if status["has_pricing"] else "N"
        github = "Y" if status["has_github"] else "N"
        blog = "Y" if status["has_blog"] else "N"
        print(f"  {v}: Pricing={pricing} GitHub={github} Blog={blog}")