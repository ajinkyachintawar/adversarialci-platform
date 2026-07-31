"""
Heads Runner (Agents V2)
========================
Mode dispatch -> consistency check (+ one re-ask) -> persist. This is the
whole of the AGENTS_V2=1 path; pipeline/court_session.py imports run_v2 from
here inside its flag-gated branch and nothing else in the old pipeline
changes.

Persists a doc to court_sessions with the same core fields the old
court/verdict.py::process_verdict writes (mode, vertical, plaintiff,
companies, priority, parsed_verdict.{overall_winner, confidence},
created_at — see server.py:775-799 for exactly what the History list reads)
plus verdict_json (the validated verdict dict), consistency
({passed, failures}), and claims_metrics, so both old and new sessions render
in the existing History UI.

Run:  .venv/bin/python -m heads.runner   (requires Atlas + Groq — see eval/heads_smoke.py)
"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heads import buyer as buyer_mod
from heads import seller as seller_mod
from heads import analyst as analyst_mod
from heads import consistency
from heads import evidence as evidence_mod
from heads import llm as llm_mod
from heads.llm import call_llm
from heads.schemas import BuyerVerdict, SellerVerdict, AnalystVerdict, parse_verdict_json

_MODEL_CLS = {"buyer": BuyerVerdict, "seller": SellerVerdict, "analyst": AnalystVerdict}


def _reask_fix(verdict, model_cls, failures: list[str], judge_model: str):
    """One re-ask, quoting the consistency failures verbatim. Returns the
    corrected verdict, or the original verdict if the re-ask itself fails
    (caller marks inconsistent: true and continues — never crashes)."""
    messages = [
        {"role": "system", "content":
            "You produced a verdict JSON that failed a deterministic "
            "consistency check. Fix it."},
        {"role": "user", "content":
            f"PREVIOUS OUTPUT:\n{json.dumps(verdict.model_dump())}\n\n"
            f"FAILURES:\n" + "\n".join(f"- {f}" for f in failures) +
            "\n\nFix these inconsistencies, return the corrected JSON only."},
    ]
    raw = call_llm(messages, model=judge_model, max_tokens=3000)
    try:
        return parse_verdict_json(raw, model_cls)
    except Exception as e:
        print(f"  ⚠️  Re-ask produced invalid JSON ({e}) — keeping original, flagging inconsistent")
        return verdict


def run_v2(state: dict) -> dict:
    from config import LLM_MODEL

    mode = state.get("plaintiff", {}).get("mode", "buyer")
    vertical = state.get("vertical", "database")
    primary = state["primary"]
    competitors = state["competitors"]
    plaintiff = state["plaintiff"]
    companies = [primary] + competitors

    print(f"\n⚖️  COURT SESSION OPENING (Agents V2)")
    print("=" * 40)
    print(f"  Mode      : {mode}")
    print(f"  Vertical  : {vertical}")
    print(f"  Companies : {', '.join(companies)}")

    _head_t0 = time.time()
    calls_before = llm_mod.call_count
    if mode == "buyer":
        verdict, claims_by_company = buyer_mod._run_with_evidence(state)
    elif mode == "seller":
        verdict, claims_by_company = seller_mod._run_with_evidence(state)
    elif mode == "analyst":
        verdict, claims_by_company = analyst_mod._run_with_evidence(state)
    else:
        raise ValueError(f"unknown mode: {mode}")

    # The head does claims-gathering then debate+judge; evidence.gather
    # records its own slice so the two are separable.
    head_seconds = round(time.time() - _head_t0, 1)
    stage_seconds = {
        **(state.get("stage_seconds") or {}),
        "claims": evidence_mod.last_gather_seconds,
        "debate_and_judge": round(head_seconds - evidence_mod.last_gather_seconds, 1),
    }
    print(f"  ⏱  claims {stage_seconds['claims']}s"
          f"{' (cached)' if evidence_mod.last_gather_cached else ''}"
          f" | debate+judge {stage_seconds['debate_and_judge']}s"
          f" | {llm_mod.call_count - calls_before} LLM calls")

    result = consistency.check(verdict, claims_by_company, vertical)
    print(f"  🔎 Consistency: {'✅ passed' if result['passed'] else '❌ failed'}"
          + (f" — {result['failures']}" if result["failures"] else ""))

    inconsistent = False
    if not result["passed"]:
        print("  🔁 Re-asking judge to fix consistency failures (one attempt)")
        verdict = _reask_fix(verdict, _MODEL_CLS[mode], result["failures"], LLM_MODEL)
        if mode == "buyer":
            verdict = buyer_mod.recompute_confidence(verdict)
        result = consistency.check(verdict, claims_by_company, vertical)
        inconsistent = not result["passed"]
        print(f"  🔎 Consistency after re-ask: {'✅ passed' if result['passed'] else '❌ still failing'}")

    from pipeline.court_session import build_challenge
    challenge = build_challenge(plaintiff, vertical)

    if mode == "buyer":
        winner, confidence_display = verdict.winner, f"{verdict.confidence}%"
    elif mode == "seller":
        winner, confidence_display = verdict.my_company, f"{verdict.win_probability}% win probability"
    else:
        winner, confidence_display = None, "N/A (no winner declared)"

    from db.atlas import connect, get_collection
    connect()
    col = get_collection("court_sessions")
    report_id = f"{mode}_report_{datetime.utcnow():%Y%m%d_%H%M%S}"
    doc = {
        "report_id": report_id,
        "mode": mode,
        "vertical": vertical,
        "plaintiff": plaintiff,
        "companies": companies,
        "challenge": challenge,
        "priority": plaintiff.get("priority"),
        "parsed_verdict": {
            "overall_winner": winner,
            "confidence": confidence_display,
        },
        "verdict_json": verdict.model_dump(),
        "consistency": result,
        "inconsistent": inconsistent,
        "claims_metrics": {c: len(claims) for c, claims in claims_by_company.items()},
        "stage_seconds": stage_seconds,
        "claims_cached": evidence_mod.last_gather_cached,
        "created_at": datetime.utcnow(),
    }
    inserted = col.insert_one(doc)
    session_id = str(inserted.inserted_id)
    print(f"  💾 Verdict saved to Atlas — session: {session_id}")

    print(f"""
╔══════════════════════════════════════════╗
║      COURT SESSION COMPLETE (V2)         ║
║                                          ║
║  Vertical   : {vertical:<25} ║
║  Winner     : {str(winner):<25} ║
║  Confidence : {confidence_display:<25} ║
║  Consistent : {str(result['passed']):<25} ║
║  Session ID : {session_id:<25} ║
╚══════════════════════════════════════════╝
    """)

    return {
        **state,
        "verdict": {"overall_winner": winner, "confidence": confidence_display,
                    "verdict_json": verdict.model_dump(), "consistency": result},
        "report_id": report_id,
        "stage_seconds": stage_seconds,
        "stage": "complete",
    }


if __name__ == "__main__":
    from state import create_initial_state
    state = create_initial_state("database", "buyer")
    state.update({
        "primary": "MongoDB",
        "competitors": ["Pinecone", "Weaviate"],
        "plaintiff": {
            "mode": "buyer",
            "company_name": "TestCorp",
            "team_size": "8 engineers",
            "budget": "$2,000",
            "use_case": "RAG pipeline for customer support",
            "scale": "5M vectors now, 50M in 12mo",
            "cloud": "AWS",
            "priority": "cost",
        },
    })
    run_v2(state)
