import os
from dotenv import load_dotenv
load_dotenv()

# API Keys
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN")
MONGODB_URI     = os.getenv("MONGODB_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# comma-separated fallback keys (different Google projects = separate quotas)
GEMINI_API_KEYS = [k.strip() for k in
                   os.getenv("GEMINI_API_KEYS", GEMINI_API_KEY or "").split(",")
                   if k.strip()]

# MongoDB
DB_NAME         = "war_room"
COLLECTION_RESEARCH  = "research_data"
COLLECTION_COMPANIES = "companies"
COLLECTION_SESSIONS  = "court_sessions"

# Freshness threshold (days)
FRESHNESS_DAYS  = 14

# LLM
LLM_MODEL       = "llama-3.3-70b-versatile"
LLM_PROVIDER    = "groq"