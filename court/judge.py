"""
Judge Module
============
Deliberates on court arguments and delivers verdict.
Mode-aware: generates different prompts for buyer, seller, and analyst modes.
Vertical-aware: loads dimensions and weights from verticals config.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import requests
from config import GROQ_API_KEY
from verticals import get_dimensions, get_priority_weights, get_judge_context, get_vertical


GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type":  "application/json"
}


def call_groq(messages: list, temperature: float = 0.2) -> str:
    """Call Groq API with retry logic."""
    payload = {
        "model":       GROQ_MODEL,
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  2000
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
            if "choices" not in data:
                wait = 60
                print(f"  ⏳ Rate limit — waiting {wait}s "
                      f"(attempt {attempt + 1}/3)...")
                time.sleep(wait)
                continue
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"ERROR: {e}"
    return "ERROR: Rate limit after 3 retries"


def format_all_statements(
    round_1:   dict,
    round_2:   dict,
    round_3:   dict,
    companies: list
) -> str:
    """Format all court arguments for judge prompt."""
    lines = []
    
    lines.append("=== ROUND 1 — OPENING STATEMENTS ===")
    for company in companies:
        stmt = round_1.get(company, {})
        lines.append(
            f"\n[{company}]\n{stmt.get('content', 'N/A')[:400]}"
        )
    
    lines.append("\n=== ROUND 2 — CROSS EXAMINATION ===")
    for key, attack in round_2.items():
        lines.append(
            f"\n[{key}]\n{attack.get('content', 'N/A')[:300]}"
        )
    
    lines.append("\n=== ROUND 3 — PLAINTIFF CHALLENGE ===")
    for company in companies:
        resp = round_3.get(company, {})
        lines.append(
            f"\n[{company}]\n{resp.get('content', 'N/A')[:300]}"
        )
    
    return "\n".join(lines)


def build_dimension_verdict_format(dimensions: list) -> str:
    """Build the dimension verdict format string for the prompt."""
    lines = ["DIMENSION VERDICTS:"]
    for dim in dimensions:
        dim_display = dim.replace("_", " ")
        lines.append(f"{dim_display}: [WINNER] — [one sentence reason]")
    return "\n".join(lines)


# ─── Plaintiff Profile Builder ──────────────────────────────

def _build_plaintiff_lines(plaintiff: dict, vertical: str) -> str:
    """Build plaintiff/prospect profile lines for prompt."""
    lines = [
        f"- Company: {plaintiff.get('company_name', 'Unknown')}",
        f"- Team: {plaintiff.get('team_size', 'Unknown')}",
        f"- Budget: {plaintiff.get('budget', 'Unknown')}/month",
        f"- Priority: {plaintiff.get('priority', 'performance')}",
        f"- Use case: {plaintiff.get('use_case', 'Unknown')}"
    ]
    
    if vertical == "database":
        lines.append(f"- Scale: {plaintiff.get('scale', 'Unknown')}")
        lines.append(f"- Cloud: {plaintiff.get('cloud', 'Unknown')}")
    elif vertical == "cloud":
        lines.append(f"- Scale: {plaintiff.get('scale', 'Unknown')}")
        lines.append(f"- Compliance: {plaintiff.get('compliance_reqs', 'None specified')}")
        lines.append(f"- Regions: {plaintiff.get('regions', 'Unknown')}")
    elif vertical == "crm":
        lines.append(f"- Deal volume: {plaintiff.get('deal_volume', 'Unknown')}")
        lines.append(f"- Integrations: {plaintiff.get('must_have_integrations', 'None specified')}")
    
    return chr(10).join(lines)


# ─── Mode-Specific Prompt Builders ──────────────────────────

def _build_buyer_prompts(
    judge_context: str,
    plaintiff: dict,
    vertical: str,
    challenge: str,
    weights: dict,
    all_statements: str,
    companies: list,
    dimension_format: str
) -> tuple:
    """Build buyer-mode system and user prompts."""
    
    system_prompt = f"""You are the judge in a {judge_context}.
Your job is to rule on each dimension and declare an overall winner — the best vendor for this specific buyer.

