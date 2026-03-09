"""
Sales Copilot - Mode 4: Chat-based meeting prep

Modified to use vendor_onboarding for inline new vendor registration.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from db.atlas import connect, get_collection
from config import GROQ_API_KEY
from vendor_onboarding import process_vendors

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_gemini_chat(messages: list, temperature: float = 0.3) -> str:
    """Call Groq API for chat completion"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 600,
        }
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  ⚠️  Groq error: {e}")
        return f"ERROR: {e}"


def load_company_intelligence(company: str) -> str:
    """Load verified research data from Atlas"""
    connect()
    col = get_collection("research_data")
    docs = list(col.find({
        "company": company,
        "verified": True
    }, {"_id": 0}))
    
    if not docs:
        return f"No data available for {company}."
    
    SOURCE_PRIORITY = {
        "pricing_scrape": 1.0,
        "github": 0.9,
        "migration_tavily": 0.9,
        "complaint_tavily": 0.8,
        "hn_2024": 0.8,
        "hn_2025": 0.8,
        "hn": 0.7,
        "blog_rss": 0.7,
        "tavily": 0.6
    }
    
    all_bullets = []
    for doc in docs:
        source_type = doc.get("source_type", "tavily")
        confidence = doc.get("confidence_score", 0.5)
        priority = SOURCE_PRIORITY.get(source_type, 0.5)
        weight = round(confidence * priority, 3)
        
        if weight < 0.30:
            continue
        
        for bullet in doc.get("content_bullets", []):
            all_bullets.append({
                "text": bullet[:300],
                "source": source_type,
                "weight": weight
            })
    
    all_bullets = sorted(
        all_bullets, key=lambda x: x["weight"], reverse=True
    )[:30]
    
    lines = [f"=== {company.upper()} INTELLIGENCE ==="]
    for b in all_bullets:
        lines.append(f"[{b['source']}] {b['text']}")
    
    return "\n".join(lines)


def build_system_prompt(
    plaintiff: dict,
    primary: str,
    competitors: list,
    intelligence: dict
) -> str:
    """Build system prompt with all intelligence"""
    primary_intel = intelligence.get(primary, "No data available.")
    
    competitor_intel = ""
    for comp in competitors:
        intel = intelligence.get(comp, "No data available.")
        competitor_intel += f"""
--- {comp.upper()} — KNOW YOUR ENEMY ---
Use this to find weaknesses, pricing issues, complaints,
migrations away from {comp}. Frame everything as why
{primary} is the better choice.
{intel}
"""
    
    return f"""You are a battle-hardened sales coach.
Your ONLY job is to help the {primary} sales rep WIN this deal.

CRITICAL RULES — NEVER BREAK THESE:
1. You work FOR {primary} — every answer must make {primary} look stronger
2. Answer ONLY what was asked — one direct answer, then stop
3. Do NOT simulate dialogue or generate fake conversations
4. Do NOT ask the rep follow-up questions
5. Be specific — reference actual data points from the intelligence
6. When asked about competitors, expose their weaknesses using the data
7. Be honest about {primary}'s weaknesses — but always follow with
   how the rep should handle that objection in the meeting
8. Keep answers punchy — reps need ammunition not essays
9. Always frame the answer from {primary}'s perspective
10. Never recommend a competitor over {primary}

BUYER PROFILE:
- Company      : {plaintiff.get('company_name')}
- Team         : {plaintiff.get('team_size')}
- Budget       : {plaintiff.get('budget')}/month
- Use case     : {plaintiff.get('use_case')}
- Scale        : {plaintiff.get('scale')}
- Cloud        : {plaintiff.get('cloud')}
- Top priority : {plaintiff.get('priority')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{primary.upper()} — YOUR COMPANY STRENGTHS
Build every argument from this data:
{primary_intel}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPETITOR WEAKNESSES — EXPLOIT THESE
{competitor_intel}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def get_plaintiff_profile() -> dict:
    """Collect buyer profile"""
    print("\n📋 BUYER PROFILE")
    print("─" * 44)
    return {
        "company_name": input("  Company name: ").strip(),
        "team_size": input("  Team size (e.g. 5 engineers): ").strip(),
        "budget": input("  Monthly budget (e.g. $3000): ").strip(),
        "use_case": input("  Use case: ").strip(),
        "scale": input("  Scale (e.g. 10M to 100M vectors): ").strip(),
        "cloud": input("  Cloud provider (AWS/GCP/Azure): ").strip(),
        "priority": input(
            "  Top priority (cost/performance/simplicity/no-lock-in): "
        ).strip()
    }


def get_companies() -> tuple[str, list[str]]:
    """Collect company names with onboarding"""
    print("\n🏢 COMPANIES")
    print("─" * 44)
    
    primary = input("  YOUR company (e.g. MongoDB): ").strip()
    raw = input(
        "  COMPETITORS separated by comma "
        "(e.g. Pinecone, Weaviate): "
    ).strip()
    competitors = [c.strip() for c in raw.split(",") if c.strip()]
    
    all_companies = [primary] + competitors
    
    # ─── Process vendors (inline registration for new ones) ───
    # Don't auto-scrape - just register
    valid_vendors = process_vendors(all_companies, scrape_new=False)
    
    if not valid_vendors:
        print("\n❌ No valid vendors. Exiting.")
        raise SystemExit(0)
    
    primary = valid_vendors[0]
    competitors = valid_vendors[1:] if len(valid_vendors) > 1 else []
    
    return primary, competitors


def run_sales_copilot():
    """Main entry point for Mode 4"""
    print("""
╔══════════════════════════════════════════╗
║      SALES COPILOT — MODE 4              ║
║      Powered by Atlas + Groq             ║
╚══════════════════════════════════════════╝
    """)
    
    # Collect inputs
    plaintiff = get_plaintiff_profile()
    primary, competitors = get_companies()
    all_companies = [primary] + competitors
    
    # Load intelligence from Atlas
    print("\n⚡ Loading intelligence from Atlas...")
    intelligence = {}
    for company in all_companies:
        print(f"  📦 {company}...", end=" ", flush=True)
        intelligence[company] = load_company_intelligence(company)
        bullet_count = intelligence[company].count("\n")
        print(f"✅ {bullet_count} bullets loaded")
    
    # Build system prompt
    system_prompt = build_system_prompt(
        plaintiff, primary, competitors, intelligence
    )
    
    # Chat history
    history = []
    
    print(f"""
✅ Ready. Coaching {primary} rep against: {', '.join(competitors) if competitors else 'N/A'}
   Buyer   : {plaintiff['company_name']}
   Use case: {plaintiff['use_case']}
   Priority: {plaintiff['priority']}

Ask me anything. Type 'quit' to exit.
─────────────────────────────────────────
    """)
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  👋 Ending session.")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ["quit", "exit", "q"]:
            print("\n  👋 Good luck on the call.")
            break
        
        history.append(f"REP: {user_input}")
        conversation = "\n".join(history[-10:])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""CONVERSATION HISTORY:
{conversation}

REP ASKS: {user_input}

Answer as {primary} sales coach. Direct, specific, no fake dialogue."""
            }
        ]
        
        response = call_gemini_chat(messages)
        
        if isinstance(response, str) and response.startswith("ERROR"):
            print(f"  ⚠️  {response}")
            continue
        
        print(f"\nCoach: {response}\n")
        print("─" * 44)
        history.append(f"COACH: {response}")


if __name__ == "__main__":
    run_sales_copilot()