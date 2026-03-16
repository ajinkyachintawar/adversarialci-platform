"""
Verdict v2
==========
Mode-aware verdict processing and report generation.
Supports: Buyer, Seller, Analyst output formats.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from db.atlas import connect, get_collection
from verticals import get_vertical


# ─── Save to Atlas ──────────────────────────────────────────

def save_verdict(
    verdict: dict,
    parsed: dict,
    round_1: dict,
    round_2: dict,
    round_3: dict,
    mode: str = "buyer"
) -> str:
    """Save verdict to Atlas."""
    connect()
    col = get_collection("court_sessions")
    
    doc = {
        "mode": mode,
        "vertical": verdict.get("vertical", "database"),
        "plaintiff": verdict["plaintiff"],
        "companies": verdict["companies"],
        "challenge": verdict["challenge"],
        "priority": verdict["priority"],
        "deliberation": verdict["deliberation"],
        "parsed_verdict": parsed,
        "round_1": {k: v["content"] for k, v in round_1.items()},
        "round_2": {k: v["content"] for k, v in round_2.items()},
        "round_3": {k: v["content"] for k, v in round_3.items()},
        "created_at": datetime.utcnow()
    }
    
    result = col.insert_one(doc)
    session_id = str(result.inserted_id)
    print(f"  💾 Verdict saved to Atlas — session: {session_id}")
    return session_id


# ─── Confidence Calculation ─────────────────────────────────

def calculate_buyer_confidence(parsed: dict, plaintiff: dict) -> dict:
    """
    Calculate confidence for buyer mode.
    Based on: priority alignment, win margin, data quality.
    """
    winner = parsed.get("overall_winner", "")
    dimensions = parsed.get("dimensions", {})
    
    # Count dimension wins for winner
    dim_wins = sum(1 for d in dimensions.values() 
                   if winner.lower() in d.get("winner", "").lower())
    total_dims = len(dimensions) if dimensions else 1
    
    # Dominance score (how many dimensions won)
    dominance = dim_wins / total_dims
    
    # Priority alignment (did winner win the priority dimension?)
    priority = plaintiff.get("priority", "").lower().replace("-", "_")
    priority_win = False
    if priority in dimensions:
        priority_win = winner.lower() in dimensions[priority].get("winner", "").lower()
    
    # Calculate confidence
    if dominance >= 0.75 and priority_win:
        confidence = 90
        label = "High"
    elif dominance >= 0.6 or priority_win:
        confidence = 75
        label = "Good"
    elif dominance >= 0.5:
        confidence = 60
        label = "Moderate"
    else:
        confidence = 45
        label = "Low"
    
    return {
        "score": confidence,
        "label": label,
        "breakdown": {
            "dimensions_won": f"{dim_wins}/{total_dims}",
            "priority_dimension_won": "Yes" if priority_win else "No",
            "dominance": f"{dominance*100:.0f}%"
        }
    }


# ─── Buyer Report Generator ─────────────────────────────────

def generate_buyer_report(
    verdict: dict,
    parsed: dict,
    session_id: str
) -> str:
    """Generate Buyer-focused recommendation report."""
    
    plaintiff = verdict["plaintiff"]
    companies = verdict["companies"]
    vertical = verdict.get("vertical", "database")
    config = get_vertical(vertical)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    winner = parsed.get("overall_winner", "N/A")
    runner_up = parsed.get("runner_up", "").split("—")[0].strip() if parsed.get("runner_up") else "N/A"
    
    # Calculate confidence
    confidence = calculate_buyer_confidence(parsed, plaintiff)
    
    md = []
    
    # ─── Header ───
    md.append(f"""╔══════════════════════════════════════════════════════════════╗
