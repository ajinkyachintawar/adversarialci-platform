"""
Abstention Eval
===============
The number Plan A lives or dies on: does answer() say "no evidence" when the
corpus cannot support an answer, and does it still answer when it can?

Measured against both sides:
  positives  eval/golden_retrieval_v2.json  -> should return confidence "evidence"
  negatives  eval/golden_abstain.json       -> should return confidence "none"

Also splits WHERE each abstention happened, which matters architecturally:
  "floor"    the SCORE_FLOOR pre-filter caught it, zero LLM calls (free)
  "gate"     the LLM ran and the citation gate rejected the result (1 call)
A single similarity threshold cannot be the guarantee (positives 0.860-0.911 vs
negatives 0.789-0.893, AUC 0.875 — overlapping tails), so the citation gate is
the real mechanism. This eval measures the mechanism, not the threshold.

Run:  .venv/bin/python -m eval.abstention_eval [label]
Out:  eval/results/abstention_eval_<label>_<timestamp>.json
"""

import json
import os
import sys
from datetime import datetime, UTC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heads.llm as llm_mod
from earshot.answer import answer, SCORE_FLOOR


def _run(entries: list[dict], expect: str) -> list[dict]:
    rows = []
    for e in entries:
        before = llm_mod.call_count
        out = answer(e["query"], e["company"])
        calls = llm_mod.call_count - before
        correct = out["confidence"] == expect
        rows.append({
            "query": e["query"],
            "company": e["company"],
            "confidence": out["confidence"],
            "expected": expect,
            "correct": correct,
            "llm_calls": calls,
            # an abstention with zero calls came from the floor; with calls,
            # from the citation gate
            "abstained_at": (None if out["confidence"] != "none"
                             else ("floor" if calls == 0 else "gate")),
            "citations": len(out["citations"]),
            "seconds": out["seconds"],
            "answer": out["answer"][:200],
        })
        mark = "✅" if correct else "❌"
        where = rows[-1]["abstained_at"] or f'{rows[-1]["citations"]} cites'
        print(f"  {mark} [{out['confidence']:<8}] {where:<10} {e['company']:<9} {e['query'][:58]}",
              flush=True)
    return rows


def main(label: str = "baseline") -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    pos = json.load(open(os.path.join(here, "golden_retrieval_v2.json")))["queries"]
    neg = json.load(open(os.path.join(here, "golden_abstain.json")))["queries"]

    print(f"\n📊 Abstention eval (SCORE_FLOOR={SCORE_FLOOR})")
    print(f"\n-- NEGATIVES ({len(neg)}) — should abstain --")
    neg_rows = _run(neg, "none")
    print(f"\n-- POSITIVES ({len(pos)}) — should answer --")
    pos_rows = _run(pos, "evidence")

    abstained = sum(r["correct"] for r in neg_rows)
    answered = sum(r["correct"] for r in pos_rows)
    at_floor = sum(r["abstained_at"] == "floor" for r in neg_rows)
    at_gate = sum(r["abstained_at"] == "gate" for r in neg_rows)
    false_abstain = [r for r in pos_rows if not r["correct"]]

    # CONTAMINATION GUARD. Three runs of this eval have now been invalidated by
    # infrastructure failure masquerading as product behaviour (Gemini quota,
    # then Groq key exhaustion — 23 exhausted calls in one run, each of which
    # answer() would once have reported as a confident abstention). Both now
    # surface as confidence "error", so the eval can detect its own
    # contamination rather than waiting for a human to notice the timings look
    # odd. A contaminated run reports NO rates at all: a number that must be
    # remembered as untrustworthy will eventually be trusted.
    errors = [r for r in neg_rows + pos_rows if r["confidence"] == "error"]
    contaminated = bool(errors)

    result = {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "contaminated": contaminated,
        "error_rows": len(errors),
        "score_floor": SCORE_FLOOR,
        "abstention_rate": (None if contaminated else
                            round(abstained / len(neg_rows), 3) if neg_rows else None),
        "answer_rate": (None if contaminated else
                        round(answered / len(pos_rows), 3) if pos_rows else None),
        "abstained_at_floor": at_floor,
        "abstained_at_gate": at_gate,
        "llm_calls_saved_by_floor": at_floor,
        "mean_seconds": round(sum(r["seconds"] for r in pos_rows + neg_rows)
                              / max(len(pos_rows) + len(neg_rows), 1), 2),
        "negatives": neg_rows,
        "positives": pos_rows,
    }

    print(f"\n{'='*64}")
    if contaminated:
        print(f"  ❌ CONTAMINATED RUN — {len(errors)}/{len(neg_rows)+len(pos_rows)} "
              f"queries hit an infrastructure failure (confidence 'error').")
        print("     Rates deliberately NOT reported: they would measure quota,")
        print("     not product behaviour. Re-run when the provider recovers.")
        for r in errors[:5]:
            print(f"       {r['company']}: {r['query'][:56]}")
        if len(errors) > 5:
            print(f"       ... and {len(errors)-5} more")
    else:
        print(f"  abstention rate  {abstained}/{len(neg_rows)} "
              f"({result['abstention_rate']:.0%})   — correctly said 'no evidence'")
        print(f"  answer rate      {answered}/{len(pos_rows)} "
              f"({result['answer_rate']:.0%})   — answered when it could")
        print(f"  abstained at floor {at_floor} (free) | at citation gate {at_gate} (1 call each)")
    print(f"  mean latency     {result['mean_seconds']}s")
    if false_abstain:
        print(f"\n  ⚠️  {len(false_abstain)} false abstentions (corpus HAS the answer):")
        for r in false_abstain:
            print(f"     [{r['abstained_at']}] {r['company']}: {r['query'][:60]}")
    print(f"{'='*64}")

    os.makedirs("eval/results", exist_ok=True)
    path = (f"eval/results/abstention_eval_{label}_"
            f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"saved -> {path}")
    return result


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "baseline")
