"""
Atlas v2
========
MongoDB Atlas database operations.
Enhanced with vendor status tracking and TTL-based freshness.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime, timedelta
from config import MONGODB_URI, DB_NAME, FRESHNESS_DAYS


client = None
db = None


# ─── TTL Configuration ──────────────────────────────────────

TTL_DAYS = {
    "pricing_scrape":   30,   # Monthly
    "tavily":           7,    # Weekly
    "hn":               7,    # Weekly
    "github":           7,    # Weekly
    "blog_rss":         14,   # Bi-weekly
    "migration_tavily": 14,   # Bi-weekly
    "complaint_tavily": 14,   # Bi-weekly
    "hn_2024":          365,  # Yearly (historical)
    "hn_2025":          365,  # Yearly (historical)
}

DEFAULT_TTL = FRESHNESS_DAYS  # Fallback


# ─── Connection ─────────────────────────────────────────────

def connect():
    global client, db
    try:
        client = MongoClient(
    MONGODB_URI,
    tls=True,
    serverSelectionTimeoutMS=5000
)
        client.admin.command("ping")
        db = client[DB_NAME]
        print("✅ Atlas connected")
    except ConnectionFailure as e:
        print(f"❌ Atlas connection failed: {e}")
        raise


def get_collection(name: str):
    if db is None:
        connect()
    return db[name]


# ─── Company Operations ─────────────────────────────────────

def upsert_company(name: str):
    """Create or update company record."""
    col = get_collection("companies")
    col.update_one(
        {"name": name},
        {"$setOnInsert": {
            "name": name,
            "created_at": datetime.utcnow(),
            "last_scraped": None,
            "freshness_flag": "new"
        }},
        upsert=True
    )


def mark_scraped(name: str):
    """Mark company as freshly scraped."""
    col = get_collection("companies")
    col.update_one(
        {"name": name},
        {"$set": {
            "last_scraped": datetime.utcnow(),
            "freshness_flag": "fresh"
        }}
    )


def get_vendor_status(name: str) -> str:
    """
    Get vendor status.
    
    Returns:
        'new' - Never scraped
        'stale' - Scraped but outdated
        'fresh' - Recently scraped
    """
    col = get_collection("companies")
    doc = col.find_one({"name": name})
    
    if not doc or not doc.get("last_scraped"):
        return "new"
    
    cutoff = datetime.utcnow() - timedelta(days=DEFAULT_TTL)
    if doc["last_scraped"] < cutoff:
        return "stale"
    
    return "fresh"


def is_stale(name: str) -> bool:
    """Check if company data is stale (legacy compatibility)."""
    return get_vendor_status(name) != "fresh"


def is_new(name: str) -> bool:
    """Check if company has never been scraped."""
    return get_vendor_status(name) == "new"


def check_historical_done(name: str, vertical: str) -> bool:
    """Check if historical scrape completed for this vertical."""
    col = get_collection("companies")
    doc = col.find_one({"name": name})
    
    if not doc:
        return False
    
    return doc.get(f"historical_scraped_{vertical}", False)


def mark_historical_done(name: str, vertical: str):
    """Mark historical scrape as complete for this vertical."""
    col = get_collection("companies")
    col.update_one(
        {"name": name},
        {"$set": {
            f"historical_scraped_{vertical}": True,
            f"historical_scraped_{vertical}_at": datetime.utcnow()
        }}
    )


# ─── Research Data ──────────────────────────────────────────

def save_research(company: str, data_type: str,
                  source_type: str, source_url: str,
                  bullets: list):
    """Save research data with TTL metadata."""
    col = get_collection("research_data")
    
    ttl = TTL_DAYS.get(source_type, DEFAULT_TTL)
    
    col.insert_one({
        "company": company,
        "data_type": data_type,
        "source_type": source_type,
        "source_url": source_url,
        "content_bullets": bullets,
        "verified": False,
        "confidence_score": None,
        "contradiction_flag": False,
        "scraped_at": datetime.utcnow(),
        "ttl_days": ttl,
        "expires_at": datetime.utcnow() + timedelta(days=ttl)
    })


def get_research(company: str, verified_only: bool = True) -> list:
    """Get research data for a company."""
    col = get_collection("research_data")
    
    query = {"company": company}
    if verified_only:
        query["verified"] = True
    
    return list(col.find(query, {"_id": 0}))


def is_source_stale(company: str, source_type: str) -> bool:
    """Check if a specific source type is stale for a company."""
    col = get_collection("research_data")
    
    doc = col.find_one(
        {"company": company, "source_type": source_type},
        sort=[("scraped_at", -1)]
    )
    
    if not doc:
        return True
    
    ttl = TTL_DAYS.get(source_type, DEFAULT_TTL)
    cutoff = datetime.utcnow() - timedelta(days=ttl)
    
    scraped_at = doc.get("scraped_at")
    if not scraped_at:
        return True
    
    return scraped_at < cutoff


def flag_contradiction(doc_id, reason: str):
    """Flag a document as containing contradictions."""
    col = get_collection("research_data")
    col.update_one(
        {"_id": doc_id},
        {"$set": {
            "contradiction_flag": True,
            "contradiction_reason": reason
        }}
    )


def mark_verified(doc_id, confidence: float):
    """Mark a document as verified with confidence score."""
    col = get_collection("research_data")
    col.update_one(
        {"_id": doc_id},
        {"$set": {
            "verified": True,
            "confidence_score": confidence
        }}
    )


# ─── Court Sessions ─────────────────────────────────────────

def save_session(session: dict) -> str:
    """Save court session and return ID."""
    col = get_collection("court_sessions")
    result = col.insert_one({
        **session,
        "created_at": datetime.utcnow()
    })
    return str(result.inserted_id)


def get_session(session_id: str) -> dict:
    """Get a court session by ID."""
    from bson import ObjectId
    col = get_collection("court_sessions")
    return col.find_one({"_id": ObjectId(session_id)})


def get_recent_sessions(limit: int = 10) -> list:
    """Get recent court sessions."""
    col = get_collection("court_sessions")
    return list(col.find(
        {},
        {"_id": 1, "created_at": 1, "plaintiff": 1, "verdict": 1}
    ).sort("created_at", -1).limit(limit))


# ─── Data Freshness Report ──────────────────────────────────

def get_freshness_report() -> dict:
    """Get freshness status for all companies."""
    col = get_collection("companies")
    companies = list(col.find({}, {"_id": 0}))
    
    report = {
        "fresh": [],
        "stale": [],
        "new": []
    }
    
    for company in companies:
        name = company["name"]
        status = get_vendor_status(name)
        
        report[status].append({
            "name": name,
            "last_scraped": company.get("last_scraped"),
            "days_ago": (datetime.utcnow() - company["last_scraped"]).days 
                        if company.get("last_scraped") else None
        })
    
    return report


if __name__ == "__main__":
    connect()
    
    # Test freshness report
    report = get_freshness_report()
    
    print("\n📊 FRESHNESS REPORT")
    print("=" * 40)
    
    print(f"\n✅ Fresh ({len(report['fresh'])}):")
    for c in report["fresh"]:
        print(f"   {c['name']} ({c['days_ago']}d ago)")
    
    print(f"\n🔄 Stale ({len(report['stale'])}):")
    for c in report["stale"]:
        print(f"   {c['name']} ({c['days_ago']}d ago)")
    
    print(f"\n🆕 New ({len(report['new'])}):")
    for c in report["new"]:
        print(f"   {c['name']}")