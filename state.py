"""
State v2
========
Enhanced state with mode support and vertical tracking.
"""

from typing import TypedDict, Literal, Optional


class WarRoomState(TypedDict):
    # ─── Mode & Vertical ───
    mode: str                       # "buyer" | "seller" | "analyst" | "sourcing"
    vertical: str                   # "database" | "cloud" | "crm"
    
    # ─── Companies ───
    primary: str                    # Primary company (for seller: your company)
    competitors: list[str]          # Competitor companies
    my_company: Optional[str]       # Seller mode: the company you sell for
    
    # ─── Plaintiff/Profile ───
    plaintiff: dict                 # Buyer/prospect profile
    
    # ─── Data Layer ───
    db_cache: dict                  # Cached data from Atlas
    new_companies: list[str]        # New vendors needing full scrape
    stale_companies: list[str]      # Vendors needing refresh
    fresh_companies: list[str]      # Vendors with fresh data
    research: dict                  # Scraped research data
    
    # ─── Court ───
    round: int                      # Current court round
    arguments: list[dict]           # Built arguments
    cross_examination: list[dict]   # Cross-exam results
    verdict: dict                   # Final verdict
    
    # ─── Meta ───
    errors: list[str]               # Error tracking
    stage: str                      # Current pipeline stage


def create_initial_state(vertical: str = "database", mode: str = "buyer") -> WarRoomState:
    """
    Create initial state with defaults.
    
    Args:
        vertical: Industry vertical
        mode: buyer | seller | analyst | sourcing
    """
    return {
        # Mode & Vertical
        "mode": mode,
        "vertical": vertical,
        
        # Companies
        "primary": "",
        "competitors": [],
        "my_company": None,
        
        # Plaintiff
        "plaintiff": {},
        
        # Data Layer
        "db_cache": {},
        "new_companies": [],
        "stale_companies": [],
        "fresh_companies": [],
        "research": {},
        
        # Court
        "round": 0,
        "arguments": [],
        "cross_examination": [],
        "verdict": {},
        
        # Meta
        "errors": [],
        "stage": "init"
    }


# ─── Convenience Functions ───

def get_all_companies(state: WarRoomState) -> list[str]:
    """Get all companies in evaluation."""
    companies = [state["primary"]] if state["primary"] else []
    companies.extend(state.get("competitors", []))
    return companies


def get_companies_to_scrape(state: WarRoomState) -> list[str]:
    """Get companies that need scraping."""
    return state.get("new_companies", []) + state.get("stale_companies", [])


def is_seller_mode(state: WarRoomState) -> bool:
    """Check if in seller mode."""
    return state.get("mode") == "seller"


def get_mode_label(state: WarRoomState) -> str:
    """Get display label for current mode."""
    labels = {
        "buyer": "🛒 Buyer Evaluation",
        "seller": "🎯 Seller Battlecard",
        "analyst": "📊 Market Analysis",
        "sourcing": "🔍 Data Collection"
    }
    return labels.get(state.get("mode", "buyer"), "Unknown Mode")