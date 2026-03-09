"""
Sources Module
==============
All source agents for competitive intelligence gathering.

Each agent is now vertical-aware and reads config from verticals module.
"""

from sources.tavily_agent import tavily_agent
from sources.hn_agent import hn_agent
from sources.pricing_agent import pricing_agent
from sources.github_agent import github_agent
from sources.blog_agent import blog_agent
from sources.migration_agent import migration_agent
from sources.router import source_router

__all__ = [
    "tavily_agent",
    "hn_agent",
    "pricing_agent",
    "github_agent",
    "blog_agent",
    "migration_agent",
    "source_router"
]