║              🛒 BUYER RECOMMENDATION REPORT                  ║
║              {plaintiff.get('company_name', 'Unknown'):<43} ║
║              {config['display_name']:<43} ║
║              Generated: {now:<36} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # ─── Bottom Line ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 BOTTOM LINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  🏆 BEST FIT FOR YOU: {winner}")
    md.append(f"")
    md.append(f"  CONFIDENCE: {confidence['score']}% ({confidence['label']})")
    md.append(f"")
    
    if parsed.get("primary_reason"):
        md.append(f"  WHY: {parsed['primary_reason']}")
    md.append("")
    
    # ─── Your Profile ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 YOUR PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Company      : {plaintiff.get('company_name', 'N/A')}")
    md.append(f"  Team         : {plaintiff.get('team_size', 'N/A')}")
    md.append(f"  Budget       : {plaintiff.get('budget', 'N/A')}/month")
    md.append(f"  Use Case     : {plaintiff.get('use_case', 'N/A')}")
    md.append(f"  Scale        : {plaintiff.get('scale', 'N/A')}")
    md.append(f"  Top Priority : {plaintiff.get('priority', 'N/A')}")
    md.append("")
    
    # ─── How Vendors Scored ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 HOW VENDORS SCORED FOR YOUR NEEDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    if parsed.get("dimensions"):
        # Header row
        dims = list(parsed["dimensions"].keys())[:6]  # Top 6 dimensions
        header = "  Vendor".ljust(20)
        for dim in dims:
            dim_short = dim.replace("_", " ").title()[:10]
            header += dim_short.center(12)
        md.append(header)
        md.append("  " + "─" * (18 + 12 * len(dims)))
        
        # Score each company
        for company in companies:
            row = f"  {company}".ljust(20)
            wins = 0
            for dim in dims:
                dim_winner = parsed["dimensions"].get(dim, {}).get("winner", "")
                if company.lower() in dim_winner.lower():
                    row += "✅ WIN".center(12)
                    wins += 1
                else:
                    row += "—".center(12)
            md.append(row)
        md.append("")
        
        # Winner summary
        winner_wins = sum(1 for d in parsed["dimensions"].values() 
                        if winner.lower() in d.get("winner", "").lower())
        md.append(f"  {winner} wins {winner_wins}/{len(dims)} dimensions")
    md.append("")
    
    # ─── Dimension Details ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DIMENSION BREAKDOWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    priority = plaintiff.get("priority", "").lower().replace("-", "_")
    
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            dim_label = dim.replace("_", " ").title()
            is_priority = dim == priority
            marker = "⭐" if is_priority else "•"
            priority_note = " (YOUR TOP PRIORITY)" if is_priority else ""
            
            md.append(f"  {marker} {dim_label}{priority_note}")
            md.append(f"    Winner: {data.get('winner', 'N/A')}")
            md.append(f"    Why: {data.get('reason', 'N/A')}")
            md.append("")
    
    # ─── Tradeoffs ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚖️ TRADEOFFS YOU'RE MAKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # What you get (dimensions winner won)
    md.append(f"  BY CHOOSING {winner.upper()}, YOU GET:")
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            if winner.lower() in data.get("winner", "").lower():
                dim_label = dim.replace("_", " ").title()
                md.append(f"    ✅ {dim_label}: {data.get('reason', '')[:60]}...")
    md.append("")
    
    # What you sacrifice (dimensions winner lost)
    md.append(f"  BUT YOU MAY SACRIFICE:")
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            if winner.lower() not in data.get("winner", "").lower():
                dim_label = dim.replace("_", " ").title()
                dim_winner = data.get("winner", "N/A")
                md.append(f"    ⚠️ {dim_label}: {dim_winner} is stronger here")
    md.append("")
    
    # ─── Runner Up ───
    if runner_up and runner_up != "N/A":
        md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥈 RUNNER UP: WHEN TO RECONSIDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        md.append(f"  {parsed.get('runner_up', '')}")
        md.append("")
        
        if parsed.get("swing_factor"):
            md.append(f"  SWING FACTOR: {parsed['swing_factor']}")
        md.append("")
    
    # ─── Questions to Ask ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❓ QUESTIONS TO ASK BEFORE SIGNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Ask {winner}:")
    
    # Generate relevant questions based on profile
    questions = []
    budget = plaintiff.get("budget", "")
    if budget:
        questions.append(f"\"What's included at the {budget}/mo tier? Any hidden costs?\"")
    
    scale = plaintiff.get("scale", "")
    if scale:
        questions.append(f"\"How does pricing change as we scale to {scale}?\"")
    
    questions.append("\"What's your SLA for uptime and support response time?\"")
    questions.append("\"Can we do a paid pilot before full commitment?\"")
    questions.append("\"What does migration/onboarding support look like?\"")
    
    for i, q in enumerate(questions[:5], 1):
        md.append(f"    {i}. {q}")
    md.append("")
    
    # ─── Confidence Breakdown ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 CONFIDENCE BREAKDOWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Overall: {confidence['score']}% ({confidence['label']})")
    md.append("")
    md.append(f"  Based on:")
    for key, value in confidence["breakdown"].items():
        key_label = key.replace("_", " ").title()
        md.append(f"    • {key_label}: {value}")
    md.append("")
    
    # ─── Next Steps ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 RECOMMENDED NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  1. Request demo/trial from {winner}")
    md.append(f"  2. Run proof-of-concept with your actual workload")
    md.append(f"  3. Validate pricing at your projected scale")
    md.append(f"  4. Check references from similar companies")
    md.append(f"  5. Review contract terms (especially exit clauses)")
    md.append("")
    
    # ─── Footer ───
    md.append(f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report ID: {session_id}
Generated by AdversarialCI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    return "\n".join(md)


# ─── Legacy Report (fallback) ───────────────────────────────

def generate_legacy_report(
    verdict: dict,
    parsed: dict,
    session_id: str
) -> str:
    """Original report format (for backwards compatibility)."""
    plaintiff = verdict["plaintiff"]
    companies = verdict["companies"]
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    md = []
    md.append("# DB WAR ROOM — VERDICT REPORT")
    md.append(f"**Session:** {session_id}")
    md.append(f"**Generated:** {now}")
    md.append("")
    
    # Plaintiff profile
    md.append("## 📋 PLAINTIFF PROFILE")
    md.append("| Field | Value |")
    md.append("|---|---|")
    md.append(f"| Company | {plaintiff.get('company_name', 'N/A')} |")
    md.append(f"| Team Size | {plaintiff.get('team_size', 'N/A')} |")
    md.append(f"| Budget | {plaintiff.get('budget', 'N/A')}/month |")
    md.append(f"| Use Case | {plaintiff.get('use_case', 'N/A')} |")
    md.append(f"| Priority | {plaintiff.get('priority', 'N/A')} |")
    md.append("")
    
    # Verdict
    md.append("## ⚖️ VERDICT")
    md.append(f"### 🏆 WINNER: {parsed.get('overall_winner', 'N/A')}")
    md.append(f"**Confidence:** {parsed.get('confidence', 'N/A')}")
    md.append("")
    
    if parsed.get("primary_reason"):
        md.append(f"**Why:** {parsed['primary_reason']}")
        md.append("")
    
    # Dimensions
    if parsed.get("dimensions"):
        md.append("## 📊 DIMENSION VERDICTS")
        md.append("| Dimension | Winner | Reason |")
        md.append("|---|---|---|")
        for dim, data in parsed["dimensions"].items():
            dim_label = dim.replace("_", " ").title()
            md.append(f"| {dim_label} | {data.get('winner', 'N/A')} | {data.get('reason', 'N/A')} |")
        md.append("")
    
    # Battlecard
    if parsed.get("battlecard"):
        md.append("## 🗡️ BATTLECARD")
        for i, arg in enumerate(parsed["battlecard"], 1):
            md.append(f"{i}. {arg}")
        md.append("")
    
    return "\n".join(md)


# ─── Save Markdown ──────────────────────────────────────────

def save_markdown(content: str, session_id: str, mode: str = "buyer") -> str:
    """Save markdown report to file and MongoDB."""
    from db.atlas import get_collection
    from bson import ObjectId
    
    os.makedirs("outputs/reports", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_id = f"{mode}_report_{timestamp}"
    filename = f"outputs/reports/{report_id}.md"
    
    # Save to file
    with open(filename, "w") as f:
        f.write(content)
    
    # Save to MongoDB
    try:
        col = get_collection("court_sessions")
        if session_id:
            # Use ObjectId for _id matching
            col.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"report_id": report_id, "report_content": content}}
            )
        else:
            # Update most recent session using find_one_and_update (supports sort)
            col.find_one_and_update(
                {},
                {"$set": {"report_id": report_id, "report_content": content}},
                sort=[("created_at", -1)]
            )
    except Exception as e:
        print(f"  ⚠️ Failed to save report to MongoDB: {e}")
    
    print(f"  📄 Report saved: {filename}")
    return filename


# ─── Main Process Function ──────────────────────────────────

def process_verdict(
    verdict: dict,
    parsed: dict,
    round_1: dict,
    round_2: dict,
    round_3: dict,
    mode: str = "buyer"
) -> dict:
    """
    Process verdict and generate mode-specific report.
    
    Args:
        verdict: Full verdict dict from judge
        parsed: Parsed verdict structure
        round_1-3: Court round results
        mode: buyer | seller | analyst
    """
    print("\n📦 VERDICT — Saving results")
    print("─" * 40)
    
    # Save to Atlas
    session_id = save_verdict(
        verdict, parsed, round_1, round_2, round_3, mode
    )
    
    # Generate mode-specific report
    if mode == "buyer":
        md_content = generate_buyer_report(verdict, parsed, session_id)
    elif mode == "seller":
        # Get seller's company from plaintiff (stored during seller mode)
        my_company = verdict.get("my_company") or verdict["companies"][0]
        md_content = generate_seller_report(verdict, parsed, session_id, my_company)
    elif mode == "analyst":
        md_content = generate_analyst_report(verdict, parsed, session_id)
    else:
        md_content = generate_legacy_report(verdict, parsed, session_id)
    
    # Save markdown file
    filename = save_markdown(md_content, session_id, mode)
    
    # Calculate confidence based on mode
    if mode == "buyer":
        confidence_data = calculate_buyer_confidence(parsed, verdict["plaintiff"])
        confidence_display = f"{confidence_data['score']}%"
    elif mode == "seller":
        my_company = verdict.get("my_company") or verdict["companies"][0]
        confidence_data = calculate_seller_confidence(parsed, verdict["plaintiff"], my_company)
        confidence_display = f"{confidence_data['score']}% win probability"
    elif mode == "analyst":
        confidence_data = calculate_analyst_data_quality(verdict, parsed)
        confidence_display = f"{confidence_data['score']}/10 data quality"
    else:
        confidence_display = parsed.get("confidence", "N/A")
    
    return {
        "session_id": session_id,
        "filename": filename,
        "winner": parsed.get("overall_winner"),
        "confidence": confidence_display,
        "mode": mode
    }


