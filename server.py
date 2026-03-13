from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import asyncio
import json

import os

# CORS for deployment
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    FRONTEND_URL
]

# Local imports from the Adversarial CI project
from vendor_registry import (
    list_vendors, get_vendor, add_vendor, update_vendor, delete_vendor,
    vendor_exists, validate_url
)
from verticals import list_verticals, get_vertical

app = FastAPI(title="Adversarial CI API", version="1.0.0")

# Allow the Vite React dev server to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Input Validation ---

class VendorCreate(BaseModel):
    name: str
    vertical: str
    pricing_url: str
    github_repo: Optional[str] = None
    blog_rss: Optional[str] = None

class VendorUpdate(BaseModel):
    name: str
    vertical: str
    pricing_url: Optional[str] = None
    github_repo: Optional[str] = None
    blog_rss: Optional[str] = None

class DeleteVendorReq(BaseModel):
    name: str
    vertical: str


# --- Vertical API Endpoints ---

@app.get("/api/verticals")
async def api_list_verticals() -> List[str]:
    """Returns a list of all supported vertical keys (e.g., ['database', 'cloud', 'crm'])."""
    return list_verticals()

@app.get("/api/verticals/{vertical}")
async def api_get_vertical_config(vertical: str) -> Dict[str, Any]:
    """Returns the configuration for a specific vertical (dimensions, questions)."""
    try:
        config = get_vertical(vertical)
        return config
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Vendor Registry API Endpoints ---

@app.get("/api/vendors/{vertical}")
async def api_list_vendors(vertical: str) -> Dict[str, Any]:
    """
    Returns the list of vendor names and their full config for a vertical.
    Replaces the frontend hardcoding of vendorsData.
    """
    try:
        # Validate vertical
        get_vertical(vertical)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vertical not found")
        
    vendor_names = list_vendors(vertical)
    vendor_data = {}
    for name in vendor_names:
        vendor_data[name] = get_vendor(name, vertical)
        
    return vendor_data

@app.post("/api/vendors")
async def api_add_vendor(vendor: VendorCreate):
    """Adds a new vendor to the registry."""
    if vendor_exists(vendor.name, vendor.vertical):
        raise HTTPException(status_code=400, detail=f"Vendor '{vendor.name}' already exists in {vendor.vertical}.")
    
    # Simple URL validation logic (from CLI)
    valid, err = validate_url(vendor.pricing_url)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid pricing URL: {err}")
        
    success = add_vendor(
        vendor.name, 
        vendor.vertical, 
        vendor.pricing_url, 
        vendor.github_repo, 
        vendor.blog_rss
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add vendor to registry.")
    
    return {"status": "success", "message": f"Vendor '{vendor.name}' added successfully."}

@app.put("/api/vendors")
async def api_update_vendor(vendor: VendorUpdate):
    """Updates an existing vendor's configuration."""
    if not vendor_exists(vendor.name, vendor.vertical):
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor.name}' not found in {vendor.vertical}.")
        
    # validate urls if provided
    if vendor.pricing_url:
        valid, err = validate_url(vendor.pricing_url)
        if not valid:
             raise HTTPException(status_code=400, detail=f"Invalid pricing URL: {err}")
             
    success = update_vendor(
        vendor.name, 
        vendor.vertical, 
        pricing_url=vendor.pricing_url,
        github_repo=vendor.github_repo,
        blog_rss=vendor.blog_rss
    )
    
    if not success:
         raise HTTPException(status_code=500, detail="Failed to update vendor.")
         
    return {"status": "success", "message": f"Vendor '{vendor.name}' updated successfully."}

@app.delete("/api/vendors")
async def api_delete_vendor(req: DeleteVendorReq):
    """Deletes a vendor from the registry."""
    if not vendor_exists(req.name, req.vertical):
         raise HTTPException(status_code=404, detail=f"Vendor '{req.name}' not found.")
         
    success = delete_vendor(req.name, req.vertical)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete vendor.")
         
    return {"status": "success", "message": f"Vendor '{req.name}' deleted."}


# --- Vendor Refresh / Re-Scrape Endpoint ---

class RefreshRequest(BaseModel):
    name: str
    vertical: str

