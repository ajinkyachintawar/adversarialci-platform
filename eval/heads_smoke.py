"""
Heads Smoke Test
================
Task A acceptance harness for the Agents V2 mode heads: run buyer/seller/
analyst against a canned plaintiff profile (MongoDB vs Pinecone vs Weaviate,
database vertical — same trio as eval/claims_eval.py's DEFAULT_PAIRS) on live
Atlas + Groq + Gemini, run heads.consistency.check, and report verdict
quality honestly rather than tuning to pass.

Run:  .venv/bin/python -m eval.heads_smoke [buyer|seller|analyst|all]
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
from heads import llm as llm_mod
from state import create_initial_state

VERTICAL = "database"
COMPANIES = ["MongoDB", "Pinecone", "Weaviate"]

# One canned plaintiff profile, reused across all three modes for
# comparability — matches the shape used in pipeline/court_session.py's
# __main__ self-test.
PLAINTIFF = {
    "company_name": "TestCorp",
    "team_size": "8 engineers",
    "budget": "$2,000",
    "use_case": "RAG pipeline for customer support",
    "scale": "5M vectors now, 50M in 12mo",
    "cloud": "AWS",
    "priority": "cost",
}

RUNNERS = {
    "buyer": (buyer_mod._run_with_evidence, {"mode": "buyer", "priority": "cost"}),
    "seller": (seller_mod._run_with_evidence, {"mode": "seller", "priority": "performance"}),
    "analyst": (analyst_mod._run_with_evidence, {"mode": "analyst", "priority": "value"}),
}


def _build_state(mode: str, plaintiff_overrides: dict) -> dict:
    state = create_initial_state(VERTICAL, mode)
    plaintiff = {**PLAINTIFF, **plaintiff_overrides}
    update = {
        "primary": COMPANIES[0],
        "competitors": COMPANIES[1:],
        "plaintiff": plaintiff,
    }
    if mode == "seller":
        update["my_company"] = "Pinecone"  # underdog on cost — the interesting case
    state.update(update)
    return state


def _count_evidence_ids(verdict_dict: dict) -> int:
    count = 0

    def walk(node):
        nonlocal count
        if isinstance(node, dict):
            if "evidence_ids" in node and isinstance(node["evidence_ids"], list):
                count += len(node["evidence_ids"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(verdict_dict)
    return count


def _summary_line(mode: str, verdict) -> str:
    if mode == "buyer":
        return f"winner={verdict.winner} confidence={verdict.confidence}%"
    if mode == "seller":
        return f"my_company={verdict.my_company} win_probability={verdict.win_probability}%"
    return f"matrix covers {len(verdict.matrix)} companies"


def run_one(mode: str) -> dict:
    print(f"\n{'=' * 50}\n🧪 SMOKE TEST — {mode}\n{'=' * 50}")
    runner, overrides = RUNNERS[mode]
    state = _build_state(mode, overrides)

    calls_before = llm_mod.call_count
    t0 = time.time()
    error = None
    verdict, claims_by_company = None, {}
    try:
        verdict, claims_by_company = runner(state)
    except Exception as e:
        error = str(e)
        print(f"  ❌ head raised: {error}")

    wall_seconds = round(time.time() - t0, 1)
    # heads.llm.call_count only tracks debate/judge calls made by the head
    # itself; claims.extractor's own extraction calls (inside
    # evidence.gather, one per dimension per company) are a separate Groq
    # budget and aren't tracked by this counter — see the report note.
    head_llm_calls = llm_mod.call_count - calls_before

    if error:
        result = {
            "mode": mode, "error": error, "wall_seconds": wall_seconds,
            "head_llm_calls": head_llm_calls, "passed": False,
        }
    else:
        verdict_dict = verdict.model_dump()
        consistency_result = consistency.check(verdict, claims_by_company, VERTICAL)
        evidence_id_count = _count_evidence_ids(verdict_dict)

        result = {
            "mode": mode,
            "summary": _summary_line(mode, verdict),
            "consistency": consistency_result,
            "evidence_ids_cited": evidence_id_count,
            "head_llm_calls": head_llm_calls,
            "wall_seconds": wall_seconds,
            "verdict": verdict_dict,
        }
        print(f"  📋 {result['summary']}")
        print(f"  🔎 consistency: {'✅ passed' if consistency_result['passed'] else '❌ FAILED'}"
              + (f" — {consistency_result['failures']}" if consistency_result["failures"] else ""))
        print(f"  📎 evidence_ids cited: {evidence_id_count}")
        print(f"  📞 head LLM calls: {head_llm_calls} | wall time: {wall_seconds}s")

        os.makedirs("eval/results", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = f"eval/results/heads_smoke_{mode}_{ts}.json"
        with open(path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  💾 saved -> {path}")
        result["passed"] = consistency_result["passed"]

    return result


def main(target: str) -> int:
    modes = ["buyer", "seller", "analyst"] if target == "all" else [target]
    results = [run_one(m) for m in modes]

    print(f"\n{'=' * 50}\n📊 SMOKE TEST SUMMARY\n{'=' * 50}")
    all_ok = True
    for r in results:
        ok = r.get("passed", False)
        all_ok = all_ok and ok
        status = "✅" if ok else "❌"
        detail = r.get("summary", r.get("error", ""))
        print(f"  {status} {r['mode']}: {detail}")

    print(f"\n{'✅ ALL PASSED' if all_ok else '❌ ONE OR MORE FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target not in ("buyer", "seller", "analyst", "all"):
        print("Usage: -m eval.heads_smoke [buyer|seller|analyst|all]")
        sys.exit(1)
    sys.exit(main(target))
