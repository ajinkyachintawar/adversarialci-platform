from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CompanyDoc(BaseModel):
    name: str
    last_scraped: Optional[datetime] = None
    freshness_flag: str = "stale"


class ResearchDoc(BaseModel):
    company: str
    data_type: str        # tech / market / pricing / sentiment / github / hn
    source_type: str      # tavily / reddit / hn / pricing_scrape / github
    source_url: str
    content_bullets: list[str]
    verified: bool = False
    confidence_score: Optional[float] = None
    contradiction_flag: bool = False
    scraped_at: datetime


class CourtSession(BaseModel):
    session_id: str
    primary: str
    competitors: list[str]
    plaintiff_profile: dict
    arguments: list[dict]
    verdict: dict