"""
Verticals Registry (v2)
=======================
Central registry for all vertical configs.
NOTE: Vendors are now in vendors.json, accessed via vendor_registry.py
"""

from verticals.database import DATABASE_CONFIG
from verticals.cloud import CLOUD_CONFIG
from verticals.crm import CRM_CONFIG

# Registry of all verticals
VERTICALS = {}


def register_vertical(config: dict):
    """Register a vertical configuration."""
    name = config.get("name")
    if name:
        VERTICALS[name] = config
        print(f"  Registered vertical: {name}")


def list_verticals() -> list[str]:
    """List all registered vertical names."""
    return list(VERTICALS.keys())


def get_vertical(name: str) -> dict:
    """Get a vertical configuration by name."""
    if name not in VERTICALS:
        raise ValueError(f"Unknown vertical: {name}. Available: {list_verticals()}")
    return VERTICALS[name]


def get_dimensions(vertical: str) -> list[str]:
    """Get dimensions for a vertical."""
    return get_vertical(vertical).get("dimensions", [])


def get_dimension_keywords(vertical: str) -> dict:
    """Get dimension keywords for a vertical."""
    return get_vertical(vertical).get("dimension_keywords", {})


def get_priority_weights(vertical: str, priority: str) -> dict:
    """Get weights for a specific priority."""
    config = get_vertical(vertical)
    priority_lower = priority.lower().strip()
    weights = config.get("priority_weights", {})
    for key in weights:
        if key in priority_lower:
            return weights[key]
    return config.get("default_weights", {})


def get_judge_context(vertical: str) -> str:
    """Get the judge context string for prompts."""
    return get_vertical(vertical).get("judge_context", "")


def get_tavily_templates(vertical: str) -> list[str]:
    """Get Tavily query templates for a vertical."""
    return get_vertical(vertical).get("tavily_query_templates", [])


def get_hn_keywords(vertical: str) -> list[str]:
    """Get HN relevance keywords for a vertical."""
    return get_vertical(vertical).get("hn_relevance_keywords", [])


def get_migration_templates(vertical: str) -> list[str]:
    """Get migration query templates for a vertical."""
    return get_vertical(vertical).get("migration_query_templates", [])


def get_complaint_templates(vertical: str) -> list[str]:
    """Get complaint query templates for a vertical."""
    return get_vertical(vertical).get("complaint_query_templates", [])


def get_plaintiff_questions(vertical: str) -> list[dict]:
    """Get plaintiff intake questions for case filing."""
    return get_vertical(vertical).get("plaintiff_questions", [])


def get_vendor_config(vertical: str, company: str) -> dict:
    """
    Get vendor-specific config (URLs, queries) from vendor_registry.
    This replaces the old lookup in verticals config.
    """
    from vendor_registry import get_vendor_urls
    result = get_vendor_urls(company, vertical)
    if result:
        return result
    # Return empty config if not found
    return {
        "pricing_url": None,
        "github_repo": None,
        "blog_rss": [],
        "blog_tavily": [],
        "migration_queries": [],
        "complaint_queries": []
    }


# ─── Auto-register on import ────────────────────────────────

register_vertical(DATABASE_CONFIG)
register_vertical(CLOUD_CONFIG)
register_vertical(CRM_CONFIG)