RULES:
- Base rulings ONLY on evidence presented in the arguments
- Weight dimensions according to plaintiff's stated priority
- Be specific about WHY each company wins or loses each dimension
- Identify the swing factor — what single constraint changes the verdict
- Do not favor any company — rule on evidence quality only
- A company that conceded honestly scores better than one that bluffed"""

    plaintiff_profile = _build_plaintiff_lines(plaintiff, vertical)
    priority = plaintiff.get("priority", "performance")
    
    user_prompt = f"""PLAINTIFF PROFILE:
{plaintiff_profile}

PLAINTIFF CONSTRAINT:
{challenge}

DIMENSION WEIGHTS FOR THIS PLAINTIFF:
{chr(10).join(f'  {dim}: {w}x' for dim, w in weights.items())}

ALL COURT ARGUMENTS:
{all_statements}

COMPANIES IN COURT:
{', '.join(companies)}

FORMAT YOUR RESPONSE EXACTLY AS:

{dimension_format}

OVERALL WINNER: [company name]
CONFIDENCE: [percentage]
PRIMARY REASON: [one paragraph explaining why this vendor is the best fit for this buyer]
RUNNER UP: [company name] — [one sentence on when they would win instead]
SWING FACTOR: [specific constraint that changes the verdict]
BATTLECARD: Top 3 arguments the sales rep should use on this call:
1. [argument]
2. [argument]
3. [argument]
WATCH OUT FOR: Top 2 objections the rep will face:
1. [objection + suggested response]
2. [objection + suggested response]"""

    return system_prompt, user_prompt


def _build_seller_prompts(
    judge_context: str,
    plaintiff: dict,
    vertical: str,
    challenge: str,
    weights: dict,
    all_statements: str,
    companies: list,
    dimension_format: str,
    my_company: str
) -> tuple:
    """Build seller-mode system and user prompts for battlecard generation."""
    
    competitors = [c for c in companies if c.lower() != my_company.lower()]
    
    system_prompt = f"""You are a competitive intelligence analyst generating a seller battlecard for {my_company}'s sales team.
You are analyzing a {judge_context} from {my_company}'s perspective.

YOUR GOAL: Help {my_company}'s sales rep WIN this deal against {', '.join(competitors)}.

RULES:
- Analyze from {my_company}'s perspective — this is NOT a neutral analysis
- Identify {my_company}'s strengths AND weaknesses honestly
- Generate actionable talking points, not vague statements
- Create specific objection handlers with counter-arguments
- Suggest questions that expose competitor weaknesses
- Do NOT declare a neutral "best fit" — always position {my_company} favorably
- Be honest about where {my_company} is weak so the rep can prepare"""

    plaintiff_profile = _build_plaintiff_lines(plaintiff, vertical)
    
    user_prompt = f"""PROSPECT PROFILE:
{plaintiff_profile}

PROSPECT CONSTRAINT:
{challenge}

DIMENSION WEIGHTS FOR THIS PROSPECT:
{chr(10).join(f'  {dim}: {w}x' for dim, w in weights.items())}

ALL COURT ARGUMENTS:
{all_statements}

MY COMPANY: {my_company}
COMPETITORS: {', '.join(competitors)}

FORMAT YOUR RESPONSE EXACTLY AS:

{dimension_format}

OVERALL WINNER: [company name — whoever objectively has the edge]
CONFIDENCE: [percentage]
PRIMARY REASON: [one paragraph]
WIN THEMES: Top 3-5 reasons {my_company} wins this deal:
1. [specific win theme with evidence]
2. [specific win theme with evidence]
3. [specific win theme with evidence]
ATTACK POINTS: Weaknesses of each competitor to exploit:
{chr(10).join(f'{c}: [specific weakness to attack]' for c in competitors)}
OBJECTION HANDLERS: Top 3 objections and counters:
1. OBJECTION: [what prospect might say] → COUNTER: [how to respond]
2. OBJECTION: [what prospect might say] → COUNTER: [how to respond]
3. OBJECTION: [what prospect might say] → COUNTER: [how to respond]
LAND MINES: Questions to ask that expose competitor weakness:
1. [question that makes competitor look bad]
2. [question that makes competitor look bad]
3. [question that makes competitor look bad]
PROOF POINTS: Evidence and references to use:
1. [customer quote, case study, or data point]
2. [customer quote, case study, or data point]
CLOSE STRATEGY: [one paragraph on how to close this specific deal]"""

    return system_prompt, user_prompt


def _build_analyst_prompts(
    judge_context: str,
    plaintiff: dict,
    vertical: str,
    challenge: str,
    weights: dict,
    all_statements: str,
    companies: list,
    dimension_format: str
) -> tuple:
    """Build analyst-mode system and user prompts for objective comparison."""
    
    system_prompt = f"""You are an objective market analyst conducting a neutral vendor comparison in {judge_context}.