if __name__ == "__main__":
    # Test buyer report generation
    test_verdict = {
        "plaintiff": {
            "company_name": "TechStartup",
            "team_size": "5 engineers",
            "budget": "$500",
            "use_case": "RAG pipeline",
            "scale": "10M to 100M vectors",
            "priority": "cost"
        },
        "companies": ["Weaviate", "Pinecone", "pgvector"],
        "challenge": "Test challenge",
        "priority": "cost",
        "vertical": "database",
        "deliberation": "Test deliberation"
    }
    
    test_parsed = {
        "overall_winner": "Weaviate",
        "confidence": "80%",
        "primary_reason": "Best cost-to-performance ratio for your scale",
        "runner_up": "pgvector — would win if you need Postgres compatibility",
        "swing_factor": "If budget increases, Pinecone becomes viable",
        "dimensions": {
            "cost": {"winner": "Weaviate", "reason": "Open source, free self-hosted"},
            "performance": {"winner": "Pinecone", "reason": "Optimized managed service"},
            "scalability": {"winner": "Pinecone", "reason": "Proven at billion scale"},
            "simplicity": {"winner": "Pinecone", "reason": "Best DX"},
            "lock_in_risk": {"winner": "Weaviate", "reason": "Open source, portable"}
        },
        "battlecard": ["Point 1", "Point 2", "Point 3"]
    }
    
    report = generate_buyer_report(test_verdict, test_parsed, "test_session_123")
    print(report)


# ─── Seller Confidence Calculation ──────────────────────────

def calculate_seller_confidence(parsed: dict, plaintiff: dict, my_company: str) -> dict:
    """
    Calculate win probability for seller mode.
    Based on: advantages, exploitable weaknesses, vulnerabilities.
    """
    winner = parsed.get("overall_winner", "")
    dimensions = parsed.get("dimensions", {})
    
    # Count dimensions my company won
    my_wins = sum(1 for d in dimensions.values() 
                  if my_company.lower() in d.get("winner", "").lower())
    total_dims = len(dimensions) if dimensions else 1
    
    # Did I win the priority dimension?
    priority = plaintiff.get("priority", "").lower().replace("-", "_")
    priority_win = False
    if priority in dimensions:
        priority_win = my_company.lower() in dimensions[priority].get("winner", "").lower()
    
    # Am I the overall winner?
    is_winner = my_company.lower() in winner.lower()
    
    # Base probability
    if is_winner:
        if my_wins >= total_dims * 0.7:
            base = 85
        elif my_wins >= total_dims * 0.5:
            base = 70
        else:
            base = 55
    else:
        # I'm not the winner - lower base
        if my_wins >= total_dims * 0.4:
            base = 45
        elif my_wins >= total_dims * 0.25:
            base = 30
        else:
            base = 20
    
    # Adjust for priority alignment
    if priority_win:
        base += 10
    
    # Cap at reasonable bounds
    probability = max(15, min(90, base))
    
    # Label
    if probability >= 70:
        label = "Likely Win"
    elif probability >= 50:
        label = "Competitive"
    elif probability >= 35:
        label = "Uphill Battle"
    else:
        label = "Long Shot"
    
    return {
        "score": probability,
        "label": label,
        "is_favorite": is_winner,
        "breakdown": {
            "dimensions_won": f"{my_wins}/{total_dims}",
            "priority_dimension_won": "Yes" if priority_win else "No",
            "overall_favorite": "Yes" if is_winner else "No"
        }
    }


# ─── Seller Report Generator ────────────────────────────────