@app.post("/api/vendors/refresh")
async def api_refresh_vendor(req: RefreshRequest):
    """
    Trigger a re-scrape of a vendor's intelligence data via SSE.
    Runs all 6 source agents and streams progress back.
    """
    from sse_starlette.sse import EventSourceResponse
    
    if not vendor_exists(req.name, req.vertical):
        raise HTTPException(status_code=404, detail=f"Vendor '{req.name}' not found in {req.vertical}")
    
    refresh_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    
    async def event_generator():
        import io, contextlib
        
        class RefreshLogStream(io.StringIO):
            def write(self, s: str) -> int:
                s = s.strip()
                if s and not s.isspace():
                    asyncio.run_coroutine_threadsafe(refresh_queue.put(s), loop)
                return len(s)
        
        def do_refresh():
            interceptor = RefreshLogStream()
            with contextlib.redirect_stdout(interceptor):
                try:
                    from sources.router import run_present_scrape
                    from db.atlas import connect, upsert_company, mark_scraped
                    connect()
                    upsert_company(req.name)
                    
                    print(f"🔄 Starting refresh for {req.name} ({req.vertical})")
                    print(f"━━━━━━━━━━━━━━━━━━━━")
                    
                    total = run_present_scrape(req.name, req.vertical)
                    mark_scraped(req.name)
                    
                    print(f"━━━━━━━━━━━━━━━━━━━━")
                    print(f"✅ Refresh complete: {total} new data points collected")
                    
                    return total
                except Exception as e:
                    print(f"❌ Refresh failed: {str(e)}")
                    return 0
        
        # Run in background thread
        refresh_task = asyncio.ensure_future(asyncio.to_thread(do_refresh))
        
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(refresh_queue.get(), timeout=1.0)
                    yield {"event": "log", "data": msg}
                except asyncio.TimeoutError:
                    if refresh_task.done():
                        # Drain remaining messages
                        while not refresh_queue.empty():
                            msg = await refresh_queue.get()
                            yield {"event": "log", "data": msg}
                        
                        result = refresh_task.result()
                        yield {"event": "log", "data": f"__REFRESH_DONE__:{result}"}
                        return
                    yield {"event": "ping", "data": "keep-alive"}
        except asyncio.CancelledError:
            return
    
    return EventSourceResponse(event_generator())


# --- Evaluation & Court Session Endpoints ---

from pydantic import Field
import uuid
import sys
import os

# Ensure the root directory is in the path so we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sse_starlette.sse import EventSourceResponse

# In-memory queues to hold logs for each session (for streaming)
# In production, this would be Redis or similar.
session_queues: Dict[str, asyncio.Queue[str]] = {}

class EvalReq(BaseModel):
    vertical: str
    mode: str = "buyer"
    primary: str
    competitors: List[str]
    plaintiff: Dict[str, Any]

@app.post("/api/evaluate")
async def api_evaluate_start(req: EvalReq):
    """
    Starts an asynchronous court session.
    Returns a session_id immediately so the client can connect to the SSE endpoint.
    """
    session_id = str(uuid.uuid4())
    session_queues[session_id] = asyncio.Queue()
    
    # We fire and forget the background task
    asyncio.create_task(run_court_background(session_id, req))
    
    return {"session_id": session_id, "status": "started"}