CRITICAL RULES:
- You are NOT making a recommendation. You are providing OBJECTIVE analysis.
- Do NOT declare a winner or "best fit"
- Do NOT show bias toward any vendor
- Present facts, trade-offs, and data points — let readers draw conclusions
- For each dimension, state which vendor has an edge AND why, without recommending
- Include pricing model comparison where possible
- List pros AND cons for EVERY vendor — no vendor should appear "perfect"
- End with an explicit statement: "This analysis does not recommend a specific vendor."
"""

    focus_areas = plaintiff.get("focus_areas", [])
    focus_note = ""
    if focus_areas:
        focus_note = f"\nFOCUS AREAS: Prioritize analysis on: {', '.join(focus_areas)}\n"

    user_prompt = f"""ANALYSIS CONTEXT:
- Vertical: {vertical}
- Companies: {', '.join(companies)}
{focus_note}
ALL COURT ARGUMENTS:
{all_statements}

COMPANIES ANALYZED:
{', '.join(companies)}

FORMAT YOUR RESPONSE EXACTLY AS:

{dimension_format}

OVERVIEW: [2-3 sentence overview of the competitive landscape]
OVERALL WINNER: [company with most dimension wins — for data purposes only, NOT a recommendation]
CONFIDENCE: N/A — objective analysis
PRIMARY REASON: [summary of competitive dynamics, not a recommendation]
PRICING COMPARISON:
{chr(10).join(f'{c}: [pricing model and approximate cost]' for c in companies)}
PROS AND CONS:
{chr(10).join(f'{c} PROS: [top 3 pros]{chr(10)}{c} CONS: [top 3 cons]' for c in companies)}
BEST FIT SCENARIOS:
{chr(10).join(f'Choose {c} if: [specific scenario]' for c in companies)}
NO RECOMMENDATION: This analysis is objective and does not recommend a specific vendor. Choice depends on specific organizational requirements, priorities, and constraints."""

    return system_prompt, user_prompt


# ─── Main Deliberate Function ───────────────────────────────

def deliberate(
    companies: list,
    plaintiff: dict,
    round_1:   dict,
    round_2:   dict,
    round_3:   dict,
    challenge: str,
    vertical:  str = "database",
    mode:      str = "buyer"
) -> dict:
    """
    Judge deliberates and delivers verdict.
    
    Args:
        companies: List of companies in court
        plaintiff: Buyer/prospect profile
        round_1: Opening statements
        round_2: Cross examination
        round_3: Plaintiff challenge responses
        challenge: The plaintiff's specific challenge
        vertical: Industry vertical for config
        mode: buyer | seller | analyst
        
    Returns:
        Dict with verdict details
    """
    print(f"\n⚖️  JUDGE — Deliberating ({mode} mode)...")
    print(f"  ℹ️  Using Groq ({GROQ_MODEL}) for verdict")
    print(f"  ℹ️  Vertical: {vertical}")
    print("─" * 40)
    
    # Get vertical-specific config
    dimensions = get_dimensions(vertical)
    judge_context = get_judge_context(vertical)
    priority = plaintiff.get("priority", "performance")
    weights = get_priority_weights(vertical, priority)
    
    all_statements = format_all_statements(
        round_1, round_2, round_3, companies
    )
    
    dimension_format = build_dimension_verdict_format(dimensions)
    
    # Build mode-specific prompts
    if mode == "seller":
        my_company = plaintiff.get("my_company") or companies[0]
        system_prompt, user_prompt = _build_seller_prompts(
            judge_context, plaintiff, vertical, challenge,
            weights, all_statements, companies, dimension_format,
            my_company
        )
    elif mode == "analyst":
        system_prompt, user_prompt = _build_analyst_prompts(
            judge_context, plaintiff, vertical, challenge,
            weights, all_statements, companies, dimension_format
        )
    else:  # buyer (default)
        system_prompt, user_prompt = _build_buyer_prompts(
            judge_context, plaintiff, vertical, challenge,
            weights, all_statements, companies, dimension_format
        )
    
    content = call_groq(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0.2
    )
    
    return {
        "plaintiff":    plaintiff,
        "companies":    companies,
        "challenge":    challenge,
        "priority":     priority,
        "weights":      weights,
        "vertical":     vertical,
        "dimensions":   dimensions,
        "deliberation": content,
        "mode":         mode
    }


# ─── Parse Verdict ──────────────────────────────────────────

def parse_verdict(deliberation: str, vertical: str = "database", mode: str = "buyer") -> dict:
    """
    Parse judge's deliberation into structured verdict.
    Handles all three modes — they share dimension parsing but
    have different additional fields.
    """
    dimensions = get_dimensions(vertical)
    
    lines = deliberation.split("\n")
    verdict = {
        "dimensions":     {},
        "overall_winner": None,
        "confidence":     None,
        "primary_reason": None,
        "runner_up":      None,
        "swing_factor":   None,
        "battlecard":     [],
        "watch_out_for":  [],
        # Seller-specific
        "win_themes":     [],
        "attack_points":  {},
        "objection_handlers": [],
        "land_mines":     [],
        "proof_points":   [],
        "close_strategy": None,
        # Analyst-specific
        "overview":       None,
        "pricing_comparison": {},
        "pros_and_cons":  {},
        "best_fit_scenarios": {},
        "no_recommendation": None,
    }
    
    current_section = None
    current_company = None  # for multi-line company parsing
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # ─── Common fields ───
        if line.startswith("OVERALL WINNER:"):
            verdict["overall_winner"] = line.replace("OVERALL WINNER:", "").strip()
            current_section = None
        elif line.startswith("CONFIDENCE:"):
            verdict["confidence"] = line.replace("CONFIDENCE:", "").strip()
            current_section = None
        elif line.startswith("PRIMARY REASON:"):
            verdict["primary_reason"] = line.replace("PRIMARY REASON:", "").strip()
            current_section = None
        elif line.startswith("RUNNER UP:"):
            verdict["runner_up"] = line.replace("RUNNER UP:", "").strip()
            current_section = None
        elif line.startswith("SWING FACTOR:"):
            verdict["swing_factor"] = line.replace("SWING FACTOR:", "").strip()
            current_section = None
        elif line.startswith("OVERVIEW:"):
            verdict["overview"] = line.replace("OVERVIEW:", "").strip()
            current_section = None
        elif line.startswith("CLOSE STRATEGY:"):
            verdict["close_strategy"] = line.replace("CLOSE STRATEGY:", "").strip()
            current_section = None
        elif line.startswith("NO RECOMMENDATION:"):
            verdict["no_recommendation"] = line.replace("NO RECOMMENDATION:", "").strip()
            current_section = None
            
        # ─── Section headers ───
        elif line.startswith("BATTLECARD:"):
            current_section = "battlecard"
        elif line.startswith("WATCH OUT FOR:"):
            current_section = "watch_out"
        elif line.startswith("WIN THEMES:"):
            current_section = "win_themes"
        elif line.startswith("ATTACK POINTS:"):
            current_section = "attack_points"
        elif line.startswith("OBJECTION HANDLERS:"):
            current_section = "objection_handlers"
        elif line.startswith("LAND MINES:"):
            current_section = "land_mines"
        elif line.startswith("PROOF POINTS:"):
            current_section = "proof_points"
        elif line.startswith("PRICING COMPARISON:"):
            current_section = "pricing_comparison"
        elif line.startswith("PROS AND CONS:"):
            current_section = "pros_and_cons"
        elif line.startswith("BEST FIT SCENARIOS:"):
            current_section = "best_fit_scenarios"
            
        # ─── Section content parsing ───
        elif current_section == "battlecard" and line[0:1].isdigit():
            verdict["battlecard"].append(line.split(".", 1)[-1].strip())
        elif current_section == "watch_out" and line[0:1].isdigit():
            verdict["watch_out_for"].append(line.split(".", 1)[-1].strip())
        elif current_section == "win_themes" and line[0:1].isdigit():
            verdict["win_themes"].append(line.split(".", 1)[-1].strip())
        elif current_section == "land_mines" and line[0:1].isdigit():
            verdict["land_mines"].append(line.split(".", 1)[-1].strip())
        elif current_section == "proof_points" and line[0:1].isdigit():
            verdict["proof_points"].append(line.split(".", 1)[-1].strip())
        elif current_section == "objection_handlers" and line[0:1].isdigit():
            verdict["objection_handlers"].append(line.split(".", 1)[-1].strip())
        elif current_section == "attack_points" and ":" in line:
            parts = line.split(":", 1)
            company = parts[0].strip()
            attack = parts[1].strip()
            verdict["attack_points"][company] = attack
        elif current_section == "pricing_comparison" and ":" in line:
            parts = line.split(":", 1)
            company = parts[0].strip()
            pricing = parts[1].strip()
            verdict["pricing_comparison"][company] = pricing
        elif current_section == "pros_and_cons":
            if "PROS:" in line:
                company = line.split("PROS:")[0].strip()
                pros = line.split("PROS:")[1].strip()
                if company not in verdict["pros_and_cons"]:
                    verdict["pros_and_cons"][company] = {"pros": "", "cons": ""}
                verdict["pros_and_cons"][company]["pros"] = pros
            elif "CONS:" in line:
                company = line.split("CONS:")[0].strip()
                cons = line.split("CONS:")[1].strip()
                if company not in verdict["pros_and_cons"]:
                    verdict["pros_and_cons"][company] = {"pros": "", "cons": ""}
                verdict["pros_and_cons"][company]["cons"] = cons
        elif current_section == "best_fit_scenarios":
            if line.lower().startswith("choose ") and " if:" in line.lower():
                parts = line.split(" if:", 1)
                company = parts[0].replace("Choose ", "").replace("choose ", "").strip()
                scenario = parts[1].strip() if len(parts) > 1 else ""
                verdict["best_fit_scenarios"][company] = scenario
                
        # ─── Dimension verdicts (common to all modes) ───
        elif ":" in line and current_section not in [
            "battlecard", "watch_out", "win_themes", "attack_points",
            "objection_handlers", "land_mines", "proof_points",
            "pricing_comparison", "pros_and_cons", "best_fit_scenarios"
        ]:
            for dim in dimensions:
                dim_display = dim.replace("_", " ")
                if line.lower().startswith(dim_display):
                    parts = line.split("—", 1)
                    winner_part = parts[0].split(":")[-1].strip()
                    reason = parts[1].strip() if len(parts) > 1 else ""
                    verdict["dimensions"][dim] = {
                        "winner": winner_part,
                        "reason": reason
                    }
    
    return verdict


if __name__ == "__main__":
    from court.argument_builder import build_all_arguments, get_dimensions_for_vertical
    from court.advocates import run_advocates
    
    # Test with database vertical
    vertical = "database"
    companies = ["MongoDB", "Pinecone", "Weaviate"]
    dimensions = get_dimensions_for_vertical(vertical)
    
    banks = build_all_arguments(companies, vertical)
    
    plaintiff = {
        "company_name": "TestCo",
        "team_size":    "3 engineers",
        "budget":       "$2000",
        "use_case":     "RAG pipeline",
        "scale":        "10M to 200M vectors",
        "cloud":        "AWS",
        "priority":     "cost"
    }
    
    challenge = (
        "Our budget is strict at $2000/month and we expect "
        "to hit 200M vectors in 18 months. "
        "Which database stays affordable at that scale?"
    )
    
    results = run_advocates(
        companies, banks, plaintiff, dimensions, challenge
    )
    
    verdict = deliberate(
        companies=companies,
        plaintiff=plaintiff,
        round_1=results["round_1"],
        round_2=results["round_2"],
        round_3=results["round_3"],
        challenge=challenge,
        vertical=vertical,
        mode="buyer"
    )
    
    print("\n\n⚖️  JUDGE VERDICT")
    print("=" * 40)
    print(verdict["deliberation"])
    
    parsed = parse_verdict(verdict["deliberation"], vertical, mode="buyer")
    print("\n\n📊 PARSED VERDICT")
    print("=" * 40)
    print(f"  Winner     : {parsed['overall_winner']}")
    print(f"  Confidence : {parsed['confidence']}")
    print(f"  Runner up  : {parsed['runner_up']}")
    print(f"  Swing      : {parsed['swing_factor']}")
    print(f"\n  Battlecard:")
    for b in parsed["battlecard"]:
        print(f"    • {b}")
    print(f"\n  Watch out for:")
    for w in parsed["watch_out_for"]:
        print(f"    • {w}")