def generate_seller_report(
    verdict: dict,
    parsed: dict,
    session_id: str,
    my_company: str
) -> str:
    """Generate Seller-focused battlecard report."""
    
    plaintiff = verdict["plaintiff"]
    companies = verdict["companies"]
    competitors = [c for c in companies if c.lower() != my_company.lower()]
    vertical = verdict.get("vertical", "database")
    config = get_vertical(vertical)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    winner = parsed.get("overall_winner", "N/A")
    
    # Calculate win probability
    win_prob = calculate_seller_confidence(parsed, plaintiff, my_company)
    
    md = []
    
    # ─── Header ───
    md.append(f"""╔══════════════════════════════════════════════════════════════╗
║              🎯 SELLER BATTLECARD                            ║
║              {my_company} vs {', '.join(competitors):<36} ║
║              Deal: {plaintiff.get('company_name', 'Unknown'):<40} ║
║              Generated: {now:<36} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # ─── Bottom Line: Can You Win? ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 BOTTOM LINE: CAN YOU WIN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    md.append(f"  WIN PROBABILITY: {win_prob['score']}% ({win_prob['label']})")
    md.append("")
    
    if win_prob["is_favorite"]:
        md.append(f"  ✅ YOU'RE THE FAVORITE")
        md.append(f"     You won {win_prob['breakdown']['dimensions_won']} dimensions")
        md.append(f"     Focus: Don't lose this deal. Protect your position.")
    else:
        md.append(f"  ⚠️ YOU'RE THE UNDERDOG")
        md.append(f"     {winner} is currently favored")
        md.append(f"     Focus: Find the wedge. Attack their weaknesses.")
    md.append("")
    
    # Why you can/can't win
    priority = plaintiff.get("priority", "cost").lower().replace("-", "_")
    priority_data = parsed.get("dimensions", {}).get(priority, {})
    priority_winner = priority_data.get("winner", "")
    
    md.append("  KEY FACTORS:")
    if my_company.lower() in priority_winner.lower():
        md.append(f"    ✅ You win on {priority.replace('_', ' ')} (prospect's TOP priority)")
    else:
        md.append(f"    ❌ {priority_winner} wins on {priority.replace('_', ' ')} (prospect's TOP priority)")
        md.append(f"       → You MUST reframe the conversation away from {priority.replace('_', ' ')}")
    md.append("")
    
    # ─── Prospect Profile ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 TARGET PROSPECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Company      : {plaintiff.get('company_name', 'N/A')}")
    md.append(f"  Team         : {plaintiff.get('team_size', 'N/A')}")
    md.append(f"  Budget       : {plaintiff.get('budget', 'N/A')}/month")
    md.append(f"  Use Case     : {plaintiff.get('use_case', 'N/A')}")
    md.append(f"  Scale        : {plaintiff.get('scale', 'N/A')}")
    md.append(f"  TOP PRIORITY : {plaintiff.get('priority', 'N/A').upper()}")
    md.append("")
    
    # ─── Your Advantages ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 YOUR ADVANTAGES (Lead with these)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    advantages = []
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            if my_company.lower() in data.get("winner", "").lower():
                dim_label = dim.replace("_", " ").title()
                is_priority = dim == priority
                advantages.append({
                    "dimension": dim_label,
                    "reason": data.get("reason", ""),
                    "is_priority": is_priority
                })
    
    # Sort priority first
    advantages.sort(key=lambda x: (not x["is_priority"], x["dimension"]))
    
    if advantages:
        for i, adv in enumerate(advantages, 1):
            priority_marker = " ⭐ (THEIR TOP PRIORITY)" if adv["is_priority"] else ""
            md.append(f"  {i}. {adv['dimension'].upper()}{priority_marker}")
            md.append(f"     \"{adv['reason'][:100]}...\"")
            md.append(f"     → Lead with this when discussing {adv['dimension'].lower()}")
            md.append("")
    else:
        md.append("  ⚠️ No clear dimension advantages found")
        md.append("     → Focus on relationship, service, and deal terms")
        md.append("")
    
    # ─── Your Vulnerabilities ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ YOUR VULNERABILITIES (Prepare for these)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    vulnerabilities = []
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            if my_company.lower() not in data.get("winner", "").lower():
                dim_label = dim.replace("_", " ").title()
                dim_winner = data.get("winner", "Competitor")
                is_priority = dim == priority
                vulnerabilities.append({
                    "dimension": dim_label,
                    "winner": dim_winner,
                    "reason": data.get("reason", ""),
                    "is_priority": is_priority
                })
    
    # Sort priority first (most dangerous)
    vulnerabilities.sort(key=lambda x: (not x["is_priority"], x["dimension"]))
    
    if vulnerabilities:
        for i, vuln in enumerate(vulnerabilities, 1):
            danger = "🚨 CRITICAL" if vuln["is_priority"] else "⚠️"
            md.append(f"  {i}. {danger} {vuln['dimension'].upper()}")
            md.append(f"     {vuln['winner']} wins here: \"{vuln['reason'][:80]}...\"")
            
            # Generate counter-strategy
            if vuln["is_priority"]:
                md.append(f"     → REFRAME: Shift conversation to dimensions you win")
                md.append(f"     → NEUTRALIZE: \"While {vuln['dimension'].lower()} matters, let me show you the TCO picture...\"")
            else:
                md.append(f"     → ACKNOWLEDGE: Don't deny it, but minimize importance")
            md.append("")
    else:
        md.append("  ✅ No major vulnerabilities detected")
        md.append("")
    
    # ─── Landmines ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💣 LANDMINES (Neutralize competitor claims)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Generate landmines based on competitor advantages
    for comp in competitors:
        comp_wins = []
        if parsed.get("dimensions"):
            for dim, data in parsed["dimensions"].items():
                if comp.lower() in data.get("winner", "").lower():
                    comp_wins.append({
                        "dimension": dim.replace("_", " ").title(),
                        "reason": data.get("reason", "")
                    })
        
        if comp_wins:
            md.append(f"  IF {comp.upper()} SAYS:")
            for win in comp_wins[:2]:  # Top 2 per competitor
                md.append(f"    \"{win['reason'][:60]}...\"")
            md.append(f"")
            md.append(f"  YOU SAY:")
            md.append(f"    \"That's one perspective. But for {plaintiff.get('company_name', 'your')}'s")
            md.append(f"     specific situation — {plaintiff.get('use_case', 'your use case')} at")
            md.append(f"     {plaintiff.get('scale', 'your scale')} — let me show you why that")
            md.append(f"     comparison doesn't tell the full story...\"")
            md.append("")
    
    # ─── Talk Track ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗣️ TALK TRACK FOR THIS DEAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Opening
    md.append("  OPENING:")
    if win_prob["is_favorite"]:
        md.append(f"    \"Based on what you've shared about {plaintiff.get('company_name', 'your company')} —")
        md.append(f"     particularly your focus on {priority.replace('_', ' ')} — I'm confident")
        md.append(f"     we're the strongest fit. Let me show you why...\"")
    else:
        md.append(f"    \"I know you're also looking at {winner}. Before you decide,")
        md.append(f"     I want to make sure you have the full picture on")
        md.append(f"     what matters most for {plaintiff.get('use_case', 'your use case')}...\"")
    md.append("")
    
    # Key points
    md.append("  KEY POINTS TO MAKE:")
    if advantages:
        for i, adv in enumerate(advantages[:3], 1):
            md.append(f"    {i}. {adv['dimension']}: {adv['reason'][:60]}...")
    md.append("")
    
    # Close
    md.append("  CLOSE:")
    md.append(f"    \"Given your {plaintiff.get('budget', 'budget')} budget and timeline,")
    md.append(f"     I'd recommend a [pilot/POC] focused on {plaintiff.get('use_case', 'your core use case')}.")
    md.append(f"     Can we schedule that for next week?\"")
    md.append("")
    
    # ─── Do Not Say ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 DO NOT SAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    md.append(f"  • Don't trash {competitors[0]} directly — it backfires")
    md.append(f"  • Don't promise features you don't have")
    md.append(f"  • Don't get defensive about {vulnerabilities[0]['dimension'] if vulnerabilities else 'weaknesses'}")
    md.append(f"  • Don't quote pricing without their specific requirements")
    md.append(f"  • Don't oversell — under-promise and over-deliver")
    md.append("")
    
    # ─── Objection Handling ───
    if parsed.get("watch_out_for"):
        md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ OBJECTION HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        for i, obj in enumerate(parsed["watch_out_for"], 1):
            md.append(f"  {i}. {obj}")
            md.append("")
    
    # ─── Next Steps ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 NEXT STEPS FOR THIS DEAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append("  IMMEDIATE:")
    md.append(f"    [ ] Send comparison document highlighting your strengths")
    md.append(f"    [ ] Schedule technical deep-dive with their team")
    md.append(f"    [ ] Prepare demo tailored to {plaintiff.get('use_case', 'their use case')}")
    md.append("")
    md.append("  THIS WEEK:")
    md.append(f"    [ ] Get them into a POC/trial")
    md.append(f"    [ ] Identify the economic buyer and their concerns")
    md.append(f"    [ ] Prep reference customer in similar industry")
    md.append("")
    md.append("  BEFORE DECISION:")
    md.append(f"    [ ] Confirm POC success criteria upfront")
    md.append(f"    [ ] Address any security/compliance requirements")
    md.append(f"    [ ] Align on pricing and contract terms")
    md.append("")
    
    # ─── Summary Box ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 DEAL SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Win Probability    : {win_prob['score']}% ({win_prob['label']})")
    md.append(f"  You Are            : {'Favorite ✅' if win_prob['is_favorite'] else 'Underdog ⚠️'}")
    md.append(f"  Dimensions Won     : {win_prob['breakdown']['dimensions_won']}")
    md.append(f"  Priority Dim Won   : {win_prob['breakdown']['priority_dimension_won']}")
    md.append(f"  Main Competitor    : {winner if not win_prob['is_favorite'] else competitors[0] if competitors else 'N/A'}")
    md.append("")
    
    # ─── Footer ───
    md.append(f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report ID: {session_id}
Generated by AdversarialCI — Seller Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    return "\n".join(md)


# ─── Analyst Data Quality Calculation ───────────────────────

def calculate_analyst_confidence(verdict: dict, parsed: dict) -> dict:
    """
    Calculate data quality score for analyst mode.
    Based on: source coverage, data freshness, sentiment balance.
    """
    companies = verdict.get("companies", [])
    dimensions = parsed.get("dimensions", {})
    
    # Dimension coverage
    expected_dims = 8
    actual_dims = len(dimensions)
    dim_coverage = min(actual_dims / expected_dims, 1.0)
    
    # Company coverage
    company_coverage = 1.0
    
    # Balance check
    unique_winners = 0
    if dimensions:
        winners = [d.get("winner", "") for d in dimensions.values()]
        unique_winners = len(set(w.lower() for w in winners if w))
        balance = min(unique_winners / len(companies), 1.0) if companies else 0.5
    else:
        balance = 0.5
    
    # Calculate quality
    quality = (dim_coverage * 0.4 + company_coverage * 0.3 + balance * 0.3) * 10
    
    if quality >= 8:
        label = "High Quality"
    elif quality >= 6:
        label = "Good Quality"
    elif quality >= 4:
        label = "Moderate Quality"
    else:
        label = "Limited Data"
    
    return {
        "score": round(quality, 1),
        "max": 10,
        "label": label,
        "breakdown": {
            "dimension_coverage": f"{actual_dims}/{expected_dims}",
            "company_coverage": f"{len(companies)}/{len(companies)}",
            "winner_diversity": f"{unique_winners if dimensions else 0} different winners"
        }
    }


def generate_analyst_report(verdict: dict, parsed: dict, session_id: str) -> str:
    """Generate Analyst-focused objective comparison report."""
    
    plaintiff = verdict.get("plaintiff", {})
    companies = verdict["companies"]
    vertical = verdict.get("vertical", "database")
    config = get_vertical(vertical)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    quality = calculate_analyst_confidence(verdict, parsed)
    
    md = []
    
    # Header
    md.append(f"{'='*65}")
    md.append(f"              MARKET ANALYSIS REPORT")
    md.append(f"              {config['display_name']}")
    md.append(f"              {', '.join(companies)}")
    md.append(f"              Generated: {now}")
    md.append(f"{'='*65}")
    md.append("")
    
    # Executive Summary
    md.append("## EXECUTIVE SUMMARY")
    md.append("-" * 40)
    
    win_counts = {c: 0 for c in companies}
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            winner = data.get("winner", "")
            for c in companies:
                if c.lower() in winner.lower():
                    win_counts[c] += 1
    
    total_dims = len(parsed.get("dimensions", {}))
    
    md.append(f"Vendors Analyzed: {len(companies)}")
    md.append(f"Dimensions Evaluated: {total_dims}")
    md.append(f"Data Quality: {quality['score']}/{quality['max']} ({quality['label']})")
    md.append("")
    
    if win_counts:
        leader = max(win_counts, key=win_counts.get)
        leader_wins = win_counts[leader]
        md.append(f"KEY FINDING: {leader} leads with {leader_wins}/{total_dims} dimension wins,")
        md.append("but no single vendor dominates all categories.")
    md.append("")
    md.append("NOTE: This is an objective analysis. No winner is declared.")
    md.append("Choice depends on specific requirements and priorities.")
    md.append("")
    
    # Comparison Matrix
    md.append("## COMPARISON MATRIX")
    md.append("-" * 40)
    
    if parsed.get("dimensions"):
        # Header
        header = "Dimension".ljust(20)
        for c in companies:
            header += c[:12].center(14)
        md.append(header)
        md.append("-" * (20 + 14 * len(companies)))
        
        for dim, data in parsed["dimensions"].items():
            dim_label = dim.replace("_", " ").title()[:18]
            row = dim_label.ljust(20)
            dim_winner = data.get("winner", "")
            
            for c in companies:
                if c.lower() in dim_winner.lower():
                    row += "WIN".center(14)
                else:
                    row += "-".center(14)
            md.append(row)
        
        md.append("-" * (20 + 14 * len(companies)))
        total_row = "TOTAL WINS".ljust(20)
        for c in companies:
            total_row += str(win_counts.get(c, 0)).center(14)
        md.append(total_row)
    md.append("")
    
    # Strengths & Weaknesses
    md.append("## STRENGTHS & WEAKNESSES BY VENDOR")
    md.append("-" * 40)
    
    for company in companies:
        md.append(f"\n### {company.upper()}")
        
        strengths = []
        weaknesses = []
        
        if parsed.get("dimensions"):
            for dim, data in parsed["dimensions"].items():
                dim_label = dim.replace("_", " ").title()
                if company.lower() in data.get("winner", "").lower():
                    reason = data.get("reason", "")[:60]
                    strengths.append(f"{dim_label}: {reason}")
                else:
                    winner = data.get("winner", "Other")
                    weaknesses.append(f"{dim_label}: {winner} stronger")
        
        md.append("Strengths:")
        if strengths:
            for s in strengths[:4]:
                md.append(f"  + {s}")
        else:
            md.append("  (No clear dimension advantages)")
        
        md.append("Weaknesses:")
        if weaknesses:
            for w in weaknesses[:4]:
                md.append(f"  - {w}")
        else:
            md.append("  (No major weaknesses)")
    md.append("")
    
    # Best Fit Scenarios
    md.append("## BEST FIT SCENARIOS")
    md.append("-" * 40)
    
    for company in companies:
        md.append(f"\nCHOOSE {company.upper()} IF:")
        
        company_strengths = []
        if parsed.get("dimensions"):
            for dim, data in parsed["dimensions"].items():
                if company.lower() in data.get("winner", "").lower():
                    company_strengths.append(dim.replace("_", " "))
        
        if company_strengths:
            md.append(f"  * Your top priority is: {', '.join(company_strengths[:2])}")
        
        if "cost" in [s.lower() for s in company_strengths]:
            md.append("  * You are budget-constrained")
        if "performance" in [s.lower() for s in company_strengths]:
            md.append("  * Raw performance is critical")
        if "simplicity" in [s.lower() for s in company_strengths]:
            md.append("  * You have a small team, need easy ops")
        if "compliance" in [s.lower() for s in company_strengths]:
            md.append("  * You have strict compliance requirements")
        if not company_strengths:
            md.append("  * You value relationship/support over features")
    md.append("")
    
    # Dimension Details
    md.append("## DETAILED DIMENSION ANALYSIS")
    md.append("-" * 40)
    
    if parsed.get("dimensions"):
        for dim, data in parsed["dimensions"].items():
            dim_label = dim.replace("_", " ").title()
            md.append(f"\n{dim_label}")
            md.append(f"  Leader: {data.get('winner', 'N/A')}")
            md.append(f"  Reason: {data.get('reason', 'N/A')}")
    md.append("")
    
    # Data Quality
    md.append("## DATA QUALITY & METHODOLOGY")
    md.append("-" * 40)
    md.append(f"Analysis Confidence: {quality['score']}/{quality['max']} ({quality['label']})")
    md.append("")
    md.append("Methodology:")
    md.append("  * Data from: pricing pages, HN, GitHub, blogs, migrations")
    md.append("  * Arguments stress-tested through adversarial debate")
    md.append("  * Verdicts based on evidence weight and source reliability")
    md.append("")
    md.append("Breakdown:")
    for key, value in quality["breakdown"].items():
        md.append(f"  * {key.replace('_', ' ').title()}: {value}")
    md.append("")
    md.append("Caveats:")
    md.append("  * Analysis based on publicly available information")
    md.append("  * Pricing may have changed since data collection")
    md.append("  * Enterprise pricing not included")
    md.append("")
    
    # How to Use
    md.append("## HOW TO USE THIS REPORT")
    md.append("-" * 40)
    md.append("1. Identify your top 2-3 priority dimensions")
    md.append("2. See which vendor leads in those dimensions")
    md.append("3. Review tradeoffs with that choice")
    md.append("4. Validate with your own POC/testing")
    md.append("")
    md.append("This report does NOT declare a winner.")
    md.append("The right choice depends on YOUR requirements.")
    md.append("")
    
    # Footer
    md.append("=" * 65)
    md.append(f"Report ID: {session_id}")
    md.append("Generated by AdversarialCI - Analyst Mode")
    md.append("=" * 65)
    
    return "\n".join(md)


# ─── Analyst Confidence (Data Quality) ──────────────────────

def calculate_analyst_confidence(parsed: dict, companies: list) -> dict:
    """
    Calculate data quality score for analyst mode.
    No win probability — just how reliable is this analysis.
    """
    dimensions = parsed.get("dimensions", {})
    
    # Check dimension coverage
    expected_dims = 8  # Standard dimension count
    actual_dims = len(dimensions)
    coverage = min(actual_dims / expected_dims, 1.0)
    
    # Check if all companies have data
    companies_with_wins = set()
    for dim, data in dimensions.items():
        winner = data.get("winner", "")
        for company in companies:
            if company.lower() in winner.lower():
                companies_with_wins.add(company)
    
    company_coverage = len(companies_with_wins) / len(companies) if companies else 0
    
    # Check reason quality (rough heuristic: longer = better)
    reason_lengths = [len(data.get("reason", "")) for data in dimensions.values()]
    avg_reason_len = sum(reason_lengths) / len(reason_lengths) if reason_lengths else 0
    reason_quality = min(avg_reason_len / 100, 1.0)  # 100 chars = good
    
    # Overall quality score (1-10)
    quality_score = (coverage * 0.4 + company_coverage * 0.4 + reason_quality * 0.2) * 10
    quality_score = round(quality_score, 1)
    
    if quality_score >= 8:
        label = "High"
    elif quality_score >= 6:
        label = "Good"
    elif quality_score >= 4:
        label = "Moderate"
    else:
        label = "Limited"
    
    return {
        "score": quality_score,
        "max": 10,
        "label": label,
        "breakdown": {
            "dimension_coverage": f"{actual_dims}/{expected_dims}",
            "company_coverage": f"{len(companies_with_wins)}/{len(companies)}",
            "reason_quality": f"{reason_quality*100:.0f}%"
        }
    }


# ─── Analyst Report Generator ───────────────────────────────

def generate_analyst_report(
    verdict: dict,
    parsed: dict,
    session_id: str
) -> str:
    """Generate Analyst-focused objective comparison report."""
    
    plaintiff = verdict.get("plaintiff", {})
    companies = verdict["companies"]
    vertical = verdict.get("vertical", "database")
    config = get_vertical(vertical)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    dimensions = parsed.get("dimensions", {})
    
    # Calculate data quality
    data_quality = calculate_analyst_confidence(parsed, companies)
    
    md = []
    
    # ─── Header ───
    md.append(f"""╔══════════════════════════════════════════════════════════════╗
║              📊 MARKET ANALYSIS REPORT                       ║
║              {config['display_name']:<43} ║
║              {', '.join(companies):<43} ║
║              Generated: {now:<36} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # ─── Executive Summary ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Count wins per company
    win_counts = {company: 0 for company in companies}
    for dim, data in dimensions.items():
        winner = data.get("winner", "")
        for company in companies:
            if company.lower() in winner.lower():
                win_counts[company] += 1
    
    # Sort by wins
    sorted_companies = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
    
    md.append(f"  Vendors Analyzed: {len(companies)}")
    md.append(f"  Dimensions Evaluated: {len(dimensions)}")
    md.append("")
    md.append("  DIMENSION WINS:")
    for company, wins in sorted_companies:
        bar = "█" * wins + "░" * (len(dimensions) - wins)
        md.append(f"    {company:<20} {bar} {wins}/{len(dimensions)}")
    md.append("")
    md.append("  ⚠️ NOTE: No single winner declared. Choice depends on priorities.")
    md.append("")
    
    # ─── Comparison Matrix ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 COMPARISON MATRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Build matrix header
    col_width = max(15, max(len(c) for c in companies) + 2)
    header = "  Dimension".ljust(20)
    for company in companies:
        header += company.center(col_width)
    md.append(header)
    md.append("  " + "─" * (18 + col_width * len(companies)))
    
    # Build matrix rows
    for dim, data in dimensions.items():
        dim_label = dim.replace("_", " ").title()
        row = f"  {dim_label}".ljust(20)
        winner = data.get("winner", "")
        
        for company in companies:
            if company.lower() in winner.lower():
                cell = "✅ WIN"
            else:
                cell = "—"
            row += cell.center(col_width)
        md.append(row)
    
    # Total row
    md.append("  " + "─" * (18 + col_width * len(companies)))
    total_row = "  TOTAL WINS".ljust(20)
    for company in companies:
        total_row += str(win_counts[company]).center(col_width)
    md.append(total_row)
    md.append("")
    
    # ─── Strengths & Weaknesses ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 STRENGTHS & WEAKNESSES BY VENDOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for company in companies:
        md.append(f"  ┌─ {company.upper()}")
        md.append(f"  │")
        
        # Strengths (dimensions won)
        strengths = []
        weaknesses = []
        for dim, data in dimensions.items():
            dim_label = dim.replace("_", " ").title()
            if company.lower() in data.get("winner", "").lower():
                strengths.append(f"{dim_label}: {data.get('reason', '')[:50]}...")
            else:
                winner = data.get("winner", "Others")
                weaknesses.append(f"{dim_label}: {winner} stronger")
        
        md.append(f"  │  ✅ Strengths:")
        if strengths:
            for s in strengths[:4]:
                md.append(f"  │     • {s}")
        else:
            md.append(f"  │     • No clear strengths identified")
        
        md.append(f"  │")
        md.append(f"  │  ⚠️ Weaknesses:")
        if weaknesses:
            for w in weaknesses[:4]:
                md.append(f"  │     • {w}")
        else:
            md.append(f"  │     • No clear weaknesses identified")
        
        md.append(f"  │")
        md.append(f"  └─────────────────────────────────────────────────────")
        md.append("")
    
    # ─── Dimension Details ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DIMENSION ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for dim, data in dimensions.items():
        dim_label = dim.replace("_", " ").upper()
        winner = data.get("winner", "N/A")
        reason = data.get("reason", "No details available")
        
        md.append(f"  {dim_label}")
        md.append(f"  Leader: {winner}")
        md.append(f"  Analysis: {reason}")
        md.append("")
    
    # ─── Best Fit Scenarios ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 BEST FIT SCENARIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for company in companies:
        # Find what this company wins on
        wins_on = []
        for dim, data in dimensions.items():
            if company.lower() in data.get("winner", "").lower():
                wins_on.append(dim.replace("_", " "))
        
        md.append(f"  CHOOSE {company.upper()} IF:")
        if wins_on:
            for win in wins_on[:3]:
                md.append(f"    • {win.title()} is your top priority")
            
            # Add contextual recommendations
            if "cost" in [w.lower() for w in wins_on]:
                md.append(f"    • You're a startup or have budget constraints")
            if "performance" in [w.lower() for w in wins_on]:
                md.append(f"    • You need maximum throughput/low latency")
            if "simplicity" in [w.lower() for w in wins_on]:
                md.append(f"    • You have a small team without dedicated ops")
            if "compliance" in [w.lower() for w in wins_on]:
                md.append(f"    • You have strict regulatory requirements")
            if "lock" in " ".join(wins_on).lower():
                md.append(f"    • You want to avoid vendor dependency")
        else:
            md.append(f"    • You have existing relationship/expertise")
            md.append(f"    • Specific features not covered in this analysis")
        md.append("")
    
    # ─── Key Tradeoffs ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚖️ KEY TRADEOFFS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Find opposing winners for common tradeoffs
    tradeoff_pairs = [
        ("cost", "performance"),
        ("simplicity", "customization"),
        ("cost", "support"),
        ("simplicity", "scalability")
    ]
    
    for dim1, dim2 in tradeoff_pairs:
        if dim1 in dimensions and dim2 in dimensions:
            winner1 = dimensions[dim1].get("winner", "?")
            winner2 = dimensions[dim2].get("winner", "?")
            if winner1.lower() != winner2.lower():
                dim1_label = dim1.replace("_", " ").title()
                dim2_label = dim2.replace("_", " ").title()
                md.append(f"  {dim1_label.upper()} vs {dim2_label.upper()}:")
                md.append(f"    {winner1} leads on {dim1_label}")
                md.append(f"    {winner2} leads on {dim2_label}")
                md.append("")
    
    # ─── Data Quality ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DATA QUALITY ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append(f"  Analysis Quality: {data_quality['score']}/{data_quality['max']} ({data_quality['label']})")
    md.append("")
    md.append("  Based on:")
    for key, value in data_quality["breakdown"].items():
        key_label = key.replace("_", " ").title()
        md.append(f"    • {key_label}: {value}")
    md.append("")
    md.append("  CAVEATS:")
    md.append("    • Analysis based on publicly available information")
    md.append("    • Pricing and features may have changed since data collection")
    md.append("    • Your specific use case may yield different results")
    md.append("    • Recommend validating with vendor-provided benchmarks")
    md.append("")
    
    # ─── Methodology ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 METHODOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append("  Data Sources:")
    md.append("    • Official vendor websites and documentation")
    md.append("    • Hacker News discussions (2024-2025)")
    md.append("    • GitHub issues and activity")
    md.append("    • Migration stories and case studies")
    md.append("    • Independent benchmarks and reviews")
    md.append("")
    md.append("  Analysis Process:")
    md.append("    1. Automated data collection from multiple sources")
    md.append("    2. Adversarial evaluation (advocates argue each position)")
    md.append("    3. Neutral synthesis of arguments")
    md.append("    4. Dimension-by-dimension winner determination")
    md.append("")
    
    # ─── Footer ───
    md.append(f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report ID: {session_id}
Generated by AdversarialCI — Analyst Mode

NOTE: This is an objective analysis with no single winner declared.
The best choice depends on your specific priorities and constraints.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    return "\n".join(md)


# ─── Analyst Report Generator ───────────────────────────────

def calculate_analyst_data_quality(verdict: dict, parsed: dict) -> dict:
    """
    Calculate data quality score for analyst mode.
    No winner confidence — just data reliability.
    """
    companies = verdict.get("companies", [])
    dimensions = parsed.get("dimensions", {})
    
    # Dimension coverage (do we have verdicts for all expected dims?)
    expected_dims = 8  # Typical vertical has ~8 dimensions
    actual_dims = len(dimensions)
    coverage = min(actual_dims / expected_dims, 1.0)
    
    # Reasoning quality (do dimensions have reasons?)
    dims_with_reasons = sum(1 for d in dimensions.values() 
                           if d.get("reason") and len(d.get("reason", "")) > 20)
    reasoning = dims_with_reasons / actual_dims if actual_dims > 0 else 0
    
    # Company coverage (all companies evaluated?)
    companies_mentioned = set()
    for d in dimensions.values():
        winner = d.get("winner", "").lower()
        for c in companies:
            if c.lower() in winner:
                companies_mentioned.add(c.lower())
    company_coverage = len(companies_mentioned) / len(companies) if companies else 0
    
    # Overall quality score (1-10)
    quality = round((coverage * 0.4 + reasoning * 0.3 + company_coverage * 0.3) * 10, 1)
    
    if quality >= 8:
        label = "High"
    elif quality >= 6:
        label = "Good"
    elif quality >= 4:
        label = "Moderate"
    else:
        label = "Limited"
    
    return {
        "score": quality,
        "max": 10,
        "label": label,
        "breakdown": {
            "dimension_coverage": f"{actual_dims}/{expected_dims}",
            "reasoning_quality": f"{dims_with_reasons}/{actual_dims} with detailed reasons",
            "company_coverage": f"{len(companies_mentioned)}/{len(companies)} companies evaluated"
        }
    }


def generate_analyst_report(
    verdict: dict,
    parsed: dict,
    session_id: str
) -> str:
    """Generate Analyst-focused objective comparison report."""
    
    plaintiff = verdict.get("plaintiff", {})
    companies = verdict["companies"]
    vertical = verdict.get("vertical", "database")
    config = get_vertical(vertical)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    dimensions = parsed.get("dimensions", {})
    
    # Calculate data quality
    data_quality = calculate_analyst_data_quality(verdict, parsed)
    
    md = []
    
    # ─── Header ───
    md.append(f"""╔══════════════════════════════════════════════════════════════╗
║              📊 MARKET ANALYSIS REPORT                       ║
║              {config['display_name']:<43} ║
║              {' vs '.join(companies):<43} ║
║              Generated: {now:<36} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # ─── Executive Summary ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Count wins per company
    win_counts = {c: 0 for c in companies}
    for dim_data in dimensions.values():
        winner = dim_data.get("winner", "")
        for c in companies:
            if c.lower() in winner.lower():
                win_counts[c] += 1
                break
    
    # Sort by wins
    sorted_companies = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
    
    md.append("  This analysis compares vendors across multiple dimensions.")
    md.append("  No single winner is declared — choice depends on priorities.")
    md.append("")
    md.append("  DIMENSION WINS:")
    for company, wins in sorted_companies:
        bar = "█" * wins + "░" * (len(dimensions) - wins)
        md.append(f"    {company:<20} {bar} {wins}/{len(dimensions)}")
    md.append("")
    
    # ─── Comparison Matrix ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 COMPARISON MATRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Header row
    header = "  Dimension".ljust(22)
    for company in companies:
        header += company[:12].center(14)
    md.append(header)
    md.append("  " + "─" * (20 + 14 * len(companies)))
    
    # Dimension rows
    for dim, data in dimensions.items():
        dim_label = dim.replace("_", " ").title()
        row = f"  {dim_label}".ljust(22)
        
        winner = data.get("winner", "").lower()
        for company in companies:
            if company.lower() in winner:
                row += "✅ WINS".center(14)
            else:
                row += "—".center(14)
        md.append(row)
    
    md.append("  " + "─" * (20 + 14 * len(companies)))
    
    # Total row
    total_row = "  TOTAL WINS".ljust(22)
    for company in companies:
        total_row += str(win_counts[company]).center(14)
    md.append(total_row)
    md.append("")
    
    # ─── Detailed Dimension Analysis ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DIMENSION ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for dim, data in dimensions.items():
        dim_label = dim.replace("_", " ").upper()
        winner = data.get("winner", "N/A")
        reason = data.get("reason", "No detailed analysis available")
        
        md.append(f"  ▸ {dim_label}")
        md.append(f"    Leader: {winner}")
        md.append(f"    Analysis: {reason}")
        md.append("")
    
    # ─── Strengths & Weaknesses ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 STRENGTHS & WEAKNESSES BY VENDOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for company in companies:
        md.append(f"  ┌─ {company.upper()}")
        md.append(f"  │")
        
        # Strengths (dimensions won)
        strengths = []
        weaknesses = []
        for dim, data in dimensions.items():
            winner = data.get("winner", "").lower()
            dim_label = dim.replace("_", " ").title()
            if company.lower() in winner:
                strengths.append(dim_label)
            else:
                weaknesses.append(dim_label)
        
        md.append(f"  │  Strengths:")
        if strengths:
            for s in strengths:
                md.append(f"  │    ✅ {s}")
        else:
            md.append(f"  │    (none in this comparison)")
        
        md.append(f"  │")
        md.append(f"  │  Weaknesses:")
        if weaknesses:
            for w in weaknesses:
                md.append(f"  │    ⚠️ {w}")
        else:
            md.append(f"  │    (none identified)")
        
        md.append(f"  │")
        md.append(f"  └────────────────────────────────────")
        md.append("")
    
    # ─── Best Fit Scenarios ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 BEST FIT SCENARIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    for company in companies:
        # Find dimensions this company won
        won_dims = []
        for dim, data in dimensions.items():
            if company.lower() in data.get("winner", "").lower():
                won_dims.append(dim.replace("_", " "))
        
        md.append(f"  CHOOSE {company.upper()} IF:")
        if won_dims:
            md.append(f"    • Your top priority is: {', '.join(won_dims[:3])}")
            
            # Generate scenario based on wins
            if "cost" in [d.lower() for d in won_dims]:
                md.append(f"    • Budget is constrained")
            if "performance" in [d.lower() for d in won_dims]:
                md.append(f"    • Speed and latency are critical")
            if "simplicity" in [d.lower() for d in won_dims]:
                md.append(f"    • Team has limited ops capacity")
            if "compliance" in [d.lower() for d in won_dims]:
                md.append(f"    • Regulatory requirements are strict")
            if "scalability" in [d.lower() for d in won_dims]:
                md.append(f"    • Expecting significant growth")
        else:
            md.append(f"    • You have specific requirements not covered in this analysis")
        md.append("")
    
    # ─── Key Tradeoffs ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚖️ KEY TRADEOFFS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Find contrasting dimensions
    dim_list = list(dimensions.keys())
    tradeoffs_shown = 0
    
    for i, dim1 in enumerate(dim_list):
        for dim2 in dim_list[i+1:]:
            winner1 = dimensions[dim1].get("winner", "").lower()
            winner2 = dimensions[dim2].get("winner", "").lower()
            
            # Find if different companies win
            company1 = None
            company2 = None
            for c in companies:
                if c.lower() in winner1:
                    company1 = c
                if c.lower() in winner2:
                    company2 = c
            
            if company1 and company2 and company1 != company2 and tradeoffs_shown < 3:
                dim1_label = dim1.replace("_", " ").upper()
                dim2_label = dim2.replace("_", " ").upper()
                md.append(f"  {dim1_label} vs {dim2_label}:")
                md.append(f"    {company1} leads on {dim1_label.lower()}")
                md.append(f"    {company2} leads on {dim2_label.lower()}")
                md.append(f"    → Choose based on which matters more to you")
                md.append("")
                tradeoffs_shown += 1
    
    if tradeoffs_shown == 0:
        md.append("  No significant tradeoffs identified — one vendor may dominate.")
        md.append("")
    
    # ─── Data Quality ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DATA QUALITY NOTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    md.append(f"  ANALYSIS QUALITY: {data_quality['score']}/{data_quality['max']} ({data_quality['label']})")
    md.append("")
    md.append("  Based on:")
    for key, value in data_quality["breakdown"].items():
        key_label = key.replace("_", " ").title()
        md.append(f"    • {key_label}: {value}")
    md.append("")
    md.append("  CAVEATS:")
    md.append("    • Analysis based on publicly available information")
    md.append("    • Pricing and features may have changed since data collection")
    md.append("    • Recommend verifying critical facts with vendors directly")
    md.append("")
    
    # ─── Methodology ───
    md.append("""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 METHODOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    md.append("  This analysis was generated using AdversarialCI:")
    md.append("")
    md.append("  1. DATA COLLECTION")
    md.append("     Sources: Pricing pages, HN discussions, GitHub issues,")
    md.append("     official blogs, migration stories, user complaints")
    md.append("")
    md.append("  2. ADVERSARIAL DEBATE")
    md.append("     AI advocates argued for each vendor's strengths")
    md.append("     Cross-examination stress-tested claims")
    md.append("")
    md.append("  3. SYNTHESIS")
    md.append("     Neutral analysis synthesized debate results")
    md.append("     No predetermined winner — data-driven conclusions")
    md.append("")
    
    # ─── Footer ───
    md.append(f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report ID: {session_id}
Generated by AdversarialCI — Analyst Mode
This report is for informational purposes only.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    return "\n".join(md)