async def run_court_background(session_id: str, req: EvalReq):
    """Background task that runs the LangGraph loop and intercepts print statements."""
    queue = session_queues[session_id]
    
    # helper to easily push logs to UI
    async def log(msg: str):
        await queue.put(msg)
        
    await log("Initializing war room state...")
    
    try:
        from state import create_initial_state
        from main import build_main_graph
        from db.atlas import connect, upsert_company
        import sys
        
        # 1. Setup DB
        connect()
        companies = [req.primary] + req.competitors
        for company in companies:
            upsert_company(company)
            
        # 2. Setup State
        state = create_initial_state(req.vertical, req.mode)
        
        # Determine roles based on mode (same as main.py)
        if req.mode == "seller":
            my_company = req.primary
            primary = my_company
            competitors = req.competitors
        else:
            primary = req.primary
            competitors = req.competitors
            my_company = None
            
        state.update({
            "primary": primary,
            "competitors": competitors,
            "my_company": my_company,
            "plaintiff": req.plaintiff,
            "stage": "db_check"
        })
        
        await log(f"🎯 Target Acquired: {primary} vs {', '.join(competitors)}")
        
        app_graph = build_main_graph()
        
        # Custom interceptor for stdout to capture prints from the pipeline nodes
        import io
        import contextlib
        
        # Capture the event loop BEFORE entering the thread
        loop = asyncio.get_running_loop()
        
        class LogCapturingStream(io.StringIO):
            def write(self, s: str) -> int:
                s = s.strip()
                if s and not s.isspace():
                    # Thread-safe way to put items into the async queue
                    asyncio.run_coroutine_threadsafe(queue.put(s), loop)
                return len(s)
        
        # Run graph invocation silently, capturing output
        interceptor = LogCapturingStream()
        
        await log("--- COURT SESSION INITIALIZED ---")
        
        # Because the graph involves synchronous LLM calls (Groq), it will block the event loop
        # We run it in a threadpool to keep the server responsive
        def run_graph() -> dict:
            with contextlib.redirect_stdout(interceptor):
                return app_graph.invoke(state)
        
        final_state = await asyncio.to_thread(run_graph)
        
        # Find the latest report file written by the pipeline
        import glob
        report_files = sorted(glob.glob("outputs/reports/*.md"), key=os.path.getmtime, reverse=True)
        report_id = None
        if report_files:
            # Use the filename (without extension) as the report ID
            report_id = os.path.basename(report_files[0]).replace(".md", "")
        
        if report_id:
            await queue.put(f"__REPORT_READY__:{report_id}")
        else:
            await queue.put("⚠️ Pipeline completed but no report file was generated.")
        
    except Exception as e:
        await queue.put(f"ERROR: {str(e)}")
    finally:
        await queue.put("__DONE__")


@app.get("/api/stream/{session_id}")
async def api_stream_logs(session_id: str):
    """
    SSE Endpoint for streaming terminal logs to the UI.
    """
    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="Session not found")
        
    queue = session_queues[session_id]
    
    async def log_generator():
        try:
            while True:
                msg = await queue.get()
                if msg == "__DONE__":
                    # Cleanup server memory
                    session_queues.pop(session_id, None)
                    yield dict(data=msg)
                    break
                
                # Format for Server-Sent Events
                yield dict(data=msg)
        except asyncio.CancelledError:
            # Client disconnected
            pass
            
    return EventSourceResponse(log_generator())


@app.get("/api/reports/{report_id}")
async def api_get_report(report_id: str):
    """Read the report markdown file from disk."""
    report_path = f"outputs/reports/{report_id}.md"
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail=f"Report file not found: {report_id}")
    
    with open(report_path, "r") as f:
        content = f.read()
    
    return {"id": report_id, "content": content}

# --- Atlas Intelligence Endpoints ---

@app.get("/api/vendors/{vertical}/enriched")
async def api_get_enriched_vendors(vertical: str):
    """
    Returns vendor registry data enriched with Atlas intelligence stats.
    Merges vendors.json config with Atlas freshness + research counts.
    """
    try:
        get_vertical(vertical)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vertical not found")
    
    vendor_names = list_vendors(vertical)
    enriched = []
    
    # Try to get Atlas data
    atlas_data = {}
    try:
        from db.atlas import connect, get_collection, get_vendor_status as atlas_vendor_status
        connect()
        research_col = get_collection("research_data")
        
        for name in vendor_names:
            # Count research docs
            research_count = research_col.count_documents({"company": name})
            
            # Get source type breakdown using actual MongoDB source_type values
            SOURCE_TYPE_MAP = {
                "Pricing":    ["pricing_scrape"],
                "Blog":       ["blog_rss"],
                "GitHub":     ["github"],
                "Tavily":     ["tavily"],
                "HN":         ["hn", "hn_2024", "hn_2025", "hn_2026"],
                "Migration":  ["migration_tavily"],
                "Complaints": ["complaint_tavily"],
            }
            sources = {}
            for label, db_types in SOURCE_TYPE_MAP.items():
                sources[label] = research_col.count_documents({
                    "company": name,
                    "source_type": {"$in": db_types}
                })
            
            # Get last scraped time
            latest = research_col.find_one(
                {"company": name},
                sort=[("scraped_at", -1)]
            )
            last_scraped = None
            if latest and latest.get("scraped_at"):
                last_scraped = latest["scraped_at"].isoformat()
            
            atlas_data[name] = {
                "research_count": research_count,
                "sources": sources,
                "last_scraped": last_scraped,
                "status": atlas_vendor_status(name)
            }
    except Exception as e:
        print(f"Atlas connection failed (non-fatal): {e}")
    
    for name in vendor_names:
        config = get_vendor(name, vertical)
        if not config:
            continue
            
        vendor_info = {
            "name": name,
            "vertical": vertical,
            "pricing_url": config.get("pricing_url"),
            "github_repo": config.get("github_repo"),
            "blog_rss": config.get("blog_rss", []),
            "blog_tavily": config.get("blog_tavily", []),
            "migration_queries": config.get("migration_queries", []),
            "complaint_queries": config.get("complaint_queries", []),
            "added_at": config.get("added_at"),
            "added_by": config.get("added_by", "unknown"),
        }
        
        # Merge Atlas data if available
        if name in atlas_data:
            vendor_info["atlas"] = atlas_data[name]
        else:
            vendor_info["atlas"] = None
            
        enriched.append(vendor_info)
    
    return enriched


