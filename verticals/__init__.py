"""
Verticals Module
================
Central configuration for all supported industry verticals.

Each vertical defines:
- Dimensions for courtroom evaluation
- Keywords for argument routing
- Vendor-specific configs (pricing URLs, GitHub repos, etc.)
- Plaintiff question templates

Usage:
    from verticals import get_vertical, list_verticals
    
    config = get_vertical("database")
    vendors = config["vendors"]
"""

from verticals.registry import (
    get_vertical,
    list_verticals,
    get_vendor_config,
    get_plaintiff_questions,
    get_dimensions,
    get_dimension_keywords,
    get_priority_weights,
    get_judge_context,
    get_tavily_templates,
    get_hn_keywords,
    register_vertical,
    VERTICALS
)

__all__ = [
    "get_vertical",
    "list_verticals", 
    "get_vendor_config",
    "get_plaintiff_questions",
    "get_dimensions",
    "get_dimension_keywords",
    "get_priority_weights",
    "get_judge_context",
    "get_tavily_templates",
    "get_hn_keywords",
    "register_vertical",
    "VERTICALS"
]