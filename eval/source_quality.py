"""
Source Quality Evaluation v2
============================
Now with LLM-based quality scoring for meaningful evaluation.

Layers:
1. Coverage: Did we scrape all sources?
2. Freshness: Is data recent?
3. LLM Quality: Is the content accurate, relevant, balanced?
"""

import json
import time
import requests
from datetime import datetime, timedelta
from db.atlas import connect, get_collection
from verticals import list_verticals, get_vertical
from config import GROQ_API_KEY


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}


# ─── LLM Call ───────────────────────────────────────────────

def call_groq(prompt: str, temperature: float = 0.1) -> str:
    """Call Groq API."""
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 500
    }
    
    for attempt in range(3):
        try:
            response = requests.post(
                GROQ_URL,
                headers=GROQ_HEADERS,
                json=payload,
                timeout=30
            )
            data = response.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            
            # Rate limit
            print(f"    ⏳ Rate limit, waiting 30s (attempt {attempt + 1}/3)...")
            time.sleep(30)
        except Exception as e:
            print(f"    ⚠️ Groq error: {e}")
            return None
    
    return None


# ─── Vertical Selection ─────────────────────────────────────

def select_vertical() -> str:
    """Prompt user to select vertical."""
    available = list_verticals()
    
    print("\n📂 SELECT VERTICAL TO EVALUATE")
    print("─" * 40)
    for i, v in enumerate(available, 1):
        config = get_vertical(v)
        print(f"  [{i}] {config['display_name']}")
    print(f"  [{len(available) + 1}] All Verticals")
    
    while True:
        choice = input(f"\nEnter choice (1-{len(available) + 1}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                return available[idx]
            elif idx == len(available):
                return "all"
        except ValueError:
            pass
        print(f"  ⚠️  Invalid choice")


def get_companies_for_vertical(vertical: str, all_companies: list) -> list:
    """Filter companies by vertical config."""
    config = get_vertical(vertical)
    vendors = set(config.get("vendors", {}).keys())
    matched = [c for c in all_companies if c in vendors]
    return matched if matched else all_companies


# ─── Layer 1: Coverage ──────────────────────────────────────

def eval_coverage(company: str, docs: list) -> dict:
    """Check if all expected source types are present."""
    source_types = set(d.get("source_type") for d in docs)
    expected = {"tavily", "hn", "pricing_scrape", "github", "blog_rss", "migration_tavily"}
    
    present = source_types & expected
    missing = expected - source_types
    
    total_bullets = sum(len(d.get("content_bullets", [])) for d in docs)
    
    coverage_pct = round(len(present) / len(expected) * 100, 1)
    
    return {
        "coverage_pct": coverage_pct,
        "sources_present": list(present),
        "sources_missing": list(missing),
        "total_bullets": total_bullets,
        "pass": coverage_pct >= 66  # At least 4/6 sources
    }


# ─── Layer 2: Freshness ─────────────────────────────────────

def eval_freshness(company: str, docs: list) -> dict:
    """Check if data is recent."""
    now = datetime.utcnow()
    
    scraped_dates = []
    for doc in docs:
        scraped_at = doc.get("scraped_at")
        if scraped_at:
            if isinstance(scraped_at, str):
                scraped_at = datetime.fromisoformat(scraped_at.replace("Z", ""))
            scraped_dates.append(scraped_at)
    
    if not scraped_dates:
        return {
            "newest_days_ago": None,
            "oldest_days_ago": None,
            "pass": False,
            "reason": "No scraped_at timestamps"
        }
    
    newest = max(scraped_dates)
    oldest = min(scraped_dates)
    
    newest_age = (now - newest).days
    oldest_age = (now - oldest).days
    
    return {
        "newest_days_ago": newest_age,
        "oldest_days_ago": oldest_age,
        "pass": newest_age <= 7,  # At least some data from last week
        "reason": f"Newest: {newest_age}d ago, Oldest: {oldest_age}d ago"
    }


# ─── Layer 3: LLM Quality Scoring ───────────────────────────

def eval_llm_quality(company: str, docs: list, vertical: str) -> dict:
    """Use LLM to score research quality."""
    
    # Collect sample bullets from each source
    all_bullets = []
    for doc in docs:
        source = doc.get("source_type", "unknown")
        bullets = doc.get("content_bullets", [])[:5]  # Max 5 per source
        for b in bullets:
            all_bullets.append(f"[{source}] {b[:300]}")
    
    # Limit total to avoid token limits
    sample = all_bullets[:25]
    
    if not sample:
        return {
            "accuracy": 0,
            "relevance": 0,
            "balance": 0,
            "specificity": 0,
            "overall": 0,
            "pass": False,
            "reason": "No bullets to evaluate"
        }
    
    config = get_vertical(vertical)
    
    prompt = f"""You are evaluating competitive intelligence research about {company} ({config['display_name']} vertical).

Rate the following research bullets on a scale of 1-10:

RESEARCH BULLETS:
{chr(10).join(sample)}

SCORING CRITERIA:
1. ACCURACY (1-10): Are the facts verifiable and likely correct? Look for specific numbers, dates, version numbers.
2. RELEVANCE (1-10): Is this info useful for comparing {company} against competitors? Does it cover pricing, features, limitations?
3. BALANCE (1-10): Does it cover BOTH strengths AND weaknesses/complaints? Or is it one-sided?
4. SPECIFICITY (1-10): Are there concrete data points (prices, benchmarks, dates, customer names) vs vague claims?

Respond ONLY with valid JSON, no other text:
{{"accuracy": N, "relevance": N, "balance": N, "specificity": N, "reasoning": "one sentence summary"}}"""

    response = call_groq(prompt)
    
    if not response:
        return {
            "accuracy": 0,
            "relevance": 0,
            "balance": 0,
            "specificity": 0,
            "overall": 0,
            "pass": False,
            "reason": "LLM call failed"
        }
    
    # Parse JSON response
    try:
        # Clean response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        scores = json.loads(response)
        
        overall = round((
            scores.get("accuracy", 0) +
            scores.get("relevance", 0) +
            scores.get("balance", 0) +
            scores.get("specificity", 0)
        ) / 4, 1)
        
        return {
            "accuracy": scores.get("accuracy", 0),
            "relevance": scores.get("relevance", 0),
            "balance": scores.get("balance", 0),
            "specificity": scores.get("specificity", 0),
            "overall": overall,
            "reasoning": scores.get("reasoning", ""),
            "pass": overall >= 6.0
        }
    
    except json.JSONDecodeError:
        return {
            "accuracy": 0,
            "relevance": 0,
            "balance": 0,
            "specificity": 0,
            "overall": 0,
            "pass": False,
            "reason": f"Failed to parse LLM response: {response[:100]}"
        }


# ─── Run Full Eval ──────────────────────────────────────────

def run_eval_vertical(vertical: str):
    """Run full evaluation for a vertical."""
    config = get_vertical(vertical)
    
    print(f"""
╔══════════════════════════════════════════╗
║         SOURCE QUALITY EVAL v2           ║
║         {config['display_name']:<30} ║
╚══════════════════════════════════════════╝
    """)
    
    connect()
    col = get_collection("research_data")
    
    all_companies = col.distinct("company")
    companies = get_companies_for_vertical(vertical, all_companies)
    
    if not companies:
        print(f"❌ No {vertical} companies found in Atlas.")
        return None
    
    print(f"  📦 Evaluating {len(companies)} companies\n")
    
    results = []
    
    for company in companies:
        print(f"  ── {company} ──")
        
        docs = list(col.find({"company": company}, {"_id": 0}))
        
        # Layer 1: Coverage
        coverage = eval_coverage(company, docs)
        cov_status = "✅" if coverage["pass"] else "⚠️"
        print(f"     Coverage: {cov_status} {coverage['coverage_pct']}% ({coverage['total_bullets']} bullets)")
        
        # Layer 2: Freshness
        freshness = eval_freshness(company, docs)
        fresh_status = "✅" if freshness["pass"] else "⚠️"
        print(f"     Freshness: {fresh_status} {freshness['reason']}")
        
        # Layer 3: LLM Quality
        print(f"     Quality: 🔄 Analyzing with LLM...")
        quality = eval_llm_quality(company, docs, vertical)
        qual_status = "✅" if quality["pass"] else "⚠️"
        print(f"     Quality: {qual_status} Overall {quality['overall']}/10")
        print(f"        Accuracy: {quality['accuracy']}/10 | Relevance: {quality['relevance']}/10")
        print(f"        Balance: {quality['balance']}/10 | Specificity: {quality['specificity']}/10")
        if quality.get("reasoning"):
            print(f"        → {quality['reasoning']}")
        
        results.append({
            "company": company,
            "coverage": coverage,
            "freshness": freshness,
            "quality": quality
        })
        
        print()
        
        # Rate limit protection
        time.sleep(1)
    
    # ── Summary ──
    print("=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    passing = [r for r in results if r["coverage"]["pass"] and r["quality"]["pass"]]
    avg_quality = sum(r["quality"]["overall"] for r in results) / len(results) if results else 0
    
    print(f"""
  Companies Evaluated : {len(results)}
  Passing (Coverage)  : {sum(1 for r in results if r['coverage']['pass'])}/{len(results)}
  Passing (Quality)   : {sum(1 for r in results if r['quality']['pass'])}/{len(results)}
  Average Quality     : {avg_quality:.1f}/10
    """)
    
    # Quality breakdown
    print("  Quality Scores by Company:")
    for r in sorted(results, key=lambda x: x["quality"]["overall"], reverse=True):
        status = "✅" if r["quality"]["overall"] >= 6 else "⚠️" if r["quality"]["overall"] >= 4 else "❌"
        print(f"    {status} {r['company']:<25} {r['quality']['overall']}/10")
    
    # Save report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "vertical": vertical,
        "summary": {
            "companies_evaluated": len(results),
            "passing_coverage": sum(1 for r in results if r["coverage"]["pass"]),
            "passing_quality": sum(1 for r in results if r["quality"]["pass"]),
            "avg_quality": round(avg_quality, 1)
        },
        "results": results
    }
    
    import os
    os.makedirs("outputs/reports", exist_ok=True)
    filename = f"outputs/reports/eval_v2_{vertical}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n  📄 Report saved to: {filename}\n")
    
    return report


# ─── Main ───────────────────────────────────────────────────

def run_eval():
    """Main entry point."""
    vertical = select_vertical()
    
    if vertical == "all":
        for v in list_verticals():
            run_eval_vertical(v)
            print("\n" + "=" * 60 + "\n")
    else:
        run_eval_vertical(vertical)


if __name__ == "__main__":
    run_eval()