@app.get("/api/atlas/freshness")
async def api_get_freshness():
    """Returns Atlas data freshness report for all companies."""
    try:
        from db.atlas import connect, get_freshness_report
        connect()
        report = get_freshness_report()
        # Convert datetimes to strings
        for category in ["fresh", "stale", "new"]:
            for item in report.get(category, []):
                if item.get("last_scraped"):
                    item["last_scraped"] = item["last_scraped"].isoformat()
        return report
    except Exception as e:
        return {"fresh": [], "stale": [], "new": [], "error": str(e)}


# --- Intelligence Tracker / History ---

@app.get("/api/sessions")
async def api_get_sessions(
    mode: str = None,
    vertical: str = None,
    days: int = 30,
    limit: int = 20,
    offset: int = 0
):
    """
    Return paginated list of court sessions with filters and aggregate stats.
    Used by the Intelligence Tracker page.
    """
    try:
        from db.atlas import connect, get_collection
        from datetime import datetime, timedelta
        connect()
        col = get_collection("court_sessions")
        
        # Build query filter
        query = {}
        if mode:
            query["mode"] = mode
        if vertical:
            query["vertical"] = vertical
        if days and days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query["created_at"] = {"$gte": cutoff}
        
        # Get total count
        total = col.count_documents(query)
        
        # Get paginated sessions
        cursor = col.find(query).sort("created_at", -1).skip(offset).limit(limit)
        
        sessions = []
        for doc in cursor:
            parsed = doc.get("parsed_verdict", {})
            plaintiff = doc.get("plaintiff", {})
            mode_val = doc.get("mode", "buyer")
            
            # Build report_id from the session
            report_id = None
            created = doc.get("created_at")
            if created:
                report_id = f"{mode_val}_report_{created.strftime('%Y%m%d_%H%M%S')}"
            
            session = {
                "id": str(doc["_id"]),
                "mode": mode_val,
                "vertical": doc.get("vertical", "database"),
                "vendors": doc.get("companies", []),
                "winner": parsed.get("overall_winner") if mode_val != "analyst" else None,
                "confidence": None,
                "plaintiff_profile": {
                    "company": plaintiff.get("company_name", ""),
                    "budget": plaintiff.get("budget", ""),
                    "use_case": plaintiff.get("use_case", ""),
                    "priority": plaintiff.get("priority", ""),
                    "team_size": plaintiff.get("team_size", ""),
                } if mode_val != "analyst" else None,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "report_id": report_id,
            }
            
            # Parse confidence
            conf_str = parsed.get("confidence", "")
            if conf_str and conf_str != "N/A":
                import re
                match = re.search(r'(\d+)', str(conf_str))
                if match:
                    session["confidence"] = int(match.group(1))
            
            sessions.append(session)
        
        # Compute aggregate stats USING THE SAME FILTERS
        # Build a filter-aware stats query (same as session query but without pagination)
        stats_query = {}
        if mode:
            stats_query["mode"] = mode
        if vertical:
            stats_query["vertical"] = vertical
        if days and days > 0:
            stats_cutoff = datetime.utcnow() - timedelta(days=days)
            stats_query["created_at"] = {"$gte": stats_cutoff}
        
        month_cutoff = datetime.utcnow() - timedelta(days=30)
        
        total_verdicts = col.count_documents(stats_query)
        
        # "This month" within the filtered set
        month_query = {**stats_query, "created_at": {"$gte": month_cutoff}}
        this_month = col.count_documents(month_query)
        
        # Top winner (filtered)
        winner_match = {**stats_query, "parsed_verdict.overall_winner": {"$exists": True, "$ne": None}}
        pipeline = [
            {"$match": winner_match},
            {"$group": {"_id": "$parsed_verdict.overall_winner", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        top_winner_result = list(col.aggregate(pipeline))
        top_winner = None
        if top_winner_result and total_verdicts > 0:
            tw = top_winner_result[0]
            top_winner = {
                "vendor": tw["_id"],
                "percentage": round(tw["count"] / total_verdicts * 100)
            }
        
        # Average confidence (filtered)
        conf_pipeline = [
            {"$match": {**stats_query, "parsed_verdict.confidence": {"$exists": True}}},
            {"$project": {"conf_str": "$parsed_verdict.confidence"}},
        ]
        conf_docs = list(col.aggregate(conf_pipeline))
        conf_values = []
        for cd in conf_docs:
            import re
            m = re.search(r'(\d+)', str(cd.get("conf_str", "")))
            if m:
                conf_values.append(int(m.group(1)))
        avg_confidence = round(sum(conf_values) / len(conf_values)) if conf_values else 0
        
        return {
            "sessions": sessions,
            "total": total,
            "stats": {
                "total_verdicts": total_verdicts,
                "this_month": this_month,
                "top_winner": top_winner,
                "avg_confidence": avg_confidence
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "sessions": [],
            "total": 0,
            "stats": {
                "total_verdicts": 0,
                "this_month": 0,
                "top_winner": None,
                "avg_confidence": 0
            },
            "error": str(e)
        }


@app.get("/api/sessions/trends")
async def api_get_session_trends(
    mode: str = None,
    vertical: str = None,
    days: int = 30
):
    """
    Return winner distribution for trend visualization.
    """
    try:
        from db.atlas import connect, get_collection
        from datetime import datetime, timedelta
        connect()
        col = get_collection("court_sessions")
        
        query = {}
        if vertical:
            query["vertical"] = vertical
        if days and days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query["created_at"] = {"$gte": cutoff}
        
        # If mode is specified AND it's not analyst, filter to that mode
        # If mode is analyst, there are no winners so return empty
        if mode and mode == "analyst":
            return {
                "vertical": vertical or "all",
                "period_days": days,
                "total_verdicts": 0,
                "distribution": [],
                "insights": ["Analyst mode does not declare winners"]
            }
        elif mode:
            query["mode"] = mode
        else:
            # Exclude analyst (no winners) when no mode filter
            query["mode"] = {"$ne": "analyst"}
        
        query["parsed_verdict.overall_winner"] = {"$exists": True, "$ne": None}
        
        total_verdicts = col.count_documents(query)
        
        # Win distribution
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$parsed_verdict.overall_winner", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        results = list(col.aggregate(pipeline))
        
        distribution = []
        for r in results:
            if r["_id"]:
                pct = round(r["count"] / total_verdicts * 100) if total_verdicts > 0 else 0
                distribution.append({
                    "vendor": r["_id"],
                    "wins": r["count"],
                    "percentage": pct
                })
        
        # Generate simple insights
        insights = []
        if distribution:
            top = distribution[0]
            insights.append(f"{top['vendor']} leads with {top['percentage']}% of verdicts ({top['wins']} wins)")
        
        # Check priority-specific wins
        priority_pipeline = [
            {"$match": {**query, "priority": {"$exists": True}}},
            {"$group": {
                "_id": {"winner": "$parsed_verdict.overall_winner", "priority": "$priority"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        priority_results = list(col.aggregate(priority_pipeline))
        for pr in priority_results:
            if pr["_id"]["winner"] and pr["_id"]["priority"]:
                insights.append(
                    f"{pr['_id']['winner']} wins {pr['count']}x when {pr['_id']['priority']} is top priority"
                )
        
        return {
            "vertical": vertical or "all",
            "period_days": days,
            "total_verdicts": total_verdicts,
            "distribution": distribution,
            "insights": insights[:3]  # cap at 3
        }
    except Exception as e:
        return {
            "vertical": vertical or "all",
            "period_days": days,
            "total_verdicts": 0,
            "distribution": [],
            "insights": [],
            "error": str(e)
        }


# --- Health Check ---

@app.get("/health")
async def health_check():
    return {"status": "online"}

