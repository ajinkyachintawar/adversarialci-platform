"""
Court Session v2
================
Orchestrates the adversarial courtroom debate.
Now mode-aware for Buyer/Seller/Analyst output.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import WarRoomState
from court.argument_builder import build_all_arguments, get_dimensions_for_vertical
from court.advocates import run_advocates
from court.judge import deliberate, parse_verdict
from court.verdict import process_verdict
from verticals import get_vertical


def build_challenge(plaintiff: dict, vertical: str) -> str:
    """Build challenge string based on vertical and plaintiff profile."""
    
    config = get_vertical(vertical)
    
    # Base challenge
    challenge_parts = [
        f"Given a budget of {plaintiff.get('budget', 'unspecified')}/month"
    ]
    
    # Vertical-specific parts
    if vertical == "database":
        challenge_parts.extend([
            f"a scale of {plaintiff.get('scale', 'unspecified')}",
            f"and a primary use case of {plaintiff.get('use_case', 'unspecified')}",
            f"on {plaintiff.get('cloud', 'cloud infrastructure')}",
            f"with a team of {plaintiff.get('team_size', 'small team')}"
        ])
    elif vertical == "cloud":
        challenge_parts.extend([
            f"scaling to {plaintiff.get('scale', 'unspecified')}",
            f"with compliance requirements of {plaintiff.get('compliance', 'standard')}",
            f"needing coverage in {plaintiff.get('regions', 'multiple regions')}",
            f"for {plaintiff.get('use_case', 'general workloads')}"
        ])
    elif vertical == "crm":
        challenge_parts.extend([
            f"a sales team of {plaintiff.get('team_size', 'unspecified')}",
            f"handling {plaintiff.get('deal_volume', 'typical')} deals",
            f"needing integrations with {plaintiff.get('integrations', 'common tools')}",
            f"for {plaintiff.get('use_case', 'sales management')}"
        ])
    
    # Priority
    priority = plaintiff.get('priority', 'value')
    challenge_parts.append(f"where {priority} is the top priority")
    
    return ", ".join(challenge_parts) + "."


def court_session(state: WarRoomState) -> WarRoomState:
    """
    Run the full courtroom session.
    
    Mode affects:
    - Challenge framing
    - Verdict output format
    - Confidence calculation
    """
    
    # Get mode and vertical
    mode = state.get("plaintiff", {}).get("mode", "buyer")
    vertical = state.get("vertical", "database")
    config = get_vertical(vertical)
    
    print(f"\n⚖️  COURT SESSION OPENING")
    print("=" * 40)
    
    primary = state["primary"]
    competitors = state["competitors"]
    plaintiff = state["plaintiff"]
    companies = [primary] + competitors
    
    # Mode-specific header
    if mode == "buyer":
        print(f"\n  Mode      : 🛒 Buyer Evaluation")
    elif mode == "seller":
        my_company = state.get("my_company") or primary
        print(f"\n  Mode      : 🎯 Seller Battlecard")
        print(f"  You Sell  : {my_company}")
    else:
        print(f"\n  Mode      : 📊 Analyst Comparison")
    
    print(f"  Vertical  : {config['display_name']}")
    print(f"  Companies : {', '.join(companies)}")
    print(f"  Plaintiff : {plaintiff.get('company_name', 'N/A')}")
    print(f"  Use case  : {plaintiff.get('use_case', 'N/A')}")
    print(f"  Budget    : {plaintiff.get('budget', 'N/A')}/month")
    print(f"  Priority  : {plaintiff.get('priority', 'N/A')}")
    
    # Build challenge
    challenge = build_challenge(plaintiff, vertical)
    print(f"\n  Challenge : {challenge[:100]}...")
    
    # Step 1 — Build argument banks
    argument_banks = build_all_arguments(companies, vertical)
    
    # Step 2 — Run advocates (Ollama)
    dimensions = get_dimensions_for_vertical(vertical)
    results = run_advocates(
        companies=companies,
        argument_banks=argument_banks,
        plaintiff=plaintiff,
        dimensions=dimensions,
        challenge=challenge
    )
    
    # Step 3 — Judge deliberates (Groq) — mode-aware
    verdict = deliberate(
        companies=companies,
        plaintiff=plaintiff,
        round_1=results["round_1"],
        round_2=results["round_2"],
        round_3=results["round_3"],
        challenge=challenge,
        vertical=vertical,
        mode=mode
    )
    
    # Step 4 — Parse verdict (mode-aware)
    parsed = parse_verdict(verdict["deliberation"], vertical, mode=mode)
    
    # Step 5 — Prepare verdict data with mode info
    verdict_data = {
        **verdict,
        "vertical": vertical,
        "my_company": state.get("my_company") or primary
    }
    
    # Step 6 — Save to Atlas + generate mode-specific report
    output = process_verdict(
        verdict=verdict_data,
        parsed=parsed,
        round_1=results["round_1"],
        round_2=results["round_2"],
        round_3=results["round_3"],
        mode=mode
    )
    
    # Mode-specific summary
    if mode == "buyer":
        summary_label = "Best Fit"
    elif mode == "seller":
        summary_label = "Win Prob"
    else:
        summary_label = "Quality"
    
    print(f"""
╔══════════════════════════════════════════╗
║      COURT SESSION COMPLETE              ║
║                                          ║
║  Vertical   : {config['display_name']:<25} ║
║  Winner     : {output['winner']:<25} ║
║  {summary_label:<10}  : {output['confidence']:<25} ║
║  Report     : outputs/reports/           ║
║  Session ID : saved to Atlas             ║
╚══════════════════════════════════════════╝
    """)
    
    return {
        **state,
        "verdict": parsed,
        "stage": "complete"
    }


if __name__ == "__main__":
    # Test
    from state import create_initial_state
    
    state = create_initial_state("cloud", "buyer")
    state.update({
        "primary": "AWS",
        "competitors": ["Microsoft Azure", "Google Cloud"],
        "plaintiff": {
            "mode": "buyer",
            "company_name": "TestCorp",
            "team_size": "10 engineers",
            "budget": "$10,000",
            "use_case": "SaaS platform",
            "scale": "100 VMs now, 500 in 18mo",
            "compliance": "SOC2, GDPR",
            "regions": "US, EU",
            "priority": "compliance"
        }
    })
    
    challenge = build_challenge(state["plaintiff"], "cloud")
    print(f"Challenge: {challenge}")